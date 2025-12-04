import sys
import os
import time
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel, 
                             QPushButton, QFileDialog, QComboBox, QProgressBar, QMessageBox, QLineEdit, QHBoxLayout, QInputDialog)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from typing import List, Literal, Optional
import re
import requests
import zipfile
import shutil
from enum import Enum, auto

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
}
PYTHON_VER = "3.13"
BASE_FILENAME = f"hlmod-hl-nightly-python{PYTHON_VER}-"
FILENAME_END = ".zip"
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
# TODO: windows

class Tweak(Enum):
    USE_EXISTING_STEAM = auto()
    INSTALL_DCMOD = auto()
    NO_BASE_MODS = auto()

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

    def __init__(self, directory, version: Literal["latest"]|str, type: str):
        super().__init__()
        self.directory = directory
        self.version = version
        self.type = type

    def run(self):
        if self.version == "latest":
            self.status_signal.emit(f"Finding latest version...")
            r = requests.get(f"https://api.github.com/repos/{REPO}/commits/main")
            try:
                r.raise_for_status()
            except:
                self.status_signal.emit("Failed to find latest version!")
                return
            self.version = r.json()["sha"]
            
        assert self.version != "latest"
        self.status_signal.emit(f"Finding build...")
        self.progress_signal.emit(5) 
        
        r = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs?head_sha={self.version}")
        try:
            r.raise_for_status()
        except:
            self.status_signal.emit("Failed to find build!")
            return
        j = r.json()
        run_id: Optional[int] = None
        for run_i in j["workflow_runs"]:
            if run_i["name"] == "Nightly Build":
                if run_i["conclusion"] == "success":
                    run_id = run_i["id"]
        if run_id == None:
            self.status_signal.emit(f"Failed to find successful build!")
            return
        
        self.status_signal.emit(f"Downloading hlmod {self.version[0:7]} from {run_id}")
        self.progress_signal.emit(10) # 10-60% will be downloading
        url = f"https://nightly.link/{REPO}/actions/runs/{run_id}/{BASE_FILENAME}{self.type}{FILENAME_END}"
        print(f"Using: {url}")
        assert url is not None
        with requests.get(url, stream=True, allow_redirects=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            chunk_size = 8192
            downloaded_bytes = 0             
            with open(os.path.join(self.directory, "temp.zip"), 'wb') as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk: # filter out keep-alive new chunks
                        size = f.write(chunk)
                        downloaded_bytes += size
                        
                        if total_size > 0:
                            if downloaded_bytes % (1024*1024) < chunk_size: 
                                print(f"{downloaded_bytes}/{total_size}")
                                self.progress_signal.emit(round(map_value(downloaded_bytes, 0, total_size, 10, 60)))
        print("Done downloading")
        self.status_signal.emit(f"Extracting...")
        self.progress_signal.emit(60)
        
        zip_file = os.path.join(self.directory, "temp.zip")
        extract_dir = os.path.join(self.directory, "hlmod")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_file, 'r') as zf:
            file_list = zf.infolist()
            total_uncompressed_size = sum(f.file_size for f in file_list)
            current_uncompressed_size = 0
            for member in file_list:
                zf.extract(member, extract_dir)
                current_uncompressed_size += member.file_size
                if total_uncompressed_size > 0:
                    val = map_value(current_uncompressed_size, 0, total_uncompressed_size, 60, 70)
                    self.progress_signal.emit(round(val))
                    
        self.status_signal.emit(f"Auto-detecting configuration...")
        self.progress_signal.emit(70)
        
        tweaks: List[Tweak] = []
        if os.path.exists(os.path.join(self.directory, "steam.hdll")) and os.name == "posix":
            print("Using existing hlsteam.")
            tweaks.append(Tweak.USE_EXISTING_STEAM)
        if os.path.exists(os.path.join(self.directory, "deadcells")) or os.path.exists(os.path.join(self.directory, "deadcells.exe")):
            print("Installing hlmod.")
            tweaks.append(Tweak.INSTALL_DCMOD)
        
        self.status_signal.emit(f"Installing...")
        self.progress_signal.emit(80)
        
        shutil.rmtree(os.path.join(self.directory, "mods"), ignore_errors=True)
        
        if os.name == "posix":
            make_executable(os.path.join(extract_dir, "hl"))
            make_executable(os.path.join(extract_dir, "hl.bin"))
            with open(os.path.join(self.directory, "run_hlmod.sh"), "w") as f:
                f.write(LAUNCH_SCRIPT_LINUX)
            make_executable(os.path.join(self.directory, "run_hlmod.sh"))
            if Tweak.USE_EXISTING_STEAM in tweaks:
                shutil.copy(os.path.join(self.directory, "steam.hdll"), os.path.join(extract_dir, "steam.hdll"))
                shutil.copy(os.path.join(self.directory, "libsteam_api.so"), os.path.join(extract_dir, "libsteam_api.so"))
        
        if Tweak.INSTALL_DCMOD in tweaks:
            shutil.copytree(os.path.join(extract_dir, "mods", "dcmod"), os.path.join(self.directory, "mods", "dcmod"))
        
        if not Tweak.NO_BASE_MODS in tweaks:
            shutil.copy(os.path.join(extract_dir, "mods", "hlobj.py"), os.path.join(self.directory, "mods", "hlobj.py"))
            shutil.copytree(os.path.join(extract_dir, "mods", "modcore"), os.path.join(self.directory, "mods", "modcore"))

        shutil.copy(os.path.join(extract_dir, "mods", "hlmod.pyi"), os.path.join(self.directory, "mods", "hlmod.pyi"))
         
        self.status_signal.emit(f"Done!")
        self.progress_signal.emit(100)
        
                

class InstallerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("hlmod Installer")
        self.setGeometry(300, 300, 500, 350)

        layout = QVBoxLayout()
        layout.setSpacing(15)

        title = QLabel("hlmod Installer")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
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

        self.status_label = QLabel("Ready to install.")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

        self.install_btn = QPushButton("INSTALL")
        self.install_btn.setMinimumHeight(50)
        self.install_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; font-size: 14px;")
        self.install_btn.clicked.connect(self.start_installation)
        
        layout.addWidget(self.install_btn)

        self.setLayout(layout)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Game Folder")
        if folder:
            self.path_input.setText(folder)

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

        version = "latest" if self.version_combo.currentText() != "Custom" else version_override
        assert version is not None
        self.worker = InstallWorker(target_dir, version, LINUX_OPTIONS.get(self.type_combo.currentText()) if os.name == "posix" else WIN_OPTIONS.get(self.type_combo.currentText()))
        
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.status_signal.connect(self.update_status)
        self.worker.finished_signal.connect(self.installation_finished)
        
        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, text):
        self.status_label.setText(text)

    def installation_finished(self):
        QMessageBox.information(self, "Success", "hlmod is now installed!")
        self.install_btn.setEnabled(True)
        self.path_input.setEnabled(True)
        self.version_combo.setEnabled(True)
        self.type_combo.setEnabled(True)
        self.install_btn.setText("INSTALL (Done!)")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setStyle("Fusion")
    
    window = InstallerWindow()
    window.show()
    sys.exit(app.exec())