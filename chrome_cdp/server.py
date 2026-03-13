"""MCP stdio server using FastMCP that controls Chrome via the Chrome DevTools Protocol (CDP).

Chrome must be running with --remote-debugging-port enabled.
No screenshot support — text-only interaction to minimize token usage.

Tools:
  - list_tabs: list open browser tabs
  - navigate: go to a URL
  - evaluate: run JavaScript in the page
  - get_page_content: get page text or HTML
  - click: click a DOM element by CSS selector
  - type_text: type into an input element by CSS selector
  - query_elements: find elements matching a CSS selector
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import httpx
import websockets
from fastmcp import FastMCP

mcp = FastMCP("chrome-cdp")

_MSG_ID_COUNTER = 0


def _next_id() -> int:
    global _MSG_ID_COUNTER
    _MSG_ID_COUNTER += 1
    return _MSG_ID_COUNTER


async def _get_tabs(host: str, port: int) -> List[Dict[str, Any]]:
    """Fetch the list of debuggable targets from Chrome."""
    url = f"http://{host}:{port}/json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        targets = resp.json()
    return [t for t in targets if t.get("type") == "page"]


async def _get_ws_url(host: str, port: int, tab_index: int) -> str:
    """Get the WebSocket debugger URL for a specific tab."""
    tabs = await _get_tabs(host, port)
    if not tabs:
        raise ValueError("No open tabs found in Chrome.")
    if tab_index < 0 or tab_index >= len(tabs):
        raise ValueError(
            f"tab_index {tab_index} out of range. Found {len(tabs)} tab(s)."
        )
    ws_url = tabs[tab_index].get("webSocketDebuggerUrl")
    if not ws_url:
        raise ValueError(
            f"Tab {tab_index} has no webSocketDebuggerUrl. "
            "It may already be attached to another debugger."
        )
    return ws_url


async def _cdp_send(ws, method: str, params: Optional[Dict] = None) -> Dict:
    """Send a CDP command and wait for its response."""
    msg_id = _next_id()
    payload = {"id": msg_id, "method": method}
    if params:
        payload["params"] = params
    await ws.send(json.dumps(payload))

    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=30)
        data = json.loads(raw)
        if data.get("id") == msg_id:
            if "error" in data:
                raise RuntimeError(
                    f"CDP error: {data['error'].get('message', data['error'])}"
                )
            return data.get("result", {})


async def _cdp_command(
    host: str, port: int, tab_index: int, method: str, params: Optional[Dict] = None
) -> Dict:
    """Open a WebSocket to a tab, send one CDP command, return the result."""
    ws_url = await _get_ws_url(host, port, tab_index)
    async with websockets.connect(ws_url, max_size=10 * 1024 * 1024) as ws:
        return await _cdp_send(ws, method, params)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_tabs(host: str = "localhost", port: int = 9222) -> str:
    """List open Chrome tabs.

    Args:
        host: Chrome DevTools host (default: localhost).
        port: Chrome DevTools port (default: 9222).
    """
    try:
        tabs = await _get_tabs(host, port)
        lines = []
        for i, tab in enumerate(tabs):
            title = tab.get("title", "(no title)")
            url = tab.get("url", "")
            lines.append(f"[{i}] {title}\n    {url}")
        return "\n".join(lines) if lines else "No open tabs found."
    except httpx.ConnectError:
        return f"Error: Could not connect to Chrome at {host}:{port}. Is Chrome running with --remote-debugging-port={port}?"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def navigate(
    url: str,
    host: str = "localhost",
    port: int = 9222,
    tab_index: int = 0,
    wait_for_load: bool = True,
) -> str:
    """Navigate a tab to a URL.

    Args:
        url: The URL to navigate to.
        host: Chrome DevTools host (default: localhost).
        port: Chrome DevTools port (default: 9222).
        tab_index: Index of the tab to use (default: 0, the first tab).
        wait_for_load: Wait for the page load event before returning (default: true).
    """
    try:
        ws_url = await _get_ws_url(host, port, tab_index)
        async with websockets.connect(ws_url, max_size=10 * 1024 * 1024) as ws:
            if wait_for_load:
                await _cdp_send(ws, "Page.enable")

            result = await _cdp_send(ws, "Page.navigate", {"url": url})

            if wait_for_load:
                # Wait for Page.loadEventFired
                deadline = asyncio.get_event_loop().time() + 30
                while asyncio.get_event_loop().time() < deadline:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    data = json.loads(raw)
                    if data.get("method") == "Page.loadEventFired":
                        break

            error_text = result.get("errorText")
            if error_text:
                return f"Navigation error: {error_text}"
            return f"Navigated to {url}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def evaluate(
    expression: str,
    host: str = "localhost",
    port: int = 9222,
    tab_index: int = 0,
) -> str:
    """Execute JavaScript in the page context and return the result.

    Args:
        expression: JavaScript expression to evaluate.
        host: Chrome DevTools host (default: localhost).
        port: Chrome DevTools port (default: 9222).
        tab_index: Index of the tab (default: 0).
    """
    try:
        result = await _cdp_command(
            host,
            port,
            tab_index,
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        remote_obj = result.get("result", {})
        if remote_obj.get("subtype") == "error":
            return f"JS error: {remote_obj.get('description', remote_obj)}"
        value = remote_obj.get("value")
        if value is None and remote_obj.get("type") == "undefined":
            return "undefined"
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2)
        return str(value)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def get_page_content(
    host: str = "localhost",
    port: int = 9222,
    tab_index: int = 0,
    format: str = "text",
) -> str:
    """Get the current page content.

    Args:
        host: Chrome DevTools host (default: localhost).
        port: Chrome DevTools port (default: 9222).
        tab_index: Index of the tab (default: 0).
        format: "text" for innerText (default, saves tokens) or "html" for full HTML.
    """
    if format == "html":
        expr = "document.documentElement.outerHTML"
    else:
        expr = "document.body.innerText"
    return await evaluate(expr, host, port, tab_index)


@mcp.tool()
async def click(
    selector: str,
    host: str = "localhost",
    port: int = 9222,
    tab_index: int = 0,
) -> str:
    """Click a DOM element by CSS selector.

    Args:
        selector: CSS selector for the element to click.
        host: Chrome DevTools host (default: localhost).
        port: Chrome DevTools port (default: 9222).
        tab_index: Index of the tab (default: 0).
    """
    js = f"""
    (() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) return 'ERROR: No element found for selector: {selector}';
        el.scrollIntoView({{block: 'center'}});
        el.click();
        return 'Clicked: ' + (el.tagName || '') + (el.id ? '#' + el.id : '') + (el.className ? '.' + el.className.split(' ').join('.') : '');
    }})()
    """
    return await evaluate(js, host, port, tab_index)


@mcp.tool()
async def type_text(
    selector: str,
    text: str,
    clear_first: bool = True,
    host: str = "localhost",
    port: int = 9222,
    tab_index: int = 0,
) -> str:
    """Type text into an input or textarea element.

    Args:
        selector: CSS selector for the input element.
        text: The text to type.
        clear_first: Clear existing value before typing (default: true).
        host: Chrome DevTools host (default: localhost).
        port: Chrome DevTools port (default: 9222).
        tab_index: Index of the tab (default: 0).
    """
    escaped_text = json.dumps(text)
    clear_js = "el.value = '';" if clear_first else ""
    js = f"""
    (() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) return 'ERROR: No element found for selector: {selector}';
        el.focus();
        {clear_js}
        el.value = {escaped_text};
        el.dispatchEvent(new Event('input', {{bubbles: true}}));
        el.dispatchEvent(new Event('change', {{bubbles: true}}));
        return 'Typed ' + {escaped_text}.length + ' chars into ' + (el.tagName || '');
    }})()
    """
    return await evaluate(js, host, port, tab_index)


@mcp.tool()
async def query_elements(
    selector: str,
    host: str = "localhost",
    port: int = 9222,
    tab_index: int = 0,
    limit: int = 20,
) -> str:
    """Find elements matching a CSS selector and return their details.

    Args:
        selector: CSS selector to query.
        host: Chrome DevTools host (default: localhost).
        port: Chrome DevTools port (default: 9222).
        tab_index: Index of the tab (default: 0).
        limit: Maximum number of elements to return (default: 20).
    """
    js = f"""
    (() => {{
        const els = Array.from(document.querySelectorAll({json.dumps(selector)})).slice(0, {limit});
        return els.map((el, i) => ({{
            index: i,
            tag: el.tagName.toLowerCase(),
            id: el.id || null,
            classes: el.className || null,
            text: (el.innerText || '').slice(0, 200),
            href: el.href || null,
            type: el.type || null,
            value: el.value || null,
            name: el.name || null,
        }}));
    }})()
    """
    return await evaluate(js, host, port, tab_index)


@mcp.tool()
async def get_element_attributes(
    selector: str,
    host: str = "localhost",
    port: int = 9222,
    tab_index: int = 0,
) -> str:
    """Get all attributes of an element matching a CSS selector.

    Args:
        selector: CSS selector for the element.
        host: Chrome DevTools host (default: localhost).
        port: Chrome DevTools port (default: 9222).
        tab_index: Index of the tab (default: 0).
    """
    js = f"""
    (() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) return 'ERROR: No element found for selector: {selector}';
        const attrs = {{}};
        for (const attr of el.attributes) {{
            attrs[attr.name] = attr.value;
        }}
        attrs['_tag'] = el.tagName.toLowerCase();
        attrs['_text'] = (el.innerText || '').slice(0, 500);
        return attrs;
    }})()
    """
    return await evaluate(js, host, port, tab_index)


if __name__ == "__main__":
    mcp.run(transport="stdio")
