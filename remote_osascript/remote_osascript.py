"""
MCP stdio server using FastMCP that runs AppleScript/JXA remotely via a Go host agent.
Usage: python remote_osascript.py
"""

import shlex

import httpx
from fastmcp import FastMCP

mcp = FastMCP("remote-osascript")


def _build_osascript_command(script: str, language: str) -> str:
    normalized = language.strip().lower()
    if normalized not in {"applescript", "javascript"}:
        raise ValueError("language must be 'AppleScript' or 'JavaScript'")

    lang_arg = ""
    if normalized == "javascript":
        lang_arg = "-l JavaScript "

    return f"osascript {lang_arg}-e {shlex.quote(script)}"


@mcp.tool()
async def run_osascript(
    ip: str,
    script: str,
    timeout: int = 30,
    language: str = "AppleScript",
) -> str:
    """
    Run AppleScript or JavaScript for Automation on a remote macOS host agent.
    The remote Go host agent must be running on port 8080.

    Args:
        ip: IP address of the remote host (e.g. 192.168.1.50)
        script: The script body passed to osascript -e
        timeout: Timeout in seconds (default: 30)
        language: "AppleScript" (default) or "JavaScript" (JXA)
    """
    try:
        command = _build_osascript_command(script, language)
    except ValueError as e:
        return f"Error: {str(e)}"

    url = f"http://{ip.strip()}:8080/run"
    payload = {"command": command, "timeout": timeout}

    try:
        async with httpx.AsyncClient(timeout=timeout + 5) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        stdout = data.get("stdout", "")
        stderr = data.get("stderr", "")
        exit_code = data.get("exit_code", 0)

        parts = []
        if stdout:
            parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            parts.append(f"STDERR:\n{stderr}")
        parts.append(f"Exit code: {exit_code}")
        return "\n".join(parts)

    except httpx.ConnectError:
        return f"Error: Could not connect to agent at {ip}:8080"
    except httpx.TimeoutException:
        return f"Error: Request timed out after {timeout}s"
    except httpx.HTTPStatusError as e:
        return f"Error: Agent returned HTTP {e.response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
