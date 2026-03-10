# Utilities

Use this when the user needs current date/time, hashes, environment info, network reachability (ping), or MIME type detection.

## When to use

Use when the user asks to:
- Get the current date or time (in any timezone format, UTC, epoch, etc.)
- Hash a string (e.g. for checksums or idempotency keys)
- Learn about the environment (platform, Python version, timezone)
- Ping a host to check reachability or latency
- Detect the MIME type of a file (by path or by content)

## Common MCP tool usage

Use the **utilities** MCP server tools as needed:

- **current_date** — no args; returns date/time in multiple formats (utc, iso, epoch, epoch_ms, mountain, human).
- **hash_sha256** — `text` (string to hash); returns 64-char hex digest.
- **environment_info** — no args; returns platform, release, Python version, timezone.
- **ping** — `host` (required), optional `count` (1–10), `timeout_seconds` (1–30).
- **detect_mime_type** — optional `path` (file path), optional `content_base64` (base64-encoded content); provide at least one.

## Parameters (summary)

| Tool              | Key parameters | Notes |
|-------------------|----------------|--------|
| current_date      | —              | Returns: utc, iso, epoch, epoch_ms, mountain, human |
| hash_sha256       | text           | UTF-8 encoded then hashed |
| environment_info  | —              | Returns: platform, platform_release, python_version, timezone |
| ping              | host, count, timeout_seconds | rtt_ms in result when available |
| detect_mime_type  | path, content_base64 | source is "path", "content", or "path_fallback" |

## Response (high level)

- **current_date**: dict with `utc`, `iso`, `epoch`, `epoch_ms`, `mountain`, `human`.
- **ping**: dict with `success`, `message`, and optionally `rtt_ms`.
- **detect_mime_type**: dict with `mime_type`, `encoding`, `source`.

## Example user request

"What's the current time in UTC?" or "Ping google.com" or "What MIME type is report.pdf?"

## Example approach

1. Identify which utility is needed (date, hash, env, ping, or MIME).
2. Call the corresponding tool with the right parameters (e.g. **ping** with host; **detect_mime_type** with path and/or content_base64).
3. Use the returned fields (e.g. `current_date.utc`, `ping.rtt_ms`, `detect_mime_type.mime_type`) to answer or pass on to other tools.
4. For **detect_mime_type**, prefer content (content_base64) when the file might have a wrong extension; use path for quick extension-based guess.

## Safety notes

- **ping**: Use reasonable timeout; some hosts block ICMP.
- **hash_sha256**: Use for non-secret content (checksums, ids); do not rely on SHA-256 alone for password storage.
- **detect_mime_type**: Content-based detection uses magic bytes; provide enough bytes (e.g. first few KB as base64) for reliable detection.
