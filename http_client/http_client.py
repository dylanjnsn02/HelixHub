"""MCP stdio server using FastMCP that performs generic HTTP requests.

Tools:
  - request: make an HTTP request with method, URL, headers, query params, and body.
"""

from typing import Any, Dict, Optional

import httpx
from fastmcp import FastMCP

mcp = FastMCP("http-client")


@mcp.tool()
async def request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    text_body: Optional[str] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Make an HTTP request.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE, etc.).
        url: Full URL to call (including scheme, e.g. https://...).
        headers: Optional HTTP headers.
        params: Optional query parameters.
        json_body: Optional JSON body (will set Content-Type: application/json).
        text_body: Optional raw text body (ignored if json_body is provided).
        timeout: Timeout in seconds (default: 30).

    Returns:
        A dict with keys: status_code, headers, text, json (if parseable),
        and error (if something went wrong).
    """

    method_upper = method.upper().strip()

    # Decide body and content type
    data = None
    json_data = None

    if json_body is not None:
        json_data = json_body
    elif text_body is not None:
        data = text_body

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method=method_upper,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                content=data,
            )

        result: Dict[str, Any] = {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "text": resp.text,
        }

        # Try to parse JSON body if present
        try:
            result["json"] = resp.json()
        except Exception:
            result["json"] = None

        return result

    except httpx.RequestError as e:
        return {"error": f"Request error: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
