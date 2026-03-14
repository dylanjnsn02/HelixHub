# Obsidian

Use this when the user needs to interact with their Obsidian vault via the Local REST API: read/write notes, search, execute commands, manage periodic notes, or work with the active file.

## When to use

Use when the user asks to:
- Read, create, update, append to, or delete notes in their Obsidian vault
- Get or modify the currently active file in Obsidian
- Search the vault by text query, JsonLogic, or Dataview DQL
- List files or directories in the vault
- Execute Obsidian commands (e.g. open graph view, global search)
- Open a file in the Obsidian UI
- Work with periodic notes (daily, weekly, monthly, quarterly, yearly)
- Patch content relative to headings, block references, or frontmatter fields
- Configure the Obsidian API connection (host, port, protocol)

## Setup

- Requires the **Obsidian Local REST API** plugin installed in Obsidian.
- API key stored in `auth.key` next to `server.py`.
- Connection settings (optional) in `connection.json` — defaults to `https://127.0.0.1:27124`.
- Self-signed certificates are accepted automatically.

## Common MCP tool usage

Use the **obsidian** MCP server tools. All tools return a dict with `status_code` and either `data` (JSON), `text` (markdown/string), or `message` ("Success" for 204 responses).

### Connection

- **configure_connection** — `host` (optional), `port` (optional), `protocol` ("http"/"https", optional); saves to connection.json; returns updated connection info.
- **get_server_status** — no args; returns server info and authentication status.

### Active File

- **get_active_file** — `format` ("markdown", "json", "document-map"); returns the currently open file's content.
- **update_active_file** — `content`; replaces the entire active file content.
- **append_to_active_file** — `content`; appends markdown to the end of the active file.
- **patch_active_file** — `content`, `operation` ("append"/"prepend"/"replace"), `target_type` ("heading"/"block"/"frontmatter"), `target`, optional `target_delimiter` (default "::"), optional `content_type`; inserts content relative to a heading, block ref, or frontmatter field.
- **delete_active_file** — no args; deletes the active file.

### Vault Files

- **list_vault_files** — `path` (default "/"); lists files in a vault directory.
- **get_vault_file** — `filename`, `format` ("markdown"/"json"/"document-map"); returns file content.
- **create_or_update_vault_file** — `filename`, `content`; creates or overwrites a file.
- **append_to_vault_file** — `filename`, `content`; appends to a file (creates if missing).
- **patch_vault_file** — `filename`, `content`, `operation`, `target_type`, `target`, optional `target_delimiter`, optional `content_type`; patches content relative to a target.
- **delete_vault_file** — `filename`; deletes a file.

### Commands

- **list_commands** — no args; returns all available Obsidian commands with id and name.
- **execute_command** — `command_id` (e.g. "global-search:open"); executes the command.

### Open

- **open_file** — `filename`, optional `new_leaf` (bool); opens a file in the Obsidian UI.

### Search

- **search_simple** — `query`, optional `context_length` (default 100); text search across all vault files. Returns filenames, scores, and match contexts.
- **search_jsonlogic** — `query` (JsonLogic object); searches note metadata (content, frontmatter, path, stat, tags). Extra operators: `glob`, `regexp`.
- **search_dataview** — `dql_query`; runs a Dataview DQL TABLE query (requires Dataview plugin).

### Periodic Notes

Current period:
- **get_periodic_note** — `period` ("daily"/"weekly"/"monthly"/"quarterly"/"yearly"), `format`.
- **update_periodic_note** — `period`, `content`.
- **append_to_periodic_note** — `period`, `content`.
- **patch_periodic_note** — `period`, `content`, `operation`, `target_type`, `target`, optional `target_delimiter`, optional `content_type`.
- **delete_periodic_note** — `period`.

By specific date:
- **get_periodic_note_by_date** — `period`, `year`, `month`, `day`, `format`.
- **update_periodic_note_by_date** — `period`, `year`, `month`, `day`, `content`.
- **append_to_periodic_note_by_date** — `period`, `year`, `month`, `day`, `content`.
- **patch_periodic_note_by_date** — `period`, `year`, `month`, `day`, `content`, `operation`, `target_type`, `target`, optional `target_delimiter`, optional `content_type`.
- **delete_periodic_note_by_date** — `period`, `year`, `month`, `day`.

## Patch targeting

The `patch_*` tools allow inserting content relative to:
- **heading**: Use `::` delimiter for nested headings (e.g. `"Heading 1::Subheading 1:1"`).
- **block**: Use the block reference ID without the `^` prefix (e.g. `"2d9b4a"`).
- **frontmatter**: Use the field name (e.g. `"alpha"`).

Use `format: "document-map"` on any GET tool to discover available headings, blocks, and frontmatter fields.

When patching tables (block target), use `content_type: "application/json"` with row data as `[["col1", "col2"]]`.

## Response format

All tools return a dict with:
- **status_code**: HTTP status (200, 204, 400, 404, 405).
- **data**: Parsed JSON (when response is JSON).
- **text**: Raw text (when response is markdown or plain text).
- **message**: "Success" (for 204 no-content responses).

## Example user requests

"What's in my daily note?", "Create a new note called projects/roadmap.md", "Search my vault for meeting notes", "Append a task to my active file", "Set the frontmatter field status to done in my daily note", "List all commands available in Obsidian", "Connect to Obsidian on 192.168.1.10 port 27124"

## Example approach

1. If connecting to a non-default host/port, use **configure_connection** first.
2. For reads: use **get_vault_file**, **get_active_file**, **search_simple**, or **list_vault_files**.
3. For writes: use **create_or_update_vault_file**, **append_to_vault_file**, or **patch_vault_file**.
4. For targeted edits: first get the document map (`format: "document-map"`), then use the appropriate `patch_*` tool.
5. For periodic notes: use the period-specific tools with the appropriate period type.

## Safety notes

- **Destructive operations**: `delete_*` and `update_*` (full replace) are irreversible. Confirm with the user before deleting or overwriting files.
- **Connection**: Self-signed SSL certs are accepted. The API key is read from `auth.key` and sent as a Bearer token.
- **Paths**: All file paths are relative to the vault root. Do not use absolute paths.
