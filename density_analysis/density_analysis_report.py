# ------------------------------------------------------------------------------
# Use the results of the density analysis to create a PDF report.
# Author: Natalie Jackson
# ------------------------------------------------------------------------------

# Built-in imports
import os
import shutil

# Public imports
from datetime import datetime
import textwrap
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Table, TableStyle, Paragraph
from reportlab.graphics import renderPDF
from PyPDF2 import PdfFileMerger, PdfFileReader

# Local imports
try:
    # Use this version of importing (in the try clause) when running from
    # liqcs_gui.py
    import density_analysis.density_analysis_config as density_analysis_config
except Exception:
    # Use this version of importing (in the except clause) when running from
    # density_analysis subfolder scripts (e.g., density_analysis_main.py)
    import density_analysis_config


class ReportColours:
    """
    Theme colours for report.

    Based on:
        https://developer.gov.bc.ca/Colour-Palette
    """
    # Colours from https://developer.gov.bc.ca/Colour-Palette
    colour_regular_above_min = "#2E8540"  # Green
    colour_regular_below_min = "#D8292F"  # Red
    colour_regular_minimum_density_histogram_line = "#FCBA19"  # Gold
    colour_very_low_density = "black"


def time_stamp_string():
    """
    Get the current date as a
    formatted string.

    Format: YYYY-MM-DD

    Returns:
        str:
            - Current dateformatted for printing.
    """
    timestamp = datetime.now()
    formatting_time_stamp_string = timestamp.strftime("%Y-%m-%d")
    return formatting_time_stamp_string


def density_analysis_results_temp_subdir(density_analysis_results_dir):
    """
    Get the full path the directory for
    temporary outputs.

    Args:
        density_analysis_results_dir (str):
            - Path to folder in which to create
                temporary subdirectory.
                This function assumes this folder exists.

    Returns:
        str:
            - Path to folder in which to save
                temporary outputs.
    """
    density_analysis_results_temp_subdir_ = density_analysis_config.temp_dir(
        density_analysis_results_dir
    )
    return density_analysis_results_temp_subdir_


def report_page_path(parent_dir, i):
    """
    Get the path to a report page, given
    a directory in which to save the page,
    and an index that will later be used
    to compile the full report in order.
    (The combined results page has an index 
    of 0, and the individual report pages
    have indices starting at 1)

    Args:
        parent_dir (str):
            - Path to directory in which
                to save report page.
        i (int):
            - Index of report page.
                Report pages will later be
                compiled in order of this index.

    Returns:
        str: Path to report page.
    """
    return os.path.join(
        parent_dir,
        f"report_page_{i + 1}.pdf"
    )


def _geobc_logo_png_path():
    """
    Get the path to GeoBC in the local cloned repo.

    Returns:
        geobc_logo_png_path (str):
            - Path to GeoBC in the local cloned repo.

    """
    geobc_logo_png_path = os.path.join(
        density_analysis_config.working_dir(),
        "boilerplate",
        "png",
        "BCID_GeoBC_RGB_sanBPOE_pos.png"
    )
    return geobc_logo_png_path


def _download_bc_sans_message():
    return (
        "Download the BC Sans font here:\n\n"
        "https://www2.gov.bc.ca/gov/content/governments/services-for-government/policies-procedures/bc-visual-identity/bc-sans"
    )


def _regular_font(report_object, font_size):
    """
    Set the regular font at a given size for a report.

    If it is available, use BC Sans.

    Otherwise, use Helvetica.

    Download BC Sans font here:
    https://www2.gov.bc.ca/gov/content/governments/services-for-government/policies-procedures/bc-visual-identity/bc-sans

    Args:
        report_object (reportlab.pdfgen.canvas.Canvas object):
            - Any reportlab.pdfgen.canvas.Canvas
    """
    try:
        # BC Sans
        font_name = "BC Sans"
        pdfmetrics.registerFont(TTFont(font_name, "BCSans-Regular.ttf"))

    except Exception:
        print(_download_bc_sans_message())
        font_name = "Helvetica"

    getattr(report_object, canvas_object_attr_name()).setFont(font_name, font_size)


def _bold_font(report_object, font_size):
    """
    Set the bold font at a given size for a report.

    If it is available, use BC Sans-Bold.

    Otherwise, use Helvetica-Bold.

    Download BC Sans font here:
    https://www2.gov.bc.ca/gov/content/governments/services-for-government/policies-procedures/bc-visual-identity/bc-sans

    Args:
        report_object (reportlab.pdfgen.canvas.Canvas object):
            - Any reportlab.pdfgen.canvas.Canvas
    """
    try:
        bold_font_name = "BC Sans-Bold"
        pdfmetrics.registerFont(TTFont(bold_font_name, "BCSans-Bold.ttf"))
    except Exception:
        print(_download_bc_sans_message())
        bold_font_name = "Helvetica-Bold"

    report_object.density_report.setFont(bold_font_name, font_size)


def _title_pixels_from_bottom():
    """
    Position of the document title (y-coordinate)
    in pixels from the bottom of the page.

    Letter size page has 792 pixels total
    on the long dimension. (612 x 792)

    Returns:
        int:
            - Number of pixels from the bottom
                of the page to position the
                document title.
    """
    return 710


def _wrap_and_draw_subtitle(
    report_page_object,
    path_to_print,
    wrap_length
):
    """
    Add a long path name as a subtitle to the canvas object,
    wrapping the text at a maximum wrap length, but splitting
    lines between folder names to keep folder names intact.

    Args:
        individual_report_canvas_object
        (reportlab.pdfgen.canvas.Canvas object):
            - The canvas (pdf page) on which to print the subtitle
        path_to_print (str):
            - Path to use as subtitle of pdf page
        font_size (int):
            - Font size for subtitle
        wrap_length (_type_):
            - Maximum number of characters to allow in a line
                before wrapping, although wrapping will be done
                at the last folder separator before this limit.
    """
    j = 0
    path_to_print = f"Input raster: {path_to_print}"
    # Approximate the number lines to print to set the font size in the
    # draw_subtitle_line function.
    # (plus one for good luck..  change to plus two to be more lucky?)
    approx_num_lines_to_print = len(path_to_print) / wrap_length + 1

    while path_to_print:
        path_to_print_next_x_characters = path_to_print[:wrap_length]
        last_slash = path_to_print_next_x_characters.rfind(os.sep)
        if last_slash != -1:
            start_to_last_slash = path_to_print[:last_slash + 1]
            path_to_print = path_to_print[last_slash + 1:]
        else:
            start_to_last_slash = path_to_print
            path_to_print = None
        draw_subtitle_line(report_page_object, j, start_to_last_slash, approx_num_lines_to_print)
        j += 1


def _combined_results_subtitle(
    combined_report_canvas_object,
    num_rasters_to_analyze
):
    """
    Add subtitle to combined results page.

    Args:
        combined_report_canvas_object (RasterDensityReportPage object)):
            - Instance of a RasterDensityReportPage object
        num_rasters_to_analyze (int):
            - Number of rasters used to create report.
    """
    # Define the subtitles as simple strings
    combined_results_subtitle_1 = (
        f"The results on this page include data from {num_rasters_to_analyze} "
        "input rasters."
    )
    combined_results_subtitle_2 = (
        "Subsequent pages of this report show the analysis of "
        "individual rasters contributing to the results on this page."
    )

    # Wrap the subtitles to a certain width
    wrap_width_num_characters = 70
    subtitle_1_list = textwrap.wrap(
        combined_results_subtitle_1,
        width=wrap_width_num_characters
    )
    subtitle_2_list = textwrap.wrap(
        combined_results_subtitle_2,
        width=wrap_width_num_characters
    )

    # Combine the two lists with an empty string entry between
    # to create an empty line between the subtitles.
    subtitle_line_list = subtitle_1_list + [""] + subtitle_2_list

    # Count the number of lines there will be in the subtitle
    # (affects the font size of the subtitle)
    num_lines_to_print = len(subtitle_line_list)

    # Add each line of the subtitle to the report
    for j, line in enumerate(subtitle_line_list):
        draw_subtitle_line(
            combined_report_canvas_object,
            j,
            line,
            num_lines_to_print
        )


def draw_subtitle_line(report_object, line_index, subtitle_line, num_lines_to_print):
    """
    Add an individual line of the subtitle to a report page.
    (Subtitles might be long, and therefore best printed on
    multiple lines).

    Written as a function rather than a method,
    in case someday there is a new class
    for different page types that wants
    to use this subtitle printing strategy.

    Args:
        report_object (RasterDensityReportPage object):
            - Instance of a RasterDensityReportPage object
        line_index (int):
            - Index of subtitle line (first line of
                subtitle is 0, next line is 1, etc.)
        subtitle_line (str):
            - Text for this line of the subtitle
        num_lines_to_print (int):
            - Number of lines to print (affects font size in this function)
    """
    if num_lines_to_print < 6:
        subtitle_font_size = 8
    else:
        subtitle_font_size = 6
    _regular_font(report_object, subtitle_font_size)  # Subtitle font
    report_object.density_report.drawCentredString(
        306,  # x pixels from left
        _title_pixels_from_bottom() - 20 - line_index * (subtitle_font_size + 2),  # y from bottom
        subtitle_line
    )


def _scale_rlg(rlg_object, scale_factor):
    """
    Scale a reportlab graphic (RLG) object
    by some factor, preserving aspect ratio.

    Developed from info here:
    https://www.blog.pythonlibrary.org/2018/04/12/adding-svg-files-in-reportlab/

    Args:
        rlg_object (reportlab graphic (RLG) object):
            - Any RLG object.
        scale_factor (float or int):
            - Value by which to scale object.

    Returns:
        rlg_object (reportlab graphic (RLG) object):
            - The RLG object with new width and height dimensions.
    """
    rlg_object.width = rlg_object.minWidth() * scale_factor
    rlg_object.height = rlg_object.height * scale_factor

    rlg_object.scale(scale_factor, scale_factor)
    return rlg_object


def format_statistic_value(calculation_result_dict_value):
    """
    Format a statistic value as a string from the
    calculation results dictionary to be
    printed nicely.

    e.g., if the value tuple is (17.37641465, 1, "pts/m²"),
    this function returns "17.4 pts/m²"

    Args:
        calculation_result_dict_value (tuple):
            0 (int or float): Value for the statistic
            1 (int): Number of decimal places that statistic
                should be rounded to, to be print-friendly
            2 (str): Print-friendly units of the statistic
            3 (opt dict): Dictionary of limits to test value by

    Returns:
        statistic_value_formatted (str):
            - Statistics value rounded to an appropriate number
                of decimal place, with units.
    """
    # Parse out the relevant calculation result parts
    statistic_value = calculation_result_dict_value[0]
    decimal_places = calculation_result_dict_value[1]   
    units = calculation_result_dict_value[2]

    statistic_value_formatted = (
        # Comma puts commas between every 3 digits,
        # .{number decimal places}f prints the value to
        # the correct number of decimal places
        f"{statistic_value:,.{decimal_places}f} {units}"
    )
    return statistic_value_formatted


def flag_funky_values(calculation_result_dict_value):
    """
    Check if a statistic has a 4th element, (index 3);
    that element is a dictionary of limits by which to flag
    the value if it falls above or below the limits
    defined in that dictionary.

    Args:
        calculation_result_dict_value (tuple):
            0 (int or float): value for the statistic
            1 (int): Number of decimal places that statistic
                should be rounded to, to be print-friendly
            2 (str): Print-friendly units of the statistic
            3 (dict) (optional): Dictionary of range of acceptable
                values for statistic.

    Returns:
        str or None:
            - Symbol to identify values outside expected range
    """
    flag_symbol = "!"
    flag = None

    if len(calculation_result_dict_value) > 3:
        statistic_value = calculation_result_dict_value[0]
        limits_dict = calculation_result_dict_value[3]
        if density_analysis_config.lower_limit_key() in limits_dict:
            lower_limit = limits_dict[density_analysis_config.lower_limit_key()]
            if statistic_value < lower_limit:
                flag = flag_symbol
        if density_analysis_config.upper_limit_key() in limits_dict:
            upper_limit = limits_dict[density_analysis_config.upper_limit_key()]
            if statistic_value > upper_limit:
                flag = flag_symbol

    return flag


def _draw_statistics_table(report_object, calculation_results_dict):
    """
    Add a table of statistics to a report page.

    Written as a function rather than a method,
    in case someday there is a new class
    for different page types that wants
    to use the same table properties.

    Args:
        report_object (RasterDensityReportPage object or similar):
            - Instance of a RasterDensityReportPage object or similar
        calculation_results_dict (dict):
            - Dictionary of calculation results:
                keys (str):
                    Unique, print-friendly description of value.
                values (tuple):
                    0 (int or float): value for the statistic
                    1 (int): number of decimal places that statistic
                        should be rounded to, to be print-friendly
                    2 (str): print-friendly units of the statistic
    """
    canvas = getattr(report_object, canvas_object_attr_name())
    x_position_statistics = 50

    # Table title
    _bold_font(report_object, 10)
    y_position_statistics_table_title = _title_pixels_from_bottom() - 100
    canvas.drawString(
        x_position_statistics,
        y_position_statistics_table_title,
        "Masked Raster Statistics"
    )

    # Put the calculation results dictionary entries
    # in a list of lists, formatting values for printing,
    # to use as table data.
    statistics_table_data = []
    flag_count = 0
    for key in calculation_results_dict:
        formatted_value = format_statistic_value(
            calculation_results_dict[key]
        )
        value_flag = flag_funky_values(
            calculation_results_dict[key]
        )
        if value_flag:
            flag_count += 1
        statistics_table_data.append([key, formatted_value, value_flag])
    if flag_count:
        statistics_table_data.append(
            ["! Value outside expected range", None, None]
        )
        last_row_of_stats = -2
        num_stats_rows = len(statistics_table_data) - 1
    else:
        last_row_of_stats = -1
        num_stats_rows = len(statistics_table_data)

    # Initialize the statistics table with calculation results data
    first_column_width = 176
    second_column_width = 70
    third_column_width = 20
    statistics_table = Table(
        statistics_table_data,
        colWidths=[
            first_column_width,
            second_column_width,
            third_column_width
        ],
    )

    # Define the style settings for the table
    table_style_list = [
        # Format:
        # ("ATTRIBUTE", (from column, from row), (to column, to row), ...)

        # Black line around statistics:
        ("BOX", (0, 0), (1, last_row_of_stats), 0.25, colors.black),
        # Grey inner lines of table:
        ("INNERGRID", (0, 0), (1, last_row_of_stats), 0.25, colors.darkgrey),
        # Left align first column (statistics labels)
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        # Right align second column (statistics values)
        ("ALIGN", (1, 0), (1, last_row_of_stats), "RIGHT"),
        # Font for all cells (overridden for flag column)
        ("FONT", (0, 0), (-1, -1), "BC Sans"),
        # Bold font for flag column
        ("FONT", (-1, 0), (-1, last_row_of_stats), "BC Sans-Bold"),
        # Red text for flag column
        (
            "TEXTCOLOR",
            (-1, 0),
            (-1, last_row_of_stats),
            ReportColours.colour_regular_below_min
        )
    ]
    if flag_count:
        table_style_list.extend(
            (
                # Red text for explanatory note of flags
                (
                    "TEXTCOLOR",
                    (0, -1),
                    (0, -1),
                    ReportColours.colour_regular_below_min
                ),
                # Text size for explanatory note of flags
                (
                    "FONTSIZE",
                    (0, -1),
                    (0, -1),
                    8
                )
            )
        )

    # Apply the table style settings
    statistics_table.setStyle(TableStyle(table_style_list))

    # Alternate table row shading
    for row in range(num_stats_rows):
        if row % 2 == 0:
            row_colour = colors.whitesmoke
        else:
            row_colour = colors.lightgrey
        statistics_table.setStyle(
            TableStyle([("BACKGROUND", (0, row), (1, row), row_colour)])
        )
    available_height = 600
    w, h = statistics_table.wrap(first_column_width, available_height)

    # Add the table to canvas (pdf page)
    statistics_table.drawOn(
        canvas,
        x_position_statistics,
        available_height - h
    )


def report_page_path_attr_name():
    return "report_path_page"


def canvas_object_attr_name():
    return "density_report"


def initialize_general_report_page_attributes(
    page_object,
    report_page_path,
    num_rasters_to_analyze,
    i,
    density_raster_path,
    raster_basenames_list
):
    """
    Initialize the attributes for any page of the report.
    (Combined results page, individual results page, or AllNan page)

    Args:
        page_object (RasterDensityReportPage or AllNanDensityRasterPage object):
            - Class object as defined in this module
        report_page_path (str):
            - Path to the report page
        num_rasters_to_analyze (int):
            - Total number of rasters being analyzed
        i (int): 
            - Index of raster (will be None for combined raster report page)
        density_raster_path (str):
            - Path to density raster being analyzed
                (will be None for combined raster report page)
        raster_basenames_list (_type_):
            - List of rasters used in combined report
                (will be None for individual raster report page)
    """
    setattr(
        page_object,
        report_page_path_attr_name(),
        report_page_path
    )
    setattr(
        page_object,
        canvas_object_attr_name(),
        canvas.Canvas(
            report_page_path,
            pagesize=letter
        )
    )

    # Add GeoBC Logo to report page
    geobc_logo_img = Image(
        _geobc_logo_png_path(),
        width=121,
        height=56
    )
    geobc_logo_img.drawOn(
        getattr(page_object, canvas_object_attr_name()),
        20,  # x pixels from left
        730  # y pixels from bottom
    )

    # Top right table contains the report generation date (row 0)
    # and the raster count label (row 1)
    top_right_table_font_size = 10
    top_right_table_row_height = top_right_table_font_size + 2

    # Raster count label
    _regular_font(page_object, top_right_table_font_size)
    # If there's a combined result, it won't have an index, i.
    if i is None:
        raster_count_label = (
            f"Combined results for {num_rasters_to_analyze} rasters"
        )
    else:
        raster_count_label = (
            f"Results for raster {i + 1} of {num_rasters_to_analyze}"
        )

    top_right_table_data = [
        [f"Report generated: {time_stamp_string()}"],
        [raster_count_label]
    ]
    top_right_table = Table(
        top_right_table_data,
        colWidths=[60],
        rowHeights=[top_right_table_row_height, top_right_table_row_height]
    )
    top_right_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT")
            ]
        )
    )
    top_right_table.wrap(60, 10)
    top_right_table.drawOn(
        getattr(page_object, canvas_object_attr_name()),
        520,  # x
        740  # y
    )

    # Page title
    _bold_font(page_object, 18)
    if i is None:
        # Combined report page title
        title = "Combined Density Raster Analysis Results"
    else:
        title = "Individual Density Raster Analysis Results"
    getattr(page_object, canvas_object_attr_name()).drawCentredString(
        306,  # pixels from left (total 612)
        _title_pixels_from_bottom(),  # pixels from bottom (total 792)
        title
    )

    # Subtitle
    if i is None:
        # Combined report page subtitle
        _combined_results_subtitle(
            page_object,
            num_rasters_to_analyze
        )
    else:
        # Individual raster report page subtitle
        subtitle = density_raster_path
        _wrap_and_draw_subtitle(
            page_object,
            subtitle,
            80
        )


def all_nan_text(plural):
    """
    Text to put on report page when raster contains all nan values,
    either due to:
        - bad input,
        - being completely masked
            - due to not falling in the project area,
            - or from being completely masked by water,
        - or by some other unforeseen reason.

    Args:
        plural (bool):
            - If True, this page is for combined rasters, all of which are all nan.
            - If False, this page is for a single all nan raster.

    Returns:
        (str):
            - Text to put in the report when the masked raster is all nan,
                with html tags for formatting in the reportlab Paragraph object.
    """
    if plural:
        this_these = "these"
        s_no_s = "s"
        a_no_a = ""
        do_does = "do"
        was_were = "were"
    else:
        this_these = "this"
        s_no_s = ""
        a_no_a = "a "
        do_does = "does"
        was_were = "was"
    html_text = (
        f"<b><font color='{ReportColours.colour_regular_below_min}'>Uh oh!</font></b>"
        f"<br/><br/>"
        f"The masking process for {this_these} density raster{s_no_s} produced "
        f"{a_no_a}masked raster{s_no_s} containing only no-data values."
        f"<br/><br/><b><font color='{ReportColours.colour_regular_above_min}'>"
        f"Troubleshooting:"
        f"</font></b>"

        f"<br/><br/>- {do_does.capitalize()} the original input raster{s_no_s} "
        f"have values besides the no-data value?"

        f"<br/><br/>- Values outside the project area are masked. "
        f"{do_does.capitalize()} the input raster{s_no_s} fall "
        f"within the project area?"

        f"<br/><br/>- Values within water polygons are masked. "
        f"{was_were.capitalize()} the original raster{s_no_s} "
        f"completely masked by water polygons within the project area?"
    )
    return html_text


class RasterDensityReportPage:
    """
    Object for a density report page,
    whether for an individual raster,
    or for combined raster results.
    """
    def __init__(
        self,
        report_page_path,
        calculation_results_dict,
        histogram_rlg,
        num_rasters_to_analyze,
        i=None,
        density_raster_path=None,
        classified_raster_rlg=None,
        original_raster_data_type=None,
        raster_basenames_list=None
    ):
        """
        Initialize the report page and attributes.

        Args:
            report_page_path (str):
                - Path to file to save this page as.
            calculation_results_dict (dict):
                - Dictionary of calculation results:
                    keys (str):
                        Unique, print-friendly description of value.
                    values (tuple):
                        0 (int or float): value for the statistic
                        1 (int): number of decimal places that statistic
                            should be rounded to, to be print-friendly
                        2 (str): print-friendly units of the statistic
            histogram_rlg (reportlab graphics (RLG) object):
                - The histogram as an RLG object (vector graphic)
            num_rasters_to_analyze (int):
                - The total number of density rasters being analyzed.
            i (int, optional):
                - Index of raster, if the report page is for an individual raster
                - Defaults to None, which will be the case when the report
                    page is for combined raster results, rather than an
                    individual raster.
            density_raster_path (str, optional):
                - Path to original input raster.
                - Defaults to None, which will be the case when the report
                    page is for combined raster results, rather than an
                    individual raster.
            classified_raster_rlg (ReportLab Graphic object, optional):
                - Classified raster as an RLG Python object (vector graphic),
                    ready to be added to a ReportLab pdf.
                - Defaults to None, which will be the case when the report
                    page is for combined raster results, rather than an
                    individual raster.
            original_raster_data_type (numpy.dtype, optional):
                - Data type of original raster as interpreted by rasterio when
                    reading original raster into a numpy array.
                - Only relevant for individual raster page; defaults to None
                    for combined results page.
            raster_basenames_list (list of str, optional):
                - List of raster file (without full paths, to conserve space on report)
                - Defaults to None. which will be the case when the report
                    page is for an individual raster, rather than combined results.
        """
        # Add the letterhead, titles, page count, etc
        initialize_general_report_page_attributes(
            self,
            report_page_path,
            num_rasters_to_analyze,
            i,
            density_raster_path,
            raster_basenames_list
        )

        # Report whether the original data type is a float
        # or some other unacceptable type.
        if original_raster_data_type:
            self.check_data_type(
                original_raster_data_type
            )

        # Add the classified raster (Results Overview visualization)
        x_position_classified_raster = 260
        y_position_classified_raster = 380
        if i is not None:
            # Add the classified raster (Results Overview visualization)
            classified_raster_rlg_scaled = _scale_rlg(classified_raster_rlg, 0.56)
            renderPDF.draw(
                classified_raster_rlg_scaled,
                self.density_report,
                x_position_classified_raster,
                y_position_classified_raster
            )
        else:
            self.density_report.drawCentredString(
                x_position_classified_raster + 190,
                y_position_classified_raster + 150,
                "See individual raster results for classified overviews."
            )

        # Statistics
        _draw_statistics_table(self, calculation_results_dict)

        # Add the histogram to the report
        histogram_rlg_scaled = _scale_rlg(histogram_rlg, 0.72)
        x_position_histogram = (612 - histogram_rlg_scaled.width) / 2
        renderPDF.draw(
            histogram_rlg_scaled,
            getattr(self, canvas_object_attr_name()),
            x_position_histogram,  # x
            40  # y
        )

        # ? VS CODE/REPORTLAB/PYLANCE BUG
        # ? the code after renderPDF.draw appears unreachable,
        # ? however, it runs...
        # ? Bug reported:
        # ? https://github.com/microsoft/pylance-release/issues/3270
        # ? https://github.com/Distrotech/reportlab/issues/22

        # Save the canvas to a pdf
        getattr(self, canvas_object_attr_name()).save()

    def check_data_type(self, original_data_type):
        """
        Check if the original raster contained float values,
        as it should or some other data type.

        Add the result of this check to the individual raster report page.

        Args:
            original_data_type (numpy.dtype):
                - Data type of original raster as read
                    by rasterio into numpy array.
        """
        canvas = getattr(self, canvas_object_attr_name())
        acceptable_data_types = density_analysis_config.acceptable_raster_value_data_types()

        if original_data_type in acceptable_data_types:
            pass_fail = "Pass"
            pass_fail_text_colour = ReportColours.colour_regular_above_min
        else:
            pass_fail = "Fail"
            pass_fail_text_colour = ReportColours.colour_regular_below_min

        canvas = getattr(self, canvas_object_attr_name())
        x_position_data_type_check = 50
        y_position_data_type_check = _title_pixels_from_bottom() - 72
        _regular_font(self, 10)

        data_type_check_text_html = (
            f"<b>Data type:</b> {original_data_type} "
            f"<b><font color = {pass_fail_text_colour}>{pass_fail}</font></b>"
        )

        data_type_paragraph = Paragraph(data_type_check_text_html)
        data_type_paragraph.wrapOn(
            canvas,
            200,  # Wrap width
            10  # Available height (??)
        )
        data_type_paragraph.drawOn(
            canvas,
            x_position_data_type_check,
            y_position_data_type_check
        )

# End of RasterDensityReportPage class
# ------------------------------------------------------------------------------


class AllNanDensityRasterPage():
    """
    Object for a density report page when,
    whether for an individual raster, or combined results,
    in the case where all values are not a number (nan).
    """
    def __init__(
        self,
        report_page_path,
        num_rasters_to_analyze,
        i=None,
        density_raster_path=None,
        raster_basenames_list=None
    ):
        initialize_general_report_page_attributes(
            self,
            report_page_path,
            num_rasters_to_analyze,
            i,
            density_raster_path,
            raster_basenames_list
        )

        if raster_basenames_list:
            plural = True
        else:
            plural = False

        p1 = Paragraph(all_nan_text(plural))

        p1.wrapOn(
            getattr(self, canvas_object_attr_name()),
            300,  # Wrap width
            50  # Available height (??)
        )
        p1.drawOn(
            getattr(self, canvas_object_attr_name()),
            140,  # p1 x position (left side of paragraph)
            440  # p1 y position (top of paragraph)
        )

        getattr(self, canvas_object_attr_name()).save()


def compile_full_report(
        dir_for_full_report,
        num_rasters_to_analyze,
        combined_all_nan
):
    """
    Compile the individual report pages into
    a multi-page pdf document.

    Then, delete the folder containing the
    individual report pages.

    Args:
        dir_for_full_report (str):
            - Path to folder in which to save
                the full report. This folder also contains the
                subdirectory containing the individual report
                pages to be compiled into the full report.
        num_rasters_to_analyze (int):
            - The total number of rasters being analyzed.
    """
    # Identify the temporary folder where the
    # individual report pages are saved.
    density_analysis_results_temp_subdir_ = density_analysis_results_temp_subdir(
        dir_for_full_report
    )

    # Initialize the merger object
    merger = PdfFileMerger()

    # Set the loop parameters, dependent
    # on whether there is a single or
    # multiple rasters to analyze.
    if num_rasters_to_analyze == 1:
        start_page = 1
    else:
        start_page = 0

    if combined_all_nan:
        end_page = 1
    else:
        end_page = num_rasters_to_analyze + 1

    # Compile the final report page by page
    for pdf_page in range(start_page, end_page):
        merger.append(
            PdfFileReader(
                report_page_path(
                    density_analysis_results_temp_subdir_,
                    pdf_page - 1
                )
            )
        )

    # Define the path for the full report
    full_report_path = os.path.join(
        dir_for_full_report,
        "density_analysis_report.pdf"
    )

    # Save the final report as a pdf
    merger.write(full_report_path)

    # Print a nice message to the console
    print(
        f"{density_analysis_config.dashline()}"
        "Density analysis report created:"
        f"\n\t{full_report_path}"
    )

    # Delete the temp folder containing the individual report pages.
    shutil.rmtree(density_analysis_results_temp_subdir_)


def main():
    print(
        "\nIt's much easier to test this module as it is called from analyze_density.py."
        "\n\nThat's where we make all the graphics to insert into the report, and generate "
        "the statistics to print, too."
        "\n\nThis module is intended to keep the report class "
        "stuff separate, but it means nothing without analyze_density.py."
        "\n\nTry again by running analyze_density.py."
    )


if __name__ == "__main__":
    main()
