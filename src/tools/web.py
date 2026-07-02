from __future__ import annotations
from duckduckgo_search import DDGS
from src.tools.registry import tool

@tool("WebSearch")
def web_search(query: str, max_results: int = 5) -> dict:
    """
    Search the web using DuckDuckGo.
    """
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return {"results": results}
