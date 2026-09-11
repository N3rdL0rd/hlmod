"""Compile and run the generic Heaps/hxd resource-overlay regression without
loading the user's mods or games: `mods/heaps` hooks whichever of
`hxd.Res.initEmbed`/`.initLocal`/`.initPak` a game actually calls, swaps in
an overlay `hxd.fs.FileSystem` in front of the real one, and must let loose
override files win while everything else still reaches the base game's own
FileSystem untouched."""

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
    with tempfile.TemporaryDirectory(prefix="hlmod-heaps-") as temporary:
        work = Path(temporary)
        mods = work / "mods"
        mods.mkdir()
        shutil.copy2(root / "mods/hlobj.py", mods / "hlobj.py")
        shutil.copy2(root / "mods/hlvalues.py", mods / "hlvalues.py")
        shutil.copytree(root / "mods/modcore", mods / "modcore", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(root / "mods/heaps", mods / "heaps", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(fixture / "heaps_overlay_mod.py", mods / "heaps_overlay_mod.py")
        shutil.copytree(fixture / "overlay_res", mods / "overlay_res")
        bytecode = work / "HeapsFixture.hl"
        for mode in ("debug", "release"):
            print(f"=== Heaps fixture: {mode} ===", flush=True)
            subprocess.run(
                [args.haxe, "-cp", str(fixture), "-main", "HeapsFixture", "-hl", str(bytecode)]
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
                raise SystemExit(f"Heaps fixture exited with status {result.returncode}")
            for marker in (
                "HEAPS_FIXTURE_OK", "HEAPS_OVERLAY_OVERRIDE_OK", "HEAPS_OVERLAY_PASSTHROUGH_OK",
            ):
                if marker not in result.stdout:
                    raise SystemExit(f"Heaps fixture did not reach {marker}")


if __name__ == "__main__":
    main()
