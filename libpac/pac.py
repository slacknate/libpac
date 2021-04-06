import os
import struct

PAC_PREFIX = b"FPAC"
PAC_HEADER_SIZE = 32


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
    (_, string_size, __, ___), remaining = _unpack_from("IIII", remaining)
    entry_size = (data_start - PAC_HEADER_SIZE) / file_count

    if not entry_size.is_integer():
        raise ValueError(f"Invalid meta data entry size {entry_size}!")

    entry_size = int(entry_size)
    return data_start, string_size, file_count, entry_size, remaining


def _get_format(string_size, entry_size):
    """
    Get our unpack format based on the string size and entry size.
    """
    int_size = struct.calcsize("I")
    num_ints = (entry_size - string_size) / int_size

    if not num_ints.is_integer():
        raise ValueError(f"Meta data chunk size is not a multiple of {int_size}! Cannot parse file info!")

    num_ints = int(num_ints)
    return f"{string_size}s" + "I" * num_ints


def _enumerate_files(pac_contents, file_count, string_size, entry_size):
    """
    Create a list that describes all embedded files included in our PAC file.
    It is a list of tuples that contain the file name, file ID (which is just
    an index that is incremented with each file), the file offset (where the file
    data starts), and the size of the file.
    """
    file_list = []
    total_entry_size = file_count * entry_size
    fmt = _get_format(string_size, entry_size)

    for file_index in range(file_count):
        offset = file_index * entry_size
        entry_data = pac_contents[offset:offset+entry_size]
        unpacked = struct.unpack(fmt, entry_data)

        file_name = unpacked[0]
        file_id = unpacked[1]
        file_offset = unpacked[2]
        file_size = unpacked[3]

        file_name = file_name.rstrip(b"\x00").decode("latin-1")
        file_list.append((file_name, file_id, file_offset, file_size))

    return file_list, pac_contents[total_entry_size:]


def enumerate_pac(pac_path):
    """
    Return a list of files contained within a PAC file.
    """
    with open(pac_path, "rb") as pac_fp:
        pac_contents = pac_fp.read()

    _, string_size, file_count, entry_size, remaining = _parse_header(pac_contents)
    file_list, _ = _enumerate_files(remaining, file_count, string_size, entry_size)

    return file_list


def _extract_files(pac_contents, file_list, out_dir, extract_filter=None):
    """
    Pull our embedded files out of the PAC file data.
    """
    if extract_filter is not None:
        file_list = filter(extract_filter, file_list)

    for file_name, _, file_offset, file_size in file_list:
        file_data = pac_contents[file_offset:file_offset+file_size]

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


def extract_pac(pac_path, out_dir=None, extract_filter=None):
    """
    Extract the contents of a PAC file, outputting them to a directory.
    We allow for extracing only certain files in the PAC via `extract_filter`
    which is a callable object that is a suitable filter() function.
    Reference: https://github.com/dantarion/bbtools/blob/master/pac.py
    """
    if extract_filter is not None and not callable(extract_filter):
        raise TypeError("Extract filter must be a callable object suitable to pass to filter()!")

    if out_dir is None:
        out_dir = _get_out_dir(pac_path)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with open(pac_path, "rb") as pac_fp:
        pac_contents = pac_fp.read()

    data_start, string_size, file_count, entry_size, remaining = _parse_header(pac_contents)
    file_list, remaining = _enumerate_files(remaining, file_count, string_size, entry_size)

    data_contents = pac_contents[data_start:]
    _extract_files(data_contents, file_list, out_dir, extract_filter)
