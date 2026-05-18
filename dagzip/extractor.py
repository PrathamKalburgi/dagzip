"""
DAGZip Archive Extractor Module (Patched)

Handles adaptive chunk decompression with robust fallback logic to prevent
Enum initialization errors when mixed compression modes are used.
"""

import os
import struct
import msgpack
from typing import Dict, Any, Optional

from .compressor import decompress_chunk, CompressionAlgo
from .encryptor import ChunkEncryptor, EncryptionAlgo


class ArchiveExtractor:
    def __init__(self, archive_path: str, password: Optional[str] = None):
        self.archive_path = archive_path
        self.password = password
        self.file_stream = open(self.archive_path, 'rb')
        self._read_header()
        
        self.encryptor = None
        if self.encryption_algo == EncryptionAlgo.AES_256_GCM:
            if not self.password: raise ValueError("This archive is encrypted. A password is required.")
            self.encryptor = ChunkEncryptor(self.password, self.salt)
            
        self.manifest_offset, self.manifest_size = self._read_footer()
        self.manifest = self._load_manifest()
        self.chunk_registry = self.manifest["chunks"]

    def _read_header(self) -> None:
        self.file_stream.seek(0)
        unpacked = struct.unpack("<4s B B 16s 42s", self.file_stream.read(64))
        self.compression_algo = CompressionAlgo(unpacked[1])
        self.encryption_algo = EncryptionAlgo(unpacked[2])
        self.salt = unpacked[3]

    def _read_footer(self) -> tuple[int, int]:
        self.file_stream.seek(-16, os.SEEK_END)
        return struct.unpack("<Q Q", self.file_stream.read(16))

    def _load_manifest(self) -> Dict[str, Any]:
        self.file_stream.seek(self.manifest_offset)
        raw_manifest = self.file_stream.read(self.manifest_size)
        if self.encryptor:
            raw_manifest = self.encryptor.decrypt(raw_manifest, self.encryption_algo)
        import zstandard as zstd
        if self.compression_algo == CompressionAlgo.ZSTANDARD:
            manifest_bytes = zstd.ZstdDecompressor().decompress(raw_manifest)
        else:
            manifest_bytes = raw_manifest
        return msgpack.unpackb(manifest_bytes, raw=False)

    def _get_chunk_data(self, chunk_hash: str) -> bytes:
        chunk_info = self.chunk_registry[chunk_hash]
        self.file_stream.seek(chunk_info["offset"])
        stored_size = struct.unpack("<I", self.file_stream.read(4))[0]
        payload = self.file_stream.read(stored_size)
        
        if self.encryptor:
            payload = self.encryptor.decrypt(payload, self.encryption_algo)
            
        # FIXED: Robust fallback logic
        # We check if the key exists AND is not None. 
        # If it's missing or Null, we use the archive's default compression.
        override = chunk_info.get("algo_override")
        algo = CompressionAlgo(override) if override is not None else self.compression_algo
        
        return decompress_chunk(payload, algo, chunk_info["original_size"])

    def _extract_node(self, node: Dict[str, Any], current_path: str) -> None:
        target_path = os.path.join(current_path, node["name"])
        if node["type"] == "directory":
            os.makedirs(target_path, exist_ok=True)
            for child in node.get("children", []):
                self._extract_node(child, target_path)
            os.chmod(target_path, node["metadata"]["permissions"])
            os.utime(target_path, (node["metadata"]["mtime"], node["metadata"]["mtime"]))
        elif node["type"] == "file":
            with open(target_path, 'wb') as out_file:
                for chunk_hash in node["chunks"]:
                    out_file.write(self._get_chunk_data(chunk_hash))
            os.chmod(target_path, node["metadata"]["permissions"])
            os.utime(target_path, (node["metadata"]["mtime"], node["metadata"]["mtime"]))

    def extract(self, destination_dir: str, strip_root: bool = False) -> None:
        if not os.path.exists(destination_dir): os.makedirs(destination_dir)
        root_node = self.manifest["root"]
        if strip_root:
            for child in root_node.get("children", []): self._extract_node(child, destination_dir)
        else:
            self._extract_node(root_node, destination_dir)
        self.file_stream.close()

    def extract_specific_node(self, target_node: Dict[str, Any], destination_dir: str) -> None:
        if not os.path.exists(destination_dir): os.makedirs(destination_dir)
        self._extract_node(target_node, destination_dir)
        self.file_stream.close()

def extract_archive(archive_path: str, destination: str, password: str = "", strip_root: bool = False) -> None:
    extractor = ArchiveExtractor(archive_path, password=password if password else None)
    extractor.extract(destination, strip_root)
