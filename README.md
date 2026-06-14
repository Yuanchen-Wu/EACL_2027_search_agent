# Personalization Placement in Query Fan-out (EACL 2027 prototype)

A simple, inspectable search-based AI agent for studying **where personalization
should be applied** in a search-augmented LLM pipeline.

## Motivation

When you build a retrieval-augmented agent, you can inject the user's persona /
context at different stages:

- only at **final answer synthesis**, or
- during **query fan-out** (the search queries themselves), or
- at **both** stages, or
- via a **mixed** fan-out that explicitly seeks generic, personalized,
  constraint, and *disconfirming* evidence.

**Research question:** does personalization help more at synthesis, at fan-out,
at both, or in a mixed/disconfirming fan-out design?

This first iteration is deliberately minimal: plain Python, clean logging, no
reranking or fusion. The goal is **ablation control and research transparency**,
not production performance.

## Pipeline

```
user query (+ optional persona)
  -> query fan-out generation        (Gemini; variant-dependent)
  -> Tavily Search API calls         (one call per branch)
  -> collect top results per branch  (normalized, duplicates flagged)
  -> final answer synthesis          (Gemini; persona-dependent)
  -> structured JSONL log            (outputs/runs.jsonl)
```

We use **Tavily only for search evidence** — its generated `answer` field is
never used. All synthesis is done by Gemini so the experiment cleanly isolates
personalization placement.

## Variants

| Variant | Fan-out | Persona in fan-out? | Persona in synthesis? |
|---|---|---|---|
| `V0_generic_single` | raw query as one branch | no | no |
| `V1_generic_fanout` | 3–5 generic queries | no | no |
| `V2_synthesis_only_personalization` | generic queries (same as V1) | no | **yes** |
| `V3_personalized_fanout` | personalized queries | **yes** | **yes** |
| `V4_mixed_fanout` | generic + personalized + constraint + disconfirming | **yes** | **yes** |

No fusion, reranking, or Reciprocal Rank Fusion is implemented in this version.

## Project structure

```
project/
  README.md
  .env.example
  requirements.txt
  src/
    config.py          # env vars, defaults, paths
    llm_gemini.py      # call_gemini(...)
    search_tavily.py   # search_tavily(...), collect_search_results(...)
    fanout.py          # generate_fanout_queries(...)
    synthesize.py      # synthesize_answer(...)
    run_agent.py       # orchestration + CLI
    schemas.py         # dataclass schemas
    logging_utils.py   # JSONL logging
  experiments/
    sample_queries.jsonl
    sample_personas.jsonl
    run_batch.py
  outputs/
    runs.jsonl         # appended run logs
```

## Setup

1. Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure API keys. **Keys are read only from environment variables; nothing
   is hardcoded.** Copy the example file and fill in your real keys:

```bash
cp .env.example .env
# then edit .env:
#   GEMINI_API_KEY=...
#   TAVILY_API_KEY=...
```

`.env` is git-ignored. You can also export the variables directly instead of
using a `.env` file:

```bash
export GEMINI_API_KEY=...
export TAVILY_API_KEY=...
```

## Run one query

```bash
python src/run_agent.py \
  --query "What laptop should I buy for ML research?" \
  --persona_id ml_phd_budget \
  --variant V4_mixed_fanout
```

This prints:

- the fan-out branches (with type, query, rationale, persona fields used),
- the top Tavily results per branch,
- the final synthesized answer,
- a cost proxy,

and appends one JSON line to `outputs/runs.jsonl`.

Useful flags: `--variant` (one of the five), `--persona_id` (from
`experiments/sample_personas.jsonl`, optional), `--max_results_per_branch`,
`--model`, `--no_log`.

## Run the batch ablation

```bash
python experiments/run_batch.py
```

Reads `experiments/sample_queries.jsonl` (5 queries) and
`experiments/sample_personas.jsonl` (3 personas) and runs the variants.

By default it runs in **deduplicated** mode: the non-personalized variants
(`V0`, `V1`) run once per query, and the personalized variants (`V2`, `V3`,
`V4`) run once per (query, persona) pair. Pass `--full-grid` for a strict
factorial design (every variant for every pair). Use `--limit N` for a quick
smoke test.

## Interpreting the logs

Each line in `outputs/runs.jsonl` is one run:

```json
{
  "run_id": "...",
  "timestamp": "2026-...Z",
  "variant": "V4_mixed_fanout",
  "user_query": "...",
  "persona_id": "ml_phd_budget",
  "persona": { "...": "..." },
  "fanout_branches": [
    {"branch_type": "personalized", "query": "...", "rationale": "...",
     "used_persona_fields": ["budget", "expertise"]}
  ],
  "raw_search_results": [
    {"title": "...", "url": "...", "content": "...", "score": 0.91,
     "rank": 1, "branch_type": "personalized", "branch_query": "...",
     "is_duplicate_url": false}
  ],
  "final_answer": "...",
  "cost_proxy": {
    "num_gemini_calls": 2,
    "num_tavily_calls": 7,
    "num_fanout_branches": 7,
    "num_raw_results": 31
  }
}
```

Suggested analyses:

- **Fan-out inspection:** compare branch types/queries across V1 vs V3 vs V4 to
  see how persona conditioning changes retrieval.
- **Evidence overlap:** group `raw_search_results` by `branch_type` /
  `branch_query`; `is_duplicate_url` flags URLs seen in an earlier branch.
- **Answer comparison:** read `final_answer` across V0–V4 for the same query to
  judge where personalization actually changes the output.
- **Cost vs. benefit:** `cost_proxy` gives a transparent proxy for the work each
  variant did (Gemini + Tavily calls, branch and result counts).

A quick way to scan results:

```bash
python -c "import json;[print(j['variant'], j['cost_proxy']) for j in map(json.loads, open('outputs/runs.jsonl'))]"
```

## Notes & limitations

- No reranking / fusion yet (planned for later iterations).
- Duplicate URLs are kept but flagged, not removed.
- `cost_proxy` is a transparency aid, not real billing.
- Soft-fails on a single bad search/branch so a batch run keeps going.
