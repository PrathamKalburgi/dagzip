"""
DAGZip Visual DAG Viewer

Provides a graphical PyQt6 dialog to inspect the internal DAG manifest 
and optionally extract specific isolated files or subfolders directly 
from the UI using QThread to prevent UI freezing.
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
    QPushButton, QLabel, QHeaderView, QMessageBox, QLineEdit, QHBoxLayout,
    QFileDialog, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from dagzip.extractor import ArchiveExtractor
from dagzip.utils import format_size


class SpecificExtractionWorker(QThread):
    """Background thread specifically for extracting isolated nodes from the Viewer."""
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, archive_path: str, password: str, target_node: dict, dest_dir: str):
        super().__init__()
        self.archive_path = archive_path
        self.password = password
        self.target_node = target_node
        self.dest_dir = dest_dir

    def run(self):
        try:
            # We instantiate a fresh extractor just for this operation
            extractor = ArchiveExtractor(self.archive_path, self.password)
            extractor.extract_specific_node(self.target_node, self.dest_dir)
            self.finished_signal.emit(True, f"Successfully extracted '{self.target_node['name']}' to {self.dest_dir}")
        except Exception as e:
            self.finished_signal.emit(False, f"Extraction failed: {str(e)}")


class DAGViewerDialog(QDialog):
    """A pop-up window that visualizes the JSON manifest as an interactive tree."""
    
    def __init__(self, archive_path: str, parent=None):
        super().__init__(parent)
        self.archive_path = archive_path
        self.current_password = ""  # We store this so the extraction worker can use it later
        
        self.setWindowTitle(f"Archive Inspector - {os.path.basename(archive_path)}")
        self.resize(850, 600)
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #e0e0e0; }
            QTreeWidget { background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #555555; font-family: Consolas; font-size: 13px; }
            QTreeWidget::item:hover { background-color: #2a2d2f; }
            QTreeWidget::item:selected { background-color: #007acc; color: white; }
            QHeaderView::section { background-color: #3c3f41; color: white; padding: 5px; border: 1px solid #555555; font-weight: bold; }
        """)

        layout = QVBoxLayout(self)

        self.info_label = QLabel(f"Inspecting: {self.archive_path}")
        self.info_label.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        layout.addWidget(self.info_label)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Name", "Type", "Original Size", "Chunks"])
        self.tree.itemSelectionChanged.connect(self._on_item_selected)
        
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.tree)

        # Extraction Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_extract = QPushButton("Extract Selected Item...")
        self.btn_extract.setStyleSheet("background-color: #28a745; color: white; padding: 8px; font-weight: bold;")
        self.btn_extract.clicked.connect(self._extract_selected)
        self.btn_extract.setEnabled(False) # Disabled until they click a file/folder
        
        btn_close = QPushButton("Close Inspector")
        btn_close.setStyleSheet("background-color: #555555; color: white; padding: 8px;")
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.btn_extract)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)

    def load_manifest(self, password: str = "") -> bool:
        try:
            extractor = ArchiveExtractor(self.archive_path, password)
            manifest_root = extractor.manifest["root"]
            
            # Save the successful password
            self.current_password = password if password else ""
            
            self.info_label.setText(
                f"Inspecting: {os.path.basename(self.archive_path)} "
                f"| Unique Pool Chunks: {len(extractor.chunk_registry)}"
            )
            
            self._populate_tree(manifest_root, self.tree.invisibleRootItem())
            if self.tree.topLevelItemCount() > 0:
                self.tree.topLevelItem(0).setExpanded(True)
                
            return True
        except ValueError as e:
            if "password" in str(e).lower() or "tag" in str(e).lower():
                return self._prompt_for_password()
            else:
                QMessageBox.critical(self, "Read Error", f"Failed to read archive:\n{e}")
                return False

    def _prompt_for_password(self) -> bool:
        from PyQt6.QtWidgets import QInputDialog
        pwd, ok = QInputDialog.getText(self, "Encrypted Archive", "Enter password:", QLineEdit.EchoMode.Password)
        if ok and pwd:
            return self.load_manifest(pwd)
        return False

    def _populate_tree(self, node: dict, parent_item: QTreeWidgetItem):
        item = QTreeWidgetItem(parent_item)
        item.setText(0, node["name"])
        
        # MAGIC: We invisibly attach the raw JSON node dictionary to this UI item!
        item.setData(0, Qt.ItemDataRole.UserRole, node)
        
        if node["type"] == "directory":
            item.setText(1, "Folder")
            item.setText(2, "--")
            item.setText(3, "--")
            item.setForeground(0, Qt.GlobalColor.cyan)
            for child in node.get("children", []):
                self._populate_tree(child, item)
                
        elif node["type"] == "file":
            item.setText(1, "File")
            item.setText(2, format_size(node["size"]))
            item.setText(3, str(len(node["chunks"])))
            item.setForeground(0, Qt.GlobalColor.green)

    def _on_item_selected(self):
        """Enables the extract button only if something is actually selected."""
        self.btn_extract.setEnabled(bool(self.tree.selectedItems()))

    def _extract_selected(self):
        selected_items = self.tree.selectedItems()
        if not selected_items: return
        
        # Retrieve the hidden JSON node dictionary from the UI element
        target_node = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
        
        dest_dir = QFileDialog.getExistingDirectory(self, f"Select destination for '{target_node['name']}'")
        if not dest_dir: return
        
        # Lock UI to prevent clicking multiple times
        self.btn_extract.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        # Spin up the background thread to decrypt and decompress the file
        self.worker = SpecificExtractionWorker(
            archive_path=self.archive_path,
            password=self.current_password,
            target_node=target_node,
            dest_dir=dest_dir
        )
        self.worker.finished_signal.connect(self._on_extraction_finished)
        self.worker.start()

    def _on_extraction_finished(self, success: bool, message: str):
        self.progress_bar.setVisible(False)
        self.btn_extract.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Extraction Complete", message)
        else:
            QMessageBox.critical(self, "Extraction Error", message)
