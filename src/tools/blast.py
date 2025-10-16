from __future__ import annotations
import time
import requests
from src.tools.registry import tool

NCBI_BLAST = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"


@tool("BlastSubmit")
def blast_submit(program: str, database: str, sequence: str) -> dict:
    # Minimal illustration; for production use, handle FASTA & params properly
    params = {"CMD": "Put", "PROGRAM": program, "DATABASE": database, "QUERY": sequence}
    r = requests.post(NCBI_BLAST, data=params, timeout=60)
    r.raise_for_status()
    rid = None
    for line in r.text.splitlines():
        if line.strip().startswith("RID ="):
            rid = line.split("=")[-1].strip()
    if not rid:
        raise RuntimeError("Failed to obtain RID")
    return {"rid": rid}


@tool("BlastPoll")
def blast_poll(rid: str, wait_s: int = 15) -> dict:
    time.sleep(wait_s)
    params = {"CMD": "Get", "RID": rid, "FORMAT_TYPE": "JSON2_S"}
    r = requests.get(NCBI_BLAST, params=params, timeout=60)
    r.raise_for_status()
    if "Status=WAITING" in r.text:
        return {"status": "WAITING"}
    return {"status": "READY", "raw": r.text}
