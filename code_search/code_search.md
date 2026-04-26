# Code Search

Use this when the user wants semantic/code search over a local directory by providing a path and query.

## When to use

Use when the user asks to:
- Search a local codebase with natural language
- Search a remote GitHub repository with natural language
- Find relevant code chunks for a query
- Locate where behavior appears in code using semantic matching

## Common MCP tool usage

Use:
- `code_search.search_codebase` for local directories
- `code_search.search_github_repo` for remote GitHub repositories

## Parameters

`code_search.search_codebase`:
- **path**: Local directory path to index and search.
- **query**: Natural-language or code search query.
- **top_k**: Optional number of matches to return (default: 5).

`code_search.search_github_repo`:
- **repo_url**: GitHub repository URL to index (for example `https://github.com/MinishLab/model2vec`).
- **query**: Natural-language or code search query.
- **top_k**: Optional number of matches to return (default: 5).

## Response

The tool returns:
- **results**: Array of matched chunks with:
  - `file_path`
  - `start_line`
  - `end_line`
  - `content`

## Example user request

"Search `./src` for where API keys are stored."  
"Search `https://github.com/MinishLab/model2vec` for save_pretrained logic."

## Example approach

1. Confirm whether the target is local path or GitHub URL.
2. Write a focused query.
3. Run `code_search.search_codebase` (local) or `code_search.search_github_repo` (GitHub).
4. Summarize key matches and suggest follow-up queries.

## Safety notes

- Indexing very large directories may take longer.
- Ensure the provided path exists on disk before searching.
- Indexing large remote repositories may take longer and depends on network access.
