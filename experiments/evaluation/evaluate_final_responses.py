import argparse
import json
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs):
        return iterable

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(EVAL_DIR, "..", ".."))
SYNTHETIC_DATA_DIR = os.path.join(PROJECT_ROOT, "experiments", "synthetic_data")

sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "src"))
sys.path.append(SYNTHETIC_DATA_DIR)

from src.llm_gemini import call_gemini
from utils import parse_json_response, read_jsonl

EVAL_RPM = 200
rate_limit_lock = threading.Lock()
last_request_time = 0.0

def rate_limited_gemini(*args, **kwargs):
    global last_request_time
    delay = 60.0 / EVAL_RPM
    with rate_limit_lock:
        now = time.time()
        elapsed = now - last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        last_request_time = time.time()
    return call_gemini(*args, **kwargs)

def load_prompt() -> str:
    with open(os.path.join(EVAL_DIR, "prompts", "final_response_pointwise_judge.txt"), "r") as f:
        return f.read()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs_path", type=str, default=os.path.join(PROJECT_ROOT, "outputs", "generated_benchmark_runs.jsonl"))
    parser.add_argument("--output_path", type=str, default=os.path.join(EVAL_DIR, "generated", "final_response_scores.jsonl"))
    parser.add_argument("--judge_model", type=str, default="gemini-flash-latest")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output_path), exist_ok=True)
    prompt_template = load_prompt()

    runs = read_jsonl(args.runs_path)
    if not runs:
        print(f"Error: Runs file {args.runs_path} not found or empty.")
        sys.exit(1)
        
    if args.limit > 0:
        runs = runs[:args.limit]
        
    print(f"Loaded {len(runs)} benchmark runs to evaluate.")

    mode = "a" if args.append else "w"
    
    def evaluate_single_run(run):
        eval_record = {
            "eval_id": f"eval_{str(uuid.uuid4())[:8]}",
            "example_id": run.get("example_id"),
            "domain": run.get("domain"),
            "query_type": run.get("query_type"),
            "persona_id": run.get("persona_id"),
            "variant": run.get("variant"),
            "ambiguous_query": run.get("ambiguous_query"),
            "clear_hidden_intent": run.get("query_metadata", {}).get("clear_hidden_intent", ""),
            "final_answer": run.get("run_log", {}).get("final_answer", ""),
            "judge_model": args.judge_model
        }
        
        required = ["example_id", "variant", "clear_hidden_intent", "query_type", "domain", "final_answer"]
        for req in required:
            if not eval_record.get(req):
                eval_record["error"] = f"Missing required field: {req}"
                return eval_record
                
        prompt = prompt_template
        replacements = {
            "{domain}": eval_record["domain"],
            "{query_type}": eval_record["query_type"],
            "{ambiguous_query}": eval_record["ambiguous_query"],
            "{persona}": json.dumps(run.get("run_log", {}).get("persona", {}), indent=2),
            "{clear_hidden_intent}": eval_record["clear_hidden_intent"],
            "{must_use}": json.dumps(run.get("query_metadata", {}).get("must_use", []), indent=2),
            "{should_not_use}": json.dumps(run.get("query_metadata", {}).get("should_not_use", []), indent=2),
            "{desired_fanout_keywords}": json.dumps(run.get("query_metadata", {}).get("desired_fanout_keywords", []), indent=2),
            "{final_answer}": eval_record["final_answer"]
        }
        for k, v in replacements.items():
            prompt = prompt.replace(k, str(v))

        try:
            response = rate_limited_gemini(
                prompt=prompt,
                model=args.judge_model,
                temperature=0.1,
                response_mime_type="application/json"
            )
            eval_record["raw_judge_response"] = response
            parsed = parse_json_response(response)
            
            eval_record["scores"] = {
                "intent_satisfaction": parsed.get("intent_satisfaction", 1),
                "personalization_target_use": parsed.get("personalization_target_use", 1),
                "overpersonalization": parsed.get("overpersonalization", 1),
                "specificity": parsed.get("specificity", 1),
                "safety": parsed.get("safety", 1),
                "overall": parsed.get("overall", 1)
            }
            eval_record["diagnostic_feedback"] = parsed.get("diagnostic_feedback", "")
            eval_record["failure_modes"] = parsed.get("failure_modes", [])
        except Exception as e:
            eval_record["error"] = str(e)
            
        return eval_record

    with open(args.output_path, mode) as out_f:
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(evaluate_single_run, r): r for r in runs}
            for future in tqdm(as_completed(futures), total=len(futures), desc="Evaluating runs"):
                try:
                    result = future.result()
                    out_f.write(json.dumps(result) + "\n")
                    out_f.flush()
                except Exception as e:
                    print(f"\nFailed to evaluate a run: {e}")
                    
    print(f"Finished evaluation. Results saved to {args.output_path}")

if __name__ == "__main__":
    main()
