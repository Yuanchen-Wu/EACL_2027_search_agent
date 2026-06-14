# Final Response Evaluation

This directory contains the tools to evaluate the final answers of our personalized search-based AI agent.

## Purpose
The purpose of this evaluation is to answer:
> Does personalized fan-out or mixed fan-out improve final response quality compared with generic fan-out and synthesis-only personalization?

This evaluates *only* the final answer. Fan-out branch evaluation, retrieval quality evaluation, and pairwise LLM comparisons are left for future work.

## Pointwise vs. Exact-Match Evaluation
Because this is an open-ended personalized search task, there is no single exact ground-truth string to compare against. Instead, we use an LLM-as-a-judge to evaluate how well the final response satisfies the user's hidden intent while properly utilizing specific required user constraints (and avoiding irrelevant ones).

## Compact Judge Dimensions
The judge evaluates 6 distinct dimensions using an integer scale of 1-5:
1. `intent_satisfaction`: Does it satisfy the true hidden intent? (Higher is better)
2. `personalization_target_use`: Does it effectively use `must_use` constraints? (Higher is better)
3. `overpersonalization`: Does it misuse `should_not_use` constraints or overly force persona traits? (Lower is better)
4. `specificity`: Is the answer concrete instead of generic? (Higher is better)
5. `safety`: Crucial for health/medical scenarios. Are there unsafe recommendations? (Higher is better)
6. `overall`: Holistic quality score. (Higher is better)

*Note on LLM-as-judge limits:* The judge provides a heuristic evaluation and relies heavily on the `clear_hidden_intent` and `personalization_targets`. It might occasionally misinterpret subtle nuances in search results.

## Workflow

### 1. Generate Benchmark Data
Ensure you have synthetic users and queries generated via `experiments/synthetic_data`.

### 2. Run the Benchmark
Run all variants (V0-V4) on the generated queries. This will produce a JSONL log with the exact queries, personas, variant types, and outputs.

```bash
python experiments/run_generated_benchmark.py --limit 50
```

### 3. Evaluate Final Responses
Run the pointwise judge over the benchmark logs.

```bash
python experiments/evaluation/evaluate_final_responses.py --limit 50
```

### 4. Summarize Results
Aggregate the JSONL scores into readable CSVs and a Markdown summary report.

```bash
python experiments/evaluation/summarize_eval_results.py
```
