# Myelin — AI Research Automation Agent

An agentic runner for bioinformatics and literature research. It plans a
sequence of steps with an LLM (Gemini), calls domain tools (PubMed, GEO,
BLAST, RCSB/UniProt, differential expression, WGCNA, pathway enrichment,
PPI networks, a local RAG knowledge base, ...), and executes small Python
snippets in a resource-limited sandbox. Human approval between steps is
required by default (`--auto-approve` to skip it).

## Status

Verified working end-to-end (this session, real Gemini + NCBI calls):

* **CLI pipeline** (`python -m src.main "<goal>"`): plan → tool calls →
  sandboxed code → LLM summary, with structured JSONL logging to
  `logs/run.jsonl`. Tried both a trivial shell goal and a full PubMed
  search → fetch → summarize goal; both ran cleanly with correct citations.
* **Tool suite**, all registered and dispatchable: `PubMedSearch`,
  `PubMedFetch`, `GEO_DOWNLOAD`, `DIFF_EXPRESSION`, `WGCNA_ANALYSIS`,
  `PATHWAY_ENRICHMENT`, `PPI_NETWORK`, `BlastSubmit`/`BlastPoll`,
  `RCSBFindByGene`, `UniProtSearch`, `ReadFile`/`WriteFile`, `SafeShell`,
  `WebSearch`, plus RAG tools `IndexDocument`/`QueryKnowledge`/`ListIndexedDocuments`.
* **Bioinformatics correctness fixes** (GEO sample-group labeling,
  log2FC double-transform, WGCNA distance matrix) landed and re-verified
  against cached GSE65391/WGCNA output — sample counts and module sizes
  now look sane.
* **Sandbox**: CPU/memory/time-limited Python execution for `{CODE:}`
  steps; network access disabled by policy inside generated code.
* **RAG**: local Chroma-backed indexing/query, including an adversarial
  test that confirms it doesn't hallucinate answers for off-topic queries.
* **Usage auditing / tiered rate limiting**: requests are tracked per day
  across `pro`/`flash`/`lite` Gemini tiers (`work/usage.json`,
  `work/api_usage_audit.csv`); `scripts/usage_report.py` prints a summary.
* **Test suite**: `pytest tests/` → 23 passed (unit + mocked integration +
  sandbox + RAG + variable substitution/passing).

### Known limitations

* **Hierarchical multi-agent mode** (`HierarchicalOrchestrator`: Director →
  Reviewer → Worker → Writer) decomposes goals fine on the `lite` tier, but
  the Reviewer and Writer steps require the `pro` tier
  (`gemini-2.5-pro`), and the current API key's free tier allows **zero**
  daily `pro` requests (Google returns `429 RESOURCE_EXHAUSTED, limit: 0`).
  This isn't a code bug — the local usage tracker just can't see that the
  server-side free tier has no `pro` quota at all — but it means the
  hierarchical/review/writer path can't complete until the key has paid
  `pro` access, or those steps are pointed at `flash`.
* **Docker workflow** (`Dockerfile`/`docker-compose.yml`) is present but
  wasn't verified this session (no Docker permissions in this environment).
  The primary, verified way to run the project is directly inside the
  `myelin` conda env (see Quickstart).
* A stray, unused module (`src/agent/writer_agent.py`) references
  provider/backend settings not wired into the active pipeline — dead code,
  safe to ignore.

## Quickstart

```bash
# 1. Configure secrets
cp .env.example .env
# edit .env: GEMINI_API_KEY, NCBI_EMAIL (and optionally NCBI_API_KEY)

# 2. Use the myelin conda env (has all deps already installed)
conda activate myelin   # env at /home/sarthak/miniconda3/envs/myelin

# 3. Run
python -m src.main "Search PubMed for 'CRISPR off-target' and summarize findings" --auto-approve
```

Useful flags: `--auto-approve` (skip per-step confirmation),
`--verbose` (DEBUG logging), `--save-llm` (dump raw prompts/responses to
`logs/llm/`).

## Configuration

Settings load from environment variables (`.env`) with `config.yaml` as a
fallback — see `src/configs/settings.py` for the full list, including
per-tier model names/quotas (`MODEL_PRO`/`QUOTA_PRO`, etc.), sandbox limits
(`MAX_WORKER_SECONDS`, `MAX_WORKER_MEMORY_MB`), and RAG tuning
(`RAG_CHUNK_SIZE`, `RAG_RELEVANCE_THRESHOLD`, ...).

## Testing

```bash
python -m pytest tests/ -q
```

Most tests mock the LLM/network. A few are opt-in and marked accordingly:
`@pytest.mark.network` (real PubMed calls) and `@pytest.mark.integration`
(real Gemini calls, skipped automatically if no API key is set).

## Coming soon

* Quota-aware tier fallback for the Reviewer/Writer steps (so hierarchical
  mode degrades to `flash` instead of failing when `pro` is unavailable).
* Verified Docker build/run path.
* Broader bioinformatics tool coverage.
