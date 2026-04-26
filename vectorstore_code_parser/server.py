from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP

from embeddings_store import get_store
from embedder import embed_query

load_dotenv(Path(__file__).with_name(".env"))

mcp = FastMCP("code-search")

ChunkType = Literal["raw_code", "description", "both"]
_VALID_CHUNK_TYPES = {"raw_code", "description", "both"}
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.3"))


def _error(error_type: str, message: str) -> Dict[str, Any]:
    return {"status": "error", "error": {"type": error_type, "message": message}}


def _no_results() -> Dict[str, Any]:
    return {"status": "no_results", "results": []}


@mcp.tool
async def search_code(
    embeddings_path: str,
    query: str,
    chunk_type: ChunkType = "both",
    language: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """Search the codebase using a natural language query."""
    if not embeddings_path or not query:
        return _error("validation_error", "embeddings_path and query are required")

    if chunk_type not in _VALID_CHUNK_TYPES:
        return _error("validation_error", f"chunk_type must be one of: {sorted(_VALID_CHUNK_TYPES)}")

    path = Path(embeddings_path).expanduser()
    if not path.exists():
        return _error("not_found", f"No embeddings file found at: {embeddings_path}")

    try:
        store = get_store(str(path))
        query_vector = await embed_query(query)
        search_limit = max(1, min(limit * 3, 60))
        results = store.search(query_vector, limit=search_limit)
    except Exception as e:  # noqa: BLE001
        return _error("search_failed", str(e))

    filtered = [
        r
        for r in results
        if (chunk_type == "both" or r.get("chunk_type") == chunk_type)
        and (not language or r.get("language", "").lower() == language.lower())
        and float(r.get("score", 0.0)) >= MIN_SCORE
    ][: max(1, limit)]

    if not filtered:
        return _no_results()
    return {"status": "ok", "results": filtered}


@mcp.tool
async def get_function(
    embeddings_path: str,
    function_name: str,
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch raw code and description for a specific function by name."""
    if not embeddings_path or not function_name:
        return _error("validation_error", "embeddings_path and function_name are required")

    path = Path(embeddings_path).expanduser()
    if not path.exists():
        return _error("not_found", f"No embeddings file found at: {embeddings_path}")

    try:
        store = get_store(str(path))
    except Exception as e:  # noqa: BLE001
        return _error("load_failed", str(e))

    matched = [
        r
        for r in store.records
        if r.get("function_name") == function_name and (not file_path or r.get("file_path") == file_path)
    ]

    results = [{k: v for k, v in r.items() if k != "embedding"} for r in matched]
    results.sort(key=lambda r: (r.get("chunk_type") != "raw_code"))

    if not results:
        return _no_results()

    return {"status": "ok", "results": results}


if __name__ == "__main__":
    mcp.run(transport="stdio")
