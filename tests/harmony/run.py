"""Run Harmony-style prefix/postfix patch and native-hook regressions on custom Haxe."""

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
    with tempfile.TemporaryDirectory(prefix="hlmod-harmony-") as temporary:
        work = Path(temporary)
        mods = work / "mods"
        mods.mkdir()
        for name in ("hlobj.py", "hlvalues.py"):
            shutil.copy2(root / "mods" / name, mods / name)
        shutil.copytree(root / "mods/modcore", mods / "modcore", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(fixture / "zz_controller.py", mods / "zz_controller.py")
        bytecode = work / "HarmonyFixture.hl"
        for mode in ("debug", "release"):
            print(f"=== Harmony fixture: {mode} ===", flush=True)
            subprocess.run(
                [args.haxe, "-cp", str(fixture), "-main", "HarmonyFixture", "-hl", str(bytecode)]
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
                raise SystemExit(f"Harmony fixture exited with status {result.returncode}")
            for marker in ("HARMONY_FIXTURE_OK",):
                if marker not in result.stdout:
                    raise SystemExit(f"Harmony fixture did not reach {marker}")


if __name__ == "__main__":
    main()
