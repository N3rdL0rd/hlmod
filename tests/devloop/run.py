"""Verify tools/dev.py restarts `hl` when a mod's Python source changes."""
import argparse
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time


def controller_source(marker: str) -> str:
    return f'''MOD_INFO = {{"id": "controller", "dependencies": []}}

from modcore import hook
import hlmod


@hook(hlmod.findex_for_name("$DevLoopFixture.verify"))
def verify(context):
    print("{marker}", flush=True)
'''


def pump(pipe, sink: "queue.Queue[str]") -> None:
    for line in iter(pipe.readline, ""):
        sink.put(line)
    pipe.close()


def wait_for(sink: "queue.Queue[str]", text: str, timeout: float, buffer: list) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            line = sink.get(timeout=max(0.0, deadline - time.monotonic()))
        except queue.Empty:
            break
        buffer.append(line)
        if text in line:
            return
    raise SystemExit(f"Dev loop did not print {text!r} within {timeout}s. Output so far:\n{''.join(buffer)}")


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hl", type=Path, default=root / "hlmod-hl/build/bin/hl")
    parser.add_argument("--haxe", default="haxe")
    args = parser.parse_args()
    fixture = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="hlmod-devloop-") as temporary:
        work = Path(temporary)
        mods = work / "mods"
        mods.mkdir()
        for name in ("hlobj.py", "hlvalues.py"):
            shutil.copy2(root / "mods" / name, mods / name)
        shutil.copytree(root / "mods/modcore", mods / "modcore", ignore=shutil.ignore_patterns("__pycache__"))
        controller = mods / "controller.py"
        controller.write_text(controller_source("DEVLOOP_MARKER_V1"), encoding="utf-8")
        bytecode = work / "DevLoopFixture.hl"
        subprocess.run(
            [args.haxe, "-cp", str(fixture), "-main", "DevLoopFixture", "-hl", str(bytecode)],
            check=True, timeout=60,
        )
        dev_script = root / "tools/dev.py"
        process = subprocess.Popen(
            [sys.executable, str(dev_script), str(bytecode), "--hl", str(args.hl.resolve()),
             "--mods", str(mods), "--poll", "0.1"],
            cwd=work, env={**os.environ, "PYTHONUNBUFFERED": "1"},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        sink: "queue.Queue[str]" = queue.Queue()
        threading.Thread(target=pump, args=(process.stdout, sink), daemon=True).start()
        buffer: list[str] = []
        try:
            wait_for(sink, "DEVLOOP_MARKER_V1", 60, buffer)
            # A source edit must trigger a restart, and the restarted process
            # must reflect the new code, not the module cached at the first run.
            controller.write_text(controller_source("DEVLOOP_MARKER_V2"), encoding="utf-8")
            wait_for(sink, "[dev] Restarting due to change", 15, buffer)
            wait_for(sink, "DEVLOOP_MARKER_V2", 60, buffer)
            print("DEVLOOP_FIXTURE_OK", flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    _check_extra_mods(root, fixture, args)


def _check_extra_mods(root, fixture, args) -> None:
    """--extra-mods must watch a directory outside the primary mods folder
    and actually get hl to load mods from it, not just watch it inertly."""
    with tempfile.TemporaryDirectory(prefix="hlmod-devloop-extra-") as temporary:
        work = Path(temporary)
        mods = work / "mods"
        mods.mkdir()
        for name in ("hlobj.py", "hlvalues.py"):
            shutil.copy2(root / "mods" / name, mods / name)
        shutil.copytree(root / "mods/modcore", mods / "modcore", ignore=shutil.ignore_patterns("__pycache__"))
        author_project = work / "author_project"
        author_project.mkdir()
        controller = author_project / "controller.py"
        controller.write_text(controller_source("DEVLOOP_MARKER_V1"), encoding="utf-8")
        bytecode = work / "DevLoopFixture.hl"
        subprocess.run(
            [args.haxe, "-cp", str(fixture), "-main", "DevLoopFixture", "-hl", str(bytecode)],
            check=True, timeout=60,
        )
        dev_script = root / "tools/dev.py"
        process = subprocess.Popen(
            [sys.executable, str(dev_script), str(bytecode), "--hl", str(args.hl.resolve()),
             "--mods", str(mods), "--extra-mods", str(author_project), "--poll", "0.1"],
            cwd=work, env={**os.environ, "PYTHONUNBUFFERED": "1"},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        sink: "queue.Queue[str]" = queue.Queue()
        threading.Thread(target=pump, args=(process.stdout, sink), daemon=True).start()
        buffer: list[str] = []
        try:
            wait_for(sink, "DEVLOOP_MARKER_V1", 60, buffer)
            controller.write_text(controller_source("DEVLOOP_MARKER_V2"), encoding="utf-8")
            wait_for(sink, "[dev] Restarting due to change", 15, buffer)
            wait_for(sink, "DEVLOOP_MARKER_V2", 60, buffer)
            print("DEVLOOP_EXTRA_MODS_OK", flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
