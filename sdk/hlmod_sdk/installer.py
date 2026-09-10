"""Core hlmod install logic: download a nightly build, extract it, apply
tweaks, write a launcher, and record the install in the registry.

This is Qt-free and callback-driven so both the GUI installer (`installer/`)
and `hlmod-sdk install` share one implementation instead of drifting apart.
"""
from __future__ import annotations

import os
import shutil
import zipfile
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

import requests

from .registry import record_install

REPO = "N3rdL0rd/hlmod"
# Must match the `python` matrix value in .github/workflows/nightly.yml: the
# artifact filename embeds it, so a drift here makes every download 404.
PYTHON_VER = "3.13"
BASE_FILENAME = f"hlmod-hl-nightly-python{PYTHON_VER}-"
FILENAME_END = ".zip"
REQUEST_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 60
CANCELLED = "Installation cancelled."

# Friendly name -> exact `nightly.yml` artifact suffix.
LINUX_BUILD_TYPES = {
    "gcc-release": "Linux-gcc-Release",
    "gcc-debug": "Linux-gcc-Debug",
    "clang-release": "Linux-clang-Release",
    "clang-debug": "Linux-clang-Debug",
}
WINDOWS_BUILD_TYPES = {
    "msvc-release": "Windows-msvc-Release",
    "msvc-relwithdebinfo": "Windows-msvc-RelWithDebInfo",
    "mingw-release": "Windows-mingw-Release",
}

# Friendly display labels for the GUI dropdown, keyed the same way.
BUILD_TYPE_LABELS = {
    "gcc-release": "GCC (Release)",
    "gcc-debug": "GCC (Debug)",
    "clang-release": "Clang (Release)",
    "clang-debug": "Clang (Debug)",
    "msvc-release": "MSVC (Release)",
    "msvc-relwithdebinfo": "MSVC (Release w/ debug info)",
    "mingw-release": "MinGW (Release)",
}


def default_build_types() -> dict[str, str]:
    return WINDOWS_BUILD_TYPES if os.name == "nt" else LINUX_BUILD_TYPES


class Tweak(Enum):
    USE_EXISTING_STEAM = auto()
    USE_EXISTING_SDL = auto()
    USE_EXISTING_OPENAL = auto()
    INSTALL_DCMOD = auto()
    NO_BASE_MODS = auto()


TWEAK_LABELS = {
    Tweak.USE_EXISTING_STEAM: "Use the game's existing steam.hdll instead of hlmod's bundled build",
    Tweak.USE_EXISTING_SDL: "Use the game's existing sdl.hdll instead of hlmod's bundled build",
    Tweak.USE_EXISTING_OPENAL: "Use the game's existing openal.hdll instead of hlmod's bundled build",
    Tweak.INSTALL_DCMOD: "Install the Dead Cells mod (dcmod)",
    Tweak.NO_BASE_MODS: "Skip installing base framework mods (hlobj, hlvalues, modcore)",
}

# Short CLI-facing aliases for -t/--tweak.
TWEAK_ALIASES = {
    "steam": Tweak.USE_EXISTING_STEAM,
    "sdl": Tweak.USE_EXISTING_SDL,
    "openal": Tweak.USE_EXISTING_OPENAL,
    "dcmod": Tweak.INSTALL_DCMOD,
    "no-base-mods": Tweak.NO_BASE_MODS,
}

LAUNCH_SCRIPT_LINUX = """#!/bin/sh

DIR=$(cd "$(dirname "$0")" && pwd)
HLMOD_DIR="$DIR/hlmod"
PY_LIB="$HLMOD_DIR/python3.13"

if [ ! -d "$PY_LIB" ]; then
    echo "Error: Directory $PY_LIB does not exist."
    exit 1
fi

export PYTHONHOME="$HLMOD_DIR"
export PYTHONPATH="$PY_LIB:$PY_LIB/lib-dynload"
SYSTEM_LIBS="/usr/lib/x86_64-linux-gnu:/usr/lib64:/usr/lib:/lib"
export LD_LIBRARY_PATH="$SYSTEM_LIBS:$HLMOD_DIR"
exec "$HLMOD_DIR/hl.bin" "$@"
"""

LAUNCH_SCRIPT_WINDOWS = """@echo off
setlocal
set "DIR=%~dp0"
set "HLMOD_DIR=%DIR%hlmod"

if not exist "%HLMOD_DIR%\\Lib" (
    echo Error: Directory %HLMOD_DIR%\\Lib does not exist.
    exit /b 1
)

set "PYTHONHOME=%HLMOD_DIR%"
set "PYTHONPATH=%HLMOD_DIR%"
"%HLMOD_DIR%\\hl.exe" %*
"""


class InstallError(RuntimeError):
    """A recoverable install failure with a message meant for end users."""


class InstallCancelled(RuntimeError):
    def __init__(self):
        super().__init__(CANCELLED)


@dataclass
class InstallCallbacks:
    on_status: Callable[[str], None] = field(default=lambda text: None)
    on_progress: Callable[[int], None] = field(default=lambda percent: None)
    should_cancel: Callable[[], bool] = field(default=lambda: False)

    def check_cancelled(self) -> None:
        if self.should_cancel():
            raise InstallCancelled()


def make_executable(path: str) -> None:
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2  # copy R bits to X
    os.chmod(path, mode)


def map_value(x, src_min, src_max, dst_min, dst_max):
    return ((x - src_min) / (src_max - src_min)) * (dst_max - dst_min) + dst_min


def resolve_run_id(version: str, callbacks: InstallCallbacks) -> tuple[str, int]:
    """Returns `(resolved_sha, run_id)` for the given version ("latest" or a
    commit SHA)."""
    if version == "latest":
        callbacks.on_status("Finding latest version...")
        r = requests.get(f"https://api.github.com/repos/{REPO}/commits/main", timeout=REQUEST_TIMEOUT)
        try:
            r.raise_for_status()
        except requests.RequestException as error:
            raise InstallError("Failed to find latest version!") from error
        version = r.json()["sha"]

    callbacks.check_cancelled()
    callbacks.on_status("Finding build...")
    callbacks.on_progress(5)

    r = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs?head_sha={version}", timeout=REQUEST_TIMEOUT)
    try:
        r.raise_for_status()
    except requests.RequestException as error:
        raise InstallError("Failed to find build!") from error
    run_id: Optional[int] = None
    # The API returns runs newest-first; stop at the first successful match
    # so a re-run of the same commit can't select an older build.
    for run_i in r.json()["workflow_runs"]:
        if run_i["name"] == "Nightly Build" and run_i["conclusion"] == "success":
            run_id = run_i["id"]
            break
    if run_id is None:
        raise InstallError("Failed to find successful build!")
    return version, run_id


def download(run_id: int, build_type: str, directory: str, version: str, callbacks: InstallCallbacks) -> str:
    callbacks.on_status(f"Downloading hlmod {version[0:7]} from {run_id}")
    callbacks.on_progress(10)  # 10-60% will be downloading
    url = f"https://nightly.link/{REPO}/actions/runs/{run_id}/{BASE_FILENAME}{build_type}{FILENAME_END}"
    zip_path = os.path.join(directory, "temp.zip")
    with requests.get(url, stream=True, allow_redirects=True, timeout=DOWNLOAD_TIMEOUT) as r:
        try:
            r.raise_for_status()
        except requests.RequestException as error:
            raise InstallError(f"Failed to download build: {error}") from error
        total_size = int(r.headers.get("content-length", 0))
        chunk_size = 8192
        downloaded_bytes = 0
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                callbacks.check_cancelled()
                if not chunk:  # filter out keep-alive new chunks
                    continue
                downloaded_bytes += f.write(chunk)
                if total_size > 0 and downloaded_bytes % (1024 * 1024) < chunk_size:
                    callbacks.on_progress(round(map_value(downloaded_bytes, 0, total_size, 10, 60)))
    return zip_path


def extract(zip_path: str, directory: str, callbacks: InstallCallbacks) -> str:
    callbacks.on_status("Extracting...")
    callbacks.on_progress(60)
    extract_dir = os.path.join(directory, "hlmod")
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        file_list = zf.infolist()
        total_uncompressed_size = sum(f.file_size for f in file_list)
        current_uncompressed_size = 0
        for member in file_list:
            callbacks.check_cancelled()
            zf.extract(member, extract_dir)
            current_uncompressed_size += member.file_size
            if total_uncompressed_size > 0:
                val = map_value(current_uncompressed_size, 0, total_uncompressed_size, 60, 70)
                callbacks.on_progress(round(val))
    os.remove(zip_path)
    return extract_dir


def detect_tweaks(directory: str) -> list[Tweak]:
    tweaks: list[Tweak] = []
    if os.path.exists(os.path.join(directory, "steam.hdll")) and os.name == "posix":
        tweaks.append(Tweak.USE_EXISTING_STEAM)
    if os.path.exists(os.path.join(directory, "sdl.hdll")):
        tweaks.append(Tweak.USE_EXISTING_SDL)
    if os.path.exists(os.path.join(directory, "openal.hdll")) and os.name == "nt":
        tweaks.append(Tweak.USE_EXISTING_OPENAL)
    if os.path.exists(os.path.join(directory, "deadcells")) or os.path.exists(os.path.join(directory, "deadcells.exe")):
        tweaks.append(Tweak.INSTALL_DCMOD)
    return tweaks


def install_files(directory: str, extract_dir: str, tweaks: list[Tweak]) -> None:
    # Only touch the specific framework-managed paths below; anything else a
    # user has placed in mods/ (their own or third-party mods) is left
    # alone, including across reinstalls/updates.
    mods_dir = os.path.join(directory, "mods")
    os.makedirs(mods_dir, exist_ok=True)

    if os.name == "posix":
        make_executable(os.path.join(extract_dir, "hl"))
        make_executable(os.path.join(extract_dir, "hl.bin"))
        with open(os.path.join(directory, "run_hlmod.sh"), "w") as f:
            f.write(LAUNCH_SCRIPT_LINUX)
        make_executable(os.path.join(directory, "run_hlmod.sh"))
        if Tweak.USE_EXISTING_STEAM in tweaks:
            shutil.copy(os.path.join(directory, "steam.hdll"), os.path.join(extract_dir, "steam.hdll"))
            shutil.copy(os.path.join(directory, "libsteam_api.so"), os.path.join(extract_dir, "libsteam_api.so"))
    else:
        with open(os.path.join(directory, "run_hlmod.bat"), "w") as f:
            f.write(LAUNCH_SCRIPT_WINDOWS)

    if Tweak.USE_EXISTING_SDL in tweaks:
        sdl_src = os.path.join(directory, "sdl.hdll")
        if os.path.exists(sdl_src):
            shutil.copy(sdl_src, os.path.join(extract_dir, "sdl.hdll"))

    if Tweak.USE_EXISTING_OPENAL in tweaks:
        if os.path.exists(os.path.join(directory, "OpenAL32.dll")):
            shutil.copy(os.path.join(directory, "OpenAL32.dll"), os.path.join(extract_dir, "OpenAL32.dll"))
        openal_src = os.path.join(directory, "openal.hdll")
        if os.path.exists(openal_src):
            shutil.copy(openal_src, os.path.join(extract_dir, "openal.hdll"))

    if Tweak.INSTALL_DCMOD in tweaks:
        dcmod_src = os.path.join(extract_dir, "mods", "dcmod")
        if os.path.isdir(dcmod_src):
            shutil.copytree(dcmod_src, os.path.join(mods_dir, "dcmod"), dirs_exist_ok=True)

    if Tweak.NO_BASE_MODS not in tweaks:
        for name in ("hlobj.py", "hlobj.pyi", "hlvalues.py"):
            src = os.path.join(extract_dir, "mods", name)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(mods_dir, name))
        modcore_src = os.path.join(extract_dir, "mods", "modcore")
        if os.path.isdir(modcore_src):
            shutil.copytree(modcore_src, os.path.join(mods_dir, "modcore"), dirs_exist_ok=True)

    # hlmod.pyi is the low-level native API stub; it ships regardless of
    # NO_BASE_MODS since `import hlmod` needs it even without the framework.
    hlmod_pyi_src = os.path.join(extract_dir, "mods", "hlmod.pyi")
    if os.path.exists(hlmod_pyi_src):
        shutil.copy(hlmod_pyi_src, os.path.join(mods_dir, "hlmod.pyi"))


def install(
    directory: str,
    build_type: str,
    version: str = "latest",
    tweaks: Optional[set[Tweak]] = None,
    auto_detect: bool = True,
    callbacks: Optional[InstallCallbacks] = None,
) -> None:
    """Runs a full hlmod install into `directory`.

    Raises `InstallError`/`InstallCancelled` on failure; on success the
    install has already been recorded in the registry.
    """
    callbacks = callbacks or InstallCallbacks()
    callbacks.check_cancelled()
    resolved_version, run_id = resolve_run_id(version, callbacks)
    callbacks.check_cancelled()
    zip_path = download(run_id, build_type, directory, resolved_version, callbacks)
    callbacks.check_cancelled()
    extract_dir = extract(zip_path, directory, callbacks)
    callbacks.check_cancelled()

    callbacks.on_status("Auto-detecting configuration..." if auto_detect else "Applying manual tweaks...")
    callbacks.on_progress(70)
    resolved_tweaks = detect_tweaks(directory) if auto_detect else list(tweaks or ())

    callbacks.on_status("Installing...")
    callbacks.on_progress(80)
    install_files(directory, extract_dir, resolved_tweaks)

    try:
        record_install(directory, version=resolved_version, build_type=build_type)
    except OSError:
        pass  # Recording the install is best-effort; a failed install would already have raised.

    callbacks.on_status("Done!")
    callbacks.on_progress(100)
