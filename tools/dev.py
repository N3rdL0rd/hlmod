"""Dev loop for mod authors: run `hl` against a bytecode file and restart it
whenever a mod's Python source changes.

This is deliberately not a packaging tool - see the installer for end-user
distribution and `hlmod-hl`'s build for compiling the runtime itself. hlmod
mods are plain Python with no compile step, so there is nothing to "build";
the only friction in the loop is noticing an edit and restarting the process
by hand. This closes that gap with a plain mtime/size poll - no extra
dependency, consistent with the rest of the mod SDK.
"""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def watched_files(mods_dirs: list[Path], extra_files: list[Path]) -> list[Path]:
    """Only real mod source: hlmod regenerates `mods/stubs/**` (and each
    package's `__pycache__`) on its own schedule, not in response to edits,
    so treating those as user changes would restart on every launch."""
    def is_generated(mods_dir: Path, path: Path) -> bool:
        parts = path.relative_to(mods_dir).parts
        return parts and (parts[0] == "stubs" or any(part == "__pycache__" for part in parts))
    files = []
    for mods_dir in mods_dirs:
        if mods_dir.is_dir():
            files.extend(path for path in mods_dir.rglob("*.py") if not is_generated(mods_dir, path))
    files.extend(path for path in extra_files if path.is_file())
    return files


def snapshot(paths: list[Path]) -> dict[Path, tuple[int, int]]:
    """mtime_ns + size per file, so edits are seen even with coarse mtimes."""
    state = {}
    for path in paths:
        try:
            info = path.stat()
        except OSError:
            continue
        state[path] = (info.st_mtime_ns, info.st_size)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bytecode", type=Path, help="Compiled .hl bytecode to run")
    parser.add_argument("--hl", type=Path, default=Path("hlmod-hl/build/bin/hl"),
                         help="Path to the hl executable (default: hlmod-hl/build/bin/hl)")
    parser.add_argument("--mods", type=Path, default=Path("mods"), help="Primary mods directory to watch")
    parser.add_argument("--extra-mods", action="append", default=[], type=Path,
                         help="Additional directory to watch and load mods from (repeatable); "
                              "passed to hl via HLMOD_EXTRA_MODS alongside any already set in the environment")
    parser.add_argument("--cwd", type=Path, default=None,
                         help="Working directory for the hl process (default: the bytecode's directory)")
    parser.add_argument("--poll", type=float, default=0.5, help="Filesystem poll interval in seconds")
    args = parser.parse_args()

    hl = args.hl.resolve()
    bytecode = args.bytecode.resolve()
    cwd = (args.cwd or args.bytecode.resolve().parent).resolve()
    extra_dirs = list(args.extra_mods)
    extra_dirs.extend(Path(p) for p in os.environ.get("HLMOD_EXTRA_MODS", "").split(os.pathsep) if p)
    mods_dirs = [args.mods] + extra_dirs
    extra_files = [args.mods / "hlmod.toml", args.mods / "typing_overlays.json"]
    state = snapshot(watched_files(mods_dirs, extra_files))
    process: subprocess.Popen | None = None

    def start() -> None:
        nonlocal process
        print(f"[dev] Starting `{hl.name} {bytecode.name}`", flush=True)
        # A restart can follow an edit within the same second; CPython's pyc
        # cache only stores mtime at second granularity, so without this a
        # fast edit-restart cycle can silently rerun stale mod bytecode.
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        if extra_dirs:
            env["HLMOD_EXTRA_MODS"] = os.pathsep.join(str(path) for path in extra_dirs)
        process = subprocess.Popen([str(hl), str(bytecode)], cwd=cwd, env=env)

    def stop() -> None:
        if process is None or process.poll() is not None:
            return
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    start()
    exited_notice_given = False
    try:
        while True:
            time.sleep(args.poll)
            if process is not None and process.poll() is not None and not exited_notice_given:
                print(f"[dev] hl exited with status {process.returncode}; waiting for a change to restart.", flush=True)
                exited_notice_given = True
            current = snapshot(watched_files(mods_dirs, extra_files))
            changed = {path for path in current.keys() | state.keys() if current.get(path) != state.get(path)}
            if changed:
                print(f"[dev] Restarting due to change: {', '.join(sorted(path.name for path in changed))}", flush=True)
                stop()
                state = current
                exited_notice_given = False
                start()
    except KeyboardInterrupt:
        print("[dev] Stopping.", flush=True)
    finally:
        stop()


if __name__ == "__main__":
    sys.exit(main())
