import struct


def parse_header(filename: str, verbose=False) -> dict:

    """
    Parse input LAS/LAS file into dict object.

    @param filename: Input LAS/LAZ filepath.
    @param verbose: Write messages to stdout (True/False)
    @return: Dictionary containing LAS/LAZ file header contents
    """

    headerstruct = (
        ('filesig', 4, 'c', 4),
        ('filesourceid', 2, 'H', 1),
        ('reserved', 2, 'H', 1),
        ('guid1', 4, 'L', 1),
        ('guid2', 2, 'H', 1),
        ('guid3', 2, 'H', 1),
        ('guid4', 8, 'B', 8),
        ('vermajor', 1, 'B', 1),
        ('verminor', 1, 'B', 1),
        ('sysid', 32, 'c', 32),
        ('gensoftware', 32, 'c', 32),
        ('fileday', 2, 'H', 1),
        ('fileyear', 2, 'H', 1),
        ('headersize', 2, 'H', 1),
        ('offset', 4, 'L', 1),
        ('numvlrecords', 4, 'L', 1),
        ('pointformat', 1, 'B', 1),
        ('pointreclen', 2, 'H', 1),
        ('numptrecords', 4, 'L', 1),
        ('numptbyreturn', 20, 'L', 5),
        ('xscale', 8, 'd', 1),
        ('yscale', 8, 'd', 1),
        ('zscale', 8, 'd', 1),
        ('xoffset', 8, 'd', 1),
        ('yoffset', 8, 'd', 1),
        ('zoffset', 8, 'd', 1),
        ('xmax', 8, 'd', 1),
        ('xmin', 8, 'd', 1),
        ('ymax', 8, 'd', 1),
        ('ymin', 8, 'd', 1),
        ('zmax', 8, 'd', 1),
        ('zmin', 8, 'd', 1),
        ('waveform', 8, 'Q', 1),
        ('firstEVLR', 8, 'Q', 1),
        ('numEVLR', 4, 'L', 1),
        ('exnumbptrec', 8, 'Q', 1),
        ('exnumbyreturn', 120, 'Q', 15)
    )

    header = {'infile': filename}

    with open(filename, 'rb') as fh:
        for i in headerstruct:
            if i[2] == 'c':
                value = fh.read(i[1])
            elif i[3] > 1:
                value = struct.unpack(
                    '=' + str(i[3]) + i[2],
                    fh.read(i[1])
                )
            else:
                value = struct.unpack(
                    '=' + i[2],
                    fh.read(i[1])
                )[0]
            if verbose:
                print(i[0] + '\t', i[2] + '\t', value)

            header[i[0]] = value

    # if laz file, subtract 128 from the point data format
    # (laz compression adds 128 to the point format)
    if header['infile'].endswith('.laz'):
        header['pointformat'] = header['pointformat'] - 128

    return header
