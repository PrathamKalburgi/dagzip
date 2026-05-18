# DAGZip

> Next-Generation Deduplicating, Content-Addressable Archiver

DAGZip is a high-performance archive format and toolchain that breaks files into variable-sized chunks, deduplicates them globally, compresses them with Zstandard, and indexes them using a Merkle Directed Acyclic Graph (DAG).

## Features

- Content-Defined Chunking (CDC)
- Global deduplication
- Merkle DAG-based indexing
- AES-256-GCM encryption
- FastAPI streaming server
- Multithreaded PyQt6 GUI
- Hardware-aware I/O optimization

## Key Features

DAGZip is built from the ground up to solve modern storage constraints using advanced data structures and algorithms.

### Content-Defined Chunking (CDC)

Utilizes a custom Gear Hash algorithm to find shift-resistant block boundaries. If you insert a single byte at the beginning of a 10GB file, DAGZip only stores the single changed chunk rather than recompressing the whole file.

### O(1) Delta Comparisons

By comparing Merkle DAG root hashes and child chunk arrays, DAGZip can diff two multi-gigabyte archives in milliseconds without extracting a single byte.

### Military-Grade Security

Implements Authenticated Encryption with Associated Data (AEAD) via AES-256-GCM. Keys are derived using Scrypt, a memory-hard KDF designed to resist GPU brute-force attacks.

### Zero-Copy REST Streaming

Includes a built-in FastAPI ASGI server that can mount an archive and stream individual chunks over HTTP on demand, without extracting the archive to disk.

### Multithreaded PyQt6 GUI

A responsive, non-blocking desktop application with an interactive DAG Inspector to visualize and selectively extract isolated nodes from the graph.

### Hardware-Aware I/O

Optimized buffer reads using 4 MB blocks and `os.scandir` usage tuned for maximum throughput on both mechanical HDDs and SSDs.

## Installation

DAGZip requires Python 3.10 or higher.

```bash
git clone https://github.com/yourusername/dagzip.git
cd dagzip
pip install -e .
```

Using editable mode installs the core dependencies:

- zstandard
- cryptography
- rich
- click
- msgpack
- fastapi
- PyQt6

## Command-Line Interface

DAGZip provides a Rich-powered terminal UI.

### Pack an Archive

Compress a directory, deduplicate its contents, and optionally encrypt it.

```bash
# Standard packing
dagzip pack ./my_project ./backup.dgz

# Encrypted packing (will prompt for a password securely)
dagzip pack ./my_project ./secure_backup.dgz --encrypt
```

### Unpack an Archive

Extract an archive back into a standard filesystem tree.

```bash
# Standard extraction
dagzip unpack ./backup.dgz ./extracted_files

# If the archive is encrypted, DAGZip will automatically detect it and prompt for the password.
# Alternatively, pass it directly (not recommended for bash history security):
dagzip unpack ./secure_backup.dgz ./extracted_files -p "my_super_secret_password"
```

### Compare Archives (Diff)

Calculate added, removed, modified, and identical files between two snapshots instantly.

```bash
dagzip diff ./backup_v1.dgz ./backup_v2.dgz
```

### Serve via HTTP

Mount the archive as a read-only FastAPI server. This exposes `/api/manifest` to browse the DAG and `/api/chunk/{hash}` to stream binary data directly to remote clients.

```bash
dagzip serve ./backup.dgz --port 8080
```

## Desktop GUI

DAGZip comes with a full-featured desktop interface. It uses PyQt6 QThreads to ensure the UI remains responsive while packing or unpacking massive datasets.

To launch the GUI, simply run:

```bash
dagzip-gui
```

### GUI Features

- Archive Inspector: Visually navigate the internal DAG manifest tree before extracting.
- Selective Extraction: Right-click a specific file inside a massive archive and extract only that file by reassembling its constituent chunks on the fly.
- Progress Tracking: Real-time visual feedback for I/O-bound operations.

## System Architecture

DAGZip's internal pipeline is designed for strict memory bounds and CPU efficiency.

### 1. The Chunking Engine

Files are not compressed whole. Instead, they pass through a chunker:

#### High-Entropy Mode (FSC)

For pre-compressed formats such as `.mp4`, `.zip`, and `.jpg`, DAGZip uses a Fixed-Size Chunker reading directly into memory buffers for maximum I/O speed.

#### Deduplication Mode (CDC)

For raw data such as code, text, and VMs, it uses a Rolling Gear Hash to slice the byte stream into variable chunks ranging from 4 KB to 64 KB.

### 2. Processing Pipeline

#### Hash

Each chunk is hashed using SHA-256. If the hash exists in the global `chunk_registry`, the data is discarded for deduplication.

#### Compress

Unique chunks are compressed using an isolated Zstandard state block, keeping memory allocations strictly flat with O(1) memory complexity per chunk.

#### Encrypt

If enabled, a unique 12-byte nonce is generated, and the chunk is encrypted via AES-256-GCM with a 16-byte authentication tag.

### 3. Binary Format (`.dgz`)

The resulting `.dgz` file is a flat byte stream organized as follows:

- **64-byte header**: Magic bytes (`DGZ\x01`), algorithm flags, and crypto salt.
- **Chunk pool**: A continuous sequence of `[Size (4 bytes)] [Payload (Variable)]`.
- **DAG manifest**: A highly compressed MsgPack payload detailing the folder hierarchy and chunk pointers.
- **16-byte footer**: Pointer coordinates to instantly locate the manifest at the end of the file.

For full byte-level specifications, see `format.md`.

## Development & Contributing

We welcome pull requests. To set up a development environment with linting and typing tools:

```bash
pip install -e ".[dev]"
```

### Code Formatting

This project enforces Black and mypy strict typing.

```bash
black dagzip/ gui/
mypy dagzip/ gui/
```

## License

This project is licensed under the GNU Affero General Public License v3.0. See the `LICENSE` file for details.
