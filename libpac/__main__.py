import os
import argparse

from .pac import extract_pac


def abs_path(value):
    value = os.path.abspath(value)

    if not os.path.exists(value):
        raise argparse.ArgumentError("Invalid file path! Does not exist!")

    return value


def main():
    parser = argparse.ArgumentParser("pac")
    subparsers = parser.add_subparsers(title="commands")

    extract = subparsers.add_parser("extract")
    extract.add_argument(dest="pac_path", type=abs_path, help="PAC file input path.")
    extract.add_argument("-o", "--output-dir", dest="out_dir", type=os.path.abspath,
                         required=False, default=None, help="HPL file output path.")

    args, _ = parser.parse_known_args()

    pac_path = getattr(args, "pac_path", None)
    out_dir = getattr(args, "out_dir", None)

    if pac_path is not None:
        extract_pac(pac_path, out_dir)


if __name__ == "__main__":
    main()
