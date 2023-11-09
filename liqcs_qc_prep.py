# QC Prep test; part of LiQCS.


from shutil import copy2, rmtree
from glob import glob
from math import ceil

import random
import getopt
import sys
import os

# Local imports
import liqcs_config


def run_qc_prep(out_dir, sample_size, file_list):

    """
    Copy a percentage of lidar files from a list of
    lidar file paths to a subfolder in an output directory.

    Number of files copied is always rounded up (math.ceil)
    from the percentage value.

    @param out_dir: Output directory for qc_prep results.
    @param sample_size: Percentage of files to operate on.
    @param file_list: List of .las/.laz file paths
    """

    print(
        f"{liqcs_config.dashline()}QC Prep running...",
        flush=True
    )
    num_las_laz_files_input_dir = len(file_list)
    qc_prep_path = os.path.join(out_dir, "QC_Prep")

    # Delete any previous version of QC Prep folder and its contents
    if os.path.exists(qc_prep_path):
        rmtree(qc_prep_path)

    # Make the QC Prep folder
    os.mkdir(qc_prep_path)

    # Calculate the number of files to copy.
    # Round up to the nearest integer.
    num_files_to_copy = ceil(num_las_laz_files_input_dir * sample_size / 100)

    # Initialize the list of indices chosen by the random number generator
    index_list = []

    # Make .txt file with info about what files are copies
    lidar_sample_info_file = os.path.join(qc_prep_path, "LiDAR_Sample_Info.txt")
    with open(os.path.join(qc_prep_path, lidar_sample_info_file), mode="w") as out:
        print(
            f"Total las/laz files provided: {num_las_laz_files_input_dir}"
            f"\nPercent sampled: {sample_size}%"
            f"\nFiles copied: {num_files_to_copy}\n",
            file=out
        )

    for _ in range(num_files_to_copy):
        while True:
            # Generate a random number
            random_index = random.randrange(0, num_las_laz_files_input_dir)

            # If the random number hasn't been used as an index yet
            if random_index not in index_list:
                # Add the random number to the chosen list of indices
                index_list.append(random_index)

                # Copy file with that index number into the QC Prep folder
                copied_filepath = os.path.join(
                    qc_prep_path, os.path.basename(file_list[random_index])
                )
                copy2(file_list[random_index], copied_filepath)

                # Add the name of the copied file to the .txt report file
                with open(lidar_sample_info_file, mode='a') as out:
                    print(os.path.basename(file_list[random_index]), file=out)
                break
            else:
                continue

    print("\nQC Prep complete!\n", flush=True)


def cli_opts() -> list:

    """
    Get the constant for CLI options.

    @return: list of CLI options.
    """

    opts = [
            "help"
            "read_dir",
            "write_dir",
            "sample_size"
        ]

    return opts


def cli_flags() -> str:

    """
    Get the constant CLI flags.

    @return: String of formatted CLI flag options.
    """

    flags = "hr:w:s:"

    return flags


def cli_help():

    """
    Print CLI menu to stdout.
    """

    print("\n liqcs_qc_prep.py -r <input/dir/> -w <output/dir/> -s <percentage>")
    print("\t-r, --read_dir:\n\t\tInput LAS/LAZ file.")
    print("\t-w, --write_dir:\n\t\tOutput directory.")
    print("\t-s, --sample_size:\n\t\tSample size (percentage) of las/laz files to copy from read_dir")

    sys.exit()


def cli(opts: list):
    """
    Handle command-line arguments.

    @param opts: Command-line passed to liqcs_grid.py
    """

    read_dir, write_dir = None, None
    sample_size = None

    for opt, arg in opts:

        if opt in ("-h", "--help"):
            cli_help()

        elif opt in ("-r", "--read_dir"):
            read_dir = arg

        elif opt in ("-w", "--write_dir"):
            write_dir = arg

        elif opt in ("-s", "--sample_size"):
            sample_size = int(arg)

        if (not read_dir) or (not write_dir) or (not sample_size):
            print("\nSupplied invalid arguments...")
            cli_help()  # program will terminate

        las_laz_path_list = glob(os.path.join(read_dir, "*.laz"))
        las_laz_path_list.extend(
            glob(os.path.join(read_dir, "*.las"))
        )

        run_qc_prep(write_dir, sample_size, read_dir)


def main(argv: list):
    opts, args = getopt.getopt(
        argv, cli_flags(), cli_opts()
    )
    cli(opts)


if __name__ == "__main__":
    main(sys.argv[1:])
