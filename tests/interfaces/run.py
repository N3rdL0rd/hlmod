"""Compile and run interface-implementation regressions without loading the
user's mods or games: create_subclass's `interfaces=` parameter, letting a
Python class satisfy a Haxe interface via brand-new native proto entries,
not just override an ancestor's existing methods."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hl", type=Path, default=root / "hlmod-hl/build/bin/hl")
    parser.add_argument("--haxe", default="haxe")
    args = parser.parse_args()
    fixture = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="hlmod-interfaces-") as temporary:
        work = Path(temporary)
        mods = work / "mods"
        mods.mkdir()
        shutil.copy2(root / "mods/hlobj.py", mods / "hlobj.py")
        shutil.copy2(root / "mods/hlvalues.py", mods / "hlvalues.py")
        shutil.copytree(root / "mods/modcore", mods / "modcore", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(fixture / "interface_mod.py", mods / "interface_mod.py")
        bytecode = work / "InterfaceFixture.hl"
        for mode in ("debug", "release"):
            print(f"=== Interface fixture: {mode} ===", flush=True)
            subprocess.run(
                [args.haxe, "-cp", str(fixture), "-main", "InterfaceFixture", "-hl", str(bytecode)]
                + (["-debug"] if mode == "debug" else []),
                check=True, timeout=60,
            )
            result = subprocess.run(
                [str(args.hl.resolve()), str(bytecode)], cwd=work,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=90,
            )
            print(result.stdout, end="")
            if result.returncode:
                raise SystemExit(f"Interface fixture exited with status {result.returncode}")
            for marker in (
                "INTERFACE_FIXTURE_OK", "OVERRIDE_PATH_OK", "NEW_INTERFACE_METHOD_OK",
                "SECOND_INSTANCE_OK", "EXCEPTION_PROPAGATION_OK", "INTERFACE_MOD_OK",
            ):
                if marker not in result.stdout:
                    raise SystemExit(f"Interface fixture did not reach {marker}")


if __name__ == "__main__":
    main()
