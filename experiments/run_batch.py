"""Batch experiment runner for the personalization-placement ablation.

Reads sample queries and personas, then runs the V0-V4 variants and appends one
JSONL record per run to ``outputs/runs.jsonl``.

Run:
    python experiments/run_batch.py

By default we avoid redundant work: the non-personalized variants (V0, V1) are
run ONCE per query (persona has no effect on them), while the personalized
variants (V2, V3, V4) are run once per (query, persona) pair. Pass --full-grid
to instead run every variant for every (query, persona) pair (matches a strict
factorial design but produces duplicate V0/V1 logs).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

# Make the src/ modules importable when running this script directly.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))

from config import (  # noqa: E402
    DEFAULT_GEMINI_MODEL,
    DEFAULT_MAX_RESULTS_PER_BRANCH,
    DEFAULT_RUNS_LOG,
)
from logging_utils import append_run_log  # noqa: E402
from run_agent import (  # noqa: E402
    PERSONALIZED_SYNTHESIS_VARIANTS,
    load_personas,
    run_agent,
)
from schemas import Persona, VARIANTS  # noqa: E402

DEFAULT_QUERIES_PATH = os.path.join(
    _PROJECT_ROOT, "experiments", "sample_queries.jsonl"
)
DEFAULT_PERSONAS_PATH = os.path.join(
    _PROJECT_ROOT, "experiments", "sample_personas.jsonl"
)

# Variants that ignore the persona entirely (fan-out + synthesis both generic).
NON_PERSONALIZED_VARIANTS = [
    v for v in VARIANTS if v not in PERSONALIZED_SYNTHESIS_VARIANTS
]


def load_queries(path: str) -> List[Dict[str, str]]:
    """Load queries from a JSONL file."""
    queries: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            queries.append(json.loads(line))
    return queries


def build_plan(
    queries: List[Dict[str, str]],
    personas: Dict[str, Persona],
    full_grid: bool,
) -> List[tuple[str, Optional[Persona], str]]:
    """Build the list of (query, persona, variant) jobs to run."""
    persona_list = list(personas.values())
    plan: List[tuple[str, Optional[Persona], str]] = []

    for q in queries:
        query_text = q["query"]
        if full_grid:
            for persona in persona_list:
                for variant in VARIANTS:
                    plan.append((query_text, persona, variant))
        else:
            # Non-personalized variants once per query (no persona needed).
            for variant in NON_PERSONALIZED_VARIANTS:
                plan.append((query_text, None, variant))
            # Personalized variants once per (query, persona).
            for persona in persona_list:
                for variant in PERSONALIZED_SYNTHESIS_VARIANTS:
                    plan.append((query_text, persona, variant))
    return plan


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Run the ablation batch.")
    parser.add_argument("--queries_path", default=DEFAULT_QUERIES_PATH)
    parser.add_argument("--personas_path", default=DEFAULT_PERSONAS_PATH)
    parser.add_argument("--log_path", default=DEFAULT_RUNS_LOG)
    parser.add_argument("--model", default=DEFAULT_GEMINI_MODEL)
    parser.add_argument(
        "--max_results_per_branch",
        type=int,
        default=DEFAULT_MAX_RESULTS_PER_BRANCH,
    )
    parser.add_argument(
        "--full-grid",
        action="store_true",
        help="Run every variant for every (query, persona) pair.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on number of runs (for quick smoke tests).",
    )
    args = parser.parse_args(argv)

    queries = load_queries(args.queries_path)
    personas = load_personas(args.personas_path)
    plan = build_plan(queries, personas, args.full_grid)
    if args.limit is not None:
        plan = plan[: args.limit]

    total = len(plan)
    print(f"[run_batch] {total} runs planned "
          f"({'full grid' if args.full_grid else 'deduplicated'} mode).")

    failures = 0
    for i, (query_text, persona, variant) in enumerate(plan, start=1):
        pid = persona.persona_id if persona else None
        print(f"[{i}/{total}] variant={variant} persona={pid} "
              f"query={query_text[:50]!r}")
        try:
            run_log = run_agent(
                user_query=query_text,
                persona=persona,
                variant=variant,
                model=args.model,
                max_results_per_branch=args.max_results_per_branch,
            )
            append_run_log(run_log, path=args.log_path)
        except Exception as err:  # noqa: BLE001 - keep batch resilient
            failures += 1
            print(f"    ERROR: {err}")

    print(f"[run_batch] done. {total - failures}/{total} succeeded. "
          f"Logs appended to {args.log_path}")


if __name__ == "__main__":
    main()
