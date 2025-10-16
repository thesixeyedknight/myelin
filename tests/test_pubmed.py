from src.tools.pubmed import pubmed_search

def test_pubmed_search_smoke():
    out = pubmed_search("CRISPR", retmax=2)
    assert "pmids" in out