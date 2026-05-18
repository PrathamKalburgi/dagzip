DAGZip (.dgz) Format Specification v1.0
=======================================

1\. Architectural Overview
--------------------------

DAGZip is a deduplicating, content-addressable archive format. It utilizes Content-Defined Chunking (CDC) to break files into variable-sized blocks, which are then stored in a flat pool and indexed via a Directed Acyclic Graph (DAG) manifest.

2\. Binary Layout
-----------------

Section

Size

Description

**Header**

64 Bytes

Versioning, Compression, and Encryption metadata.

**Chunk Pool**

Variable

Stream of length-prefixed binary chunks.

**DAG Manifest**

Variable

Msgpack serialized tree of the filesystem.

**Footer**

16 Bytes

Pointers to the Manifest for O(1) access.

3\. Header Definitions (Offset 0x00)
------------------------------------

*   0x00 \[4b\]: Magic (DGZ\\x01)
    
*   0x04 \[1b\]: Compression (0: None, 1: Zstd)
    
*   0x05 \[1b\]: Encryption (0: None, 1: AES-256-GCM)
    
*   0x06 \[16b\]: Salt/IV for Crypto
    
*   0x16 \[42b\]: Reserved/Padding
    

4\. Manifest Structure
----------------------

The manifest is a dictionary containing:

*   chunks: A registry mapping SHA-256 hashes to offset, size, and original\_size.
    
*   root: A recursive directory structure where file nodes contain arrays of chunk hashes rather than raw data.
    

5\. Implementation Notes
------------------------

*   **Deduplication:** Chunks are written to the pool only if their hash is unique.
    
*   **Fast Seeking:** Extractors must seek to the final 16 bytes to locate the manifest.
    
*   **Security:** AES-256-GCM provides authenticated encryption (AEAD) for both data chunks and the manifest metadata.