# Vectorstore Code Parser

Use this when the user needs semantic code retrieval from a local embeddings JSON file that contains indexed code chunks and metadata.

## When to use

Use when the user asks to:
- Search for relevant code by meaning (not exact string match)
- Retrieve function-level code and description chunks
- Filter results by chunk type (`raw_code`, `description`, or both)
- Narrow by language or specific file path/function name
- Query across multiple codebases by changing the per-call `embeddings_path`

## Common MCP tool usage

Use the `code-search` MCP server tools.

### `search_code`
- Required: `embeddings_path`, `query`
- Optional: `chunk_type` (`both` default), `language`, `limit` (default 5)
- Behavior: embeds the query with `text-embedding-3-small`, runs local cosine similarity search, then post-filters by `chunk_type`, `language`, and `MIN_SCORE`.

### `get_function`
- Required: `embeddings_path`, `function_name`
- Optional: `file_path`
- Behavior: direct metadata lookup in loaded records (no embedding API call), returns matching `raw_code`/`description` chunks.

## Response shape (high level)

All tool calls return JSON dictionaries:
- `status`: `ok`, `no_results`, or `error`
- `results`: list of result objects when applicable
- On errors: `error.type` and `error.message`

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

1. Confirm or request the `embeddings_path`.
2. Use `search_code` with a focused natural-language query.
3. Apply filters (`chunk_type`, `language`) and tune with `MIN_SCORE` if needed.
4. If a specific symbol is needed, call `get_function`.
5. Summarize top matches with file path, function name, and confidence.

## Safety notes

- `OPENAI_API_KEY` must be configured for the MCP server process.
- Ensure `embeddings_path` exists and points to a valid embeddings JSON array.
- Validate required fields before calls (`embeddings_path`, `query`/`function_name`).
- Embedding vectors are stripped from tool outputs before returning results.
- Treat semantic matches as candidates and verify with surrounding code context.
