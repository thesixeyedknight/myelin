from __future__ import annotations
import time
import requests
import xml.etree.ElementTree as ET
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
    # Use efetch to get full records including abstracts
    text = _get(f"{BASE}/efetch.fcgi", {"db": "pubmed", "id": ids, "retmode": "xml"})
    
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {"articles": [], "error": "Failed to parse PubMed XML"}

    articles = []
    for article in root.findall(".//PubmedArticle"):
        medline = article.find("MedlineCitation")
        if medline is None:
            continue
            
        pmid = medline.findtext("PMID")
        article_data = medline.find("Article")
        
        title = article_data.findtext("ArticleTitle")
        
        abstract_elem = article_data.find("Abstract")
        abstract = ""
        if abstract_elem is not None:
            abstract_texts = abstract_elem.findall("AbstractText")
            abstract = " ".join(t.text for t in abstract_texts if t.text)
            
        authors = []
        author_list = article_data.find("AuthorList")
        if author_list is not None:
            for au in author_list.findall("Author"):
                last = au.findtext("LastName")
                initials = au.findtext("Initials")
                if last and initials:
                    authors.append(f"{last} {initials}")
                elif last:
                    authors.append(last)
                    
        journal = article_data.find("Journal/Title")
        journal_title = journal.text if journal is not None else ""
        
        pubdate = article_data.find("Journal/JournalIssue/PubDate")
        year = pubdate.findtext("Year") if pubdate is not None else ""

        articles.append(
            {
                "pmid": pmid,
                "title": title,
                "authors": authors,
                "pubdate": year,
                "journal": journal_title,
                "abstract": abstract
            }
        )
    return {"articles": articles}
