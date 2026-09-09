"""Compile and run bridge regressions without loading the user's mods or games."""

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
    with tempfile.TemporaryDirectory(prefix="hlmod-bridge-") as temporary:
        work = Path(temporary)
        mods = work / "mods"
        mods.mkdir()
        shutil.copy2(root / "mods/hlobj.py", mods / "hlobj.py")
        shutil.copy2(root / "mods/hlvalues.py", mods / "hlvalues.py")
        shutil.copytree(root / "mods/modcore", mods / "modcore", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(fixture / "bridge_mod.py", mods / "bridge_mod.py")
        bytecode = work / "BridgeFixture.hl"
        for mode in ("debug", "release"):
            print(f"=== Bridge fixture: {mode} ===", flush=True)
            subprocess.run(
                [args.haxe, "-cp", str(fixture), "-main", "BridgeFixture", "-hl", str(bytecode)]
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
                raise SystemExit(f"Bridge fixture exited with status {result.returncode}")
            for marker in ("PYTHON_BRIDGE_CHECKS_OK", "PYTHON_BRIDGE_GC_OK", "BRIDGE_FIXTURE_OK"):
                if marker not in result.stdout:
                    raise SystemExit(f"Bridge fixture did not reach {marker}")


if __name__ == "__main__":
    main()
