"""
DAGZip GUI Utilities

This module provides helper functions specifically for the PyQt6 interface.
It handles the mapping of the internal DAG manifest (JSON/Dict) into 
visual elements for the QTreeWidget.
"""

from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from dagzip.utils import format_size

# Column indices for the DAG Viewer Tree to maintain consistency
COL_NAME = 0
COL_TYPE = 1
COL_SIZE = 2
COL_CHUNKS = 3

def populate_tree_from_manifest(node: dict, parent_item: QTreeWidgetItem):
    """
    Recursively populates a QTreeWidget with the DAG manifest.
    
    This function is optimized for large directory structures (like Android 
    Studio projects). it sorts folders to the top and binds the raw data 
    nodes to the UI elements for on-demand extraction.
    """
    item = QTreeWidgetItem(parent_item)
    
    # 1. Set basic text properties
    item.setText(COL_NAME, node["name"])
    
    # 2. Bind the raw node data (the JSON-like dict) to the UI element.
    # We use Qt.ItemDataRole.UserRole to store the Python dictionary invisibly.
    # This allows the GUI to "know" which chunks belong to which file when clicked.
    item.setData(COL_NAME, Qt.ItemDataRole.UserRole, node)
    
    if node["type"] == "directory":
        item.setText(COL_TYPE, "Folder")
        item.setText(COL_SIZE, "--")
        
        # Stylize folders with a distinct color (Cyberpunk Cyan)
        item.setForeground(COL_NAME, Qt.GlobalColor.cyan)
        
        # 3. Handle Thousands of Files: Sorting
        # We sort children so that directories appear at the top, followed by 
        # files in alphabetical order. This makes navigation much faster 
        # for human users.
        children = sorted(
            node.get("children", []), 
            key=lambda x: (x["type"] != "directory", x["name"].lower())
        )
        
        for child in children:
            populate_tree_from_manifest(child, item)
            
    elif node["type"] == "file":
        item.setText(COL_TYPE, "File")
        item.setText(COL_SIZE, format_size(node.get("size", 0)))
        
        # Files get a distinct color (Deduplication Green)
        item.setForeground(COL_NAME, Qt.GlobalColor.green)
        
        # If the node has chunks, we show the count
        chunk_count = len(node.get("chunks", []))
        # Note: We use a separate column for chunk count in the viewer
        # item.setText(COL_CHUNKS, str(chunk_count))

def get_node_stats(node: dict) -> str:
    """
    Returns a quick summary string for a selected node.
    Useful for status bars or tooltips.
    """
    if node["type"] == "file":
        return f"File: {node['name']} ({format_size(node['size'])}, {len(node['chunks'])} chunks)"
    return f"Folder: {node['name']} ({len(node.get('children', []))} items)"
