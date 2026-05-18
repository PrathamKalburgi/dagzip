"""
DAGZip Chunk Compression Module

This module handles the compression and decompression of individual CDC chunks.
It uses Zstandard (Zstd) as the primary algorithm, optimized for high-throughput
small-block processing.
"""

import enum
import zstandard as zstd
from typing import Dict, Optional


class CompressionAlgo(enum.IntEnum):
    """
    Enum representing the compression algorithms supported by DAGZip.
    These integer values correspond exactly to the byte values defined 
    in the header specification (format.md).
    """
    NONE = 0x00
    ZSTANDARD = 0x01
    LZ4 = 0x02  # Reserved for future extremely high-speed, lower-ratio use cases


class ChunkCompressor:
    """
    A stateful compression wrapper.
    
    Why use a class instead of a simple function?
    Initializing a ZstdCompressor requires allocating memory for compression 
    dictionaries and state blocks. Doing this for every 8KB chunk would destroy 
    CPU performance. By using a class, we initialize the C-backend once and 
    reuse the thread-safe instance across thousands of chunks.
    """
    
    def __init__(self, level: int = 3):
        """
        Initialize the compressor with a specific compression level.
        Level 3 is the Zstd default: a perfect balance of speed and ratio.
        """
        self._level = level
        
        # Initialize the Zstd C-extension context once.
        # We use empty dictionaries here, but for advanced CDC, we could 
        # train a Zstd dictionary on file samples to vastly improve small-chunk ratios.
        self._zstd_compressor = zstd.ZstdCompressor(level=self._level)
        self._zstd_decompressor = zstd.ZstdDecompressor()

    def compress(self, data: bytes, algo: CompressionAlgo = CompressionAlgo.ZSTANDARD) -> bytes:
        """
        Compresses a raw chunk of bytes.
        
        Args:
            data: The raw binary data from the chunker.
            algo: The algorithm to use. Defaults to ZSTANDARD.
            
        Returns:
            The compressed binary data.
        """
        if algo == CompressionAlgo.NONE:
            return data
            
        elif algo == CompressionAlgo.ZSTANDARD:
            # Zstd can compress directly to bytes. 
            # This avoids Python object creation overhead for fast I/O.
            return self._zstd_compressor.compress(data)
            
        elif algo == CompressionAlgo.LZ4:
            raise NotImplementedError("LZ4 compression is reserved but not yet implemented.")
            
        else:
            raise ValueError(f"Unknown compression algorithm: {algo}")

    def decompress(self, data: bytes, algo: CompressionAlgo, uncompressed_size: int) -> bytes:
        """
        Decompresses a chunk of bytes during archive extraction.
        
        Args:
            data: The compressed binary payload.
            algo: The algorithm used to compress it (read from DAG header/manifest).
            uncompressed_size: The exact original size of the chunk. Providing this 
                               prevents the decompressor from having to dynamically 
                               reallocate memory buffers during extraction.
                               
        Returns:
            The original raw binary data.
        """
        if algo == CompressionAlgo.NONE:
            return data
            
        elif algo == CompressionAlgo.ZSTANDARD:
            # By passing max_output_size, the C-backend allocates exactly the 
            # right amount of RAM immediately, preventing expensive reallocations.
            return self._zstd_decompressor.decompress(data, max_output_size=uncompressed_size)
            
        elif algo == CompressionAlgo.LZ4:
            raise NotImplementedError("LZ4 decompression is reserved but not yet implemented.")
            
        else:
            raise ValueError(f"Unknown decompression algorithm: {algo}")

# -------------------------------------------------------------------------
# Singleton Pattern for Global Pipeline Usage
# -------------------------------------------------------------------------
# We provide a default, globally accessible instance so the CLI and DAG builder
# don't need to constantly pass compressor instances around.
_DEFAULT_COMPRESSOR = ChunkCompressor()

def compress_chunk(data: bytes, algo: CompressionAlgo = CompressionAlgo.ZSTANDARD) -> bytes:
    """Helper function utilizing the global compressor instance."""
    return _DEFAULT_COMPRESSOR.compress(data, algo)

def decompress_chunk(data: bytes, algo: CompressionAlgo, uncompressed_size: int) -> bytes:
    """Helper function utilizing the global decompressor instance."""
    return _DEFAULT_COMPRESSOR.decompress(data, algo, uncompressed_size)

if __name__ == "__main__":
    # A quick execution guard to verify the module compiles and runs
    test_data = b"Hello DAGZip! " * 1000  # Highly compressible repetitive data
    print(f"Original size: {len(test_data)} bytes")
    
    compressed = compress_chunk(test_data, CompressionAlgo.ZSTANDARD)
    print(f"Compressed size: {len(compressed)} bytes")
    
    decompressed = decompress_chunk(compressed, CompressionAlgo.ZSTANDARD, len(test_data))
    assert test_data == decompressed
    print("Decompression verified successfully.")
