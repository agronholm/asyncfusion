from __future__ import annotations

from argparse import ArgumentParser
from runpy import run_module, run_path

from asyncfusion import install


def main() -> None:
    parser = ArgumentParser(
        prog="asyncfusion",
        description=(
            "Installs the asyncfusion import hooks for running a Python script or "
            "module"
        ),
    )
    parser.add_argument(
        "-m",
        action="store_true",
        help="Import a module (e.g. package.module) instead of running a script",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print a debug message each time an import is diverted by the import hook",
    )
    parser.add_argument(
        "name",
        help="Script file name to run, or module name if the -m option was given",
    )
    args = parser.parse_args()

    install(debug=args.debug)
    if args.m:
        run_module(args.name, run_name="__main__")
    else:
        run_path(args.name, run_name="__main__")


if __name__ == "__main__":
    main()
