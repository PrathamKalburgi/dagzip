"""
DAGZip Content-Defined Chunker (CDC)

This module implements both a variable-sized chunking algorithm (Gear Hash) 
for deduplicable data, and a blazing-fast Fixed-Size Chunker (FSC) for 
high-entropy media and pre-compressed archives.
"""

import hashlib
from typing import Iterator, NamedTuple

# CDC Constants
MIN_CHUNK_SIZE = 4096      
MAX_CHUNK_SIZE = 65536     
TARGET_CHUNK_SIZE = 8192   
READ_BUFFER_SIZE = 1048576 * 4 
CHUNK_MASK = 0x1FFF

# Generate Deterministic Gear Table
GEAR_TABLE = []
for i in range(256):
    hash_bytes = hashlib.sha256(f"DAGZIP_GEAR_MAGIC_SEED_{i}".encode('utf-8')).digest()
    val = int.from_bytes(hash_bytes[:8], byteorder='little')
    GEAR_TABLE.append(val)

class ChunkResult(NamedTuple):
    data: bytes
    size: int
    hash_sha256: str

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def chunk_data(stream_generator: Iterator[bytes]) -> Iterator[ChunkResult]:
    """Core algorithm for Content-Defined Chunking using Gear Hash."""
    chunk_buffer = bytearray()
    fingerprint = 0
    current_chunk_length = 0 
    
    for block in stream_generator:
        i = 0
        block_len = len(block)
        
        while i < block_len:
            byte = block[i]
            chunk_buffer.append(byte)
            current_chunk_length += 1
            i += 1
            
            fingerprint = ((fingerprint << 1) + GEAR_TABLE[byte]) & 0xFFFFFFFFFFFFFFFF
            
            if current_chunk_length >= MIN_CHUNK_SIZE:
                if (fingerprint & CHUNK_MASK) == 0 or current_chunk_length >= MAX_CHUNK_SIZE:
                    chunk_bytes = bytes(chunk_buffer)
                    yield ChunkResult(
                        data=chunk_bytes,
                        size=current_chunk_length,
                        hash_sha256=compute_sha256(chunk_bytes)
                    )
                    chunk_buffer.clear()
                    current_chunk_length = 0
                    fingerprint = 0

    if current_chunk_length > 0:
        chunk_bytes = bytes(chunk_buffer)
        yield ChunkResult(
            data=chunk_bytes, size=current_chunk_length, hash_sha256=compute_sha256(chunk_bytes)
        )

def chunk_file(filepath: str) -> Iterator[ChunkResult]:
    """Reads a file and yields CDC chunks (Slow, high deduplication)."""
    def block_reader() -> Iterator[bytes]:
        with open(filepath, 'rb') as f:
            while True:
                block = f.read(READ_BUFFER_SIZE)
                if not block: break
                yield block
    yield from chunk_data(block_reader())

def chunk_file_fixed(filepath: str, fixed_size: int = 1048576 * 4) -> Iterator[ChunkResult]:
    """
    Reads a file and yields Fixed-Size chunks (Blazing fast, low deduplication).
    This bypasses all byte-level math and operates at the maximum read speed 
    of the underlying hardware.
    """
    with open(filepath, 'rb') as f:
        while True:
            # We read exactly 4MB directly from the OS page cache
            block = f.read(fixed_size)
            if not block: break
            
            yield ChunkResult(
                data=block,
                size=len(block),
                hash_sha256=compute_sha256(block)
            )
