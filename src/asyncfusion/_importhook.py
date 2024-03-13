from __future__ import annotations

import sys
from collections.abc import Sequence
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from importlib.util import spec_from_file_location
from pathlib import Path
from types import ModuleType

asyncio_path = Path(__file__).parent / "shims" / "asyncio"
trio_path = Path(__file__).parent / "shims" / "trio"


class AsyncReplaceFinder(MetaPathFinder):
    def __init__(self, debug: bool = False) -> None:
        super().__init__()
        self.debug = debug

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        if fullname == "asyncio" or fullname.startswith("asyncio."):
            base_path = asyncio_path
        elif fullname == "trio" or fullname.startswith("trio."):
            base_path = trio_path
        else:
            return None

        final_path = base_path
        parts = fullname.split(".")
        for part in parts[1:-1]:
            final_path = final_path / part

        if len(parts) == 1:
            final_path = final_path / "__init__.py"
        else:
            final_path = final_path / f"{parts[-1]}.py"

        if self.debug:
            print(f"diverting import of {fullname} to {final_path}")

        return spec_from_file_location(fullname, final_path)


def install() -> None:
    # Skip if we already have the import hook in place
    if any(isinstance(finder, AsyncReplaceFinder) for finder in sys.meta_path):
        return

    for modname in "asyncio", "trio":
        if modname in sys.modules:
            raise RuntimeError(
                f"cannot install asyncfusion import hook: {modname} has already been"
                f"imported"
            )

    sys.meta_path.insert(0, AsyncReplaceFinder())
