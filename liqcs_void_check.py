from osgeo import gdal_array, ogr, gdal
from typing import Union
import numpy as np
import getopt
import glob
import sys
import os

from liqcs_const import Strings

# constants
BUFFER_2300 = 2300
VOID_THRESHOLD_500 = 500
MASK_SHP_FILENAME = "mask.shp"
CSV_FILENAME = "voids_summary.csv"
CSV_COLUMNS = 'filename, size of void (pixels)'


def void_compute(grid: str, out_dir: str, mask: ogr.Layer = None, write: bool = False) -> int:
    """
    Create raster data used for void computation using vector mask.


    This utility is intended to flag or alert analysts to potential systematic voids
    present in lidar data.

    Function accepts a density grid derived from lidar, and a vector geometry mask
    produced from create_mask(). The function will use this information to compute
    the sum of suspicious voided areas present in the gridded lidar data.

    @precondition: User SHOULD execute create mask before running void_compute()
    @precondition: User must provide a density grid (preferably derived from last return points).
    @param grid: Path to density grid file.
    @param out_dir: Directory to write results to.
    @param mask: shapefile output from create_mask()
    @param write: Control whether void grids are written to disk.

    @return: Computed void area in square units
    """

    filename = grid.split('\\')[-1][:-14]
    out_path = os.path.join(out_dir, f"{filename}_voids.tif")

    grid1 = gdal.Open(grid, gdal.GA_ReadOnly)  # Read the density grid
    band = grid1.GetRasterBand(1)  # extract raster band from density grid
    wkt = grid1.GetProjection()  # extract projection from density grid
    band_array = gdal_array.BandReadAsArray(band)  # read raster band as an array

    # Anywhere density > 0 is set to 1, else unchanged
    data_out = np.where(band_array > 0, 1, band_array)
    data_out[0:20] = 1
    data_out[-20::] = 1
    data_out[:, 0:20] = 1
    data_out[:, -20::] = 1

    driver = gdal.GetDriverByName(
        "GTiff" if write else "MEM"
    )  # Create Geotiff driver object

    # Create new geotiff file object with same dimensions and data-type as input file
    ds_out = driver.Create(
        out_path if write else "",
        grid1.RasterXSize, grid1.RasterYSize, 1, band.DataType
    )

    gdal_array.CopyDatasetInfo(grid1, ds_out)   # copy properties of density grid to new output raster
    ds_out.SetProjection(wkt)                   # set projection for output raster
    band_out = ds_out.GetRasterBand(1)          # set number of bands for new raster

    # write new information to blank raster
    gdal_array.BandWriteArray(band_out, data_out)
    gdal.SieveFilter(band_out, None, band_out, 25, connectedness=8)
    if mask is not None:
        gdal.RasterizeLayer(ds_out, [1], mask, burnValues=[1])

    # filter out peppery void areas smaller than 9x9 pixels
    sieve_band = ds_out.GetRasterBand(1)
    sieve_array = gdal_array.BandReadAsArray(sieve_band)

    # calculate number of pixels missing from the raster
    void_area = int(np.size(sieve_array) - np.sum(sieve_array))

    # flush data to output
    band_out.FlushCache()

    # close the datasource(s)
    grid1, ds_out = None, None

    return void_area


def void_mask(breaklines: str = None, aoi: str = None, out_dir: str = None) -> Union[ogr.Layer, None]:
    """
    Create new vector geometry and write to shapefile.

    This program creates a mask made from a cutout of the AOI within
    the bounding box of the AOI, and the breaklines. It is intended to be
    used with void detection tool within the lidar Quality Control Suite
    (LiQCs).

    @param breaklines: Path to shapefile containing vector geometry of water bodies.
    @param aoi: Path to shapefile containing vector geometry of AOI.
    @param out_dir: Output directory for resulting shapefile
    """

    if (breaklines is None) or (aoi is None):
        return None

    driver = ogr.GetDriverByName("ESRI Shapefile")  # Create driver object
    in_ds = driver.Open(aoi, 0)  # open shapefile in read mode
    in_layer = in_ds.GetLayer()  # call get layer method (mandatory)
    in_breaks = driver.Open(breaklines, 0)  # open shapefile in read mode
    breaks_layer = in_breaks.GetLayer()  # call get layer method (mandatory)
    out = os.path.join(out_dir, MASK_SHP_FILENAME)  # define output name

    # steal prj file from input and write new one for output
    prj_file = f"{os.path.splitext(aoi)[0]}.prj"  # define prj file out name
    with open(prj_file, "r") as f:  # context manager
        contents = f.read()  # read contents
        prj = open(os.path.splitext(out)[0] + ".prj", "w+")  # open new prj file
        prj.write(contents)  # write contents to new file
        prj.close()  # close new file

    # collect bounding geometry
    bounds_list = []  # empty list for bounds
    geom_list = []  # empty list for feature geometry
    for feature in in_layer:  # for geometry feature in layer
        geom = feature.GetGeometryRef()  # not sure what this does yet
        geom_list.append(geom.GetGeometryRef(0).GetPoints())
        bounds_list.append(geom.GetEnvelope())  # get bounds of each geometry feature

    # Create multipolygon of all bounding boxes with cut outs of the geometry they bound
    multipolygon = ogr.Geometry(ogr.wkbMultiPolygon)  # define empty multipolygon
    out_ring = ogr.Geometry(ogr.wkbLinearRing)  # Create geometry ring object
    in_ring = ogr.Geometry(ogr.wkbLinearRing)  # define inner ring object
    poly = ogr.Geometry(ogr.wkbPolygon)  # create polygon object
    for b, g in zip(bounds_list, geom_list):  # for bounds of each geometry feature
        out_ring.AddPoint(b[0] - BUFFER_2300, b[2] - BUFFER_2300)  # add points with 2300m buffer
        out_ring.AddPoint(b[0] - BUFFER_2300, b[3] + BUFFER_2300)  # add points with 2300m buffer
        out_ring.AddPoint(b[1] + BUFFER_2300, b[3] + BUFFER_2300)  # add points with 2300m buffer
        out_ring.AddPoint(b[1] + BUFFER_2300, b[2] - BUFFER_2300)  # add points with 2300m buffer
        out_ring.AddPoint(b[0] - BUFFER_2300, b[2] - BUFFER_2300)  # close polygon on beginning point
        for p in g:  # for vertices in geometry
            in_ring.AddPoint(p[0], p[1])  # add vertex to inner ring
        poly.AddGeometry(out_ring)  # Polygon inherits outer ring geometry
        poly.AddGeometry(in_ring)  # Polygon inherits inner ring geometry
        multipolygon.AddGeometry(poly)  # add polygon to multipolygon

    # get vertices for breaklines
    break_point = []
    for feature in breaks_layer:  # for geometry feature in layer
        geom_breaks = feature.GetGeometryRef()  # not sure what this does yet
        break_point.append(geom_breaks.GetGeometryRef(0).GetPoints())

    # make polygon feature from breaklines
    multipoly_break = ogr.Geometry(ogr.wkbMultiPolygon)  # define empty multipolygon
    ring_breaks = ogr.Geometry(ogr.wkbLinearRing)  # define inner ring object
    poly_breaks = ogr.Geometry(ogr.wkbPolygon)  # create polygon object
    for t in break_point:
        for p in t:
            ring_breaks.AddPoint(p[0], p[1])
        poly_breaks.AddGeometry(ring_breaks)
        multipoly_break.AddGeometry(poly_breaks)

    # calculate union for breaks and bounds with AOI hole cutout
    union = multipolygon.Union(multipoly_break)

    # save bounds
    out_driver = ogr.GetDriverByName("Memory")

    # Remove output shapefile if it already exists
    if os.path.exists(out):
        out_driver.DeleteDataSource(out)

    # create the datasource for the output shapefile
    out_ds = out_driver.CreateDataSource(out)  # create datasource object
    out_layer = out_ds.CreateLayer(
        "mask", geom_type=ogr.wkbMultiPolygon
    )  # create new layer

    # add ID field
    id_field = ogr.FieldDefn("id", ogr.OFTInteger)  # define field
    out_layer.CreateField(id_field)  # create field

    # create feature and set values
    feature_defn = (out_layer.GetLayerDefn())

    feature = ogr.Feature(feature_defn)  # same as above
    feature.SetGeometry(union)  # set geometry for feature class
    feature.SetField("id", 1)  # set field for feature class
    out_layer.CreateFeature(feature)  # create new feature
    # feature = None  # remove feature from memory
    # # Save and close DataSource
    in_ds = None
    in_breaks = None

    return out_layer


def void_report(grids_path: str, out_dir: str, mask: Union[ogr.Layer, None]):

    """
    Calculate void area in a list of grid files and produces tabular report.

    @param mask: ogr.Layer generated from void_mask()
    @param grids_path: Path to directory of density grid files.
    @param out_dir: Path to write results.
    """

    void_path = os.path.join(out_dir, Strings.VOIDS)
    density_glob = glob.glob(os.path.join(grids_path, "*.tif"))

    with open(os.path.join(out_dir, CSV_FILENAME), 'a', newline='') as csv_file:
        print(CSV_COLUMNS, file=csv_file)
        for density_grid in density_glob:
            void = void_compute(density_grid, void_path, mask)
            if void > VOID_THRESHOLD_500:
                name = os.path.basename(density_grid).replace('void_', '')
                row = f"{name}, {void}"
                print(row, file=csv_file)


def cli_opts() -> list:

    """
    Get the constant for CLI options.

    @return: list of CLI options.
    """

    opts = [
            "help"
            "read_grid",
            "write_dir"
            "breaklines",
            "aoi"
        ]

    return opts


def cli_flags() -> str:

    """
    Get the constant CLI flags.

    @return: String of formatted CLI flag options.
    """

    flags = "hr:w:b:a:"

    return flags


def cli_help():

    """
    Print CLI menu to stdout.
    """

    print("\n liqcs_void_check.py -r <input.tif> -b <breaklines.shp> -a <aoi.shp> [-w <out/dir/>]")
    print("\t-r, --read_grid:\n\t\tInput density grid (TIFF format).")
    print("\t-w, --write_dir:\n\t\tOutput directory for generate vector and raster files.")
    print("\t-b, --breaklines:\n\t\tInput water delineation geometry (SHP format).")
    print("\t-a, --aoi:\n\t\tInput AOI geometry (SHP format).")

    sys.exit()


def cli(opts: list):
    """
    Handle command-line arguments.

    @param opts: Command-line passed to liqcs_grid.py
    """

    in_grid, out_dir = None, None
    aoi, breaklines = None, None

    for opt, arg in opts:

        if opt in ("-h", "--help"):
            cli_help()

        elif opt in ("-r", "--read_grid"):
            in_grid = arg

        elif opt in ("-w", "--write_dir"):
            out_dir = arg

        elif opt in ("-b", "--breaklines"):
            breaklines = arg

        elif opt in ("-a", "--aoi"):
            aoi = arg

    if (not in_grid) or (not breaklines) or (not aoi):
        print("Insufficient arguments provided...")
        cli_help()  # program will terminate

    if not out_dir:
        out_dir = os.getcwd()

    void_mask(breaklines, aoi, out_dir)
    mask_path = os.path.join(out_dir, MASK_SHP_FILENAME)
    void_area = void_compute(in_grid, out_dir, mask_path, write=False)
    las_tile = os.path.basename(in_grid).split(".")[0]
    print(f"{las_tile}\nvoid area: {void_area}")


def main(argv: list):

    opts, args = getopt.getopt(argv, cli_flags(), cli_opts())
    cli(opts)


if __name__ == "__main__":
    main(sys.argv[1:])

