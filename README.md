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
  against cached GSE65391/WGCNA output.
* **Sandbox**: CPU/memory/time-limited Python execution for `{CODE:}`
  steps; network access disabled by policy inside generated code.
* **RAG**: local Chroma-backed indexing/query, including an adversarial
  test that confirms it doesn't hallucinate answers for off-topic queries.
* **Usage auditing / tiered rate limiting**: requests are tracked per day
  across `pro`/`flash`/`lite` Gemini tiers (`work/usage.json`,
  `work/api_usage_audit.csv`); `scripts/usage_report.py` prints a summary.
* **Test suite**: `pytest tests/` → 23 passed (unit + mocked integration +
  sandbox + RAG + variable substitution/passing).
* **Hierarchical multi-agent mode** (`HierarchicalOrchestrator`: Director →
  Reviewer → Worker → Writer): full real run verified end-to-end
  (`tests/test_hierarchical.py`, ~8.5 min, real Gemini + PubMed calls) —
  Director decomposed the goal, Reviewer rejected an under-specified first
  draft with concrete feedback then approved the revision, all 7 worker
  subtasks executed, and the Writer produced a complete 15KB Markdown
  report (`work/report.md`). `gemini-2.5-pro` has been removed from the
  free tier (confirmed via `429 RESOURCE_EXHAUSTED, limit: 0`); the `pro`
  tier slot now points at `gemini-3.5-flash` (`MODEL_PRO` in
  `src/configs/settings.py`), which ran with zero errors.

## Setup

Requires Python 3.11+ and a [Gemini API key](https://aistudio.google.com/apikey).

```bash
# 1. Clone and enter the repo
git clone git@github.com:thesixeyedknight/myelin.git && cd myelin

# 2. Create and activate an environment, then install dependencies
conda create -n myelin python=3.11 -y
conda activate myelin
pip install -r requirements.txt

# (no conda? use a venv instead of steps 2-3 above)
# python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env
# edit .env: GEMINI_API_KEY, NCBI_EMAIL (and optionally NCBI_API_KEY)

# 4. Run
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

### LLM provider: Gemini or Ollama

`LLM_PROVIDER` selects the backend (`gemini`, the default, or `ollama`):

```bash
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434      # default
OLLAMA_MODEL_PRO=llama3                 # heavy reasoning: Reviewer, Writer
OLLAMA_MODEL_FLASH=llama3               # default: planner, summarizer
OLLAMA_MODEL_LITE=llama3                # cheap/high-volume: Director decompose
OLLAMA_EMBED_MODEL=nomic-embed-text     # RAG indexing/query (pull it: `ollama pull nomic-embed-text`)
```

Unlike Gemini's `pro`/`flash`/`lite` tiers — which cascade to a lower tier when
a daily quota (`QUOTA_PRO`, etc.) is exhausted, because those quotas exist to
ration a rate-limited cloud API — Ollama has no call limits, so there's
nothing to ration: each tier just runs whichever local model you point it at,
with no quota tracking or auto-fallback. Point all three `OLLAMA_MODEL_*`
vars at the same model if you don't want per-role differentiation. When
`LLM_PROVIDER=ollama`, RAG embeddings also switch to `OLLAMA_EMBED_MODEL`
instead of Gemini's `text-embedding-004`, so an Ollama-only setup needs no
`GEMINI_API_KEY` at all.

## Testing

```bash
python -m pytest tests/ -q
```

Most tests mock the LLM/network. A few are opt-in and marked accordingly:
`@pytest.mark.network` (real PubMed calls) and `@pytest.mark.integration`
(real Gemini calls, skipped automatically if no API key is set).

## Example test cases

`scripts/verify.py` runs a small matrix of real end-to-end goals against a
live Gemini key and checks that the expected tools got called:

```bash
python scripts/verify.py          # run the whole matrix
python scripts/verify.py UC3_L2   # run a single case by id
```

**Good performance** — `UC3_L2` ("Data QC - Complex") asks the agent to
scan `data/*.log` for an `Error rate: X%` line and flag files where
`X > 1.0`. The fixtures make the expected answer unambiguous:

| File | Contents | Expected result |
| --- | --- | --- |
| `data/good.log` | `Error rate: 0.5%` | not flagged (below threshold) |
| `data/bad.log` | `Error rate: 2.5%` | flagged (above threshold) |

A correct run prints exactly `data/bad.log` and nothing else — the agent
writes a `{CODE:}` step that parses both files and applies the threshold,
rather than guessing from the filenames.

**Correct handling of bad input** — `tests/test_rag_adversarial.py`
indexes a CRISPR research document, then asks an off-topic question
("What does the document say about quantum computing?"):

```bash
python -m pytest tests/test_rag_adversarial.py -v
```

Good performance here means `query_knowledge` returns a `warning` and no
fabricated answer, instead of hallucinating a response from unrelated
chunks — this is the case the test asserts on.

**Known failure mode** — the `pro` tier has no automatic fallback yet
(see [Coming soon](#coming-soon)). If the configured `pro` model is
exhausted or deprecated, calls fail hard instead of retrying on `flash`:

```
429 RESOURCE_EXHAUSTED, limit: 0
```

This was hit for real when `gemini-2.5-pro` was pulled from the free tier;
the workaround today is to repoint `MODEL_PRO` in
`src/configs/settings.py` at a live model, not to rely on the agent to
degrade gracefully.

## Coming soon

* Verified Docker build/run path.
* Broader bioinformatics tool coverage.
* Quota-aware tier fallback in general (today, if a configured tier model
  is fully exhausted or removed from the free tier, calls fail rather than
  cascading to another tier automatically).
