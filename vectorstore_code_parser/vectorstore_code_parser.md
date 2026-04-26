# Vectorstore Code Parser

Use this when the user needs semantic code retrieval from an OpenAI Vector Store that contains indexed code chunks and metadata.

## When to use

Use when the user asks to:
- Search for relevant code by meaning (not exact string match)
- Retrieve function-level code and description chunks
- Filter results by chunk type (`raw_code`, `description`, or both)
- Narrow by language or specific file path/function name
- Explore unfamiliar codebases already embedded in a Vector Store

## Common MCP tool usage

Use the `vectorstore-code-parser` MCP server tools.

### `search_code`
- Required: `vector_store_id`, `query`
- Optional: `chunk_type` (`both` default), `language`, `limit` (default 5, capped)
- Behavior: semantic search against Vector Store and returns normalized results sorted by score.

### `get_function`
- Required: `vector_store_id`, `function_name`
- Optional: `file_path`
- Behavior: fetches best `raw_code`/`description` chunks for one function name.

## Response shape (high level)

All tool calls return JSON dictionaries:
- `status`: `ok`, `no_results`, or `error`
- `results`: list of result objects when applicable
- On errors: `error.type`, `error.message`, and optional `error.details`

Result rows typically include:
- `function_name`
- `file_path`
- `lines`
- `language`
- `chunk_type`
- `content`
- `score`

## Example user requests

- "Find where auth tokens are validated in this codebase."
- "Get the `create_user` function implementation."
- "Search only Python description chunks for retry logic."
- "Show the `parse_config` function from `src/config.py`."

## Example approach

1. Confirm or request the `vector_store_id`.
2. Use `search_code` with a focused natural-language query.
3. Apply filters (`chunk_type`, `language`) to reduce noise.
4. If a specific symbol is needed, call `get_function`.
5. Summarize top matches with file path, function name, and confidence.

## Safety notes

- `OPENAI_API_KEY` must be configured for the MCP server process.
- Validate required fields before calls (`vector_store_id`, `query`/`function_name`).
- Treat semantic matches as candidates and verify with surrounding code context.
