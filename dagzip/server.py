"""
DAGZip Remote Server Module

Provides a FastAPI-based REST API to serve chunks and manifests from a 
DAGZip archive over the network. This allows clients to stream specific 
files without downloading the entire archive.
"""

import os
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

# Import our existing extractor to handle the heavy lifting
from .extractor import ArchiveExtractor

# We use a global variable to hold the open extractor instance.
# In a massive production system, we'd use connection pooling, but for a 
# local FastAPI instance, holding one open file stream is highly efficient.
app = FastAPI(
    title="DAGZip Remote API",
    description="Content-Addressable Storage streaming server.",
    version="0.1.0"
)

# Global state
_EXTRACTOR: ArchiveExtractor | None = None


class ServerConfig:
    """Holds the startup configuration for the server."""
    archive_path: str = ""
    password: str = ""


@app.on_event("startup")
def startup_event() -> None:
    """
    Fires when the server boots. Opens the archive and keeps the file 
    stream hot in memory so we don't have to reopen it for every HTTP request.
    """
    global _EXTRACTOR
    try:
        print(f"Loading archive into memory: {ServerConfig.archive_path}")
        _EXTRACTOR = ArchiveExtractor(ServerConfig.archive_path, ServerConfig.password)
        print("Archive loaded successfully. Ready to serve chunks.")
    except Exception as e:
        print(f"FATAL: Failed to load archive for serving: {e}")
        os._exit(1)


@app.get("/api/manifest")
def get_manifest() -> dict:
    """
    Returns the complete DAG Manifest (the folder and file tree).
    A remote client uses this to browse the archive and discover chunk hashes.
    """
    if not _EXTRACTOR:
        raise HTTPException(status_code=500, detail="Extractor not initialized")
    
    # We return the root node, which contains the entire nested filesystem graph.
    return _EXTRACTOR.manifest["root"]


@app.get("/api/chunk/{chunk_hash}")
def get_chunk(chunk_hash: str) -> Response:
    """
    Fetches, decrypts, and decompresses a specific chunk by its SHA-256 hash,
    returning the raw binary data over HTTP.
    """
    if not _EXTRACTOR:
        raise HTTPException(status_code=500, detail="Extractor not initialized")
        
    if chunk_hash not in _EXTRACTOR.chunk_registry:
        raise HTTPException(status_code=404, detail="Chunk hash not found in archive")
        
    try:
        # _get_chunk_data handles the disk seek, read, decryption, and decompression!
        raw_binary_data = _EXTRACTOR._get_chunk_data(chunk_hash)
        
        # We return it as an 'application/octet-stream' so the browser/client 
        # knows it is raw binary data, not text or HTML.
        return Response(content=raw_binary_data, media_type="application/octet-stream")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract chunk: {str(e)}")


def run_server(archive_path: str, password: str = "", host: str = "127.0.0.1", port: int = 8000) -> None:
    """
    Entry point to configure and launch the Uvicorn ASGI server.
    """
    ServerConfig.archive_path = archive_path
    ServerConfig.password = password
    
    # Uvicorn is the high-performance async server that runs FastAPI
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m dagzip.server <archive.dgz>")
    else:
        run_server(sys.argv[1])
