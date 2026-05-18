"""
DAGZip Delta & Snapshot Module

Provides algorithms to compare two DAGZip archives. By leveraging the DAG 
manifests and chunk cryptographic hashes, it calculates file differences 
(Added, Removed, Modified, Identical) with extreme efficiency without 
needing to decompress the actual file payloads.
"""

import os
from typing import Dict, List, Any, Tuple
from .extractor import ArchiveExtractor

class ArchiveDiff:
    """
    Analyzes the differences between two DAGZip archives.
    """
    
    def __init__(self, old_archive_path: str, new_archive_path: str, 
                 old_password: str = "", new_password: str = ""):
        """
        Initializes the diff engine by extracting ONLY the manifests from both archives.
        """
        self.old_extractor = ArchiveExtractor(old_archive_path, old_password)
        self.new_extractor = ArchiveExtractor(new_archive_path, new_password)
        
        # Flatten the nested tree graphs into simple 1D dictionaries.
        # We pass is_root=True so the top-level folder name (e.g. 'test_v1') 
        # is ignored, allowing us to compare the actual contents accurately.
        self.old_files = self._flatten_tree(self.old_extractor.manifest["root"], is_root=True)
        self.new_files = self._flatten_tree(self.new_extractor.manifest["root"], is_root=True)

    def _flatten_tree(self, node: Dict[str, Any], current_path: str = "", is_root: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Recursively converts a tree graph into a flat dictionary using Depth-First Search.
        """
        flat_map = {}
        
        # If this is the root node, we do NOT append its name to the path.
        # This prevents "test_v1/file.txt" and "test_v2/file.txt" from being seen as different.
        if is_root:
            target_path = current_path
        else:
            target_path = os.path.join(current_path, node["name"]).replace("\\", "/")
            
        if node["type"] == "file":
            flat_map[target_path] = node
        elif node["type"] == "directory":
            for child in node.get("children", []):
                # Pass is_root=False for all subsequent children
                flat_map.update(self._flatten_tree(child, target_path, is_root=False))
                
        return flat_map

    def compute_diff(self) -> Dict[str, List[str]]:
        """
        Calculates the exact differences between the two snapshots.
        """
        diff_report: Dict[str, List[str]] = {
            "added": [],
            "removed": [],
            "modified": [],
            "identical": []
        }
        
        old_keys = set(self.old_files.keys())
        new_keys = set(self.new_files.keys())
        
        diff_report["added"] = list(new_keys - old_keys)
        diff_report["removed"] = list(old_keys - new_keys)
        
        intersection = old_keys.intersection(new_keys)
        
        for filepath in intersection:
            old_node = self.old_files[filepath]
            new_node = self.new_files[filepath]
            
            # Compare the arrays of SHA-256 chunk hashes
            if old_node["chunks"] == new_node["chunks"]:
                diff_report["identical"].append(filepath)
            else:
                diff_report["modified"].append(filepath)
                
        for key in diff_report:
            diff_report[key].sort()
            
        return diff_report


def print_diff_report(old_archive: str, new_archive: str, old_pwd: str = "", new_pwd: str = "") -> None:
    """Helper function to run and pretty-print the diff report to the terminal."""
    differ = ArchiveDiff(old_archive, new_archive, old_pwd, new_pwd)
    report = differ.compute_diff()
    
    from rich.console import Console
    console = Console()
    
    console.print(f"\n[bold yellow]Archive Diff Report[/bold yellow]")
    console.print(f"Old: [cyan]{old_archive}[/cyan]")
    console.print(f"New: [cyan]{new_archive}[/cyan]\n")
    
    if report["added"]:
        console.print("[bold green]Added Files:[/bold green]")
        for f in report["added"]: console.print(f"  + {f}")
        
    if report["removed"]:
        console.print("\n[bold red]Removed Files:[/bold red]")
        for f in report["removed"]: console.print(f"  - {f}")
        
    if report["modified"]:
        console.print("\n[bold blue]Modified Files:[/bold blue]")
        for f in report["modified"]: console.print(f"  ~ {f}")
        
    if not (report["added"] or report["removed"] or report["modified"]):
        console.print("[bold green]Archives are completely identical.[/bold green]")
    else:
        console.print(f"\n[dim]{len(report['identical'])} files remained unchanged.[/dim]")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m dagzip.diff <old.dgz> <new.dgz>")
    else:
        print_diff_report(sys.argv[1], sys.argv[2])
