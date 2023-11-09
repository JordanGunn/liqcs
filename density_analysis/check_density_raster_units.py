# ------------------------------------------------------------------------------
# Check the values of the input density rasters fall in
# a range that indicates they have the correct units. (pts/m²)
#
# Written by: Natalie Jackson
# ------------------------------------------------------------------------------

# Public imports
import numpy as np
import rasterio as rio
import sys


# Local imports
try:
    # Use this version of importing (in the try clause) when running from
    # liqcs_gui.py
    import density_analysis.density_analysis_config as density_analysis_config
    import density_analysis.mask_lidar_density_rasters as mask_lidar_density_rasters
    import density_analysis.normalize_density_raster as normalize_density_raster
except Exception:
    # Use this version of importing (in the except clause) when running from
    # density_analysis subfolder scripts (e.g., density_analysis_main.py)
    import density_analysis_config
    import mask_lidar_density_rasters
    import normalize_density_raster


def run_unit_check(input_raster, suspect_median_density_limit=50):
    """
    _summary_

    Args:
        input_raster (str):
            - Path to raster that will have its values
                tested for suspect units.
        suspect_median_density_limit (int, optional):
            - Value above which this function will flag
                rasters with suspiciously large values.
            - Defaults to 50 pts/m².

    Returns:
        good_units (bool): boolean True or False:
            - if True, the values of the provided input file indicate
                it has the correct units (points per square metre)
            - if False, the values of the provided input file indicate
                it has incorrect units (perhaps points per 25 square metres).
    """
    # Read the raster into an array, and determine the nodata value.
    with rio.open(input_raster) as input_dataset:
        nodata = input_dataset.nodata
        density_array = input_dataset.read(1)

    # Make sure the raster contains float values (change to float if not)
    density_array, original_data_type = mask_lidar_density_rasters.array_to_float64(density_array)

    # Replace nodata value with np.nan
    density_array = mask_lidar_density_rasters.replace_nodata_in_array(
        density_array,
        nodata
    )

    # Find the median value of densities, ignoring np.nan values.
    median_density = np.nanmedian(density_array)

    # Check if the median falls below the suspect value limit.
    if median_density < suspect_median_density_limit:
        good_units = True
    else:
        good_units = False

    return good_units


def rasters_with_good_units(
    input_density_raster_list,
    output_dir,
    suspect_median_density_limit,
    normalization_divisor
):
    """
    Check input rasters for good units (pts/m²).
    If the units appear incorrect, normalize them.
    Put the paths of all rasters with good units in a list.

    Args:
        input_density_raster_list (list[str]):
            - List of input density raster paths to check
                for good units (pts/m²)
        output_dir (str):
            - Path to output directory in which to save all outputs
                of the density checker, including any normalized
                rasters.

    Returns:
        rasters_with_good_units (list[str]):
            - List of density raster paths that have passed the unit check.

    Raises:
        RasterUnitError:
            - Raises an exception when normalization fails to make the
            raster pass the unit check.
    """
    rasters_with_good_units = []
    rasters_normalization_failed = []

    for input_raster in input_density_raster_list:
        good_units = None
        number_normalization_attempts = 0

        while not good_units:
            # Check the density raster has expected range of values for units
            good_units = run_unit_check(
                input_raster,
                suspect_median_density_limit=suspect_median_density_limit
            )

            if good_units:
                # If the raster has correct units, add its path
                # to the list of rasters with good units.
                rasters_with_good_units.append(input_raster)
            else:
                # If the raster doesn't have the correct units, normalize it
                # and replcae the path of the original raster with the path
                # of the normalized raster to check again.
                if number_normalization_attempts == 0:
                    original_raster = input_raster
                input_raster = normalize_density_raster.run_normalizer(
                    input_raster,
                    output_dir,
                    normalization_divisor
                )
                number_normalization_attempts += 1
                # If a raster has already been normalized and it still fails
                # the check_density_raster_units.run_unit_check, add the
                # path of the original raster to a list, and move on to
                # the next raster in the input list.
                if number_normalization_attempts >= 2:
                    rasters_normalization_failed.append(original_raster)
                    break

    # If any rasters failed the unit check after attempting normalization,
    # print the list of rasters that failed, and abort the density checker.
    if rasters_normalization_failed:
        print_friendly_rasters_normalization_failed = ""
        for raster in rasters_normalization_failed:
            print_friendly_rasters_normalization_failed += f"\n\t- {raster}"
        print(
            f"{density_analysis_config.dashline()}"
            f"\nDividing raster values by {normalization_divisor} failed "
            "to make the following rasters pass the unit check:"
            f"\n{print_friendly_rasters_normalization_failed}"
            "\n\nPlease review the original rasters and confirm they "
            "represent the correct units (points per square metre)."
            "\n\nTo bypass the unit check, change the check_units parameter "
            "to of main.run_main_density_check to False."
            "\n\t- i.e., main.run_main_density_check(..., check_units=False)"
            "\n\nTo change the value by which raster values are divided to "
            "achieve points per square metre units, provide a new value "
            "through the normalization_divisor parameter of "
            "main.run_main_density_check(), and keep the "
            "check_units parameter set to True."
            "\n\t- e.g., if the input raster units are [pts/100 m²], set "
            "normalization_divisor=100 to convert to [pts/m²]:"
            "\n\t\tmain.run_main_density_check(..., check_units=True, "
            "normalization_divisor=100)"
            "\n\nDensity analysis aborted."
            f"{density_analysis_config.dashline()}"
        )
        sys.exit()

    return rasters_with_good_units


# ------------------------------------------------------------------------------
# Run this module independently

def main():
    # --------------------------------------------------------------------------
    # Testing switches

    test_io = False
    limit_inputs = True
    delete_previous_test_outputs = False

    # --------------------------------------------------------------------------
    # Specify inputs

    input_raster_dir = density_analysis_config.specify_input_dir(
        test_io=test_io,
        limit_inputs=limit_inputs
    )
    input_raster_list = density_analysis_config.get_density_raster_list(input_raster_dir)

    output_dir = density_analysis_config.specify_output_dir(
        test_io=test_io,
        delete_previous_test_outputs=delete_previous_test_outputs
    )

    suspect_median_density_limit = 50

    normalization_divisor = 25

    # --------------------------------------------------------------------------
    # Execute!

    rasters_with_good_units(
        input_raster_list,
        output_dir,
        suspect_median_density_limit,
        normalization_divisor
    )


if __name__ == "__main__":
    main()
