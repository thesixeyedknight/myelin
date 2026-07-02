"""Tools for RAG (local knowledge base) operations."""
from src.tools.registry import tool
from src.tools.parsers.file_parsers import parse_file
from src.agent.rag import get_rag_manager


@tool("IndexDocument")
def index_document(filepath: str) -> dict:
    """
    Index a document into the local knowledge base.
    
    Args:
        filepath: Path to document file (supports: .txt, .md, .json, .csv, .fasta, .pdb)
    
    Returns:
        Status dict with chunk count or error message
    """
    rag_manager = get_rag_manager()
    if not rag_manager:
        return {"error": "RAG is disabled. Enable in config."}
    
    # Parse file
    result = parse_file(filepath)
    if "error" in result:
        return result
    
    # Index document
    return rag_manager.index_document(
        text=result["text"],
        metadata=result["metadata"]
    )


@tool("QueryKnowledge")
def query_knowledge(question: str, k: int = 5) -> dict:
    """
    Query the local knowledge base for relevant information.
    
    Args:
        question: Research question
        k: Number of results to return (default: 5)
    
    Returns:
        Dict with relevant chunks, citations, and relevance scores
    """
    rag_manager = get_rag_manager()
    if not rag_manager:
        return {"error": "RAG is disabled. Enable in config."}
    
    if not question:
        return {"error": "Question cannot be empty. Please provide a specific query."}
    
    if len(question) < 5:
        return {"error": "Query too vague. Please be more specific (at least 5 characters)."}
    
    return rag_manager.query(question, k=k)


@tool("ListIndexedDocuments")
def list_indexed_documents() -> dict:
    """
    List all documents currently in the knowledge base.
    
    Returns:
        Dict with document list and statistics
    """
    rag_manager = get_rag_manager()
    if not rag_manager:
        return {"error": "RAG is disabled. Enable in config."}
    
    return rag_manager.list_documents()
