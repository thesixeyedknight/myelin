"""Local RAG (Retrieval-Augmented Generation) using ChromaDB."""
from __future__ import annotations
import chromadb
from chromadb.config import Settings as ChromaSettings
from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib
import json

from src.configs.settings import SETTINGS
from src.utils.logging import LOGGER


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    
    return chunks


class RAGManager:
    """Manages the local knowledge base using ChromaDB."""
    
    def __init__(self, persist_directory: str = "work/chroma_db"):
        """Initialize ChromaDB client."""
        self.persist_dir = Path(persist_directory)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=SETTINGS.rag_collection_name,
            metadata={"description": "Myelin research knowledge base"}
        )
        
        LOGGER.log(event="rag_init", collection=SETTINGS.rag_collection_name)
    
    def index_document(
        self, 
        text: str, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Index a document by chunking and adding to vector store.
        
        Args:
            text: Document text content
            metadata: Metadata dict (must include 'source' field)
        
        Returns:
            Status dict with chunk count and IDs
        """
        if not text or not text.strip():
            return {"error": "Cannot index empty document"}
        
        if "source" not in metadata:
            return {"error": "Metadata must include 'source' field"}
        
        # Chunk the document
        chunks = chunk_text(
            text, 
            chunk_size=SETTINGS.rag_chunk_size,
            overlap=SETTINGS.rag_chunk_overlap
        )
        
        # Generate unique IDs for each chunk
        source_hash = hashlib.md5(metadata["source"].encode()).hexdigest()[:8]
        chunk_ids = [f"{source_hash}_chunk_{i}" for i in range(len(chunks))]
        
        # Add chunk index to metadata
        chunk_metadata = []
        for i, chunk in enumerate(chunks):
            meta = metadata.copy()
            meta["chunk_index"] = i
            meta["total_chunks"] = len(chunks)
            chunk_metadata.append(meta)
        
        try:
            self.collection.add(
                documents=chunks,
                metadatas=chunk_metadata,
                ids=chunk_ids
            )
            
            LOGGER.log(
                event="rag_index_success",
                source=metadata["source"],
                chunks=len(chunks)
            )
            
            return {
                "status": "success",
                "source": metadata["source"],
                "chunks_indexed": len(chunks),
                "chunk_ids": chunk_ids
            }
        except Exception as e:
            LOGGER.log(event="rag_index_error", error=str(e))
            return {"error": f"Failed to index document: {str(e)}"}
    
    def query(
        self, 
        question: str, 
        k: int = 5
    ) -> Dict[str, Any]:
        """
        Query the knowledge base.
        
        Args:
            question: Query string
            k: Number of results to return
        
        Returns:
            Dict with chunks, metadata, and relevance scores
        """
        if not question or not question.strip():
            return {"error": "Query cannot be empty"}
        
        try:
            results = self.collection.query(
                query_texts=[question],
                n_results=k
            )
            
            # Extract results
            chunks = results["documents"][0] if results["documents"] else []
            metadatas = results["metadatas"][0] if results["metadatas"] else []
            distances = results["distances"][0] if results["distances"] else []
            ids = results["ids"][0] if results["ids"] else []
            
            # Convert distances to similarity scores (1 - normalized distance)
            # ChromaDB uses L2 distance, lower is better
            max_dist = max(distances) if distances else 1.0
            similarities = [1.0 - (d / max_dist) for d in distances] if max_dist > 0 else [1.0] * len(distances)
            
            # Filter by relevance threshold
            relevant_results = []
            for i, (chunk, meta, sim, chunk_id) in enumerate(zip(chunks, metadatas, similarities, ids)):
                if sim >= SETTINGS.rag_relevance_threshold:
                    relevant_results.append({
                        "chunk_id": chunk_id,
                        "text": chunk,
                        "metadata": meta,
                        "relevance_score": round(sim, 3)
                    })
            
            # Warn if no relevant results
            warning = None
            if not relevant_results:
                warning = f"No relevant information found (all scores < {SETTINGS.rag_relevance_threshold})"
                LOGGER.log(event="rag_query_no_results", question=question)
            
            LOGGER.log(
                event="rag_query_success",
                question=question,
                results_count=len(relevant_results)
            )
            
            response = {
                "question": question,
                "results": relevant_results,
                "total_results": len(relevant_results)
            }
            
            if warning:
                response["warning"] = warning
            
            return response
            
        except Exception as e:
            LOGGER.log(event="rag_query_error", error=str(e))
            return {"error": f"Query failed: {str(e)}"}
    
    def list_documents(self) -> Dict[str, Any]:
        """List all indexed documents."""
        try:
            data = self.collection.get()
            metadatas = data.get("metadatas", [])
            
            # Group by source
            sources = {}
            for meta in metadatas:
                source = meta.get("source", "unknown")
                if source not in sources:
                    sources[source] = {
                        "source": source,
                        "chunks": 0,
                        "metadata": meta
                    }
                sources[source]["chunks"] += 1
            
            return {
                "total_documents": len(sources),
                "total_chunks": len(metadatas),
                "documents": list(sources.values())
            }
        except Exception as e:
            return {"error": f"Failed to list documents: {str(e)}"}
    
    def clear(self) -> Dict[str, Any]:
        """Clear the entire collection (for testing)."""
        try:
            self.client.delete_collection(SETTINGS.rag_collection_name)
            self.collection = self.client.create_collection(
                name=SETTINGS.rag_collection_name,
                metadata={"description": "Myelin research knowledge base"}
            )
            LOGGER.log(event="rag_clear")
            return {"status": "Collection cleared"}
        except Exception as e:
            return {"error": f"Failed to clear collection: {str(e)}"}


# Lazy initialization to avoid import-time side effects
_rag_manager_instance = None


def get_rag_manager() -> Optional[RAGManager]:
    """
    Get or create the global RAG manager instance (lazy initialization).
    
    Returns:
        RAGManager instance if RAG is enabled, None otherwise
    """
    global _rag_manager_instance
    
    if not SETTINGS.rag_enabled:
        return None
    
    if _rag_manager_instance is None:
        _rag_manager_instance = RAGManager()
    
    return _rag_manager_instance


# Backward compatibility alias (deprecated, use get_rag_manager() instead)
def _get_rag_manager_legacy():
    """Legacy accessor for backward compatibility. Use get_rag_manager() instead."""
    return get_rag_manager()


RAG_MANAGER = None  # Deprecated: use get_rag_manager() instead
