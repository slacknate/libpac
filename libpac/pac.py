import os
import struct

PAC_PREFIX = b"FPAC"
PAC_HEADER_SIZE = 32

INT_SIZE = struct.calcsize("I")
BLOCK_SIZE = 4 * INT_SIZE


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
        raise ValueError(f"Invalid file entry size {entry_size}!")

    entry_size = int(entry_size)
    return data_start, string_size, file_count, entry_size, remaining


def _get_format(string_size, entry_size):
    """
    Get our unpack format based on the string size and entry size.
    """
    num_ints = (entry_size - string_size) / INT_SIZE

    if not num_ints.is_integer():
        raise ValueError(f"File entry size mismatch with string size! Entry size or "
                         f"string size is not a multiple of {INT_SIZE}! Cannot parse file entries!")

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


def _parse_file_list(file_list):
    """
    Parse a file list and determine the values of the the meta data we need
    in order to create a valid PAC file from the files list.
    """
    parsed_file_list = []

    # This is pretty straight forward.
    file_count = len(file_list)

    # Total size of all files we are putting in the PAC file.
    total_file_size = 0

    # Set the string size to the length of longest file name in the file list.
    string_size = 0
    for file_name in file_list:
        name_len = len(os.path.basename(file_name))

        if name_len > string_size:
            string_size = name_len

        file_size = os.path.getsize(file_name)
        parsed_file_list.append((file_name, name_len, file_size))

        total_file_size += file_size

    # Ensure string_size is a multiple of `INT_SIZE`. We need to do this for alignment.
    remainder = string_size % INT_SIZE
    if remainder:
        string_size += INT_SIZE - remainder

    # Ensure string_size is a multiple of `BLOCK_SIZE`. We need to do this for alignment.
    # It also appears that we need the entry size to be greater than or equal to 2 * `string_size`.
    entry_size = string_size
    double_string = 2 * string_size
    while entry_size < double_string or entry_size % BLOCK_SIZE != 0:
        entry_size += INT_SIZE

    return string_size, file_count, entry_size, total_file_size, parsed_file_list


def _build_header(total_size, data_start, string_size, file_count):
    """
    Build a valid PAC file header.
    This is the start of our PAC contents.
    """
    # Not sure what these are for but the values seem static.
    unknown_00 = 1
    unknown_01 = 0
    unknown_02 = 0

    # Fill in our required prefix and meta data.
    header = PAC_PREFIX
    header += struct.pack("III", data_start, total_size, file_count)
    header += struct.pack("IIII", unknown_00, string_size, unknown_01, unknown_02)

    return header


def _build_file_entries(parsed_file_list, string_size, entry_size):
    """
    Create a PAC file entry listing based on our provided file list.
    This will be appended to our PAC contents.
    """
    file_id = 0
    file_offset = 0
    file_entries = b""

    fmt = _get_format(string_size, entry_size)

    # We need to align our entry size to certain byte sizes. As such it is very
    # likely that our data is smaller than the entry size and when that happens we need to
    # create a null-byte padding to fill in the remaining data.
    pad_length = entry_size - string_size - (3 * INT_SIZE)
    pad = (0,) * int(pad_length / INT_SIZE)

    for file_name, name_len, file_size in parsed_file_list:
        file_name_bytes = os.path.basename(file_name).encode("latin-1")

        if name_len < string_size:
            file_name_bytes += b"\x00" * (string_size - name_len)

        elif name_len > string_size:
            raise ValueError("Name too long!")

        file_entries += struct.pack(fmt, file_name_bytes, file_id, file_offset, file_size, *pad)

        file_offset += file_size
        file_id += 1

    return file_entries


def _build_file_contents(parsed_file_list):
    """
    Append the contents of all the files in the list together.
    This will be appended to our PAC contents.
    """
    file_contents = b""

    for file_name, _, __ in parsed_file_list:
        with open(file_name, "rb") as fp:
            file_contents += fp.read()

    return file_contents


def _get_file_list(file_dir):
    """
    Helper to get a list of full paths from the given directory.
    """
    return [os.path.join(file_dir, file_name) for file_name in os.listdir(file_dir)]


def create_pac(file_dir, out_file=None, create_filter=None):
    """
    """
    if create_filter is not None and not callable(create_filter):
        raise TypeError("Create filter must be a callable object suitable to pass to filter()!")

    if create_filter is not None:
        file_list = list(filter(create_filter, _get_file_list(file_dir)))

    else:
        file_list = _get_file_list(file_dir)

    string_size, file_count, entry_size, total_file_size, parsed_file_list = _parse_file_list(file_list)
    data_start = PAC_HEADER_SIZE + (file_count * entry_size)
    total_size = data_start + total_file_size

    pac_contents = _build_header(total_size, data_start, string_size, file_count)
    pac_contents += _build_file_entries(parsed_file_list, string_size, entry_size)
    pac_contents += _build_file_contents(parsed_file_list)

    if len(pac_contents) != total_size:
        raise ValueError("Invalid PAC file generated! File size does not match meta data total size!")

    if out_file is None:
        parent_dir = os.path.dirname(file_dir)
        pac_file_name = os.path.basename(file_dir) + ".pac"
        out_file = os.path.join(parent_dir, pac_file_name)

    elif not out_file.endswith(".pac"):
        raise ValueError("Must have .pac extension for PAC files!")

    with open(out_file, "wb") as pac_fp:
        pac_fp.write(pac_contents)
