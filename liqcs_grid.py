import os
import sys
import laspy
import getopt
import numpy as np

from osgeo import osr
from osgeo import gdal
from math import floor, ceil

from liqcs_const import ImageFormats


class Grid:
    """
    Class to generate density and/or intensity grids from lidar.
    """

    def __init__(self):
        self.data_in = None
        self.data_out = None
        self.cell_size = 1
        self.rows = 0
        self.cols = 0
        self.NO_DATA_VALUE = 0
        self.crs = ""
        self.min = None
        self.max = None
        self.verbose = False
        self.err = os.getcwd()

    def set_err(self, err_dir: str):
        """
        Set the directory for error logging.

        @param err_dir: Directory for err_log destination.
        @return: None
        """
        if os.path.exists(err_dir) and os.path.isdir(err_dir):
            self.err = err_dir

    def read_lidar(self, filepath: str):

        """
        Read LAS/LAZ file, getting file object.

        @param filepath: Path to input LAS/LAZ file
        @return:
        """

        # handle laz file if it is encountered

        # may need to add meipass here
        if 'laz' in os.path.splitext(filepath)[1]:
            if self.verbose:
                print('\nDecompressing LAZ file...\n')
            try:
                self.data_in = laspy.read(
                    filepath,
                    # Lazrs does not support waveform data.
                    # At writing, we do not collect waveform data.
                    # If we start to collect waveform data, we'll
                    # have to find a new way to decompress.
                    # Or perhaps in the future lazrs will support waveform data.
                    # But, if the script is having trouble decompressing
                    # waveform data, Lazrs may be the culprit.
                    laz_backend=laspy.LazBackend.LazrsParallel
                )
                if self.verbose:
                    print('Finished decompressing')

            except Exception as e:
                print(f'Error opening {filepath}, file may be corrupt...\n')
                with open(os.path.join(self.err, "lidar_read_errors.txt"), mode='a+') as f:
                    f.write(f"{filepath}: {e}\n")

        else:
            try:
                self.data_in = laspy.read(filepath)
            except Exception as e:
                print(f'Error opening {filepath}, file may be corrupt...\n')
                with open(os.path.join(self.err, "lidar_read_errors.txt"), mode='a+') as f:
                    f.write(f"{filepath}: {e}\n")
        if self.verbose:
            print(f'Created laspy file object from {filepath}')

        if self.data_in:
            self.__set_min_max()

    def set_crs(self, epsg_code: int):

        """
        Set the Coordinate Reference System (CRS) as a Well-Known Text string.

        @param epsg_code: EPSG code as a string.
        """

        sr = osr.SpatialReference()  # SpatialReference object instantiation.
        sr.ImportFromEPSG(epsg_code)  # pass in the epsg code

        self.crs = sr.ExportToWkt()

    def compute(self, cls: int = None, last_return: bool = False, intensity: bool = False):
        """
        Create rasterized data from loaded LAS/LAZ file.

        @precondition: User must make a valid call to read_lidar(), such that Grid->data points to valid LAS/LAZ file.
        @param cls: List of valid class numbers as defined by global GridClass object (e.g. GRID_CLASS.GROUND)
        @param last_return: Bool value indicating whether the points should be filtered by last return.
        @param intensity: Bool value indicating whether the resulting data should be derived from intensity values.
        """

        self.NO_DATA_VALUE = 0

        # Get x and y axis distances (m) from las file
        dist_x, dist_y = self.get_las_xy_dimensions()

        # calculate number of columns for raster grid
        self.cols = int(dist_x / self.cell_size)
        # self.col += 1
        self.rows = int(dist_y / self.cell_size)
        # self.row += 1

        # Create empty numpy array to write values to
        count = np.zeros((self.rows, self.cols)).astype(np.int32)

        # Apply -1 to have negative y resolution for raster
        ycell = -1 * self.cell_size

        # apply filter to points based on class and/or last return
        if intensity:
            las_x, las_y = self.data_in.x, self.data_in.y
        else:
            las_x, las_y = self.filter_points(cls, last_return)

        # Scale or "project" values  of lidar data to grid,
        scale_x = (las_x - self.min[0]) / self.cell_size
        scale_y = (las_y - self.min[1]) / ycell

        # Change type to integer and save as variables to use for index values
        ind_x = scale_x.astype(np.int32)
        ind_y = scale_y.astype(np.int32)

        if intensity:
            self.__compute_intensity(count, ind_x, ind_y)
        else:
            self.__compute_density(count, ind_x, ind_y)

        self.data_out = np.delete(self.data_out, 0, axis=0)

    def filter_points(self, cls: int, last_return: bool) -> tuple:
        """
        @param cls: Integer indicating class number you wish to filter by.
        @param last_return: Boolean indicating whether to filter yb last return.
        @return:
        """

        las = self.data_in
        las_x, las_y = las.x, las.y

        if last_return and cls:
            las_x = las_x[(las.num_returns == las.return_num) & (las.classification == cls)]
            las_y = las_y[(las.num_returns == las.return_num) & (las.classification == cls)]

        elif last_return:
            las_x = las_x[las.num_returns == las.return_num]
            las_y = las_y[las.num_returns == las.return_num]

        elif cls:
            las_x = las_x[las.classification == cls]
            las_y = las_y[las.classification == cls]

        return las_x, las_y

    def __compute_intensity(self, count, ind_x, ind_y):
        """
        Compute intensity from Grid->data.

        A private method for encapsulation of density computation.
        """
        int_sum = np.zeros((self.rows, self.cols)).astype(np.int32)
        # Runtime bottleneck - This is O(n) WRT the number of points in the point cloud
        # We can't do better than this without sacrificing accuracy
        for x, y, i in np.nditer([ind_x, ind_y, self.data_in.intensity]):
            count[y, x] += 1
            int_sum[y, x] += i
        # Fill areas lacking data with 1 to avoid divide by zero error
        count_no_zero = (np.where(count > 0, count, 1)).astype(np.int32)
        # calculate intensity
        int_avg = (int_sum / count_no_zero).astype(np.int32)
        # Interpolate 0 values in array to avoid any holes in data
        self.data_out = np.where(
            np.logical_and(int_avg > 1, int_avg != 0),
            int_avg, self.NO_DATA_VALUE
        ).astype(np.int32)

    def __compute_density(self, count, ind_x, ind_y):
        """
        Compute density from Grid->data.

        A private method for encapsulation of density computation.
        """

        # Runtime bottleneck - This is O(n) WRT the number of points in the point cloud
        # We can't do better than this without sacrificing accuracy
        for x, y in np.nditer([ind_x, ind_y]):
            count[y, x] += 1
        # Fill areas lacking data with keyword argument specified no data value
        count_no_data = (np.where(count > 0, count, self.NO_DATA_VALUE)).astype(np.int32)
        # calculate density
        self.data_out = (count_no_data / self.cell_size).astype(np.int32)

    def write(self, out_name: str = "", out_fmt: str = "tif"):
        """
        Write rasterized lidar data to file.

        @param out_name: Output file name.
        @param out_fmt: Output file format [asc | tif]
        """

        if out_fmt == ImageFormats.ESRI_ASCII:
            # Create ASCII header
            header = self.create_ascii_header()

            # Open output file, write header, save array to output file
            if self.data_out is not None:
                with open(out_name, "wb") as f:
                    f.write(bytes(header, 'UTF-8'))
                    # fmt string to output integers only
                    np.savetxt(f, self.data_out, fmt="%.0f")
            else:
                raise Exception('No array attribute found for grid object')

        elif (out_fmt == ImageFormats.GEOTIFF) or (out_fmt == ImageFormats.GEOTIF):
            # Create new raster and write array to image

            # Get geotiff driver
            driver = gdal.GetDriverByName('GTiff')

            if self.data_out is not None:
                # Create raster object
                out_img = driver.Create(
                    out_name, self.cols, self.rows, 1, gdal.GDT_Int32,
                    options=['COMPRESS=LZW', 'NUM_THREADS=ALL_CPUS']
                )

                # Set positional parameters
                out_img.SetGeoTransform(
                    (
                        floor(self.min[0]), self.cell_size, 0,
                        ceil(self.max[1]), 0, self.cell_size * -1
                    )
                )

                out_band = out_img.GetRasterBand(1)  # get band from raster object
                out_band.SetNoDataValue(self.NO_DATA_VALUE)
                out_band.WriteArray(self.data_out)  # write array to raster band
                # write wkt proj metadata to image if it exists
                if self.crs is not None:
                    out_img.SetProjection(self.crs)
                out_band.FlushCache()
                out_img = None  # Necessary to free dynamically allocated memory created by GDAL - do not remove
            else:
                raise Exception('No array attribute found for grid object')
        else:
            raise Exception(f'Invalid format: {out_fmt}')

    def create_ascii_header(self) -> str:
        """
        @precondition: User must first make a successful call to create_grid()

        @return: ESRI ASCII header as a string.
        """

        header = "ncols {}\n".format(self.data_out.shape[1])
        header += "nrows {}\n".format(self.data_out.shape[0])
        header += "xllcorner {}\n".format(floor(self.min[0]))
        header += "yllcorner {}\n".format(ceil(self.min[1]))
        header += "cellsize {}\n".format(self.cell_size)
        header += "NODATA_value {}\n".format(self.NO_DATA_VALUE)

        return header

    def __set_min_max(self):
        """
        Set the minimum and maximum X,Y values for the grid surface.

        Private helper method to set the minimum and maximum
        values for the resulting grid sruface.
        """

        las = self.data_in

        self.min = [
            floor(las.header.x_min),
            floor(las.header.y_min)
        ]
        self.max = [
            floor(las.header.x_max) + 1,
            floor(las.header.y_max) + 1
        ]

    def get_las_xy_dimensions(self) -> tuple:
        """
        Get the x and y dimensions of a las file,
        based on its max and min coordinates.
        """
        dist_x = self.max[0] - self.min[0]
        dist_y = self.max[1] - self.min[1]

        return dist_x, dist_y

    def reset(self):

        """
        Reset all computational related properties.

        Resets all properties of a Grid object related to
        grid computation from a LAS/LAZ file. NOTE: this
        method will maintain the reference to an opened
        LAS/LAZ. Functionally, the intention of this method
        is to enable reading/decompression of a file once,
        while enabling the ability to produce multiples
        kinds of grids from a single object.
        """

        self.data_out = None
        self.cell_size = 1
        self.rows = 0
        self.cols = 0

    def close_lidar(self):
        """
        Remove reference to LAS/LAZ file owned by the class attribute
        Grid->data_in.
        """

        if self.data_in:
            self.data_in = None


def cli(opts: list):
    """
    Handle command-line arguments.

    @param opts: Command-line passed to liqcs_grid.py
    """

    in_file, out_dir = "", ""
    density, intensity = False, False
    last_return, class_number = False, None

    for opt, arg in opts:

        if opt in ("-h", "--help"):
            cli_help()

        elif opt in ("-r", "--read_file"):
            in_file = arg

        elif opt in ("-w", "--write_dir"):
            out_dir = arg

        elif opt in ("-c", "--class_number"):
            class_number = int(arg)

        elif opt in ("-l", "--last_return"):
            last_return = True

        elif opt in ("-d", "--density"):
            density = True

        elif opt in ("-i", "--intensity"):
            intensity = True

    if len(in_file) > 0:
        grid = Grid()
        grid.read_lidar(in_file)

        grid.compute(
            cls=class_number,
            intensity=intensity,
            last_return=last_return
        )

        if len(out_dir) > 0:
            file_name = (in_file.split(os.sep)[-1].split(".")[0]) + ".tif"
            out = os.path.join(out_dir, file_name)
        else:
            out = in_file.split(".")[0].join(".tif")

        grid.write(out)


def cli_help():

    """
    Print CLI menu to stdout.
    """

    print("\n liqcs_grid.py -r input.la{s|z} [-w out/dir/] [-c {1 .. 99}] [-l] [-i]")
    print("\t-l, --last_return:\n\t\tFilter by last return.")
    print("\t-c, --class_number:\n\t\tFilter by classification. User must pass argument as number (e.g. '2').")
    print("\t-d, --density:\n\t\tMake density grid.")
    print("\t-i, --intensity:\n\t\tMake intensity grid.")
    print("\t-r, --read_file:\n\t\tInput LAS/LAZ file.")
    print("\t-o, --write_dir:\n\t\tOutput raster directory. For now, only TIFF format "
          "\n\t\tis provided. Also note that if no out file is provided,"
          "\n\t\toutput will simply adopt the name of the in_file with"
          "\n\t\ttan extension of .tif")

    sys.exit()


def cli_opts() -> list:

    """
    Get the constant for CLI options.

    @return: list of CLI options.
    """

    opts = [
            "help"
            "in_file",
            "out_dir",
            "last_return",
            "class_number",
            "density",
            "intensity"
        ]

    return opts


def cli_flags() -> str:

    """
    Get the constant CLI flags.

    @return: String of formatted CLI flag options.
    """

    flags = "hr:w:l:c:di"

    return flags


def main(argv: list):
    opts, args = getopt.getopt(
        argv, cli_flags(), cli_opts()
    )
    cli(opts)


if __name__ == "__main__":
    main(sys.argv[1:])
