"""
DAGZip Main GUI Window

This module provides a PyQt6 desktop interface for the DAGZip archiver.
It utilizes QThread to perform heavy packing and unpacking operations in 
the background, ensuring the GUI remains responsive.
"""

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTabWidget,
    QTextEdit, QMessageBox, QGroupBox, QProgressBar, QCheckBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont

from dagzip.dag_builder import create_archive
from dagzip.extractor import extract_archive
from gui.dag_viewer import DAGViewerDialog

# -------------------------------------------------------------------------
# Background Worker Threads
# -------------------------------------------------------------------------

class PackWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, source_dir: str, output_path: str, password: str):
        super().__init__()
        self.source_dir = source_dir
        self.output_path = output_path
        self.password = password

    def run(self):
        self.log_signal.emit(f"Starting pack operation...\nSource: {self.source_dir}\nOutput: {self.output_path}")
        try:
            create_archive(
                source=self.source_dir, 
                destination=self.output_path, 
                use_encryption=bool(self.password), 
                password=self.password
            )
            self.finished_signal.emit(True, "Packing completed successfully!")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class UnpackWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, archive_path: str, dest_dir: str, password: str, strip_root: bool):
        super().__init__()
        self.archive_path = archive_path
        self.dest_dir = dest_dir
        self.password = password
        self.strip_root = strip_root

    def run(self):
        mode = "STRIPPED ROOT" if self.strip_root else "PRESERVED ROOT"
        self.log_signal.emit(f"Starting unpack operation ({mode})...\nArchive: {self.archive_path}\nDestination: {self.dest_dir}")
        try:
            extract_archive(
                archive_path=self.archive_path, 
                destination=self.dest_dir, 
                password=self.password,
                strip_root=self.strip_root
            )
            self.finished_signal.emit(True, "Extraction completed successfully!")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

# -------------------------------------------------------------------------
# Main GUI Window
# -------------------------------------------------------------------------

class DAGZipMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DAGZip - Content Defined Archiver")
        self.resize(750, 600)
        self._apply_stylesheet()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        title_label = QLabel("DAGZip Manager")
        title_label.setFont(QFont("Consolas", 20, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        self.tabs = QTabWidget()
        self.tab_pack = QWidget()
        self.tab_unpack = QWidget()
        self.tabs.addTab(self.tab_pack, "Pack Archive")
        self.tabs.addTab(self.tab_unpack, "Unpack Archive")
        main_layout.addWidget(self.tabs)

        self._setup_pack_tab()
        self._setup_unpack_tab()

        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas;")
        main_layout.addWidget(QLabel("System Console:"))
        main_layout.addWidget(self.console_output)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; }
            QLabel { color: #e0e0e0; }
            QLineEdit { background-color: #3c3f41; color: #ffffff; border: 1px solid #555555; padding: 5px; border-radius: 3px; }
            QPushButton { background-color: #007acc; color: white; border: none; padding: 8px 15px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #005999; }
            QPushButton:disabled { background-color: #555555; color: #aaaaaa; }
            QTabWidget::pane { border: 1px solid #555555; background: #2b2b2b; }
            QTabBar::tab { background: #3c3f41; color: #aaaaaa; padding: 8px 20px; border: 1px solid #555555; }
            QTabBar::tab:selected { background: #2b2b2b; color: #ffffff; border-bottom: none; }
            QGroupBox { color: #e0e0e0; font-weight: bold; border: 1px solid #555555; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
            QCheckBox { color: #e0e0e0; font-weight: bold; margin-top: 5px; }
        """)

    def _setup_pack_tab(self):
        layout = QVBoxLayout(self.tab_pack)
        
        src_layout = QHBoxLayout()
        self.pack_src_input = QLineEdit()
        self.pack_src_input.setPlaceholderText("Select folder to pack...")
        btn_browse_src = QPushButton("Browse Folder")
        btn_browse_src.clicked.connect(lambda: self.pack_src_input.setText(QFileDialog.getExistingDirectory(self) or self.pack_src_input.text()))
        src_layout.addWidget(self.pack_src_input)
        src_layout.addWidget(btn_browse_src)
        layout.addLayout(src_layout)

        out_layout = QHBoxLayout()
        self.pack_out_input = QLineEdit()
        self.pack_out_input.setPlaceholderText("Save archive as (.dgz)...")
        btn_browse_out = QPushButton("Save As...")
        btn_browse_out.clicked.connect(lambda: self.pack_out_input.setText(QFileDialog.getSaveFileName(self, filter="DAGZip (*.dgz)")[0] or self.pack_out_input.text()))
        out_layout.addWidget(self.pack_out_input)
        out_layout.addWidget(btn_browse_out)
        layout.addLayout(out_layout)

        enc_group = QGroupBox("Security Options (Optional)")
        enc_layout = QHBoxLayout()
        self.pack_pwd_input = QLineEdit()
        self.pack_pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pack_pwd_input.setPlaceholderText("Enter password to encrypt (Leave blank for no encryption)")
        enc_layout.addWidget(self.pack_pwd_input)
        enc_group.setLayout(enc_layout)
        layout.addWidget(enc_group)

        btn_layout = QHBoxLayout()
        self.btn_pack_start = QPushButton("START PACKING")
        self.btn_pack_start.setStyleSheet("background-color: #28a745; font-size: 14px; padding: 12px;")
        self.btn_pack_start.clicked.connect(self._start_packing)
        
        self.btn_pack_cancel = QPushButton("CANCEL")
        self.btn_pack_cancel.setStyleSheet("background-color: #d32f2f; font-size: 14px; padding: 12px;")
        self.btn_pack_cancel.clicked.connect(self._cancel_packing)
        self.btn_pack_cancel.setEnabled(False)
        
        btn_layout.addWidget(self.btn_pack_start)
        btn_layout.addWidget(self.btn_pack_cancel)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def _setup_unpack_tab(self):
        layout = QVBoxLayout(self.tab_unpack)
        
        arc_layout = QHBoxLayout()
        self.unpack_src_input = QLineEdit()
        self.unpack_src_input.setPlaceholderText("Select .dgz archive to extract...")
        btn_browse_arc = QPushButton("Browse Archive")
        btn_browse_arc.clicked.connect(lambda: self.unpack_src_input.setText(QFileDialog.getOpenFileName(self, filter="DAGZip (*.dgz)")[0] or self.unpack_src_input.text()))
        arc_layout.addWidget(self.unpack_src_input)
        arc_layout.addWidget(btn_browse_arc)
        layout.addLayout(arc_layout)

        out_layout = QHBoxLayout()
        self.unpack_out_input = QLineEdit()
        self.unpack_out_input.setPlaceholderText("Select destination folder...")
        btn_browse_out = QPushButton("Select Folder")
        btn_browse_out.clicked.connect(lambda: self.unpack_out_input.setText(QFileDialog.getExistingDirectory(self) or self.unpack_out_input.text()))
        out_layout.addWidget(self.unpack_out_input)
        out_layout.addWidget(btn_browse_out)
        layout.addLayout(out_layout)

        # NEW FEATURE: Strip Root Checkbox
        self.chk_strip_root = QCheckBox(" Extract contents directly into destination (Strip Root Folder)")
        self.chk_strip_root.setChecked(True) # Set to true by default as it's common preference!
        layout.addWidget(self.chk_strip_root)

        dec_group = QGroupBox("Security Details")
        dec_layout = QHBoxLayout()
        self.unpack_pwd_input = QLineEdit()
        self.unpack_pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.unpack_pwd_input.setPlaceholderText("Enter password if archive is encrypted")
        dec_layout.addWidget(self.unpack_pwd_input)
        dec_group.setLayout(dec_layout)
        layout.addWidget(dec_group)

        btn_layout = QHBoxLayout()
        self.btn_unpack_start = QPushButton("START EXTRACTION")
        self.btn_unpack_start.setStyleSheet("background-color: #d32f2f; font-size: 14px; padding: 12px;")
        self.btn_unpack_start.clicked.connect(self._start_unpacking)
        
        self.btn_unpack_cancel = QPushButton("CANCEL")
        self.btn_unpack_cancel.setStyleSheet("background-color: #555555; font-size: 14px; padding: 12px;")
        self.btn_unpack_cancel.clicked.connect(self._cancel_unpacking)
        self.btn_unpack_cancel.setEnabled(False)

        btn_layout.addWidget(self.btn_unpack_start)
        btn_layout.addWidget(self.btn_unpack_cancel)
        layout.addLayout(btn_layout)

        self.btn_inspect = QPushButton("INSPECT ARCHIVE CONTENTS (DAG Viewer)")
        self.btn_inspect.setStyleSheet("background-color: #007acc; font-size: 14px; padding: 12px; margin-top: 10px;")
        self.btn_inspect.clicked.connect(self._open_inspector)
        layout.addWidget(self.btn_inspect)
        
        layout.addStretch()

    def log(self, message: str):
        self.console_output.append(f"> {message}")

    def _open_inspector(self):
        archive_path = self.unpack_src_input.text().strip()
        if not archive_path or not os.path.exists(archive_path):
            QMessageBox.warning(self, "Input Error", "Please select a valid .dgz archive to inspect.")
            return
            
        viewer = DAGViewerDialog(archive_path, self)
        pwd = self.unpack_pwd_input.text()
        if viewer.load_manifest(pwd):
            viewer.exec()

    def _start_packing(self):
        src = self.pack_src_input.text().strip()
        dest = self.pack_out_input.text().strip()
        pwd = self.pack_pwd_input.text()

        if not src or not dest: return
        self.btn_pack_start.setEnabled(False)
        self.btn_pack_cancel.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.tabs.setTabEnabled(1, False)

        self.pack_worker = PackWorker(src, dest, pwd)
        self.pack_worker.log_signal.connect(self.log)
        self.pack_worker.finished_signal.connect(self._on_pack_finished)
        self.pack_worker.start()

    def _cancel_packing(self):
        if hasattr(self, 'pack_worker') and self.pack_worker.isRunning():
            self.pack_worker.terminate()
            self.pack_worker.wait()
            self.log("[WARNING] Packing cancelled.")
            self._reset_pack_ui()

    def _start_unpacking(self):
        src = self.unpack_src_input.text().strip()
        dest = self.unpack_out_input.text().strip()
        pwd = self.unpack_pwd_input.text()
        strip = self.chk_strip_root.isChecked()

        if not src or not dest: return
        self.btn_unpack_start.setEnabled(False)
        self.btn_unpack_cancel.setEnabled(True)
        self.btn_inspect.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.tabs.setTabEnabled(0, False)

        self.unpack_worker = UnpackWorker(src, dest, pwd, strip)
        self.unpack_worker.log_signal.connect(self.log)
        self.unpack_worker.finished_signal.connect(self._on_unpack_finished)
        self.unpack_worker.start()

    def _cancel_unpacking(self):
        if hasattr(self, 'unpack_worker') and self.unpack_worker.isRunning():
            self.unpack_worker.terminate()
            self.unpack_worker.wait()
            self.log("[WARNING] Extraction cancelled.")
            self._reset_unpack_ui()

    def _on_pack_finished(self, success: bool, message: str):
        self._reset_pack_ui()
        self.log(f"[{'SUCCESS' if success else 'ERROR'}] {message}")
        if not success: QMessageBox.critical(self, "Error", message)

    def _on_unpack_finished(self, success: bool, message: str):
        self._reset_unpack_ui()
        self.log(f"[{'SUCCESS' if success else 'ERROR'}] {message}")
        if not success: QMessageBox.critical(self, "Error", message)

    def _reset_pack_ui(self):
        self.progress_bar.setVisible(False)
        self.btn_pack_start.setEnabled(True)
        self.btn_pack_cancel.setEnabled(False)
        self.tabs.setTabEnabled(1, True)

    def _reset_unpack_ui(self):
        self.progress_bar.setVisible(False)
        self.btn_unpack_start.setEnabled(True)
        self.btn_unpack_cancel.setEnabled(False)
        self.btn_inspect.setEnabled(True)
        self.tabs.setTabEnabled(0, True)

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    window = DAGZipMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
