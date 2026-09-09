"""Run core-library event broadcast and mod lifecycle regressions on custom Haxe."""

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
    with tempfile.TemporaryDirectory(prefix="hlmod-events-") as temporary:
        work = Path(temporary)
        mods = work / "mods"
        mods.mkdir()
        for name in ("hlobj.py", "hlvalues.py"):
            shutil.copy2(root / "mods" / name, mods / name)
        shutil.copytree(root / "mods/modcore", mods / "modcore", ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("fixture_core.py", "plugin_a.py", "plugin_b.py", "zz_controller.py"):
            shutil.copy2(fixture / name, mods / name)
        bytecode = work / "EventsFixture.hl"
        for mode in ("debug", "release"):
            print(f"=== Events fixture: {mode} ===", flush=True)
            subprocess.run(
                [args.haxe, "-cp", str(fixture), "-main", "EventsFixture", "-hl", str(bytecode)]
                + (["-debug"] if mode == "debug" else []),
                check=True, timeout=60,
            )
            result = subprocess.run(
                [str(args.hl.resolve()), str(bytecode)], cwd=work,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120,
            )
            print(result.stdout, end="")
            if result.returncode:
                raise SystemExit(f"Events fixture exited with status {result.returncode}")
            for marker in ("EVENTS_LIFECYCLE_OK", "EVENTS_FIXTURE_OK"):
                if marker not in result.stdout:
                    raise SystemExit(f"Events fixture did not reach {marker}")


if __name__ == "__main__":
    main()
