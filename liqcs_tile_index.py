from shapely import speedups, geometry
from fiona.crs import from_epsg
from rsge_toolbox.lidar import Laszy
from rsge_toolbox.util import WktCrsInfo
import shapely.geometry
import geopandas as gpd
import pandas as pd
import laspy
import datetime
import re
import os

from liqcs_parse_header import parse_header


def tile_index(file_list: list, contract: str, out_dir: str):

    """
    Write tile index geometry to a gpkg file.

    @param file_list: List of LAS/LAZ files.
    @param epsg: Output EPSG code.
    @param contract: Contract number of project (?)
    @param out_dir: Output directory.
    """

    gdf = gpd.GeoDataFrame(columns=["map_tile", "file", "geometry", "contract_number"])
    tiles = [bounding_box(f) for f in file_list]
    contract_list = [contract] * len(file_list)
    gdf = append_to_gdf(tiles, file_list, gdf, contract_list)

    out_dir = out_dir + '/Tile_Index/'
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    os.chdir(out_dir)

    fileByEpsg = getProjectionsFromInput(file_list, out_dir)
    __write_tile_index(fileByEpsg, contract, out_dir, gdf)


def bounding_box(file: str) -> shapely.geometry.Polygon:

    """
    Create shapely.geometry.Polygon from input LAS/LAZ file.

    @param file: input LAS/LAZ file.
    @return: shapely.geometry.Polygon object representing bounding box of input file.
    """

    # parse las/laz header body
    hdr = parse_header(file, verbose=False)

    # gt min/max from las/laz header
    xmin, xmax, ymin, ymax = [hdr['xmin'], hdr['xmax'], hdr['ymin'], hdr['ymax']]

    # Create polygon from bounding box of las file
    speedups.disable()
    bbox_poly = geometry.Polygon(
        [
            (xmin, ymax),
            (xmax, ymax),
            (xmax, ymin),
            (xmin, ymin),
            (xmin, ymax),
        ]
    )

    return bbox_poly


def append_to_gdf(geom_list: list, file_list: list, gdf: gpd.GeoDataFrame, contract: list[str]) -> gpd.GeoDataFrame:

    """

    @param geom_list: List of bounding box geometries.
    @param file_list: List of filenames.
    @param gdf: GeoDataFrame to append to.
    @param contract: Contract number of project (?)
    @return: GeoDataFrame with appended geometries and other fields.
    """

    for geom, file, contract_number in zip(geom_list, file_list, contract):

        filename = os.path.basename(file)
        tile = filename[3:16]

        # append to dataframe
        gdf = pd.concat(
            [
                gdf, gpd.GeoDataFrame.from_records(
                    [
                        {
                            "map_tile": tile, "file": file,
                            "geometry": geom, "contract_number": contract_number
                        }
                    ]
                )
            ], ignore_index=True)

    return gdf

def getProjectionsFromInput(file_list: list, out_dir: str):
    fileByEpsg={}
    projectionsNotFound = []
    
    for file in file_list:
        las = Laszy.Laszy(file, read_points=False)
        wkt_str = las.get_crs_info()
        crsinfo = WktCrsInfo.WktCrsInfo(wkt_str)
        epsg = crsinfo.get_proj_epsg()
        
        if epsg == -1:
            projectionsNotFound.append(file)
            continue
        
        if epsg not in fileByEpsg:
            fileByEpsg[epsg] = []
        fileByEpsg[epsg].append(file)

    if len(projectionsNotFound) > 0:
        with open(os.path.join(out_dir,"files_with_projection_errors.txt"), 'w+') as errFile:
            errFile.write("The projection data could not be found for the following file(s):\n")
            for file in projectionsNotFound:
                errFile.write(f'\n{file}')
    return fileByEpsg


def __write_tile_index(fileByEpsg: dict, contract: str, out_dir: str, tile_gdf: gpd.GeoDataFrame):

    """
    @param contract:
    @param out_dir:
    @param tile_gdf:
    @param epsg_code:
    @return:
    """

    for epsg in fileByEpsg:
        out_name = f"tile_index_{contract}_{datetime.date.today()}.gpkg"
        tile_gdf.crs = from_epsg(epsg)
        bbox_tiles_gpkg = os.path.join(out_dir, out_name)
        tile_gdf.to_file(bbox_tiles_gpkg, layer=str(epsg), driver='GPKG')
