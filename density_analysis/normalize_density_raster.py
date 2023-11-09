# ------------------------------------------------------------------------------
# Some of our density grids have values reported in number of points
# per 25 square metres (the number of points in the 25 m² raster cells).
# We want the density reported in points per square meter (pts/m²).
# This script normalizes the density values (changes the units from
# to points per 25 square metres to points per square metre).
#
# Author: Natalie Jackson
# ------------------------------------------------------------------------------

import rasterio as rio
import rasterio.plot as rioplt
import os

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
# Code settings:

def _verbose():
    """
    Set whether to print additional messages to the console.

    Returns:
        bool: if True, print additional messages to the console
    """
    return False


# ------------------------------------------------------------------------------
# Primary coordination function

def run_normalizer(input_raster, output_dir, normalization_divisor):
    """
    Divide the raster values of an input raster by
    a given value (normalization_divisor).

    Args:
        input_raster (str):
            - Path to input raster
        normalization_divisor (int):
            - Value by which to divide input raster values
            - e.g., if the input raster units are points per 25 m²,
                the normalization_divisor is 25.

    Returns:
        output_raster (str):
            - Path to output raster
    """
    # --------------------------------------------------------------------------
    # Get the parts of the input file path (directory, filename, extension)

    _, filename, ext = decompose_input_raster_path(input_raster)

    # --------------------------------------------------------------------------
    # File management:

    # Make a subdirectory for the normalized output
    normalized_density_grids_subdir = os.path.join(
        output_dir,
        "NORMALIZED_DENSITY_GRIDS"
    )
    if not os.path.isdir(normalized_density_grids_subdir):
        os.mkdir(normalized_density_grids_subdir)
    normalized_raster_path = os.path.join(
        normalized_density_grids_subdir,
        f"{filename}_DIVIDED_BY_{normalization_divisor}{ext}"
    )

    # Delete the output file if we made it before
    if os.path.isfile(normalized_raster_path):
        os.unlink(normalized_raster_path)

    # --------------------------------------------------------------------------
    # Raster manipulation:

    # Read the original raster
    with rio.open(input_raster) as src:
        raster_array = src.read()
        metadata = src.meta

    # Determine the nodata value for the input raster
    no_data_value = metadata['nodata']

    # Have a look at the raster shape and some of its values (optional)
    if _verbose():
        print(
            f"ORIGINAL: {raster_array.shape}"
            f"\n{raster_array}"
        )

    # Normalize that raster! (change units from pts/25m² - or whatever
    # normalization_divisor value if not 25 - to pts/m²),
    # except for cells with the 'nodata' value.
    # Cells with the nodata value keep the nodata value.
    raster_array[raster_array != no_data_value] = (
        raster_array[raster_array != no_data_value] / normalization_divisor
    )

    print(
        f"\nRaster values divided by {normalization_divisor} "
        f"and saved to:\n\t{normalized_raster_path}"
    )

    # Have a look at the raster shape and some of its values (optional)
    if _verbose():
        print(
            f"MODIFIED: {raster_array.shape}"
            f"\n{raster_array}"
        )

    # Write a new raster with the new units in the new subdirectory (original file unaffected)
    with rio.open(normalized_raster_path, "w", **metadata, compress="LZW") as dest:
        dest.write(raster_array)

    if _verbose():
        # Open output directory?
        ask_open_outdir(normalized_density_grids_subdir)

        # Show a visualization in a temporary pop-up?
        ask_open_visualization(raster_array, filename)

        # Bye!
        density_analysis_config.exit_message()

    return normalized_raster_path


# ------------------------------------------------------------------------------
# Supporting functions

def colormap():
    """
    Colormap for visuals
    https://matplotlib.org/stable/tutorials/colors/colormaps.html
    """
    return 'nipy_spectral'


def decompose_input_raster_path(input_raster):
    """
    _summary_

    Args:
        input_raster (_type_): _description_

    Returns:
        input_dir (str): _description_
            - the directory containing the input 
        input_filename (str):
            - the filename without the folder or extension
            - e.g., "my_raster"
        ext (str):
            - the extension of the input file
            - e.g., ".tif"
    """
    input_dir = os.path.dirname(input_raster)
    input_filename_with_ext = os.path.basename(input_raster)
    input_filename, ext = os.path.splitext(input_filename_with_ext)

    return input_dir, input_filename, ext


def ask_open_outdir(outdir):
    """
    Ask at the terminal if you'd like to
    open the output directory.
    """
    open_outdir = None
    while open_outdir not in ("Y", "N"):
        open_outdir = input(
            "\nOpen the output directory? (y/n) "
        )
        try:
            open_outdir = open_outdir.capitalize()
        except Exception:
            pass
        if open_outdir == "Y":
            import webbrowser
            webbrowser.open(outdir)


# ------------------------------------------------------------------------------
# Visualization:

def ask_open_visualization(raster_array, filename):
    """
    Ask at the terminal if you'd like to
    open a little visualization of the raster.
    """
    show_visuals = None
    while show_visuals not in ("Y", "N"):
        show_visuals = input(
            "\nShow the raster in a temporary pop-up figure? (y/n) "
        )
        try:
            show_visuals = show_visuals.capitalize()
        except Exception:
            pass
        if show_visuals == "Y":
            _show_visuals(raster_array, filename)


def _show_visuals(raster_array, filename):
    """
    Have a look at the raster in a nifty little pop-up.
    """
    message_while_showing_figure = (
        "\nImage of raster in figure pop-up. Close figure to proceed."
    )
    print(message_while_showing_figure, end="\r")
    rioplt.show(
        raster_array,
        cmap=colormap(),
        title=f"Density Raster for {filename}"
    )
    print(" " * len(message_while_showing_figure))


# ------------------------------------------------------------------------------
# Run module independently
def main():
    input_raster = density_analysis_config.specify_input_raster_path()
    output_dir = density_analysis_config.specify_output_dir()

    normalized_raster = run_normalizer(
        input_raster,
        output_dir,
        25
    )

    print(f"Normalized raster:\n\t{normalized_raster}")    


if __name__ == "__main__":
    main()
