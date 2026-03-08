"""
MCP stdio server using FastMCP that proxies system commands to remote Go host agents via HTTP POST.
Usage: python mcp_server.py
"""

import httpx
from fastmcp import FastMCP

mcp = FastMCP("remote-exec")


@mcp.tool()
async def run_command(ip: str, command: str, timeout: int = 30) -> str:
    """
    Run a shell command on a remote host agent.
    The agent must be running the Go host agent on port 8080.

    Args:
        ip: IP address of the remote host agent (e.g. 192.168.1.50)
        command: Shell command to execute on the remote host
        timeout: Timeout in seconds (default: 30)
    """
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
