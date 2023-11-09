from osgeo import ogr, os
from tkinter import filedialog
from time import sleep

"""
THIS SCRIPT CREATES A SHAPEFILE WITH 100m BUFFER BASED ON AOI SHAPEFILE
"""

def create_bufferShp_fromPointShp(inShpPath, bufferSize):

    
    buffShpPath = inShpPath.replace('.shp', '_BPA-BUFFER.shp')

    inputds = ogr.Open(inShpPath)
    inputlyr = inputds.GetLayer()

    shpdriver = ogr.GetDriverByName('ESRI Shapefile')
    if os.path.exists(buffShpPath):
        shpdriver.DeleteDataSource(buffShpPath)
    outputBufferds = shpdriver.CreateDataSource(buffShpPath)
    bufferlyr = outputBufferds.CreateLayer(buffShpPath, geom_type=ogr.wkbPolygon)
    featureDefn = bufferlyr.GetLayerDefn()

    # Create new fields in the output shp and get a list of field names for feature creation
    fieldNames = []
    for i in range(inputlyr.GetLayerDefn().GetFieldCount()):
        fieldDefn = inputlyr.GetLayerDefn().GetFieldDefn(i)
        bufferlyr.CreateField(fieldDefn)
        fieldNames.append(fieldDefn.name)

    for feature in inputlyr:
        ingeom = feature.GetGeometryRef()
        fieldVals = [] # make list of field values for feature
        for f in fieldNames: fieldVals.append(feature.GetField(f))

        outFeature = ogr.Feature(featureDefn)
        geomBuffer = ingeom.Buffer(bufferSize)
        outFeature.SetGeometry(geomBuffer)
        for v, val in enumerate(fieldVals): # Set output feature attributes
            outFeature.SetField(fieldNames[v], val)
        bufferlyr.CreateFeature(outFeature)

        outFeature = None

    # Copy the input .prj file
    from shutil import copyfile
    copyfile(inShpPath.replace('.shp', '.prj'), buffShpPath.replace('.shp', '.prj'))


    return buffShpPath

def main():
    inShpPath = filedialog.askopenfilename(title="Select Project AOI Shapefile")
    bufferSize = 100
    create_bufferShp_fromPointShp(inShpPath, bufferSize)
    print (f"\n\n << Shapefile Buffer Complete >>")
    print (f"\n\n Buffered shapefile output is now in the same folder as original AOI \n\n ")
    sleep(6)

if __name__ == '__main__':
    main()