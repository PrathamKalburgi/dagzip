"""
DAGZip Shared Utilities Module

This module contains helper functions for formatting, file system checks,
and common operations shared across the CLI, GUI, and server.
"""

import os
from typing import Tuple

def format_size(size_in_bytes: int) -> str:
    """
    Converts a raw byte count into a human-readable string.
    Uses base-2 (1024) calculations (KiB, MiB, GiB).
    """
    if size_in_bytes < 1024:
        return f"{size_in_bytes} bytes"
        
    # FIX: Added 'bytes' to index 0 so the first division (/1024) correctly 
    # shifts the unit_index to 1 (KB).
    units = ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    calculated_size = float(size_in_bytes)
    
    while calculated_size >= 1024.0 and unit_index < len(units) - 1:
        calculated_size /= 1024.0
        unit_index += 1
        
    return f"{calculated_size:.2f} {units[unit_index]}"

def get_directory_stats(dir_path: str) -> Tuple[int, int]:
    """
    Recursively calculates the total size and file count of a directory.
    Uses os.scandir() for optimal 7200 RPM HDD mechanical traversal.
    """
    total_size = 0
    total_files = 0
    stack = [dir_path]
    
    while stack:
        current_path = stack.pop()
        try:
            with os.scandir(current_path) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat().st_size
                        total_files += 1
                    elif entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
        except PermissionError:
            continue
            
    return total_size, total_files
