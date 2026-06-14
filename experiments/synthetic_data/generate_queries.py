import argparse
import csv
import json
import os
import sys
import uuid
from typing import Any, Dict, List

# Add the project root and src to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(PROJECT_ROOT)
sys.path.append(os.path.join(PROJECT_ROOT, "src"))

from src.llm_gemini import call_gemini

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
GENERATED_DIR = os.path.join(os.path.dirname(__file__), "generated")
DOMAIN_SCHEMAS_FILE = os.path.join(os.path.dirname(__file__), "domain_schemas.yaml")

def load_prompt() -> str:
    with open(os.path.join(PROMPTS_DIR, "generate_query_prompt.txt"), "r") as f:
        return f.read()

def load_domain_schemas_text() -> str:
    with open(DOMAIN_SCHEMAS_FILE, "r") as f:
        return f.read()

def parse_json_response(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    from tqdm import tqdm
except ImportError:
    # Fallback if tqdm is not installed
    def tqdm(iterable, *args, **kwargs):
        return iterable

EVALUATOR_RPM = 250
EVALUATOR_MAX_WORKERS = 15

rate_limit_lock = threading.Lock()
last_request_time = 0.0

def rate_limited_call_gemini(*args, **kwargs):
    global last_request_time
    delay = 60.0 / EVALUATOR_RPM
    with rate_limit_lock:
        now = time.time()
        elapsed = now - last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        last_request_time = time.time()
    return call_gemini(*args, **kwargs)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--users_file", type=str, default=os.path.join(GENERATED_DIR, "users.jsonl"))
    parser.add_argument("--queries_per_user_per_domain", type=int, default=2)
    parser.add_argument("--model", type=str, default="gemini-flash-latest")
    args = parser.parse_args()

    os.makedirs(GENERATED_DIR, exist_ok=True)
    prompt_template = load_prompt()
    domain_schemas_text = load_domain_schemas_text()
    
    # Extract domains and query types manually from our known yaml structure
    domains = ["ecommerce", "health_medical", "education", "travel"]
    query_types = [
        "personalization_required", 
        "personalization_helpful", 
        "overpersonalization_trap"
    ]

    users = []
    if os.path.exists(args.users_file):
        with open(args.users_file, "r") as f:
            for line in f:
                if line.strip():
                    users.append(json.loads(line))
    else:
        print(f"Error: Users file {args.users_file} not found. Generate users first.")
        sys.exit(1)

    print(f"Loaded {len(users)} users.")
    queries = []
    
    total_expected = len(users) * len(domains) * args.queries_per_user_per_domain

    print(f"Generating queries (Total expected: {total_expected}) using model {args.model}...")
    
    def generate_single_query(user, domain, q_type, domain_schema_info):
        persona_id = user.get("persona_id")
        user_profile_json = json.dumps(user, indent=2)
        
        prompt = prompt_template.replace("{user_profile}", user_profile_json)
        prompt = prompt.replace("{domain}", domain)
        prompt += f"\n\nConstraint: Ensure the query type is {q_type}."
        prompt += f"\nHere is the domain schema for {domain} for your reference:\n{domain_schema_info}"
        prompt += f"\nGenerate a unique example."

        response = rate_limited_call_gemini(
            prompt=prompt,
            model=args.model,
            temperature=1.0,
            response_mime_type="application/json"
        )
        query_data = parse_json_response(response)
        
        if "example_id" not in query_data or not query_data["example_id"]:
            query_data["example_id"] = f"{domain}_{persona_id}_{str(uuid.uuid4())[:6]}"
        
        # Ensure persona_id matches
        query_data["persona_id"] = persona_id
        return query_data

    # Pre-compute tasks to round-robin query types
    tasks = []
    query_type_idx = 0
    for user in users:
        for domain in domains:
            domain_schema_info = domain_schemas_text
            for _ in range(args.queries_per_user_per_domain):
                q_type = query_types[query_type_idx % len(query_types)]
                query_type_idx += 1
                tasks.append((user, domain, q_type, domain_schema_info))

    with ThreadPoolExecutor(max_workers=EVALUATOR_MAX_WORKERS) as executor:
        futures = {executor.submit(generate_single_query, *task): task for task in tasks}
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="Generating queries"):
            try:
                query_data = future.result()
                queries.append(query_data)
            except Exception as e:
                print(f"\nFailed to generate a query: {e}")

    # Save to JSONL
    jsonl_path = os.path.join(GENERATED_DIR, "queries.jsonl")
    with open(jsonl_path, "w") as f:
        for q in queries:
            f.write(json.dumps(q) + "\n")
            
    # Save to simplified sample_queries for the main project
    sample_queries_path = os.path.join(PROJECT_ROOT, "experiments", "sample_queries.generated.jsonl")
    with open(sample_queries_path, "w") as f:
        for q in queries:
            simplified = {
                "query_id": q["example_id"],
                "query": q.get("ambiguous_query", ""),
                "domain": q.get("domain", ""),
                "query_type": q.get("query_type", ""),
                "persona_id": q.get("persona_id", ""),
                "metadata": {
                    "clear_hidden_intent": q.get("clear_hidden_intent", ""),
                    "must_use": q.get("personalization_targets", {}).get("must_use", []),
                    "should_not_use": q.get("personalization_targets", {}).get("should_not_use", []),
                    "desired_fanout_keywords": q.get("personalization_targets", {}).get("desired_fanout_keywords", [])
                }
            }
            f.write(json.dumps(simplified) + "\n")

    # Save to CSV
    csv_path = os.path.join(GENERATED_DIR, "queries.csv")
    if queries:
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["example_id", "persona_id", "domain", "query_type", "ambiguous_query", "clear_hidden_intent"])
            for q in queries:
                writer.writerow([
                    q.get("example_id"),
                    q.get("persona_id"),
                    q.get("domain"),
                    q.get("query_type"),
                    q.get("ambiguous_query"),
                    q.get("clear_hidden_intent")
                ])

    # Save to MD
    md_path = os.path.join(GENERATED_DIR, "queries_preview.md")
    with open(md_path, "w") as f:
        f.write("# Generated Queries Preview\n\n")
        
        # Group by domain
        queries_by_domain = {}
        for q in queries:
            d = q.get("domain", "unknown")
            if d not in queries_by_domain:
                queries_by_domain[d] = []
            queries_by_domain[d].append(q)
            
        for domain, d_queries in queries_by_domain.items():
            f.write(f"## Domain: {domain}\n\n")
            for q in d_queries:
                f.write(f"### {q.get('example_id')} (User: {q.get('persona_id')})\n")
                f.write(f"**Type:** {q.get('query_type')}\n\n")
                f.write(f"**Ambiguous Query:** `{q.get('ambiguous_query')}`\n\n")
                f.write(f"**Clear Hidden Intent:** {q.get('clear_hidden_intent')}\n\n")
                
                targets = q.get("personalization_targets", {})
                f.write(f"- **Must Use:** {', '.join(targets.get('must_use', []))}\n")
                f.write(f"- **Should Not Use:** {', '.join(targets.get('should_not_use', []))}\n")
                f.write(f"- **Desired Fanout Keywords:** {', '.join(targets.get('desired_fanout_keywords', []))}\n\n")
            f.write("---\n\n")

    print(f"Done! {len(queries)} queries saved to generated directory and experiments/sample_queries.generated.jsonl")

if __name__ == "__main__":
    main()
