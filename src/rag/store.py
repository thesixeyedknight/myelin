from __future__ import annotations
from dataclasses import dataclass
from typing import List
from rapidfuzz import process, fuzz


@dataclass
class Doc:
    doc_id: str
    text: str
    meta: dict


class TinyStore:
    def __init__(self):
        self.docs: List[Doc] = []

    def add(self, doc: Doc):
        self.docs.append(doc)

    def search(self, query: str, k: int = 5):
        choices = {d.doc_id: d.text for d in self.docs}
        hits = process.extract(query, choices, scorer=fuzz.WRatio, limit=k)
        out = []
        for doc_id, score, _ in hits:
            d = next(x for x in self.docs if x.doc_id == doc_id)
            out.append({"doc_id": doc_id, "score": score, "meta": d.meta})
        return out
