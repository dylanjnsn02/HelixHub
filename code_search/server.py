from __future__ import annotations

from typing import Any, Dict, List

from fastmcp import FastMCP
from semble import SembleIndex


mcp = FastMCP("code_search")


def _serialize_result(result: Any) -> Dict[str, Any]:
    chunk = result.chunk
    return {
        "file_path": chunk.file_path,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "content": chunk.content,
    }


@mcp.tool()
def search_codebase(path: str, query: str, top_k: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build a Semble index from a local directory and search it.

    Args:
        path: Local directory path to index.
        query: Natural-language or code query.
        top_k: Number of results to return.
    """
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    index = SembleIndex.from_path(path)
    results = index.search(query, top_k=top_k)
    return {"results": [_serialize_result(result) for result in results]}


@mcp.tool()
def search_github_repo(repo_url: str, query: str, top_k: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build a Semble index from a GitHub repo and search it.

    Args:
        repo_url: Git repository URL (for example: https://github.com/org/repo).
        query: Natural-language or code query.
        top_k: Number of results to return.
    """
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    index = SembleIndex.from_git(repo_url)
    results = index.search(query, top_k=top_k)
    return {"results": [_serialize_result(result) for result in results]}


if __name__ == "__main__":
    mcp.run(transport="stdio")
