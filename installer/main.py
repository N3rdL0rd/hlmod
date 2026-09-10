import os
import sys
from typing import Optional

from hlmod_sdk.installer import (
    BUILD_TYPE_LABELS,
    TWEAK_LABELS,
    InstallCallbacks,
    InstallCancelled,
    InstallError,
    Tweak,
    default_build_types,
    install,
)
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


class InstallWorker(QThread):
    """
    Runs `hlmod_sdk.installer.install()` in the background so the GUI
    doesn't freeze; the actual install logic lives in hlmod-sdk so the GUI
    and `hlmod-sdk install` never drift apart.
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
        callbacks = InstallCallbacks(
            on_status=self.status_signal.emit,
            on_progress=self.progress_signal.emit,
            should_cancel=self.isInterruptionRequested,
        )
        try:
            install(
                self.directory, self.build_type, version=self.version,
                tweaks=self.manual_tweaks, auto_detect=self.auto_detect, callbacks=callbacks,
            )
        except (InstallError, InstallCancelled) as error:
            self.error_signal.emit(str(error))
            return
        self.finished_signal.emit()


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
        self.build_types = {BUILD_TYPE_LABELS.get(key, key): value for key, value in default_build_types().items()}
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
        self.type_combo.addItems(self.build_types.keys())

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
        build_type = self.build_types.get(self.type_combo.currentText())
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
        if message == str(InstallCancelled()):
            QMessageBox.information(self, "Cancelled", message)
        else:
            QMessageBox.critical(self, "Error", f"Installation failed: {message}")
        self._reset_controls()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setStyle("Fusion")

    window = InstallerWindow()
    window.show()
    sys.exit(app.exec())
