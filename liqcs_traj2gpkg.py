import os
import pandas as pd
from math import pi
from shapely.geometry import Point
from geopandas import GeoDataFrame
import numpy as np
import sys
import liqcs_config
import tkinter as tk
from tkinter import Tk, filedialog, LEFT, ttk
from glob import glob
import subprocess

from liqcs_const import EpsgCode


###########################################################################
# Get a list of the SBET record types
# This is the definition of a SBET record
###########################################################################
def sbet_record_types() -> list:

    """
    @return: SBET record types as a list of tuples.
    """

    return [
        ("time", np.float64),
        ("lat", np.float64),
        ("lon", np.float64),
        ("alt", np.float64),
        ("ewspeed", np.float64),
        ("nsspeed", np.float64),
        ("vertspeed", np.float64),
        ("roll", np.float64),
        ("pitch", np.float64),
        ("heading", np.float64),
        ("wander", np.float64),
        ("xacc", np.float64),
        ("yacc", np.float64),
        ("zacc", np.float64),
        ("xangrate", np.float64),
        ("yangrate", np.float64),
        ("zangrate", np.float64)
    ]


def readSbet(filename: str) -> np.ndarray:

    """
    Read an SBET file into a numpy array.

    @param filename: String of filename to read into a numpy array
    @return: np.ndarray of SBET data
    """

    return np.fromfile(filename, dtype=np.dtype(sbet_record_types()))


def sbet_to_geopandas(sbet_array: np.ndarray, epsg_code: int, nth_point: int = 100) -> GeoDataFrame:

    """
    Convert SBET np.ndarray to Geodataframe.

    @param sbet_array: np.ndarray of SBET data.
    @param epsg_code: EPSG code for output CRS.
    @param nth_point: Sample every Nth point
    @return: GeoDataFrame
    """

    # thin array to every 100th entry
    sbet = sbet_array[::nth_point]

    # put array into a pandas dataframe
    df = pd.DataFrame(
        {
            "time": sbet["time"],
            "lat": sbet["lat"],
            "long": sbet["lon"],
            "altitude": sbet["alt"],
            "roll": sbet["roll"],
            "pitch": sbet["pitch"],
            "heading": sbet["heading"],
            "x_velocity": sbet["ewspeed"],
            "y_velocity": sbet["nsspeed"],
            "z_velocity": sbet["vertspeed"],
            "wander": sbet["wander"],
            "x_accel": sbet["xacc"],
            "y_accel": sbet["yacc"],
            "z_accel": sbet["zacc"],
            "x_ang_rate": sbet["xangrate"],
            "y_ang_rate": sbet["yangrate"],
            "z_ang_rate": sbet["zangrate"],
        }
    )

    # convert radians to degrees
    df["lat"] = df["lat"] * (180 / pi)
    df["long"] = df["long"] * (180 / pi)

    df["roll"] = df["roll"] * (180 / pi)
    df["pitch"] = df["pitch"] * (180 / pi)
    df["heading"] = df["heading"] * (180 / pi)
    # df['wander'] = df['wander'] * (180/pi)

    # convert into geopandas dataframe
    geometry = [Point(xy) for xy in zip(df.long, df.lat)]
    gdf = GeoDataFrame(df, geometry=geometry)

    # If the desired output is WGS84, geopandas has a problem assigning
    # EPSG as a coordinate system. The problem could be solved by changing
    # the geopandas/pyproj installation parameters, but as a workaround,
    # this "if" clause lets us keep 4326 as an output option without
    # monkeying around with a fussy geopandas/pyproj  installation.
    if epsg_code != EpsgCode.WGS_84:
        # Set coordinate reference system of geopandas dataframe.
        # SBETS are not projected; they only have lats and longs,
        # derived from GPS data, which uses WGS84.
        # Therefore, the input data uses WGS84 (EPSG:4326).
        gdf = gdf.set_crs(epsg=EpsgCode.WGS_84)

        # Re-project to desired coordinate reference system
        gdf = gdf.to_crs(epsg=epsg_code)

    return gdf


def traj_to_gpkg(sbet_files: list, out_dir: str, nth_point: int, epsg_code: int):

    """
    Write Trajectory data vector geometry to gpkg file.

    @param sbet_files: List of SBET files.
    @param out_dir: Desired output directory.
    @param nth_point: Sample every Nth point
    @param epsg_code: Desired output EPSG code.
    """

    for idx, file in enumerate(sbet_files, start=1):
        basename = os.path.splitext(os.path.basename(file))[0]   # get basename of file for output 

        sbet = readSbet(file)   # read SBET file
        gdf = sbet_to_geopandas(
            sbet,
            epsg_code,
            nth_point
        )   # translate SBET numpy array into geopandas df

        outfile = os.path.join(
            out_dir,
            f"{basename}_{__epsg_dict_with_WSG84()[epsg_code][1]}.gpkg"
        )

        print(
            f"\r Writing geopackage {idx} of {len(sbet_files)} "
            f"using every {nth_point}th record of SBET "
            f"to CRS: {__epsg_dict_with_WSG84()[epsg_code][0]}",
            flush=True
        )

        # use geopandas built-in method to write gdf to a geopackage
        gdf.to_file(outfile, driver='GPKG')


def ___run_from_liqcs(infile_glob, outdir, epsg_code):
    nth_point = 100
    sbet_files = []
    for file in infile_glob:
        if os.path.splitext(file)[1].lower() == '.out':
            sbet_files.append(file)

    traj_to_gpkg(sbet_files, outdir, nth_point, epsg_code)


def __print_invalid_crs_choice_message():
    print(
        f"{liqcs_config.AnsiColors.magenta}\n\tInvalid entry!{liqcs_config.AnsiColors.reset}"
    )


def __crs_option_string_entry(index, entry):
    return (
        f"\n\t{index}. {entry}"
    )


def __epsg_dict_with_WSG84():
    epsg_dict = EpsgCode.EPSG_DICT_CODE_TO_TUPLE_WKT_PROJ
    epsg_dict[4326] = (
        "EPSG 4326: WGS84 (no projection assigned to GPKG)",
        "WGS84_no_projection"
    )
    return epsg_dict


def __get_crs_from_user_input():
    """
    Get the CRS from user input at the terminal.

    Returns an EPSG code.
    """
    epsg_dict = __epsg_dict_with_WSG84()
    crs_options_list = list(element[0] for element in epsg_dict.values())

    num_crs_options = len(crs_options_list)
    crs_options_str = ""
    for i, crs_option in enumerate(crs_options_list):
        crs_options_str += __crs_option_string_entry(i + 1, crs_option)

    num_crs_options = len(crs_options_list)

    output_crs = None
    while output_crs not in range(1, num_crs_options + 1):
        print(
            f"{liqcs_config.dashline()}Choose a "
            f"{liqcs_config.AnsiColors.yellow}coordinate reference system (CRS) "
            f"from 1-{str(num_crs_options)}{liqcs_config.AnsiColors.reset} to set the CRS"
            "\nof the output geopackage, "
            f"enter {liqcs_config.AnsiColors.cyan}I{liqcs_config.AnsiColors.reset} for more info, "
            f"or enter {liqcs_config.AnsiColors.magenta}Q{liqcs_config.AnsiColors.reset} to quit: "
        )
        output_crs = input(
            f"{crs_options_str}\n"
        )

        try:
            output_crs = int(output_crs)
            if output_crs not in range(1, num_crs_options + 1):
                __print_invalid_crs_choice_message()

        except Exception:
            if output_crs.capitalize() == "I":
                print(
                    f"{liqcs_config.dashline()}"
                    f"{liqcs_config.AnsiColors.cyan}"
                    "More Info:"
                    "\n\n\t- Smoothed Best Estimate Trajectory (SBET) .out files do "
                    "not have a projection; their locations are lats and longs, "
                    "referenced to WGS84, the coordinate system used by GPS."
                    "\n\n\t- Geopackages can have any CRS, including projections."
                    "\n\n\t- This script allows you to specify the CRS of "
                    "the output geopackage. The geopackage will "
                    "have the CRS you specify here."
                    "\n\n\t- If you do not wish to project the output geopackage to "
                    "a specific projection, choose option "
                    f"{liqcs_config.AnsiColors.yellow}{i + 1}{liqcs_config.AnsiColors.cyan}, "
                    "which is WGS84. WGS84 is a good choice "
                    "if your geopackage will be used in maps with different projections."
                    f"{liqcs_config.AnsiColors.reset}"
                )
                output_crs = None

            elif output_crs.capitalize() == "Q":
                sys.exit()

            else:
                __print_invalid_crs_choice_message()

    # Set the output epsg code based on user input (output_crs - 1)
    epsg_code = list(epsg_dict)[output_crs - 1]

    return epsg_code


def __ask_open_outdir(outdir):
    """
    Ask at the terminal if you'd like to
    open the output directory.
    """
    open_outdir = None
    while open_outdir not in ("Y", "N"):
        open_outdir = input(
            f"\n{liqcs_config.dashline()}Open the output directory? (y/n) "
        )
        try:
            open_outdir = open_outdir.capitalize()
        except Exception:
            pass
        if open_outdir == "Y":
            import webbrowser
            webbrowser.open(outdir)


def __print_exit_message():
    print(
        f"{liqcs_config.rainbow_string(liqcs_config.dashline())}"
        "Have a nice day!"
    )


# ------------------------------------------------------------------------------
# Run this script independently of LiQCS
# ------------------------------------------------------------------------------
def __browse_to_input_directory(input_directory):
    input_directory.delete(0, tk.END)
    input_dir_temp = filedialog.askdirectory(title="Select SBET directory")
    input_directory.insert(0, input_dir_temp)


def __browse_to_output_directory(output_directory):
    output_directory.delete(0, tk.END)
    output_dir_temp = filedialog.askdirectory(title="Select output directory")
    output_directory.insert(0, output_dir_temp)


def __reset_sample_rate(sample_rate, default_sample_rate):
    sample_rate.delete(0, tk.END)
    sample_rate.insert(0, default_sample_rate)


def __run_traj_to_geopackage_from_gui(
    sample_rate,
    request_integer_sample_rate,
    input_directory,
    request_input_directory,
    output_directory,
    request_output_directory,
    output_crs_dropdown,
    epsg_dict,
    request_crs,
    open_output_location,
    close_app_when_done,
    window
):
    try:
        nth_point = int(sample_rate.get())
        request_integer_sample_rate.config(
            text=""
        )
        sample_rate_valid = True
    except ValueError:
        request_integer_sample_rate.config(
            text="Enter an integer sample rate"
        )
        sample_rate_valid = False
    if os.path.isdir(input_directory.get().strip()):
        request_input_directory.config(
            text=""
        )
        input_directory_valid = True
    else:
        request_input_directory.config(
            text="Provide directory containing SBET file(s)"
        )
        input_directory_valid = False
    if os.path.isdir(output_directory.get().strip()):
        request_output_directory.config(
            text=""
        )
        output_directory_valid = True
    else:
        request_output_directory.config(
            text="Provide a directory to save the output geopackage(s)"
        )
        output_directory_valid = False
    try:
        # Initialize crs_valid
        crs_valid = None

        # Get the entry from the CRS dropdown/entry box
        crs_as_entered = output_crs_dropdown.get()

        print(crs_as_entered)
        # Check if the entry was in the dropdown, if so, return the 
        # EPSG code (integer value) from the dictionary (epsg_dict)
        for crs in epsg_dict:
            if crs_as_entered == epsg_dict.get(crs)[0]:
                output_crs_epsg = crs
                crs_valid = True

        # If the entry wasn't in the dropdown, check if the entry
        # is a valid EPSG code (integer between 1024-32767)
        if not crs_valid:
            output_crs_epsg = int(output_crs_dropdown.get())
            if EpsgCode.MIN <= output_crs_epsg <= EpsgCode.MAX:
                request_crs.config(text="")
                crs_valid = True
            else:
                request_crs.config(text="Please enter a valid EPSG code")
                crs_valid = False
    except ValueError:
        request_crs.config(
            text="Please enter a valid EPSG code, or select a coordinate system from the dropdown menu"
        )
        crs_valid = False

    if (
        sample_rate_valid
        and input_directory_valid
        and output_directory_valid
        and crs_valid
    ):
        indir = input_directory.get().strip()
        outdir = output_directory.get().strip()

        sbet_files = glob(os.path.join(indir, "**\*.out"), recursive=True)

        print(
            f"{liqcs_config.dashline()}"
            f"Writing every {nth_point}th record from SBET files to geopackages\n"
        )

        traj_to_gpkg(sbet_files, outdir, nth_point, output_crs_epsg)

        # Open the output directory in File Explorer window
        if (open_output_location.get()):
            subprocess.Popen(f"explorer {outdir.replace('/', os.sep)}")

        # Close the app
        if (close_app_when_done.get()):
            window.destroy()


def __trajectory_to_geopackage_gui():
    """
    Run this script independently of LiQCS using
    using a GUI.
    """
    # --------------------------------------------------------------------------
    # Some style settings
    directory_entry_field_width = 52
    bg_colour = "#D2E9E4"
    button_colour = "#DFEFEC"
    create_geopackage_button_colour = "#377165"
    input_error_text_colour = "red"
    default_indir = None
    default_outdir = None
    default_sample_rate = "100"

    epsg_dict = __epsg_dict_with_WSG84()

    # Assign the values of the dictionary to a list
    epsg_list = []
    for crs in epsg_dict.values():
        epsg_list.append(crs[0])

    # --------------------------------------------------------------------------
    # Initialize app window
    window = tk.Tk()
    window.title("Trajectory Converter: SBET to GeoPackage")
    #window.iconbitmap("plane_icon.ico")
    window.configure(bg=bg_colour)

    # --------------------------------------------------------------------------
    # Size and place app window
    window_width = 520
    window_height = 480
    window.resizable(False, False)
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    horiz_centre = int((screen_width - window_width) / 2)
    vert_centre = int((screen_height - window_height) / 2)
    window.geometry(
        f"{window_width}x{window_height}+{horiz_centre}+{vert_centre}"
    )
    window.attributes("-topmost", True)  # Keep window on top of other windows

    # --------------------------------------------------------------------------
    # Initialize window features:

    # Input directory
    input_directory_label = tk.Label(
        window,
        bg=bg_colour,
        text="Directory containing smoothed best estimate trajectory (SBET) file(s):"
    )
    input_directory_var = tk.StringVar(value=default_indir)
    input_directory = tk.Entry(
        window,
        textvariable=input_directory_var,
        width=directory_entry_field_width
    )
    browse_input_directory_button = tk.Button(
        window,
        text="Browse to SBET directory",
        bg=button_colour,
        command=lambda: __browse_to_input_directory(input_directory)
    )
    request_input_directory = tk.Label(
        window,
        fg=input_error_text_colour,
        bg=bg_colour, text=""
    )

    # Output directory
    output_directory_label = tk.Label(
        window,
        bg=bg_colour,
        text="Directory to create geopackage(s) in:"
    )
    output_directory_var = tk.StringVar(value=default_outdir)
    output_directory = tk.Entry(
        window,
        textvariable=output_directory_var,
        width=directory_entry_field_width
    )
    browse_output_directory_button = tk.Button(
        window,
        text="Browse to output directory",
        bg=button_colour,
        command=lambda: __browse_to_output_directory(output_directory)
    )
    request_output_directory = tk.Label(
        window,
        bg=bg_colour,
        fg=input_error_text_colour,
        text=""
    )

    # Sample rate
    sample_rate_label_prefix = tk.Label(
        window,
        bg=bg_colour,
        text="Create geopackage sampling every"
    )
    sample_rate_label_suffix = tk.Label(
        window,
        bg=bg_colour,
        text="points from SBET."
    )
    sample_rate = tk.Entry(
        window,
        width=5,
        justify="right"
    )
    __reset_sample_rate(sample_rate, default_sample_rate)
    sample_rate_reset_button = tk.Button(
        text="Reset sample rate to default",
        bg=button_colour,
        command=lambda: __reset_sample_rate(sample_rate, default_sample_rate)
    )
    request_integer_sample_rate = tk.Label(
        window,
        text="",
        bg=bg_colour,
        fg=input_error_text_colour
    )

    # Coordinate reference system (CRS)
    output_crs_label = tk.Label(
        window,
        bg=bg_colour,
        text="Choose a coordinate reference system or enter an EPSG code for the output geopackage:"
    )
    output_crs_string = tk.StringVar()
    output_crs_dropdown = ttk.Combobox(
        window,
        width=44,
        textvariable=output_crs_string,
        values=epsg_list
    )
    output_crs_dropdown.current()
    '''
    crs_info_button = tk.Button(
        window,
        text="More info",
        bg=button_colour,
        command=crs_info
    )
    '''
    request_crs = tk.Label(
        window,
        text="",
        bg=bg_colour,
        fg=input_error_text_colour,
        justify=LEFT,
    )

    # Open File Explorer to output location checkbox
    open_output_location = tk.BooleanVar(value=True)
    open_output_location_checkbox = tk.Checkbutton(
        window,
        text="Open output directory when geopackage creation complete",
        variable=open_output_location,
        bg=bg_colour
    )

    close_app_when_done = tk.BooleanVar(value=True)
    close_app_when_done_checkbox = tk.Checkbutton(
        window,
        text="Close this program when done",
        variable=close_app_when_done,
        bg=bg_colour
    )

    # Main execute button
    run_traj_to_geopackage_from_gui_button = tk.Button(
        window,
        text="Validate inputs and create geopackage",
        padx=30,
        pady=20,
        command=lambda: __run_traj_to_geopackage_from_gui(
            sample_rate,
            request_integer_sample_rate,
            input_directory,
            request_input_directory,
            output_directory,
            request_output_directory,
            output_crs_dropdown,
            epsg_dict,
            request_crs,
            open_output_location,
            close_app_when_done,
            window
        ),
        fg="white",
        bg=create_geopackage_button_colour,
    )

    # --------------------------------------------------------------------------
    # Place window features:

    # Input directory
    input_directory_label.grid(
        row=0,
        column=0,
        sticky="w",
        padx=(10, 0),
        pady=(10, 0)
    )
    input_directory.grid(
        row=1,
        column=0,
        padx=10,
        columnspan=4
    )
    browse_input_directory_button.grid(
        row=1,
        column=4,
        sticky="w"
    )
    request_input_directory.grid(
        row=2,
        column=0,
        sticky="w",
        padx=10,
        columnspan=4
    )

    # Output directory
    output_directory_label.grid(
        row=3,
        column=0,
        sticky="w",
        padx=(10, 0),
        pady=(10, 0)
    )
    output_directory.grid(
        row=4,
        column=0,
        padx=10,
        columnspan=4
    )
    browse_output_directory_button.grid(
        row=4,
        column=4,
        sticky="w"
    )
    request_output_directory.grid(
        row=5,
        column=0,
        sticky="w",
        padx=10,
        columnspan=4
    )

    # Sample rate
    sample_rate_label_prefix.grid(
        row=6,
        column=0,
        sticky="w",
        padx=(10, 0),
        pady=(20, 0)
    )
    sample_rate.grid(
        row=6,
        column=1,
        pady=(20, 0)
    )
    sample_rate_label_suffix.grid(
        row=6,
        column=2,
        sticky="w",
        pady=(20, 0),
        columnspan=2
    )
    sample_rate_reset_button.grid(
        row=6,
        column=4,
        sticky="w",
        pady=(20, 0)
    )
    request_integer_sample_rate.grid(
        row=7,
        column=0,
        sticky="w",
        padx=10,
        columnspan=4
    )

    # Coordinate reference system (CRS)
    output_crs_label.grid(
        row=8,
        column=0,
        sticky="w",
        padx=10,
        pady=(20, 0),
        columnspan=5
    )
    '''
    crs_info_button.grid(
        row=8,
        column=4,
        sticky='w',
        pady=(20,0)
    )
    '''
    output_crs_dropdown.grid(
        row=9,
        column=0,
        sticky="w",
        padx=10,
        columnspan=3
    )
    request_crs.grid(
        row=10,
        column=0,
        sticky="w",
        padx=10,
        columnspan=5
    )

    # Open File Explorer to output location checkbox
    open_output_location_checkbox.grid(
        row=11,
        column=0,
        sticky="w",
        padx=30,
        pady=2,
        columnspan=5
    )

    # Close app when done checkbox
    close_app_when_done_checkbox.grid(
        row=12,
        column=0,
        sticky="w",
        padx=30,
        pady=2,
        columnspan=5
    )

    # Main execute button
    run_traj_to_geopackage_from_gui_button.grid(
        row=13,
        column=0,
        pady=20,
        columnspan=5
    )

    # --------------------------------------------------------------------------
    # Run the GUI
    window.mainloop()


def cli():
    """
    Run this script independently of LiQCS using
    using the command line interface.
    """
    root = Tk()
    root.attributes("-topmost", True)
    root.withdraw()

    nth_point = 100

    print(liqcs_config.dashline())
    sbet_files = None

    while not sbet_files:
        select_sbet_directory_message = (
            "Select directory (or parent, grandparent, etc. directory) "
            "containing SBET file(s) from the pop-up window."
        )
        if True:  # this line to preserve indenting of halo option
            print(select_sbet_directory_message)  # this line instead of halo
        # with Halo(  # halo not cooperating with pyinstaller; commenting out...
        #    text=select_sbet_directory_message
        # ):
            indir = filedialog.askdirectory(
                title="Select directory (or parent, grandparent, etc.) "
                "containing SBET file(s)."
            )

        print(
            f"For the input directory, you selected:"
            f"{liqcs_config.AnsiColors.yellow}\n\t{indir}{liqcs_config.AnsiColors.reset}"
        )

        sbet_files = glob(os.path.join(indir, '**\*.out'), recursive=True)

        if sbet_files and indir:
            if len(sbet_files) == 1:
                is_are = "is"
                s_no_s = ""
            else:
                is_are = "are"
                s_no_s = "s"
            print(
                "\nGreat choice! "
                f"There {is_are} {len(sbet_files)} SBET file{s_no_s} in that directory."
            )
        elif sbet_files and not indir:
            print(
                f"{liqcs_config.AnsiColors.magenta}"
                f"\nNo input directory selected! Please try again."
                f"{liqcs_config.AnsiColors.reset}{liqcs_config.dashline()}"
            )
            sbet_files = None
        else:
            print(
                f"{liqcs_config.AnsiColors.magenta}"
                f"\nNo SBET files in that directory! Please try again."
                f"{liqcs_config.AnsiColors.reset}{liqcs_config.dashline()}\n"
            )

    print(liqcs_config.dashline())
    outdir = None
    while not outdir:
        select_output_directory_message = (
            "Select directory to create output geopackage(s) from the pop-up window."
        )
        if True:  # this line to preserve indenting of halo option
            print(select_output_directory_message)  # this line instead of halo
        # with Halo(  # halo not cooperating with pyinstaller
        #     text=select_output_directory_message
        # ):
            outdir = filedialog.askdirectory(
                title="Select directory to create output geopackage(s)"
            )
        print(
            f"For the output directory, you selected:"
            f"{liqcs_config.AnsiColors.yellow}\n\t{outdir}{liqcs_config.AnsiColors.reset}\n"
        )
        if not outdir:
            print(
                f"{liqcs_config.AnsiColors.magenta}"
                f"\nNo output directory selected! Please try again."
                f"{liqcs_config.AnsiColors.reset}{liqcs_config.dashline()}"
            )
        else:
            print(liqcs_config.dashline())

    output_epsg = __get_crs_from_user_input()

    traj_to_gpkg(sbet_files, outdir, nth_point, output_epsg)

    __ask_open_outdir(outdir)

    __print_exit_message()


def main():
    # This script can be run two ways without using LiQCS:
    # with a chatty command line interface,
    # or a snazzy green GUI.
    # Choose your preferred interface by flipping this switch.
    use_command_line_interface = False
    if use_command_line_interface:
        cli()
    else:
        __trajectory_to_geopackage_gui()


if __name__ == '__main__':
    main()
