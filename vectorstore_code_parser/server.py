from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP


mcp = FastMCP("vectorstore-code-parser")

load_dotenv(Path(__file__).with_name(".env"))

ChunkType = Literal["raw_code", "description", "both"]
_VALID_CHUNK_TYPES = {"raw_code", "description", "both"}
_DEFAULT_LIMIT = 5
_DEFAULT_MAX_RESULTS = 20


def _max_results_cap() -> int:
    raw = os.getenv("MAX_RESULTS", str(_DEFAULT_MAX_RESULTS))
    try:
        parsed = int(raw)
        if parsed <= 0:
            return _DEFAULT_MAX_RESULTS
        return parsed
    except ValueError:
        return _DEFAULT_MAX_RESULTS


def _error(error_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"status": "error", "error": {"type": error_type, "message": message}}
    if details:
        payload["error"]["details"] = details
    return payload


def _validate_required(value: Any, field_name: str) -> Optional[Dict[str, Any]]:
    if value is None:
        return _error("validation_error", f"Missing required field: {field_name}", {"field": field_name})
    if isinstance(value, str) and not value.strip():
        return _error("validation_error", f"Missing required field: {field_name}", {"field": field_name})
    return None


def _normalize_limit(limit: int) -> int:
    if limit <= 0:
        return 1
    return min(limit, _max_results_cap())


def _extract_content(item: Dict[str, Any]) -> str:
    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces: List[str] = []
        for chunk in content:
            if isinstance(chunk, dict):
                text = chunk.get("text")
                if isinstance(text, str):
                    pieces.append(text)
                elif isinstance(chunk.get("content"), str):
                    pieces.append(chunk["content"])
        return "\n".join(pieces).strip()
    return ""


def _extract_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    attributes = item.get("attributes")
    if isinstance(attributes, dict):
        return attributes

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        return metadata

    return {}


def _normalize_result(item: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _extract_metadata(item)
    file_path = metadata.get("file_path") or item.get("filename") or ""
    function_name = metadata.get("function_name") or metadata.get("name") or ""
    language = metadata.get("language") or ""
    chunk_type = metadata.get("chunk_type") or ""
    lines = metadata.get("lines") or ""
    score = item.get("score")

    return {
        "function_name": str(function_name),
        "file_path": str(file_path),
        "lines": str(lines),
        "language": str(language),
        "chunk_type": str(chunk_type),
        "content": _extract_content(item),
        "score": float(score) if isinstance(score, (int, float)) else 0.0,
    }


def _matches_filters(
    row: Dict[str, Any],
    *,
    chunk_type: ChunkType,
    language: Optional[str] = None,
    function_name: Optional[str] = None,
    file_path: Optional[str] = None,
) -> bool:
    if chunk_type != "both" and row.get("chunk_type") != chunk_type:
        return False

    if language and row.get("language", "").lower() != language.lower():
        return False

    if function_name and row.get("function_name") != function_name:
        return False

    if file_path:
        actual = row.get("file_path", "")
        if actual != file_path:
            return False

    return True


async def _vector_store_search(vector_store_id: str, query: str, limit: int) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _error("validation_error", "OPENAI_API_KEY is required in environment")

    url = f"https://api.openai.com/v1/vector_stores/{vector_store_id}/search"
    body = {"query": query, "max_num_results": limit}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "assistants=v2",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=body)
            if response.status_code >= 400:
                return _error(
                    "vector_store_unavailable",
                    "Vector Store search request failed",
                    {"status_code": response.status_code, "body": response.text},
                )
            payload = response.json()
    except Exception as exc:  # noqa: BLE001
        return _error("vector_store_unavailable", "Vector Store search request failed", {"cause": str(exc)})

    data = payload.get("data")
    if not isinstance(data, list):
        return {"status": "ok", "results": []}

    normalized = [_normalize_result(item) for item in data if isinstance(item, dict)]
    return {"status": "ok", "results": normalized}


def _no_results() -> Dict[str, Any]:
    return {"status": "no_results", "results": []}


@mcp.tool
async def search_code(
    vector_store_id: str,
    query: str,
    chunk_type: ChunkType = "both",
    language: Optional[str] = None,
    limit: int = _DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """Search code chunks in an OpenAI Vector Store."""
    missing = _validate_required(vector_store_id, "vector_store_id") or _validate_required(query, "query")
    if missing:
        return missing

    if chunk_type not in _VALID_CHUNK_TYPES:
        return _error(
            "validation_error",
            "Invalid chunk_type. Must be one of: raw_code, description, both",
            {"field": "chunk_type", "allowed": sorted(_VALID_CHUNK_TYPES)},
        )

    safe_limit = _normalize_limit(min(limit, 20))
    search_result = await _vector_store_search(vector_store_id, query, safe_limit)
    if search_result.get("status") == "error":
        return search_result

    filtered = [
        row
        for row in search_result["results"]
        if _matches_filters(row, chunk_type=chunk_type, language=language)
    ]
    filtered.sort(key=lambda row: row.get("score", 0.0), reverse=True)
    filtered = filtered[:safe_limit]

    if not filtered:
        return _no_results()
    return {"status": "ok", "results": filtered}


@mcp.tool
async def get_function(
    vector_store_id: str,
    function_name: str,
    file_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch code/description chunks for a specific function name."""
    missing = _validate_required(vector_store_id, "vector_store_id") or _validate_required(
        function_name, "function_name"
    )
    if missing:
        return missing

    search_result = await _vector_store_search(vector_store_id, function_name, _max_results_cap())
    if search_result.get("status") == "error":
        return search_result

    matched = [
        row
        for row in search_result["results"]
        if _matches_filters(
            row,
            chunk_type="both",
            function_name=function_name,
            file_path=file_path,
        )
    ]
    matched.sort(key=lambda row: (row.get("chunk_type") != "raw_code", -row.get("score", 0.0)))

    if not matched:
        return _no_results()

    by_chunk_type: Dict[str, Dict[str, Any]] = {}
    for row in matched:
        ctype = row.get("chunk_type", "")
        if ctype not in by_chunk_type:
            by_chunk_type[ctype] = row
        if "raw_code" in by_chunk_type and "description" in by_chunk_type:
            break

    results = list(by_chunk_type.values())
    results.sort(key=lambda row: row.get("chunk_type", ""))
    return {"status": "ok", "results": results}


if __name__ == "__main__":
    mcp.run(transport="stdio")
