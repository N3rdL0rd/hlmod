"""Measure native dispatch, proxy collection and event broadcast on custom Haxe."""

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
    source = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="hlmod-performance-") as directory:
        work = Path(directory)
        mods = work / "mods"
        mods.mkdir()
        for name in ("hlobj.py", "hlvalues.py"):
            shutil.copy2(root / "mods" / name, mods / name)
        shutil.copytree(root / "mods/modcore", mods / "modcore", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(source / "perf_mod.py", mods / "perf_mod.py")
        bytecode = work / "PerfFixture.hl"
        subprocess.run([args.haxe, "-cp", str(source), "-main", "PerfFixture", "-hl", str(bytecode)], check=True, timeout=60)
        result = subprocess.run(
            [str(args.hl.resolve()), str(bytecode)], cwd=work,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            capture_output=True, text=True, timeout=120,
        )
        print(result.stdout, end="")
        print(result.stderr, end="")
        if result.returncode:
            raise SystemExit(result.returncode)
        for key in ("NATIVE_NS_PER_CALL=", "GC_SECONDS_100=", "GC_SECONDS_500=",
                    "GC_SECONDS_1000=", "EVENT_SECONDS=", "HOOKED_NS_PER_CALL="):
            if key not in result.stdout:
                raise SystemExit(f"Benchmark did not produce {key}")


if __name__ == "__main__":
    main()
