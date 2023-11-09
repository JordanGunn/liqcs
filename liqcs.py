# ------------------------------------------------------------------------------
# lidar Quality Control Suite (LiQCS)
# Called by liqcs_gui.py
# ------------------------------------------------------------------------------

# -- System imports
from functools import partial
import concurrent.futures
import subprocess
import traceback
import datetime


# -- Local imports
from liqcs_config import IS_LINUX, SHELL_EXEC, rainbow_string, dashline, total_ram, RAM
from liqcs_const import LidarClass, GridType, EpsgCode, LiqcsTests
from liqcs_summary import LidarSummary, find_format_errors
from rsge_toolbox.lidar.Laszy import Laszy, LaszyReport
from liqcs_validate_filename import filename_is_bad
from liqcs_void_check import *
from liqcs_grid import Grid

import density_analysis.density_analysis_main as density_analysis_main
import vector.shp_field_check as shp_field_check
import liqcs_tile_index
import liqcs_traj2gpkg
import liqcs_qc_prep

# -- Constants
EXCEPTIONS = []


def run_from_gui(
    inputPath,
    resultsPath,
    infileGlob,
    testList,
    cores,
    epsgCode,
    shapefile,
    gridClasses,
    qcPercent,
    siteName,
    contract,
    concavity,
    densityAnalysisDict,
    liqcsSummaryCompletedPath
):
    """
    Run LiQCS from its GUI.

    Args:
        inputPath (str):
            - Main directory provided as LiQCS input
        resultsPath (str):
            - Main directory for LiQCS output
        infileGlob (list of str):
            - List of filepaths in the input directory that will have
                tests run on them.
        testList (list of int):
            - List of LiQCS test numbers (as ordered in config.TEST_DICT)
                to perform on input file paths
        cores (int):
            - Number of computer cores to use in processing.
                More cores makes LiQCS processing faster, but slows down other
                computer processes.
        epsgCode (int):
            - Coordinate reference system (CRS) for LiQCS outputs.
        shapefile (list of str):
            - 0: Path to breakline shapefile for void test
            - 1: Path to AOI shapefile for void test
        gridClasses (_type_): _description_
        qcPercent (int):
            - Percentage of files to perform LiQCS tests on.
        siteName (str):
            - Input site/project name for lidar extents test.
        contract (str):
            - Input contract name for tile index.
        densityAnalysisDict (dict):
            - Contains input parameters for the density analysis test.
        liqcsSummaryCompletedPath (str):
            - Path of liqcs summary file, to print to the console during processing.

    Returns:
        (list of str):
            - List of exceptions the code encountered.
    """

    # reduce number of concurrent process based on total RAM
    if total_ram() < RAM.GB_8:
        cores = 1
    elif total_ram() < RAM.GB_32:
        cores = 2

    exceptions = run_tests(
        testList,
        inputPath,
        infileGlob,
        cores,
        resultsPath,
        epsgCode,
        shapefile,
        gridClasses,
        qcPercent,
        siteName,
        contract,
        concavity,
        densityAnalysisDict,
        liqcsSummaryCompletedPath
    )

    return exceptions


def run_tests(
    testList,
    inputPath,
    infileGlob,
    cores,
    resultsPath,
    epsgCode,
    shapefile,
    gridClasses,
    qcPercent,
    siteName,
    contract,
    concavity,
    densityAnalysisDict,
    # liqcs_gui.py produces full path of liqcs summary text file, which it also creates/writes.
    # This parameter will be None if liqcs is run from liqcs.py rather than liqcs_gui.py.
    liqcsSummaryCompletedPath=None
):
    las_files = lidar_file_list(infileGlob)
    num_las_files = len(las_files)
    grid_path = None
    for currentTest in testList:
        # Check for bad filenames
        if LiqcsTests.FILE_NAMING == currentTest:
            print(f"Checking {num_las_files} filenames...")
            filename_handler(infileGlob, resultsPath)

        if LiqcsTests.SHAPEFILE_CHECK == currentTest:
            print("Shapefile check in progress...", flush=True)
            shapefile_check_handler(inputPath, resultsPath)

        if LiqcsTests.TILE_INDEX == currentTest:
            print("Generating tile index...", flush=True)
            tile_index_handler(las_files, contract, resultsPath)

        if LiqcsTests.TRAJ_TO_GPKG == currentTest:
            print("Trajectories To GPKG running...", flush=True)
            traj_to_gpkg_handler(epsgCode, infileGlob, resultsPath)

        if LiqcsTests.LASZY == currentTest:
            print(f"Generating {len(las_files)} Laszy json files...", flush=True)
            laszy_info_handler(las_files, resultsPath, int(cores))

        if LiqcsTests.LASZY_SUMMARY == currentTest:
            print("Generating Laszy Summary from Laszy json files...", flush=True)
            laszy_summary_handler(las_files, resultsPath)

        if LiqcsTests.QC_PREP == currentTest:
            print("Running qc prep...", flush=True)
            qc_prep_handler(las_files, qcPercent, resultsPath)

        if LiqcsTests.VOID_CHECK == currentTest:
            print("Void check/reporting in progress...", flush=True)
            void_check_handler(grid_path, resultsPath, shapefile)

        if LiqcsTests.DENSITY_ANALYSIS == currentTest:
            print("Density Analysis running...", flush=True)
            density_analysis_handler(densityAnalysisDict, resultsPath)

        if LiqcsTests.LIDAR_EXTENTS == currentTest:
            print("Generating LiDAR Extents...", flush=True)
            lidar_extents_handler(las_files, resultsPath, siteName, concavity)

        if currentTest in (LiqcsTests.GRID_INTENSITY, LiqcsTests.GRID_LAST_RETURN, LiqcsTests.GRID_DENSITY_CLASS):
            print(f"Generating {num_las_files} sets of grids...", flush=True)
            grid_path = make_grid_directories(gridClasses, resultsPath, testList)
            grid_handler(cores, epsgCode, gridClasses, grid_path,  las_files, testList)
        
    return EXCEPTIONS


def void_check_handler(grid_path, resultsPath, shapefile):

    """

    :param grid_path:
    :param resultsPath:
    :param shapefile:
    :return:
    """

    try:
        void_path = os.path.join(resultsPath, Strings.VOIDS)
        os.makedirs(void_path, exist_ok=True)

        last_return_path = os.path.join(grid_path, Strings.DENSITY, GridType.LAST_RETURN)
        mask = void_mask(breaklines=shapefile[0], aoi=shapefile[1], out_dir=void_path)
        void_report(last_return_path, resultsPath, mask)

    except Exception as e:
        print(e)
        EXCEPTIONS.append(f"Void Check:\n{traceback.format_exc()}")


def traj_to_gpkg_handler(epsgCode, infileGlob, resultsPath):

    """

    :param epsgCode:
    :param infileGlob:
    :param resultsPath:
    :return:
    """

    try:
        traj_path = os.path.join(resultsPath, "trajectory_to_gpkg")
        os.makedirs(traj_path, exist_ok=True)
        liqcs_traj2gpkg.___run_from_liqcs(infileGlob, traj_path, epsgCode)
        print("Trajectories To GPKG complete!\n", flush=True)

    except Exception as e:
        print(e)
        EXCEPTIONS.append(f"Trajectories To GPKG:\n{traceback.format_exc()}")


def grid_handler(cores, epsgCode, gridClasses, grid_path, las_files, testList):

    """

    :param cores:
    :param epsgCode:
    :param gridClasses:
    :param grid_path:
    :param las_files:
    :param testList:
    :return:
    """

    grid_types = [
        GridType.FLAG_DICT[flag]
        for flag in testList
        if flag in LiqcsTests.GRID_TESTS
    ]

    generate_grids_partial = partial(
        generate_grids, grid_types=grid_types, out_dir=grid_path,
        gridClasses=gridClasses, epsgCode=epsgCode
    )

    with concurrent.futures.ProcessPoolExecutor(cores) as executor:
        executor.map(generate_grids_partial, las_files)


def lidar_extents_handler(las_files, resultsPath, siteName, concavity):

    """
    :param concavity:
    :param las_files:
    :param resultsPath:
    :param siteName:
    :return:
    """

    try:
        date = datetime.datetime.today().strftime('%Y-%m-%d')
        lidar_extents_out = f"{siteName}_LiDAR_Extent_{date}.shp"
        lidar_extents_path = os.path.join(resultsPath, Strings.LIDAR_EXTENTS)
        extent_shapefile_path = os.path.join(lidar_extents_path, lidar_extents_out)

        os.makedirs(lidar_extents_path, exist_ok=True)
        lasboundary = "lasboundary64" if IS_LINUX else "lasboundary.exe"
        cmd = f'{lasboundary} -i {" ".join(las_files)} -concavity {concavity} -merged -keep_every_nth 100 -o {extent_shapefile_path}'
        subprocess.call(cmd, shell=True, executable=SHELL_EXEC)

        print("lidar Extents generated!\n", flush=True)

    except Exception as e:
        print(e)
        EXCEPTIONS.append(f"Generate lidar Extents:\n{traceback.format_exc()}")


def lidar_summary_handler(resultsPath):

    """

    :param resultsPath:
    :return:
    """

    try:
        format_path = os.path.join(resultsPath, Strings.FORMATTING)
        os.makedirs(format_path, exist_ok=True)

        lasinfo_path = os.path.join(resultsPath, Strings.LASINFO)
        lasinfo_glob = glob.glob(
            os.path.join(lasinfo_path, "*.txt")
        ) if os.path.exists(lasinfo_path) else None

        if bool(lasinfo_glob):
            summary_csv = None
            for file in lasinfo_glob:
                info_record = LidarSummary(file)
                summary_csv = info_record.output(format_path, write_errors=False)

            if bool(summary_csv):
                find_format_errors(summary_csv, format_path, save_output=True)
                print("lidar summary generated!\n", flush=True)

    except Exception as e:
        print(e)
        EXCEPTIONS.append(f"lidar Summary:\n{traceback.format_exc()}")
        

def laszy_summary_handler(flist: list, outdir: str):

    """
    :param flist:
    :param outdir:
    """

    try:
        report = LaszyReport(file_list=flist, outdir=outdir, las_to_json=True, verbose=False)
        report.write(Strings.LASZY_REPORT, validate=True, check_logs=True)
    except Exception as e:
        print(e)
        EXCEPTIONS.append(f"lidar Summary:\n{traceback.format_exc()}")


def lasinfo_handler(cores, las_files, resultsPath):

    """

    :param cores:
    :param las_files:
    :param resultsPath:
    :return:
    """

    try:
        # Generate lasinfo .txts
        # Create a subdirectory for the lasinfo.txts
        lasinfo_path = os.path.join(resultsPath, Strings.LASINFO)
        os.makedirs(lasinfo_path, exist_ok=True)

        # Loop through infile glob, generating lasinfo .txts for each
        try:
            # MEIPASS exists if running from .exe
            lastools = r'C:\LAStools\bin'
            meipass = sys._MEIPASS
            if meipass not in os.environ["PATH"] and lastools not in os.environ["PATH"]:
                try:
                    os.environ["PATH"] += (os.pathsep + sys._MEIPASS)
                except Exception:
                    os.environ["PATH"] += (os.pathsep + r'C:\LAStools\bin')
        except AttributeError:
            # If running from .py rather than .exe, don't use MEIPASS
            os.environ["PATH"] += os.pathsep + "C:\\LAStools\\bin"

        # adding this for LAStools on linux machine
        lasinfo = "lasinfo64" if IS_LINUX else "lasinfo.exe"
        cmd = f'{lasinfo} -i {" ".join(las_files)} -cd -otxt -odir {lasinfo_path} -cores {cores}'
        subprocess.call(cmd, shell=True, executable=SHELL_EXEC)

        print("Lasinfo files generated!\n", flush=True)

    except Exception as e:
        print(e)
        EXCEPTIONS.append(f"Lasinfo:\n{traceback.format_exc()}")


def _laszy_json(file: str, outdir: str):

    """Helper for laszy info."""

    las = Laszy(file)
    las.summarize(outdir=outdir)


def laszy_info_handler(flist: list, outdir: str, cores: int = 1):

    """
    :param flist:
    :param outdir:
    :param cores:
    """

    json_outdir = os.path.join(outdir, Strings.LASZY_JSON)
    laszy_partial = partial(_laszy_json, outdir=json_outdir)
    with concurrent.futures.ProcessPoolExecutor(cores) as executor:
        executor.map(laszy_partial, flist)


def density_analysis_handler(densityAnalysisDict, resultsPath):

    """

    :param densityAnalysisDict:
    :param resultsPath:
    :return:
    """

    try:
        density_analysis_main.run_main_density_check(
            densityAnalysisDict['rasterDir'],
            densityAnalysisDict['projectAreaDir'],
            resultsPath,
            densityAnalysisDict['minDensityReq'],
            densityAnalysisDict['bcgwCredentials'],
            densityAnalysisDict['check_correct_units'],
            densityAnalysisDict['normalizationDivisor'],
        )
        print("Density Analysis complete!\n", flush=True)
    except Exception as e:
        print(e)
        EXCEPTIONS.append(f"Density Analysis:\n{traceback.format_exc()}")


def qc_prep_handler(las_files, qcPercent, resultsPath):

    """

    :param las_files:
    :param qcPercent:
    :param resultsPath:
    :return:
    """

    try:
        liqcs_qc_prep.run_qc_prep(resultsPath, qcPercent, las_files)
    except Exception as e:
        print(e)
        EXCEPTIONS.append(f"QC Prep:\n{traceback.format_exc()}")


def tile_index_handler(las_files, contract, resultsPath):

    """

    :param contract:
    :param las_files:
    :param resultsPath:
    :return:
    """

    try:
        liqcs_tile_index.tile_index(las_files, contract, resultsPath)

    except Exception as e:
        print(e)
        EXCEPTIONS.append(f"Tile Index:\n{traceback.format_exc()}")


def shapefile_check_handler(inputPath, resultsPath):
    try:
        shp_field_check.run_from_gui(inputPath, resultsPath)
    except Exception as e:
        print(e)
        EXCEPTIONS.append(f"Shapefile Check:\n{traceback.format_exc()}")


def filename_handler(file_list, resultsPath):

    """

    :param file_list:
    :param resultsPath:
    :return:
    """

    try:
        # Create a subdirectory for format reports
        format_path = os.path.join(resultsPath, Strings.FORMATTING)
        os.makedirs(format_path, exist_ok=True)

        bad_filenames = [os.path.split(f)[-1] for f in file_list if filename_is_bad(f)]
        
        filename_check_file = os.path.join(format_path, "filename_check.txt")
        with open(filename_check_file, mode='w') as out:
            if len(bad_filenames) == 0:
                print("All file names are formatted correctly!", file=out)
            else:
                print(f"Bad file names: {len(bad_filenames)} of {len(file_list)}", file=out)
                print("\nList of bad file names:", file=out)
                for filename in bad_filenames:
                    print(filename, file=out)

        print("File name check complete!\n", flush=True)

    except Exception as e:
        print(e)
        EXCEPTIONS.append(f"File Naming:\n{traceback.format_exc()}")


def make_grid_directories(gridClasses: list, resultsPath: str, testList: list) -> str:

    """
    Create/setup directories for LIQCS gridded output data.

    :param gridClasses: List of class number definitions (conforming to ASPRS LAS specification)
    :param resultsPath: Parent output directory (grid directories creates as children)
    :param testList: List or Set of input test flags.

    :return: Parent grid path.
    """

    grid_path = os.path.join(resultsPath, Strings.GRIDS)

    if LiqcsTests.GRID_INTENSITY in testList:
        intensity_grid_path = os.path.join(grid_path, GridType.INTENSITY)
        os.makedirs(intensity_grid_path, exist_ok=True)

    if LiqcsTests.GRID_DENSITY_CLASS in testList or LiqcsTests.GRID_LAST_RETURN in testList:
        density_grid_path = os.path.join(grid_path, Strings.DENSITY)
        os.makedirs(density_grid_path, exist_ok=True)

        if LiqcsTests.GRID_DENSITY_CLASS in testList:
            if bool(gridClasses):
                for grid_class in gridClasses:
                    grid_class_path = os.path.join(density_grid_path, LidarClass.DICT[grid_class])
                    os.makedirs(grid_class_path, exist_ok=True)

        if LiqcsTests.GRID_LAST_RETURN in testList:
            last_return_path = os.path.join(density_grid_path, GridType.LAST_RETURN)
            os.makedirs(last_return_path, exist_ok=True)

    return grid_path



def lidar_file_list(list_of_input_file_paths):
    """
    Find the all the .las/.laz files
    in a list of file paths.

    Args:
        list_of_input_file_paths (list of str):
            - List of file paths

    Returns:
        (list of str):
            - List of file paths (.laz/.las files only)
    """
    las_laz_paths_list = []

    for file in list_of_input_file_paths:
        if file.endswith(".las") or file.endswith(".laz"):
            las_laz_paths_list.append(file)

    return las_laz_paths_list


def epsg_menu():

    """
    Write epsg menu to stdout.
    """

    print(
        "Specified a test that requires defining a CRS"
        "\nEPSG 2955: NAD83(CSRS) / UTM zone 11"
        "\nEPSG 3157: NAD83(CSRS) / UTM zone 10"
        "\nEPSG 3156: NAD83(CSRS) / UTM zone 9"
        "\nEPSG 3155: NAD83(CSRS) / UTM zone 8"
        "\nEPSG 3154: NAD83(CSRS) / UTM zone 7"
        "\nEPSG 3005: NAD83 / BC Albers\n"
    )


def is_epsg_required(tests: Union[list, set]) -> bool:

    """
    Determine is EPSG code is required for tests.

    :param tests: A list of test strings.

    :return: True or False
    """

    is_tile_index = (LiqcsTests.TILE_INDEX in tests)
    is_trajectory = (LiqcsTests.TRAJ_TO_GPKG in tests)
    is_intensity = (LiqcsTests.GRID_INTENSITY in tests)
    is_class_density = (LiqcsTests.GRID_DENSITY_CLASS in tests)
    is_last_density = (LiqcsTests.GRID_LAST_RETURN in tests)

    is_vector_output = (is_trajectory or is_tile_index)
    is_raster_output = (is_intensity or is_last_density or is_class_density)

    return is_vector_output or is_raster_output


def generate_grids(in_file: str, grid_types: list, out_dir: str, epsgCode: int, gridClasses: list):
    """
    Generate gridded data from input LAS/LAZ file.

    :param in_file: Input LAS/LAZ file
    :param grid_types: List of GRID_TYPE(s) or string if one type provided. (See liqcs_const.py)
    :param out_dir: Output directory for writing.
    :param epsgCode: EPSG code defining Coordinate Reference System for output data.
    :param gridClasses: List of class number definitions (conforming to ASPRS LAS specification)
    """

    filename = in_file.split(os.sep)[-1]
    resultsPath = f"{os.sep}".join(out_dir.split(os.sep)[:-1])
    basename = os.path.basename(filename).split(".")[0]

    if isinstance(grid_types, str):
        grid_types = [grid_types]

    try:
        grid = Grid()
        grid.set_crs(epsgCode)
        grid.read_lidar(in_file)
        for t in grid_types:
            folder = (Strings.INTENSITY if (t == GridType.INTENSITY) else Strings.DENSITY)

            if t == GridType.CLASS:
                for class_number in gridClasses:
                    cls = LidarClass.DICT[class_number]
                    out_name = os.path.join(out_dir, folder, cls, f"{basename}_{cls}.tif")
                    if not os.path.exists(out_name):
                        grid.compute(class_number, False, False)
                        grid.write(out_name)
                        grid.reset()
            else:
                last_return = (GridType.LAST_RETURN if (t == GridType.LAST_RETURN) else "")
                out_name = os.path.join(out_dir, folder, last_return, f"{basename}_{t}.tif")
                if not os.path.exists(out_name):
                    grid.compute(
                        last_return=(t == GridType.LAST_RETURN),
                        intensity=(t == GridType.INTENSITY)
                    )
                    grid.write(out_name)
                    grid.reset()

    except Exception as e:
        print(f'{filename} grid process failed with exception: \n{e}\n')
        with open(f'{resultsPath}\\grid_failures.txt', 'a+') as f:
            f.write(f'{filename}:\n')
            f.write(f'{traceback.format_exc()}\n')


def main():
    """
    To re-instate command line interface of LiQCS,
    go through git commit history to 49c93c0d1257c8c3a6d1411da0775c516f73ec64
    or earlier.

    This function will need some development, but the bones are there.

    But why would you want to do that, when you could use a nice GUI?
    """
    print(
        f"{rainbow_string(dashline())}"
        "\nLiQCS command line interface not supported."
        "\n\nPlease run LiQCS from liqcs_gui.py.\n"
        f"{rainbow_string(dashline())}"
    )

    in_file = "/home/jordan/work/geobc/test_data/las/bc_092b044_1_1_2_xyes_8_utm10_2019.las"
    out_dir = "/home/jordan/work/geobc/test_data/liqcs_out/after"

    generate_grids(
        in_file,
        GridType.CLASS,
        out_dir,
        EpsgCode.NAD_83_CSRS_UTM_Z10,
        gridClasses=[2]
    )


if __name__ == '__main__':
    main()
