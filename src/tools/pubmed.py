from __future__ import annotations
import time
import requests
from typing import List, Dict
from tenacity import retry, wait_exponential_jitter, stop_after_attempt
from src.tools.registry import tool
from src.configs.settings import SETTINGS

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@retry(wait=wait_exponential_jitter(initial=1, max=30), stop=stop_after_attempt(5))
def _get(url, params):
    params = {**params, "email": SETTINGS.ncbi_email}
    if SETTINGS.ncbi_api_key:
        params["api_key"] = SETTINGS.ncbi_api_key
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(0.34)  # ~3 req/s etiquette when unauthenticated
    ct = r.headers.get("Content-Type", "")
    if ct.startswith("application/json"):
        return r.json()
    return r.text


@tool("PubMedSearch")
def pubmed_search(query: str, retmax: int = 20, mindate: str | None = None, maxdate: str | None = None) -> Dict:
    params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": retmax}
    if mindate or maxdate:
        params.update({"mindate": mindate or "1900", "maxdate": maxdate or "3000", "datetype": "pdat"})
    data = _get(f"{BASE}/esearch.fcgi", params)
    ids = data["esearchresult"].get("idlist", [])
    return {"pmids": ids}


@tool("PubMedFetch")
def pubmed_fetch(pmids: List[str]) -> Dict:
    if not pmids:
        return {"articles": []}
    ids = ",".join(pmids)
    data = _get(f"{BASE}/esummary.fcgi", {"db": "pubmed", "id": ids, "retmode": "json"})
    result = data.get("result", {})
    articles = []
    for pid in pmids:
        it = result.get(pid)
        if not it:
            continue
        articles.append(
            {
                "pmid": pid,
                "title": it.get("title"),
                "authors": [a.get("name") for a in it.get("authors", [])],
                "pubdate": it.get("pubdate"),
                "journal": it.get("fulljournalname"),
            }
        )
    return {"articles": articles}
