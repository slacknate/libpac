import os
import struct

PAC_PREFIX = b"FPAC"


def _unpack_from(fmt, data):
    """
    Helper function to call and return the result of struct.unpack_from
    as well as any remaining packed data that exists in our bytestring following what was unpacked.
    """
    offset = struct.calcsize(fmt)
    unpacked = struct.unpack_from(fmt, data)
    remaining = data[offset:]
    return unpacked, remaining


def _parse_header(pac_contents):
    """
    Parse the header of a PAC file.
    We do basic validation of the header with the PAC_PREFIX constant.
    """
    if not pac_contents.startswith(PAC_PREFIX):
        raise ValueError("Not a valid PAC file!")

    remaining = pac_contents[len(PAC_PREFIX):]

    (data_start, _, file_count), remaining = _unpack_from("III", remaining)
    (_, meta_chunk_size, __, ___), remaining = _unpack_from("IIII", remaining)

    return data_start, meta_chunk_size, file_count, remaining


def _get_format(meta_chunk_size):
    """
    The chunk size is seemingly not just the length of data allocated to file names.
    The file info format seems to be 2*`meta_chunk_size` (chunk size comes from the header)
    where the first half is the file name and the second half is a series of integers.
    Determine what struct format specifier we need to unpack this data correctly.
    """
    int_size = struct.calcsize("I")
    num_ints = meta_chunk_size / int_size

    if not num_ints.is_integer():
        raise ValueError(f"Meta data chunk size is not a multiple of {int_size}! Cannot parse file info!")

    num_ints = int(num_ints)
    return f"{meta_chunk_size}s" + "I" * num_ints


def _enumerate_files(pac_contents, file_count, meta_chunk_size):
    """
    Create a list that describes all embedded files included in our PAC file.
    It is a list of tuples that contain the file name, file ID (which is just
    an index that is incremented with each file), the file offset (where the file
    data starts), and the size of the file.
    """
    file_list = []
    remaining = pac_contents
    fmt = _get_format(meta_chunk_size)

    for _ in range(file_count):
        unpacked, remaining = _unpack_from(fmt, remaining)

        file_name = unpacked[0]
        file_id = unpacked[1]
        file_offset = unpacked[2]
        file_size = unpacked[3]

        file_name = file_name.rstrip(b"\x00").decode("latin-1")
        file_list.append((file_name, file_id, file_offset, file_size))

    return file_list, remaining


def _extract_files(pac_contents, file_list, out_dir):
    """
    Pull our embedded files out of the PAC file data.
    We ignore the file ID (although we could use it for some more basic validation),
    as well as the offset seems to be with respect to the start of the PAC file
    and not with respect to the previous embedded file.
    However, it is possible that the algorithm implemented here is wrong and
    eventually well need to use the offset (i.e. not all the files are tightly
    packed/"right next to" each other) so we keep it around.
    """
    remaining = pac_contents

    for file_name, _, __, file_size in file_list:
        file_data = remaining[:file_size]
        remaining = remaining[file_size:]

        full_path = os.path.join(out_dir, file_name)
        with open(full_path, "wb") as emb_fp:
            emb_fp.write(file_data)


def _get_out_dir(pac_path):
    """
    Get an output directory name based on the PAC file path we are given.
    Used as the default output directory.
    """
    parent_dir = os.path.dirname(pac_path)
    out_dir, _ = os.path.splitext(os.path.basename(pac_path))
    return os.path.join(parent_dir, out_dir)


def extract_pac(pac_path, out_dir=None):
    """
    Extract the contents of a PAC file, outputting them to a directory.

    Reference: https://github.com/dantarion/bbtools/blob/master/pac.py
    """
    if out_dir is None:
        out_dir = _get_out_dir(pac_path)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with open(pac_path, "rb") as pac_fp:
        pac_contents = pac_fp.read()

    data_start, meta_chunk_size, file_count, remaining = _parse_header(pac_contents)
    file_list, remaining = _enumerate_files(remaining, file_count, meta_chunk_size)

    data_contents = pac_contents[data_start:]
    _extract_files(data_contents, file_list, out_dir)
