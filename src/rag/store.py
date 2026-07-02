from __future__ import annotations
from dataclasses import dataclass
from typing import List
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from src.agent.llm import LLMClient

@dataclass
class Doc:
    doc_id: str
    text: str
    meta: dict


class GeminiEmbeddingFunction(EmbeddingFunction):
    def __init__(self):
        self.client = LLMClient()

    def __call__(self, input: Documents) -> Embeddings:
        # Naive loop, can be optimized if API supports batch
        return [self.client.embed(text) for text in input]


class TinyStore:
    def __init__(self):
        # Ephemeral client
        self.client = chromadb.Client()
        self.collection = self.client.create_collection(
            name="myelin_rag",
            embedding_function=GeminiEmbeddingFunction()
        )

    def add(self, doc: Doc):
        self.collection.add(
            documents=[doc.text],
            metadatas=[doc.meta] if doc.meta else None,
            ids=[doc.doc_id]
        )

    def search(self, query: str, k: int = 5):
        # Handle empty collection
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(k, self.collection.count())
        )
        
        out = []
        if not results["ids"]:
            return []
            
        ids = results["ids"][0]
        # Chroma returns distance (L2 by default?), we want similarity.
        # But for now just returning raw distance/score is fine or we can invert it.
        distances = results["distances"][0] if results["distances"] else [0.0]*len(ids)
        metas = results["metadatas"][0]
        
        for i, doc_id in enumerate(ids):
            out.append({
                "doc_id": doc_id,
                "score": distances[i], 
                "meta": metas[i]
            })
        return out
