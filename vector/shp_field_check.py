from osgeo import ogr
from tkinter import filedialog
import os
import re
from pathlib import Path
import vector.shapefile_dictionaries as shapefile_dictionaries

"""
Checks field name and field type in shapefiles and generates a .txt report
within a 'Shapefile_Report' folder, with any fields that are:
1. Missing Fields
2. Unnecessary Fields (extra fields)
3. Incorrect Field Types

IMPORTANT INFO

- This script finds files recursively from the input directory, therefore the input directory
need only be at the top of the folder structure where your files you wish to check are located.

- This script currently only looks for the following shapefiles:

- Ground Control
- Swath Polygons
- lidar Coverage
- Photo Centre Index
- Tree Height

This is because at this time we only have specifications for these shapefile deliverables.

- The results for Swath Polygons are merged to output one .txt file

- The results called 'Swath_Report.txt' is the result of looking at both swath polygons and raw
swath lidar files and reporting if there are any discrepencies (every swath polygon should have
corresponding raw swath lidar file).

*** INSTRUCTIONS ON HOW TO ADD ANOTHER SHAPEFILE TYPE TO THIS TEST ***

1. Add a complete/correct dictionary of both field name and field type to 'shapefile_dictionaries.py'
based on the most currect specification we have.
This script contains the correct dictionaries used to compare the found shapefile field names and values.

2. Add an aditional regular expression to find the new shapefile being added to 'regex_list'.
Going forward, you will need to add the new lines in the same order that they occur in other
lists. For example, Ground Control is the first element in every list. When a ground control
shapefile is found, this program looks at the first element in all the appropriate lists for
specific information.

3. Create a variable called "[shapefile type name]_fields and have it equal to
'shapefile_dictionaries.[variable name given in shapefile_dictionaries]. This will
call that specific dictionary from that script and assign it to the variable given.

4. Add the dictionary variable you just created in step 3 'field_lists' (this is a list of dictioaries)

5. Add an empty dictionary called '[shapefile type]_field_list' to the other empty field dictionaries.

6. In the 'found_fields' list add the dictionary variable you created in step 5.

7. Add shapefile type string to the list 'text_names' based on the naming conventions of the previous names.

8. Add the following to the main script where:
- the 'regex_list' value is the index number of the regex string to be used
- the 'shapefile' variable should be the same value as the 'regex_list' value already given

e.g.
    # [Shapefile Name] Shapefile
            elif re.match(regex_list[#], file):
                shapefile = #
                run_script(root, file, shapefile)

"""

def run_from_gui(inDir,outDir):
        

    ################ CREATE LISTS ################


    # regular expressions
    regex_list = [
    r'^.*(Ground_Control|ground_control).*\.shp$', # Ground Control [0]
    r'^.*_\d{3}_\d{4}_.*\.shp$', # Swath Polygons [1]
    r'^.*_LiDAR.*\.shp$', # Final lidar Coverage [2]
    r'^.*_Photo_Centre_Index\.shp$', # Photo Centre Index [3]
    r'^.*(Tree_Height|tree_height).\.shp$', # Tree Height [3]
    ]
    
    # regular expression for swath report
    strip_regex = r'^\d{1,6}_\d{3}_\d{4}_.*\.laz$'
    swath_regex = r'^\d{1,6}_\d{3}_\d{4}_.*\.shp$'

    # correct dictionary of field names (key) and field types (value) for a given shapefile grabbed from 'shapefile_dictionaries.py'
    control_fields = shapefile_dictionaries.control_fields

    swath_fields = shapefile_dictionaries.swath_fields

    final_coverage_fields = shapefile_dictionaries.final_coverage_fields

    photo_centre_fields = shapefile_dictionaries.photo_centre_fields

    tree_heights_fields = shapefile_dictionaries.tree_height_fields
    
    # list of field name/field type dictionaries
    field_lists = [

    control_fields, # [0]
    swath_fields, # [1]
    final_coverage_fields, # [2]
    photo_centre_fields, # [3]
    tree_heights_fields # [4]
    ]

    # create empty field dictionaries (for appending found field names and field types in shapefiles)
    control_field_list = {}
    swath_field_list = {}
    final_coverage_field_list = {}
    photo_centre_field_list = {}
    tree_heights_field_list = {}

    # empty found fields list of dictionaries
    found_fields = [

    control_field_list, # [0]
    swath_field_list, # [1]
    final_coverage_field_list, # [2]
    photo_centre_field_list, # [3]
    tree_heights_field_list # [4]
    ]

    # empty lists/dictionaries/counters for swath polygons
    swath_missing_fields = []
    swath_missing_fields_count = 0
    swath_unnecessary_fields = []
    swath_unnecessary_fields_count = 0
    swath_incorrect_type = {}
    swath_incorrect_type_count = 0
    swath_found_fields = []
    swath_polygon_count = 0

    # empty lists for swath report
    strip_list = []
    swath_list = []

    # list of names for naming files
    text_names = [
    'Control_',
    'Swath_Polygons_',
    'Final_Coverage_',
    'Photo_Centre_',
    'Tree_Heights_'
    ]


    ################ CREATE FUNCTIONS ################

    def create_field_list(root, file, found_fields):
        """
        Summary:
            This function clears the found_fields list in order to avoid mixing fields found
            by this script. Using OGR, both the field name and field type are extracted from
            the shapefile given as an argument. Both field name and field type are then placed
            in the corresponding found_field dictionary as a Key:Value pair.

        Args:
            root (string): path to shapfile directory (from os.walk())
            file (string): file element in list of files (from os.walk())
            found_fields (dictionary): the dictionary used to save found field name/types based
            on the 'Shapefile' integer used in the main script


        Returns:
            found_fields (dictionary): Key(field_name):Value(field_type) pairs from shapefile
            file_name (string): filename of shapefile
        """
        found_fields.clear()
        f = os.path.join(root, file)
        file_name = Path(f).stem
        dataSource = ogr.Open(f)
        daLayer = dataSource.GetLayer(0)
        layerDefinition = daLayer.GetLayerDefn()
        for i in range(layerDefinition.GetFieldCount()):
            field_name =  layerDefinition.GetFieldDefn(i).GetName()
            fieldTypeCode = layerDefinition.GetFieldDefn(i).GetType()
            fieldType = layerDefinition.GetFieldDefn(i).GetFieldTypeName(fieldTypeCode)
            found_fields.update({field_name:fieldType})
        return found_fields, file_name
    
    # find both missing, unnecessary fields, and incorrect types
    def field_differences(found_fields, field_lists):
        """
        Summary:
            Compares the found_fields dictionary with the corresponding field_lists dictionary
            to find missing fields, unecessary fields, and incorrect field types

        Args:
            found_fields (dictionary): field name and type of shapefile
            field_lists (dictionary): correct field name and type based on specs

        Returns:
            missing_fields (list) : list of missing fields
            missing_field_count (integer) : number of fields missing
            unnecessary_fields (list) : list of unecessary_fields
            unnecessary_field_count (integer) : number of unecessary fields
            type_incorrect (dictionary) : dictionary of field names/types
                                        where the type is incorrect
            incorrect_type_count (integer) : number of incorrect field types
        """
        # create emtpy lists for missing fields and unecessary fields
        missing_fields = []
        unnecessary_fields = []

        #find missing fields
        missing = { k : field_lists[k] for k in set(field_lists) - set(found_fields) }
        for key, value in missing.items():
            missing_fields.append(key)
        missing_field_count = len(missing_fields)

        #find unnecessary fields
        unnecessary = { k : found_fields[k] for k in set(found_fields) - set(field_lists) }
        for key, value in unnecessary.items():
            unnecessary_fields.append(key)
        unnecessary_field_count = len(unnecessary_fields)

        #find incorrect field types among correct fields
        
        good_list = []
        good_dict = {}
        type_incorrect = {}

        #replace different integer types with "Integer" to avoid invalid errors *** CAN BE REMOVED ONCE WE HAVE SPECS FOR INTEGER TYPE ***
        for (key,value) in set(found_fields.items()):
            if key == "PRF":
                if value == "Integer32" or "Integer64":
                    found_fields['PRF'] = "Integer"
            elif key == "density":
                if value == "Integer32" or "Integer64":
                    found_fields['density'] = "Integer"
            elif key == "acq_year":
                if value == "Integer32" or "Integer64":
                    found_fields['acq_year'] = "Integer"
            

        for (key) in set(found_fields.keys()):
            if (key) in set(field_lists.keys()):
                good_list.append(key)

        filtered_dict = {k: field_lists[k] for k in good_list if k in field_lists}

        for (key,value) in set(found_fields.items()):
            if (key,value) in set(field_lists.items()):
                good_dict.update({key:value})

        for (key,value) in set(filtered_dict.items()):
            if (key,value) not in set(good_dict.items()):
                type_incorrect.update({key:value})
        incorrect_type_count = len(type_incorrect)
        
        return missing_fields, missing_field_count, unnecessary_fields, unnecessary_field_count, type_incorrect, incorrect_type_count

    # write a report that states all fields were correct
    def no_issues_report(unnecessary_field_count, missing_field_count, incorrect_type_count, file_name):
        if unnecessary_field_count == 0 and missing_field_count and incorrect_type_count == 0:
                with open(report_folder + f"/{file_name}_{text_names[shapefile]}Shapefile_Report.txt", "a") as shapefile_report:
                    shapefile_report.write(f"All Shapefile Fields/Types in {file_name}.shp are CORRECT")

    # append all missing fields to report.txt file
    def create_missing_field_report(missing_field_count, file_name, missing_fields):
        if missing_field_count == 0:
            with open(report_folder + f"/{file_name}_{text_names[shapefile]}Shapefile_Report.txt", "a") as shapefile_report:
                    shapefile_report.write(f"\n\n")
                    shapefile_report.write(f"------------------\n")
                    shapefile_report.write(f'  MISSING FIELDS  \n')
                    shapefile_report.write(f'------------------\n\n')
                    shapefile_report.write(f'   None')
        if missing_field_count >0:
                with open(report_folder + f"/{file_name}_{text_names[shapefile]}Shapefile_Report.txt", "a") as shapefile_report:
                    shapefile_report.write(f"\n\n")
                    shapefile_report.write(f"------------------\n")
                    shapefile_report.write(f'  MISSING FIELDS  \n')
                    shapefile_report.write(f'------------------\n\n')
                    for e in missing_fields:
                        shapefile_report.write(f'   {e}\n')

    # append all unnecessary fields to report.txt file
    def create_unnecessary_field_report(unnecessary_field_count, file_name, unnecessary_fields):
        if unnecessary_field_count == 0:
            with open(report_folder + f"/{file_name}_{text_names[shapefile]}Shapefile_Report.txt", "a") as shapefile_report:
                shapefile_report.write(f"\n\n")
                shapefile_report.write(f"----------------------\n\n")
                shapefile_report.write(f'  UNNECESSARY FIELDS \n\n')
                shapefile_report.write(f"----------------------\n\n")
                shapefile_report.write(f'   None')
        if unnecessary_field_count >0:
                with open(report_folder + f"/{file_name}_{text_names[shapefile]}Shapefile_Report.txt", "a") as shapefile_report:
                    shapefile_report.write(f"\n\n")
                    shapefile_report.write(f"----------------------\n\n")
                    shapefile_report.write(f'  UNNECESSARY FIELDS  \n\n')
                    shapefile_report.write(f"----------------------\n\n")
                    for e in unnecessary_fields:
                        shapefile_report.write(f'   {e}\n')

    # append all incorrect fields with inccorect field types
    def create_field_type_report(type_incorrect, incorrect_type_count, file_name):
        if incorrect_type_count == 0:
            with open(report_folder + f"/{file_name}_{text_names[shapefile]}Shapefile_Report.txt", "a") as shapefile_report:
                shapefile_report.write(f"\n\n")
                shapefile_report.write(f"-------------------------\n\n")
                shapefile_report.write(f'  INCORRECT FIELD TYPES  \n\n')
                shapefile_report.write(f"-------------------------\n\n")
                shapefile_report.write(f'   None')
        if incorrect_type_count >0:
            with open(report_folder + f"/{file_name}_{text_names[shapefile]}Shapefile_Report.txt", "a") as shapefile_report:
                shapefile_report.write(f"\n\n")
                shapefile_report.write(f"-----------------------------------------------------------------------------------------------------------------\n\n")
                shapefile_report.write(f"  INCORRECT FIELD TYPES ('Field', 'Type') << The listed type below is what the type should be for that field >>\n\n")
                shapefile_report.write(f"-----------------------------------------------------------------------------------------------------------------\n\n")
                for key, value in type_incorrect.items():
                    shapefile_report.write(f'   {key, value}\n')

    # append all found fields/types
    def create_found_field_report(found_field_list, file_name):
        with open(report_folder + f"/{file_name}_{text_names[shapefile]}Shapefile_Report.txt", "a") as shapefile_report:
            shapefile_report.write(f"------------------------\n\n")
            shapefile_report.write(f"  ALL FOUND FIELD/TYPE  \n\n")
            shapefile_report.write(f"------------------------\n\n")
            for key, value in found_field_list.items():
                shapefile_report.write(f'{key, value}\n')
            
    # runs all main functions on a chosen shapefile    
    def run_script(root, file, shapefile):
        found_field_list, file_name = create_field_list(root, file, found_fields[shapefile])
        missing_fields, missing_field_count, unnecessary_fields, unnecessary_field_count, type_incorrect, incorrect_type_count = field_differences(found_field_list, field_lists[shapefile])
        no_issues_report(unnecessary_field_count, missing_field_count, incorrect_type_count, file_name)
        create_found_field_report(found_field_list, file_name)
        create_unnecessary_field_report(unnecessary_field_count, file_name, unnecessary_fields)
        create_missing_field_report(missing_field_count, file_name, missing_fields)
        create_field_type_report(type_incorrect, incorrect_type_count, file_name)
        


    ################ MAIN SCRIPT ################

    # create output folder if none existant and delete previously created reports
    report_folder = (outDir + r'/Shapefile_Reports')
    if not os.path.exists(report_folder):
        os.makedirs(report_folder)

    # walk through input directory and run functions
    for root, subFolder, files in (os.walk(inDir)):
        for file in files:
            # Append list of all lidar strip files found in directory
            if re.search(strip_regex, file):
                    f = Path(file).name
                    f_name = f.split('.')
                    f_name_start = f_name[0]
                    strip_list.append (f_name_start)

            # Append list of all Swath Polygons found in directory
            if re.search(swath_regex, file):
                    f = Path(file).name
                    f_name = f.split('.')
                    f_name_start = f_name[0]
                    swath_list.append (f_name_start)

            # Control Shapefile
            if re.match(regex_list[0], file):
                shapefile = 0
                run_script(root, file, shapefile)

            # Swath Polygon Shapefile
            elif re.match(regex_list[1], file):
                shapefile = 1
                swath_polygon_count += 1
                found_field_list, file_name = create_field_list(root, file, found_fields[shapefile])
                s_missing_fields, s_missing_field_count, s_unnecessary_fields, s_unnecessary_field_count, s_type_incorrect, s_incorrect_type_count = field_differences(found_field_list, field_lists[shapefile])
                
                for (key,value) in (found_fields[shapefile].items()):
                    (swath_found_fields).append({key:value})

                for e in (s_missing_fields):
                    swath_missing_fields.append(e)

                for e in (s_unnecessary_fields):
                    swath_unnecessary_fields.append(e)

                for (key,value) in set(s_type_incorrect.items()): 
                    swath_incorrect_type.update({key:value})

                swath_unnecessary_fields_count+=(s_unnecessary_field_count)
                swath_missing_fields_count+=(s_missing_field_count)
                swath_incorrect_type_count+=(s_incorrect_type_count)
                

            # Final Coverage Shapefile
            elif re.match(regex_list[2], file):
                shapefile = 2
                run_script(root, file, shapefile)

            # Photo Centre Index Shapefile
            elif re.match(regex_list[3], file):
                shapefile = 3
                run_script(root, file, shapefile)

            # Tree Heights Shapefile
            elif re.match(regex_list[4], file):
                shapefile = 4
                run_script(root, file, shapefile)
            
            else:
                continue

    ######## TO MERGE SWATH POLYGON RESULTS #########
    # remove duplicates in swath lists
    if swath_polygon_count >0:
        final_swath_found_fields = [dict(t) for t in {tuple(d.items()) for d in swath_found_fields}]
        if swath_missing_fields_count >0:
            final_swath_missing_fields = list(dict.fromkeys(swath_missing_fields))

        if swath_unnecessary_fields_count >0:
            final_swath_unnecessary_fields = list(dict.fromkeys(swath_unnecessary_fields))

        # write all found field/type
        with open(report_folder + f"/Swath_Polygons_Shapefile_Report.txt", "a") as shapefile_report:
                        shapefile_report.write(f"*** PLEASE NOTE ***\n\nThese results reflect all Swath Polygon shapefiles found\n\n")
                        shapefile_report.write(f"------------------------\n\n")
                        shapefile_report.write(f"  ALL FOUND FIELD/TYPE  \n\n")
                        shapefile_report.write(f"------------------------\n\n")
                        for e in (final_swath_found_fields):
                            shapefile_report.write(f'   {e}\n')

        # write all unnecessary fields
        if swath_unnecessary_fields_count == 0:
            with open(report_folder + f"/Swath_Polygons_Shapefile_Report.txt", "a") as shapefile_report:
                shapefile_report.write(f"\n\n")
                shapefile_report.write(f"----------------------\n\n")
                shapefile_report.write(f'  UNNECESSARY FIELDS  \n\n')
                shapefile_report.write(f"----------------------\n\n")
                shapefile_report.write(f'   None')
        if swath_unnecessary_fields_count >0:
                with open(report_folder + f"/Swath_Polygons_Shapefile_Report.txt", "a") as shapefile_report:
                    shapefile_report.write(f"\n\n")
                    shapefile_report.write(f"----------------------\n\n")
                    shapefile_report.write(f'  UNNECESSARY FIELDS  \n\n')
                    shapefile_report.write(f"----------------------\n\n")
                    for e in final_swath_unnecessary_fields:
                        shapefile_report.write(f'   {e}\n')
        
        # write all missing fields
        if swath_missing_fields_count == 0:
                with open(report_folder + f"/Swath_Polygons_Shapefile_Report.txt", "a") as shapefile_report:
                        shapefile_report.write(f"\n\n")
                        shapefile_report.write(f"------------------\n\n")
                        shapefile_report.write(f'  MISSING FIELDS  \n\n')
                        shapefile_report.write(f"------------------\n\n")
                        shapefile_report.write(f'   None')
        if swath_missing_fields_count >0:
                with open(report_folder + f"/Swath_Polygons_Shapefile_Report.txt", "a") as shapefile_report:
                    shapefile_report.write(f"\n\n")
                    shapefile_report.write(f"------------------\n\n")
                    shapefile_report.write(f'  MISSING FIELDS  \n\n')
                    shapefile_report.write(f"------------------\n\n")
                    for e in final_swath_missing_fields:
                        shapefile_report.write(f'   {e}\n')

        # write all incorrect field types
        if swath_incorrect_type_count == 0:
                with open(report_folder + f"/Swath_Polygons_Shapefile_Report.txt", "a") as shapefile_report:
                    shapefile_report.write(f"\n\n")
                    shapefile_report.write(f"-------------------------\n\n")
                    shapefile_report.write(f'  INCORRECT FIELD TYPES  \n\n')
                    shapefile_report.write(f"-------------------------\n\n")
                    shapefile_report.write(f'   None')
        if swath_incorrect_type_count >0:
            with open(report_folder + f"/Swath_Polygons_Shapefile_Report.txt", "a") as shapefile_report:
                shapefile_report.write(f"\n\n")
                shapefile_report.write(f"-----------------------------------------------------------------------------------------------------------------\n\n")
                shapefile_report.write(f"  INCORRECT FIELD TYPES ('Field', 'Type') << The listed type below is what the type should be for that field >>  \n\n")
                shapefile_report.write(f"-----------------------------------------------------------------------------------------------------------------\n\n")
                for key, value in swath_incorrect_type.items():
                    shapefile_report.write(f'   {key, value}\n')

    ####### Swath Polygon comparison with raw lidar Swath and create report ########
    set_dif = set(strip_list).symmetric_difference(set(swath_list))

    difference = list(set_dif)

    list_length = len(difference)

    if list_length >0:
        with open(report_folder + f"/Swath_Report.txt", "a") as swath_report:
            swath_report.write(f'-----------------------------\n')
            swath_report.write(f'------- SWATH REPORT --------\n')
            swath_report.write(f'-----------------------------\n\n')
            swath_report.write(f'The following do not have a partner file\n\n')
            for e in difference:
                swath_report.write(f'   {e}\n')
    elif len(strip_list) or len(swath_list) == 0: 
        with open(report_folder + f"/Swath_Report.txt", "a") as swath_report:
            swath_report.write(f'-----------------------------\n')
            swath_report.write(f'------- SWATH REPORT --------\n')
            swath_report.write(f'-----------------------------\n\n')
            swath_report.write(f'Either no swath polygons or raw lidar swath files were found in directory.')
    else:
        with open(report_folder + f"/Swath_Report.txt", "a") as swath_report:
            swath_report.write(f'-----------------------------\n')
            swath_report.write(f'------- SWATH REPORT --------\n')
            swath_report.write(f'-----------------------------\n\n')
            swath_report.write(f'Every swath polygon has a corresponding raw lidar swath file. HURRAY!!.')

        

def main():
    inDir = filedialog.askdirectory(title="Select input directory")
    outDir = filedialog.askdirectory(title="Select output directory")
    run_from_gui(inDir, outDir)
    print (f"\n\n Shapefile Check COMPLETE \n\n ")

if __name__ == '__main__':
    main()