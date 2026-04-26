from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np


class EmbeddingsStore:
    def __init__(self, path: str):
        self.path = path
        self.records: List[dict] = []
        self.matrix: np.ndarray | None = None
        self._load(path)

    def _load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        if not isinstance(payload, list):
            raise ValueError("Embeddings file must contain a JSON array of records")

        self.records = payload
        vectors = [r.get("embedding") for r in self.records]
        if not vectors:
            self.matrix = np.empty((0, 0), dtype=np.float32)
            return

        self.matrix = np.array(vectors, dtype=np.float32)
        if self.matrix.ndim != 2:
            raise ValueError("Embeddings array must be 2-dimensional")

        # Pre-normalize to make cosine similarity a matrix multiply.
        norms = np.linalg.norm(self.matrix, axis=1, keepdims=True)
        self.matrix = self.matrix / np.clip(norms, 1e-10, None)

    def search(self, query_vector: List[float], limit: int) -> List[dict]:
        if self.matrix is None or self.matrix.size == 0:
            return []

        q = np.array(query_vector, dtype=np.float32)
        if q.ndim != 1:
            raise ValueError("Query embedding must be a 1D vector")
        if q.shape[0] != self.matrix.shape[1]:
            raise ValueError(
                f"Embedding dimension mismatch: query={q.shape[0]} store={self.matrix.shape[1]}"
            )

        q = q / np.clip(np.linalg.norm(q), 1e-10, None)
        scores = self.matrix @ q
        top_indices = np.argsort(scores)[::-1][:limit]

        results: List[dict] = []
        for i in top_indices:
            record = self.records[int(i)].copy()
            record["score"] = float(scores[int(i)])
            record.pop("embedding", None)
            results.append(record)
        return results


_store_cache: Dict[str, EmbeddingsStore] = {}


def get_store(embeddings_path: str) -> EmbeddingsStore:
    resolved = str(Path(embeddings_path).expanduser().resolve())
    if resolved not in _store_cache:
        _store_cache[resolved] = EmbeddingsStore(resolved)
    return _store_cache[resolved]
