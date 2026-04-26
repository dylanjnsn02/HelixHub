from __future__ import annotations

import os
from typing import List

import httpx


async def embed_query(text: str) -> List[float]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required in environment")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"input": text, "model": "text-embedding-3-small"},
        )
        response.raise_for_status()
        payload = response.json()
        return payload["data"][0]["embedding"]
