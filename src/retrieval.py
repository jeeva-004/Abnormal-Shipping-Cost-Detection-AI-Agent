"""Stage 3b: vector retrieval of candidate notes (Chroma + local embeddings)."""
import uuid
from datetime import date
from typing import Callable

import chromadb

from src import config


class NoteIndex:
    def __init__(self, notes: list, embed_fn: Callable):
        self.embed_fn = embed_fn
        self.col = chromadb.EphemeralClient().create_collection(
            name=f"notes_{uuid.uuid4().hex}", metadata={"hnsw:space": "cosine"})
        self.col.add(
            ids=[n.note_id for n in notes],
            embeddings=embed_fn([f"{n.applies_to}: {n.text}" for n in notes]),
            metadatas=[{"scope": n.applies_to, "start_ord": n.eff_start.toordinal(),
                        "end_ord": n.eff_end.toordinal()} for n in notes],
        )

    def search(self, route: str, week_start: date, week_end: date,
               k: int = config.RETRIEVAL_K) -> list:
        """Notes for this route (or All Routes) whose window overlaps the week.

        Returns [(note_id, similarity)] sorted by similarity, ties broken by note_id.
        """
        query = self.embed_fn([f"Freight cost increase on {route} route, week of {week_start}"])[0]
        where = {"$and": [{"scope": {"$in": [route, config.ALL_ROUTES]}},
                          {"start_ord": {"$lte": week_end.toordinal()}},
                          {"end_ord": {"$gte": week_start.toordinal()}}]}
        res = self.col.query(query_embeddings=[query], n_results=k, where=where)
        hits = [(i, round(1 - d, 6)) for i, d in zip(res["ids"][0], res["distances"][0])]
        return sorted(hits, key=lambda h: (-h[1], h[0]))