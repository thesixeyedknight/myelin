# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Myelin is an agentic runner for bioinformatics/literature research. An LLM (Gemini)
plans a sequence of steps, the orchestrator dispatches domain tools (PubMed, GEO,
BLAST, RCSB/UniProt, differential expression, WGCNA, pathway enrichment, PPI
networks, a local RAG store) and runs small Python snippets in a sandboxed
subprocess. Human approval between steps is required by default.

## Setup & running

```bash
conda create -n myelin python=3.11 -y && conda activate myelin
pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY, NCBI_EMAIL, (optional) NCBI_API_KEY

python -m src.main "Search PubMed for 'CRISPR off-target' and summarize findings" --auto-approve
```

Useful flags: `--auto-approve` (skip per-step confirmation), `--verbose` (DEBUG
logging), `--save-llm` (dump raw prompts/responses to `logs/llm/`).

Note: `ai_agent_context/rules.md` (one level up) states Python 3.12 as a strict
requirement and `pyprojects.toml` as the dependency source of truth, but
`pyprojects.toml` is currently empty — `requirements.txt` is what actually pins
dependencies, and the README's Python 3.11+ / conda flow is what's verified to
work.

## Testing

```bash
python -m pytest tests/ -q                    # full suite
python -m pytest tests/test_sandbox.py -v      # single file
python -m pytest tests/test_pubmed.py::test_name -v   # single test

python scripts/verify.py          # real end-to-end goals against a live Gemini key
python scripts/verify.py UC3_L2   # run a single use case by id
```

Most tests mock the LLM/network. Two markers gate real calls and are defined in
`pytest.ini`: `@pytest.mark.network` (real PubMed calls) and
`@pytest.mark.integration` (real Gemini calls — skipped automatically if no API
key is set).

## Architecture

**Flow:** `src/main.py` → `Orchestrator.run(goal)` (`src/agent/orchestrator.py`):
1. `plan()` sends the goal + tool list (`src/tools/registry.py: list_tools()`) to
   the LLM via `prompts/plan_system.md` / `plan_user.md`, gets back JSON, and
   validates/normalizes it into a `Plan` (`src/utils/schema.py`). Planner output
   is rejected loudly (not silently patched) if it uses placeholder args, calls
   tools from inside `{CODE:}`, or otherwise breaks the plan grammar.
2. Each step is one of three kinds, encoded as a canonical string:
   - `{TOOL:Name(k=v,...)}` — dispatched through `src/tools/registry.py`. Tools
     are registered via the `@tool("Name")` decorator; each module in
     `src/tools/*.py` registers itself on import.
   - `{CODE:...}` — arbitrary Python run through `src/sandbox/runner.py` in a
     subprocess with CPU/memory/time limits (`MAX_WORKER_SECONDS`,
     `MAX_WORKER_MEMORY_MB`) and blocked dangerous imports/file ops. CODE steps
     cannot call tools directly; they read the previous tool's output from
     `work/last_tool_output.json`.
   - `{SUMMARIZE}` — sends accumulated `Evidence` to the LLM for a final
     narrative summary.
3. `{{ variable }}` placeholders in tool kwargs are resolved against
   `Orchestrator.context`, which is built by flattening (one level deep) every
   prior tool's dict output. Only explicit `{{name}}` placeholders are
   substituted — there is intentionally no implicit string-match substitution,
   because flattened context keys can collide with unrelated literal argument
   values (see the docstring on `_substitute_variables`).
4. `T.dispatch()` catches exceptions inside tools and returns
   `{"error":..., "traceback":...}` instead of raising — the orchestrator
   treats a returned `traceback` key as a fatal crash (raises), while a tool
   deliberately returning just `{"error": ...}` for bad input is treated as a
   normal result. This distinction matters when adding new tools: raise inside
   the tool for real bugs, return a bare `error` dict for expected bad input.
5. `PubMedFetch.pmids` must exactly match the immediately preceding
   `PubMedSearch` result (or the literal placeholder `$LAST_PMIDS`) — this is
   an intentional hard binding to stop the planner from hallucinating PMIDs it
   never searched for.

**Hierarchical mode** (`src/agent/hierarchical.py`, `HierarchicalOrchestrator`):
Director → Reviewer → Worker → Writer, for more complex goals than the flat
orchestrator handles well.
- `DirectorAgent` decomposes a goal into subtasks (`prompts/director_*.md`).
- `ReviewerAgent` (`src/agent/reviewer.py`) approves/rejects the subtask plan
  with feedback; rejected plans loop back to the Director (max 3 attempts).
- `WorkerAgent` wraps a plain `Orchestrator` (`auto_approve=True`) to execute
  each subtask.
- `WriterAgent` (`src/agent/writer.py`) composes the final report from all
  subtask evidence.
- A single subtask's failure is caught and logged, not fatal to the whole run
  — later subtasks and the final report still get a chance to execute.

**LLM provider + tiering:** `src/agent/llm.py` (`LLMClient`) delegates to a
provider (`src/llm/providers.py`: `GeminiProvider` / `OllamaProvider`,
selected via `SETTINGS.llm_provider` / `LLM_PROVIDER` env var, default
`gemini`) so callers (`Orchestrator`, `HierarchicalOrchestrator`,
`ReviewerAgent`, `WriterAgent`, RAG's `MyelinEmbeddingFunction`) never touch a
provider SDK directly — they only ever call `LLMClient.generate()` /
`.count_tokens()` / `.embed()`.

Both providers expose the same `pro`/`flash`/`lite` tiers, but the tiers mean
different things per provider (`src/agent/rate_limits.py`,
`ModelManager.get_available_model`):
- **Gemini** (`MODEL_PRO`/`MODEL_FLASH`/`MODEL_LITE`): each tier has its own
  daily quota tracked in `work/usage.json` / `work/api_usage_audit.csv`
  (`src/agent/usage_auditor.py`). There is currently no automatic fallback if
  a tier's model is exhausted or deprecated — calls fail hard (`429
  RESOURCE_EXHAUSTED`) rather than cascading to another tier. If a configured
  model is pulled from the free tier, repoint the relevant `MODEL_*` setting
  rather than expecting graceful degradation.
- **Ollama** (`OLLAMA_MODEL_PRO`/`OLLAMA_MODEL_FLASH`/`OLLAMA_MODEL_LITE`,
  `OLLAMA_HOST`): no quota gating at all — Ollama has no call limits, so
  `ModelManager` skips quota checks/cascading entirely and just returns
  whichever local model the user configured for that tier. There's no
  auto-detection of installed models; the user sets each `OLLAMA_MODEL_*`
  var manually (or points them all at the same model). RAG embeddings switch
  to `OLLAMA_EMBED_MODEL` (default `nomic-embed-text`) instead of Gemini's
  `text-embedding-004` when this provider is active.

**Config:** `src/configs/settings.py` loads from environment variables (`.env`)
with `config.yaml` as fallback (env wins). Read this file for the full list of
tunables (sandbox limits, RAG chunking, model tiers/quotas) rather than
grepping `.env.example`, which only covers a subset.

**RAG:** `src/rag/` (ingest/store) + `src/tools/rag_tools.py` expose
`IndexDocument`/`QueryKnowledge`/`ListIndexedDocuments`, backed by a local
Chroma DB (`work/chroma_db`). `query_knowledge` is expected to return a
`warning` rather than a fabricated answer when the query is off-topic for the
indexed documents (see `tests/test_rag_adversarial.py`) — preserve this
behavior when touching retrieval/relevance-threshold logic
(`RAG_RELEVANCE_THRESHOLD`).

**Tools** (`src/tools/`): each file registers one or more tools via `@tool(...)`
in `registry.py` — e.g. `pubmed.py`, `geo_data.py`, `diff_expression.py`,
`wgcna.py`, `enrichment.py`, `ppi_network.py`, `blast.py`, `pdb_uniprot.py`,
`files.py`, `shell.py`, `web.py`, `rag_tools.py`. New tools just need the
decorator plus a docstring — `list_tools()` builds the planner's tool catalog
from the function signature and first docstring line automatically.

**Prompts** live in `prompts/*.md` as plain templates with `{{placeholder}}`
substitution done manually in Python (not a templating engine) — check the
matching `*_system.md`/`*_user.md` pair when changing what an agent role sees.

**Logging:** structured JSONL to `logs/run.jsonl` via `src/utils/logging.py`
(`LOGGER`); `--save-llm` additionally dumps full prompt/response pairs to
`logs/llm/`.

## Known project state (see `../ai_agent_context/` for full detail)

- `ai_agent_context/active_context.md` is the current status dashboard (goal,
  open tasks, blockers) — check it before starting nontrivial work, since it's
  updated far more often than this file.
- `ai_agent_context/rules.md` defines context tiers/exclusions for AI agents
  working in this repo (e.g. don't casually load `myelin/data/` or
  `redo_pubmed_tests/papers|results/` — token-heavy raw data).
- Current known gap: DEGs from `DIFF_EXPRESSION` are identified by raw probe ID
  (e.g. `ILMN_*`), not gene symbol, so downstream `PATHWAY_ENRICHMENT`/
  `PPI_NETWORK` steps return empty results until probe→gene mapping is added.
