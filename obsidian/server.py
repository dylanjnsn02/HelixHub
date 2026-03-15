"""MCP stdio server using FastMCP for interacting with Obsidian's Local REST API.

Requires the Obsidian Local REST API plugin to be installed and configured.
API key should be stored in auth.key in this directory.
Connection settings (host, port, protocol) can be stored in connection.json.
"""

import json
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import httpx
from fastmcp import FastMCP

mcp = FastMCP("obsidian")

AUTH_KEY_PATH = Path(__file__).parent / "auth.key"
CONNECTION_PATH = Path(__file__).parent / "connection.json"

# Defaults
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 27124
_DEFAULT_PROTOCOL = "https"


def _load_connection() -> Dict[str, Any]:
    """Load connection settings from connection.json, falling back to defaults."""
    defaults = {
        "host": _DEFAULT_HOST,
        "port": _DEFAULT_PORT,
        "protocol": _DEFAULT_PROTOCOL,
    }
    try:
        data = json.loads(CONNECTION_PATH.read_text())
        defaults.update(data)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return defaults


def _get_base_url() -> str:
    """Build the base URL from connection settings."""
    conn = _load_connection()
    return f"{conn['protocol']}://{conn['host']}:{conn['port']}"


def _get_api_key() -> str:
    """Read the API key from auth.key."""
    try:
        return AUTH_KEY_PATH.read_text().strip()
    except FileNotFoundError:
        raise RuntimeError(
            f"API key file not found at {AUTH_KEY_PATH}. "
            "Create auth.key with your Obsidian Local REST API key."
        )


def _client() -> httpx.AsyncClient:
    """Create an httpx client with auth and SSL verification disabled (self-signed cert)."""
    return httpx.AsyncClient(
        base_url=_get_base_url(),
        headers={"Authorization": f"Bearer {_get_api_key()}"},
        verify=False,
        timeout=30,
    )


def _format_response(resp: httpx.Response) -> Dict[str, Any]:
    """Format an HTTP response into a standard dict."""
    result: Dict[str, Any] = {"status_code": resp.status_code}
    if resp.status_code == 204:
        result["message"] = "Success"
        return result
    content_type = resp.headers.get("content-type", "")
    if "json" in content_type:
        try:
            result["data"] = resp.json()
        except Exception:
            result["text"] = resp.text
    else:
        result["text"] = resp.text
    return result


# ── System ──────────────────────────────────────────────────────────────────


@mcp.tool()
async def configure_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    protocol: Optional[Literal["http", "https"]] = None,
) -> Dict[str, Any]:
    """Configure the Obsidian API connection. Settings are saved to connection.json.

    Args:
        host: IP address or hostname (e.g. "192.168.1.50"). Default "127.0.0.1".
        port: Port number (e.g. 27124). Default 27124.
        protocol: "http" or "https". Default "https".
    """
    conn = _load_connection()
    if host is not None:
        conn["host"] = host
    if port is not None:
        conn["port"] = port
    if protocol is not None:
        conn["protocol"] = protocol
    CONNECTION_PATH.write_text(json.dumps(conn, indent=2))
    return {"message": "Connection updated", "connection": conn, "url": _get_base_url()}


@mcp.tool()
async def get_server_status() -> Dict[str, Any]:
    """Get basic details about the Obsidian REST API server and authentication status."""
    async with _client() as client:
        resp = await client.get("/")
        return _format_response(resp)


# ── Active File ─────────────────────────────────────────────────────────────


@mcp.tool()
async def get_active_file(
    format: Literal["markdown", "json", "document-map"] = "markdown",
) -> Dict[str, Any]:
    """Return the content of the currently active file in Obsidian.

    Args:
        format: Response format - "markdown" for raw text, "json" for parsed note
                with frontmatter/tags/stat, "document-map" for headings/blocks/frontmatter fields.
    """
    accept_map = {
        "markdown": "text/markdown",
        "json": "application/vnd.olrapi.note+json",
        "document-map": "application/vnd.olrapi.document-map+json",
    }
    async with _client() as client:
        resp = await client.get("/active/", headers={"Accept": accept_map[format]})
        return _format_response(resp)


@mcp.tool()
async def update_active_file(content: str) -> Dict[str, Any]:
    """Replace the entire content of the currently active file.

    Args:
        content: The new content for the file (markdown).
    """
    async with _client() as client:
        resp = await client.put(
            "/active/",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        return _format_response(resp)


@mcp.tool()
async def append_to_active_file(content: str) -> Dict[str, Any]:
    """Append content to the end of the currently active file.

    Args:
        content: Markdown content to append.
    """
    async with _client() as client:
        resp = await client.post(
            "/active/",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        return _format_response(resp)


@mcp.tool()
async def patch_active_file(
    content: str,
    operation: Literal["append", "prepend", "replace"],
    target_type: Literal["heading", "block", "frontmatter"],
    target: str,
    target_delimiter: str = "::",
    content_type: Literal["text/markdown", "application/json"] = "text/markdown",
) -> Dict[str, Any]:
    """Insert content into the active file relative to a heading, block reference, or frontmatter field.

    Args:
        content: Content to insert.
        operation: "append", "prepend", or "replace".
        target_type: "heading", "block", or "frontmatter".
        target: The target identifier (heading path, block ref ID, or frontmatter field name).
        target_delimiter: Delimiter for nested headings (default "::").
        content_type: Content type - "text/markdown" or "application/json".
    """
    async with _client() as client:
        resp = await client.patch(
            "/active/",
            content=content,
            headers={
                "Content-Type": content_type,
                "Operation": operation,
                "Target-Type": target_type,
                "Target": target,
                "Target-Delimiter": target_delimiter,
            },
        )
        return _format_response(resp)


@mcp.tool()
async def delete_active_file() -> Dict[str, Any]:
    """Delete the currently active file in Obsidian."""
    async with _client() as client:
        resp = await client.delete("/active/")
        return _format_response(resp)


# ── Vault Files ─────────────────────────────────────────────────────────────


@mcp.tool()
async def list_vault_files(path: str = "/") -> Dict[str, Any]:
    """List files in a vault directory.

    Args:
        path: Directory path relative to vault root. Use "/" for root.
    """
    url = "/vault/" if path == "/" else f"/vault/{path.strip('/')}/"
    async with _client() as client:
        resp = await client.get(url)
        return _format_response(resp)


@mcp.tool()
async def get_vault_file(
    filename: str,
    format: Literal["markdown", "json", "document-map"] = "markdown",
) -> Dict[str, Any]:
    """Get the content of a specific file in the vault.

    Args:
        filename: Path to the file relative to vault root (e.g. "notes/my-note.md").
        format: Response format - "markdown", "json" (with frontmatter/tags), or "document-map".
    """
    accept_map = {
        "markdown": "text/markdown",
        "json": "application/vnd.olrapi.note+json",
        "document-map": "application/vnd.olrapi.document-map+json",
    }
    async with _client() as client:
        resp = await client.get(
            f"/vault/{filename}",
            headers={"Accept": accept_map[format]},
        )
        return _format_response(resp)


@mcp.tool()
async def create_or_update_vault_file(filename: str, content: str) -> Dict[str, Any]:
    """Create a new file or update an existing file in the vault.

    Args:
        filename: Path relative to vault root (e.g. "notes/new-note.md").
        content: File content (markdown).
    """
    async with _client() as client:
        resp = await client.put(
            f"/vault/{filename}",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        return _format_response(resp)


@mcp.tool()
async def append_to_vault_file(filename: str, content: str) -> Dict[str, Any]:
    """Append content to the end of a vault file. Creates the file if it doesn't exist.

    Args:
        filename: Path relative to vault root.
        content: Markdown content to append.
    """
    async with _client() as client:
        resp = await client.post(
            f"/vault/{filename}",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        return _format_response(resp)


@mcp.tool()
async def patch_vault_file(
    filename: str,
    content: str,
    operation: Literal["append", "prepend", "replace"],
    target_type: Literal["heading", "block", "frontmatter"],
    target: str,
    target_delimiter: str = "::",
    content_type: Literal["text/markdown", "application/json"] = "text/markdown",
) -> Dict[str, Any]:
    """Insert content into a vault file relative to a heading, block reference, or frontmatter field.

    Args:
        filename: Path relative to vault root.
        content: Content to insert.
        operation: "append", "prepend", or "replace".
        target_type: "heading", "block", or "frontmatter".
        target: The target identifier.
        target_delimiter: Delimiter for nested headings (default "::").
        content_type: "text/markdown" or "application/json".
    """
    async with _client() as client:
        resp = await client.patch(
            f"/vault/{filename}",
            content=content,
            headers={
                "Content-Type": content_type,
                "Operation": operation,
                "Target-Type": target_type,
                "Target": target,
                "Target-Delimiter": target_delimiter,
            },
        )
        return _format_response(resp)


@mcp.tool()
async def delete_vault_file(filename: str) -> Dict[str, Any]:
    """Delete a file from the vault.

    Args:
        filename: Path relative to vault root.
    """
    async with _client() as client:
        resp = await client.delete(f"/vault/{filename}")
        return _format_response(resp)


# ── Commands ────────────────────────────────────────────────────────────────


@mcp.tool()
async def list_commands() -> Dict[str, Any]:
    """List all available Obsidian commands."""
    async with _client() as client:
        resp = await client.get("/commands/")
        return _format_response(resp)


@mcp.tool()
async def execute_command(command_id: str) -> Dict[str, Any]:
    """Execute an Obsidian command by its ID.

    Args:
        command_id: The command ID (e.g. "global-search:open").
    """
    async with _client() as client:
        resp = await client.post(f"/commands/{command_id}/")
        return _format_response(resp)


# ── Open ────────────────────────────────────────────────────────────────────


@mcp.tool()
async def open_file(filename: str, new_leaf: bool = False) -> Dict[str, Any]:
    """Open a file in the Obsidian UI.

    Args:
        filename: Path relative to vault root.
        new_leaf: Whether to open in a new pane/leaf.
    """
    params = {}
    if new_leaf:
        params["newLeaf"] = "true"
    async with _client() as client:
        resp = await client.post(f"/open/{filename}", params=params)
        return _format_response(resp)


# ── Search ──────────────────────────────────────────────────────────────────


@mcp.tool()
async def search_simple(query: str, context_length: int = 100) -> Dict[str, Any]:
    """Search for documents matching a text query.

    Args:
        query: The search query string.
        context_length: How much context to return around matches (default 100).
    """
    async with _client() as client:
        resp = await client.post(
            "/search/simple/",
            params={"query": query, "contextLength": context_length},
        )
        return _format_response(resp)


@mcp.tool()
async def search_jsonlogic(query: Dict[str, Any]) -> Dict[str, Any]:
    """Search vault using a JsonLogic query against note metadata.

    Args:
        query: A JsonLogic query object. Notes are represented as NoteJson objects
               with fields: content, frontmatter, path, stat, tags.
               Extra operators: glob(pattern, value), regexp(pattern, value).
    """
    async with _client() as client:
        resp = await client.post(
            "/search/",
            json=query,
            headers={"Content-Type": "application/vnd.olrapi.jsonlogic+json"},
        )
        return _format_response(resp)


@mcp.tool()
async def search_dataview(dql_query: str) -> Dict[str, Any]:
    """Search vault using a Dataview DQL TABLE query.

    Args:
        dql_query: A Dataview TABLE query string.
    """
    async with _client() as client:
        resp = await client.post(
            "/search/",
            content=dql_query,
            headers={"Content-Type": "application/vnd.olrapi.dataview.dql+txt"},
        )
        return _format_response(resp)


# ── Periodic Notes ──────────────────────────────────────────────────────────

Period = Literal["daily", "weekly", "monthly", "quarterly", "yearly"]


@mcp.tool()
async def get_periodic_note(
    period: Period = "daily",
    format: Literal["markdown", "json", "document-map"] = "markdown",
) -> Dict[str, Any]:
    """Get the current periodic note for the specified period.

    Args:
        period: "daily", "weekly", "monthly", "quarterly", or "yearly".
        format: Response format.
    """
    accept_map = {
        "markdown": "text/markdown",
        "json": "application/vnd.olrapi.note+json",
        "document-map": "application/vnd.olrapi.document-map+json",
    }
    async with _client() as client:
        resp = await client.get(
            f"/periodic/{period}/",
            headers={"Accept": accept_map[format]},
        )
        return _format_response(resp)


@mcp.tool()
async def update_periodic_note(period: Period, content: str) -> Dict[str, Any]:
    """Replace the content of the current periodic note.

    Args:
        period: The period type.
        content: New content (markdown).
    """
    async with _client() as client:
        resp = await client.put(
            f"/periodic/{period}/",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        return _format_response(resp)


@mcp.tool()
async def append_to_periodic_note(period: Period, content: str) -> Dict[str, Any]:
    """Append content to the current periodic note. Creates it if necessary.

    Args:
        period: The period type.
        content: Markdown content to append.
    """
    async with _client() as client:
        resp = await client.post(
            f"/periodic/{period}/",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        return _format_response(resp)


@mcp.tool()
async def patch_periodic_note(
    period: Period,
    content: str,
    operation: Literal["append", "prepend", "replace"],
    target_type: Literal["heading", "block", "frontmatter"],
    target: str,
    target_delimiter: str = "::",
    content_type: Literal["text/markdown", "application/json"] = "text/markdown",
) -> Dict[str, Any]:
    """Insert content into the current periodic note relative to a heading, block, or frontmatter field.

    Args:
        period: The period type.
        content: Content to insert.
        operation: "append", "prepend", or "replace".
        target_type: "heading", "block", or "frontmatter".
        target: The target identifier.
        target_delimiter: Delimiter for nested headings (default "::").
        content_type: "text/markdown" or "application/json".
    """
    async with _client() as client:
        resp = await client.patch(
            f"/periodic/{period}/",
            content=content,
            headers={
                "Content-Type": content_type,
                "Operation": operation,
                "Target-Type": target_type,
                "Target": target,
                "Target-Delimiter": target_delimiter,
            },
        )
        return _format_response(resp)


@mcp.tool()
async def delete_periodic_note(period: Period) -> Dict[str, Any]:
    """Delete the current periodic note for the specified period.

    Args:
        period: The period type.
    """
    async with _client() as client:
        resp = await client.delete(f"/periodic/{period}/")
        return _format_response(resp)


@mcp.tool()
async def get_periodic_note_by_date(
    period: Period,
    year: int,
    month: int,
    day: int,
    format: Literal["markdown", "json", "document-map"] = "markdown",
) -> Dict[str, Any]:
    """Get a periodic note for a specific date.

    Args:
        period: The period type.
        year: Year.
        month: Month (1-12).
        day: Day (1-31).
        format: Response format.
    """
    accept_map = {
        "markdown": "text/markdown",
        "json": "application/vnd.olrapi.note+json",
        "document-map": "application/vnd.olrapi.document-map+json",
    }
    async with _client() as client:
        resp = await client.get(
            f"/periodic/{period}/{year}/{month}/{day}/",
            headers={"Accept": accept_map[format]},
        )
        return _format_response(resp)


@mcp.tool()
async def update_periodic_note_by_date(
    period: Period, year: int, month: int, day: int, content: str
) -> Dict[str, Any]:
    """Replace the content of a periodic note for a specific date.

    Args:
        period: The period type.
        year: Year.
        month: Month (1-12).
        day: Day (1-31).
        content: New content (markdown).
    """
    async with _client() as client:
        resp = await client.put(
            f"/periodic/{period}/{year}/{month}/{day}/",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        return _format_response(resp)


@mcp.tool()
async def append_to_periodic_note_by_date(
    period: Period, year: int, month: int, day: int, content: str
) -> Dict[str, Any]:
    """Append content to a periodic note for a specific date. Creates it if necessary.

    Args:
        period: The period type.
        year: Year.
        month: Month (1-12).
        day: Day (1-31).
        content: Markdown content to append.
    """
    async with _client() as client:
        resp = await client.post(
            f"/periodic/{period}/{year}/{month}/{day}/",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        return _format_response(resp)


@mcp.tool()
async def patch_periodic_note_by_date(
    period: Period,
    year: int,
    month: int,
    day: int,
    content: str,
    operation: Literal["append", "prepend", "replace"],
    target_type: Literal["heading", "block", "frontmatter"],
    target: str,
    target_delimiter: str = "::",
    content_type: Literal["text/markdown", "application/json"] = "text/markdown",
) -> Dict[str, Any]:
    """Insert content into a periodic note for a specific date relative to a heading, block, or frontmatter field.

    Args:
        period: The period type.
        year: Year.
        month: Month (1-12).
        day: Day (1-31).
        content: Content to insert.
        operation: "append", "prepend", or "replace".
        target_type: "heading", "block", or "frontmatter".
        target: The target identifier.
        target_delimiter: Delimiter for nested headings (default "::").
        content_type: "text/markdown" or "application/json".
    """
    async with _client() as client:
        resp = await client.patch(
            f"/periodic/{period}/{year}/{month}/{day}/",
            content=content,
            headers={
                "Content-Type": content_type,
                "Operation": operation,
                "Target-Type": target_type,
                "Target": target,
                "Target-Delimiter": target_delimiter,
            },
        )
        return _format_response(resp)


@mcp.tool()
async def delete_periodic_note_by_date(
    period: Period, year: int, month: int, day: int
) -> Dict[str, Any]:
    """Delete a periodic note for a specific date.

    Args:
        period: The period type.
        year: Year.
        month: Month (1-12).
        day: Day (1-31).
    """
    async with _client() as client:
        resp = await client.delete(f"/periodic/{period}/{year}/{month}/{day}/")
        return _format_response(resp)


if __name__ == "__main__":
    mcp.run()
