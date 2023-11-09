# ------------------------------------------------------------------------------
# GUI module for LiQCS
# Written by Sam May
# ------------------------------------------------------------------------------
# Updates by Natalie Jackson
# ------------------------------------------------------------------------------

from tkinter import *
from tkinter import ttk, filedialog, messagebox
from idlelib.tooltip import Hovertip
from multiprocessing import freeze_support
from datetime import datetime
import progressbar
import os
import base64
import glob
import random
from pathlib import Path
import shutil
import sys
import platform
import ctypes
import tempfile

# Local imports
from liqcs_const import EpsgCode, LiqcsTests
import liqcs
import liqcs_config
import density_analysis.density_analysis_config

sys.path.append(
    os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    __file__
                )
            )
        ),
        "corrupt_checks"
    )
)
from liqcs_min_max_xy import check_min_max_x_y


# Testing switch for Sam to bypass connecting to BCGW
# (density check will use previously pickled water polygons)
# Set to False to run on new data; True for development only.
sam_testing = False
IS_LINUX = (sys.platform == "linux") or (sys.platform == "linux2")


def fix_ansi_colours_for_colourful_text_in_terminal():
    """
    This function keeps the coloured text in the terminal printing
    properly, rather than switching back to the Ansi codes.

    It's not necessary in the .py version of this script, but the coloured
    text doesn't always work in the .exe file without this function call.

    Reference:
    https://gist.github.com/RDCH106/6562cc7136b30a5c59628501d87906f7
    """
    if os.name == 'nt' and platform.release() == '10' and platform.version() >= '10.0.14393':
        # Fix ANSI color in Windows 10 version 10.0.14393 (Windows Anniversary Update)
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


def _io_frame_label():
    return "Set input and output directories"


def _input_frame_label():
    return (
        "Input directory path or .txt path (.txt contains list of input file paths)"
    )


def _output_frame_label():
    return "Output directory path"


def _choose_output_directory_button_text():
    return "Browse to output\ndirectory"


def _choose_input_directory_button_text():
    return "Browse to input\ndirectory"


def _file_list_button_text():
    return "Browse to file list\n.txt file"


def _search_subdirectories_checkbutton_text():
    return "Include subdirectories"


def _percentage_of_files_label():
    return "Percentage of files to test: ", "%"


def _core_frame_label():
    return "Choose number of cores for processing"


def _choose_tests_frame_label():
    return "Choose tests to run on input data"


def _quit_button_text():
    return "Quit"


def _process_queue_button_text():
    return "Process queue"


class LiQCS_GUI:

    def __init__(self):
        self.root = Tk()
        self.open_liqcs_gui_on_top_of_other_windows()
        self.set_icon(self.root)
        self.root.title(liqcs_config.SOFTWARE_NAME)
        self.root.resizable(width=False, height=False)
        self.queueDict = {}
        self.queueItemFrames = []
        self.chkbTestText = [f'{i+1}. {LiqcsTests.TEST_TEXT_LIST[i]}' for i in range(len(LiqcsTests.TEST_TEXT_LIST))]
        self.populate_gui()

    def open_liqcs_gui_on_top_of_other_windows(self):
        """
        Open the LiQCS GUI window on top of other windows,
        but allow other windows to be placed on top
        after it's opened.
        """
        # Open window on top of others
        self.root.attributes('-topmost', True)
        self.root.update()
        # Allow other windows to go on top of it afterwards
        self.root.attributes('-topmost', False)

    def open_popup_on_top_of_other_windows(self, popup):
        # Open window on top of others
        popup.attributes('-topmost', True)
        popup.update()
        # Allow other windows to go on top of it afterwards
        popup.attributes('-topmost', False)

    def set_icon(self, frame):

        if not IS_LINUX:
            icon_data = base64.b64decode(liqcs_config.BC_LOGO_B64)
            icon_path = os.path.join(os.getcwd(), "bc.ico")

            with open(icon_path, 'wb') as icon_file:
                icon_file.write(icon_data)

            frame.wm_iconbitmap(icon_path)
            os.remove(icon_path)


    def populate_gui(self, edit=False, queuePointer=None):
        """
        Everything in the GUI minus the queue.
        """
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # topFrame - Makes up the left side of the GUI, contains: input, output, cores, config
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if edit == True:
            popup = Toplevel()
            self.open_popup_on_top_of_other_windows(popup)
            popup.resizable(False, False)
            self.set_icon(popup)
            popup.grab_set()

            topFrame = Frame(popup)
        else:
            topFrame = Frame(self.root)
        
        topFrame.grid(row=0, column=0, padx=55)
        ioFrame = ttk.LabelFrame(topFrame, text=_io_frame_label())
        ioFrame.grid(row=0, column=0, pady=5, padx=5)
        chooseTestsFrame = ttk.LabelFrame(topFrame, text=_choose_tests_frame_label())
        chooseTestsFrame.grid(row=0, column=1, pady=5, padx=5)

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # inputFrame - Select input directory
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        inputFrame = ttk.LabelFrame(ioFrame, text=_input_frame_label())
        inputFrame.grid(row=0, column=0, padx=5)
        
        inputEntry = StringVar()
        if edit == True:
           inputEntry.set(self.queueDict[queuePointer]['inputPath']) 
        ttk.Entry(
            inputFrame,
            width=40,
            textvariable=inputEntry
        ).grid(row=0, column=0)
        ttk.Button(
            inputFrame,
            text=_choose_input_directory_button_text(),
            command=lambda: self.path_select(inputEntry)
        ).grid(row=0, column=1)
        ttk.Button(
            inputFrame,
            text=_file_list_button_text(),
            command=lambda: self.file_list_select(inputEntry)
        ).grid(row=1, column=1)

        recurseEntry = IntVar()
        if edit == True:
            recurseEntry.set(self.queueDict[queuePointer]['recurse'])
        
        ttk.Checkbutton(
            inputFrame,
            text=_search_subdirectories_checkbutton_text(),
            variable=recurseEntry,
            onvalue=1,
            offvalue=0
        ).grid(row=1, column=0)

        percentFrame = Frame(inputFrame)
        percentFrame.grid(row=2, column=0)
        ttk.Label(percentFrame, text=_percentage_of_files_label()[0]).grid(row=1, column=0)
        sampleSize = StringVar()
        if edit == True:
            sampleSize.set(int(100 * (self.queueDict[queuePointer]['sampleSize'])))
        else:
            sampleSize.set(100)
        ttk.Entry(percentFrame, width=3, textvariable=sampleSize).grid(row=1, column=1)
        ttk.Label(percentFrame, text="%").grid(row=1, column=2)

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # outputFrame - Select output directory
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        outputFrame = ttk.LabelFrame(ioFrame, text=_output_frame_label())
        outputFrame.grid(row=1, column=0, padx=5, pady=5)
        outputEntry = StringVar()
        if edit == True:
            outputEntry.set(self.queueDict[queuePointer]['outputPath'])
        ttk.Entry(
            outputFrame,
            width=40,
            textvariable=outputEntry
        ).grid(row=0, column=0)
        ttk.Button(
            outputFrame,
            text=_choose_output_directory_button_text(),
            command=lambda: self.path_select(outputEntry)
        ).grid(row=0, column=1)

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # coreFrame - Select number of processor cores from drop down menu
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        coreFrame = ttk.LabelFrame(
            topFrame,
            text=_core_frame_label()
        )
        coreFrame.grid(row=2, column=0, pady=(0, 5), sticky=W)
        ttk.Label(
            coreFrame,
            text="Cores:"
        ).grid(row=0, column=0)

        # Core selection combobox
        coreSelect = StringVar()
        coreOptions = ttk.Combobox(
            coreFrame,
            textvariable=coreSelect,
            state="readonly",
            width=9,
            height=9
        )

        coreOptions['values'] = (
            '1',
            '2',
            '3',
            'Default (4)',
            '5',
            '6',
            '7',
            '8'
        )
        if edit == True:
            coreOptions.current(self.queueDict[queuePointer]['cores'] - 1)
        else:
            coreOptions.current(3)
        coreOptions.grid(row=0, column=1)

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # testFrame - contains all test options
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        testsFrame = ttk.LabelFrame(chooseTestsFrame, text="Tests")
        testsFrame.grid(row=0, column=0, pady=5, padx=5)

        testCheckboxFrame = Frame(testsFrame)
        testCheckboxFrame.grid(row=0, column=0)

        chkbList = [IntVar() for i in range(len(self.chkbTestText))]
        if edit == True:
            selectedTests = self.queueDict[queuePointer]['tests']
            for i in range(len(chkbList)):
                if i + 1 in selectedTests:
                    chkbList[i].set(1)

        # Create checkbuttons for tests
        row_num = 0
        column_num = 0
        for x, y, z in zip(chkbList, self.chkbTestText, LiqcsTests.TEST_DESC_LIST):
            chkb = ttk.Checkbutton(testCheckboxFrame, text=y, variable=x)
            if row_num >= 6:
                row_num = 0
                column_num = column_num + 2
            CreateToolTip(chkb, text=z)
            chkb.grid(
                row=row_num,
                column=column_num,
                sticky='W'
            )
            row_num = row_num + 1

        selectFrame = Frame(testsFrame)
        selectFrame.grid(row=1, column=0)
        ttk.Button(
            selectFrame,
            text="Select/clear all",
            command=lambda: self.select_trigger(chkbList)
        ).grid(
            row=0,
            column=0,
            pady=5,
            sticky='WE'
        )

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Default Tests - Contains buttons that select tests in chkblist
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        dTestFrame = ttk.LabelFrame(
            chooseTestsFrame,
            text="Default tests"
        )
        dTestFrame.grid(row=0, column=1, padx=5)
        default_test_dict = self._default_test_dict()
        default_test_dict_keys = list(default_test_dict)
        default_test_buttons_column = 0
        default_test_button_padx = 5
        default_test_buttons_pady = 4
        default_test_buttons_sticky = W

        # Button 0: First set of default tests from _default_test_dict()
        ttk.Button(
            dTestFrame,
            text=self._default_test_button_text(0),  # 0
            command=lambda: self.default_test_select(
                chkbList,
                default_test_dict_keys[0]  # 0
            )
        ).grid(
            row=0,  # 0
            column=default_test_buttons_column,
            padx=default_test_button_padx,
            pady=default_test_buttons_pady,
            sticky=default_test_buttons_sticky
        )

        # Button 1: Second set of default tests from _default_test_dict()
        ttk.Button(
            dTestFrame,
            text=self._default_test_button_text(1),  # 1
            command=lambda: self.default_test_select(
                chkbList,
                default_test_dict_keys[1]  # 1
            )
        ).grid(
            row=1,  # 1
            column=default_test_buttons_column,
            padx=default_test_button_padx,
            pady=default_test_buttons_pady,
            sticky=default_test_buttons_sticky
        )
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Bottom of window - edit: update, discard, delete and main: queue, queue options 
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if edit == True:
            buttonClicked = IntVar()
            saveClicked = IntVar(value=0)
            doneClicked = IntVar()
            buttonFrame = Frame(popup)
            buttonFrame.grid(row=1, column=0, pady=(0, 5))

            ttk.Button(
                buttonFrame,
                text="Update queue item",
                padding=10,
                command=lambda: [buttonClicked.set(1), saveClicked.set(value=1)]
            ).grid(row=0, column=0)
            ttk.Button(
                buttonFrame,
                text="Discard changes",
                padding=10,
                command=lambda: [buttonClicked.set(1), doneClicked.set(1)]
            ).grid(row=0, column=1, padx=5)
            ttk.Button(
                buttonFrame,
                text="Delete queue item",
                padding=10,
                command=lambda: [
                    self.delete_queue(queuePointer),
                    buttonClicked.set(1),
                    doneClicked.set(1)
                ]
            ).grid(row=0, column=2)

            popup.wait_variable(buttonClicked)

            if saveClicked.get() == 1:
                self.add_to_queue(
                    inputEntry,
                    outputEntry,
                    chkbList,
                    coreSelect.get(),
                    sampleSize.get(),
                    recurseEntry,
                    queuePointer
                )
                popup.destroy()

            popup.wait_variable(doneClicked)
            popup.destroy()
        else:
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # addToQueueFrame - Contains the "Add to queue" button
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

            addToQueueFrame = Frame(self.root)
            addToQueueFrame.grid(row=1, column=0, pady=(20, 0), columnspan=3)

            ttk.Button(
                addToQueueFrame,
                text="Add to Queue",
                padding=20,
                command=lambda: self.add_to_queue(
                    inputEntry,
                    outputEntry,
                    chkbList, 
                    coreSelect.get(),
                    sampleSize.get(),
                    recurseEntry,
                    None
                )
            ).grid(row=3, column=0, pady=5)

            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # queueActionFrame - Process and clear queue buttons
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            queueActionFrame = Frame(self.root)
            queueActionFrame.grid(row=3, column=0, pady=5)
            ttk.Button(
                queueActionFrame,
                text=_process_queue_button_text(),
                command=lambda: self.run_tests(),
                padding=20
            ).grid(row=0, column=0)
            ttk.Button(
                queueActionFrame,
                text="Clear queue",
                command=lambda: self.clear_queue(),
                padding=20
            ).grid(row=0, column=1, padx=(10, 0))

            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # queueFrame - Contains queue of tests to be run
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

            self.queueFrame = ScrollingFrame(self.root)
            self.queueFrame.grid(row=2, column=0, pady=5, padx=5, sticky="WE")
            self.innerQueueFrame = self.queueFrame.frame

            print(
                f" {liqcs_config.rainbow_string (liqcs_config.dashline())}"
                f"Add tests to LiQCS queue in the LiQCS GUI."
            )

            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # softwareFrame - Information and quit buttons
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            softwareFrame = Frame(self.root)
            softwareFrame.grid(row=4, column=0, pady=(5, 10))
            ttk.Button(
                softwareFrame,
                text="Help",
                command=lambda: self.help_page()
            ).grid(row=0, column=0, padx=10)
            ttk.Button(
                softwareFrame,
                text="About",
                command=lambda: self.about_page()
            ).grid(row=0, column=1, padx=10)
            ttk.Button(
                softwareFrame,
                text=_quit_button_text(),
                command=self.root.destroy
            ).grid(row=0, column=2, padx=10)

    def select_trigger(self, chkbList):
        """
        Set all test checkboxes to checked, if all checked uncheck all
        """
        intList = [var.get() for var in chkbList]
        if 0 not in intList:
            for x in chkbList:
                x.set(0)
        else:
            for x in chkbList:
                x.set(1)

    def path_select(self, pathSV):
        """
        Opens 'select folder' windows dialog,
        adds the selected folder to the relevant entrybox.
        """
        dirPath = filedialog.askdirectory(initialdir="/")
        pathSV.set(dirPath)

    def file_list_select(self, entry):
        """
        Opens 'select file' windows dialog,
        adds the selected txt file to the relevant entrybox.

        Args:
            entry (tkinter StrVar object):
        """
        fileListInput = filedialog.askopenfilename(
            initialdir="/",
            filetypes=[("Text File", "*.txt")]
        )
        entry.set(fileListInput)

    def get_test_list_str(self, testList):
        """
        Formats a string of tests by test number for queueItems.

        Args:
            testList: List of StringVars
        
        Returns:
            String ex: 'Tests: 1, 2, 3'
        """
        testStr = "Tests: "
        x = 0
        for x in range(len(testList)):
            if testStr == "Tests: ":
                testStr += str(testList[x])
            else:
                testStr += ", "
                testStr += str(testList[x])
        return testStr

    def get_short_path_str(self, path):
        """
        Creates a shortened string for a folder or file path.

        Args:
            folder or file path: String.
        
        Returns:
            A shortened folder or file path: String.
            Ex: 'C:/.../input_folder'
        """
        if (path.count('/') > 1):
            startOfPath = path[0:2]
            endOfPath = path.split('/').pop()
            shortPath = f"{startOfPath}/.../{endOfPath}"
        else:
            shortPath = path

        return shortPath

    def format_datetime(self, datetime_stamp):
        """
        Format datetime object as a nice string for printing.

        Args:
            datetime_stamp (datetime object):
                - Any datetime object.

        Returns:
            str:
                - Time stamp as string, formatted: "YYYY-MM-DD, HH:MM:SS"
        """
        formatted_datetime = datetime_stamp.strftime('%Y-%m-%d, %H:%M:%S')
        return formatted_datetime

    def format_datetime_duration(self, some_duration, num_decimal_places_seconds):
        """
        Format a datetime timedelta (duration) object
        as a string truncated to a certain number of 
        characters past the second colon.

        Args:
            some_duration (datetime timedelta object):
                - Any datetime timedelta object

        Returns:
            str:
                - Duration formatted as a string, truncated
                    to a certain number of characters past the
                    second colon.
        """
        # Convert timedelta to a string
        some_duration_str = str(some_duration)

        # Find the position of the first colon (can be in a different
        # location depending on how many hours are in the timedelta:
        # 1000 hours vs 100 hours vs 10 hours vs 1 hour, etc.)
        first_colon = some_duration_str.find(":")

        # Find the position of the second colon in the string, between the 
        # minutes and the seconds
        second_colon = some_duration_str.find(":", first_colon + 1)

        if num_decimal_places_seconds == 0:
            truncation_index = second_colon + 3
        else:
            truncation_index = second_colon + num_decimal_places_seconds + 4

        # Truncate the string to remove unnecessary decimal places
        formatted_datetime = some_duration_str[:truncation_index]

        return formatted_datetime

    def about_page(self):
        """
        Displays a tkinter message box showing all test descriptions.
        """
        messagebox.showinfo(
            "About LiQCS Tests",
            liqcs_config.LiQCS_ABOUT_PAGE_TEXT
        )

    def help_page(self):
        """
        Displays a tkinter message box detailing input reqirements and test descriptions.
        """
        messagebox.showinfo(
            "LiQCS Help",
            liqcs_config.LiQCS_HELP_PAGE_TEXT
        )


    def _default_test_dict(self):
        default_test_dict = {
            # File Naming, Laszy, LiDAR Summary, Density Analysis
            "Acquisition LiDAR (raw strip data)": [
                LiqcsTests.FILE_NAMING, 
                LiqcsTests.LASZY, 
                LiqcsTests.LASZY_SUMMARY, 
                LiqcsTests.DENSITY_ANALYSIS
            ],
            # File Naming, Tile index, QC Prep, Laszy, LiDAR Summary, Density Analysis
            "Production LiDAR (classified, tiled data)": [
                LiqcsTests.FILE_NAMING, 
                LiqcsTests.TILE_INDEX, 
                LiqcsTests.QC_PREP, 
                LiqcsTests.LASZY, 
                LiqcsTests.LASZY_SUMMARY, 
                LiqcsTests.DENSITY_ANALYSIS
            ]
        }
        return default_test_dict

    def default_test_select(self, chkbList, test):
        # Reset all tests to unchecked
        for chkb in chkbList:
            chkb.set(0)
        testDict = self._default_test_dict()
        # Check the default tests
        for x in testDict[test]:
            chkbList[x - 1].set(1)

    def _default_test_button_text(self, default_test_dict_index):
        default_test_dict = self._default_test_dict()
        default_test_dict_keys = list(default_test_dict)
        test_numbers_in_string_with_commas = str(
            default_test_dict.get(default_test_dict_keys[default_test_dict_index])
        )[1:-1]
        default_test_button_text = (
            f"{default_test_dict_keys[default_test_dict_index]}"
            f"\nTests: {test_numbers_in_string_with_commas}"
        )
        return default_test_button_text


    def add_to_queue(
        self,
        inputEntry,
        outputEntry,
        chkbList,
        cores,
        sampleSize,
        recurseEntry,
        queuePointer=None
    ):
        """
        Takes in a list of tests, input and output paths, other info, and creates queue object.
        Gathers requirements for selected tests.
        """
        inputPath = inputEntry.get()
        outputPath = outputEntry.get()
        recurse = recurseEntry.get()
        try:
            inputPath, outputPath, testList, infileGlob, sampleSize, isSingleFile, isFileList, cores = self.validate_input(
                inputPath,
                outputPath,
                chkbList,
                cores,
                sampleSize,
                recurse)
        except ValueError as inputError:
            messagebox.showerror(
                "Input Error", 
                str(inputError)
                )
            return

        # ----------------------------------------------------------------------

        # Initialize queueDict values
        epsg = None
        QCPercent = None
        shp_files = None
        siteName = None
        concavity = None
        contract = None
        gridClasses = None
        self.densityAnalysisDict = None

        # ----------------------------------------------------------------------

        # Void check (12) requires Density Grid By Class (7)
        if (LiqcsTests.VOID_CHECK in testList) and (LiqcsTests.GRID_LAST_RETURN not in testList):
            print(
                "\nSpecified a test that requires a last return density grid; "
                "adding density grid to tests"
            )
            testList.append(LiqcsTests.GRID_LAST_RETURN)
            testList.sort()

        # ----------------------------------------------------------------------

        # Prompt user for an EPSG code if needed
        if (
            LiqcsTests.GRID_DENSITY_CLASS in testList  # Ground Density Grid
            or LiqcsTests.GRID_LAST_RETURN in testList  # Last Return Density Grid
            or LiqcsTests.GRID_INTENSITY in testList  # Intensity Grid
            or LiqcsTests.TRAJ_TO_GPKG in testList  # Trajectory to Geopackage
        ):
            epsg = self.epsg_popup()

        if LiqcsTests.TILE_INDEX in testList:
            contract = self.contract_popup()

        if LiqcsTests.GRID_DENSITY_CLASS in testList:
            while True:
                gridClasses = self.grid_classes_popup()
                if gridClasses is not None:
                    break

        # Generate lidar Extents (6) requires a site/project name for the output shape file name
        if LiqcsTests.LIDAR_EXTENTS in testList:
            while True:
                siteName, concavity = self.LiDAR_extents_popup(siteName, concavity)
                if siteName == "":
                    messagebox.showerror(
                        "Input error",
                        f"A site/project name must be specified."
                    )
                    siteName = None
                    if concavity.isdigit() is False:
                        concavity = None
                        continue
                    else:
                        continue
        
                if concavity.isdigit() is False:
                    messagebox.showerror(
                        "Input error",
                        f"LiDAR boundary concavity must be a postive whole or decimal number."
                    )
                    concavity = None
                    continue
                else: 
                    break
            concavity = float(concavity)
        
        # Lidar Summary (5) requires lasinfos (4)
        if (LiqcsTests.LASZY_SUMMARY in testList) and (LiqcsTests.LASZY not in testList):

            print(
                "\nSpecified a test that requires Laszy results; "
                "adding Laszy to tests."
            )
            testList.append(LiqcsTests.LASZY)
            testList.sort()

        # QC Prep (3) requires a user specified percentage
        if LiqcsTests.QC_PREP in testList:
            QCPercent = self.lidar_qc_prep_popup()

        # Void check (v) requires a shapefiles for AOI and breaklines
        if LiqcsTests.VOID_CHECK in testList:
            while True:
                shp_files = self.shape_files_popup()
                if (
                    os.path.isfile(shp_files[0])
                    and os.path.isfile(shp_files[1])
                ):
                    break
                elif (
                    not os.path.isfile(shp_files[0])
                    and not os.path.isfile(shp_files[1])
                ):
                    print(
                        "Both specified shapefiles could not be found."
                    )
                elif not os.path.isfile(shp_files[0]):
                    print(
                        "Specified breaklines file could not be found."
                    )
                elif not os.path.isfile(shp_files[1]):
                    print(
                        "Specified AOI file could not be found."
                    )

        if LiqcsTests.TRAJ_TO_GPKG in testList:
            out_files_exist = False
            for file in infileGlob:
                if os.path.splitext(file)[1].lower() == '.out':
                    out_files_exist = True
                    break
            if not out_files_exist:
                messagebox.showerror(
                    "Input error",
                    "Input path does not contain \'.out\' files, which "
                    "are required for the \'Trajectories To GPKG\' test."
                )
                return

        if LiqcsTests.DENSITY_ANALYSIS in testList:
            if (
                queuePointer is not None
                and self.queueDict[queuePointer]['densityAnalysisDict'] is not None
            ):
                self.densityAnalysisDict = {}
                self.densityAnalysisDict['rasterDir'] = (
                    self.queueDict[queuePointer]['densityAnalysisDict']['rasterDir']
                )
                self.densityAnalysisDict['projectAreaDir'] = (
                    self.queueDict[queuePointer]['densityAnalysisDict']['projectAreaDir']
                )
                self.densityAnalysisDict['minDensityReq'] = (
                    self.queueDict[queuePointer]['densityAnalysisDict']['minDensityReq']
                )
                self.densityAnalysisDict['bcgwCredentials'] = (
                    self.queueDict[queuePointer]['densityAnalysisDict']['bcgwCredentials']
                )
                self.densityAnalysisDict['check_correct_units'] = (
                    self.queueDict[queuePointer]['densityAnalysisDict']['check_correct_units']
                )
                self.densityAnalysisDict['normalizationDivisor'] = (
                    self.queueDict[queuePointer]['densityAnalysisDict']['normalizationDivisor']
                )

            else:
                tif_files_exist = False
                for file in infileGlob:
                    if os.path.splitext(file)[1].lower() in ('.tiff', '.tif'):
                        tif_files_exist = True
                        break

                self.densityAnalysisDict = {
                    "rasterDir": inputPath if tif_files_exist else None,
                    'projectAreaDir': None,
                    'minDensityReq': None,
                    'bcgwCredentials': None,
                    'check_correct_units': None,
                    'normalizationDivisor': None

                }

            while True:
                self.density_analysis_popup()
                daValid = self.density_analysis_validation()
                if daValid is True:
                    if self.densityAnalysisDict['check_correct_units'] == 1:
                        self.densityAnalysisDict['check_correct_units'] = True
                    else:
                        self.densityAnalysisDict['check_correct_units'] = False
                    break

        # ----------------------------------------------------------------------


        # point to end of queue
        if queuePointer is None:
            queuePointer = len(self.queueDict)
        self.queueDict[queuePointer] = {}
        self.queueDict[queuePointer]['inputPath'] = inputPath
        self.queueDict[queuePointer]['outputPath'] = outputPath
        self.queueDict[queuePointer]['tests'] = testList
        self.queueDict[queuePointer]['cores'] = cores
        self.queueDict[queuePointer]['epsg'] = epsg
        self.queueDict[queuePointer]['shapeFiles'] = shp_files
        self.queueDict[queuePointer]['gridClasses'] = gridClasses
        self.queueDict[queuePointer]['QCPercent'] = QCPercent
        self.queueDict[queuePointer]['sampleSize'] = sampleSize
        self.queueDict[queuePointer]['recurse'] = recurse
        self.queueDict[queuePointer]['isSingleFile'] = isSingleFile
        self.queueDict[queuePointer]['siteName'] = siteName
        self.queueDict[queuePointer]['concavity'] = concavity
        self.queueDict[queuePointer]['contract'] = contract
        self.queueDict[queuePointer]['isFileList'] = isFileList
        self.queueDict[queuePointer]['densityAnalysisDict'] = self.densityAnalysisDict
        

        for x in chkbList:
            x.set(0)
        
        inputEntry.set('')
        outputEntry.set('')
        recurseEntry.set(0)

        self.update_queue()

        self.print_queue_updated_message()

    def validate_input(
        self,
        inputPath,
        outputPath,
        chkbList,
        cores,
        sampleSize,
        recurse
        ):
        """
        Validates all input from main_gui and edit_queue
        """
        # Check if there are tests selected -------------------------------------------
        testList = []
        for t in range(len(chkbList)):
            if type(chkbList[t]) == IntVar:
                if chkbList[t].get() == 1:
                    testList.append(t + 1)
            else:
                if chkbList[t] == 1:
                    testList.append(t + 1)

        if len(testList) == 0:
            raise ValueError("No tests selected! Please select one or more tests.")

        for i in range(len(testList)):
            if testList[i] >= 1:
                break
        
        # Check if input path is valid ------------------------------------------------
        # Remove leading and trailing whitespace from input path
        inputPath = inputPath.strip()

        # Check if input directory contains spaces
        if ' ' in inputPath:
            raise ValueError("Invaild input path. Please remove spaces from input path.")

        # Check if input directory exists
        if not os.path.exists(inputPath):
            raise ValueError("Input path does not exist! Please provide another path.")
        
        # -----------------------------------------------------------------------------
        # Validate sample size is an integer 1-100
        try:
            sampleSize = int(sampleSize)
            if sampleSize > 100 or sampleSize <= 0:
                raise ValueError
        except ValueError:
            raise ValueError("Percentage of files must be a number from 1-100.")

        # Convert sample size percentage to fraction of 1
        sampleSize = sampleSize / 100

        # -----------------------------------------------------------------------------

        if cores == "Default (4)":
            cores = 4
        else:
            cores = int(cores)

        # -----------------------------------------------------------------------------

        try:
            if os.path.splitext(inputPath)[1] in ('.txt', '.las', '.laz'):
                isSingleFile = True
                if os.path.splitext(inputPath)[1] in '.txt':
                    isFileList = True
                else:
                    isFileList = False
            else:
                isFileList = False
                isSingleFile = False
        except IndexError:
            isFileList = False
            isSingleFile = False

        # Check if files exist in input -----------------------------------------------
        infileGlob = self.glob_input_files(
            inputPath,
            testList,
            sampleSize,
            recurse,
            isFileList,
            isSingleFile
        )
        if len(testList) == 1:
            s_no_s = ""
        else:
            s_no_s = "s"
        if len(infileGlob) == 0:
            raise ValueError(f"No valid files for the selected test{s_no_s} found in input!")
        
        # Check if output path is valid -----------------------------------------------
        # Strip any leading or trailing whitespace from the output path
        outputPath = outputPath.strip()

        # Make an outputPath if it doesn't exist
        default_liqcs_results_folder_name = 'liqcs_results'
        if outputPath == '' and not isSingleFile:
            outputPath = os.path.join(inputPath, default_liqcs_results_folder_name)
            if not os.path.isdir(outputPath):
                os.makedirs(outputPath)
                print("Output path created: ", outputPath)
        elif outputPath == '' and isSingleFile:

            singleFilePath = list(os.path.split(inputPath))
            del singleFilePath[1]
            singleFilePath = str(singleFilePath[0])
            outputPath = os.path.join(singleFilePath, default_liqcs_results_folder_name)
            if not os.path.isdir(outputPath):
                os.makedirs(outputPath)
                print(f"\nOutput path created:\n\t{outputPath}\n")

        elif not os.path.exists(outputPath):
            os.makedirs(outputPath)
            if not os.path.exists(outputPath):
                print(
                    "Selected output path could not be created;"
                    "\ncreating output folder within input folder"
                )
                outputPath = os.path.join(inputPath, default_liqcs_results_folder_name)
                if not os.path.isdir(outputPath):
                    os.makedirs(outputPath)

            print("Output path: ", outputPath)
        # -----------------------------------------------------------------------------
        
        return inputPath, outputPath, testList, infileGlob, sampleSize, isSingleFile, isFileList, cores

    def update_queue(self):
        """
        Destroys all queueItemFrames and rebuilds them using queueDict.
        """
        for x in range(len(self.queueItemFrames)):
            self.queueItemFrames[x].destroy()

        self.queueItemFrames = []
        i = 0

        for i in range(len(self.queueDict)):

            inputStr = f"Input directory:\n{self.queueDict[i]['inputPath']}"
            outputStr = f"Output directory:\n{self.queueDict[i]['outputPath']}"

            testStr = self.get_test_list_str(self.queueDict[i]['tests'])
            cores_str = f"Cores: {self.queueDict[i]['cores']}"
            percentage_to_test_str = (
                f"Files to test:\n{int(self.queueDict[i]['sampleSize']*100)}%"
            )

            self.queueItemFrames.append(
                ttk.LabelFrame(
                    self.innerQueueFrame,
                    width=450,
                    height=100,
                    text=i + 1
                )
            )

            # Position the queue item frame in the queue frame
            self.queueItemFrames[i].grid(
                row=i,
                column=0,
                padx=70,
                pady=(0, 5)
            )

            io_string_wraplength = '180m'  # millimetres

            # Input string
            ttk.Label(
                self.queueItemFrames[i], 
                width=150, 
                wraplength=io_string_wraplength,
                text=inputStr
            ).grid(row=0, column=0, sticky=N)

            # Output string
            ttk.Label(
                self.queueItemFrames[i], 
                width=150,
                wraplength=io_string_wraplength,
                text=outputStr
            ).grid(row=1, column=0, pady=4, sticky=N)

            # Percentage of files to test string
            ttk.Label(
                self.queueItemFrames[i],
                text=percentage_to_test_str
            ).grid(row=0, column=1, padx=4, sticky=N + W)

            # Tests string
            ttk.Label(
                self.queueItemFrames[i],
                width=12,
                wraplength='24m',
                text=testStr
            ).grid(row=0, column=2, padx=4, sticky=W)

            # Cores string
            ttk.Label(
                self.queueItemFrames[i],
                text=cores_str
            ).grid(row=1, column=2, padx=4, sticky=W)

            # Button: edit queue item 
            ttk.Button(
                self.queueItemFrames[i],
                text="Edit",
                command=lambda i=i: self.populate_gui(True, i)
            ).grid(row=0, column=3)

            # Button: delete queue item
            ttk.Button(
                self.queueItemFrames[i],
                text="Delete",
                command=lambda i=i: self.delete_queue(i)
            ).grid(row=1, column=3)

        self.innerQueueFrame.update_idletasks()
        self.queueFrame.on_canvas_configure(None)

    def delete_queue(self, queuePointer):
        """
        Deletes queue item.

        Args:
            queuePointer: Integer
        """
        lastQueuePos = len(self.queueDict) - 1

        del self.queueDict[queuePointer]

        # idx of first queueDict that needs to be changed
        posChange = lastQueuePos - queuePointer

        if queuePointer < lastQueuePos:
            for n in range(posChange):
                queueMove = queuePointer + 1 + n

                if (queueMove) == lastQueuePos:
                    self.queueDict[queueMove - 1] = self.queueDict[queueMove]
                    del self.queueDict[lastQueuePos]
                    break
                else:
                    self.queueDict[queueMove - 1] = self.queueDict[queueMove]

        self.update_queue()

    def clear_queue(self):
        """
        Deletes all items in the queue.
        """
        self.queueDict = {}
        self.update_queue()

    def print_queue_updated_message(self):
        """
        Print a helpful message to the console
        when the queue has been updated.
        """
        print(
            f" {liqcs_config.rainbow_string (liqcs_config.dashline())}"
            f" {liqcs_config.AnsiColors.yellow}Queue updated!"
            f" {liqcs_config.AnsiColors.reset}"
            "\n\nAdd more tests to the queue, or click the "
            f" {liqcs_config.AnsiColors.cyan}{_process_queue_button_text()}"
            f" {liqcs_config.AnsiColors.reset} button in the LiQCS GUI "
            "to begin processing."
        )

    def glob_input_files(
        self,
        inputPath,
        testList,
        sampleSize,
        recurse,
        isFileList,
        isSingleFile,
        runTime=False
    ):
        """
        Grabs all input file paths and adds them to a list.

        Args:
            inputPath: String
            testList: List of integers,
            sampleSize: Percentage of files to grab: Integer,
            recurse: Search for files recursivly?: Boolean,
            isFileList: Is the input a text file full of file paths?: Boolean,
            isSingleFile: Is the input a single file?: bo0lean,
            runTime: Verifies if files from a text file exist: Boolean, Default=False
        """

        extensions = []
        infileGlob = []
        if not isSingleFile:
            if len(testList) == 1 and LiqcsTests.SHAPEFILE_CHECK in testList:
                extensions = (".laz", ".shp")
            # If Trajectories To GPKG is the only test
            elif len(testList) == 1 and LiqcsTests.TRAJ_TO_GPKG in testList:
                extensions = (".out", )  # Tuple length 1 needs internal comma
            # Grab .tiff/.tif files for Density Analysis test
            elif (len(testList) == 1) and (LiqcsTests.DENSITY_ANALYSIS in testList) and (recurse == 0):
                extensions = (".tiff", ".tif")
            elif (LiqcsTests.DENSITY_ANALYSIS in testList) and (recurse == 0):
                extensions = (".laz", ".las", ".out", ".tiff", ".tif")
            else:
                extensions.extend([".laz", ".las", ".out", ".shp"])
            for extension in extensions:
                if recurse == 1:
                    infileGlob.extend(
                        glob.iglob(inputPath + "\**/*" + extension, recursive=True)
                    )
                else:
                    infileGlob.extend(
                        glob.iglob(inputPath + "/*" + extension)
                    )

        elif isFileList:
            with open(inputPath, 'r') as f:
                line_strip = [line.strip() for line in f]
            for line in line_strip:
                if os.path.splitext(line)[1].lower() in extensions:
                    infileGlob.append(line)

        elif not isFileList and isSingleFile:
            infileGlob.append(inputPath)

        if not isSingleFile and sampleSize < 1:
            fileSample = int(len(infileGlob) * sampleSize)
            sample_set = set({})
            while len(sample_set) < fileSample:
                i = random.randrange(0, len(infileGlob))
                sample_set.add(i)
            sample_set = list(sample_set)
            sample_set.sort()
            sample_files = []
            for x in sample_set:
                sample_files.append(infileGlob[x])
            infileGlob = sample_files

        if runTime == True and isFileList == True:
            filesNotFound = []
            for file in infileGlob:
                if not os.path.isfile(file):
                    filesNotFound.append(file)

            if len(filesNotFound) > 0:
                for file in filesNotFound:
                    infileGlob.remove(file)
                filesNotFoundFile = os.path.join(self.queueDict[i]['outputPath'], "files_not_found.txt")
                with open(filesNotFoundFile, mode='w') as filesNotFoundOut:
                    print("File(s) not Found:\n", file=filesNotFoundOut)
                    for file in filesNotFound:
                        print(f"{file}", file=filesNotFoundOut)
        
        return infileGlob

    def do_file_types_exist(self, input, extensions):
        """
        Check if file types exist anywhere in a directory
        (searches directory recursively).

        Args:
            input (str): Path to a directory.
            extensions (list of str):
                - List of extensions to check for within directory,
                    including the "." symbol.
                - e.g., [".tif", ".tiff"]
                - Not case sensitive; no need to include both ".TIF" and ".tif".

        Returns:
            bool: True or False depending if any of the specified file type(s)
                exist within the given directory.
        """
        if input:
            input_pathobj = Path(input)
            infileGlob = []
            for extension in extensions:
                infileGlob.extend(
                    input_pathobj.rglob(f"*{extension}")
                )

            if infileGlob:
                file_types_exist = True
            else:
                file_types_exist = False
        else:
            # If the project areas directory field is blank,
            # we don't want this function to search through the root
            # directory for those files; force file_types_exist to be False.
            file_types_exist = False

        return file_types_exist


    def density_analysis_popup(self):
        """
        Pop-up window for user to enter input parameters
        for the Density Analysis test.
        """
        popup = Toplevel()
        self.open_popup_on_top_of_other_windows(popup)
        popup.resizable(False, False)
        self.set_icon(popup)
        popup.grab_set()
        ttk.Label(
            popup,
            text="Density Analysis Parameters"
        ).grid(row=0, column=0, pady=5)

        dirFrame = Frame(popup)
        dirFrame.grid(row=1, column=0, padx=10)

        # Input Raster directory---------------------
        ttk.Label(
            dirFrame,
            text="Input density raster directory"
        ).grid(row=0, column=0)

        rasterEntry = StringVar()
        if self.densityAnalysisDict['rasterDir'] is not None:
            rasterEntry.set(self.densityAnalysisDict['rasterDir'])
        input_raster_entry = ttk.Entry(
            dirFrame,
            width=40,
            textvariable=rasterEntry
        )
        input_raster_entry.grid(row=1, column=0)

        # Tooltip with some extra instructions when you hover over the
        # input entry box.
        Hovertip(
            input_raster_entry,
            density_analysis.density_analysis_config.input_raster_rules()
        )

        ttk.Button(
            dirFrame,
            text="Choose directory",
            command=lambda: self.path_select(rasterEntry)
        ).grid(row=1, column=1)
        # -------------------------------------------

        # Project area directory --------------------
        ttk.Label(
            dirFrame,
            text="Project area directory"
        ).grid(row=2, column=0)

        projectAreaEntry = StringVar()
        if self.densityAnalysisDict['projectAreaDir'] is not None:
            projectAreaEntry.set(self.densityAnalysisDict['projectAreaDir'])
        ttk.Entry(
            dirFrame,
            width=40,
            textvariable=projectAreaEntry
        ).grid(row=3, column=0)

        ttk.Button(
            dirFrame,
            text="Choose directory",
            command=lambda: self.path_select(projectAreaEntry)
        ).grid(row=3, column=1)
        # -------------------------------------------

        # Minimum desity requirement ----------------
        densityFrame = Frame(popup)
        densityFrame.grid(row=2, column=0, pady=10)

        ttk.Label(
            densityFrame,
            text="Minimum density requirement:  "
        ).grid(row=0, column=0)

        minDensityReqEntry = StringVar()
        if self.densityAnalysisDict['minDensityReq'] is not None:
            minDensityReqEntry.set(self.densityAnalysisDict['minDensityReq'])
        ttk.Entry(
            densityFrame,
            width=5,
            textvariable=minDensityReqEntry
        ).grid(row=0, column=1)

        ttk.Label(
            densityFrame,
            text="  points per square meter"
        ).grid(row=0, column=2)
        # -------------------------------------------

        # BCGW username and password ----------------
        BCGWFrame = Frame(popup)
        BCGWFrame.grid(row=3, column=0)

        ttk.Label(
            BCGWFrame,
            text="BCGW Username:      "
        ).grid(row=0, column=0, pady=(0, 5))

        bcgwUserEntry = StringVar()
        if self.densityAnalysisDict['bcgwCredentials'] is not None:
            bcgwUserEntry.set(self.densityAnalysisDict['bcgwCredentials'][0])
        ttk.Entry(
            BCGWFrame,
            textvariable=bcgwUserEntry
        ).grid(row=0, column=1, pady=(0, 5))

        ttk.Label(
            BCGWFrame,
            text="BCGW Password:      "
        ).grid(row=1, column=0)

        bcgwPassEntry = StringVar()
        if self.densityAnalysisDict['bcgwCredentials'] is not None:
            bcgwPassEntry.set(self.densityAnalysisDict['bcgwCredentials'][1])
        ttk.Entry(
            BCGWFrame,
            textvariable=bcgwPassEntry,
            show="*"
        ).grid(row=1, column=1)

        normalizeFrame = Frame(popup)
        normalizeFrame.grid(row=4, column=0, pady=10)

        ttk.Label(
            normalizeFrame,
            text="Divide raster values with incorrect units by: "
        ).grid(row=1, column=0, sticky=E)

        divisorEntry = StringVar(value=None)
        if self.densityAnalysisDict['normalizationDivisor'] is not None:
            divisorEntry.set(self.densityAnalysisDict['normalizationDivisor'])
        self.divisorEntryPointer = ttk.Entry(
            normalizeFrame,
            width=4,
            textvariable=divisorEntry,
            state='disabled'
        )
        self.divisorEntryPointer.grid(row=1, column=1, sticky=W)

        check_correct_unitsEntry = IntVar()
        check_correct_unitsEntry.set(0)
        ttk.Checkbutton(
            normalizeFrame,
            text="Check for incorrect units and attempt to correct? Not recommended.",
            variable=check_correct_unitsEntry,
            command=lambda: self.chkb_check(check_correct_unitsEntry)
        ).grid(row=0, column=0, padx=10, columnspan=2)

        if self.densityAnalysisDict['check_correct_units'] is not None:
            if self.densityAnalysisDict['check_correct_units'] is True:
                check_correct_unitsEntry.set(1)
                self.chkb_check(check_correct_unitsEntry)

        isSubmitClicked = IntVar()
        Submit = ttk.Button(
            popup,
            text="Validate inputs and submit",
            padding=10,
            command=lambda: isSubmitClicked.set(1)
        )
        Submit.grid(row=5, column=0, pady=(10, 20))

        popup.wait_variable(isSubmitClicked)
        popup.destroy()

        self.densityAnalysisDict['rasterDir'] = rasterEntry.get().strip()
        self.densityAnalysisDict['projectAreaDir'] = projectAreaEntry.get().strip()
        self.densityAnalysisDict['minDensityReq'] = minDensityReqEntry.get().strip()
        self.densityAnalysisDict['bcgwCredentials'] = (
            bcgwUserEntry.get().strip(),
            bcgwPassEntry.get().strip()
        )
        self.densityAnalysisDict['check_correct_units'] = check_correct_unitsEntry.get()
        self.densityAnalysisDict['normalizationDivisor'] = divisorEntry.get().strip()

    def density_analysis_validation(self):
        """
        Validate the user inputs from the Density Analysis parameters popup.

        Returns:
            bool:
                - True if inputs valid
                - False if some input invalid
        """
        errorList = []

        # Validate input directory contains tiff/tif file(s)
        if not self.do_file_types_exist(self.densityAnalysisDict['rasterDir'], [".tiff", ".tif"]):
            errorList.append(
                f"No .tif/.tiff files found in density raster directory:"
                f"\n{self.densityAnalysisDict['rasterDir']}"
            )
            print(
                f" {liqcs_config.dashline()}"
                f"No .tif/.tiff files found in density raster directory "
                f"{self.densityAnalysisDict['rasterDir']}"
            )
            self.densityAnalysisDict['rasterDir'] = None

        # Validate project areas directory contains shapefile(s)
        if not self.do_file_types_exist(self.densityAnalysisDict['projectAreaDir'], [".shp"]):
            errorList.append(
                f"No .shp files found in project area directory:\n"
                f"{self.densityAnalysisDict['projectAreaDir']}"
            )
            print(
                f" {liqcs_config.dashline()}"
                f"No .shp files found in project area directory "
                f"{self.densityAnalysisDict['projectAreaDir']}"
            )
            self.densityAnalysisDict['projectAreaDir'] = None

        # Validate minimum density requirement entry
        try:
            if ("." in self.densityAnalysisDict['minDensityReq']):
                self.densityAnalysisDict['minDensityReq'] = float(
                    self.densityAnalysisDict['minDensityReq']
                )
            else:
                self.densityAnalysisDict['minDensityReq'] = int(
                    self.densityAnalysisDict['minDensityReq']
                )
            if self.densityAnalysisDict['minDensityReq'] <= 0:
                min_density_positive = "Minimum density requirement must be positive."
                errorList.append(min_density_positive)
                print(f"\n{min_density_positive}")
                self.densityAnalysisDict['minDensityReq'] = None

        except ValueError:
            min_density_number_message = "Minimum density requirement must be a number."
            errorList.append(min_density_number_message)
            print(f"\n{min_density_number_message}")
            self.densityAnalysisDict['minDensityReq'] = None

        # Validate BCGW credentials
        print(
            f" {liqcs_config.dashline()}Testing BCGW credentials..."
        )
        bcgw_connection = density_analysis.density_analysis_config.get_bcgw_connection(
            self.densityAnalysisDict['bcgwCredentials']
        )
        if not bcgw_connection:
            # If bcgw_connection is None, the credentials were invalid.
            # See print statements in density_analysis.config.get_bcgw_connection
            # for messaging to user.
            if sam_testing:
                print(
                    "\nNo connection to BCGW; using pickled water polygons instead."
                    "\n\nDevelopment setting only, available "
                    "if sam_testing in liqcs_gui.py is True."
                    f" {liqcs_config.dashline()}"
                )
                pass
            else:
                errorList.append(
                    f"{density_analysis.density_analysis_config.invalid_bcgw_credentials_message()}"
                )
                self.densityAnalysisDict['bcgwCredentials'] = None
        else:
            # Close the successful BCGW connection;
            # The density analysis script will connect to it again when it needs it.
            density_analysis.density_analysis_config.close_bcgw_connection_credential_check(
                bcgw_connection
            )

        # Validate normalization divisor (if check_correct_units is checked)
        if self.densityAnalysisDict['check_correct_units'] == 1:

            try:
                self.densityAnalysisDict['normalizationDivisor'] = int(
                    self.densityAnalysisDict['normalizationDivisor']
                )
                if self.densityAnalysisDict['normalizationDivisor'] < 0:
                    errorList.append("The raster value divisor must be positive.")
                    print("The raster value divisor must be positive.")
                    self.densityAnalysisDict['normalizationDivisor'] = None

            except ValueError:
                errorList.append("The raster value divisor must be a integer.")
                print("The raster value divisor must be a integer.")
                self.densityAnalysisDict['normalizationDivisor'] = None

        if len(errorList) > 0:
            errorTxt = ""
            for error in errorList:
                errorTxt += f"{error}\n"
                if error != errorList[-1]:
                    errorTxt += liqcs_config.dashline()
            # print(f"Type: {type(errorTxt)}\n{errorTxt=}")

            messagebox.showerror("Density Analysis Input Error", errorTxt)
            density_analysis_user_inputs_valid = False
        else:
            density_analysis_user_inputs_valid = True

        return density_analysis_user_inputs_valid

    def chkb_check(self, var):
        """
        Enables or disables self.divisorEntryPointer in the density_analysis_popup function.

        Args:
            var: Check for incorrect units check button: IntVar.
        """
        if var.get() == 0:
            self.divisorEntryPointer.config(state='disable')
        else:
            self.divisorEntryPointer.config(state='enable')
            current_divisor_value = self.divisorEntryPointer.get()
            if current_divisor_value == "":
                # If there isn't a current normalization divisor
                # when the box to check for correct units
                # and attempt to correct is checked,
                # populate this field with the default value, 25.
                # This input can be manually changed by the user
                # in the GUI entry box.
                self.divisorEntryPointer.delete(0, 'end')
                self.divisorEntryPointer.insert(0, '25')

    def LiDAR_extents_popup(self, siteName, concavity):
        """
        Prompts user for a site name and covcavity of LIDAR extents.
        """
        popup = Toplevel()
        self.open_popup_on_top_of_other_windows(popup)
        popup.resizable(False, False)
        self.set_icon(popup)
        popup.grab_set()
        ttk.Label(
            popup,
            text="Generate LiDAR Extents requirements."
        ).grid(row=0, column=0, padx=5, pady=(5, 0))

        ttk.Label(
            popup,
            text="Site/project name"
        ).grid(row=1, column=0, padx=5, pady=(5, 0))

        site_name_entry = StringVar()
        if siteName is not None:
            site_name_entry.set(siteName)
        ttk.Entry(
            popup,
            textvariable=site_name_entry
        ).grid(row=2, column=0, padx=5, pady=(0, 5))

        ttk.Label(
            popup,
            text="LiDAR boundary concavity"
        ).grid(row=3, column=0, padx=5, pady=(5, 0))

        concavity_entry = StringVar()
        if concavity is not None:
            concavity_entry.set(concavity)
        else:
            concavity_entry.set("20")
        ttk.Entry(
            popup,
            textvariable=concavity_entry
        ).grid(row=4, column=0, padx=5, pady=(0, 5))

        isSubmitClicked = IntVar()
        shapeFileSubmit = ttk.Button(
            popup,
            text="Submit",
            command=lambda: isSubmitClicked.set(1)
        )
        shapeFileSubmit.grid(row=5, column=0, pady=(0, 5))

        popup.wait_variable(isSubmitClicked)
        popup.destroy()
        return site_name_entry.get(), concavity_entry.get()

    def contract_popup(self):
        """
        Prompts user for a contract number.
        """
        popup = Toplevel()
        self.open_popup_on_top_of_other_windows(popup)
        popup.resizable(False, False)
        self.set_icon(popup)
        popup.grab_set()
        ttk.Label(
            popup,
            text="Input Contract Number"
        ).grid(row=0, column=0, padx=5, pady=(5, 0))

        contract = StringVar()
        ttk.Entry(
            popup,
            textvariable=contract
        ).grid(row=1, column=0, padx=5, pady=5)

        isSubmitClicked = IntVar()
        shapeFileSubmit = ttk.Button(
            popup,
            text="Submit",
            command=lambda: isSubmitClicked.set(1)
        )
        shapeFileSubmit.grid(row=5, column=0, pady=(0, 5))

        popup.wait_variable(isSubmitClicked)
        popup.destroy()
        return contract.get()

    def shape_files_popup(self):
        """
        Opens shapefile popup window,
        takes breaklines and AOI shapefile paths
        """
        popup = Toplevel()
        self.open_popup_on_top_of_other_windows(popup)
        popup.resizable(False, False)
        self.set_icon(popup)
        popup.grab_set()
        shp_files = []
        ttk.Label(
            popup,
            text="The void check test requires \nshapefiles for Breaklines and AOI"
        ).grid(row=0, column=0)
        breaklineFrame = ttk.LabelFrame(popup, text='Breaklines path')
        breaklineFrame.grid(row=2, column=0)
        AOIFrame = ttk.LabelFrame(popup, text='AOI path')
        AOIFrame.grid(row=3, column=0)

        breaklines = StringVar()
        ttk.Entry(
            breaklineFrame,
            width=40,
            textvariable=breaklines
        ).grid(row=0, column=0)
        ttk.Button(
            breaklineFrame,
            text="Choose directory",
            command=lambda: self.shape_file_select(breaklines)
        ).grid(row=0, column=1)

        aoi = StringVar()
        ttk.Entry(
            AOIFrame,
            width=40,
            textvariable=aoi
        ).grid(row=0, column=0)
        ttk.Button(
            AOIFrame,
            text="Choose directory",
            command=lambda: self.shape_file_select(aoi)
        ).grid(row=0, column=1)

        isSubmitClicked = IntVar()
        shapeFileSubmit = ttk.Button(
            popup,
            text="Submit",
            command=lambda: isSubmitClicked.set(1)
        )
        shapeFileSubmit.grid(row=4, column=0)

        popup.wait_variable(isSubmitClicked)

        if len(shp_files) > 0:
            del shp_files[:]

        shp_files.insert(0, breaklines.get())
        shp_files.insert(1, aoi.get())
        popup.destroy()
        return shp_files

    def shape_file_select(self, SHP):
        """
        Opens 'select file' windows dialog,
        adds the selected shp file to the relevant entrybox.

        Args:
            SHP (tkinter StrVar object):
        """
        shpInput = filedialog.askopenfilename(
            initialdir="/",
            filetypes=[("Shapefile", "*.shp")]
        )
        SHP.set(shpInput)

    def grid_classes_popup(self):
        
        gridClasses = []
        while not gridClasses:
            popup = Toplevel()
            self.open_popup_on_top_of_other_windows(popup)
            popup.resizable(False, False)
            self.set_icon(popup)
            popup.grab_set()
            ttk.Label(
                popup,
                text="Classes to be used by the Density Grid By Class test:"
            ).grid(row=0, column=0, padx=5, pady=5)
            chkb_frame = ttk.LabelFrame(popup, text='')
            chkb_frame.grid(row=1)

            class_dict = {
                1: "1. Default",
                2: "2. Ground",
                5: "5. High Vegatation",
                7: "7. Outliers",
                9: "9. Water",
                18: "18. High Noise",
                20: "20. Ignored Ground"
            }

            chkbList = [IntVar() for i in range(len(class_dict))]

            # Create checkbuttons for tests
            row_num = 0
            column_num = 0
            for x, y in zip(chkbList, class_dict.values()):
                chkb = ttk.Checkbutton(chkb_frame, text=y, variable=x)
                if row_num >= 4:
                    row_num = 0
                    column_num = column_num + 2
                chkb.grid(row=row_num, column=column_num, sticky='W')
                row_num = row_num + 1

            button_frame = Frame(popup)
            button_frame.grid(row=2)
            is_submit_clicked = IntVar()
            ttk.Button(
                button_frame,
                text="Submit",
                command=lambda: is_submit_clicked.set(1)
            ).grid(pady=5)

            popup.wait_variable(is_submit_clicked)

            for t in range(len(chkbList)):
                if chkbList[t].get() == 1:
                    gridClasses.append(list(class_dict)[t])

            if len(gridClasses) == 0:
                messagebox.showerror(
                    "Input error",
                    "No classes selected! Please select at least one class."
                )

            popup.destroy()

        return gridClasses

    def epsg_popup(self):
        popup = Toplevel()
        self.open_popup_on_top_of_other_windows(popup)
        popup.resizable(False, False)
        self.set_icon(popup)
        popup.grab_set()
        options = list(
            crs_options[0] for crs_options in EpsgCode.EPSG_DICT_CODE_TO_TUPLE_WKT_PROJ.values()
        )
        epsg_codes = list(EpsgCode.EPSG_DICT_CODE_TO_TUPLE_WKT_PROJ.keys())
        ttk.Label(
            popup,
            text="Specified a test that requires defining a CRS"
        ).grid(row=0, column=0)
        ttk.Label(
            popup,
            text="Please select EPSG code: "
        ).grid(row=1, column=0)
        epsg_radio_button = IntVar()
        isButtonClicked = IntVar()
        for i, option in enumerate(options):
            ttk.Radiobutton(
                popup,
                text=option,
                variable=epsg_radio_button,
                value=i
            ).grid(row=i + 2, column=0, sticky='W')
        ttk.Button(
            popup,
            text="Submit",
            command=lambda: isButtonClicked.set(1)
        ).grid(row=i + 3, column=0)
        popup.wait_variable(isButtonClicked)
        popup.destroy()
        return epsg_codes[epsg_radio_button.get()]

    def lidar_qc_prep_popup(self):
        popup = Toplevel()
        self.open_popup_on_top_of_other_windows(popup)
        popup.resizable(False, False)
        self.set_icon(popup)
        popup.grab_set()
        qc_prep_title = "QC Prep Options"
        popup.title(qc_prep_title)

        ttk.Label(popup, text=qc_prep_title).grid(row=0, column=0)

        sampleFrame = Frame(popup)
        sampleFrame.grid(row=1, column=0)
        ttk.Label(sampleFrame, text="lidar sample size %:").grid(row=0, column=0)
        sampleEntry = StringVar(value=10)
        ttk.Entry(sampleFrame, width=2, textvariable=sampleEntry).grid(row=0, column=1)

        isButtonClicked = IntVar()
        ttk.Button(
            popup,
            text="Submit",
            command=lambda: isButtonClicked.set(1)
        ).grid(row=5, column=0)

        popup.wait_variable(isButtonClicked)
        popup.destroy()
        return int(sampleEntry.get())


    def run_tests(self):
        """
        Takes in all inputs, adds test dependencies
        if they were not selected, passes inputs to liqcs.py
        """
        if self.queueDict == {}:
            print(
                f" {liqcs_config.dashline()}No items in queue"
            )
            return
        liqcs_start_time = datetime.now()
        print(
            f" {liqcs_config.rainbow_string (liqcs_config.dashline())}"
            f"LiQCS processing started {self.format_datetime(liqcs_start_time)}\n\n"
            f"LiQCS GUI will be non-responsive during processing.\n"
        )

        # all tests have their output own folder in outputPath if more than one file being returned
        # total_time = time.time()
        totalTestsNum = 0

        for x in range(len(self.queueDict)):
            totalTestsNum += len(self.queueDict[x]['tests'])

        widgets = [
            progressbar.SimpleProgress(),
            ' ', progressbar.Percentage(),
            ' ', progressbar.Bar(),
            ' ', progressbar.Timer()
        ]

        with progressbar.ProgressBar(
            widgets=widgets,
            max_value=len(self.queueDict),
            redirect_stdout=True
        ) as p:
            p.start()

            for i in range(len(self.queueDict)):
                # Define filename and paths for LiQCS queue item summary text file
                # Text file is written in a temporary hidden directory,
                # and will be copied to the final output location with a
                # date-and-time stamp when it is completed.
                # The final path is used by liqcs.py to
                # direct users to that location.
                queue_item_start_time = datetime.now()
                liqcs_summary_file_basename = "LiQCS_Summary"
                liqcs_summary_file_extension = ".txt"
                liqcs_summary_filename = (
                    f"{liqcs_summary_file_basename}{liqcs_summary_file_extension}"
                )
                if IS_LINUX:
                    tmp = tempfile.TemporaryDirectory(dir=self.queueDict[i]['outputPath'])
                    temp_dir = tmp.name
                else:
                    temp_dir = liqcs_config.temp_hidden_dir(self.queueDict[i]['outputPath'])
                liqcs_summary_filepath_write_mode = os.path.join(
                    temp_dir,
                    liqcs_summary_filename
                )
                placeholder_for_timestamp = ".."
                liqcs_summary_file_completed_with_placeholder = os.path.join(
                    self.queueDict[i]['outputPath'],
                    f"{liqcs_summary_file_basename}"
                    f"{placeholder_for_timestamp}"
                    f"{liqcs_summary_file_extension}"
                )
                # Purge output directory of previous LiQCS_Summary...txt files
                for file in os.listdir(self.queueDict[i]['outputPath']):
                    if file.startswith(liqcs_summary_file_basename):
                        previous_summary_file = os.path.join(
                            self.queueDict[i]['outputPath'],
                            file
                        )
                        print(
                            "\nRemoving previous LiQCS Summary file:"
                            f"\n\t{previous_summary_file}\n"
                        )
                        os.remove(previous_summary_file)

                # --------------------------------------------------------------

                with open(
                    liqcs_summary_filepath_write_mode,
                    'w+'
                ) as sum:
                    sum.write(
                        "LiQCS Summary\n\n"
                        f"Queue item start time: {self.format_datetime(queue_item_start_time)}\n"
                        f" {liqcs_config.dashline()}"
                        f"Input directory:\n\n{self.queueDict[i]['inputPath']}\n\n"
                        f"Output directory:\n\n{self.queueDict[i]['outputPath']}\n"
                        f" {liqcs_config.dashline()}"
                        "Tests:\n\n"
                    )
                    for x in self.queueDict[i]['tests']:
                        sum.write(f"- {list(LiqcsTests.TEST_TEXT_LIST)[x - 1]}\n")

                    infileGlob = self.glob_input_files(
                        self.queueDict[i]['inputPath'],
                        self.queueDict[i]['tests'],
                        self.queueDict[i]['sampleSize'],
                        self.queueDict[i]['recurse'],
                        self.queueDict[i]['isFileList'],
                        self.queueDict[i]['isSingleFile'],
                        runTime=True
                    )

                    exceptions = liqcs.run_from_gui(
                        self.queueDict[i]['inputPath'],
                        self.queueDict[i]['outputPath'],
                        infileGlob,
                        self.queueDict[i]['tests'],
                        self.queueDict[i]['cores'],
                        self.queueDict[i]['epsg'],
                        self.queueDict[i]['shapeFiles'],
                        self.queueDict[i]['gridClasses'],
                        self.queueDict[i]['QCPercent'],
                        self.queueDict[i]['siteName'],
                        self.queueDict[i]['contract'],
                        self.queueDict[i]['concavity'],
                        self.queueDict[i]['densityAnalysisDict'],
                        liqcs_summary_file_completed_with_placeholder
                    )

                    # Check lidar files for x/y max/min errors
                    xy_error_report_text = (
                        check_min_max_x_y(self.queueDict[i]['inputPath'])
                    )
                    # If there are lidar files in the input directory,
                    # add the error report text to the LiQCS Summary.
                    # (xy_error_report_text will be None if there are no las/laz
                    # files in the input directory)
                    if xy_error_report_text:
                        sum.write(
                            f" {liqcs_config.dashline()}"
                            f"{xy_error_report_text}"
                        )

                    queue_item_finish_time = datetime.now()
                    queue_item_duration = queue_item_finish_time - queue_item_start_time
                    sum.write(
                        f"\n {liqcs_config.dashline()}"
                        f"Queue item completed: {self.format_datetime(queue_item_finish_time)}"
                        f"\n\nLiQCS queue item runtime: "
                        f"{self.format_datetime_duration(queue_item_duration, 0)}"
                    )

                    if len(exceptions) > 0:
                        sum.write("\n\nExceptions:\n")
                        for exception in exceptions:
                            sum.write(f"{exception}\n\n")

                # --------------------------------------------------------------.

                # Add date-and-time stamp to the LiQCS Summary filename
                # with the completion time.
                datetime_stamp_string = queue_item_finish_time.strftime('%Y-%m-%d_%H%M')
                liqcs_summary_file_completed = (
                    liqcs_summary_file_completed_with_placeholder.replace(
                        placeholder_for_timestamp, ""
                    )
                )
                liqcs_summary_file_completed = (
                    f"{os.path.splitext(liqcs_summary_file_completed)[0]}"   # 'path/LiQCS_Summary'
                    f"_{datetime_stamp_string}"
                    f"{os.path.splitext(liqcs_summary_file_completed)[1]}"  # '.txt'
                )

                # Copy the LiQCS Summary file out of the temporary hidden directory
                # into the main output directory
                shutil.copyfile(
                    liqcs_summary_filepath_write_mode,
                    liqcs_summary_file_completed
                )

                # Delete the temporary hidden directory with the redundant LiQCS summary file
                if IS_LINUX:
                    tmp.cleanup()
                else:
                    shutil.rmtree(temp_dir)

                # --------------------------------------------------------------

                p.update(i + 1, force=True)

                print(f"Queue item {i + 1} of {len(self.queueDict)} complete.")

                # Open the queue item output directory
                # wb.open(self.queueDict[i]['outputPath'])

        liqcs_finish_time = datetime.now()
        liqcs_runtime = liqcs_finish_time - liqcs_start_time

        print(
            f" {liqcs_config.rainbow_string (liqcs_config.dashline())}"
            f"LiQCS processing complete {self.format_datetime(liqcs_finish_time)}."
            f"\n\nLiQCS processing duration: {self.format_datetime_duration(liqcs_runtime, 1)}"
            f"\n\nTo run more LiQCS tests, add more items to the queue "
            "in the GUI and click the "
            f" {liqcs_config.AnsiColors.cyan}"
            f"{_process_queue_button_text()} {liqcs_config.AnsiColors.reset} button."
            f"\n\nTo quit LiQCS, close this terminal window, "
            f"or click the  {liqcs_config.AnsiColors.magenta}{_quit_button_text()}"
            f" {liqcs_config.AnsiColors.reset} button in the GUI."
        )

        self.clear_queue()
    

class ScrollingFrame(Frame):
    def __init__(self, parentObject):
        ttk.LabelFrame.__init__(self, parentObject, text="Queue")
        self.canvas = Canvas(self)
        self.frame = Frame(self.canvas)
        self.grid(sticky=E + W)

        self.vsb = Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.grid(row=0, column=1, sticky=N + S + E)

        self.canvas.grid(row=0, column=0, sticky=N + S + E + W)
        self.window = self.canvas.create_window(
            0,
            0,
            window=self.frame,
            anchor="nw",
            tags="self.frame"
        )

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

    def on_frame_configure(self, event):
        # Reset the scroll region to encompass the inner frame
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        # Resize the inner frame to match the canvas
        minHeight = self.frame.winfo_reqheight()

        if self.winfo_height() >= minHeight:
            newHeight = self.winfo_height()
            # Hide the scrollbar when not needed
            self.vsb.grid_remove()
        else:
            newHeight = minHeight
            # Show the scrollbar when needed
            self.vsb.grid()

        self.canvas.itemconfig(self.window, height=newHeight)


class CreateToolTip(object):
    """
    Create a tooltip for a given widget.
    """
    def __init__(self, widget, text='Widget info'):
        self.waittime = 500     #miliseconds
        self.wraplength = 180   #pixels
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None
    
    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)
    
    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = ttk.Label(self.tw, text=self.text, justify='left',
                       background="#ffffff", relief='solid', borderwidth=1,
                       wraplength = self.wraplength)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw= None
        if tw:
            tw.destroy()

def main():
    fix_ansi_colours_for_colourful_text_in_terminal()
    gui = LiQCS_GUI()
    gui.root.mainloop()


if __name__ == '__main__':
    freeze_support()
    main()
