---
name: searcher
description: Use the Searcher MCP to index local files or URLs and run hybrid semantic+keyword retrieval. Trigger when the user asks to find relevant documentation sections, explore large text/code knowledge bases, fetch full line ranges from results, or discover related chunks.
---

# Searcher MCP Skill

Use this skill when users need high-recall document discovery across repos, docs, markdown, text, or indexed web pages.

## When to use

- User asks to "search docs", "find where this is explained", or "locate relevant sections."
- User needs semantic retrieval (meaning-based) plus keyword matching in one query.
- User wants to expand a result into exact line ranges or nearby related chunks.

## Available tools

- `search(path, query, top_k=5, context_lines=20)`
  - Returns hybrid-ranked chunks with: `file_path`, `start_line`, `end_line`, `heading`, `content`, `score`, `rank`.
  - Supports local paths and indexed URLs.
- `find_related(path, file_path, start_line, top_k=3)`
  - Returns similar chunks to a known result anchor.
- `get_content(path, file_path, start_line, end_line)`
  - Retrieves the exact inclusive line range from an indexed file or URL text.

## Usage workflow

1. Start with `search` using a focused natural-language query.
2. If hits are broad, refine terms and increase/decrease `top_k`.
3. Use `get_content` to pull full sections for the best hits.
4. Use `find_related` from a strong hit to expand nearby concepts.
5. Summarize findings with clear source references and key excerpts.

## Query tips

- Prefer domain terms plus intent (example: "token refresh flow error handling").
- For symbol-heavy queries, keep exact identifiers in the prompt.
- Increase `context_lines` when local surrounding context matters.
- Keep `top_k` small for precision, larger for exploration.

## Constraints and caveats

- Results only come from content indexed under the provided `path`.
- `get_content` returns empty content for non-indexed targets.
- URL indexing requires optional runtime dependencies for HTTP and HTML parsing.
- PDF indexing requires a compatible PyMuPDF package.
