# HTTP Client

Use this when the user needs to call an HTTP API, fetch a URL, or send web requests.

## When to use

Use when the user asks to:
- Call an API (REST, webhooks, etc.)
- Fetch a URL or webpage content
- Send GET, POST, PUT, PATCH, or DELETE requests
- Check if a URL is reachable or what it returns

## Common MCP tool usage

Use the **http_client__request** tool with the appropriate method, URL, and optional headers, query params, or body.

## Parameters

- **method**: HTTP method — `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, etc.
- **url**: Full URL including scheme (e.g. `https://api.example.com/v1/users`).
- **headers**: Optional map of header name → value (e.g. `Authorization`, `Content-Type`).
- **params**: Optional query parameters as a map (e.g. `{"page": "1", "limit": "10"}`).
- **json_body**: Optional JSON body; sets `Content-Type: application/json` automatically. Use for POST/PUT/PATCH when sending JSON.
- **text_body**: Optional raw text body; ignored if `json_body` is provided. Use for form data or plain text.
- **timeout**: Timeout in seconds (default: 30).

## Response

The tool returns a dict with:
- **status_code**: HTTP status (200, 404, 500, etc.).
- **headers**: Response headers as a map.
- **text**: Response body as a string.
- **json**: Parsed JSON if the response is JSON; otherwise `null`.
- **error**: Present only if the request failed (e.g. connection error, timeout).

## Example user request

"Check what https://api.github.com returns" or "POST to https://example.com/webhook with body {\"event\": \"ping\"}"

## Example approach

1. Choose the correct method (GET for fetching, POST for sending data, etc.).
2. Build the full URL; add query params via **params** or in the URL.
3. For POST/PUT/PATCH with JSON, use **json_body**; for custom headers (e.g. API key), use **headers**.
4. Call **http_client__request** and inspect **status_code**, **text** or **json**, and **error** if present.
5. Summarize the result for the user (status, key fields, or error message).

## Safety notes

- Use **timeout** to avoid hanging on slow or unresponsive hosts.
- Do not send secrets in URLs or in log summaries; use headers when possible.
- If the response has **error**, report it clearly and suggest next steps (e.g. check URL, network, or API key).
