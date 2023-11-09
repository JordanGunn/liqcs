# ------------------------------------------------------------------------------
# How to create executables
#
# Instructions for using this .spec file to create an executable
# in the RSGE wiki:
#
# https://bcgov.sharepoint.com/teams/01112/_layouts/OneNote.aspx?id=%2Fteams%2F01112%2FShared%20Documents%2FQC%20Team%2FRSGE%20Wiki&wd=target%28Python%2FMaking%20Executables%20%28.exe%5C%29.one%7C10000CB6-8674-4968-A78A-52FE5089DAE5%2F0.%20Making%20Executables%3A%20Introduction%7C9CEC57FB-34F4-417F-B6E8-D349251100C5%2F%29
#
# ------------------------------------------------------------------------------

# -*- mode: python ; coding: utf-8 -*-

from glob import glob

block_cipher = None


# ------------------------------------------------------------------------------
# Variables to update before running pyinstaller

# Update with the latest version number
# Remember to also update in config.py
executable_name = 'LiQCS_v.1.5.0'

# Update this variable to point to the folder containing your python.exe file:
python_environment_path = 'C:\\Users\\SFLOYD\\AppData\\Local\\Programs\\Python\\Python39'

# Update this variable to your local repo path
local_repo_path = 'C:\Git_Hub\RSGE_codebase'

# ------------------------------------------------------------------------------
# Paths

paths = [
    os.path.join(local_repo_path, 'LiDAR/lasattr'),
    os.path.join(local_repo_path, 'LiDAR/corrupt_checks'),
    'density_analysis'
]

# ------------------------------------------------------------------------------
# Hidden imports

hidden_imports = [
    'tkinter',
    'fiona',
    'gdal',
    'shapely',
    'shapely.geometry',
    'pyproj',
    'geopandas',
    'pytest',
    'pandas',
    'fiona._shim',
    'fiona.schema',
    'multiprocessing',
    'subprocess',
    'cryptography.hazmat.primitives.kdf.pbkdf2',  # Used by oracledb
    'rasterio._shim',
]

# Add all the .py files in rasterio to the hidden imports list.
# Reference:
# https://stackoverflow.com/questions/53149750/something-wrong-with-how-im-bundling-rasterio-into-an-executable
site_packages_dir = os.path.join(python_environment_path, 'Lib', 'site-packages')
rasterio_dir = os.path.join(site_packages_dir, 'rasterio')
rasterio_imports_paths = glob(
    os.path.join(rasterio_dir, '*.py')
)
for module in rasterio_imports_paths:
    module_filename = os.path.split(module)[-1]
    module_filename = 'rasterio.' + module_filename.replace('.py', '')
    hidden_imports.append(module_filename)

# -------------------------------------------------------------------------------
# Non-binary files

data_to_include = [
    (os.path.join(site_packages_dir, 'osgeo\\data\\proj\\proj.db'), '.'),
    (os.path.join(site_packages_dir, 'geopandas'),'geopandas'),
    (os.path.join(site_packages_dir, 'geopandas\\datasets'), 'geopandas\\datasets')
]

# ------------------------------------------------------------------------------
# Binary files

binaries_to_include = [
    ('C:\\LAStools\\bin', 'LAStools'),
    ('Z:\\PYTHON_SETUP\\density_analysis_script_supporting_files\\BC_Ocean_shp', 'BC_Ocean'),
    (os.path.join(local_repo_path, 'boilerplate\\png\\BCID_GeoBC_RGB_sanBPOE_pos.png'), 'boilerplate\\png')
]

# ------------------------------------------------------------------------------

a = Analysis(
    ['liqcs_gui.py'],
    pathex=paths,
    binaries=binaries_to_include,
    datas=data_to_include,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=['hook.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=executable_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True, 
    icon=os.path.join(local_repo_path, 'boilerplate\\ico\\BC.ico')
)
