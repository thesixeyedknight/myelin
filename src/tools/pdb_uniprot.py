from __future__ import annotations
import requests
from src.tools.registry import tool

RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
UNIPROT_API = "https://rest.uniprot.org/uniprotkb/search"


@tool("RCSBFindByGene")
def rcsb_find_by_gene(gene: str, organism: str = "Homo sapiens", rows: int = 10, experimental_only: bool = False) -> dict:
    request_options = {"paginate": {"rows": rows, "start": 0}}
    if experimental_only:
        request_options["results_content_type"] = ["experimental"]
    
    query = {
        "query": {
            "type": "group",
            "logical_operator": "and",
            "nodes": [
                {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_entity_source_organism.taxonomy_lineage.name", "operator": "exact_match", "value": organism}},
                {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_polymer_entity_annotation.type", "operator": "exact_match", "value": "Gene Name"}},
                {"type": "terminal", "service": "text", "parameters": {"attribute": "rcsb_polymer_entity_annotation.annotation_value", "operator": "exact_match", "value": gene}},
            ],
        },
        "return_type": "entry",
        "request_options": {"results_content_type": ["experimental"], "paginate": {"rows": rows, "start": 0}},
    }
    r = requests.post(RCSB_SEARCH, json=query, timeout=30)
    r.raise_for_status()
    data = r.json()
    ids = [it["identifier"] for it in data.get("result_set", [])]
    return {"pdb_ids": ids}


@tool("UniProtSearch")
def uniprot_search(query: str, size: int = 10) -> dict:
    params = {"query": query, "format": "json", "size": size, "fields": "accession,id,protein_name,organism_name"}
    r = requests.get(UNIPROT_API, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    results = [{"accession": x.get("primaryAccession"), "id": x.get("uniProtkbId"), "organism": x.get("organism", {}).get("scientificName")} for x in data.get("results", [])]
    return {"results": results}
