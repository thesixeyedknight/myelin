# AI Research Automation Framework (Minimal)

A tiny agentic runner that plans steps with an LLM (Gemini), calls domain tools (e.g., PubMed), and safely executes small Python snippets in a sandbox. Human approval is required between steps by default.

## Quickstart

1. **Create env file**

   ```bash
   cp .env.example .env
   # Edit .env to add GEMINI_API_KEY and NCBI_EMAIL
   ```

2. **Build the container**

   ```bash
   docker build -t ai-auto:dev .
   ```

3. **Run**

   ```bash
   docker run --rm -it \
     --name ai-auto \
     -v "$PWD/data":/app/data:ro \
     -v "$PWD/work":/app/work \
     -v "$PWD/logs":/app/logs \
     --env-file ./.env \
     ai-auto:dev \
     python -m src.main "Summarize recent literature on CRISPR off-target detection in human cells and draft a small QC script to parse a TSV of GUIDE-seq results"
   ```

   Use `--auto-approve` to skip human confirmations for non-destructive steps.

## Philosophy

* Few **high-value** LLM calls (free-tier friendly).
* Tools do the evidence gathering; LLM explains/decides.
* Generated code runs in a sandbox with CPU/memory/time limits.
* Everything logged to `logs/` for reproducibility.

## Notes

* Network access for generated code is **disabled by policy** (runner prevents `socket` by default). If you need it, enable explicitly.
* PubMed access respects NCBI E-utilities etiquette with backoff.
