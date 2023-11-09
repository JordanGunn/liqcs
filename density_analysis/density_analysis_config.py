from datetime import datetime
import os
from pathlib import Path
import shutil
import sys
import getpass
from typing import Tuple
from stat import FILE_ATTRIBUTE_HIDDEN
import ctypes
import oracledb
import numpy as np


# ------------------------------------------------------------------------------
# Functions related to testing
# ------------------------------------------------------------------------------

def test_data_folder():
    """
    Get the path to the test data folder.
    Relevant for testing only.

    Returns:
        str: Path to test data folder.
    """

    return os.path.join(
        os.path.dirname(
            os.path.realpath(__file__)  # Path to this script in local cloned repo
        ),
        "test_files",
    )


def test_input_folder():
    """
    Get the path to the test data input folder.
    Relevant for testing only.

    Returns:
        str: Path to test data input folder.
"""
    return os.path.join(
        test_data_folder(),
        "INPUT"
    )


# ------------------------------------------------------------------------------
# Path to local cloned repo
# ------------------------------------------------------------------------------


def working_dir():
    """
    Get the path of the working directory.

    If using .exe, the working directory is MEIPASS.

    If using .py, the working directory is the root of the local repo.

    Returns:
        str: path to local cloned repo
    """
    try:
        # If running from .exe, use MEIPASS
        working_dir_ = sys._MEIPASS
    except Exception:
        # Otherwise, path to the local repo
        working_dir_ = os.path.abspath('.')
    return working_dir_


# ------------------------------------------------------------------------------
# Output subdirectories
# ------------------------------------------------------------------------------

def density_analysis_results_dirname():
    """
    Name of subdirectory within the output_dir
    where the density analysis results are saved.

    Returns:
        str: Directory name for density analysis results
    """
    return "DENSITY_ANALYSIS_RESULTS"


def density_analysis_results_dir_path(output_dir):
    """
    Path to the subdirectory within the output_dir
    where density analysis results and outputs are saved.

    If the folder doesn't exist already, create it.

    Returns:
        str: Path to density analysis results directory.
    """
    density_analysis_results_dir_path_ = os.path.join(
        output_dir,
        density_analysis_results_dirname()
    )
    if not os.path.isdir(density_analysis_results_dir_path_):
        os.mkdir(density_analysis_results_dir_path_)

    return density_analysis_results_dir_path_


# ------------------------------------------------------------------------------
# Consistent messaging formatting
# ------------------------------------------------------------------------------

def dashline():
    """
    Get a string of hyphens, with a new line character on either end.

    Returns:
        str: Eighty hyphens, bookended by new line characters.
    """
    return f"\n{'-' * 80}\n"


def bad_input():
    """
    Print a message to the console if the user
    didn't give us what we expected.
    """
    print("\nThat's not a raster! Please try again.")


def exit_message():
    """
    Print a message to the console when this program quits.
    """
    print(f"{dashline()}Bye!")


# ------------------------------------------------------------------------------
# If user enters Q to quit...
# ------------------------------------------------------------------------------

def q_to_quit(input_value):
    """
    If the input value is a q or a Q,
    quit the program.

    Args:
        input_value (str):
            - Any string.
    """
    if input_value.capitalize() == "Q":
        exit_message()
        sys.exit()


# ------------------------------------------------------------------------------
# Input project areas
# ------------------------------------------------------------------------------

def specify_project_areas_dir(test_io=False):
    """
    Create a list of paths to project area shapefiles.

    Args:
        test_io (bool, optional):
            - Option to use test inputs.
            - Defaults to False.

    Returns:
        list of str:
            - List of paths to shapefiles.
    """
    if test_io:
        project_area_dir = os.path.join(
            test_input_folder(),
            "PROJECT_AREAS"
        )

    else:
        project_area_dir = None
        while not project_area_dir:
            project_area_dir = input(
                f"{dashline()}"
                "Provide the path to a directory containing project area shapefile(s) "
                "(searches recursively), or Q to quit: "
            )
            q_to_quit(project_area_dir)
            if not os.path.isdir(project_area_dir):
                print("That's not a directory! Please try again.")
                project_area_dir = None
            else:
                project_areas_list = get_project_areas_list(project_area_dir)
                if not project_areas_list:
                    print("No shapefiles in that directory! Please try again.")
                    project_area_dir = None
                else:
                    num_shapefiles = len(project_areas_list)
                    if num_shapefiles == 1:
                        s_no_s = ""
                    else:
                        s_no_s = "s"
                    print(
                        f"\nGreat! That directory contains {num_shapefiles} shapefile{s_no_s}."
                    )

    print(f"\nProject areas directory:\n\t{project_area_dir}")

    return project_area_dir


def get_project_areas_list(project_area_dir):
    """
    Recursively search for shapefiles within a directory;
    return the paths of those shapefiles in a list.

    Args:
        project_area_dir (str):
            - Full path of directory containing project area shapefiles.

    Returns:
        list of str:
            - List of paths to shapefile(s) that describe the project area(s).
                e.g.,
                ['C:/MY_PROJECT/AOI/north.shp', 'C:/MY_PROJECT/AOI/south.shp']
    """
    project_area_dir = Path(project_area_dir)
    shapefiles = project_area_dir.rglob("*.shp")
    project_areas_list = [
        str(f)
        for f in shapefiles
    ]
    return project_areas_list


# ------------------------------------------------------------------------------
# Input rasters
# ------------------------------------------------------------------------------

def string_signifying_masked_raster():
    return "MASKED"


def input_raster_rules():
    """
    Description of what files will be included in the density analysis.

    The code implementation of these rules is located in
    get_density_raster_list(), definition of density_files variable.

    Returns:
        (str): 
            - Text as used by LiQCS GUI tooltip in the
                Density Analysis popup window
    """
    input_raster_rules_string = (
        "To be included in the density analysis, "
        "raster files must:"
        "\n\n1. Have the extension .tif or .tiff"
        "\n- Not case sensitive, can be .TIF, .TIFF, etc."
        "\n\n2. The filename must include the word 'density'"
        "\n- Not case sensitive, can be Density, DENSITY, etc."
        "\n\n3. The filename must not include the word "
        f"'{string_signifying_masked_raster()}' (all caps)"
        "\n- The file path is allowed to contain the word "
        f"{string_signifying_masked_raster()}"
    )
    return input_raster_rules_string


def get_density_raster_list(input_path: str) -> list:
    """
    Create a list of all density grids in a
    directory and subdirectories.

    To be included,
        1. Files must have the extension .tif or .tiff
        2. Filenames must include the word "density"
            (not case sensitive, can be Density, DENSITY, etc)
        3. Filenames cannot contain the word "MASKED" (all caps).
            - the file path is allowed to contain the word "MASKED".


    Args:
        input_path (str): path to directory containing density grids

    Returns:
        density_files (list): list of density grid filenames
    """
    inpath = Path(input_path)
    tif_files = []
    extensions = (".tif", ".tiff")
    for extension in extensions:
        tif_files.extend(inpath.rglob(f"*{extension}"))

    # ! If these rules change, please update the text in
    # * 1. The docstring for this function
    # * 2. In input_raster_rules() -- the text used in the tooltip in the GUI,
    # * 3. The wiki :) (Production Checks/Density Analysis(LiQCS test))
    density_files = [
        str(filepath)
        for filepath in tif_files
        if "density" in str(filepath.name).lower()
        and string_signifying_masked_raster() not in str(filepath.name)
    ]

    return density_files


def specify_input_dir(test_io=False, limit_inputs=False) -> str:
    """
    Specify location of density grids.

    Returns:
        input_density_rasters_dir (str):
            - path of directory containing input density grids
        density_raster_list (list):
            - list of density rasters within the input directory
    """
    if test_io:
        input_density_rasters_dir = os.path.join(
            test_input_folder(),
            "Density_Grids",
            # "NORMALIZED_DENSITY_GRIDS"
        )
        if limit_inputs:
            input_density_rasters_dir = os.path.join(
                test_input_folder(),
                "Density_Grids",
                "LIMIT_INPUTS"
            )
        input_density_raster_list = get_density_raster_list(input_density_rasters_dir)
    else:
        input_density_rasters_dir = None
        while not input_density_rasters_dir:
            input_density_rasters_dir = input(
                f"{dashline()}Provide directory containing "
                "density grids (searches recursively), or Q to quit: "
            )
            q_to_quit(input_density_rasters_dir)
            if not os.path.isdir(input_density_rasters_dir):
                print("\nThat's not a directory! Please try a again.")
                input_density_rasters_dir = None
            else:
                input_density_raster_list = get_density_raster_list(input_density_rasters_dir)
                if input_density_raster_list:
                    num_density_grids = len(input_density_raster_list)
                    if num_density_grids == 1:
                        s_no_s = ""
                    else:
                        s_no_s = "s"
                    print(
                        f"\nGreat! That directory contains {len(input_density_raster_list)} "
                        f"density grid{s_no_s}."
                    )
                else:
                    print(
                        "No density grids found in that directory! Please try again."
                    )
                    input_density_rasters_dir = None

    print(f"\nInput density rasters directory:\n\t{input_density_rasters_dir}")

    return input_density_rasters_dir


def specify_input_raster_path():
    """
    Get the path to an input raster from the user.

    Returns:
        str: Path to raster.

    TODO: is this function needed? Not called by main.py.
    """
    input_raster_path = None
    while not input_raster_path:
        input_raster_path = input(
            f"{dashline()}"
            "Provide the full path to a raster, or Q to quit: "
        )
        q_to_quit(input_raster_path)
        # When dragging and dropping filenames into the terminal,
        # sometimes they have quotes around them.
        # Get rid of those quotes.
        if input_raster_path.startswith('"') or input_raster_path.startswith("'"):
            input_raster_path = input_raster_path[1:]
        if input_raster_path.endswith('"') or input_raster_path.endswith("'"):
            input_raster_path = input_raster_path[:-1]

        # Check if the input represents a raster file.
        if os.path.isfile(input_raster_path):
            filename_with_ext = os.path.basename(input_raster_path)
            _, ext = os.path.splitext(filename_with_ext)
            if ext.lower() not in (".tif", ".tiff"):
                input_raster_path = bad_input()
        else:
            input_raster_path = bad_input()

    return input_raster_path


# ------------------------------------------------------------------------------
# Output path
# ------------------------------------------------------------------------------

def specify_output_dir(
    test_io=False,
    delete_previous_test_outputs=True
):
    """
    Specify the path of the directory for output files.

    Args:
        test_io (bool, optional):
            - Option to automatically create a new output directory
                in the testing folder. True for testing only.
            - Defaults to False.
        delete_previous_test_outputs (bool, optional):
            - Option to delete previous test outputs in the testing folder.
            - Relevant only if test_io is True.
            - Defaults to True.

    Returns:
        str:
            - Path to directory to save outputs.
    """
    if test_io:
        output_folder_prefix = "TEST_OUTPUTS_"

        if delete_previous_test_outputs:
            # Delete previous test outputs (folders and contents)
            for item in os.listdir(test_data_folder()):
                if item.startswith(output_folder_prefix):
                    shutil.rmtree(os.path.join(test_data_folder(), item))

        # Make a new test output folder with a timestamp
        outdir = os.path.join(
            test_data_folder(),
            f"{output_folder_prefix}{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        if not os.path.isdir(outdir):
            os.mkdir(outdir)

    else:
        # Get the output folder from user input at the command line
        outdir = None
        while not outdir:
            outdir = input(
                f"{dashline()}Provide a folder path to save the outputs "
                "of this script, or Q to quit: "
            )
            q_to_quit(outdir)
            if not os.path.isdir(outdir):
                print("\nThat's not a folder path! Please try again.")
                outdir = None

    print(
        "\nThe density analysis outputs will be saved here:"
        f"\n\t{outdir}"
    )

    return outdir


# ------------------------------------------------------------------------------
# Minimum density
# ------------------------------------------------------------------------------

def specify_minimum_density_requirement(
    use_default_minimum_density_requirement=False
):
    """
    Specify the minimum density requirement for
    input rasters, as defined by project specifications.

    Args:
        use_default_minimum_density_requirement (bool, optional):
            - Option to use the default value, for testing only.
            - Defaults to False.

    Returns:
        int or float:
            - Minimum density requirement for input rasters.
    """
    if use_default_minimum_density_requirement:
        minimum_density_requirement = 8
    else:
        # Get the minimum density requirement from the command line
        minimum_density_requirement = None
        while not minimum_density_requirement:
            minimum_density_requirement = input(
                f"{dashline()}"
                "What is the minimum density requirement for this project "
                "[points per square metre]? Or enter Q to quit: "
            )
            q_to_quit(minimum_density_requirement)
            try:
                # Try to turn the input into an integer
                minimum_density_requirement = int(minimum_density_requirement)

            except Exception:
                try:
                    # If it can't be an integer, try to make it a float
                    minimum_density_requirement = float(minimum_density_requirement)

                except Exception:
                    # If it can't be an integer or a float, we don't want it!
                    print("That's not a number! Please try again.")
                    minimum_density_requirement = None

    return minimum_density_requirement


# ------------------------------------------------------------------------------
# BCGW Credentials
# ------------------------------------------------------------------------------

def get_bcgw_password():
    """
    Get the user's BCGW password from the command line.

    Returns:
        str: BCGW password.
    """
    return getpass.getpass(
        prompt=f"{dashline()}BCGW password (characters hidden during input): "
    )


def specify_bcgw_credentials(test_io=False) -> Tuple[str]:
    """
    Get British Columbia Geographic Warehouse (BCGW) credentials.

    Returns:
        user (str): BCGW username
        password (str): BCGW password
    """
    if test_io:
        user = getpass.getuser()
        try:
            from sandbox_test_config import BCGW_PASSWORD
            password = BCGW_PASSWORD
        except Exception:
            password = get_bcgw_password()

    else:
        user = input(f"{dashline()}BCGW username, or Q to quit: ")
        q_to_quit(user)
        password = get_bcgw_password()

    return user, password


# ------------------------------------------------------------------------------
# Get BCGW connection
# ------------------------------------------------------------------------------

def get_bcgw_connection(bcgw_credentials):
    """
    Creates connection to the British Columbia
    Geographic Warehouse (BCGW) Oracle database.

    Args:
        bcgw_credentials (tuple of str):
            0 (str): BCGW username
            1 (str): BCGW password

    Returns:
        (connection object):
            - Python connection object to the BCGW.
    """
    # Unpack credentials
    user, password = bcgw_credentials

    print("\nConnecting to the BCGW...")

    try:
        connection = oracledb.connect(
            user=user,
            password=password,
            dsn="bcgw.bcgov:1521/idwprod1.bcgov"
        )
        print(
            "\nConnection successful!"
        )
    except Exception:
        print(
            f"{dashline()}"
            f"{invalid_bcgw_credentials_message(use_tabs=True)}"
            f"\n{dashline()}"
        )
        connection = None

    return connection


def invalid_bcgw_credentials_message(use_tabs=False):
    """
    Message to provide to user when credentials
    fail to make a BCGW Connection.

    Returns:
        (str):
            - Message to user about BCGW credentials.
    """
    if use_tabs:
        tab = "\t"
    else:
        tab = ""
    invalid_bcgw_credentials_message_ = (
        "\nUnable to connect to BC Geographic Warehose (BCGW)."
        "\n\nPlease ensure you entered the correct credentials."
        f"\n\n{tab}To change your BCGW password, visit:"
        f"\n{tab}{tab}https://apps.gov.bc.ca/int/chorapwd/"
        f"\n\n{tab}To reset your BCGW password visit the NRM IT Portal:"
        f"\n{tab}{tab}https://apps.nrs.gov.bc.ca/int/jira/servicedesk/customer/portal/1/create/42"
        f"\n\n{tab}To create a new BCGW account (approval required), visit the NRM IT Portal:"
        f"\n{tab}{tab}https://apps.nrs.gov.bc.ca/int/jira/servicedesk/customer/portal/1/create/261"
        f"\n\n{tab}If you do not have access to the NRM IT Portal, contact:"
        f"\n{tab}{tab}NRM Service Desk - NRMenquiries@gov.bc.ca"
    )
    return invalid_bcgw_credentials_message_


def close_bcgw_connection_credential_check(bcgw_connection):
    """
    Close the Oracle database connection
    and print a message to the terminal.

    Args:
        bcgw_connection (oracledb connection):
            - Oracle connection object to BC Geographic Warehouse (BCGW)
    """
    print(
        "\nClosing BCGW connection (credential check)."
        "\n\nNew connection(s) will be established as needed, "
        "using these verified credentials."
        f"{dashline()}"
    )
    bcgw_connection.close()


# ------------------------------------------------------------------------------
# Temporary hidden directory
# ------------------------------------------------------------------------------

def temp_dir(parent_dir):
    """
    Defines path to temporary, hidden directory.
    Creates the directory if it doesn't exist.

    Args:
        parent_dir (str):
            - Path to parent directory of the temp directory.

    Returns:
        (str):
            - Path to the hidden temp directory.
    """
    temp_dir = os.path.join(parent_dir, ".density_analysis_temp")
    if not os.path.isdir(temp_dir):
        os.mkdir(temp_dir)
        ctypes.windll.kernel32.SetFileAttributesW(temp_dir, FILE_ATTRIBUTE_HIDDEN)
    return temp_dir


# ------------------------------------------------------------------------------
# Dictionary keys
# ------------------------------------------------------------------------------

def lower_limit_key():
    return "lower_limit"


def upper_limit_key():
    return "upper_limit"


# ------------------------------------------------------------------------------
# Acceptable raster value data types
# ------------------------------------------------------------------------------

def acceptable_raster_value_data_types():
    """
    Tuple of data types we accept for original rasters, after
    it has been read by rasterio into a numpy array.

    More info on GeoTiff raster value data types as read by GDAL (rasterio uses GDAL):
    https://gdal.org/drivers/raster/gtiff.html

    Returns:
        (tuple of numpy.dtype objects):
            - Tuple of numpy float objects as read from original GeoTiff by
                rasterio.
    """
    acceptable_data_types = (
        np.float64,
        np.float32
    )

    return acceptable_data_types
