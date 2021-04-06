import os
import argparse

from .pac import create_pac, extract_pac


def abs_path(value):
    value = os.path.abspath(value)

    if not os.path.exists(value):
        raise argparse.ArgumentError("Invalid file path! Does not exist!")

    return value


def main():
    parser = argparse.ArgumentParser("pac")
    subparsers = parser.add_subparsers(title="commands")

    extract = subparsers.add_parser("create")
    extract.add_argument(dest="file_dir", type=abs_path, help="Directory to generate a PAC file.")
    extract.add_argument("-o", "--output-file", dest="out_file", type=os.path.abspath,
                         required=False, default=None, help="PAC file output path.")

    extract = subparsers.add_parser("extract")
    extract.add_argument(dest="pac_path", type=abs_path, help="PAC file input path.")
    extract.add_argument("-o", "--output-dir", dest="out_dir", type=os.path.abspath,
                         required=False, default=None, help="Extracted file output path.")

    args, _ = parser.parse_known_args()

    file_dir = getattr(args, "file_dir", None)
    pac_path = getattr(args, "pac_path", None)

    if file_dir is not None:
        create_pac(file_dir, args.out_file)

    if pac_path is not None:
        extract_pac(pac_path, args.out_dir)


if __name__ == "__main__":
    main()
