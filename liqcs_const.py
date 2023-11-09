# ===============================================================
# -- LiQCS test indices
# ===============================================================
class LiqcsTests:

    """
    Index values indicating the order and value of in tests in LiQCS GUI.

    @param FILE_NAMING: 1
    @param SHAPEFILE_CHECK = 2
    @param TILE_INDEX = 3
    @param TRAJ_TO_GPKG = 4
    @param LASZY = 5
    @param LIDAR_SUMMARY = 6
    @param QC_PREP = 7
    @param VOID_GRID = 8
    @param DENSITY_ANALYSIS = 9
    @param LIDAR_EXTENTS = 10
    @param GRID_INTENSITY = 11
    @param GRID_LAST_RETURN = 12
    @param GRID_DENSITY_CLASS = 13
    """

    # The Order in which tests ran in liqcs.py and displayed in 
    # liqcs_gui.py's main_gui and edit_queue test checkboxes.
    FILE_NAMING = 1
    SHAPEFILE_CHECK = 2
    TILE_INDEX = 3
    TRAJ_TO_GPKG = 4
    LASZY = 5
    LASZY_SUMMARY = 6
    QC_PREP = 7
    VOID_CHECK = 8
    DENSITY_ANALYSIS = 9
    LIDAR_EXTENTS = 10
    GRID_INTENSITY = 11
    GRID_LAST_RETURN = 12
    GRID_DENSITY_CLASS = 13
    
    TEST_LIST = [
        FILE_NAMING,  
        SHAPEFILE_CHECK, 
        TILE_INDEX,  
        TRAJ_TO_GPKG,  
        LASZY,  
        LASZY_SUMMARY,  
        QC_PREP,  
        VOID_CHECK,  
        DENSITY_ANALYSIS,  
        LIDAR_EXTENTS,  
        GRID_INTENSITY,  
        GRID_LAST_RETURN,  
        GRID_DENSITY_CLASS  
    ]
    GRID_TESTS = [
        GRID_INTENSITY,  
        GRID_LAST_RETURN,  
        GRID_DENSITY_CLASS,  
    ]

    TEST_DICT = {
        FILE_NAMING:{
            "Name": "File Naming",
            "Description": "Check naming of both acquisition and final LiDAR file naming.",
        },
        SHAPEFILE_CHECK:{
            "Name": "Shapefile Check",
            "Description": "Checks field name and field type in shapefiles and generates a .txt "
            "report."
        },
        TILE_INDEX:{
            "Name": "Tile Index",
            "Description": "Generate the bounding box tileset for input batch of laz/las files."
        },
        TRAJ_TO_GPKG:{
            "Name": "Trajectory To GeoPackage",
            "Description": "Write every 100th record from SBET trajectory files to geopackages "
            "as point data."
        },
        LASZY:{
            "Name": "Laszy",
            "Description": "Generate a json file for each las/laz file."
        },
        LASZY_SUMMARY:{
            "Name": "Laszy Summary",
            "Description": "Summarize Laszy outputs into single .csv file. "
            "Runs Laszy test automatically if it's not already selected."
        },
        QC_PREP:{
            "Name": "QC Prep",
            "Description": "Copy a user-specified percentage of lidar files "
            "in the input directory to the output directory."
        },    
        VOID_CHECK:{
            "Name": "Void Check",
            "Description": "Identify non-water point voids. Runs Generate Last Density Raster test "
            "automatically if it's not already selected."
        }, 
        DENSITY_ANALYSIS:{
            "Name": "Density Analysis",
            "Description": "Analyze density rasters for density criteria. Excludes areas "
            "identified as water in the BC Geographic Warehouse."
        },    
        LIDAR_EXTENTS:{
            "Name": "Generate LIDAR Extents",
            "Description": "Generate a \'true\' lidar extent polygon, rather than bounding boxes."
        },    
        GRID_INTENSITY:{
            "Name": "Generate Intensity Raster",
            "Description": "Generate a raster representing intensity for each laz/las file."
        },    
        GRID_LAST_RETURN:{
            "Name": "Generate Last Return Density Raster",
            "Description": "Generate a raster representing last return density for each laz/las file."
        },    
        GRID_DENSITY_CLASS:{
            "Name": "Generate Density Raster by Class",
            "Description": "Generate rasters representing the density of each selected class "
            "for each laz/las file."
        },        
    }
    TEST_TEXT_LIST = []
    for i in range(len(TEST_DICT)):
        TEST_TEXT_LIST.append(f'{TEST_DICT[i+1]["Name"]}')

    TEST_DESC_LIST = []
    for i in range(len(TEST_DICT)):
        TEST_DESC_LIST.append(f'{TEST_DICT[i+1]["Description"]}')
# ===============================================================
# -- valid formats for writing
# ===============================================================
class ImageFormats:

    """
    Class of valid image format constants.

    :param ESRI_ASCII: "asc"
    :param ASCII: "asc"
    :param ASC: "asc"
    :param GEOTIFF: "tiff"
    :param GEOTIF: "tif"
    :param TIFF: "tiff"
    :param TIF: "tif"
    :param SID: "sid"
    """

    SID = "sid"
    TIF = GEOTIF = "tif"
    TIFF = GEOTIFF = "tiff"
    ASC = ASCII = ESRI_ASCII = "asc"


# ===============================================================
# -- Valid lidar class numbers
# ===============================================================
class _LidarClass:

    """
    Child LidarClass Object.

    @param name: Name of lidar Class. (e.g. "ground")
    @param number: Integer value assigned to lidar class. (e.g. 2)
    """

    def __init__(self, name, number):
        self.name = name
        self.number = number


class LidarClass:

    """
    Constant class containing valid ASPRS lidar classifications.
    Composed of _LidarClass objects.

    @param DEFAULT: (1, "default")
    @param GROUND: (2, 'ground')
    @param HIGH_VEGETATION: (5, 'high_vegetation')
    @param OUTLIERS: (7, 'outliers')
    @param WATER: (9, 'water')
    @param HIGH_NOISE: (18, 'high_noise')
    @param IGNORED_GROUND: (20, 'ignored_ground')
    @param DICT: Dictionary mapping all class numbers to names.
    """

    DEFAULT = _LidarClass(1, "default")
    GROUND = _LidarClass(2, 'ground')
    HIGH_VEGETATION = _LidarClass(5, 'high_vegetation')
    OUTLIERS = _LidarClass(7, 'outliers')
    WATER = _LidarClass(9, 'water')
    HIGH_NOISE = _LidarClass(18, 'high_noise')
    IGNORED_GROUND = _LidarClass(20, 'ignored_ground')
    DICT = {
        1: "default",
        2: 'ground',
        5: 'high_vegetation',
        7: 'outliers',
        9: 'water',
        18: 'high_noise',
        20: 'ignored_ground'
    }



class LiqcsTestTag:
    TILE_INDEX = "Tile Index"
    VOID_CHECK = "Void Check"
    GRID_CLASS = "Density Grid (By Class)"
    GRID_LAST_RETURN = "Density Grid (Last Return)"
    GRID_INTENSITY = "Density Grid (Intensity)"
    TRAJ_TO_GPKG = "Trajectory to gpkg"
    LASZY_SUMMARY = "Laszy Summary"
    QC_PREP = "QC Prep"
    LASZY = "Laszy"
    FILE_NAME = "File Naming"
    DENSITY_ANALYSIS = "Density Analysis"
    SHAPEFILE_CHECK = "Shapefile Check"


# ===============================================================
# -- Valid grid types
# ===============================================================
class GridType:

    """
    Grid type strings consts.

    @param LAST_RETURN: "last"
    @param INTENSITY: "intensity"
    @param CLASS: "class"
    @param ALL: "all"
    @param TYPES: All types in list.
    @param FLAG_DICT: LiQCS flags mapped to grid types.
    """

    LAST_RETURN = "last"
    INTENSITY = "intensity"
    CLASS = "class"
    ALL = "all"
    TYPES = [
        CLASS,
        INTENSITY,
        LAST_RETURN
    ]
    FLAG_DICT = {
        LiqcsTests.GRID_DENSITY_CLASS: CLASS,
        LiqcsTests.GRID_INTENSITY: INTENSITY,
        LiqcsTests.GRID_LAST_RETURN: LAST_RETURN
    }


# ===============================================================
# -- EPSG codes
# ===============================================================
class EpsgCode:

    """
    EPSG code constants.

    @param MIN: 1024
    @param MAX: 32767
    @param WGS_84: 4326
    @param NAD_83_CSRS_UTM_Z11: 2955
    @param NAD_83_CSRS_UTM_Z10: 3157
    @param NAD_83_CSRS_UTM_Z09: 3156
    @param NAD_83_CSRS_UTM_Z08: 3155
    @param NAD_83_CSRS_UTM_Z07: 3154
    @param NAD_83_CSRS_BC_ALBERS: 3005
    @param EPSG_DICT_CODE_TO_TUPLE_WKT_PROJ: Epsg codes mapped to a tuple containing WKT [0] and proj [1] CRS strings.

    """

    MIN = 1024
    MAX = 32767
    WGS_84 = 4326
    NAD_83_CSRS_UTM_Z11 = 2955
    NAD_83_CSRS_UTM_Z10 = 3157
    NAD_83_CSRS_UTM_Z09 = 3156
    NAD_83_CSRS_UTM_Z08 = 3155
    NAD_83_CSRS_UTM_Z07 = 3154
    NAD_83_CSRS_BC_ALBERS = 3005
    EPSG_DICT_CODE_TO_TUPLE_WKT_PROJ = {
        NAD_83_CSRS_UTM_Z11: ("EPSG 2955: NAD83(CSRS) / UTM zone 11 N", "nad83csrs_utm11n"),
        NAD_83_CSRS_UTM_Z10: ("EPSG 3157: NAD83(CSRS) / UTM zone 10 N", "nad83csrs_utm10n"),
        NAD_83_CSRS_UTM_Z09: ("EPSG 3156: NAD83(CSRS) / UTM zone 9 N", "nad83csrs_utm09n"),
        NAD_83_CSRS_UTM_Z08: ("EPSG 3155: NAD83(CSRS) / UTM zone 8 N", "nad83csrs_utm08n"),
        NAD_83_CSRS_UTM_Z07: ("EPSG 3154: NAD83(CSRS) / UTM zone 7 N", "nad83csrs_utm07n"),
        NAD_83_CSRS_BC_ALBERS: ("EPSG 3005: NAD83 / BC Albers", "nad83_bc_albers")
    }


# ===============================================================
# -- General formalized strings and definitions
# ===============================================================
class Strings:

    """
    Constant string values.

    @param VOIDS: "voids"
    @param GRIDS: "grids"
    @param LASZY: "laszy"
    @param DENSITY: "density"
    @param INTENSITY: "intensity"
    @param FORMATTING: "formatting"
    @param LAST_RETURN: "last_return"
    @param LIDAR_EXTENTS: "LiDAR_Extents"
    """

    VOIDS = "voids"
    GRIDS = "grids"
    LASZY = "laszy"
    DENSITY = "density"
    INTENSITY = "intensity"
    FORMATTING = "formatting"
    LASZY_JSON = "laszy_json"
    LAST_RETURN = "last_return"
    LASZY_REPORT = "laszy_report"
    LIDAR_EXTENTS = "LiDAR_Extents"

    

class Regex:

    FILENAME_LIDAR_PRODUCTION = r'bc_\d{3}[a-z]\\d{3}_(\\d_){3}x(yes|no)' \
                                r'_(\d{1,2}|\dp\d[1-9])_(bcalb|utm09|utm' \
                                r'9|utm10|utm11)_2\d{3}\.la(s|z)'

    FILENAME_LIDAR_RAW = r'[0-9]{1,5}_[0-9]{3}_[0-9]{4}_([a-z0-9]?)+([A-' \
                         r'Z0-9\-?]).*\.la(s|z)'

    GUID = R'\s+([0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12})'

    CONTRACT_NUMBER = R'OP\d\dBMRS\d\d\d'

