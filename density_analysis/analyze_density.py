# Module to analyze density rasters, called by density_analysis_main.py
# Author: Natalie Jackson

# Public imports
import os
import pickle
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import matplotlib.colors
import matplotlib.patches as mpatches
from yaspin import yaspin
import warnings
import sys
import copy
from io import BytesIO
from svglib.svglib import svg2rlg
from pathlib import Path
import math

# Local imports
try:
    # Use this version of importing (in the try clause) when running from
    # liqcs_gui.py
    import density_analysis.density_analysis_config as density_analysis_config
    import density_analysis.density_analysis_report as density_analysis_report
except Exception:
    # Use this version of importing (in the except clause) when running from
    # density_analysis subfolder scripts (e.g., density_analysis_main.py)
    import density_analysis_config
    import density_analysis_report

verbose1 = True
verbose2 = False


# ------------------------------------------------------------------------------
# Functions relating to test conditions...
# ------------------------------------------------------------------------------

def _testing_parameters():
    """
    Get the testing parameters to automatically
    populate inputs without the user.
    Only used when testing this script.

    Delete any previous outputs of this script in the output location.

    Returns:
        output_dir (str): Path to output directory (folder must already exist)
        density_values (tuple): Unpacked tuple from previously pickled outputs
            from the mask_lidar_density_rasters module.
            - 0 (str): Input density raster path
            - 1 (array): Array that follows rasterio
                shape conventions. (band_value(s), x, y)
        minimum_density_requirement (int or float):
            - The default minimum density requirement for
                raster cells that report will show as cutoff for
                pass/fail, as defined in
                density_analysis_config.specify_minimum_density_requirement...
                    ...use_default_minimum_density_requirement.
    """
    output_dir = (
        # r"C:\CODE_DEVELOPMENT\_QC_repo_local_NJ_DD050861\lidar\LiQCS\source\density_analysis"
        # r"\test_files\PERSISTENT_OUTPUTS"
        r"C:\density_grids_nj\output"
    )

    # Delete previous outputs
    import shutil
    for previous_output in os.listdir(output_dir):
        if previous_output.startswith(
            density_analysis_config.density_analysis_results_dirname()
        ):
            shutil.rmtree(os.path.join(output_dir, previous_output))

    density_values = _unpack_density_values_pickle(output_dir)

    minimum_density_requirement = density_analysis_config.specify_minimum_density_requirement(
        use_default_minimum_density_requirement=True
    )

    return output_dir, density_values, minimum_density_requirement


def _unpack_density_values_pickle(output_dir):
    """
    Load the pickled list of density arrays saved in the output directory.

    Args:
        output_dir (str):
            - Path to location of pickled density array list.

    Returns:
        density_values (list of tuples):
            - 0 (str): Input density raster path
            - 1 (array): Array that follows rasterio
                shape conventions. (band_value(s), x, y)
    """
    density_values = pickle.load(
        open(
            os.path.join(output_dir, "density_values.pkl"),
            "rb"
        )
    )

    return density_values


# ------------------------------------------------------------------------------
# Supporting functions
# ------------------------------------------------------------------------------


def filter_all_nan_slice_warning():
    """
    Suppress (ignore) the warning:
    'All-Nan slice encountered'.
    """
    warnings.filterwarnings(
        'ignore',
        message="All-Nan slice encountered"
    )


def percent_above_min_key(minimum_density_requirement):
    """
    Key for calculation_results_dict percent cells
    above minimum density requirement entry.

    Returns:
        (str):
            - Key for calculation_results_dict
                percent cells above minimum
                density requirement entry.
    """
    return f"Pass rate: cells at or above {minimum_density_requirement} pts/m²"


def percent_below_min_key(minimum_density_requirement):
    """
    Key for calculation_results_dict percent cells
    below minimum density requirement entry.

    Returns:
        (str):
            - Key for calculation_results_dict
                percent cells below minimum
                density requirement entry.
    """
    return f"Fail rate: cells below {minimum_density_requirement} pts/m²"


def median_density_key():
    """
    Key for calculation_results_dict median density.

    Used by this module and by density_analysis_report.py.

    Returns:
        str: "Median density"
    """
    return "Median density"


def mean_density_key():
    """
    Key for calculation_results_dict mean density.

    Used by this module and by density_analysis_report.py.

    Returns:
        str: "Mean density"
    """
    return "Mean density"


def standard_deviation_key():
    """
    Key for calculation_results_dict standard deviation of density.

    Used by this module and by density_analysis_report.py.

    Returns:
        str: "Standard deviation of density"
    """
    return "Standard deviation of density"


def _matplotlib_regular_font():
    """
    Sets the matplotlib font to BC Sans (Regular), if it's installed
    in the usual place on Windows.

    If not, don't define the font, to allow matplotlib to revert
    to its default font (probably DejaVu Sans).

    Returns:
        str: Path to font for matplotlib to try to apply.
    """
    regular_font = Path(
        matplotlib.get_data_path(), "C:/Windows/Fonts/BCSans-Regular.ttf"
    )
    if not os.path.isfile(regular_font):
        # If BC Sans isn't installed in the location above,
        # passing this empty string allows matplotlib
        # to revert to whatever default font it uses
        # (probably DejaVu Sans)
        regular_font = ""
    return regular_font


def _matplotlib_bold_font():
    """
    Sets the matplotlib font to BC Sans (Bold), if it's installed
    in the usual place on Windows.

    If not, don't define the font to allow matplotlib to revert
    to its default font (probably DejaVu Sans).

    Returns:
        str: Path to font for matplotlib to try to apply.
    """
    bold_font = Path(matplotlib.get_data_path(), "C:/Windows/Fonts/BCSans-Bold.ttf")
    if not os.path.isfile(bold_font):
        # If BC Sans isn't installed in the location above,
        # passing this empty string allows matplotlib
        # to revert to whatever default font it uses
        # (probably DejaVu Sans)
        bold_font = ""
    return bold_font


# ------------------------------------------------------------------------------
# Class definitions for classified plot
# To add a new class to the classified plot,
#   1. Follow the conventions used in the following classes
#       - Give the object attributes:
#               class_number (int):
#                   - Preserve sequence as it will appear in legend
#               class_colour (str)
#               class_filter (logical filter)
#                   - Use the input density array (rasterio_array)
#               legend_label (str):
#                   - Text for the plot legend
#   2. Add the class to the tuple:
#       classification_objects in plot_classified_raster()
# ------------------------------------------------------------------------------

class Class_1:
    def __init__(self, rasterio_array):
        """
        Initialize the classification parameters for nan values.

        Args:
            rasterio_array (numpy array, rasterio convention):
                - The density array to filter.
        """
        self.class_number = 1
        self.class_colour = "white"
        self.class_filter = np.isnan(rasterio_array)


class Class_2:
    def __init__(self, rasterio_array, minimum_density_requirement):
        """
        Initialize the classification parameters for densities
        that meet or exceed the minimum density requirement.

        Args:
            rasterio_array (numpy array, rasterio convention):
                - The density array to filter.
            minimum_density_requirement (int or float):
                - The minimum density requirement in pts/m².
        """
        self.class_number = 2
        self.class_colour = density_analysis_report.ReportColours.colour_regular_above_min
        self.class_filter = rasterio_array >= minimum_density_requirement
        self.legend_label = f"Meets or exceeds {minimum_density_requirement} pts/m²"


class Class_3:
    def __init__(self, rasterio_array, minimum_density_requirement, very_low_density_threshold):
        """
        Initialize the classification parameters for densities
        below the minimum density requirement and above the very
        low density threshold.

        Args:
            rasterio_array (numpy array, rasterio convention):
                - The density array to filter.
            minimum_density_requirement (int or float):
                - The minimum density requirement in pts/m².
            very_low_density_threshold (int or float):
                - The density below which density is considered very low.
        """
        self.class_number = 3
        self.class_colour = density_analysis_report.ReportColours.colour_regular_below_min
        self.class_filter = (
            (rasterio_array < minimum_density_requirement)
            & (rasterio_array >= very_low_density_threshold)
        )
        self.legend_label = (
            f"{very_low_density_threshold} to {minimum_density_requirement} pts/m²"
        )


class Class_4:
    def __init__(self, rasterio_array, very_low_density_threshold):
        """
        Initialize the classification parameters for densities
        below the very low density threshold.

        Args:
            rasterio_array (numpy array, rasterio convention):
                - The density array to filter.
            very_low_density_threshold (int or float):
                - The density below which density is considered very low.
        """
        self.class_number = 4
        self.class_colour = density_analysis_report.ReportColours.colour_very_low_density
        self.class_filter = rasterio_array < very_low_density_threshold
        self.legend_label = f"Below {very_low_density_threshold} pts/m²"


# ------------------------------------------------------------------------------
# Classifed plot funtions
# ------------------------------------------------------------------------------

def classify_rasterio_array(class_obj, classification_array, colourmap_list):
    """
    Classify rasterio array for a given class definition.

    Args:
        class_obj (Class_X object, as defined in this script):
            - Class_1, Class_2, etc, as defined in this script:
                - Objects with attributes:
                    class_number, class_colour, class_filter
        classification_array (numpy array, rasterio format):
            - Array of classification values (1, 2, 3, etc.)
        colourmap_list (list of str):
            - List of colours that will be used to create
                the matplotlib.colors.ListedColormap

    Returns:
        (numpy array, rasterio format):
            - The classification array updated with the
                given class filter applied.
        (list):
            - The colourmap list updated with the given class colour,
                if that class was present in the input density.
    """
    classification_array[class_obj.class_filter] = class_obj.class_number

    # If there is at least one instance of that class in the array,
    # add the class' colour to the colourmap list.
    if np.count_nonzero(class_obj.class_filter):
        colourmap_list.append(class_obj.class_colour)

    # Return the array classified according to the given filter,
    # and the updated colourmap list. These returns will be unchanged from
    # the inputs if the filter doesn't find any True cases in the density array.
    return classification_array, colourmap_list


def plot_classified_raster(
    density_array,
    minimum_density_requirement,
    very_low_density_threshold
):
    """
    Generate a map-like image (plot -- not really a map, because
    it doesn't have any scale information) of the raster,
    classified with two classes: cells that fail to
    meet the minimum density requirement (red), and cells
    that meet or exceed that requirement (green).

    Strategy borrowed from:
    https://www.neonscience.org/resources/learning-hub/tutorials/classify-raster-thresholds-py

    Args:
        density_array (array):
            - Array that follows rasterio shape conventions.
                (band_value(s), x, y)
        minimum_density_requirement (int or float):
            - Minimum density requirement for raster cells that
                is the cutoff for pass/fail in the classified plot.
        very_low_density_threshold (int or float):
            - Threshold to flag as 'very low' density,
                whether due to poor masking or some other reason.

    Returns:
        classified_raster_rlg (ReportLab Graphic object):
            - Classified raster plot as an RLG Python object (vector graphic),
                ready to be added to a ReportLab pdf.
    """
    # Initialize colourmap list
    # Populate this list only with colours that have raster cells that
    # meet that classification criteria. If the list contains colours
    # associated with classification criteria not represented in the
    # data, the plot classifies cells incorrectly.
    colourmap_list = []

    # Make a copy of the array so the original values
    # are not replaced during classification
    density_array_classify = copy.copy(density_array)

    # Initialize classification objects
    classification_objects = (
        Class_1(density_array),
        Class_2(density_array, minimum_density_requirement),
        Class_3(density_array, minimum_density_requirement, very_low_density_threshold),
        Class_4(density_array, very_low_density_threshold)
    )

    # Initialize dictionary for legend entries
    legend_dict = {}

    # Apply classifications to the density_array_classify,
    # updating the colourmap_list on the way.
    for i, classification_object in enumerate(classification_objects):
        density_array_classify, colourmap_list = (
            classify_rasterio_array(
                classification_object,
                density_array_classify,
                colourmap_list
            )
        )
        # Make legend entries for each class,
        # except the first class (i == 0), which is the np.nan class.
        if i > 0:
            legend_dict[f"legend_entry_class_{i + 1}"] = mpatches.Patch(
                color=classification_object.class_colour,
                label=classification_object.legend_label
            )

    # Put class colours into a matplotlib.colors.ListedColormap
    cmap_pass_fail = matplotlib.colors.ListedColormap(colourmap_list)

    # Initialize matplotlib Figure and Axes objects
    # to use matplotlib API methods
    fig, ax = plt.subplots()

    # Create the plt object with the classified symbology
    ax.imshow(
        density_array_classify[0],
        cmap=cmap_pass_fail,
        interpolation='nearest'  # Otherwise can get aliasing artifacts for some input raster
    )

    # Add legend
    # TODO how to make legend font use _matplotlib_regular_font() ??
    fig.legend(
        handles=list(legend_dict.values()),
        loc="lower right"
    )

    # Add title and subtitle
    # Instead of correcting the units of the plot
    # (see ax.axis('off') in code below),
    # this "Scaled to Raster Extents" title is intended to suppress questions
    # about the scale of the figure.
    # But someone's going to want some more quantitative scale information,
    # sooner or later. (e.g., accurate axes with useful units,
    # or perhaps a scale bar)
    fig.suptitle(
        "Masked Raster Density Overview",
        font=_matplotlib_bold_font(),
        fontweight="bold"
    )
    ax.set_title(
        "Scaled to Raster Extents",
        fontsize=10,
        font=_matplotlib_regular_font(),
    )

    # Turn off the axes' ticks and labels, because the units represent
    # the size of the raster cells (1 unit on axis = 5 metres, assuming
    # raster cell size is 5x5 metres)
    # TODO: edit axis ticks to show useful units (how?)
    # TODO: note -- adding the axes will impact the position of the object
    # on the report page (it will be obscured by other report elements).
    # So, adding axes will also involve reformatting the report document,
    # preferably in a more automatic way than the current pixel-by-pixel
    # method. ReportLab is a lot more powerful than the way it's used here now,
    # but I went for the easier-to-learn-but-clunky method of placing elements
    # where they fit. All these challenges avoided by keeping the axes 'off'.
    ax.axis('off')

    # Save the figure as a reportlab graphics (RLG) object,
    # which is a vector graphic, and looks much crisper than
    # a .png file, which appears pixelated on the report.
    classified_raster_rlg = _matplotlib_fig_to_reportlab_graphic(fig)

    return classified_raster_rlg


# ------------------------------------------------------------------------------
# Calculate statistics functions
# ------------------------------------------------------------------------------

def calculate_statistics(
    density_array,
    num_rasters_to_analyze,
    minimum_density_requirement,
    very_low_density_threshold,
    density_raster_path=None,
    i=None
):
    """
    Compute a variety of descriptive statistics for an array
    of density values.

    Args:
        density_array (array):
            - Array of density values (any shape).
        num_rasters_to_analyze (int):
            - The total number of density rasters being analyzed.
        minimum_density_requirement (int or float):
            - Minimum density requirement for raster cells that
                report will show as cutoff for pass/fail.
        density_raster_path (str, optional):
            - Path to original input raster.
            - Defaults to None.
        i (int, optional): _description_. Defaults to None.

    Returns:
        calculation_results_dict (dict):
            - Dictionary of calculation results:
                keys (str):
                    Unique, print-friendly description of value.
                values (tuple):
                    0 (int or float): value for the statistic
                    1 (int): Number of decimal places that statistic
                        should be rounded to, to be print-friendly
                    2 (str): print-friendly units of the statistic
                    3 (dict) (optional): Dictionary of range of acceptable
                        values for statistic.
    """
    # ! temporary for testing
    # print(density_array)
    # density_array = density_array[::10000]
    # print(density_array)

    # Assess number of cells with no data
    num_raster_cells = np.size(density_array)
    num_nan_cells = np.count_nonzero(np.isnan(density_array))
    num_raster_cells_with_values = num_raster_cells - num_nan_cells
    num_non_zero_values = np.count_nonzero(density_array) - num_nan_cells
    num_zero_values = num_raster_cells_with_values - num_non_zero_values
    try:
        percent_zeroes = num_zero_values / num_raster_cells_with_values * 100
    except ZeroDivisionError:
        percent_zeroes = np.nan

    # Minimum points per square metre requirement
    num_cells_above_min_density = np.count_nonzero(
        density_array >= minimum_density_requirement
    )
    try:
        percent_cells_above_min_density = (
            num_cells_above_min_density / num_raster_cells_with_values * 100
        )
        percent_cells_below_min_density = (
            100 - percent_cells_above_min_density
        )
    except ZeroDivisionError:
        percent_cells_above_min_density = np.nan
        percent_cells_below_min_density = np.nan

    # Cells below very low density threshold
    num_cells_very_low_density = (
        np.count_nonzero(density_array < very_low_density_threshold)
        + num_zero_values
    )
    try:
        percent_very_low_density = (
            num_cells_very_low_density / num_raster_cells_with_values * 100
        )
    except ZeroDivisionError:
        percent_very_low_density = np.nan

    # Pass/fail excluding very low density points
    cells_with_values_above_very_low = num_raster_cells_with_values - num_cells_very_low_density
    try:
        percent_pass_if_very_low_excluded = (
            num_cells_above_min_density / cells_with_values_above_very_low * 100
        )
        # TODO: these print statements for debugging:
        # print(
        #    f"num cells above min: {num_cells_above_min_density}"
        #    f"\ncells with values above very low: {cells_with_values_above_very_low}"
        #    f"\nPERCENT: {percent_pass_if_very_low_excluded}"
        # )
        percent_fail_if_very_low_excluded = (
            100 - percent_pass_if_very_low_excluded
        )
    except ZeroDivisionError:
        percent_pass_if_very_low_excluded = np.nan
        percent_fail_if_very_low_excluded = np.nan

    # Print out some statistics
    if verbose1:
        print(density_analysis_config.dashline())
        if density_raster_path:
            print(
                f"Raster {i + 1} of {num_rasters_to_analyze}: "
                f"{os.path.basename(density_raster_path)}"
                # f"\n\nShape of raster (cell values, x, y): {density_array.shape}"
            )
        else:
            print(
                f"Combined results for {num_rasters_to_analyze} rasters:"
                f"\n"
            )
    if verbose2:
        print(
            f"Median: {np.nanmedian(density_array)} pts/m²"
            f"\nMean: {round(np.nanmean(density_array), 1)} pts/m²"
            f"\nStandard deviation: {round(np.nanstd(density_array), 1)} pts/m²"
            f"\nNumber of cells in raster with values: {num_raster_cells_with_values}"
            f"\nNumber of cells in raster with NaN values: {num_nan_cells}"
            f"\nNumber of cells with non-zero values: {num_non_zero_values}"
            f"\nNumber of cells wtih zero values: {num_zero_values}"
            f"\nPercent of cells with zero density (no lidar points): "
            f"{round(percent_zeroes, 1)} %"
            f"\nNumber of cells with density between 0 and {very_low_density_threshold}: "
            f"{num_cells_very_low_density}"
            f"\nPercent of cells with density between 0 and {very_low_density_threshold}: "
            f"{percent_very_low_density}"
            f"\nPercent of cells that meet minimum density requirement "
            f"(≥ {minimum_density_requirement} pts/m²): "
            f"{round(percent_cells_above_min_density, 1)} %"
            f"\nPercent pass if very low densities excluded: "
            f"{round(percent_pass_if_very_low_excluded, 1)} %"
            f"\nPercent fail if very low densities excluded: "
            f"{round(percent_fail_if_very_low_excluded, 1)} %",
            flush=True
        )

    # Generate the calculation results dictionary.
    # Format:
    #   key (str):
    #       - Unique description of dictionary element.
    #   value (tuple):
    #       0: Calculated value (int or float)
    #       1: Number of decimal places to round value
    #           to limit printing to significant digits (int)
    #       2: Units of value for printing (str)
    #       3: (Optional) Dictionary with keys either "below" or "above"
    #           (saved as functions in density_analysis_config.lower_limit_key(),
    #           density_analysis_config.upper_limit_key()),
    #           with an associated limit to flag the value outside of
    #           expected or acceptable values.
    calculation_results_dict = {}

    calculation_results_dict.update(
        {
            "Cells used in analysis": (num_raster_cells_with_values, 0, ""),
            # "Null cells (masked, etc.)": (num_nan_cells, 0, ""),
            # "Cells with non-zero values": (num_non_zero_values, 0, ""),
            # "Cells where density is zero": (num_zero_values, 0, ""),
            # "Percent cells with zeroes": (percent_zeroes, 1, "%"),
            f"Cells where density is 0 to {very_low_density_threshold} pts/m²": (
                num_cells_very_low_density,
                0,
                ""
            ),
            f"Percent cells with 0 to {very_low_density_threshold} pts/m²": (
                percent_very_low_density,
                1,
                "%",
                {
                    # Flag percentage of cells with very low density
                    # above this limit
                    density_analysis_config.upper_limit_key(): 5
                }
            ),
            median_density_key(): (
                np.nanmedian(density_array),
                1,
                "pts/m²",
                {
                    # Flag median values below this limit
                    density_analysis_config.lower_limit_key(): minimum_density_requirement,
                    # Flag median values above this limit
                    density_analysis_config.upper_limit_key(): 50
                }
            ),
            mean_density_key(): (
                np.nanmean(density_array),
                1,
                "pts/m²",
                {
                    # Flag mean values below this limit
                    density_analysis_config.lower_limit_key(): minimum_density_requirement,
                    # Flag mean values above this limit
                    density_analysis_config.upper_limit_key(): 50
                }
            ),
            standard_deviation_key(): (
                np.nanstd(density_array),
                1,
                "pts/m²",
                {
                    # Flag standard deviation values below this limit
                    density_analysis_config.upper_limit_key(): 1,
                    # Flag standard deviation values above this limit
                    density_analysis_config.upper_limit_key(): 50
                }
            ),
            f"Cells at or above {minimum_density_requirement} pts/m²": (
                num_cells_above_min_density,
                0,
                ""
            ),
            percent_above_min_key(minimum_density_requirement): (
                percent_cells_above_min_density,
                1,
                "%",
                {
                    # Flag percentage of passing cells below this limit
                    density_analysis_config.lower_limit_key(): 95
                }
            ),
            percent_below_min_key(minimum_density_requirement): (
                percent_cells_below_min_density,
                1,
                "%",
                {
                    # Flag percentage of failing cells above this limit
                    density_analysis_config.upper_limit_key(): 5
                }
            ),
            f"Pass rate if 0 to {very_low_density_threshold} pts/m² excluded": (
                percent_pass_if_very_low_excluded,
                1,
                "%",
                {
                    # Flag percentage of passing cells if low density values
                    # excluded below this limit
                    density_analysis_config.lower_limit_key(): 95
                }
            ),
            f"Fail rate if 0 to {very_low_density_threshold} pts/m² excluded": (
                percent_fail_if_very_low_excluded,
                1,
                "%",
                {
                    # Flag percentage of failing cells if low density values
                    # excluded above this limit
                    density_analysis_config.upper_limit_key(): 5
                }
            ),
        }
    )

    return calculation_results_dict


def _matplotlib_fig_to_reportlab_graphic(fig):
    """
    Convert a matplotlib Figure to a
    reportlab graphic (RLG) object.

    RLG graphics are vectors, which look crisper
    than pixelated raster (.png) graphics.

    Args:
        fig (matplotlib Figure):
            - The matplotlib Figure (plot) with all
                data and annotation added and
                ready for publishing.

    Returns:
        fig_rlg (reportlab graphics (RLG) object):
            - The plot as an RLG object.
    """
    # Initialize bytes object
    fig_svg = BytesIO()

    # Alert pyinstaller to use svg backend
    # This line of code not required for .py operation,
    # but is needed in the .exe.
    # See: https://github.com/pyinstaller/pyinstaller/issues/6760
    matplotlib.use("svg")

    # Save the matplotlib fig into the bytes object
    # in scalable vector graphics (SVG) format.
    fig.savefig(fig_svg, format="SVG")

    # Rewind pointer to beginning of the bytes object
    fig_svg.seek(0)

    # Convert the SVG object to a
    # reportlab graphics (RLG) object,
    # so we can put it in a pdf using reportlab.
    # We'll scale the object to the desired size later,
    # just before drawing it on the reportlab canvas.
    fig_rlg = svg2rlg(fig_svg)

    return fig_rlg


def make_histogram(
    density_array,
    calculation_results_dict,
    histogram_title,
    minimum_density_requirement,
    very_low_density_threshold,
    num_rasters_to_analyze=None
):
    """
    Generate a histogram of density values, with
    labels, annotation, and a thematic colour scheme,
    ready to be added to a reportlab pdf as a vector graphic.

    Args:
        density_array (numpy array):
            - Array of density values.
        calculation_results_dict (dict):
            - Dictionary of calculation results:
                keys (str):
                    Unique, print-friendly description of value.
                values (tuple):
                    0 (int or float): value for the statistic
                    1 (int): number of decimal places that statistic
                        should be rounded to, to be print-friendly
                    2 (str): print-friendly units of the statistic
        histogram_title (str):
            - Title for histogram.
        minimum_density_requirement (int or float):
            - Minimum density requirement for raster cells that
                report will show as cutoff for pass/fail.
        very_low_density_threshold (int or float):
            - Density limit to flag as very low
        num_rasters_to_analyze (int):
            - The total number of density rasters being analyzed.

        Returns:
            histogram_rlg (reportlab graphics (RLG) object):
                - Vector graphic version of the histogram,
                    ready to be added to a reportlab pdf.
    """
    # Parse out relevant values from the calculation results
    # to be used in histogram annotation
    percent_cells_above_min_density = calculation_results_dict[
        percent_above_min_key(minimum_density_requirement)
    ]
    percent_cells_below_min_density = calculation_results_dict[
        percent_below_min_key(minimum_density_requirement)
    ]

    # Determine if the density array represents one raster,
    # or multiple rasters combined.
    # Method:
    #   If the density array is the combined array, it has
    #   been flattened to have a shape of (num_values, ).
    #   The shape of the combined array is a tuple
    #   of length 1: (num_values, )
    #   In contrast, the individual raster arrays have
    #   dimensions (1, num_cells_x_direction, num_cells_y_direction),
    #   according to the rasterio conventions by which they
    #   were generated.
    #   The shape of the individual raster arrays are tuples
    #   of length 3: (1, num_cells_x_direction, num_cells_y_direction).
    #   So, we know if the length of the shape of the density array
    #   is 1, then the result is for multiple rasters combined.
    if len(np.shape(density_array)) == 1:
        combined_results = True
    else:
        combined_results = False

    with yaspin(
        text="Counting frequencies to create histogram...",
        color='green',
        timer=True
    ):
        # Set histogram colours
        hist_colour_below_min = (
            density_analysis_report.ReportColours.colour_regular_below_min
        )
        hist_colour_above_min = (
            density_analysis_report.ReportColours.colour_regular_above_min
        )
        min_density_line_colour = (
            density_analysis_report.ReportColours.colour_regular_minimum_density_histogram_line
        )
        hist_colour_very_low_density = (
            density_analysis_report.ReportColours.colour_very_low_density
        )

        # Set the maximum x-value to show in the histogram.
        # Values above this threshold will still be represented
        # in statistics, but not shown in the histogram.
        # max_density_to_show_in_hist = 50
        try:
            # Set the max density to show in histogram to be
            # the median plus 3x the standard deviation (~3 sigma)
            # This try will fail for cases where the median or standard
            # deviation is np.nan, which means we've got more problems than
            # just the histogram...  (e.g. sample file Density_Grid.tif)
            max_density_to_show_in_hist = math.ceil(
                calculation_results_dict[median_density_key()][0]
                + calculation_results_dict[standard_deviation_key()][0] * 3
            )
        except Exception:
            max_density_to_show_in_hist = 50

        # Create the matplotlib Figure and Axes objects
        # More info about using the matplotlib API,
        # rather than the plotly command technique.
        # (i.e., working with the Figure and Axes objects, rather
        # than just calling plotly methods. Working with
        # the Figure and Axes objects provides more formatting
        # options than the limited plotly methods.)
        # https://matplotlib.org/stable/api/index.html
        fig, ax = plt.subplots()

        # Create the histogram in the Axes object
        n, bins, patches = ax.hist(
            density_array[~np.isnan(density_array)],  # Ignore nan values
            range(0, max_density_to_show_in_hist),  # Range of bins to show in histogram
            density=True,  # Normalize y-axis
            histtype='barstacked',  # Stack values from each row of raster in same bars
        )

        # Plot a gold vertical line at the minimum density value
        ax.vlines(
            minimum_density_requirement,
            0,  # Line starts at x-axis
            n.max() + 0.1,  # Make the line extend above the histogram values
            color=min_density_line_colour  # Gold
        )

        # Colour the bars below the minimum density red, bars above green
        for patch in patches:
            if patch.get_x() < very_low_density_threshold:
                patch.set_facecolor(hist_colour_very_low_density)
            elif (
                patch.get_x() < minimum_density_requirement
                and patch.get_x() >= very_low_density_threshold
            ):
                patch.set_facecolor(hist_colour_below_min)  # Red
            else:
                patch.set_facecolor(hist_colour_above_min)  # Green

        # Add some annotation to label the minimum density requirement
        # (could use a legend item instead, but I like this better...
        # TODO ...unless this looks too goofy with non-8 minimum density
        # requirements... consider changing to fit all minimum density
        # scenarios)
        ax.annotate(
            f"Minimum density requirement: {minimum_density_requirement} pts/m²",
            (minimum_density_requirement + 1, n.max() + 0.05),
            font=_matplotlib_bold_font(),
            weight='bold',
            color=min_density_line_colour,  # Gold
        )

        # Add some annotation for the percent of raster cells
        # above the minimum density requirement
        percent_pass_formatted = density_analysis_report.format_statistic_value(
            percent_cells_above_min_density
        )
        ax.annotate(
            f"Pass: {percent_pass_formatted}",
            # Placement of this annotation:
            (
                (max_density_to_show_in_hist + 3 * minimum_density_requirement) / 4,
                n.max() + 0.02
            ),
            font=_matplotlib_regular_font(),
            color=hist_colour_above_min
        )

        # Add some annotation for the percent of raster cells
        # below the minimum density requirement
        percent_fail_formatted = density_analysis_report.format_statistic_value(
            percent_cells_below_min_density
        )
        ax.annotate(
            f"Fail: {percent_fail_formatted}",
            # Placement of this annotation:
            (
                0,  # minimum_density_requirement / 8,
                n.max() + 0.02
            ),
            font=_matplotlib_regular_font(),
            color=hist_colour_below_min  # Red
        )

        # Add some annotation letting us know the histogram is
        # cut off at a certain x-value.
        ax.text(
            1,  # x position
            -0.2,  # y position
            f"Densities above {max_density_to_show_in_hist} pts/m² "
            "\nnot shown on histogram.",
            ha='right',
            fontsize=8,
            font=_matplotlib_regular_font(),
            # Set units of x and y positions to be normalized to max axis value
            # (default transform is axis units, which can change depending on inputs)
            transform=ax.transAxes
        )

        # Add titles and labels to histogram
        if combined_results:
            optional_plural_s = "s"
        else:
            optional_plural_s = ""
        fig.suptitle(
            f"Frequency of Density Values for Masked Lidar Density Raster{optional_plural_s}",
            font=_matplotlib_bold_font(),
            fontweight="bold"
        )
        ax.set_title(
            f"{histogram_title}",
            fontsize=10,
            font=_matplotlib_regular_font()
        )
        ax.set_xlabel(
            "Density [points per square metre]",
            font=_matplotlib_regular_font()
        )
        ax.set_ylabel(
            f"Frequency of density in masked raster{optional_plural_s}",
            font=_matplotlib_regular_font()
        )

        # Change the y-axis to show percents instead of fractions of 1
        fig.gca().yaxis.set_major_formatter(PercentFormatter(1, decimals=0))

        # Save the figure as a reportlab graphics (RLG) object
        histogram_rlg = _matplotlib_fig_to_reportlab_graphic(fig)

        # Close the figure to avoid using too much memeory
        plt.close(fig)

    return histogram_rlg


# ------------------------------------------------------------------------------
# Run the analyze_density routine.
# Called by __main__ or main.py.
# ------------------------------------------------------------------------------

def analyze_density_values(
    density_values,
    output_dir,
    minimum_density_requirement
):
    """
    Analyze the values of raster densities
    for various descriptive statistics, and
    save the results in a pdf report.

    Args:
        density_values (list of tuples, [(str, array), (str, array), ...]:
            Tuple elements:
                - 0 (str): Input density raster path
                - 1 (array): Array that follows rasterio
                    shape conventions. (band_value(s), x, y)
                - 2 (numpy.dtype): Data type of original raster
                    as read by rasterio into numpy array.
        output_dir (str):
            - Path to output directory where results will be saved.
        minimum_density_requirement (int or float):
            - Minimum density requirement for raster cells that
                report will show as cutoff for pass/fail.
    """
    # Ignore "All-Nan slice" warnings
    filter_all_nan_slice_warning()

    # Set the "very low density" threshold
    # (Appears as black in the classified raster and histogram,
    # and pass/fail rate is calculated in statistics for case
    # where very low densities are excluded from calculations)
    very_low_density_threshold = 1

    # Identify (and create if necessary) a folder within the output directory
    # for density analysis outputs
    density_analysis_results_dir = density_analysis_config.density_analysis_results_dir_path(output_dir)

    # Make a temp folder within the density analysis
    # results folder in which to save files that
    # will be used to produce the final output,
    # so that they can be easily deleted after being
    # incorporated into the final report.
    density_analysis_results_temp_subdir_ = (
        density_analysis_report.density_analysis_results_temp_subdir(
            density_analysis_results_dir
        )
    )

    num_rasters_to_analyze = len(density_values)
    combined_array_values = np.array([])

    raster_basenames_list = []

    for i, density_raster_path_array_and_datatype in enumerate(density_values):

        # Parse out the raster path and the array
        # from the density_values object
        density_raster_path = density_raster_path_array_and_datatype[0]
        density_array = density_raster_path_array_and_datatype[1]
        original_raster_data_type = density_raster_path_array_and_datatype[2]

        # Get the basename of the raster, and add it to a list,
        # to use in various places on the report
        raster_basename = os.path.basename(density_raster_path)
        raster_basenames_list.append(raster_basename)

        # Append the data of the array to an array that will contain
        # data values from all input rasters.
        # The shape of the input rasters/arrays is not preserved
        # in the append; the combined_array_values array will have
        # a shape of (total_data_values, ), whereas the input arrays,
        # represented by the density_array variables, have dimensions of
        # (1, number_cells_x_direction, number_cells_y_direction),
        # which is the rasterio convention.
        combined_array_values = np.append(
            combined_array_values,
            density_array
        )

        # Define the path for an individual raster report
        individual_raster_report_path = density_analysis_report.report_page_path(
            density_analysis_results_temp_subdir_,
            i
        )

        # Check if the density array only contains nan values
        if np.count_nonzero(~np.isnan(density_array)):

            # Plot raster i classified by whether it meets
            # the minimum density requirement
            classified_raster_rlg = plot_classified_raster(
                density_array,
                minimum_density_requirement,
                very_low_density_threshold
            )

            # Make some calculations on raster i
            calculation_results_dict = calculate_statistics(
                density_array,
                num_rasters_to_analyze,
                minimum_density_requirement,
                very_low_density_threshold,
                density_raster_path,
                i
            )

            # Make histogram for raster i
            histogram_rlg = make_histogram(
                density_array,
                calculation_results_dict,
                raster_basename,  # Histogram title
                minimum_density_requirement,
                very_low_density_threshold,
                num_rasters_to_analyze=num_rasters_to_analyze
            )

            # Add results for raster i to a pdf
            density_analysis_report.RasterDensityReportPage(
                individual_raster_report_path,
                calculation_results_dict,
                histogram_rlg,
                num_rasters_to_analyze,
                i=i,
                density_raster_path=density_raster_path,
                classified_raster_rlg=classified_raster_rlg,
                original_raster_data_type=original_raster_data_type
            )

        else:
            density_analysis_report.AllNanDensityRasterPage(
                individual_raster_report_path,
                num_rasters_to_analyze,
                i=i,
                density_raster_path=density_raster_path
            )

    combined_all_nan = None

    if num_rasters_to_analyze > 1:
        # Define the path of the combined results page
        # Provide -1 as index to put the filename alphanumerically
        # before the individual report pages, which have i
        # indices starting at 0.
        combined_results_report_path = density_analysis_report.report_page_path(
            density_analysis_results_temp_subdir_,
            -1
        )

        # Check if all the combined arrays contain all nan values
        if np.count_nonzero(~np.isnan(combined_array_values)):

            # Make some calculations on the combined array values
            combined_calculation_results_dict = calculate_statistics(
                combined_array_values,
                num_rasters_to_analyze,
                minimum_density_requirement,
                very_low_density_threshold
            )

            # Make histogram for combined array values
            combined_results_histogram_rlg = make_histogram(
                combined_array_values,
                combined_calculation_results_dict,
                f"Results for {num_rasters_to_analyze} Combined Rasters",
                minimum_density_requirement,
                very_low_density_threshold
            )

            # Add combined results to a pdf page
            density_analysis_report.RasterDensityReportPage(
                combined_results_report_path,
                combined_calculation_results_dict,
                combined_results_histogram_rlg,
                num_rasters_to_analyze,
                raster_basenames_list=raster_basenames_list
            )

            # ? VS CODE/REPORTLAB/PYLANCE BUG
            # ? the code after renderPDF.draw appears unreachable,
            # ? however, it runs...
            # ? Bug reported:
            # ? https://github.com/microsoft/pylance-release/issues/3270
            # ? https://github.com/Distrotech/reportlab/issues/22

        else:
            combined_all_nan = True

            density_analysis_report.AllNanDensityRasterPage(
                combined_results_report_path,
                num_rasters_to_analyze,
                raster_basenames_list=raster_basenames_list
            )

    # Compile pdf report pages into a single pdf document,
    # saved in the main results output folder.
    # Delete the temp folder containing the individual report pages.
    density_analysis_report.compile_full_report(
        density_analysis_results_dir,
        num_rasters_to_analyze,
        combined_all_nan
    )


# ------------------------------------------------------------------------------
# Run this module independently from upstream modules
# ------------------------------------------------------------------------------
def main():
    # --------------------------------------------------------------------------
    # Test condition switch
    # --------------------------------------------------------------------------

    # Set to True to use testing data (pre-produced .pkl file)
    testing_analyze_density = True

    # --------------------------------------------------------------------------
    # Set parameters for analyze_density_values function
    # --------------------------------------------------------------------------

    if testing_analyze_density:
        print("\nUsing testing parameters...")
        output_dir, density_values, minimum_density_requirement = (
            _testing_parameters()
        )

    else:
        print(
            "To use testing parameters, set testing_analyze_density to True."
            "\n\nTo use other parameters, update main()"
            "or run from density_analysis_main.py."
        )
        sys.exit()

    # --------------------------------------------------------------------------
    # Execute!
    # --------------------------------------------------------------------------

    analyze_density_values(
        density_values,
        output_dir,
        minimum_density_requirement
    )


if __name__ == "__main__":
    main()