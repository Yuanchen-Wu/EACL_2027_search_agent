import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from src.run_agent import run_agent, load_personas
from src.schemas import VARIANTS

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries_path", type=str, default=os.path.join(PROJECT_ROOT, "experiments", "sample_queries.generated.jsonl"))
    parser.add_argument("--personas_path", type=str, default=os.path.join(PROJECT_ROOT, "experiments", "sample_personas.generated.jsonl"))
    parser.add_argument("--log_path", type=str, default=os.path.join(PROJECT_ROOT, "outputs", "generated_benchmark_runs.jsonl"))
    parser.add_argument("--model", type=str, default="gemini-flash-latest")
    parser.add_argument("--max_results_per_branch", type=int, default=5)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    personas = load_personas(args.personas_path)
    
    queries = []
    if os.path.exists(args.queries_path):
        with open(args.queries_path, "r") as f:
            for line in f:
                if line.strip():
                    queries.append(json.loads(line))
                    
    if args.limit > 0:
        queries = queries[:args.limit]
        
    print(f"Loaded {len(queries)} queries and {len(personas)} personas.")
    
    variants_ordered = [
        "V0_generic_single",
        "V1_generic_fanout",
        "V2_synthesis_only_personalization",
        "V3_personalized_fanout",
        "V4_mixed_fanout"
    ]
    for v in variants_ordered:
        assert v in VARIANTS, f"Variant {v} not in VARIANTS"
        
    os.makedirs(os.path.dirname(args.log_path), exist_ok=True)
    
    count = 0
    with open(args.log_path, "a") as out_f:
        for q in queries:
            persona_id = q.get("persona_id")
            persona = personas.get(persona_id)
            if not persona:
                print(f"Warning: Persona {persona_id} not found for query {q.get('query_id')}. Skipping.")
                continue
                
            ambiguous_query = q.get("query")
            
            for variant in variants_ordered:
                count += 1
                print(f"Running query {q.get('query_id')} with variant {variant}...")
                
                try:
                    run_log = run_agent(
                        user_query=ambiguous_query,
                        persona=persona,
                        variant=variant,
                        model=args.model,
                        max_results_per_branch=args.max_results_per_branch
                    )
                    
                    record = {
                        "example_id": q.get("query_id"),
                        "query_id": q.get("query_id"),
                        "domain": q.get("domain"),
                        "query_type": q.get("query_type"),
                        "persona_id": persona_id,
                        "ambiguous_query": ambiguous_query,
                        "query_metadata": q.get("metadata", {}),
                        "variant": variant,
                        "run_log": run_log.as_dict()
                    }
                    
                    out_f.write(json.dumps(record) + "\n")
                    out_f.flush()
                except Exception as e:
                    print(f"Failed to run agent for {q.get('query_id')} on {variant}: {e}")
                
    print(f"Finished {count} benchmark runs. Saved to {args.log_path}")

if __name__ == "__main__":
    main()
