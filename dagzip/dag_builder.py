"""
DAGZip Archive Builder Module (Patched)

Fixed the algo_override logic to prevent Null-pointer exceptions during 
extraction of mixed-mode archives.
"""

import os
import time
import struct
import msgpack
from typing import Dict, List, Any, Optional

from .chunker import chunk_file, chunk_file_fixed
from .compressor import compress_chunk, CompressionAlgo
from .encryptor import ChunkEncryptor, EncryptionAlgo, generate_salt

HIGH_ENTROPY_EXTENSIONS = {
    '.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg',
    '.mp4', '.mkv', '.avi', '.mov', '.webm',
    '.zip', '.rar', '.7z', '.gz', '.tar.gz', '.dgz',
    '.jpg', '.jpeg', '.png', '.gif', '.webp',
    '.jar', '.apk', '.exe' # Added common Android Studio binary types
}

class ArchiveBuilder:
    def __init__(
        self,
        output_path: str,
        compression_algo: CompressionAlgo = CompressionAlgo.ZSTANDARD,
        encryption_algo: EncryptionAlgo = EncryptionAlgo.NONE,
        password: Optional[str] = None,
        fast_mode_override: bool = False
    ):
        self.output_path = output_path
        self.compression_algo = compression_algo
        self.encryption_algo = encryption_algo
        self.fast_mode_override = fast_mode_override
        
        self.chunk_registry: Dict[str, Dict[str, Any]] = {}
        self.salt = generate_salt() if encryption_algo != EncryptionAlgo.NONE else b'\x00' * 16
        
        self.encryptor = None
        if encryption_algo == EncryptionAlgo.AES_256_GCM:
            if not password: raise ValueError("Password is required for AES-256-GCM encryption.")
            self.encryptor = ChunkEncryptor(password, self.salt)
            
        self.file_stream = open(self.output_path, 'wb')
        self._write_header()

    def _write_header(self) -> None:
        magic_bytes = b"DGZ\x01"
        header_format = "<4s B B 16s 42s"
        padding = b'\x00' * 42
        self.file_stream.write(struct.pack(header_format, magic_bytes, self.compression_algo.value, self.encryption_algo.value, self.salt, padding))

    def _process_file(self, filepath: str) -> List[str]:
        file_chunk_hashes = []
        ext = os.path.splitext(filepath)[1].lower()
        is_high_entropy = ext in HIGH_ENTROPY_EXTENSIONS or self.fast_mode_override
        
        chunk_generator = chunk_file_fixed(filepath) if is_high_entropy else chunk_file(filepath)
        
        for chunk in chunk_generator:
            file_chunk_hashes.append(chunk.hash_sha256)
            if chunk.hash_sha256 in self.chunk_registry:
                continue
                
            applied_compression = CompressionAlgo.NONE if is_high_entropy else self.compression_algo
            processed_data = compress_chunk(chunk.data, applied_compression)
            
            if self.encryptor:
                processed_data = self.encryptor.encrypt(processed_data, self.encryption_algo)
                
            current_offset = self.file_stream.tell()
            payload_size = len(processed_data)
            
            self.file_stream.write(struct.pack("<I", payload_size))
            self.file_stream.write(processed_data)
            
            chunk_meta = {
                "offset": current_offset,
                "size": payload_size,
                "original_size": chunk.size
            }
            # FIXED: Only add the key if it's actually an override!
            if is_high_entropy:
                chunk_meta["algo_override"] = applied_compression.value

            self.chunk_registry[chunk.hash_sha256] = chunk_meta
            
        return file_chunk_hashes

    def _build_tree(self, root_dir: str) -> Dict[str, Any]:
        tree: Dict[str, Any] = {
            "type": "directory",
            "name": os.path.basename(root_dir) or "/",
            "metadata": {"permissions": os.stat(root_dir).st_mode, "mtime": int(os.stat(root_dir).st_mtime)},
            "children": []
        }
        with os.scandir(root_dir) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    tree["children"].append(self._build_tree(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    stat = entry.stat()
                    tree["children"].append({
                        "type": "file", "name": entry.name, "size": stat.st_size,
                        "metadata": {"permissions": stat.st_mode, "mtime": int(stat.st_mtime)},
                        "chunks": self._process_file(entry.path)
                    })
        return tree

    def build(self, source_dir: str) -> None:
        root_node = self._build_tree(source_dir)
        manifest = {"version": 1, "timestamp": int(time.time()), "chunks": self.chunk_registry, "root": root_node}
        serialized = msgpack.packb(manifest, use_bin_type=True)
        processed_manifest = compress_chunk(serialized, self.compression_algo)
        if self.encryptor:
            processed_manifest = self.encryptor.encrypt(processed_manifest, self.encryption_algo)
        m_offset = self.file_stream.tell()
        m_size = len(processed_manifest)
        self.file_stream.write(processed_manifest)
        self.file_stream.write(struct.pack("<Q Q", m_offset, m_size))
        self.file_stream.close()

def create_archive(source: str, destination: str, use_encryption: bool = False, password: str = "", fast_mode: bool = False) -> None:
    builder = ArchiveBuilder(destination, CompressionAlgo.ZSTANDARD, EncryptionAlgo.AES_256_GCM if use_encryption else EncryptionAlgo.NONE, password, fast_mode)
    builder.build(source)
