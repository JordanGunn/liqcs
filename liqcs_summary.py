import re
import csv
import datetime
from datetime import date as date1
import os
import pandas as pd

from typing import Union
from liqcs_const import Regex


def _no_string():
    return 'no'


def _yes_string():
    return 'yes'


def _max_gps_week_time():
    """
    GPS time will be greater than this value,
    which is one week into the beginning of GPS time.

    (GPS time = 0 at Jan 6, 1980,
    GPS time = 604800 at Jan 13, 1980)
    """
    return 604800


def _good_offset_value():
    return 'Round metre offset'


def _bad_offset_value():
    return 'Decimal values in offset'


def _offset_req_check(offset_value):
    """
    Check if a value has non-zero values
    after the decimal place.

    (i.e., the value is an integer, or
    if it is a float, all decimal place
    values are zeroes, representing
    round metre values)
    """
    if float(offset_value) % 1 == 0:
        offset_req = _good_offset_value()
    else:
        offset_req = _bad_offset_value()

    return offset_req


class LidarSummary:

    """
    This class generates a tabular lidar dataset summary
    from a directory of lasinfo text files.

    information summarized is as follows:

    > Filename
    > GUID
    > System ID
    > Density
    > Global Encoding
    > Point Data Format
    > Las major and minor version
    > Coordinate reference system metadata (wkt format)
    > GPS time (min/max)
    > Local date/time (converted from GPS time)
    > flightline (start/end)
    > X min/max
    > Y min/max
    > Bounding Box (in WKT polygon format)
    > Classes
    > Flags

    Written by: Brett Edwards
    """

    # Requirements for the lidar file to pass tests and be a 'good' file
    global_encoding_req = 17
    version_req = 1.4
    contract_number_req = "Correct Format"
    pt_format_req = 6
    cmpd_proj_req = _yes_string()
    gpstime_req = _max_gps_week_time()
    classes = ['1;2;7']
    scale_factor_req = 0.01
    offset_req = _good_offset_value()

    def __init__(self, text_file):
        # Default status is that the lidar file is a good dog (meets requirements)
        self.good_file = True

        with open(text_file, 'r', errors='ignore') as f:
            # Open the lasinfo file
            self.info = f.read()

        # Store the las/laz filename
        self.file = re.split(R"\.|\\", text_file)[-2]

        # Create a dictionary to store all of the lasinfo files
        # that are being searched for in this class
        self.info_dict = {}

        # Run the read_info method,
        # storing all of the info parameters
        # on instantiation of the class in the info_dict
        self.read_info()

    def read_info(self):
        self.filename()
        self.global_encoding()
        self.guid()
        self.contract_number()
        self.system_id()
        self.version()
        self.point_format()
        self.last_density()
        self.first_density()
        self.projection()
        gps_time = self.gps_time()
        self.datetime(gps_time)
        self.classes_()
        self.flightlines()
        self.flags()
        self.vlrs()
        self.total_points()
        self.xyz_minmax()
        self.xyz_scale()
        self.xyz_offset()
        self.bbox()
        self.check_file()

    def check_file(self):

        """
        Validate file based on LidarSummary attributes.

        @note Sets self.good_file to False if file is invalid.
        """

        if (
            self.info_dict['Global_Encoding'] != str(LidarSummary.global_encoding_req)
            or self.info_dict['Version'] != str(LidarSummary.version_req)
            or self.info_dict['Contract_Number_Format'] != str(LidarSummary.contract_number_req)
            or self.info_dict['Point_Data_Format'] != str(LidarSummary.pt_format_req)
            or self.info_dict['Compound_Projection'] != LidarSummary.cmpd_proj_req
            or float(self.info_dict['GPS_Start']) <= LidarSummary.gpstime_req
            or self.info_dict['x_scale'] != str(LidarSummary.scale_factor_req)
            or self.info_dict['y_scale'] != str(LidarSummary.scale_factor_req)
            or self.info_dict['z_scale'] != str(LidarSummary.scale_factor_req)
            or self.info_dict['x_offset'] == _bad_offset_value()
            or self.info_dict['y_offset'] == _bad_offset_value()
            or self.info_dict['z_offset'] == _bad_offset_value()
            # TODO classes requirement
        ):
            self.good_file = False

    def guid(self) -> Union[str, None]:

        """
        Get GUID Summary.

        @return:
        """

        guid = re.search(
            (
                R'(project ID GUID data 1-4:)' + Regex.GUID
            ),
            self.info
        )
        if guid:
            hex_data = str(guid[2])
            clean_hex = hex_data.replace('-', '')
            contract_number = (bytes.fromhex(clean_hex).decode('utf-8'))
            self.info_dict['Contract Number From GUID'] = contract_number
            return contract_number

    def contract_number(self):

        """
        Get the contract info summary.
        """

        guid = re.search(
            (
                R'(project ID GUID data 1-4:)' + Regex.GUID
            ),
            self.info
        )
        if guid:
            hex = str(guid[2])
            clean_hex = hex.replace('-','')
            contract_number = (bytes.fromhex(clean_hex).decode('utf-8'))
            if re.search(Regex.CONTRACT_NUMBER, contract_number):
                self.info_dict['Contract_Number_Format'] = "Correct Format"
            else:
                self.info_dict['Contract_Number_Format'] = "Incorrect Format"

    def system_id(self) -> Union[re.Match, None]:

        """
        Add system ID to object dictionary if it exists.

        @return: re.Match object if found, else None.
        """

        sys_id = re.search(
            R'(system identifier:)\s+([^\n]+)',
            self.info
        )

        if sys_id:
            self.info_dict['SYSTEM_ID'] = sys_id[2]
            return sys_id

    def filename(self) -> str:

        """
        Add filename to object dictionary if it exists.

        @return: filename as string.
        """

        fname = re.search(R"report for '(.*.la[s|z])'", self.info)
        if fname:
            basename = re.split(R'\\', fname[1])
            self.info_dict['Filename'] = basename[-1]
            return fname[1]
        else:
            self.info_dict['File'] = self.file
            return self.file

    def global_encoding(self) -> Union[str, None]:

        """
        Add global encoding to object dictionary if it exists.

        @return: filename as string.
        """

        glob_enco = re.search(
            R'(global_encoding:)\s+(\d+)',
            self.info
        )  # regex to locate global encoding value in lasinfo file

        if glob_enco:
            self.info_dict['Global_Encoding'] = glob_enco[2]
            return glob_enco[2]

    def flightlines(self) -> Union[tuple, None]:

        """
        Add flight line numbers (point source ids) to dict if they exist.

        @return flightline numbers as Tuple, else None
        """

        fl_nums = re.search(R'point_source_ID\s+(\d+)\s+(\d+)', self.info)

        if fl_nums:
            self.info_dict['Flightline_Start'] = fl_nums[1]
            self.info_dict['Flightline_End'] = fl_nums[2]
            return fl_nums[1], fl_nums[2]

    def version(self) -> Union[re.Match, None]:

        """
        Add version to dictionary if it exists.

        @return: LAS version number, or None.
        """

        version = re.search(
            R'(major.minor:)\s+(\d\.\d)',
            self.info
        )  # regex

        if version:
            self.info_dict['Version'] = version[2]
            return version[2]

    def point_format(self) -> Union[re.Match, None]:
        """
        Add point data format to dictionary if it exists.

        @return: Point data format, or None.
        """
        pt_frmt = re.search(
            R'(point data format:)\s+(\d+)',
            self.info
        )  # regex

        if pt_frmt:
            self.info_dict['Point_Data_Format'] = pt_frmt[2]
            return pt_frmt[2]

    def last_density(self) -> Union[re.Match, None]:
        """
         Add last return density to dictionary if it exists.

         @return: Last return density, or None.
         """
        dens = re.search(
            R'(point density: all returns \d+.\d\d last only)\s+(\d+.\d\d)',
            self.info
        )

        if dens:
            self.info_dict['Last_Density'] = dens[2]
            return dens[2]

    def first_density(self) -> Union[re.Match, None]:
        """
         Add first return density to dictionary if it exists.

         @return: First return density, or None.
         """
        dens = re.search(R'(point density: all returns)\s+(\d+.\d\d)', self.info)
        if dens:
            self.info_dict['First_Density'] = dens[2]
            return dens[2]

    def projection(self) -> Union[re.Match, None]:
        """
         Add CRS info to dictionary if it exists.

         @return: CRS info, or None.
         """
        # Search for compound WKT
        wkt_compound = re.search(
            R'(COMPD_CS\[\")([^\"]*)',
            self.info
        )  # regex to search for compound projection
        if wkt_compound:
            self.info_dict['Projection'] = wkt_compound[2]
            self.info_dict['Compound_Projection'] = _yes_string()
            return wkt_compound[2]

        # If compound not found, we'll look for the horizontal wkt projection
        wkt_proj = re.search(
            R'(PROJCS\[\")([^\"]*)',
            self.info
        )
        if wkt_proj:
            self.info_dict['Projection'] = wkt_proj[2]
            self.info_dict['Compound_Projection'] = _no_string()
            return wkt_proj[2]

        # If the wkt projection isn't found, say so
        self.info_dict['Projection'] = 'wkt missing'
        self.info_dict['Compound_Projection'] = _no_string()

    def gps_time(self) -> Union[tuple, None]:
        """
         Add GPS time to dictionary if it exists.

         @return: GPS time, or None.
         """
        gps = re.search(
            R'gps_time\s([-]?\d+\.\d+)\s(\d+\.\d+)',
            self.info
        )  # regex
        if gps:
            self.info_dict['GPS_Start'] = gps[1]
            self.info_dict['GPS_End'] = gps[2]
            return float(gps[1]), float(gps[2])
        else:
            self.info_dict['GPS_Start'] = 0
            self.info_dict['GPS_End'] = 0

    def time_report(self, gps_time, info_dict_key):
        """
        Convert gps times to readable date and time if possible.
        If not possible, tell us why.
        """
        try:
            if gps_time > _max_gps_week_time():
                # Convert gps time to a UTC date string
                # if it is greater than the maximum gps week time,
                # (meaning it is adjusted standard time)
                self.info_dict[info_dict_key] = convert_gps_time(gps_time)
            elif gps_time > 0:
                self.info_dict[info_dict_key] = 'GPS Week time'
            else:
                self.info_dict[info_dict_key] = 'No GPS time'

        except Exception:
            self.info_dict[info_dict_key] = 'Error converting GPS time'

    def datetime(self, adjusted_gps_time):
        """
        Convert gps times to readable date and time if possible.
        If not possible, tell us why.
        """
        gps_start, gps_end = adjusted_gps_time

        adjusted_gps_time_dict = {
            'Date_Time_Start': gps_start,
            'Date_Time_End': gps_end
        }

        for info_dict_time_key in adjusted_gps_time_dict:
            self.time_report(
                adjusted_gps_time_dict.get(info_dict_time_key),
                info_dict_time_key
            )

    def classes_(self) -> Union[str, None]:
        """
        Find the classes from the lasinfo file.
        """
        class_list = []
        class_rgx = re.findall(R"\d+\s+.*\s\((\d+)\)[^']", self.info)  # regex

        for clas in class_rgx:
            class_list.append(clas)

        classes = ';'.join(class_list)
        self.info_dict['Classes'] = classes
        return classes

    def xyz_minmax(self):
        """
        find x y z min max of lidar file from the lasinfo
        """
        min_xyz = re.search(
            R'min x y z:\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)',
            self.info
        )  # regex
        if min_xyz:
            self.info_dict['x_min'] = min_xyz[1]
            self.info_dict['y_min'] = min_xyz[2]
            self.info_dict['z_min'] = min_xyz[3]

        max_xyz = re.search(
            R'max x y z:\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)',
            self.info
        )  # regex
        if max_xyz:
            self.info_dict['x_max'] = max_xyz[1]
            self.info_dict['y_max'] = max_xyz[2]
            self.info_dict['z_max'] = max_xyz[3]

        return min_xyz[1], min_xyz[2], min_xyz[3], max_xyz[1], max_xyz[2], max_xyz[3]

    def xyz_scale(self) -> tuple:
        """
        Find x y z scale factor of lidar file.
        """
        scale_xyz = re.search(
            R'scale factor x y z:\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)',
            self.info
        )

        # TODO NJ: what if this and similar if statements fail?
        # TODO NJ: should we remove these if statements, or make another 
        # TODO NJ: value to return? Do we need to return a value at all?
        if scale_xyz:
            self.info_dict['x_scale'] = scale_xyz[1]
            self.info_dict['y_scale'] = scale_xyz[2]
            self.info_dict['z_scale'] = scale_xyz[3]

        return scale_xyz[1], scale_xyz[2], scale_xyz[3]

    def xyz_offset(self):
        """
        Find x y z offset of lidar file.
        """
        offset_xyz = re.search(
            R'offset x y z:\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)',
            self.info
        )
        if offset_xyz:
            offset_xyz_dict = {
                'x_offset': offset_xyz[1],
                'y_offset': offset_xyz[2],
                'z_offset': offset_xyz[3]
            }

            for offset in offset_xyz_dict:
                self.info_dict[offset] = _offset_req_check(
                    offset_xyz_dict.get(offset)
                )

    def flags(self) -> str:
        """
        Find if any points have flags (overlap, synthetic, etc),
        and how many points have those flags
        """
        flag_list = []

        flag_rgx = re.findall(R'flagged as\s(.*:.*)', self.info)
        for flag in flag_rgx:
            flag_list.append(flag)

        flags = ';'.join(flag_list)

        self.info_dict['Flags'] = flags
        return flags

    def vlrs(self) -> Union[re.Match, None]:
        """
        Find how many VLRs there are in the file
        """
        vlrs = re.search(R'number var. length records: (\d+)', self.info)
        
        if vlrs is not None:
            self.info_dict['#VLRs'] = vlrs[1]
            return vlrs[1]

    def total_points(self) -> Union[re.Match, None]:
        """
        Find how many total points there are
        (it's stored in a different location
        in the header for las 1.2 vs 1.4)
        """
        try:
            if self.info_dict['Version'] == '1.4':
                total_pts = re.search(
                    R'extended number of point records:\s(\d+)',
                    self.info
                )
                self.info_dict['Total_Points'] = total_pts[1]
                return total_pts[1]
            elif self.info_dict['Version'] == '1.2':
                total_pts = re.search(
                    R'number of point records:\s+(\d+)',
                    self.info
                )
                self.info_dict['Total_Points'] = total_pts[1]
                return total_pts[1]
        except KeyError:
            self.info_dict['Version'] = "Failed to grab version"
            return

    def bbox(self) -> str:
        """
        Create a WKT bounding box for the lidar file
        """
        xmin, xmax, ymin, ymax = (
            self.info_dict['x_min'],
            self.info_dict['x_max'],
            self.info_dict['y_min'],
            self.info_dict['y_max']
        )
        bbox_poly = (
            f"POLYGON (({xmin} {ymax}, {xmax} {ymax}, {xmax} {ymin}, {xmin} {ymin}, {xmin} {ymax}))"
        )

        self.info_dict['wkt_bbox'] = bbox_poly
        return bbox_poly

    def output(self, output_path: str, write_errors: bool = False):
        """
        Write results to CSV file.

        @param output_path: Output directory.
        @param write_errors: Whether to write errors to file.
        @return:
        """
        date = _date_string()
        output_csv = os.path.join(output_path, f'lidar_summary_{date}.csv')
        error_csv = _error_csv_path(output_path)

        # If the file doesn't exist, create it and write the header
        if not os.path.exists(output_csv):
            with open(output_csv, 'a', newline='') as csvfile:
                fieldnames = self.info_dict.keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, escapechar="\\")
                writer.writeheader()  # write the header

        with open(output_csv, 'a', newline='') as csvfile:
            fieldnames = self.info_dict.keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, escapechar="\\")
            writer.writerow(self.info_dict)  # write the entry into the summary file

        # If write_errors=True, write out the errors csv
        if write_errors:
            if not self.good_file:
                if not os.path.exists(error_csv):
                    with open(error_csv, 'a', newline='') as csvfile:
                        fieldnames = self.info_dict.keys()
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, escapechar="\\")
                        writer.writeheader()

                with open(error_csv, 'a', newline='') as csvfile:
                    fieldnames = self.info_dict.keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, escapechar="\\")
                    writer.writerow(self.info_dict)

        return output_csv


def find_format_errors(lidar_summary: str, output_path: str, save_output: bool = True) -> pd.DataFrame:
    """
    Input is a lidar summary csv file from the LidarSummary
    class output and an output path.

    Output is a csv showing all files with errors,
    and a text file summarizing those errors
    into their specific causes.

    @todo Function should accept LidarSummary object as arg, rather than reading file.
    @todo Rather than having a save_output param, only write file 'if output_path is not None'

    @param lidar_summary: Path to lidar summary file.
    @param output_path: Output directory to write results to.
    @param save_output: Controls whether to write CSV file.
    @return: pd.Dataframe of LidarSummary errors.
    """
    date = _date_string()  # set date to today for later use

    # Read the input summary csv into a dataframe
    df = pd.read_csv(lidar_summary)

    # Find files where the version is not 1.4
    version = df['Version'] != LidarSummary.version_req
    # Count how many aren't version 1.4
    ver_issues = version.sum()

    # Find files where Contract Number is incorrect
    contract_number_format = df['Contract_Number_Format'] != LidarSummary.contract_number_req
    contract_number_issues = contract_number_format.sum()
    
    # Find files where the verison is not 17
    global_encoding = df['Global_Encoding'] != LidarSummary.global_encoding_req
    global_encoding_issues = global_encoding.sum()

    # Find files where x scale factor is not 0.01
    x_scale = df['x_scale'] != LidarSummary.scale_factor_req
    x_scale_issues = x_scale.sum()

    # Find files where y scale factor is not 0.01
    y_scale = df['y_scale'] != LidarSummary.scale_factor_req
    y_scale_issues = y_scale.sum()

    # Find files where z scale factor is not 0.01
    z_scale = df['z_scale'] != LidarSummary.scale_factor_req
    z_scale_issues = z_scale.sum()

    # Find files where x offset has non-zero decimal place values
    x_offset = df['x_offset'] != LidarSummary.offset_req
    x_offset_issues = x_offset.sum()

    # Find files where y offset has non-zero decimal place values
    y_offset = df['y_offset'] != LidarSummary.offset_req
    y_offset_issues = y_offset.sum()

    # Find files where y offset has non-zero decimal place values
    z_offset = df['z_offset'] != LidarSummary.offset_req
    z_offset_issues = z_offset.sum()

    # Find files that don't have a compound projection
    projection = df['Compound_Projection'] != LidarSummary.cmpd_proj_req
    prj_issues = projection.sum()

    # classes = ~df['Classes'].isin(['1;2;7', '1;2'])   # TODO implement a check on classes?
    # class_issues = classes.sum()

    # Find files that are not adjusted standard GPS time
    gps = df['GPS_Start'].astype(float) <= _max_gps_week_time()
    gps_issues = gps.sum()

    # Find files without flight line numbers
    flightline = df['Flightline_Start'] == 0
    fl_issues = flightline.sum()

    flags = ~df['Flags'].isnull()   # Find files with points flagged as anything
    flag_issues = flags.sum()

    # Gather SYSTEM_ID and create set to remove duplicates
    system_id = df['SYSTEM_ID'].tolist()
    system_ids = set(system_id)

    # Create filter to find the files that likely have adjusted standard GPS time
    date_filter = df['GPS_Start'] > _max_gps_week_time()

    # Pull the first 4 digits from these filtered dates
    # (the first 4 digits being the year)
    year_list_start = df[date_filter].Date_Time_Start.str[:4].tolist()
    year_list_end = (df[date_filter].Date_Time_End.str[:4].tolist())
    year_list = year_list_start + year_list_end
    years = set(year_list)  # Turn these years into a set to remove duplicates

    # Find all years that are beyond current year
    year_issues = 0
    year_list = list(years)
    current_year = str(date1.today().year)
    for year in year_list:
        if year > current_year:
            year_issues += 1

    class_list = df['Classes'].tolist()
    classes = set()

    for clas in class_list:
        if isinstance(clas, int):
            classes.add(clas)
        else:
            classes.update(map(int, clas.split(';')))

    # Put all of these files where issues were found
    # into a single dataframe.
    # '|' is 'or' in pandas
    df_errors = df[
        version | contract_number_format | global_encoding | x_scale | y_scale | z_scale | x_offset | y_offset | z_offset | projection | gps | flightline | flags
    ]

    # Print a summary of the errors found to a text file
    format_error_summary_path = os.path.join(
        output_path,
        f'format_error_summary_{date}.txt'
    )
    with open(format_error_summary_path, mode='w') as format_error_summary_txt:
        error_list = []
        issue_dict = {
            "version issues": ver_issues,
            "global encoding issues": global_encoding_issues,
            "GUID issues": contract_number_issues,
            "incorrect x scale factor": x_scale_issues,
            "incorrect y scale factor": y_scale_issues,
            "incorrect z scale factor": z_scale_issues,
            "incorrect x offset": x_offset_issues,
            "incorrect y offset": y_offset_issues,
            "incorrect z offset": z_offset_issues,
            "projection issues": prj_issues,
            "GPS time issues": gps_issues,
            "flightline issues": fl_issues,
            "points flagged": flag_issues
        }
        for item in issue_dict:
            error_list.append(
                f"{issue_dict.get(item)} out of {len(df.index)} with {item}"
            )
        error_list.append(
            f"\nYears from GPS times: {str([x for x in years])[1:-1]}"
            f"\nYears from GPS times beyond current year: {year_issues}"
            f"\nSystem IDs: {str([x[1:-1] for x in system_ids])[1:-1]}"
        )
        error_list.append(
            f"Classes included: {str([x for x in classes])[1:-1]}"
        )
        error_list.append(
            f"\n\nTotal number of files with issues: {len(df_errors.index)}"
        )

        # Print the list of errors to the out text file
        for line in error_list:
            print(
                line,
                file=format_error_summary_txt
            )

    # If save_output=True, write the summary of all files with errors to a csv
    if save_output:
        df_errors.to_csv(
            _error_csv_path(output_path),
            index=False
        )

    return df_errors


def count_leaps(gps_time: Union[int, float]) -> int:
    """
    Count number of leap seconds that have passed.

    Leap seconds are added when necessary on
    June 30th, or December 31st.

    Official announcements of leap seconds are posted here:
    https://datacenter.iers.org/data/latestVersion/16_BULLETIN_C16.txt,
    but more user-friendly announcements exist with a simple Google search.
        - Last checked July, 2022 (there will be no leap second
        added at the end of December 2022, so the next possible leap second
        is June 30, 2023.)

    If a new leap second is added, convert it to GPS time here:
    https://www.andrews.edu/~tzs/timeconv/timeconvert.php,
    and add the value to the leaps tuple.

    e.g., enter Dec 31, 2016, 23:59:60 (UTC) to find gps time 1167264017.
    """

    # A tuple of the gps times where leap seconds were added
    leaps = (
        46828800,  # Jun 30, 1981 - first leap second since start of GPS time
        78364801,  # Jun 30, 1982
        109900802,  # Jun 30, 1983
        173059203,  # Jun 30, 1985
        252028804,  # Dec 31, 1987
        315187205,  # Dec 31, 1989
        346723206,  # Dec 31, 1990
        393984007,  # Jun 30, 1992
        425520008,  # Jun 30, 1993
        457056009,  # Jun 30, 1994
        504489610,  # Dec 31, 1995
        551750411,  # Jun 30, 1997
        599184012,  # Dec 31, 1998
        820108813,  # Dec 31, 2005
        914803214,  # Dec 31, 2008
        1025136015,  # Jun 30, 2012
        1119744016,  # Jun 30, 2015
        1167264017  # Dec 31, 2016
    )

    n_leaps = 0
    for leap in leaps:
        if gps_time >= leap:
            n_leaps += 1

    return n_leaps


def convert_gps_time(time_value: Union[int, float]) -> str:

    """
    Convert GPS time to UNIX time.

    @param time_value: GPS time.
    @return:
    """

    # Number of seconds between the start of unix time (Jan 1, 1970)
    # and gps time (Jan 6, 1980)
    offset = 315964800

    time = float(time_value)
    time += 1e9  # unadjusted gps time
    unixtime = time + offset - count_leaps(time)

    datetimestr = datetime.datetime.fromtimestamp(unixtime).strftime(
        '%Y-%m-%d %H:%M:%S'
    )

    return datetimestr


def _error_csv_path(output_path):
    date = _date_string()
    error_csv = os.path.join(
        output_path,
        f'lidar_summary_errors_{date}.csv'
    )
    return error_csv


def _date_string():
    date_string = datetime.datetime.today().strftime('%Y-%m-%d')
    return date_string


def main():
    import glob
    from tkinter import filedialog, Tk
    Tk().withdraw()

    # prompt for indir and outdir
    indir = filedialog.askdirectory(title="Select input lasinfo directory")
    outdir = filedialog.askdirectory(title="Select output directory")

    files = glob.glob(os.path.join(indir, '*.txt'))

    summary_csv = None

    for file in files:
        try:
            test = LidarSummary(file)
            # the output method writes all files to a csv, and returns the path for the output
            summary_csv = test.output(outdir, write_errors=False)
        except Exception as e:
            print(e)
            with open(os.path.join(outdir, 'problem_files.txt'), 'a') as probs:
                print(file, file=probs)

    # Run the find_format_errors function on the result of the LidarSummary output
    if bool(summary_csv):
        find_format_errors(summary_csv, outdir)

    print('Done!')


if __name__ == '__main__':
    main()
