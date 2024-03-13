from argparse import ArgumentParser
from importlib import import_module
from pathlib import Path

from asyncfusion import install


def main() -> None:
    parser = ArgumentParser(
        prog='asyncfusion-instrument',
        description=(
            'Installs the asyncfusion import hooks for running a Python script or module'
        ),
    )
    parser.add_argument("-m", help="Import a module (e.g. package.module) instead of running a script")
    parser.add_argument("name", help="Script file name to run, or module name if the -m option was given")
    args = parser.parse_args()

    install()
    if args.m:
        import_module(args.name)
    else:
        exec(Path(args.name).read_text())


if __name__ == "__main__":
    main()
