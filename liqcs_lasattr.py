
# ------------------------------------------------------------------------------
# Author: Natalie Jackson
# ------------------------------------------------------------------------------
# Description:
#
#    A LasAttr object instance stores all non-point-data from
#    a las 1.4 or laz 1.4 file as attributes
#    (instance variables of the LasAttr object instance).
#
#    These attributes include:
#        - public header elements,
#        - vlr header elements,
#        - vlr contents (vlr payloads),
#        - evlr header elements,
#        - evlr contents (evlr payloads)
#
#    LasAttr attributes can updated, and they can be used to
#    write a new las/laz file with new values.
#
#    In other words, everything except point data (las payload)
#    can be modified.
#
#   This module contains an if __name__ == "__main__" clause
#   to check global variable names meet criteria for code logic.
#
# ------------------------------------------------------------------------------
# Limitiations:
#
# - GUID interpretation
#       There are 4 GUID attributes in a las/laz file; this module
#       interprets them as integers, which is fine and dandy, but those
#       integers need to be further decoded (using ascii code lookup, etc)
#       and combined in the correct order to find the GUID they represent.
#       If the user does not edit the GUID attribute values, they will
#       be re-written in the new file in the same way they appeared in
#       the original file. (No harm done).
#
# - Editing non-character VLR/EVLR payloads
#       This code interprets all VLR and EVLR payloads as character data.
#       If the payload really is character data, this script can edit that
#       data, and re-write it. But, if the payload isn't character data,
#       this script is only capabale of re-writing the data as-is, or
#       deleting it entirely. This script does not currently interpret
#       non-character VLR/EVLR payloads for easy analysis or editing.
#
# - Las version limited to las/laz 1.4
#       Some features may work with other las/laz versions, but this
#       script is neither designed for nor tested with other
#       las/laz versions. Files of different versions should be examined
#       closely for data errors if written by this code.
#
# - This code ASSUMES there is no padding at the beginning of the input
#       las/laz file; i.e., it assumes the first byte in the file is the
#       first byte of the header. Lastools las2las has an option
#       tag called -remove_padding that removes extra bytes before and after
#       the header. For now, this file removes extra bytes after the
#       header whenever a VLR value is changed. But it wouldn't know what
#       hit it if a file came in with padding at the beginning of the file.
#
# - remove_evlr() method does not currently support files that have waveform
#       data. See remove_evlr method for more information.
#
# ------------------------------------------------------------------------------
# Requirements:
#
# Python 3.7+ (version of Python where dictionaries are ordered).
# Created using Python 3.8.6.
#
# ------------------------------------------------------------------------------
# TODO:
#
# Priority A:
#   - TBD
#
# Priority B:
#   - Consolidate duplication between VLR/EVLR functions. (Use prefix as a parameter)
#   - Update remove_evlr() method to be able to cope with files that have
#       waveform data. (Update start_waveform_data attribute appropriately).
#   - Make it possible to read files that have padding before the public header
#       (and remove that padding, like lastools las2las -remove_padding option)
#   - Similarly, make this script not automatically overwrite any padding bytes
#       between the end of the VLRs and the beginning of point data
#   - Add functionality for other las/laz versions (see Limitations above)
#       e.g., try the log_attr function on a las 1.2 file -- because the public
#           header is shorter for las 1.2, LasAttr misinterprets data that it thinks
#           part of the public header, but really belongs to VLRs or point data.
#
# Priority C:
#   - Interpret GUIDs (see Limitations above)
#       - note that guid4 takes unsigned chars (must be 0-255), decoded using
#           the standard ASCII 255 codes (e.g., https://theasciicode.com.ar/)
#       - the values may be unpacking in the incorrect order from struct--
#           see https://docs.python.org/3/library/struct.html#byte-order-size-and-alignment
#           for more about the read/write order of struct bytes
#   - Interpret non-character VLR/EVLR payloads (see Limitations above)
#   - How does struct fit a 8-byte long long into a 4 byte int, and similar
#       size mismatches? Read more at:
#       https://docs.python.org/3/library/struct.html#byte-order-size-and-alignment
#   - Protect _original_offset_to_point_data from being updated externally
#       - There are a number of attributes that should not be updated
#           because they will affect how the file is read by software;
#           protecting these attributes is mostly beyond the scope of this
#           library.
#   - Add LasAttr attributes to an excel file so values can be compared between files
#       (or just a pandas object, or whatever might be best)
#
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# IMPORTS
# ------------------------------------------------------------------------------

from datetime import datetime
import pyproj
import shutil
import struct
import sys
import os


# ------------------------------------------------------------------------------
# NAME OF THIS SOFTWARE TO BE ADDED TO RE-WRITTEN LAS/LAZ FILES
# "GENERATING SOFTWARE" VALUE (32 CHARACTER MAX)
# ------------------------------------------------------------------------------

lasattr_software_name = "LasAttr Beta, GeoBC"


# ------------------------------------------------------------------------------
# FORMATTING VARIABLES
# ------------------------------------------------------------------------------

_dashline = "-" * 80


# ------------------------------------------------------------------------------
# CHECK PYTHON VERSION
# ------------------------------------------------------------------------------

def python_version_check():
    """
    Ensure Python version is 3.7+.

    In earlier versions, dictionaries are not ordered objects.
    This module relies on dictionaries being ordered.
    """
    python_version_info = sys.version_info
    python_version_min = 3.7

    if python_version_info <= (3, 7):
        sys.exit(
            f"\n{_dashline}"
            f"\n{lasattr_software_name} requires Python "
            f"version {python_version_min} or greater."
            f"\nActive environment Python version: "
            f"{python_version_info.major}.{python_version_info.minor}.{python_version_info.micro}"
            f"\n{_dashline}"
        )


python_version_check()

# ------------------------------------------------------------------------------
# ATTRIBUTES INITIALIZED GLOBAL VARIABLE
# - re-sets to false when a LasAttr object instance is initialized
#   (at the beginning of LasAttr.__init__)
# - switches to True at the end of LasAttr initialization
#   (at the end of LasAttr.__init__)
# - Used by functions/methods in cases where logic is different
#   depending on whether the attributes have already been initialized,
#   or if they are modifications from the original values.
# ------------------------------------------------------------------------------

_attributes_initialized = False

# ------------------------------------------------------------------------------
# ATTRIBUTE PREFIXES
# Note: attribute prefixes are used in class logic;
# alter with caution (i.e., don't alter).
# ------------------------------------------------------------------------------

# Prefix for all vlr attributes
_vlr_attr_prefix = "vlr"

# Prefix for all evlr attributes
_evlr_attr_prefix = "evlr"

# Separates indexed vlr/evlr attribute prefix from base key name
# Used in __setattr__() logic
_split_character = "_"

# VLR/EVLR value attribute root name
_value_attr_root = "value"


# ------------------------------------------------------------------------------
# FORMAT CODES FOR STRUCT MODULE ASSIGNED TO PYTHON VARIABLES FOR
# INCREASED CODE COMPREHENSIBILITY AND TYPO-RISK-REDUCTION
# ------------------------------------------------------------------------------

# Relevant format codes for struct module saved as python variables
# https://docs.python.org/3/library/struct.html#format-characters
# suffix is the standard number of bytes for a single unit of that format
# (1B is 1 byte, 2B is 2 bytes, etc.), for information only
_char_more_bytes = "s"
_unsigned_char_1B = "B"
_unsigned_short_2B = "H"
_unsigned_long_4B = "L"
_unsigned_long_long_8B = "Q"
_double_8B = "d"


# ------------------------------------------------------------------------------
# FORMAT CODE DICTIONARY FOR CHECKING DATA TYPES WHEN UDPATING ATTRIBUTES
# ------------------------------------------------------------------------------

# These dictionary key value pairs use the python data types
# as described by the struct module:
# https://docs.python.org/3/library/struct.html#format-characters

format_dict = {
    _char_more_bytes: str,
    _unsigned_char_1B: int,
    _unsigned_short_2B: int,
    _unsigned_long_4B: int,
    _unsigned_long_long_8B: int,
    _double_8B: float,
}


# ------------------------------------------------------------------------------
# LASATTR ATTRIBUTE DICTIONARIES (GLOBAL VARIABLES)
# ------------------------------------------------------------------------------
# public_header_dict, vlr_header_dict, and evlr_header_dict each comprise of
# elements of LAS 1.4 headers.
# (see https://www.asprs.org/wp-content/uploads/2010/12/LAS_1_4_r13.pdf)
# Dictionary keys:
#   Class object attribute label (string, python-variable-name-friendly)
# Dictionary values (tuples):
#   0: item (string),
#   1: total number of bytes to read for item (integer),
#   2: data format (string),
#   3: number of data format units comprising item,
#       e.g., if there are 8 unsigned char bytes dedicated to this attribute
#
# other_attributes_dict contains other attributes that initialize
# when a LasAttr object is created.
# ------------------------------------------------------------------------------

public_header_dict = {
    "file_signature": ("File Signature (LASF)", 4, f"4{_char_more_bytes}", 1),  # 0
    "file_source_id": ("File Source ID", 2, _unsigned_short_2B, 1),  # 1
    "global_encoding": ("Global Encoding", 2, _unsigned_short_2B, 1),  # 2
    "guid1": ("GUID1", 4, _unsigned_long_4B, 1),  # 3
    "guid2": ("GUID2", 2, _unsigned_short_2B, 1),  # 4
    "guid3": ("GUID3", 2, _unsigned_short_2B, 1),  # 5
    "guid4": ("GUID4", 8, _unsigned_char_1B, 8),  # 6
    "version_major": ("Version Major", 1, _unsigned_char_1B, 1),  # 7
    "version_minor": ("Version Minor", 1, _unsigned_char_1B, 1),  # 8
    "system_id": ("System ID", 32, f"32{_char_more_bytes}", 1),  # 9
    "generating_software": (
        "Generating Software",
        32,
        f"32{_char_more_bytes}",
        1
    ),  # 10
    "file_creation_day_of_year": (
        "File Creation Day of Year",
        2,
        _unsigned_short_2B,
        1
    ),  # 11
    "file_creation_year": ("File Creation Year", 2, _unsigned_short_2B, 1),  # 12
    "header_size": (
        "Header Size",
        2,
        _unsigned_short_2B,
        1
    ),  # 13 - 375 bytes for las 1.4
    "offset_to_point_data": ("Offset to point data", 4, _unsigned_long_4B, 1),  # 14
    "number_of_vlrs": ("Number of VLRs", 4, _unsigned_long_4B, 1),  # 15
    "pdrf": ("Point Data Record Format", 1, _unsigned_char_1B, 1),  # 16
    "point_record_length": ("Point Record Length", 2, _unsigned_short_2B, 1),  # 17
    "legacy_num_point_records": (
        "Legacy Number of point records",
        4,
        _unsigned_long_4B,
        1
    ),  # 18
    "legacy_num_points_by_return": (
        "Legacy Number of points by return",
        20,
        _unsigned_long_4B,
        5
    ),  # 19
    "x_scale": ("X scale Factor", 8, _double_8B, 1),  # 20
    "y_scale": ("Y scale Factor", 8, _double_8B, 1),  # 21
    "z_scale": ("Z scale Factor", 8, _double_8B, 1),  # 22
    "x_offset": ("X offset", 8, _double_8B, 1),  # 23
    "y_offset": ("Y offset", 8, _double_8B, 1),  # 24
    "z_offset": ("Z offset", 8, _double_8B, 1),  # 25
    "x_max": ("Max X", 8, _double_8B, 1),  # 26
    "x_min": ("Min X", 8, _double_8B, 1),  # 27
    "y_max": ("Y Max", 8, _double_8B, 1),  # 28
    "y_min": ("Y Min", 8, _double_8B, 1),  # 29
    "z_max": ("Z Max", 8, _double_8B, 1),  # 30
    "z_min": ("Z Min", 8, _double_8B, 1),  # 31
    "start_waveform_data": (
        "Start of Waveform Data Packet Record",
        8,
        _unsigned_long_long_8B,
        1
    ),  # 32
    "start_first_evlr": (
        "Start of first Extended Variable Length Record",
        8,
        _unsigned_long_long_8B,
        1
    ),  # 33
    "number_of_evlrs": (
        "Number of Extended Variable Length Records",
        4,
        _unsigned_long_4B,
        1
    ),  # 34
    "number_of_points": ("Number of point records", 8, _unsigned_long_long_8B, 1),  # 35
    "number_of_points_by_return": (
        "Number of points by return",
        120,
        _unsigned_long_long_8B,
        15
    )  # 36
}

vlr_header_dict = {
    "reserved": ("Reserved", 2, _unsigned_short_2B, 1),  # 0
    "user_id": ("User ID", 16, f"16{_char_more_bytes}", 1),  # 1
    "record_id": ("Record ID", 2, _unsigned_short_2B, 1),  # 2
    "length_after_vlr_header": ("Record Length After Header", 2, _unsigned_short_2B, 1),  # 3
    "description": ("Description", 32, f"32{_char_more_bytes}", 1),  # 4
}

evlr_header_dict = {
    "reserved": ("Reserved", 2, _unsigned_short_2B, 1),  # 0
    "user_id": ("User ID", 16, f"16{_char_more_bytes}", 1),  # 1
    "record_id": ("Record ID", 2, _unsigned_short_2B, 1),  # 2
    "length_after_evlr_header": (
        "Record Length After Header",
        8,
        _unsigned_long_long_8B,
        1
    ),  # 3
    "description": ("Description", 32, f"32{_char_more_bytes}", 1),  # 4
}

other_attributes_dict = {
    "input_laslaz_path": str,  # 0
    "_original_offset_to_point_data": int,  # 1
    "las_version": float  # 2
}

# ------------------------------------------------------------------------------
# SET HEADER LENGTHS AS GLOBAL VARIABLES FOR INCREASED CODE COMPREHENSIBILITY
# ------------------------------------------------------------------------------

# All vlr headers are 54 bytes long;
# setting global variable for increased code comprehensibility.
_vlr_header_length = 54

# All EVLR headers are 60 bytes long;
# setting global variable for increased code comprehensibility.
# _evlr_header_length = 60


# ------------------------------------------------------------------------------
# HELPER FUNCTIONS FOR LASATTR CLASS
# ------------------------------------------------------------------------------

def _auto_update_attributes_by_shift_amount(
    lasattr_instance,
    attributes_to_update_by_shift_amount,
    data_shift
):
    """
    Update attributes by a given shift amount.

    This function is called whenever a vlr#_length_after_header
    attribute is re-set (which is automatically updated when a vlr
    value is re-set).

    Inputs:
        lasattr_instance (LasAttr object)
        attributes_to_update_by_shift_amount (tuple of LasAttr attribute names)
        data_shift (int - amount data has shifted due to vlr length change (+/-))
    """

    for attribute in attributes_to_update_by_shift_amount:
        previous_value = getattr(
            lasattr_instance,
            attribute
        )  # == 0 if no data of this type

        if previous_value == 0:
            new_value = 0
        else:
            new_value = previous_value + data_shift

        setattr(
            lasattr_instance,
            attribute,
            new_value
        )


def _auto_shift_offset_values(lasattr_instance):
    """
    Update the offset_to_point data attribute, and
    use the amount of that shift to update the
    start_waveform_data and start_first_evlr
    attributes.
    """
    data_shift = _auto_update_offset_to_point_data(
        lasattr_instance
    )

    attributes_to_update_by_shift_amount = (
        list(public_header_dict)[32],  # start_waveform_data
        list(public_header_dict)[33]  # start_first_evlr
    )

    _auto_update_attributes_by_shift_amount(
        lasattr_instance,
        attributes_to_update_by_shift_amount,
        data_shift
    )


def _auto_update_length_after_header_attribute(
    lasattr_instance,
    vlr_or_evlr_value_attr_name,
    new_vlr_or_evlr_value,
    which_dict
):
    """
    Update the vlr#_length_after_vlr_header,
    or evlr#_length_after_evlr_header attribute

    This function is called whenever a vlr or evlr value
    is re-set.
    """
    attribute_prefix = vlr_or_evlr_value_attr_name.split(
        _split_character,
        1
    )[0]

    length_after_header_key = list(which_dict)[3]

    length_after_header_attribute = (
        f"{attribute_prefix}"
        f"{_split_character}"
        f"{length_after_header_key}"
    )

    if isinstance(new_vlr_or_evlr_value, str):
        # Add +1 to account for the las-spec-required
        # null-termination character
        new_value_length = len(new_vlr_or_evlr_value) + 1
    else:
        # In case this script ever deals with non-string
        # VLR/EVLR edits, set the length after header attribute
        # to the length of the new VLR/EVLR value.
        # Additional logic will need to implemented for
        # some VLR types, like GeoAsciiParamsTag.
        new_value_length = len(new_vlr_or_evlr_value)

    setattr(
        lasattr_instance,
        length_after_header_attribute,
        new_value_length
    )


def _auto_update_offset_to_point_data(
    lasattr_instance
):
    """
    Update the offset_to_point_data attribute.

    This function is called whenever a vlr#_length_after_header
    attribute is re-set (which is automatically updated when a vlr value
    is re-set).

    Returns the amount the data following the vlrs has shifted (int).

    Note 1: the return data_shift value may be different from the final
    data shift between original data and final written data, if multiple
    vlr lengths are edited. (This data_shift variable is the amount for
    a single vlr_length change; the write_output function relies on the
    total difference between the original_offset_to_point_data attribute
    and the updated offset_to_point_data attribute.)

    Note 2: This function uses the following relationship to calculate
    the new offset_to_point_data value:

        public header length
        +   length of all VLRs
        ----------------------
        =   new offset to points

    So, if there were any 'padding' bytes in the original file between
    the VLRs and the point data, those bytes will be removed when
    the new file is written. If those padding bytes need to be preserved,
    this function needs to be re-written. Lastools' program las2las uses
    the -remove_padding tag to remove these bytes (and any before the header),
    but for now this script relies on the header starting at the beginning of
    the file, and there being no padding between the header and VLRs.

    If you notice your original file offset to header is larger than the value
    obtained by the formula above, the culprits are these padding bytes, that
    show up in lasinfo as "the header is followed by 2 user-defined bytes",
    for example.

    """
    public_header_length_attribute = list(public_header_dict)[13]
    offset_to_point_data_attribute = list(public_header_dict)[14]

    orig_offset_to_point_data = getattr(
        lasattr_instance,
        offset_to_point_data_attribute
    )

    public_header_length = getattr(
        lasattr_instance,
        public_header_length_attribute
    )  # Alway 375 bytes for las 1.4

    total_vlr_length = _length_all_vlrs(lasattr_instance)

    new_offset_to_point_data = (
        public_header_length
        + total_vlr_length
    )

    setattr(
        lasattr_instance,
        list(public_header_dict)[14],
        new_offset_to_point_data
    )

    data_shift = new_offset_to_point_data - orig_offset_to_point_data

    return data_shift


def _bytes_to_string_strip_trailing_nulls(byte_string):
    """
    Decode a python bytes string with UTF-8 encoding into a python string,
    and remove trailing null characters.

    Input:
        - byte_string (byte string)
            e.g., b'WKT Projection\x00\x00\x00\x00\x00\x00'

    Return:
        - string_trailing_nulls_removed (string)
            e.g., 'WKT Projection'
    """
    decoded_string = byte_string.decode("UTF-8")
    decoded_string_trailing_nulls_removed = decoded_string.rstrip("\0")
    return decoded_string_trailing_nulls_removed


def _crs_obj_from_prefix_and_index(lasattr_instance, prefix, index):
    """
    Given a LasAttr attribute prefix (either "vlr" or "evlr"),
    and the index of that vlr or evlr, return a pyproj CRS object,
    and the WKT stored in the vlr/evlr value attribute.

    (Assumes the value is WKT value, which is verified by other
    functions in this module)
    """
    wkt_string = ""

    if prefix == _vlr_attr_prefix:
        wkt_string = getattr(
            lasattr_instance,
            _vlr_value_attr_name(index)
        )

    elif prefix == _evlr_attr_prefix:
        wkt_string = getattr(
            lasattr_instance,
            _evlr_value_attr_name(index)
        )

    crs_obj = pyproj.CRS(wkt_string)

    return crs_obj, wkt_string


def _determine_attr_category(attribute):
    """
    Determine which dictionary an attribute belongs to,
    and return that dictionary name and the associated
    key for that dictionary entry.

    Input:
        - attribute name (string)
            e.g., attribute_name = "vlr1_record_id" (string)

    Returns:
        - dictionary attribute is associated with
            e.g., vlr_header_dict (dictionary object)
        - key for that attribute name in the dictionary
            e.g., "record_id" (string)

    """
    if attribute.startswith(_vlr_attr_prefix):
        which_dict = vlr_header_dict

        # Remove the indexed prefix vlr#_ from the attribute name
        # to make the attribute match the key in the vlr_header_dict
        attribute_key = attribute.split(_split_character, 1)[1]

    elif attribute.startswith(_evlr_attr_prefix):
        which_dict = evlr_header_dict

        # Remove the indexed prefix evlr#_ from the attribute name
        # to make the attribute match the key in the evlr_header_dict
        attribute_key = attribute.split(_split_character, 1)[1]

    elif attribute in list(other_attributes_dict):
        which_dict = other_attributes_dict
        attribute_key = attribute

    else:
        which_dict = public_header_dict
        attribute_key = attribute

    return which_dict, attribute_key


def _evlr_attr_prefix_index(j):
    """
    For an evlr of index j, provide the complete evlr attribute prefix.
    """
    evlr_attr_prefix_index = f"{_evlr_attr_prefix}{j}{_split_character}"
    return evlr_attr_prefix_index


def _evlr_header_attr_name(j, evlr_header_key):
    """
    For an evlr of index j, and evlr header key evlr_header_key,
    provide the complete evlr attribute name.
    """
    evlr_header_attr_name = f"{_evlr_attr_prefix_index(j)}{evlr_header_key}"
    return evlr_header_attr_name


def _evlr_value_attr_name(j):
    evlr_value_attr_name = f"{_evlr_attr_prefix_index(j)}{_value_attr_root}"
    return evlr_value_attr_name


def _get_evlr_length_after_evlr_header(lasattr_instance, j):
    """
    Get the length of an EVLR after its EVLR header
    with EVLR index j, according to the LasAttr
    object attribute
    """
    evlr_length_key = list(evlr_header_dict)[3]
    evlr_length = getattr(
        lasattr_instance,
        _evlr_header_attr_name(j, evlr_length_key)
    )
    return evlr_length


def _get_evlr_num(lasattr_instance):
    """
    Get the number of EVLRs according to
    the LasAttr attribute.
    """
    evlr_num_key = list(public_header_dict)[34]
    evlr_num = getattr(lasattr_instance, evlr_num_key)
    return evlr_num


def _get_start_first_evlr(lasattr_instance):
    """
    Get the start of the first EVLR, according to the
    LasAttr object attribute.
    """
    start_first_evlr_key = list(public_header_dict)[33]
    start_first_evlr = getattr(
        lasattr_instance,
        start_first_evlr_key
    )
    return start_first_evlr


def _get_vlr_length_after_vlr_header(lasattr_instance, i):
    """
    Get the length of a VLR after the VLR header
    with VLR index i, according to the lasattr
    instance attribute.
    """
    vlr_length_key = list(vlr_header_dict)[3]
    vlr_length = getattr(
        lasattr_instance,
        _vlr_header_attr_name(i, vlr_length_key)
    )
    return vlr_length


def _get_vlr_num(lasattr_instance):
    """
    Get the number of VLRs according to
    the LasAttr attribute.
    """
    vlr_num_key = list(public_header_dict)[15]
    vlr_num = getattr(lasattr_instance, vlr_num_key)
    return vlr_num


def _guid_warning_gate(guid_attribute_key):
    """Known limitation of this script: interpreting GUIDS!
    Postponing interpreting GUIDs as it is lower priority.
    In the meantime, here's a warning gate about changing
    guid values.
    """
    print(
        f"\n{_dashline}"
        "\nWARNING!"
        "\nlasattr does not yet interpret "
        "guid attribute values properly."
    )

    # WARNING GATE FOR TERMINAL-SCRIPT-RUNNING ONLY:
    # proceed = ""
    # while proceed not in ("y", "Y", "n", "N"):
    #     proceed = input(
    #         f"\nAre you sure want to change the {guid_attribute_key} value? [y/n] "
    #     )
    #     if proceed in ("n", "N"):
    #         raise ValueError(
    #             f"\n{_dashline}"
    #             "\nGUID interpretation not yet implemented in the "
    #             "LasAttr class;"
    #             "\nTry again without re-writing a guid attribute."
    #             f"\n{_dashline}"

    print(_dashline)


def _initialize_evlr_attributes(
    lasattr_instance,
    infile
):
    """
    Set the EVLR attribute values (EVLR header and EVLR payload)
    for the initial state of a LasAttr object.
    """
    # Start of the first evlr
    start_first_evlr = _get_start_first_evlr(lasattr_instance)

    if start_first_evlr > 0:
        infile.seek(start_first_evlr)

        # Number of EVLRs
        evlr_num_key = list(public_header_dict)[34]
        evlr_num = getattr(
            lasattr_instance,
            evlr_num_key
        )

        for j in range(evlr_num):
            for evlr_header_key in evlr_header_dict:
                # Get the evlr header element tuple for the key
                evlr_header_tuple = evlr_header_dict.get(evlr_header_key)

                # Read the next x bytes from the las file
                evlr_binary_data = infile.read(evlr_header_tuple[1])

                unpacked_evlr_value = _unpack_header_element(
                    evlr_header_tuple,
                    evlr_binary_data
                )

                # EVLR header elements are a single element, so we can
                # remove that element from the tuple without an 'if' clause
                unpacked_evlr_value = unpacked_evlr_value[0]

                # Assign object parameters for the evlr header element
                # using key as attribute name
                setattr(
                    lasattr_instance,
                    _evlr_header_attr_name(j, evlr_header_key),
                    unpacked_evlr_value
                )

            # EVLR length after EVLR header
            evlr_length_key = list(evlr_header_dict)[3]
            evlr_length = getattr(
                lasattr_instance,
                _evlr_header_attr_name(j, evlr_length_key)
            )

            # Read the EVLR value after the EVLR header
            evlr_value_binary = infile.read(evlr_length)

            # ! this unpack line unpacks properly if the data is characters,
            # ! (as for WKT), but not if it's another data type
            evlr_value = struct.unpack(
                f"{evlr_length}{_char_more_bytes}",
                evlr_value_binary
            )[0]

            try:
                # this statement will succeed if the data is characters (as for WKT),
                # but not if it's another type and the above unpack line didn't
                # unpack the correct data type
                evlr_value = _bytes_to_string_strip_trailing_nulls(
                    evlr_value
                )
            except Exception:
                # print(
                #    "EVLR data is not characters; find another way to unpack!"
                # )
                pass

            setattr(
                lasattr_instance,
                _evlr_value_attr_name(j),
                evlr_value
            )


def _initialize_public_header_attributes(
    lasattr_instance,
    infile,
):
    """
    Set the public header attribute values for the
    initial state of a LasAttr object.

    Return the number of bytes read by this function,
    which is the size of the public header. (int)
    """
    for public_header_key in public_header_dict:
        public_header_tuple = public_header_dict.get(public_header_key)

        # Read the next x bytes from the las/laz file
        public_header_binary_data = infile.read(public_header_tuple[1])

        unpacked_value = _unpack_header_element(
            public_header_tuple,
            public_header_binary_data
        )

        # If unpacked value is a single element, remove that
        # element from the tuple:
        if len(unpacked_value) == 1:
            unpacked_value = unpacked_value[0]

        # Assign object parameters for public header element
        # using key as attribute name
        # ! figure out how the 4 guid attributes are supposed to go
        # ! together to give the correct value
        setattr(
            lasattr_instance,
            public_header_key,
            unpacked_value,
        )


def _initialize_vlr_attributes(
    lasattr_instance,
    infile
):
    """
    Set the VLR attribute values (VLR header and VLR payload)
    for the initial state of a LasAttr object.
    """
    # Get the number of VLRs
    vlr_num = _get_vlr_num(lasattr_instance)

    # Iterate through each VLR...
    for i in range(vlr_num):

        # Iterate through each VLR header element...
        for vlr_header_key in vlr_header_dict:
            # Get the vlr header element tuple for the key
            vlr_header_tuple = vlr_header_dict.get(vlr_header_key)

            # Read the next x bytes from the las file
            vlr_binary_data = infile.read(
                vlr_header_tuple[1]
            )
            vlr_header_tuple[1]

            unpacked_vlr_header_element = _unpack_header_element(
                vlr_header_tuple,
                vlr_binary_data
            )

            # VLR header elements are a single element, so we can
            # remove that element from the tuple without an 'if' clause
            unpacked_vlr_header_element = unpacked_vlr_header_element[0]

            # Assign object parameters for vlr header element
            # using key as attribute name
            setattr(
                lasattr_instance,
                _vlr_header_attr_name(i, vlr_header_key),
                unpacked_vlr_header_element,
            )

        # VLR length after VLR header
        vlr_length = _get_vlr_length_after_vlr_header(
            lasattr_instance,
            i
        )

        # Read and display the VLR values after the VLR header
        vlr_value_binary = infile.read(vlr_length)

        # ! this unpack line unpacks properly if the data is characters,
        # ! because the first argument is "Xs", (_char_more_bytes of
        # ! X bytes), as for WKT, but not if it's another data type
        # ! Can we figure out what the other data type might be, perhaps
        # ! similarly to laspy's 'known.py' library? (Or, do we even
        # ! care about those other VLR types, so can we continue to
        # ! treat them as char data for the purposes of this script?
        vlr_value = struct.unpack(
            f"{vlr_length}{_char_more_bytes}",
            vlr_value_binary
        )[0]

        try:
            # this statement will succeed if the data is characters (as for WKT),
            # but not if it's another type and the above unpack line didn't
            # unpack the correct data type
            vlr_value = _bytes_to_string_strip_trailing_nulls(vlr_value)
        except Exception:
            # print("VLR value data is not characters; find another way to unpack!")
            pass

        setattr(
            lasattr_instance,
            _vlr_value_attr_name(i),
            vlr_value
        )


def _las_version_float(lasattr_instance):
    """
    Get the las version as a float,
    according to the lasattr attributes.

    e.g., returns "1.4"
    """
    ver_maj_key = list(public_header_dict)[7]
    ver_maj = getattr(
        lasattr_instance,
        ver_maj_key
    )

    ver_min_key = list(public_header_dict)[8]
    ver_min = getattr(
        lasattr_instance,
        ver_min_key
    )

    las_version_string = f"{ver_maj}.{ver_min}"

    las_version_float = float(las_version_string)

    return las_version_float


def _las_version_check(las_version):
    """
    Issue a warning and terminal gate if las/laz
    version is not 1.4.
    """
    las_version_warning = (
        f"\n{_dashline}"
        f"\nWARNING!"
        f"\n\nLasAttr is designed to "
        f"work with las/laz version 1.4 and may "
        f"behave unexpectedly with other "
        f"versions."
        f"\n\nThe input file is version {las_version}"
        f"\n{_dashline}"
    )

    if las_version != 1.4:
        print(
            las_version_warning
        )

        # WARNING GATE FOR TERMINAL-SCRIPT-RUNNING ONLY:
        # proceed = ""
        # while proceed not in ("y", "Y", "n", "N"):
        #    proceed = input(
        #        f"{las_version_warning}"
        #        f"\n\nDo you wish to proceed? [y/n] "
        #    )
        #    if proceed in ("n", "N"):
        #        raise TypeError(
        #            f"\n{_dashline}"
        #            f"\nlasattr developed for las/laz 1.4"
        #            f"\n\nThe input file is las/laz version {las_version}"
        #            f"\n{_dashline}"
        #        )


def _length_all_vlrs(lasattr_instance):
    """
    Compute the length of all VLRs.

    Returns <int>
    """
    vlr_num = _get_vlr_num(lasattr_instance)

    total_length_vlrs = 0

    for i in range(vlr_num):
        total_length_vlrs += _vlr_header_length
        total_length_vlrs += _get_vlr_length_after_vlr_header(
            lasattr_instance,
            i
        )

    return total_length_vlrs


def _log_conclusion():
    """
    Text to add to the end of the log file.
    """
    log_conclusion = (
        f"\n{_dashline}\n"
        f"End of {lasattr_software_name} Attribute Log.\n"
    )

    return log_conclusion


def _log_header(lasattr_instance, which_dict, vlr_evlr_index=None):
    """
    Return the current values of a header as a string
    to be added to the log text.
    """
    log_header = ""

    for header_element_index, header_key in enumerate(
        which_dict
    ):
        if which_dict == vlr_header_dict:
            header_attr_name = _vlr_header_attr_name(vlr_evlr_index, header_key)
        elif which_dict == evlr_header_dict:
            header_attr_name = _evlr_header_attr_name(vlr_evlr_index, header_key)
        else:
            header_attr_name = header_key

        header_element_title = which_dict.get(header_key)[0]

        header_attr_value = getattr(
            lasattr_instance,
            header_attr_name
        )

        # If the value isn't a tuple, put it in the first element of a tuple,
        # so we can treat it like the values that are tuples.
        if not isinstance(header_attr_value, tuple):
            header_attr_value = (header_attr_value, )

        # The data type is the same for all elements in the tuple,
        # so we can tell the data type by looking at the first element of the tuple.
        # (In most cases, there is only one element).
        header_value_type = type(header_attr_value[0])

        if header_value_type is bytes:
            # Convert tuple to list to be editable
            header_attr_value = list(header_attr_value)

            # Convert value from binary string to regular python string
            # with trailing null values removed
            header_attr_value[0] = _bytes_to_string_strip_trailing_nulls(
                header_attr_value[0]
            )
            header_value_type = str

        header_values_string = "\n"
        for value in header_attr_value:
            header_values_string += f"\t{value}\n"

        log_header += (
            f"\n{header_element_index}. {header_element_title} ({header_value_type}):"
            f"{header_values_string}"
        )

    return log_header


def _log_intro(lasattr_instance, now_string):
    """
    Add the input filename to the
    beginning of the log file.

    Returns string formatted for .txt output.
    """
    log_intro = (
        f"{lasattr_software_name} Attribute Log, {now_string}"
        f"\n\n{_dashline}"
        f"\nInput file:"
        f"\n\n{getattr(lasattr_instance, list(other_attributes_dict)[0])}"
        f"\n\n{_dashline}"
    )

    return log_intro


def _log_public_header(lasattr_instance):
    """
    Add the current values of a LasAttr object's
    public header attributes to a string object.

    These values may have been altered
    since initialization of the instance,
    and therefore may not reflect the contents
    of the input file.
    """
    log_public_header = "\nPublic header elements:\n"

    log_public_header += _log_header(
        lasattr_instance,
        public_header_dict
    )

    return log_public_header


def _log_vlr_evlr(lasattr_instance, prefix):
    """
    Add the current values of a LasAttr object's
    VLR or EVLR header and value attributes to a
    string object.

    These values may have been altered
    since initialization of the instance,
    and therefore may not reflect the contents
    of the input file.
    """
    log_vlr_evlr = ""

    if prefix == _vlr_attr_prefix:
        vlr_evlr_num = _get_vlr_num(lasattr_instance)
        header_dict = vlr_header_dict
    elif prefix == _evlr_attr_prefix:
        vlr_evlr_num = _get_evlr_num(lasattr_instance)
        header_dict = evlr_header_dict

    if vlr_evlr_num == 0:
        log_vlr_evlr = f"\n{_dashline}\nNo {prefix.upper()}s.\n"

    else:
        for k in range(vlr_evlr_num):
            log_vlr_evlr += _log_vlr_evlr_intro(
                lasattr_instance,
                prefix,
                k
            )

            log_vlr_evlr += _log_header(
                lasattr_instance,
                header_dict,
                k
            )

            log_vlr_evlr += _log_vlr_evlr_value(
                lasattr_instance,
                prefix,
                k
            )

    return log_vlr_evlr


def _log_vlr_evlr_intro(lasattr_instance, prefix, index):
    """
    Set the introductory statement for the log file
    for each VLR and EVLR.
    """
    if prefix == _vlr_attr_prefix:
        num = _get_vlr_num(lasattr_instance)
    elif prefix == _evlr_attr_prefix:
        num = _get_evlr_num(lasattr_instance)

    prefix_caps = prefix.upper()
    vlr_evlr_intro = (
        f"\n\n{_dashline}\n{prefix_caps} {index + 1} "
        f"of {num} {prefix_caps}(s) (index {index}):\n"
    )

    return vlr_evlr_intro


def _log_vlr_evlr_value(lasattr_instance, prefix, index):
    """
    Set the log text for a VLR or EVLR value.
    """
    if prefix == _vlr_attr_prefix:
        record_length = _get_vlr_length_after_vlr_header(lasattr_instance, index)
        vlr_evlr_value = getattr(
            lasattr_instance,
            _vlr_value_attr_name(index)
        )
    elif prefix == _evlr_attr_prefix:
        record_length = _get_evlr_length_after_evlr_header(lasattr_instance, index)
        vlr_evlr_value = getattr(
            lasattr_instance,
            _evlr_value_attr_name(index)
        )

    prefix_caps = prefix.upper()

    log_vlr_evlr_value = (
        f"\n{prefix_caps} value:"
        f"\n\n- value type: {type(vlr_evlr_value)}"
        f"\n- value length (not including terminal null(s)): {len(vlr_evlr_value)}"
        f"\n- {prefix_caps} length after {prefix_caps} header (including terminal null(s)): {record_length}"
        f"\n\n\t{vlr_evlr_value}\n"
    )

    return log_vlr_evlr_value


def _now_strings():
    """
    Returns two versions of the current minute, formatted thus:
        YYYY-mm-dd, HH:MM
        YYYYmmdd_HHMM
    """
    now_time = datetime.now()
    now_string = now_time.strftime("%Y-%m-%d, %H:%M")
    now_string_filename = now_time.strftime("%Y%m%d_%H%M")
    return now_string, now_string_filename


def _parse_vlrs_evlrs_with_wkt(lasattr_instance):
    """
    Separate the list of VLRs and EVLRs
    identified as having WKT values into
    a list of VLR indices and a list of EVLR
    indices.
    """
    vlr_evlr_wkt = lasattr_instance.find_wkt()
    vlr_wkt = []
    evlr_wkt = []
    for item in vlr_evlr_wkt:
        if item[0] == _vlr_attr_prefix:
            vlr_wkt.append(item[1])
        elif item[0] == _evlr_attr_prefix:
            evlr_wkt.append(item[1])

    return vlr_wkt, evlr_wkt


def _prep_output_file(
    lasattr_instance,
    output_laslaz_path
):
    """
    If not overwriting in place, copy input file to output location.
    """
    input_laslaz_path = getattr(
        lasattr_instance,
        list(other_attributes_dict)[0]
    )

    # Check that the output file is the same type as the input file
    # Add the correct file extension if required
    _, input_file_ext = os.path.splitext(input_laslaz_path)
    if not output_laslaz_path.endswith(input_file_ext):
        output_laslaz_path += input_file_ext

    if input_laslaz_path == output_laslaz_path:
        print("Original file will be overwritten!")

        # WARNING GATE FOR TERMINAL-SCRIPT-RUNNING ONLY:
        # proceed = ""
        # while proceed not in ("y", "Y", "n", "N"):
        #     proceed = input("Input file will be with overwritten. Proceed? [y/n]")
        #     if proceed in ("n", "N"):
        #         raise ValueError(
        #             f"\n{_dashline}"
        #             "\nWrite not executed to avoid overwriting input file."
        #             "\nChange the output file name or "
        #             "location to avoid this problem."
        #             f"\n{_dashline}"
        #         )

    else:
        # Copy the original las/laz file to the output location
        shutil.copyfile(
            input_laslaz_path,
            output_laslaz_path
        )


def _set_logpath(lasattr_instance, log_filename, log_folder, now_string_filename):
    """
    Set the file path for the log file.

    Adds default values for the filename and folder path
    if none are provided.
        - filename default:

    """
    text_file_ext = ".txt"

    input_laslaz_path = getattr(
        lasattr_instance,
        list(other_attributes_dict)[0]
    )

    if not log_filename:
        input_laslaz_filename_with_ext = os.path.basename(input_laslaz_path)
        input_filename, _ = os.path.splitext(input_laslaz_filename_with_ext)
        log_filename = f"{input_filename}_lasattr_{now_string_filename}"
    if not log_filename.endswith(text_file_ext):
        log_filename += text_file_ext

    if not log_folder:
        log_folder = os.path.dirname(input_laslaz_path)

    log_path = os.path.join(log_folder, log_filename)

    return log_path


def _string_to_bytes_append_trailing_nulls(python_string, element_size_bytes):
    """
    Encode a python string into a python bytes string with UTF-8 encoding,
    and append the appropriate number of trailing null characters
    to make the byte string a given size.

    Inputs:
        python_string (string)
            e.g.,
                'Really Awesome Lidar Co. Inc.' (29 characters)
        element_size_bytes (int)
            e.g.,
                32

    Return:
        - encoded_string_with_nulls_to_size (byte string)
            e.g.,
                b'Really Awesome Lidar Co. Inc.\x00\x00\x00'
                (29 characters + 3 null characters = 32 bytes)
    """
    input_length = len(python_string)

    # Check the input string isn't too long for the field
    if input_length > element_size_bytes:
        raise ValueError(
            f"\n{_dashline}"
            f"\nValue error!"
            f"\nNew value is {input_length} characters:"
            f"\n\t{python_string}"
            f"\nPlease make it {element_size_bytes} characters or less, "
            f"and try again."
            f"\n{_dashline}"
        )

    # Calculate the number of null characters required to fill the element
    num_nulls = element_size_bytes - input_length

    # Remind us all what the python null string character looks like
    python_null = "\0"

    # Make a new string by combining the original string
    # with the number of null characters required to fill the element
    python_string_with_nulls_to_size = f"{python_string}{python_null * num_nulls}"

    # Convert the python string with nulls into a bytes string
    encoded_string_with_nulls_to_size = python_string_with_nulls_to_size.encode("UTF-8")

    # Return the encoded string with trailing nulls
    return encoded_string_with_nulls_to_size


def _unpack_header_element(header_tuple, binary_data):
    """
    Unpack .las/.laz binary header data into a python-readable format.

    Inputs:
        header_tuple (tuple)
            - tuple elements:
                0: item (string),
                1: total number of bytes to read for item (integer),
                2: data format (string),
                3: number of data format units comprising item
        binary_data (bytes)
            - binary data read from a las or laz file header, VLR, or EVLR

    Returns:
        unpacked_value (tuple)
            - Each tuple element is the data as a python object
            - Note: strings are maintained as byte strings with
            trailing null values

    """
    # Assign the correct number of struct code elements for struct,
    # e.g., "L" for element 15 (# of VLRs), which is a single unsigned long,
    # or "BBBBBBBB" for element 6 (GUID4), which is eight unsigned chars.
    struct_format_code = header_tuple[2] * header_tuple[3]

    unpacked_value = struct.unpack(struct_format_code, binary_data)

    # Return the unpacked_value as a tuple
    return unpacked_value


def _vlr_attr_prefix_index(i):
    """
    For a vlr of index i, provide the complete vlr attribute prefix.
    """
    vlr_attr_prefix_index = f"{_vlr_attr_prefix}{i}{_split_character}"
    return vlr_attr_prefix_index


def _vlr_header_attr_name(i, vlr_header_key):
    """
    For a vlr of index i, and vlr header key vlr_header_key,
    provide the complete vlr attribute name.
    """
    vlr_header_attr_name = f"{_vlr_attr_prefix_index(i)}{vlr_header_key}"
    return vlr_header_attr_name


def _vlr_value_attr_name(i):
    vlr_value_attr_name = f"{_vlr_attr_prefix_index(i)}{_value_attr_root}"
    return vlr_value_attr_name


def _write_evlrs(
    lasattr_instance,
    outfile
):
    """
    Write VLR data to output file using
    LasAttr object attribute values.
    """
    start_first_evlr = _get_start_first_evlr(lasattr_instance)

    if start_first_evlr > 0:
        outfile.seek(start_first_evlr)

        evlr_num = _get_evlr_num(lasattr_instance)

        # Iterate through each EVLR...
        for j in range(evlr_num):
            # Iterate through each EVLR header element...
            for evlr_header_key in evlr_header_dict:
                # Get the evlr header element tuple for the key
                evlr_header_tuple = evlr_header_dict.get(evlr_header_key)

                # Determine the struct format code for this element
                struct_format_code = evlr_header_tuple[2]

                # Get the python data for the attribute
                python_data = getattr(
                    lasattr_instance,
                    _evlr_header_attr_name(j, evlr_header_key)
                )

                # If python data is a normal string, convert it to
                # a bytes string of the appropriate length
                if isinstance(python_data, str):
                    python_data = _string_to_bytes_append_trailing_nulls(
                        python_data,
                        evlr_header_tuple[1]
                    )

                # Convert the python data to binary data, ready to be written
                # into the output file
                binary_value = struct.pack(struct_format_code, python_data)

                outfile.write(binary_value)

            # Get the length of the EVLR after the EVLR header
            evlr_length = _get_evlr_length_after_evlr_header(
                lasattr_instance,
                j
            )

            # Get the python data for the evlr value
            evlr_value_python = getattr(
                lasattr_instance,
                _evlr_value_attr_name(j)
            )

            # If the vlr value has been converted to a string,
            # convert it to bytes data. (Otherwise, it was never
            # converted from bytes --  this class only cares about
            # character VLRs for now, specifically WKT strings)
            if isinstance(evlr_value_python, str):
                evlr_value_python = _string_to_bytes_append_trailing_nulls(
                    evlr_value_python,
                    evlr_length
                )

            # Convert the python data to binary data, ready to be written into
            # the output file
            binary_value = struct.pack(
                f"{evlr_length}{_char_more_bytes}",
                evlr_value_python
            )

            # Write the EVLR value to the las/laz file
            outfile.write(binary_value)


def _write_public_header(
    lasattr_instance,
    outfile
):
    """
    Write public header data to output file using
    LasAttr object attribute values.
    """
    for public_header_key in public_header_dict:
        # Get the header tuple for the given key
        public_header_tuple = public_header_dict.get(public_header_key)

        # Assign the struct code elements for struct,
        # e.g., "L" for element 15 (# of VLRs), which is an unsigned long,
        # or "B" for an unsigned char.
        struct_format_code = public_header_tuple[2]

        # Get the header attribute value in python data format
        python_value = getattr(lasattr_instance, public_header_key)

        # If the python data is a string, convert it
        # into a bytes string with the correct number of
        # trailing null characters to meet the byte size for
        # the attribute.
        if _char_more_bytes in struct_format_code:
            element_size_bytes = public_header_tuple[1]
            python_value = _string_to_bytes_append_trailing_nulls(
                python_value,
                element_size_bytes
            )

        # Put the python data into a tuple if it wasn't in one already
        # (data with multiple entries are already tuples)
        if type(python_value) is not tuple:
            python_value = (python_value, )

        for item in python_value:
            # Convert python data to binary data, ready to be written into
            # the output file
            binary_value = struct.pack(struct_format_code, item)

            # Write the public header element to the las/laz file
            outfile.write(binary_value)


def _write_vlrs(
    lasattr_instance,
    outfile
):
    """
    Write VLR data to output file using
    LasAttr object attribute values.
    """
    vlr_num = _get_vlr_num(lasattr_instance)

    # Iterate through each VLR...
    for i in range(vlr_num):
        # Iterate through each VLR header element...
        for vlr_header_key in vlr_header_dict:
            # Get the vlr header element tuple for the key
            vlr_header_tuple = vlr_header_dict.get(vlr_header_key)

            # Determine the struct format code for this element
            struct_format_code = vlr_header_tuple[2]

            # Get the python data for the attribute
            python_data = getattr(
                lasattr_instance,
                _vlr_header_attr_name(i, vlr_header_key)
            )

            # If python data is a normal string, convert it to
            # a bytes string of the appropriate length
            if isinstance(python_data, str):
                python_data = _string_to_bytes_append_trailing_nulls(
                    python_data,
                    vlr_header_tuple[1]
                )

            # Convert python data to binary data, ready to be written into
            # the output file
            binary_value = struct.pack(struct_format_code, python_data)

            # Write the data to the las/laz file
            outfile.write(binary_value)

        # Get the length of the VLR after the VLR header
        vlr_length = _get_vlr_length_after_vlr_header(lasattr_instance, i)

        # Get the python data for the vlr value
        vlr_value_python = getattr(
            lasattr_instance,
            _vlr_value_attr_name(i)
        )

        # If the vlr value has been converted to a string,
        # convert it to bytes data. (Otherwise, it was never
        # converted from bytes --  this class only cares about
        # character VLRs for now, specifically WKT strings)
        if isinstance(vlr_value_python, str):
            vlr_value_python = _string_to_bytes_append_trailing_nulls(
                vlr_value_python,
                vlr_length
            )

        # Convert the python data to binary data, ready to be written into
        # the output file
        binary_value = struct.pack(
            f"{vlr_length}{_char_more_bytes}",
            vlr_value_python
        )

        # Write the VLR value to the las/laz file
        outfile.write(binary_value)


# ------------------------------------------------------------------------------
# CLASS DEFINITION
# ------------------------------------------------------------------------------

class LasAttr:
    """
    A LasAttr object instance stores all non-point-data from
    a las or laz file (i.e., las metadata) as attributes
    (instance variables).

    This las metadata includes:
        public header elements,
        vlr header elements,
        vlr contents (vlr payloads),
        evlr header elements,
        evlr contents (evlr payloads)

    In other words, everything but the point data (las payload).

    LasAttr attributes can updated, and the changed values can be used to
    write a new las/laz file with those elements updated.
    """

    def __init__(
        self, input_laslaz_path
    ):
        global _attributes_initialized
        # Re-set to false for each new instance of this class
        _attributes_initialized = False

        # Set input_laslaz_path attribute
        setattr(
            self,
            list(other_attributes_dict)[0],
            input_laslaz_path
        )

        with open(input_laslaz_path, "rb") as infile:
            # Set initial public header attributes
            _initialize_public_header_attributes(
                self,
                infile
            )

            # Set the _original_offset_to_point_data attribute value
            # so we can refer to that value even if the offset_to_point_data
            # value changes, to know how much the data needs to shift
            # when writing files.
            setattr(
                self,
                list(other_attributes_dict)[1],
                getattr(
                    self,
                    list(public_header_dict)[14]
                )
            )

            # Set initial vlr attributes
            _initialize_vlr_attributes(
                self,
                infile
            )

            # Get the las version as a float value
            las_version = _las_version_float(self)

            # Check if input file is las/laz version 1.4
            _las_version_check(las_version)

            # Set intial evlr attributes
            # (las versions >= 1.3 allow EVLRs)
            if las_version >= 1.3:
                _initialize_evlr_attributes(
                    self,
                    infile
                )

            # Flip the switch on this global variable
            # indicating the object instance has been
            # initialized with the original file attributes
            _attributes_initialized = True

    def __setattr__(self, attribute, new_value):
        """
        Control attribute data input.
        """
        # If the new value is a bytes string, convert it to a
        # regular python string
        if isinstance(new_value, bytes):
            try:
                new_value = _bytes_to_string_strip_trailing_nulls(new_value)
            except Exception:
                pass

        # Determine category the attribute belongs to
        # (vlr, evlr, public, other) and find the associated
        # attribute key for that dictionary
        which_dict, attribute_key = _determine_attr_category(
            attribute
        )

        # Known limitation of this script:
        # interpreting GUIDs! postponing this task as it is lower priority
        # instead, if the guid_initialize global variable is True,
        # this warning gate will activate.
        if attribute_key.startswith("guid") and _attributes_initialized:
            _guid_warning_gate(attribute_key)

        # Initialize python_data_type
        python_data_type = None

        if which_dict == other_attributes_dict:
            python_data_type = other_attributes_dict.get(attribute_key)
            header_tuple = None
        # Get the header tuple for the given dictionary and key.
        # header_tuple will be set to None if the key does not
        # exist in the dictionary.
        # Cases where key does not exist in a dictionary so
        # header_tuple is set to None:
        #   1. any vlr or evlr values that are not part
        #     of the vlr or evlr header
        #     (i.e., the attribute name is vlr#_value,
        #     or evlr#_value)
        else:
            header_tuple = which_dict.get(attribute_key)

        # If header_tuple has a value, it was in a dictionary,
        # so it has a struct format code in the [2] position
        if header_tuple:
            struct_format_code = header_tuple[2]
            if _char_more_bytes in struct_format_code:
                # If the struct format code is "#s" (#_char_more_bytes),
                # drop the numerals from the struct_format_code to just be "s",
                # to use struct_format_code as the key to the format_dict
                struct_format_code = _char_more_bytes

                if isinstance(new_value, str):
                    # Check the length of the input string fits in the field.
                    # If the input string is too long, issue a value error.
                    max_characters = header_tuple[1]
                    new_str_value_length = len(new_value)
                    if new_str_value_length > max_characters:
                        raise ValueError(
                            f"\n{_dashline}"
                            f"\nValue error!"
                            f"\n\nNew value for {attribute} is "
                            f"{new_str_value_length} characters:"
                            f"\n\t{new_value}"
                            f"\n\nPlease make {attribute} attribute "
                            f"{max_characters} characters or less, "
                            f"and try again."
                            f"\n{_dashline}"
                        )

            # Retrieve the python data type from the format_dict
            # using the struct_format_code as the key
            python_data_type = format_dict.get(struct_format_code)

            # A number of attributes in the public_header_dict
            # have multiple elements stored in tuples, so the
            # python_data_type should be overwritten as tuple
            if header_tuple[3] != 1:  # True for elements that should be tuples
                # TODO check element size is the correct number of bytes
                # TODO (consider discrepancies between struct type sizes
                # TODO and python data sizes--guid4 is a good example)
                # tuple_element_size_bytes = header_tuple[1] / header_tuple[3]
                if not isinstance(new_value, tuple):
                    raise TypeError(
                        f"\n{_dashline}"
                        f"\nIncorrect data type!"
                        f"\n{attribute} can only contain tuples."
                        f"\nIncorrect value provided:"
                        f"\n\t{new_value}"
                        f"\n{_dashline}"
                    )

                # Check the values within the tuple
                # are each the correct data type.
                bad_element_dict = {}
                for element in new_value:
                    if not isinstance(element, python_data_type):
                        bad_element_dict[element] = type(element)

                if bad_element_dict:
                    raise TypeError(
                        f"\n{_dashline}"
                        f"\nIncorrect data type!"
                        f"\n{attribute} can only contain {python_data_type} values."
                        f"\nIncorrect values provided:"
                        f"\n\t{bad_element_dict}"
                        f"\n{_dashline}"
                    )

                # Check the tuple contains the correct number of elements
                correct_element_number = header_tuple[3]
                if len(new_value) != correct_element_number:
                    raise ValueError(
                        f"\n{_dashline}"
                        f"\nIncorrect tuple length!"
                        f"\n{attribute} must contain {correct_element_number} elements."
                        f"\n{_dashline}"
                    )

                # If there were no bad elements in the tuple,
                # Overwrite the python_data_type as tuple
                python_data_type = tuple

        # If header_tuple does not have a value, the attribute
        # was either in the other_attributes_dict, and the python_data_type
        # has already been defined, or it is a vlr/evlr value.
        # For now, this class treats all vlr/evlr values as strings.
        else:
            if not python_data_type:
                python_data_type = str

        if isinstance(new_value, bytes):
            try:
                _bytes_to_string_strip_trailing_nulls(new_value)
            except Exception:
                # Some vlr/evlr values may not have been character data,
                # so they would not have been converted to strings and are
                # still bytes data. In those cases, set the python_data_type
                # to bytes.
                python_data_type = bytes

        # Check if the new value is the correct python data type
        if not isinstance(new_value, python_data_type):
            raise TypeError(
                f"\n{_dashline}"
                f"\nIncorrect data type!"
                f"\n\n{attribute} input as a {type(new_value)},"
                f"\n\tInput value:"
                f"\n\t\t{new_value}"
                f"\n\n{attribute} needs to be a {python_data_type}."
                f"\nPlease change the input value."
                f"\n{_dashline}"
            )

        # Set the attribute to the new value
        super().__setattr__(attribute, new_value)

        # If the attribute is a VLR/EVLR value, update the
        # e/vlr#_length_after_header attribute with the length
        # of the incoming value
        if _value_attr_root in attribute and _attributes_initialized:
            _auto_update_length_after_header_attribute(
                self,
                attribute,
                new_value,
                which_dict
            )

        # If a vlr#_length_after_header attribute is re-set,
        # re-set these attributes:
        #   offset_to_point_data [14]
        #   start_waveform_data [32]
        #   start_first_evlr [33]
        if list(vlr_header_dict)[3] in attribute and _attributes_initialized:
            _auto_shift_offset_values(self)

    def find_wkt(self):
        """
        Identify which VLRs and EVLRs contain a WKT value.

        Returns:
        - list of tuples, each tuple with two elements:
            [0] - attribute prefix (either "vlr" or "evlr") (string),
                    or None if no WKT present
            [1] - index of the VLR or EVLR or with the WKT (int)
                    or None if no WKT present
        """
        vlrs_evlrs_with_wkt = []

        # Check the VLRs for a WKT string
        vlr_num = _get_vlr_num(self)
        for i in range(vlr_num):
            vlr_value = getattr(
                self,
                _vlr_value_attr_name(i)
            )
            if isinstance(vlr_value, str):
                if pyproj.crs.is_wkt(vlr_value):
                    vlrs_evlrs_with_wkt.append((_vlr_attr_prefix, i))

        # Check the EVLRs for a WKT string
        evlr_num = _get_evlr_num(self)
        for j in range(evlr_num):
            vlr_num = _get_evlr_num(self)
        for j in range(evlr_num):
            evlr_value = getattr(
                self,
                _evlr_value_attr_name(j)
            )
            if isinstance(evlr_value, str):
                if pyproj.crs.is_wkt(evlr_value):
                    vlrs_evlrs_with_wkt.append((_evlr_attr_prefix, j))

        return vlrs_evlrs_with_wkt

    def log_attr(self, log_filename=None, log_folder=None, auto_open=False):
        """
        Create a text file with the current values
        of all attributes for a LasAttr instance object.

        The LasAttr version of lasinfo :)

        Args:
            - log_filename (string) (optional)
                - Name of log file that will be written.
                    (including the extension .txt is optional;
                    it will be added if not provided.)
                - If no file name is provided,
                    the the file name will be the name
                    of the input las/laz file name,
                    followed by the suffix "_lasattr".
                    e.g., "mylasfile_lasattr.txt"

            -log_folder (string) (optional)
                - Folder path where the new log file
                    will be saved.
                - If no folder path is provided,
                    the log file will be saved in
                    the same folder as the input
                    las/laz file.

        Returns:
            None
        """
        now_string, now_string_filename = _now_strings()

        # Add the input filename to the log text
        log_text = _log_intro(self, now_string)

        # Add the public header attributes
        # to the log text
        log_text += _log_public_header(self)

        # Add the VLR attributes to the log text
        log_text += _log_vlr_evlr(self, _vlr_attr_prefix)

        # Add the EVLR attributes to the log text
        log_text += _log_vlr_evlr(self, _evlr_attr_prefix)

        # Add conclusion text
        log_text += _log_conclusion()

        # Set the log path according to
        # values provided or defaults described in docstring.
        # Add .txt extension to filename if it's not already there.
        log_path = _set_logpath(
            self,
            log_filename,
            log_folder,
            now_string_filename
        )

        # Write the log file
        with open(log_path, "w") as log:
            log.write(log_text)

        # Open the file to have a look!
        if auto_open:
            os.startfile(log_path)

    def remove_all_evlrs(self):
        """
        Change the attributes of the LasAttr instance so that when
        a new file is written, it doesn't have any EVLRs.
        """
        # Current number of EVLRs
        evlr_num = _get_evlr_num(self)

        # Delete each of the evlr attributes from the LasAttr instance
        # (this step is optional for purposes of directly writing a new
        # las/laz file without EVLRs, but makes a cleaner object instance)
        for j in range(evlr_num):
            for evlr_header_key in evlr_header_dict:
                delattr(
                    self,
                    _evlr_header_attr_name(j, evlr_header_key)
                )
            delattr(self, _evlr_value_attr_name(j))

        # Set these attribute values in the public header to zero:
        #   - start_waveform_data [32]
        #       - (waveform data is a type of EVLR)
        #   - start_first_evlr [33]
        #   - number_of_evlrs [34]
        for evlr_ref_attr_in_public_header in (32, 33, 34):
            setattr(
                self,
                list(public_header_dict)[evlr_ref_attr_in_public_header],
                0
            )

    def remove_all_vlrs(self):
        """
        Change the attributes of the LasAttr instance so that when
        a new file is written, it doesn't have any VLRs.
        """
        # Current number of VLRs
        vlr_num = _get_vlr_num(self)

        # Delete each of the vlr attributes from the LasAttr instance
        # (this step is optional for purposes of directly writing a new
        # las/laz file without VLRs, but makes a cleaner object instance,
        # especially if additional operations/analysis will be done
        # on the object instance before writing the new file)
        for i in range(vlr_num):
            for vlr_header_key in vlr_header_dict:
                delattr(
                    self,
                    _vlr_header_attr_name(i, vlr_header_key)
                )
            delattr(self, _vlr_value_attr_name(i))

        # Change the number of VLRs in the public header to zero
        setattr(
            self,
            list(public_header_dict)[15],
            0
        )

        # Change the offset_to_point_data, start_waveform_data,
        # and start_first_evlr attribute values to reflect
        # the new absence of VLRs.
        _auto_shift_offset_values(self)

    def remove_all_vlrs_evlrs_except_wkt(self, keep_evlrs=False):
        """
        Remove all VLRs and EVLRs, except those VLRs and EVLRs
        that contain WKT strings.

        To keep all EVLRs (which you'll want to do, for example,
        if there is waveform data) set the optional
        keep_evlrs parameter to True.
        """
        vlr_wkt, evlr_wkt = _parse_vlrs_evlrs_with_wkt(self)

        num_vlr_wkt = len(vlr_wkt)
        num_evlr_wkt = len(evlr_wkt)

        if num_vlr_wkt == 0 and num_evlr_wkt == 0:
            raise ValueError(
                f"{_dashline}"
                f"\nNo WKT entries in las/laz file!"
                f"\n{_dashline}"
            )

        vlr_num = _get_vlr_num(self)
        evlr_num = _get_evlr_num(self)

        while num_vlr_wkt != vlr_num or num_evlr_wkt != evlr_num:
            # Get the new index numbers and counts after vlr/evlr removal
            vlr_wkt, evlr_wkt = _parse_vlrs_evlrs_with_wkt(self)
            num_vlr_wkt = len(vlr_wkt)
            num_evlr_wkt = len(evlr_wkt)
            vlr_num = _get_vlr_num(self)
            evlr_num = _get_evlr_num(self)

            for i in range(vlr_num):
                # Remove the next non-WKT VLR
                if i not in vlr_wkt:
                    # The remove_vlr method renumbers VLRs
                    self.remove_vlr(i)
                    # Break the for loop to re-set indices and count numbers
                    break

            if not keep_evlrs:
                for j in range(evlr_num):
                    # Remove the next non-WKT EVLR
                    if j not in evlr_wkt:
                        # The remove_evlr method renumbers EVLRs
                        self.remove_evlr(j)
                        # Break the for loop to re-set indices and count numbers
                        break

    def remove_evlr(self, j):
        """
        Remove an EVLR of a given index (j) from a LasAttr object instance.

        Renumber remaining EVLRs in the LasAttr object instance.
        # TODO: add functionality for waveform data
        # (need to change the start_waveform_data attribute
        # to the correct new byte address when EVLRs
        # shift position due to removals)
        """
        # Current number of EVLRs
        evlr_num_orig = _get_evlr_num(self)

        # Delete each of the EVLR attributes from the LasAttr instance
        # for the given EVLR index
        for evlr_header_key in evlr_header_dict:
            delattr(
                self,
                _evlr_header_attr_name(j, evlr_header_key)
            )
        delattr(self, _evlr_value_attr_name(j))

        # Reduce the number of EVLRs in the public header to by one
        setattr(
            self,
            list(public_header_dict)[34],
            evlr_num_orig - 1
        )

        # If there aren't any EVLRs left, set the
        # start_first_evlr [33] and start_waveform_data [32]
        # attributes to zero (waveform data is a type of EVLR):
        if evlr_num_orig - 1 == 0:
            for evlr_ref_attr_in_public_header in (32, 33):
                setattr(
                    self,
                    list(public_header_dict)[evlr_ref_attr_in_public_header],
                    0
                )

        start_waveform_data = getattr(
            self,
            list(public_header_dict)[33]
        )

        if start_waveform_data > 0:
            raise TypeError(
                    "\nDoh! LasAttr remove_evlr() method"
                    "does not yet support waveform data,"
                    "\nbecause it needs to calculate the new"
                    "start location of the waveform data,"
                    "\nwhich is an attribute in the public header."
                    "\n\nUse remove_all_evlrs() instead,"
                    "\nor add this functionality to the method!"
            )

        # If there are EVLRs after the one removed...
        if j < evlr_num_orig - 1:
            # Shift the indices of the remaining EVLRs
            for evlr in range(j, evlr_num_orig - 1):
                for evlr_header_key in evlr_header_dict:
                    setattr(
                        self,
                        _vlr_header_attr_name(
                            evlr,
                            evlr_header_key
                        ),
                        getattr(
                            self,
                            _vlr_header_attr_name(
                                evlr + 1,
                                evlr_header_key
                            )
                        )
                    )
                setattr(
                    self,
                    _vlr_value_attr_name(evlr),
                    getattr(
                        self,
                        _vlr_value_attr_name(evlr + 1)
                    )
                )

            # Drop the now duplicate final EVLR
            for evlr_header_key in evlr_header_dict:
                delattr(
                    self,
                    _vlr_header_attr_name(
                        evlr_num_orig - 1,
                        evlr_header_key
                    )
                )
            delattr(
                self,
                _evlr_value_attr_name(evlr_num_orig - 1)
            )

    def remove_vlr(self, i):
        """
        Remove a VLR of a given index (i) from a LasAttr object instance.

        Renumber remaining VLRs in the LasAttr object instance.

        Update the offset attribute values in the public header accordingly.
        """
        # Current number of VLRs
        vlr_num_orig = _get_vlr_num(self)

        # Delete each of the vlr attributes from the LasAttr instance
        # for the given VLR index
        for vlr_header_key in vlr_header_dict:
            delattr(
                self,
                _vlr_header_attr_name(i, vlr_header_key)
            )
        delattr(self, _vlr_value_attr_name(i))

        # Reduce the number of VLRs in the public header to by one
        setattr(
            self,
            list(public_header_dict)[15],
            vlr_num_orig - 1
        )

        # If there are VLRs after the one removed...
        if i < vlr_num_orig - 1:
            # Shift the indices of the remaining VLRs
            for vlr in range(i, vlr_num_orig - 1):
                for vlr_header_key in vlr_header_dict:
                    setattr(
                        self,
                        _vlr_header_attr_name(
                            vlr,
                            vlr_header_key),
                        getattr(
                            self,
                            _vlr_header_attr_name(
                                vlr + 1,
                                vlr_header_key
                            )
                        )
                    )
                setattr(
                    self,
                    _vlr_value_attr_name(vlr),
                    getattr(
                        self,
                        _vlr_value_attr_name(vlr + 1)
                    )
                )

            # Drop the now duplicate final VLR
            for vlr_header_key in vlr_header_dict:
                delattr(
                    self,
                    _vlr_header_attr_name(vlr_num_orig - 1, vlr_header_key)
                )
            delattr(self, _vlr_value_attr_name(vlr_num_orig - 1))

            # Update the offset_to_point_data, start_waveform_data,
            # and start_first_evlr attribute values
            _auto_shift_offset_values(self)

    def replace_wkt_with_compound_wkt(self, epsg=6647):
        """
        Replace a non-compound (horizontal-only) WKT VLR or EVLR
        in a las/laz file with a compound (horizontal-and-vertical)
        WKT VLR or EVLR, using the input epsg value
        for the vertical datum.

        Default vertical datum is EPSG 6647, for CGVD2013.
        https://epsg.io/6647
        """
        # Identify which VLR and EVLRs have WKT strings
        vlr_evlr_with_wkt = self.find_wkt()

        num_wkt_strings = len(vlr_evlr_with_wkt)

        if num_wkt_strings == 0:
            raise ValueError(
                f"{_dashline}"
                f"\nNo WKT entries in las/laz file!"
                f"\n{_dashline}"
            )
        else:
            vlr_evlr_with_wkt_not_compound = []
            for item in vlr_evlr_with_wkt:
                crs_obj, _ = _crs_obj_from_prefix_and_index(
                    self,
                    item[0],
                    item[1]
                )
                if not crs_obj.is_compound:
                    vlr_evlr_with_wkt_not_compound.append(item)

        num_not_compound_wkt = len(vlr_evlr_with_wkt_not_compound)

        # If there were no horizontal-only WKT entries,
        # there is nothing to replace.
        if num_not_compound_wkt == 0:
            raise ValueError(
                f"\n{_dashline}"
                f"\nNo horizontal-only WKT entries in las/laz file!"
                f"\n{_dashline}"
            )

        for not_compound_wkt in vlr_evlr_with_wkt_not_compound:
            prefix = not_compound_wkt[0]
            k = not_compound_wkt[1]

            # Make a pyproj CRS object out of the non-compound WKT string
            orig_crs_obj, wkt_string = _crs_obj_from_prefix_and_index(self, prefix, k)

            # Define the name of the new CRS as it will be written
            # at the beginning of the WKT string
            if epsg == 6647:
                epsg_text = "CGVD2013 height"
            else:
                epsg_text = f"EPSG {str(epsg)} height"
            new_crs_name = f"{orig_crs_obj.name} + {epsg_text}"

            # Create a new, compound CRS object using the original horizontal
            # WKT string and the EPSG code provided as a parameter to this method
            # (default value is 6647, CGVD2013)
            new_crs = pyproj.crs.CompoundCRS(
                new_crs_name,
                components=[wkt_string, epsg]
            )

            # Create the new WKT string for the new compound CRS
            # Note that the default WKT version for to_wkt() is WKT2_2019
            # See: https://pyproj4.github.io/pyproj/dev/api/crs/crs.html#id2
            # (search for CRS.to_wkt on the above page)
            # Possible WKT versions:
            # https://pyproj4.github.io/pyproj/dev/api/enums.html#pyproj.enums.WktVersion
            # https://pyproj4.github.io/pyproj/dev/api/crs/crs.html#id2
            version = pyproj.enums.WktVersion.WKT1_GDAL
            new_wkt = new_crs.to_wkt(version=version)

            # Find the appropriate value attribute name
            if prefix == _vlr_attr_prefix:
                value_attr_name = _vlr_value_attr_name(k)
            elif prefix == _evlr_attr_prefix:
                value_attr_name = _evlr_value_attr_name(k)

            # Replace the non-compound WKT value with the new compound value
            # in the LasAttr attribute.
            # Note: the various length and offset attributes that are affected
            # by this change are updated automatically through logic checks
            # in __setattr__.
            setattr(
                self,
                value_attr_name,
                new_wkt
            )

    def write_output(
        self,
        output_laslaz_path,
        update_generating_software=True,
        update_system_id=True
    ):
        """
        Write a new las/laz file with current attributes
        of LasAttr instance in a specified location.
        """
        if update_generating_software:
            # Update the generating software in the public header
            # to the name of this software, defined as a global
            # variable near the top of this module.
            setattr(
                self,
                list(public_header_dict)[10],
                lasattr_software_name
            )

        if update_system_id:
            # Update system_id to "MODIFICATION", per las spec 1.4, p. 7
            # https://www.asprs.org/wp-content/uploads/2010/12/LAS_1_4_r13.pdf
            setattr(
                self,
                list(public_header_dict)[9],
                "MODIFICATION"
            )

        # Copy the original file to the output location,
        # ready to be overwritten.
        _prep_output_file(
            self,
            output_laslaz_path
        )

        # Over-write the data in the output file with the LasAttr object attributes
        with open(output_laslaz_path, "r+b") as outfile:
            # FOR TESTING ONLY - time how long it takes to write a file
            # print(f"{_dashline}\nStarting write process...")
            # start_write = datetime.now()

            # FOR TESTING ONLY - print the original file size
            # outfile.seek(0)
            # print(f"Length of original file: {len(outfile.read())}")

            # Read all of the original point data and any EVLRs
            # before overwriting anything
            original_offset_to_point_data = getattr(
                self,
                list(other_attributes_dict)[1]
            )
            outfile.seek(original_offset_to_point_data)
            original_point_data_onward = outfile.read()

            # Set cursor to the beginning of the file
            outfile.seek(0)

            # Overwrite public header attributes in las/laz file
            _write_public_header(self, outfile)

            # Set cursor to the beginning of VLRs (for las 1.4, this will
            # always be 375 and we're already in the right position,
            # but other versions may be different.
            header_size = getattr(
                self,
                list(public_header_dict)[13]
            )
            outfile.seek(header_size)

            # Overwrite vlr header and value attributes in las/laz file
            _write_vlrs(self, outfile)

            # Re-write the point data and any original EVLRs after the new VLRs
            # (if the length of the VLRs changed, this data is re-positioned
            # in the new file directly after the VLRs)
            outfile.write(original_point_data_onward)

            # Get the las version as a float value
            las_version = _las_version_float(self)

            # Overwrite evlr header and value attributes in las/laz file
            if las_version >= 1.3:
                _write_evlrs(
                    self,
                    outfile
                )

            # Truncate any old point or evlr data
            # that are remnants from the original file.
            outfile.truncate()

            # FOR TESTING ONLY - print the new file size
            # outfile.seek(0)
            # print(f"Length of newly overwritten file: {len(outfile.read())}")

            # FOR TESTING ONLY - time how long it takes to write a file
            # end_write = datetime.now()
            # write_time = end_write - start_write
            # print(f"Time to write file: {write_time}")


# ------------------------------------------------------------------------------
# CHECK THE GLOBAL VARIABLES IN THIS MODULE ARE OKAY
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    # --------------------------------------------------------------------------
    # Check software name length

    def _check_software_name(lasattr_software_name):
        lasattr_software_name_length = len(lasattr_software_name)

        if lasattr_software_name_length > 32:
            raise ValueError(
                f"\n{_dashline}"
                f"\nMax length of software name is 32 characters."
                f"\nReduce string '{lasattr_software_name}' by "
                f"{lasattr_software_name_length - 32} characters."
                f"\n{_dashline}"
            )

    _check_software_name(lasattr_software_name)

    # --------------------------------------------------------------------------
    # Check prefixes okay

    def _check_prefix_format(_prefixes_to_check):
        bad_prefix = False

        error_message = ""

        for prefix in (_prefixes_to_check):
            if _split_character in prefix:
                error_message += (
                    f"\n{_dashline}\n"
                    f"\nPrefix in {__file__} may not contain the split character."
                    f"\nPrefix: '{prefix}'"
                    f"\nSplit character: '{_split_character}'"
                )
                bad_prefix = True

        if bad_prefix:
            raise ValueError(
                f"{error_message}"
                f"\n{_dashline}"
            )

    _prefixes_to_check = (
        _vlr_attr_prefix,
        _evlr_attr_prefix
    )

    _check_prefix_format(_prefixes_to_check)

    # --------------------------------------------------------------------------
    # Check dictionary key names

    # The LasAttr class definition uses the vlr attribute prefix
    # and evlr prefix as logical checks when setting attribtues,
    # so those prefixes not permitted in the public_header_dict,
    # vlr_header_dict, and evlr_header_dict dictionary keys.

    def _check_dict_keys(_dicts_to_check, _forbidden_key_beginnings):
        _bad_key = False

        error_message = ""

        for _each_dict in _dicts_to_check:
            for _each_key in _each_dict:
                for _each_beginning in _forbidden_key_beginnings:
                    if _each_key.startswith(_each_beginning):
                        error_message += (
                            f"\n{_dashline}"
                            f"\nKey name may not start with '{_each_beginning}'; "
                            f"\nplease fix key '{_each_key}' in and try again."
                        )
                        _bad_key = True
                    if _value_attr_root in _each_key:
                        error_message += (
                            f"\n{_dashline}"
                            f"\nKey name may not contain '{_value_attr_root}'; "
                            f"\nplease fix key '{_each_key}' and try again."
                        )
                        _bad_key = True

        if _bad_key:
            raise ValueError(
                f"{error_message}"
                f"\n{_dashline}"
            )

    _dicts_to_check = (
        public_header_dict,
        vlr_header_dict,
        evlr_header_dict,
        other_attributes_dict
    )

    _forbidden_key_beginnings = (
        _vlr_attr_prefix,
        _evlr_attr_prefix
    )

    _check_dict_keys(_dicts_to_check, _forbidden_key_beginnings)

    # --------------------------------------------------------------------------

    print(
        f"\n{_dashline}"
        f"\nModule:\t{__file__}"
        f"\nrun as main; global variables passed all checks!"
        f"\n{_dashline}"
    )
