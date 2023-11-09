"""
Written by Brett Edwards
Updates by Natalie Jackson

Masks density grids outside a project area via provided shapefile
and water inside the project area using Freshwater Atlas BCGW data,
so that density values in the masked areas will be ignored during
analysis.
"""
# ------------------------------------------------------------------------------
# TODO:
#   - add option to use non fwa polys (e.g. breaklines provided by vendor)
#   - add first try option to use bcdata to download FWA polygons before trying
#       BCGW (I believe bcdata module is faster than connecting to BCGW..)
#           - https://github.com/smnorris/bcdata
#               (we have this module in our environment!)
#           - This option requires updating code to query whatever form
#               of database (geodataframe, etc) rather than oracle query
#               (could be a fair wee bit of work).
# ------------------------------------------------------------------------------


from typing import List, Tuple
import oracledb
import fiona
from pyproj import Transformer, CRS, Proj
from shapely.geometry import shape, mapping, Polygon
from shapely import wkt
from shapely.ops import transform
import os
import shutil
import tqdm
import pickle
import rasterio as rio
from rasterio.mask import mask
import numpy as np
import warnings

# Local imports
try:
    # Use this version of importing (in the try clause) when running from
    # liqcs_gui.py
    import density_analysis.density_analysis_config as density_analysis_config
except Exception:
    # Use this version of importing (in the except clause) when running from
    # density_analysis subfolder scripts (e.g., density_analysis_main.py)
    import density_analysis_config

# ------------------------------------------------------------------------------
# Paths to test data folders
# ------------------------------------------------------------------------------


class TestFolders():
    def __init__(self):
        """
        Define and create folders for testing.
        """
        self.TEST_DATA_FOLDER = density_analysis_config.test_data_folder()

        self.INPUT_FOLDER = density_analysis_config.test_input_folder()

        self.WATER_INPUT = os.path.join(
            self.INPUT_FOLDER,
            "WATER"
        )

        # If any of the test data folders don't exist, make them!
        for folder in (
            self.TEST_DATA_FOLDER,
            self.INPUT_FOLDER,
            self.WATER_INPUT,
        ):
            if not os.path.isdir(folder):
                os.mkdir(folder)


def _pickled_water_polys():
    pickled_water_polys = os.path.join(
        TestFolders().WATER_INPUT,
        "water_polygons.pkl"
    )
    return pickled_water_polys


# ------------------------------------------------------------------------------
# Water polygons used to mask rasters
# (we don't want to check density of water areas)
# ------------------------------------------------------------------------------

# Freshwater Atlas layers in the BCGW, polygons covering water features in BC
BCGW_FWA_LAYERS = [
    "WHSE_BASEMAPPING.FWA_LAKES_POLY",
    "WHSE_BASEMAPPING.FWA_RIVERS_POLY",
    "WHSE_BASEMAPPING.FWA_MANMADE_WATERBODIES_POLY",
]

# Ocean shapefile created by Brett and Spence
# by downloading a land layer from BCGW with lots of island detail (which one?)
# and clipping the land from a larger polygon that covered the extents of BC,
# creating a polygon representing the ocean.
# TODO: add option to automate creating this polygon with updated land data?
top_common_path = R'\\sfp.idir.bcgov\s164\S63063\ILMB_CRIM_BMGS\PBA\Top_Common'
LOCAL_WATER_LAYERS = [
    os.path.join(
        top_common_path,
        'PYTHON_SETUP',
        'density_analysis_script_supporting_files',
        'BC_Ocean_shp',
        'BC_Ocean.shp'
    )
]


# ------------------------------------------------------------------------------
# Filter warnings
# ------------------------------------------------------------------------------

def filter_user_warnings(warning_action):
    """
    If the warning action is 'ignore',
    UserWarnings will be hidden.

    UserWarnings will happen when a raster is not within a polygon.

    Args:
        warning_action (string):
            Options: 'default', 'error', 'ignore', 'always', 'module', or 'once'.
            More info: https://docs.python.org/3/library/warnings.html
    """
    # Filter UserWarnings according to warning_action (e.g., 'ignore'),
    # which occur when a raster is not within a polygon
    warnings.filterwarnings(
        warning_action, category=UserWarning
    )


# ------------------------------------------------------------------------------
# Functions
# ------------------------------------------------------------------------------

def identify_water_polys_in_project_areas(
    db_connection: oracledb.Connection,
    project_area_polygons: List[Polygon],
    outdir: str,
    pickle_filtered_water_polys=False
) -> List[Polygon]:
    """
    Identify which water polygons from the BCGW
    fall within the project areas,
    and include the ocean too.

    Args:
        db_connection (oracledb.Connection):
            - Oracle database connection object
        project_area_polygons (List[Polygon]):
            - List of shapely.geometry Polygon objects
                representing the project area.
        outdir (str):
            - Path to the main output directory for the density checker
        pickle_filtered_water_polys (bool) (Optional, default False):
            - Switch to make a pickle file of the filtered water polygons
                to use again by a later run of this script.

    Returns:
        water_polygons (List[Polygon]):
            - List of shapely.geometry Polygon objects
                representing the water polygons that
                intersect the project area polygons.
    """
    print(
        f"\nIdentifying polygons from the Freshwater Atlas "
        f"on the BCGW that fall within the project area."
        f"\n\tQuerying layers: {*BCGW_FWA_LAYERS,}")
    water_polygons = []
    for polygon in tqdm.tqdm(project_area_polygons):
        bounds = get_shapely_bounds_albers(polygon)
        for layer in BCGW_FWA_LAYERS:
            db_result = spatial_query_bcgw(db_connection, bounds, layer)
            polygons = create_polygon_list_from_sql(db_result)
            water_polygons.extend(polygons)
    local_water_polygons = read_shapefiles_to_albers(LOCAL_WATER_LAYERS)
    water_polygons.extend(local_water_polygons)

    # TODO: do we want the water polygons as part of the final output?
    # If yes, uncomment the following:
    '''
    # Make a folder in the output directory to save the water polygon shapefile
    # filtered_fwa_polygons_dir = os.path.join(outdir, "MASKS", "WATER")
    if not filtered_fwa_polygons_dir:
        os.makedirs(filtered_fwa_polygons_dir)

    # Save the water polygons to a shapefile as part of the final output
    # of the density checker.
    # TODO make it a geopackage instead of a shapefile?
    write_to_file(water_polygons, filtered_fwa_polygons_dir)
    '''

    # Save the polygons to use again for testing this script
    if pickle_filtered_water_polys:
        pickled_water_polys = _pickled_water_polys()
        pickle.dump(water_polygons, open(pickled_water_polys, "wb"))

    return water_polygons


def get_shapely_bounds_albers(shapely_polygon: Polygon) -> Tuple[float]:
    """
    Get bounding coordinates of a shapely.geometry
    Polygon object.

    Args:
        shapely_polygon: A shapely.geometry Polygon object

    Returns:
        xmin, ymin, xmax, ymax (tuple of float values)
    """
    xmin, ymin, xmax, ymax = shapely_polygon.bounds

    return xmin, ymin, xmax, ymax


def spatial_query_bcgw(
    db_connection: oracledb.Connection,
    query_bounds: Tuple[float],
    bcgw_layer: str,
):
    """
    Performs a spatial query on a BCGW table,
    limited to the coordinate bounds provided.
    Coordinates should be BC Albers (EPSG:3005).

    Args:
        db_connection (cx_Oracle.Connection or oracledb.Connection):
            - Oracle database connection object
        query_bounds (tuple of float values):
            - Bounding coordinates within which to perform query
        bcgw_layer (str):
            - Name of BCGW layer to query

    Returns:
        result (list):
            - List of polygons in WKT format within BCGW that
                intersect/overlap the bounding box described
                by the query bounds.
    """
    xmin, ymin, xmax, ymax = query_bounds

    sdo_geom = (
        "SDO_GEOMETRY(2003, 3005, NULL, "
        "SDO_ELEM_INFO_ARRAY(1,1003,3), "
        f"SDO_ORDINATE_ARRAY({xmin}, {ymin}, {xmax}, {ymax}))"
    )

    cursor = db_connection.cursor()

    query = f"""
    SELECT SDO_UTIL.TO_WKTGEOMETRY(GEOMETRY)
    FROM {bcgw_layer} l
    WHERE SDO_RELATE(l.geometry,
    {sdo_geom}, 'mask=anyinteract') = 'TRUE'
    """

    result = cursor.execute(query).fetchall()

    return result


def create_polygon_list_from_sql(bcgw_query_result) -> List[Polygon]:
    """
    Uses Oracle query result to create Shapely polygons

    Args:
        bcgw_query_result (list):
            - List of WKT format polygons

    Returns:
        List[Polygon]:
            - List of same polygons as shapely.geometry.Polygon
                objects
    """
    polygons = []

    for geometry in bcgw_query_result:
        polygon = wkt.loads(str(geometry[0]))
        if polygon.geom_type.lower() == "polygon":
            polygons.append(polygon)
        elif polygon.geom_type.lower() == "multipolygon":
            multipoly = list(polygon.geoms)
            polygons.extend(multipoly)
        else:
            print("Couldnt convert")

    return polygons


def read_shapefile_to_albers(shapefile: str) -> List[Polygon]:
    """
    Reads shapefile path and creates a list of Shapely polygons,
    transformed to BC Albers, which is the main CRS of the BCGW.
    """
    polygons = []

    with fiona.open(shapefile) as shp:
        wkt = shp.crs_wkt
        original_crs = CRS.from_wkt(wkt)
        epsg = original_crs.to_epsg()
        albers_epsg = 3005
        if epsg != albers_epsg:
            nad83_3005 = CRS.from_epsg(albers_epsg)
            transformer = Transformer.from_crs(
                original_crs,
                nad83_3005,
                always_xy=True
            ).transform
        for record in shp:
            polygon = shape(record["geometry"])
            if epsg != albers_epsg:
                polygon = transform(transformer, polygon)

            if polygon.geom_type.lower() == "polygon":
                polygons.append(polygon)
            elif polygon.geom_type.lower() == "multipolygon":
                multipoly = list(polygon.geoms)
                polygons.extend(multipoly)

    return polygons


def read_shapefiles_to_albers(list_of_shapefiles: List[str]) -> List[Polygon]:
    """
    Reads a list of shapefile paths and
    creates a list of Shapely polygons,
    transformed to BC Albers.

    Also converts polygon coordinates to 2D
    if they are 3D to cooperate with
    Rasterio's Mask method.
    """
    polygons = []

    for shp in list_of_shapefiles:
        polygon = read_shapefile_to_albers(shp)
        polygons.extend(polygon)

    for idx, poly in enumerate(polygons):
        if polygon_is_3d(poly):
            poly_2d = convert_polygon_to_2d(poly)
            polygons[idx] = poly_2d

    return polygons


def polygon_is_3d(polygon: Polygon) -> bool:
    """
    Check if a polygon is 3D.

    Args:
        polygon (Polygon):
            - Shapely polygon

    Returns:
        (bool):
            - True if polygon is 3D, False if not.
    """
    d3 = False

    if len(polygon.exterior.coords[0]) == 3:
        d3 = True

    return d3


def convert_polygon_to_2d(polygon: Polygon) -> Polygon:
    """
    Convert polygon from 3D to 2D.

    Args:
        polygon (Polygon):
            - 3D Shapely polygon

    Returns:
        polygon (Polygon):
            - 2D Shapely polygon
    """
    poly_2d = transform(lambda x, y, z: (x, y), polygon)
    return poly_2d


def write_to_file(polygons: List[Polygon], water_dir: str):
    """
    Write list of Shapely polygons to a shapefile with
    BC Albers NAD83 projection (EPSG 3005)
    in the water mask directory.

    Args:
        polygons (list):
            - List of Shapely polygons
        water_dir (str):
            - folder in which to save output
    """
    schema = {
        "geometry": "Polygon",
    }

    water_polygons_shapefile = os.path.join(water_dir, "water_polygons.shp")

    with fiona.open(
        water_polygons_shapefile,
        "w",
        driver="ESRI Shapefile",
        schema=schema,
        crs="epsg:3005"  # BC Albers
    ) as output:
        print(f"Writing to {water_polygons_shapefile}")
        if type(polygons) is list:
            for poly in polygons:
                output.write({"geometry": mapping(poly)})
        else:
            output.write({"geometry": mapping(polygons)})


def transform_polygons_to_raster_crs(
    open_geotiff, polygons: List[Polygon]
) -> List[Polygon]:
    """
    Transform list of Shapely polygons
    to the same CRS as the provided raster,
    which has been read with rasterio.

    Args:
        open_geotiff (_type_): _description_
        polygons (List[Polygon]): _description_

    Returns:
        List[Polygon]: _description_
    """
    transformed_polygons = []

    epsg = open_geotiff.crs
    transformer = Transformer.from_crs("epsg:3005", epsg)

    for polygon in polygons:
        transformed_polygon = transform(transformer.transform, polygon)
        transformed_polygons.append(transformed_polygon)

    return transformed_polygons


def mask_all_density_grids(
    outdir: str,
    density_grids: List[str],
    project_area_polygons: List[Polygon],
    water_polys_in_project_areas: List[Polygon]
) -> List[Tuple[str, np.ndarray]]:
    """
    Mask a list of rasters using project areas and
    water polygons.

    Args:
        outdir (str):
            - Path to directory to save outputs.
        density_grids (List[str]):
            - List of paths of density rasters.
        project_area_polygons (List[Polygon]):
            - List of shapely polygons representing the project area (AOI).
        water_polys_in_project_areas (List[Polygon]):
            - List of shapely polygons representing water in the project area.

    Returns:
        list of tuples:
            Tuple elements:
                0 (str): Path of original density grid
                1 (array):
                    Array representing raster, according to rasterio conventions
                    Array shape: (1, num_x_cells, num_y_cells).
                    First value of array shape (1) indicates raster has one
                    value per cell.
                2 (np.dtype):
                    Data type of the original raster values as read by rasterio
                    into numpy array.
    """
    print("\nMasking water from project areas...")

    all_density_values = []

    for grid in density_grids:
        density_values, original_data_type = mask_density_grid(
            outdir, grid, project_area_polygons, water_polys_in_project_areas
        )
        all_density_values.append((grid, density_values, original_data_type))

    return all_density_values


def mask_density_grid(
    outdir: str,
    geotiff_file: str,
    project_polygons: List[Polygon],
    water_polygons: List[Polygon]
) -> np.ndarray:
    """
    Mask density grid, removing area outside the project area
    and area inside the water polygons.

    Writes masked rasters to Geotiff for verification of removed water.

    Args:
        outdir (str):
            - Path to directory for outputs.
        geotiff_file (str):
            - Path to input raster.
        project_polygons (List[Polygon]):
            - List of shapely polygons representing project area (AOI)
        water_polygons (List[Polygon]):
            - List of shapely polygons representing water within AOI.

    Returns:
        (np.array):
            - Array representing raster, according to rasterio conventions
                Array shape: (1, num_x_cells, num_y_cells).
                First value of array shape (1) indicates raster has one
                value per cell.

    """
    fname = os.path.basename(geotiff_file)
    masked_grids_dir = os.path.join(
        density_analysis_config.density_analysis_results_dir_path(outdir),
        "DENSITY_GRIDS_MASKED"
    )

    with rio.open(geotiff_file) as density_grid:
        nodata = density_grid.nodata

        # If the density grid's CRS isn't BC Albers NAD83,
        # project the masking polygons into the same CRS
        # as the density grid.
        if density_grid.crs != "EPSG:3005":
            t_project_polygons = transform_polygons_to_raster_crs(
                density_grid, project_polygons
            )
            t_water_polygons = transform_polygons_to_raster_crs(
                density_grid, water_polygons
            )
        else:
            t_project_polygons = project_polygons
            t_water_polygons = water_polygons

        metadata = density_grid.meta
        proj_mask_grid, out_transform = mask(
            density_grid, t_project_polygons, all_touched=True, invert=False
        )

    temp_dir = density_analysis_config.temp_dir(outdir)

    temp_raster = os.path.join(
        temp_dir,
        "temp.tif"
    )

    # Write the raster masked to the project area
    # (use the metadata from the original raster)
    with rio.open(temp_raster, "w", **metadata, compress="LZW") as dest:
        dest.write(proj_mask_grid)

    # Mask the raster with the water polygons, and read the file into
    # a new rasterio object (water_mask_grid), bringing the
    # original metadata along to use again.
    with rio.open(temp_raster) as density_grid:
        water_mask_grid, out_transform = mask(
            density_grid, t_water_polygons, all_touched=True, invert=True
        )
        metadata = density_grid.meta

    # Delete temporary directory and the temp.tif file inside it.
    shutil.rmtree(temp_dir)

    # Check if all values of the masked raster are null
    all_values_nan = np.all(water_mask_grid == nodata)

    if not all_values_nan:
        # If there are some non-null values, make a new file path
        # for the new, masked raster
        if not os.path.isdir(masked_grids_dir):
            os.mkdir(masked_grids_dir)
        final_raster = os.path.join(
            masked_grids_dir,
            f"{os.path.splitext(fname)[0]}_"
            f"{density_analysis_config.string_signifying_masked_raster()}.tif"
        )
        # Write the masked raster, using the metadata
        # from the original raster.
        with rio.open(final_raster, "w", **metadata, compress="LZW") as dest:
            print(f"\n\tWriting masked raster:\n\t\t{final_raster}")
            dest.write(water_mask_grid)
    else:
        print(
            f"\t{fname} contains only NODATA after masking. Masked raster creation skipped."
        )

    water_mask_grid, original_data_type = array_to_float64(water_mask_grid)

    water_mask_grid = replace_nodata_in_array(water_mask_grid, nodata)

    return water_mask_grid, original_data_type


def array_to_float64(data_array):
    """
    Cast any non-gdal-float-data types as float64.
    Return the array as float64, and the original data type.

    Args:
        data_array (_type_): _description_
    """
    original_data_type = data_array.dtype

    acceptable_data_types = density_analysis_config.acceptable_raster_value_data_types()

    if original_data_type not in acceptable_data_types:
        data_array = data_array.astype(np.float64)

    return data_array, original_data_type


def replace_nodata_in_array(data_array: np.ndarray, nodata: int) -> np.ndarray:
    """
    Fills array with np.NaN where there
    are nodata values ex. -9999, -32768

    Args:
        data_array (np.ndarray):
            - Array representing denstiy raster with float values
        no_data (int):
            - Value in original raster representing null/no-value/not-a-number
                to be converted to np.nan.

    Returns:
        data_array (np.ndarray):
            - Array with nodata values replaced with np.nan.
    """
    data_array[data_array == nodata] = np.nan

    return data_array


def _pickle_density_values(outdir, density_values):
    """
    Pickle density values to a file in the output directory.
    Useful for testing downstream modules, otherwise not required.

    Args:
        outdir (str):
            - Path to directory in which to save pickle file
        density values (list):
            - List of tuples containing masked raster path
                and associated rasterio array
    """
    # Write output to pickle file to use to test downstream modules.
    pickled_density_values = os.path.join(outdir, "density_values.pkl")
    pickle.dump(density_values, open(pickled_density_values, "wb"))


# ------------------------------------------------------------------------------
# Primary function this module (mask_lidar_density_rasters.py)

def run(
    density_grids,
    outdir,
    project_areas_list,
    bcgw_credentials,
    use_new_water_polys=True,
    pickle_filtered_water_polys=False,
    pickle_density_values=False
):
    """
    Mask a list of lidar density rasters by project areas
    and water polygons.

    Create an array representing the density values of each
    masked raster.

    Args:
        density_grids (list of str):
            - List of paths to density grids to mask
        outdir (str):
            - Path to directory for outputs.
        project_areas_list (list of str):
            - List of paths to project area shapefiles.
        bcgw_credentials (tuple of 2 strings):
            Tuple elements:
                0 (str): BCGW username
                1 (str): BCGW password
        use_new_water_polys (bool, optional):
            - Option to connect to the BCGW to download new water polygons,
                versus using a previously pickled file.
            - Defaults to True.
        pickle_filtered_water_polys (bool, optional):
            - Option to save water polygons to a pickle file to use again later,
                if the use_new_water_polys switch is off.
            - Defaults to False.
        pickle_density_values (bool, optional):
            - Option to save density values to a pickle file to use for later
                testing of downstream modules.
            - Defaults to False.

    Returns:
        density_values (list of tuples):
            Tuple elements:
                0 (str): Path of original density grid
                1 (array):
                    Array representing raster, according to rasterio conventions
                    Array shape: (1, num_x_cells, num_y_cells).
                    First value of array shape (1) indicates raster has one
                    value per cell.
    """
    # --------------------------------------------------------------------------
    # Hide UserWarnings which will happen when a raster is not within a polygon

    filter_user_warnings("ignore")

    # --------------------------------------------------------------------------
    # Convert list of shapefiles to list of Shapely polygons in BC Albers NAD83
    project_area_polygons = read_shapefiles_to_albers(project_areas_list)

    # use_new_water_polys will only be False in testing situations.
    # bcgw_credentials will be None only in testing situations,
    # specifically, if sam_testing in liqcs_gui.py is set to True.
    if use_new_water_polys and bcgw_credentials:
        # Connect to BCGW
        with density_analysis_config.get_bcgw_connection(bcgw_credentials) as conn:
            # Identify which water polygons fall within the project areas
            water_polys_in_project_areas = identify_water_polys_in_project_areas(
                conn,
                project_area_polygons,
                outdir,
                pickle_filtered_water_polys=pickle_filtered_water_polys
            )

    else:
        # Only use this pickle file for test purposes to avoid needing to
        # connect to BCGW and query layers
        water_polys_in_project_areas = pickle.load(
            open(_pickled_water_polys(), "rb")
        )

    # --------------------------------------------------------------------------
    # Mask water from project areas

    # density_values is a list of tuples:
    # [( path to masked raster, array of density values, original data type), ... ]
    density_values = mask_all_density_grids(
        outdir,
        density_grids,
        project_area_polygons,
        water_polys_in_project_areas
    )

    if pickle_density_values:
        # Pickle density values, to use by analyze_density.py
        # in case we want to run that script without running this one again.
        # (The pickle file will be saved in the outdir)
        _pickle_density_values(outdir, density_values)

    return density_values


def main():
    # --------------------------------------------------------------------------
    # Test condition switches
    # --------------------------------------------------------------------------

    # If test_io is False, the script will ask for a path to the density grids
    # and a path to save outputs.
    # If test_io is True, this script will look for density grids in
    # the test data folder, and create a test_output folder in the same
    # location.
    # (test_io is only True in testing scenarios)
    test_io = False

    # Delete previous test ouput files
    # (deletes folders in the test area starting with "TEST_OUTPUTS_")
    # Can only be True if test_io is True.
    delete_previous_test_outputs = False

    # Only use input density grids that are in the "LIMIT_INPUTS subfolder"
    # Only relevant if test_io is True.
    limit_inputs = False

    # If use_new_water_polys is True,
    # connect to BCGW and query layers.
    # If false, use previously pickled polys.
    # (only False in testing scenarios -- faster than re-connecting to BCGW & querying)
    # Independently relevant. (Doesn't matter if other switches are True or False)
    use_new_water_polys = True

    # if connected to BCGW, save the query output to a pickle file
    # to use on a later run of the script
    # One relevant if use_new_water_polys is True.
    pickle_filtered_water_polys = False

    # Pickle the outputs of this script to use by analyze_density.py,
    # so the next time we want to independently run analyze_density.py
    # we don't need to run this script first.
    # Independently relevant. (Doesn't matter if other switches are True or False)
    pickle_density_values = False

    # --------------------------------------------------------------------------
    # Input rasters
    input_dir = density_analysis_config.specify_input_dir(
        test_io=test_io,
        limit_inputs=limit_inputs
    )

    input_density_raster_list = density_analysis_config.get_density_raster_list(
        input_dir
    )

    # --------------------------------------------------------------------------
    # Project areas

    project_areas_dir = density_analysis_config.specify_project_areas_dir(
        test_io=test_io
    )

    project_areas_list = density_analysis_config.get_project_areas_list(
        project_areas_dir
    )

    # --------------------------------------------------------------------------
    # Output directory

    outdir = density_analysis_config.specify_output_dir(
        test_io=test_io,
        delete_previous_test_outputs=delete_previous_test_outputs
    )

    # --------------------------------------------------------------------------
    # BCGW credentials (including input validation)

    bcgw_connection = None
    while not bcgw_connection:
        bcgw_credentials = density_analysis_config.specify_bcgw_credentials()
        bcgw_connection = density_analysis_config.get_bcgw_connection(
            bcgw_credentials)
    bcgw_connection.close()

    # --------------------------------------------------------------------------
    # Send all that info to primary function of this module

    run(
        input_density_raster_list,
        outdir,
        project_areas_list,
        bcgw_credentials=bcgw_credentials,
        use_new_water_polys=use_new_water_polys,
        pickle_filtered_water_polys=pickle_filtered_water_polys,
        pickle_density_values=pickle_density_values
    )


if __name__ == "__main__":
    main()
