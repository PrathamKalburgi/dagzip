# DAGZip

> Next-Generation Deduplicating, Content-Addressable Archiver

DAGZip is a high-performance archive format and toolchain that breaks files into variable-sized chunks, deduplicates them globally, compresses them with Zstandard, and indexes them using a Merkle Directed Acyclic Graph (DAG). :contentReference[oaicite:0]{index=0}

---

## Features

- Content-Defined Chunking (CDC)
- Global Deduplication
- Merkle DAG-Based Indexing
- AES-256-GCM Encryption
- FastAPI Streaming Server
- Multithreaded PyQt6 GUI
- Hardware-Aware I/O Optimization

---

# Key Features

DAGZip is built from the ground up to solve modern storage constraints using advanced Data Structures and Algorithms. :contentReference[oaicite:1]{index=1}

## Content-Defined Chunking (CDC)

Utilizes a custom Gear Hash algorithm to find shift-resistant block boundaries. If you insert a single byte at the beginning of a 10GB file, DAGZip only stores the single changed chunk rather than recompiling the entire archive. :contentReference[oaicite:2]{index=2}

## O(1) Delta Comparisons

By comparing Merkle DAG root hashes and child chunk arrays, DAGZip can diff two multi-gigabyte archives in milliseconds without extracting a single byte. :contentReference[oaicite:3]{index=3}

## Military-Grade Security

Implements Authenticated Encryption with Associated Data (AEAD) using AES-256-GCM. Keys are derived using Scrypt, a memory-hard KDF designed to resist GPU brute-force attacks. :contentReference[oaicite:4]{index=4}

## Zero-Copy REST Streaming

Includes a built-in FastAPI ASGI server that can mount an archive and stream individual chunks over HTTP on-demand without extracting the archive to disk. :contentReference[oaicite:5]{index=5}

## Multithreaded PyQt6 GUI

A responsive, non-blocking desktop application with an interactive DAG Inspector to visualize and selectively extract isolated nodes from the graph. :contentReference[oaicite:6]{index=6}

## Hardware-Aware I/O

Optimized buffer reads using 4MB blocks and `os.scandir` usage tuned for maximum throughput on both HDDs and SSDs. :contentReference[oaicite:7]{index=7}

---

# Installation

DAGZip requires **Python 3.10+**. :contentReference[oaicite:8]{index=8}

## Clone the Repository

```bash
git clone https://github.com/yourusername/dagzip.git
cd dagzip