"""
MCP stdio server using FastMCP with common utilities for LLM use.

Tools:
  - current_date: Current date/time in UTC, epoch, mountain time, ISO, and human-readable.
  - hash_sha256: SHA-256 hash of a string (useful for checksums, idempotency keys).
  - environment_info: Basic environment info (platform, timezone name, Python version).
  - ping: Ping a host and return reachability and round-trip time.
  - detect_mime_type: Detect MIME type from file path or from content (magic bytes).
"""

import hashlib
import mimetypes
import platform
import re
import subprocess
from base64 import b64decode
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastmcp import FastMCP

mcp = FastMCP("utilities")


@mcp.tool()
def current_date() -> dict:
    """
    Return the current date and time in several formats useful for an LLM.

    Returns:
        A dict with: utc (ISO), epoch (seconds since 1970), epoch_ms, mountain (US/Mountain),
        iso (UTC ISO 8601), and human (readable string in UTC).
    """
    now_utc = datetime.now(timezone.utc)
    now_mountain = now_utc.astimezone(ZoneInfo("America/Denver"))

    return {
        "utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "iso": now_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "epoch": int(now_utc.timestamp()),
        "epoch_ms": int(now_utc.timestamp() * 1000),
        "mountain": now_mountain.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "human": now_utc.strftime("%A, %B %d, %Y at %I:%M %p UTC"),
    }


@mcp.tool()
def hash_sha256(text: str) -> str:
    """
    Compute the SHA-256 hash (hex) of the given string. Useful for checksums, idempotency keys, or content hashing.

    Args:
        text: The string to hash (encoded as UTF-8).

    Returns:
        The 64-character lowercase hex digest.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@mcp.tool()
def environment_info() -> dict:
    """
    Return basic environment information useful for an LLM (e.g. which machine, timezone, Python version).
    """
    now = datetime.now(timezone.utc)
    try:
        tz_name = now.astimezone().tzname() or "UTC"
    except Exception:
        tz_name = "UTC"

    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python_version": platform.python_version(),
        "timezone": tz_name,
    }


# Magic bytes (prefix -> MIME type) for content-based detection
_MAGIC: list[tuple[bytes, str]] = [
    (b"%PDF", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"PK\x03\x04", "application/zip"),
    (b"\x1f\x8b", "application/gzip"),
    (b"Rar!\x1a\x07", "application/vnd.rar"),
    (b"BM", "image/bmp"),
    (b"<!DOCTYPE", "text/html"),
    (b"<!doctype", "text/html"),
    (b"<html", "text/html"),
    (b"<?xml", "application/xml"),
]


@mcp.tool()
def ping(host: str, count: int = 1, timeout_seconds: int = 5) -> dict:
    """
    Ping a host and return reachability and round-trip time.

    Args:
        host: Hostname or IP address to ping (e.g. "google.com" or "8.8.8.8").
        count: Number of ping probes (default 1).
        timeout_seconds: Timeout in seconds for the whole ping run (default 5).

    Returns:
        A dict with: success (bool), message (str), and optionally rtt_ms (float) if available.
    """
    count = max(1, min(10, count))
    timeout_seconds = max(1, min(30, timeout_seconds))
    host = host.strip()
    if not host:
        return {"success": False, "message": "host is empty"}

    is_windows = platform.system() == "Windows"
    if is_windows:
        cmd = ["ping", "-n", str(count), "-w", str(timeout_seconds * 1000), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout_seconds), host]

    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 2,
        )
        stdout = out.stdout or ""
        stderr = out.stderr or ""

        if out.returncode != 0:
            return {
                "success": False,
                "message": stderr.strip() or stdout.strip() or f"ping failed with code {out.returncode}",
            }

        # Try to parse round-trip time (e.g. "time=12.3 ms" or "time=12 ms")
        rtt_match = re.search(r"time[=:]?\s*([\d.]+)\s*ms", stdout, re.IGNORECASE)
        rtt_ms = float(rtt_match.group(1)) if rtt_match else None

        return {
            "success": True,
            "message": "ok",
            "rtt_ms": rtt_ms,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "ping timed out"}
    except FileNotFoundError:
        return {"success": False, "message": "ping command not found"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@mcp.tool()
def detect_mime_type(path: str | None = None, content_base64: str | None = None) -> dict:
    """
    Detect MIME type from a file path (extension) and/or from raw content (magic bytes).

    Provide either path or content_base64 (or both). If both are given, content-based
    detection takes precedence when the content is recognized.

    Args:
        path: File path or filename (e.g. "doc.pdf" or "/path/to/image.png"). Used for extension-based guess.
        content_base64: Optional base64-encoded file content. Used for magic-byte detection (PDF, PNG, JPEG, GIF, ZIP, etc.).

    Returns:
        A dict with: mime_type (str or None), encoding (str or None, e.g. 'gzip'), source ('path', 'content', or 'path_fallback').
    """
    from_path = None
    encoding_from_path = None
    if path:
        path = path.strip()
        if path:
            guess = mimetypes.guess_type(path, strict=False)
            from_path = guess[0]
            encoding_from_path = guess[1]

    from_content = None
    if content_base64:
        try:
            raw = b64decode(content_base64, validate=True)
        except Exception:
            raw = b""
        for prefix, mime in _MAGIC:
            if len(raw) >= len(prefix) and raw[: len(prefix)] == prefix:
                from_content = mime
                break

    if from_content is not None:
        return {
            "mime_type": from_content,
            "encoding": None,
            "source": "content",
        }
    if from_path is not None:
        return {
            "mime_type": from_path,
            "encoding": encoding_from_path,
            "source": "path",
        }
    return {
        "mime_type": None,
        "encoding": encoding_from_path,
        "source": "path_fallback",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
