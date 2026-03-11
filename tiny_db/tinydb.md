# TinyDB

Use this when the user needs to read or write JSON document data via TinyDB: create tables, insert/query/update/remove documents, inspect schema, or manage DB files.

## When to use

Use when the user asks to:
- Store or retrieve structured JSON-like data in a local file
- Create or manage TinyDB tables and documents
- Query documents by field conditions (equality, ranges, regex, one_of, etc.)
- Update or remove documents by doc_id or query
- Inspect table names, document counts, or schema (field types and examples)
- Truncate tables, drop tables, or read raw DB JSON

## Common MCP tool usage

Use the **tinydb-mcp** (or **tinydb**) MCP server tools as needed. All tools that take `db_path` require an absolute or relative path to a TinyDB JSON file (e.g. `data.json`). Optional `table_name` defaults to the default table (`_default`).

### Response format (TOON vs JSON)
- **TOON format**: All tools except **read_raw_db** and **get_schema** return a single **TOON**-formatted string. Decode with `toon_format.decode()` (Python) or your language’s TOON decoder to get the same structure (e.g. `documents`, `count`, `document`, `found`). See [TOON API](https://github.com/toon-format/toon-python/blob/main/docs/api.md).
- **read_raw_db** and **get_schema** return normal JSON/dicts (raw data and schema) unchanged.

### Input format for document payloads (TOON or JSON)
- **insert_document**, **insert_documents**, **update_documents**, and **upsert_documents** accept **either JSON or TOON** for the document payload:
  - **document** (single): pass a JSON object **or** a TOON string that encodes a single object. The server decodes TOON to a JSON object before inserting/updating/upserting.
  - **documents** (multiple, insert only): pass a JSON array **or** a TOON string that encodes a list of objects. The server decodes TOON to a list of JSON objects before inserting.
- Prefer **TOON** when the LLM finds it easier to produce (e.g. fewer escaping issues, more compact). Example TOON for one document: `text: create things telegram bot\ncreated_at: "2026-03-10T00:00:00Z"`. The server converts TOON to JSON internally; stored data is the same either way.

### Tables
- **list_tables** — `db_path`; returns TOON with `tables` (sorted list of table names).
- **create_table** — `db_path`, `table_name`; creates/opens table; returns TOON with `created_or_opened`, `tables`.
- **drop_table** — `db_path`, `table_name`; drops one table; returns TOON.
- **drop_tables** — `db_path`; drops all tables; returns TOON.
- **truncate_table** — `db_path`, optional `table_name`; empties the table; returns TOON.

### Documents (read)
- **all_documents** — `db_path`, optional `table_name`; returns TOON with `documents` (list), `count`.
- **get_document** — `db_path`, optional `table_name`, and either `doc_id` or `query`; returns TOON with `document`, `found`.
- **search_documents** — `db_path`, `query` (query spec), optional `table_name`; returns TOON with `documents`, `count`.
- **contains_document** — `db_path`, optional `table_name`, and either `doc_id` or `query`; returns TOON with `contains`.
- **count_documents** — `db_path`, `query`, optional `table_name`; returns TOON with `count`.
- **table_length** — `db_path`, optional `table_name`; returns TOON with `count`.

### Documents (write)
- **insert_document** — `db_path`, `document` (JSON object **or** TOON string for one object), optional `table_name`; server converts TOON to JSON; returns TOON with `doc_id`.
- **insert_documents** — `db_path`, `documents` (JSON array **or** TOON string for a list of objects), optional `table_name`; server converts TOON to JSON; returns TOON with `doc_ids`, `count`.
- **update_documents** — `db_path`, `document` (JSON object **or** TOON string for the update payload), optional `table_name`, and either `doc_ids` or `query`; server converts TOON to JSON; returns TOON with `updated_doc_ids`, `count`.
- **upsert_documents** — `db_path`, `document` (JSON object **or** TOON string for one object), `query`, optional `table_name`; server converts TOON to JSON; returns TOON with `affected_doc_ids`, `count`.
- **remove_documents** — `db_path`, optional `table_name`, and either `doc_ids` or `query`; returns TOON with `removed_doc_ids`, `count`.

### Inspection / raw
- **read_raw_db** — `db_path`; returns **JSON** dict with `raw` (unchanged; not TOON).
- **get_schema** — `db_path`, optional `table_name`, optional `sample_limit` (default 1000); returns **JSON** dict with `table`, `sampled_documents`, `schema` (unchanged; not TOON).
- **close_db** — `db_path`; closes the DB (optional); returns TOON.
- **ping** — no args; returns TOON with server status.

## Query spec (for search_documents, count_documents, update_documents, remove_documents, upsert_documents)

Queries are JSON objects with an `op` and supporting fields:

| op        | Required fields     | value/other | Description |
|-----------|---------------------|-------------|-------------|
| eq        | field, value        | any         | field == value |
| ne        | field, value       | any         | field != value |
| lt, lte, gt, gte | field, value | number/string | comparison |
| exists    | field              | —           | field exists |
| matches   | field, value       | regex str   | full match |
| search    | field, value       | regex str   | substring match |
| one_of    | field, value       | list        | field in list |
| any       | field, value       | list        | field contains any of list |
| all       | field, value       | list        | field contains all of list |
| fragment  | value              | object      | document contains fragment |
| and       | conditions         | list of query specs | all must match |
| or        | conditions         | list of query specs | at least one matches |
| not       | condition          | one query spec | negation |

Example: `{"op": "and", "conditions": [{"op": "eq", "field": "status", "value": "active"}, {"op": "gte", "field": "score", "value": 10}]}`

## Response (high level)

- **TOON responses** (all tools except read_raw_db and get_schema): the tool returns a single TOON string. Decode with `toon_format.decode(response)` (Python) to get a dict with the same logical fields (e.g. `documents`, `document`, `count`, `found`, `doc_id`, `tables`). Documents include `doc_id`.
- **read_raw_db** / **get_schema**: return normal JSON dicts; `raw` and `schema` unchanged.
- Counts and ids in TOON-decoded dicts: `count`, `doc_id`, `doc_ids`, `updated_doc_ids`, `removed_doc_ids`, `affected_doc_ids`.

## Example user request

"Create a TinyDB table called tasks and insert a task with title and done", "Find all documents where status is active", "Update the document with doc_id 3 to set completed to true", "What's the schema of the users table?"

## Example approach

1. Identify the DB file path and table (if not default).
2. For reads: use **list_tables** / **all_documents** / **get_document** / **search_documents** / **count_documents** / **table_length** / **get_schema** as needed.
3. For writes: use **insert_document** / **insert_documents** / **update_documents** / **upsert_documents** / **remove_documents** / **truncate_table**.
4. For **insert_document** / **insert_documents** / **update_documents** / **upsert_documents**: pass `document` (or `documents` for insert_documents) as **TOON** when convenient (e.g. `text: my task\ncreated_at: "2026-03-10T00:00:00Z"` for one doc). The server decodes TOON to JSON before storing/updating. You can also pass normal JSON.
5. Build query specs for search/count/update/remove/upsert using the op table above.
6. Decode TOON responses with `toon_format.decode()` when you need to use document content or other fields; use **read_raw_db** / **get_schema** results as plain JSON.

## Safety notes

- **db_path**: Use a path the process can read/write; relative paths are resolved from the MCP server cwd.
- **query**: Invalid query specs (e.g. missing `field` for `eq`, wrong types) raise errors; validate before calling.
- **get_schema**: Uses a sample of documents; large tables may have incomplete type coverage.
