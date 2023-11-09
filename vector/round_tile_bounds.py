from shapely.geometry import Polygon
import geopandas as gpd
from math import ceil, floor


f = R"D:\Grids\2500_grid_bc_data\BCGS_2500_GRID\BCGS2500GR_polygon.shp"

df = gpd.read_file(f)
df.crs = {'init' :'epsg:26909'}
df = df.to_crs({'init': 'epsg:3157'})


bounds = df['geometry'].bounds
print(bounds.head())

for row in range(len(df.index)):
    xmin = floor(bounds.iloc[row]['minx'])
    ymin = floor(bounds.iloc[row]['miny'])
    xmax = ceil(bounds.iloc[row]['maxx'])
    ymax = ceil(bounds.iloc[row]['maxy'])

    df['geometry'][row] = Polygon(
        [
            (xmin, ymax),
            (xmax, ymax),
            (xmax, ymin),
            (xmin, ymin),
            (xmin, ymax)
        ]
    )

print(df.head())

df.to_file(R"D:\Grids\BC_rounded_grids\2500\2500_utm10_csrs.shp")