"""docindex: hybrid (semantic + BM25) document search with heading-aware reranking."""
from __future__ import annotations

import math
import pickle
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

SUPPORTED_EXTS = {
    ".md", ".txt", ".rst", ".mdx", ".pdf",
    ".py", ".json", ".yaml", ".yml", ".toml",
    ".html", ".htm", ".csv", ".log", ".ini", ".cfg",
}
DEMOTE_PATH_RE = re.compile(r"changelog|examples|legacy|compat|deprecated|archive", re.I)
KEYWORD_QUERY_RE = re.compile(r"[_.]|[a-z][A-Z]|[A-Z]{2,}")
TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S")
MODEL_NAME = "minishlab/potion-retrieval-32M"


@dataclass
class Chunk:
    file_path: str
    start_line: int
    end_line: int
    content: str
    heading: Optional[str]


@dataclass
class SearchResult:
    chunk: Chunk
    score: float
    rank: int


def _tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _line_of_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _find_heading(text: str, start_line: int) -> Optional[str]:
    lines = text.splitlines()
    idx = min(max(start_line - 1, 0), len(lines) - 1)
    for i in range(idx, -1, -1):
        if HEADING_RE.match(lines[i]):
            return lines[i].strip()
    return None


def _read_file(path: Path) -> Optional[str]:
    try:
        if path.suffix.lower() == ".pdf":
            try:
                import pymupdf  # type: ignore
            except ImportError:
                try:
                    import fitz as pymupdf  # type: ignore
                except ImportError:
                    return None
            with pymupdf.open(str(path)) as doc:
                return "\n".join(page.get_text("text") for page in doc)
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _fetch_url(url: str) -> Optional[str]:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as e:
        print(f"URL indexing requires `requests` and `beautifulsoup4`: {e}", file=sys.stderr)
        return None
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "docindex/0.1"})
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "").lower()
        if "html" in ctype:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            return soup.get_text("\n", strip=True)
        # Plain text / markdown / etc — return as-is
        return resp.text
    except Exception as e:
        print(f"Failed to fetch {url}: {e}", file=sys.stderr)
        return None


class DocumentIndex:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.embeddings: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self.bm25 = None
        self._chunk_tokens: list[list[str]] = []
        self._url_text: dict[str, str] = {}
        self._model = None

    def _get_source_text(self, identifier: str) -> Optional[str]:
        if identifier in self._url_text:
            return self._url_text[identifier]
        return _read_file(Path(identifier))

    def _load_model(self):
        if self._model is None:
            from model2vec import StaticModel
            self._model = StaticModel.from_pretrained(MODEL_NAME)
        return self._model

    @classmethod
    def from_path(cls, path: str | Path) -> "DocumentIndex":
        from chonkie import SentenceChunker
        import bm25s

        self = cls()
        chunker = SentenceChunker(chunk_size=512, chunk_overlap=64)

        # Build a list of (identifier, text) tuples to index. Identifier is
        # either an absolute file path or a URL, and is what gets stored on
        # each Chunk's `file_path`.
        documents: list[tuple[str, str]] = []
        if isinstance(path, str) and _is_url(path):
            text = _fetch_url(path)
            if text and text.strip():
                self._url_text[path] = text
                documents.append((path, text))
        else:
            root = Path(path)
            files: list[Path] = []
            if root.is_file():
                files = [root] if root.suffix.lower() in SUPPORTED_EXTS else []
            else:
                for p in root.rglob("*"):
                    if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                        files.append(p)
            for fp in files:
                text = _read_file(fp)
                if text and text.strip():
                    documents.append((str(fp), text))

        for identifier, text in documents:
            try:
                file_chunks = chunker.chunk(text)
            except Exception:
                continue
            for ch in file_chunks:
                content = getattr(ch, "text", None) or str(ch)
                start_idx = getattr(ch, "start_index", 0)
                end_idx = getattr(ch, "end_index", start_idx + len(content))
                start_line = _line_of_offset(text, start_idx)
                end_line = _line_of_offset(text, end_idx)
                heading = _find_heading(text, start_line)
                self.chunks.append(Chunk(
                    file_path=identifier,
                    start_line=start_line,
                    end_line=end_line,
                    content=content,
                    heading=heading,
                ))

        if not self.chunks:
            self.embeddings = np.zeros((0, 1), dtype=np.float32)
            self._chunk_tokens = []
            self.bm25 = bm25s.BM25(k1=1.5, b=0.75)
            self.bm25.index([[""]])
            return self

        contents = [c.content for c in self.chunks]
        model = self._load_model()
        emb = np.asarray(model.encode(contents), dtype=np.float32)
        norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
        self.embeddings = emb / norms

        self._chunk_tokens = [_tokenize(c) or [""] for c in contents]
        self.bm25 = bm25s.BM25(k1=1.5, b=0.75)
        self.bm25.index(self._chunk_tokens)
        return self

    def _semantic_scores(self, query: str) -> np.ndarray:
        if self.embeddings.shape[0] == 0:
            return np.zeros(0, dtype=np.float32)
        model = self._load_model()
        q = np.asarray(model.encode([query]), dtype=np.float32)[0]
        q = q / (np.linalg.norm(q) + 1e-9)
        return self.embeddings @ q

    def _bm25_scores(self, query: str) -> np.ndarray:
        if not self.chunks:
            return np.zeros(0, dtype=np.float32)
        q_tokens = _tokenize(query) or [""]
        scores = self.bm25.get_scores(q_tokens)
        return np.asarray(scores, dtype=np.float32).reshape(-1)

    def _expand_with_context(
        self,
        results: list[SearchResult],
        context_lines: int,
        file_cache: dict[str, Optional[str]],
    ) -> list[SearchResult]:
        if context_lines <= 0:
            return results
        expanded: list[SearchResult] = []
        for sr in results:
            fp = sr.chunk.file_path
            if fp not in file_cache:
                file_cache[fp] = self._get_source_text(fp)
            text = file_cache[fp]
            if not text:
                expanded.append(sr)
                continue
            lines = text.splitlines()
            new_start = max(1, sr.chunk.start_line - context_lines)
            new_end = min(len(lines), sr.chunk.end_line + context_lines)
            new_content = "\n".join(lines[new_start - 1:new_end])
            new_chunk = Chunk(
                file_path=fp,
                start_line=new_start,
                end_line=new_end,
                content=new_content,
                heading=sr.chunk.heading,
            )
            expanded.append(SearchResult(chunk=new_chunk, score=sr.score, rank=sr.rank))
        return expanded

    def search(
        self,
        query: str,
        top_k: int = 5,
        context_lines: int = 20,
    ) -> list[SearchResult]:
        n = len(self.chunks)
        if n == 0:
            return []

        sem = self._semantic_scores(query)
        bm = self._bm25_scores(query)

        # ranks: rank 1 = best
        sem_order = np.argsort(-sem)
        bm_order = np.argsort(-bm)
        sem_rank = np.empty(n, dtype=np.int32)
        bm_rank = np.empty(n, dtype=np.int32)
        sem_rank[sem_order] = np.arange(1, n + 1)
        bm_rank[bm_order] = np.arange(1, n + 1)

        if KEYWORD_QUERY_RE.search(query):
            sem_w, bm_w = 0.4, 0.6
        else:
            sem_w, bm_w = 0.6, 0.4

        fused = sem_w / (60.0 + sem_rank) + bm_w / (60.0 + bm_rank)

        q_tokens = set(_tokenize(query))
        for i, c in enumerate(self.chunks):
            if c.content.lstrip().startswith("#"):
                fused[i] *= 1.3
            if c.heading and q_tokens:
                heading_tokens = set(_tokenize(c.heading))
                if q_tokens & heading_tokens:
                    fused[i] *= 1.4
            if DEMOTE_PATH_RE.search(c.file_path):
                fused[i] *= 0.6

        # File coherence: among top candidates, count hits per file
        cand_n = min(n, max(top_k * 5, 10))
        cand_idx = np.argsort(-fused)[:cand_n]
        file_hits: dict[str, int] = {}
        for i in cand_idx:
            file_hits[self.chunks[i].file_path] = file_hits.get(self.chunks[i].file_path, 0) + 1
        for i in cand_idx:
            hits = file_hits[self.chunks[i].file_path]
            if hits > 1:
                fused[i] *= 1.0 + math.log(hits) * 0.1

        order = np.argsort(-fused)[:top_k]
        results = [
            SearchResult(chunk=self.chunks[i], score=float(fused[i]), rank=r + 1)
            for r, i in enumerate(order)
        ]
        return self._expand_with_context(results, context_lines, {})

    def get_content(self, file_path: str, start_line: int, end_line: int) -> str:
        """Return the lines [start_line, end_line] (1-indexed, inclusive) from a file
        or URL that was part of this index. Returns empty string on miss."""
        indexed_files = {c.file_path for c in self.chunks}
        if file_path not in indexed_files:
            return ""
        text = self._get_source_text(file_path)
        if not text:
            return ""
        lines = text.splitlines()
        s = max(1, start_line)
        e = min(len(lines), end_line)
        if s > e:
            return ""
        return "\n".join(lines[s - 1:e])

    def find_related(self, result: SearchResult, top_k: int = 3) -> list[SearchResult]:
        if self.embeddings.shape[0] == 0:
            return []
        target = result.chunk
        src_idx = None
        for i, c in enumerate(self.chunks):
            if c.file_path == target.file_path and c.start_line == target.start_line:
                src_idx = i
                break
        if src_idx is None:
            return []
        sims = self.embeddings @ self.embeddings[src_idx]
        sims[src_idx] = -np.inf
        order = np.argsort(-sims)[:top_k]
        return [
            SearchResult(chunk=self.chunks[i], score=float(sims[i]), rank=r + 1)
            for r, i in enumerate(order)
        ]

    def save(self, path: str | Path) -> None:
        with open(path, "wb") as f:
            pickle.dump({
                "chunks": self.chunks,
                "embeddings": self.embeddings,
                "bm25": self.bm25,
                "chunk_tokens": self._chunk_tokens,
                "url_text": self._url_text,
            }, f)

    @classmethod
    def load(cls, path: str | Path) -> "DocumentIndex":
        with open(path, "rb") as f:
            data = pickle.load(f)
        self = cls()
        self.chunks = data["chunks"]
        self.embeddings = data["embeddings"]
        self.bm25 = data["bm25"]
        self._chunk_tokens = data["chunk_tokens"]
        self._url_text = data.get("url_text", {})
        return self


# ---------- MCP server ----------

_INDEX_CACHE: dict[str, DocumentIndex] = {}


def _get_index(path: str) -> DocumentIndex:
    key = str(Path(path).resolve())
    if key not in _INDEX_CACHE:
        _INDEX_CACHE[key] = DocumentIndex.from_path(key)
    return _INDEX_CACHE[key]


def _result_to_dict(r: SearchResult) -> dict:
    return {
        "file_path": r.chunk.file_path,
        "start_line": r.chunk.start_line,
        "end_line": r.chunk.end_line,
        "heading": r.chunk.heading,
        "content": r.chunk.content,
        "score": r.score,
        "rank": r.rank,
    }


def run_mcp(path: Optional[str] = None) -> None:
    try:
        from fastmcp import FastMCP
    except ImportError:
        print("fastmcp is not installed. Run: pip install fastmcp", file=sys.stderr)
        sys.exit(1)

    mcp = FastMCP("searcher")
    # Optionally pre-warm an initial index for faster first query.
    if path:
        _get_index(path)

    @mcp.tool
    def search(path: str, query: str, top_k: int = 5, context_lines: int = 20) -> list[dict]:
        """Hybrid semantic+BM25 search over documents at `path`.

        Each result is padded with `context_lines` neighboring lines so the
        returned chunk includes surrounding context from its source file.
        """
        idx = _get_index(path)
        return [
            _result_to_dict(r)
            for r in idx.search(query, top_k=top_k, context_lines=context_lines)
        ]

    @mcp.tool
    def find_related(path: str, file_path: str, start_line: int, top_k: int = 3) -> list[dict]:
        """Find chunks similar to the one at (file_path, start_line)."""
        idx = _get_index(path)
        target = next(
            (c for c in idx.chunks if c.file_path == file_path and c.start_line == start_line),
            None,
        )
        if target is None:
            return []
        seed = SearchResult(chunk=target, score=0.0, rank=0)
        return [_result_to_dict(r) for r in idx.find_related(seed, top_k=top_k)]

    @mcp.tool
    def get_content(path: str, file_path: str, start_line: int, end_line: int) -> dict:
        """Fetch the raw content of `file_path` between lines `start_line` and
        `end_line` (1-indexed, inclusive). `file_path` must be a file that was
        indexed under `path`. Use this to retrieve the full content of a
        chunk surfaced by `search`, beyond the `context_lines` window."""
        idx = _get_index(path)
        content = idx.get_content(file_path, start_line, end_line)
        return {
            "file_path": file_path,
            "start_line": start_line,
            "end_line": end_line,
            "content": content,
        }

    mcp.run(transport="stdio")


# ---------- CLI ----------

def _print_results(results: list[SearchResult]) -> None:
    for r in results:
        c = r.chunk
        preview = re.sub(r"\s+", " ", c.content).strip()[:300]
        heading = c.heading or "-"
        print(f"\n[{r.rank}] score={r.score:.4f}  {c.file_path}:{c.start_line}-{c.end_line}")
        print(f"    heading: {heading}")
        print(f"    {preview}")


def main(argv: list[str]) -> int:
    # MCP launcher mode (used by mcporter): `python server.py`
    if len(argv) == 1:
        run_mcp()
        return 0

    if len(argv) < 3:
        print('Usage: python docindex.py <path> "<query>" [--top-k N] [--context-lines N]', file=sys.stderr)
        print("       python docindex.py <path> --mcp", file=sys.stderr)
        print("       python docindex.py <path> --get <file_path> <start_line> <end_line>", file=sys.stderr)
        return 2

    path, second = argv[1], argv[2]
    if second == "--mcp":
        run_mcp(path)
        return 0

    if second == "--get":
        if len(argv) < 6:
            print("Usage: python docindex.py <path> --get <file_path> <start_line> <end_line>", file=sys.stderr)
            return 2
        target_file, start_s, end_s = argv[3], argv[4], argv[5]
        try:
            start_line, end_line = int(start_s), int(end_s)
        except ValueError:
            print("start_line and end_line must be integers", file=sys.stderr)
            return 2
        text = _fetch_url(target_file) if _is_url(target_file) else _read_file(Path(target_file))
        if not text:
            print(f"Could not read: {target_file}", file=sys.stderr)
            return 1
        lines = text.splitlines()
        s = max(1, start_line)
        e = min(len(lines), end_line)
        if s > e:
            return 0
        print(f"{target_file}:{s}-{e}")
        print("\n".join(lines[s - 1:e]))
        return 0

    # Parse optional flags from remaining args
    top_k = 5
    context_lines = 20
    rest = argv[3:]
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg in ("--top-k", "-k") and i + 1 < len(rest):
            top_k = int(rest[i + 1])
            i += 2
        elif arg in ("--context-lines", "-c") and i + 1 < len(rest):
            context_lines = int(rest[i + 1])
            i += 2
        else:
            print(f"Unknown argument: {arg}", file=sys.stderr)
            return 2

    query = second
    t0 = time.perf_counter()
    idx = DocumentIndex.from_path(path)
    t1 = time.perf_counter()
    results = idx.search(query, top_k=top_k, context_lines=context_lines)
    t2 = time.perf_counter()

    print(f"Indexed {len(idx.chunks)} chunks in {t1 - t0:.2f}s")
    print(f"Query '{query}' in {(t2 - t1) * 1000:.1f}ms (top_k={top_k}, context_lines={context_lines})")
    _print_results(results)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
