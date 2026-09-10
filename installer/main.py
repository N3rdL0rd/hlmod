import os
import shutil
import sys
import zipfile
from enum import Enum, auto
from typing import Optional

import requests
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

REPO = "N3rdL0rd/hlmod"
LINUX_OPTIONS = {
    "GCC (Release)": "Linux-gcc-Release",
    "GCC (Debug)": "Linux-gcc-Debug",
    "Clang (Release)": "Linux-clang-Release",
    "Clang (Debug)": "Linux-clang-Debug",
}
WIN_OPTIONS = {
    "MSVC (Release)": "Windows-msvc-Release",
    "MSVC (Release w/ debug info)": "Windows-msvc-RelWithDebInfo",
    "MinGW (Release)": "Windows-mingw-Release",
}
# Must match the `python` matrix value in .github/workflows/nightly.yml: the
# artifact filename embeds it, so a drift here makes every download 404.
PYTHON_VER = "3.13"
BASE_FILENAME = f"hlmod-hl-nightly-python{PYTHON_VER}-"
FILENAME_END = ".zip"
REQUEST_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 60
CANCELLED = "Installation cancelled."

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


def make_executable(path):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2    # copy R bits to X
    os.chmod(path, mode)


def map_value(x, src_min, src_max, dst_min, dst_max):
    return ((x - src_min) / (src_max - src_min)) * (dst_max - dst_min) + dst_min


class InstallWorker(QThread):
    """
    Handles the 'heavy lifting' (downloading/extracting) in the background
    so the GUI doesn't freeze.
    """
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, directory: str, version: str, build_type: str, auto_detect: bool, manual_tweaks: set[Tweak]):
        super().__init__()
        self.directory = directory
        self.version = version
        self.build_type = build_type
        self.auto_detect = auto_detect
        self.manual_tweaks = manual_tweaks

    def run(self):
        try:
            self._run()
        except Exception as error:
            self.error_signal.emit(str(error))
            return
        self.finished_signal.emit()

    def _check_cancelled(self):
        if self.isInterruptionRequested():
            raise RuntimeError(CANCELLED)

    def _resolve_run_id(self) -> int:
        if self.version == "latest":
            self.status_signal.emit("Finding latest version...")
            r = requests.get(f"https://api.github.com/repos/{REPO}/commits/main", timeout=REQUEST_TIMEOUT)
            try:
                r.raise_for_status()
            except requests.RequestException as error:
                raise RuntimeError("Failed to find latest version!") from error
            self.version = r.json()["sha"]

        self._check_cancelled()
        self.status_signal.emit("Finding build...")
        self.progress_signal.emit(5)

        r = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs?head_sha={self.version}", timeout=REQUEST_TIMEOUT)
        try:
            r.raise_for_status()
        except requests.RequestException as error:
            raise RuntimeError("Failed to find build!") from error
        run_id: Optional[int] = None
        # The API returns runs newest-first; stop at the first successful
        # match so a re-run of the same commit can't select an older build.
        for run_i in r.json()["workflow_runs"]:
            if run_i["name"] == "Nightly Build" and run_i["conclusion"] == "success":
                run_id = run_i["id"]
                break
        if run_id is None:
            raise RuntimeError("Failed to find successful build!")
        return run_id

    def _download(self, run_id: int) -> str:
        self.status_signal.emit(f"Downloading hlmod {self.version[0:7]} from {run_id}")
        self.progress_signal.emit(10)  # 10-60% will be downloading
        url = f"https://nightly.link/{REPO}/actions/runs/{run_id}/{BASE_FILENAME}{self.build_type}{FILENAME_END}"
        zip_path = os.path.join(self.directory, "temp.zip")
        with requests.get(url, stream=True, allow_redirects=True, timeout=DOWNLOAD_TIMEOUT) as r:
            try:
                r.raise_for_status()
            except requests.RequestException as error:
                raise RuntimeError(f"Failed to download build: {error}") from error
            total_size = int(r.headers.get("content-length", 0))
            chunk_size = 8192
            downloaded_bytes = 0
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    self._check_cancelled()
                    if not chunk:  # filter out keep-alive new chunks
                        continue
                    downloaded_bytes += f.write(chunk)
                    if total_size > 0 and downloaded_bytes % (1024 * 1024) < chunk_size:
                        self.progress_signal.emit(round(map_value(downloaded_bytes, 0, total_size, 10, 60)))
        return zip_path

    def _extract(self, zip_path: str) -> str:
        self.status_signal.emit("Extracting...")
        self.progress_signal.emit(60)
        extract_dir = os.path.join(self.directory, "hlmod")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            file_list = zf.infolist()
            total_uncompressed_size = sum(f.file_size for f in file_list)
            current_uncompressed_size = 0
            for member in file_list:
                self._check_cancelled()
                zf.extract(member, extract_dir)
                current_uncompressed_size += member.file_size
                if total_uncompressed_size > 0:
                    val = map_value(current_uncompressed_size, 0, total_uncompressed_size, 60, 70)
                    self.progress_signal.emit(round(val))
        os.remove(zip_path)
        return extract_dir

    def _detect_tweaks(self) -> list[Tweak]:
        if not self.auto_detect:
            return list(self.manual_tweaks)
        tweaks: list[Tweak] = []
        if os.path.exists(os.path.join(self.directory, "steam.hdll")) and os.name == "posix":
            tweaks.append(Tweak.USE_EXISTING_STEAM)
        if os.path.exists(os.path.join(self.directory, "sdl.hdll")):
            tweaks.append(Tweak.USE_EXISTING_SDL)
        if os.path.exists(os.path.join(self.directory, "openal.hdll")) and os.name == "nt":
            tweaks.append(Tweak.USE_EXISTING_OPENAL)
        if os.path.exists(os.path.join(self.directory, "deadcells")) or os.path.exists(os.path.join(self.directory, "deadcells.exe")):
            tweaks.append(Tweak.INSTALL_DCMOD)
        return tweaks

    def _install(self, extract_dir: str, tweaks: list[Tweak]) -> None:
        self.status_signal.emit("Installing...")
        self.progress_signal.emit(80)

        # Only touch the specific framework-managed paths below; anything
        # else a user has placed in mods/ (their own or third-party mods)
        # is left alone, including across reinstalls/updates.
        mods_dir = os.path.join(self.directory, "mods")
        os.makedirs(mods_dir, exist_ok=True)

        if os.name == "posix":
            make_executable(os.path.join(extract_dir, "hl"))
            make_executable(os.path.join(extract_dir, "hl.bin"))
            with open(os.path.join(self.directory, "run_hlmod.sh"), "w") as f:
                f.write(LAUNCH_SCRIPT_LINUX)
            make_executable(os.path.join(self.directory, "run_hlmod.sh"))
            if Tweak.USE_EXISTING_STEAM in tweaks:
                shutil.copy(os.path.join(self.directory, "steam.hdll"), os.path.join(extract_dir, "steam.hdll"))
                shutil.copy(os.path.join(self.directory, "libsteam_api.so"), os.path.join(extract_dir, "libsteam_api.so"))
        else:
            with open(os.path.join(self.directory, "run_hlmod.bat"), "w") as f:
                f.write(LAUNCH_SCRIPT_WINDOWS)

        if Tweak.USE_EXISTING_SDL in tweaks:
            sdl_src = os.path.join(self.directory, "sdl.hdll")
            if os.path.exists(sdl_src):
                shutil.copy(sdl_src, os.path.join(extract_dir, "sdl.hdll"))

        if Tweak.USE_EXISTING_OPENAL in tweaks:
            if os.path.exists(os.path.join(self.directory, "OpenAL32.dll")):
                shutil.copy(os.path.join(self.directory, "OpenAL32.dll"), os.path.join(extract_dir, "OpenAL32.dll"))
            openal_src = os.path.join(self.directory, "openal.hdll")
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

        self.status_signal.emit("Done!")
        self.progress_signal.emit(100)

    def _run(self):
        self._check_cancelled()
        run_id = self._resolve_run_id()
        self._check_cancelled()
        zip_path = self._download(run_id)
        self._check_cancelled()
        extract_dir = self._extract(zip_path)
        self._check_cancelled()
        self.status_signal.emit("Auto-detecting configuration..." if self.auto_detect else "Applying manual tweaks...")
        self.progress_signal.emit(70)
        tweaks = self._detect_tweaks()
        self._install(extract_dir, tweaks)


class AdvancedTweaksDialog(QDialog):
    """Lets a user override or disable hlmod's install-time auto-detection."""

    def __init__(self, parent, auto_detect: bool, manual_tweaks: set[Tweak]):
        super().__init__(parent)
        self.setWindowTitle("Advanced Tweaks")
        layout = QVBoxLayout()

        self.auto_checkbox = QCheckBox("Auto-detect tweaks (recommended)")
        self.auto_checkbox.setChecked(auto_detect)
        self.auto_checkbox.stateChanged.connect(self._update_enabled)
        layout.addWidget(self.auto_checkbox)

        info = QLabel(
            "When auto-detect is off, hlmod applies exactly the tweaks checked "
            "below and nothing else - no steam.hdll/sdl.hdll/openal.hdll or "
            "Dead Cells detection runs."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.tweak_checkboxes: dict[Tweak, QCheckBox] = {}
        for tweak, label in TWEAK_LABELS.items():
            box = QCheckBox(label)
            box.setChecked(tweak in manual_tweaks)
            layout.addWidget(box)
            self.tweak_checkboxes[tweak] = box

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)
        self._update_enabled()

    def _update_enabled(self):
        enabled = not self.auto_checkbox.isChecked()
        for box in self.tweak_checkboxes.values():
            box.setEnabled(enabled)

    def result_state(self) -> tuple[bool, set[Tweak]]:
        selected = {tweak for tweak, box in self.tweak_checkboxes.items() if box.isChecked()}
        return self.auto_checkbox.isChecked(), selected


class InstallerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.auto_detect = True
        self.manual_tweaks: set[Tweak] = set()
        self.worker: Optional[InstallWorker] = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("hlmod Installer")
        self.setGeometry(300, 300, 500, 380)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        title = QLabel("hlmod Installer")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        caption = QLabel("A smart automated installer for hlmod that works with any HL game.")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(caption)

        dir_layout = QVBoxLayout()
        dir_label = QLabel("Select game directory:")

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("C:/Program Files (x86)/Steam/steamapps/common/...")

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_folder)

        h_box = QHBoxLayout()
        h_box.addWidget(self.path_input)
        h_box.addWidget(browse_btn)

        dir_layout.addWidget(dir_label)
        dir_layout.addLayout(h_box)
        layout.addLayout(dir_layout)

        ver_layout = QVBoxLayout()
        ver_label = QLabel("Select version:")
        self.version_combo = QComboBox()
        self.version_combo.addItems(["Nightly (latest, will be unstable)", "Custom"])

        ver_layout.addWidget(ver_label)
        ver_layout.addWidget(self.version_combo)

        ver_layout2 = QVBoxLayout()
        ver_label2 = QLabel("Select build type:")
        self.type_combo = QComboBox()
        self.type_combo.addItems(LINUX_OPTIONS.keys() if os.name == "posix" else WIN_OPTIONS.keys())

        ver_layout2.addWidget(ver_label2)
        ver_layout2.addWidget(self.type_combo)

        layout.addLayout(ver_layout)
        layout.addLayout(ver_layout2)

        tweaks_row = QHBoxLayout()
        self.tweaks_status_label = QLabel("Tweaks: Auto-detect")
        self.advanced_btn = QPushButton("Advanced Tweaks...")
        self.advanced_btn.clicked.connect(self.open_advanced_tweaks)
        tweaks_row.addWidget(self.tweaks_status_label)
        tweaks_row.addStretch()
        tweaks_row.addWidget(self.advanced_btn)
        layout.addLayout(tweaks_row)

        self.status_label = QLabel("Ready to install.")
        self.status_label.setStyleSheet("font-style: italic;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

        install_row = QHBoxLayout()
        self.install_btn = QPushButton("INSTALL")
        self.install_btn.setMinimumHeight(50)
        self.install_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; font-size: 14px;")
        self.install_btn.clicked.connect(self.start_installation)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(50)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_installation)
        install_row.addWidget(self.install_btn)
        install_row.addWidget(self.cancel_btn)

        layout.addLayout(install_row)

        self.setLayout(layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Game Folder")
        if folder:
            self.path_input.setText(folder)

    def open_advanced_tweaks(self):
        dialog = AdvancedTweaksDialog(self, self.auto_detect, self.manual_tweaks)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.auto_detect, self.manual_tweaks = dialog.result_state()
            if self.auto_detect:
                self.tweaks_status_label.setText("Tweaks: Auto-detect")
            else:
                count = len(self.manual_tweaks)
                self.tweaks_status_label.setText(f"Tweaks: Manual ({count} selected)")

    def start_installation(self):
        target_dir = self.path_input.text()

        version_override = None
        if self.version_combo.currentText() == "Custom":
            version_override, did_finish = QInputDialog.getText(self, "Enter a version", "Enter a version by its git commit long hash.")
            if not did_finish:
                QMessageBox.warning(self, "Error", "Please specify a git commit hash to use!")
                return

        if not target_dir:
            QMessageBox.warning(self, "Error", "Please select a game directory first.")
            return

        if not os.path.exists(target_dir):
            QMessageBox.warning(self, "Error", "The selected directory does not exist.")
            return

        self.install_btn.setEnabled(False)
        self.path_input.setEnabled(False)
        self.version_combo.setEnabled(False)
        self.type_combo.setEnabled(False)
        self.advanced_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        version = "latest" if self.version_combo.currentText() != "Custom" else version_override
        assert version is not None
        build_type = LINUX_OPTIONS.get(self.type_combo.currentText()) if os.name == "posix" else WIN_OPTIONS.get(self.type_combo.currentText())
        assert build_type is not None
        self.worker = InstallWorker(target_dir, version, build_type, self.auto_detect, self.manual_tweaks)

        self.worker.progress_signal.connect(self.update_progress)
        self.worker.status_signal.connect(self.update_status)
        self.worker.finished_signal.connect(self.installation_finished)
        self.worker.error_signal.connect(self.installation_failed)

        self.worker.start()

    def cancel_installation(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.status_label.setText("Cancelling...")
            self.cancel_btn.setEnabled(False)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, text):
        self.status_label.setText(text)

    def _reset_controls(self):
        self.install_btn.setEnabled(True)
        self.path_input.setEnabled(True)
        self.version_combo.setEnabled(True)
        self.type_combo.setEnabled(True)
        self.advanced_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def installation_finished(self):
        QMessageBox.information(self, "Success", "hlmod is now installed!")
        self._reset_controls()
        self.install_btn.setText("INSTALL (Done!)")

    def installation_failed(self, message: str):
        if message == CANCELLED:
            QMessageBox.information(self, "Cancelled", CANCELLED)
        else:
            QMessageBox.critical(self, "Error", f"Installation failed: {message}")
        self._reset_controls()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setStyle("Fusion")

    window = InstallerWindow()
    window.show()
    sys.exit(app.exec())
