import re


def filename_is_bad(filename: str) -> bool:

    """
    Return filename if it does not conform to GeoBC naming conventions.

    Check if input filename for lidar data is "bad," aka does not fit GeoBC
    naming conventions. Works for both raw las/las files and production
    las/las files.

    @param filename: Filename to check.
    @return: True if filename is invalid, otherwise, False.
    """

    production_lidar_regex = (
        r'bc_\d{3}[a-z]\d{3}_(\d_){3}x(yes|no)_(\d{1,2}|\dp\d[1-9])_(bcalb|utm07|utm7|utm08|utm8|utm09|utm9|utm10|utm11)_2\d{3}\.la(s|z)'
    )
    raw_lidar_regex = (
        r'[0-9]{1,5}_[0-9]{3}_[0-9]{4}_([a-z0-9]?)+([A-Z0-9\-?]).*\.la(s|z)'
    )
    filename = filename.split('\\')[-1]
    if (
        re.fullmatch(production_lidar_regex, filename) is None
        and re.fullmatch(raw_lidar_regex, filename) is None
        and not filename.lower().endswith(".out")  # Trajectory files
        and not filename.endswith(".tiff")  # Density Analysis files
        and not filename.endswith(".tif")
        and not filename.endswith(".shp")
    ):
        bad_filename = filename
    else:
        bad_filename = None

    return bad_filename
