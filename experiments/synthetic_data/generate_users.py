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


def load_prompt() -> str:
    with open(os.path.join(PROMPTS_DIR, "generate_user_prompt.txt"), "r") as f:
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
    parser.add_argument("--num_users", type=int, default=20)
    parser.add_argument("--model", type=str, default="gemini-flash-latest")
    args = parser.parse_args()

    os.makedirs(GENERATED_DIR, exist_ok=True)
    prompt_template = load_prompt()

    users = []
    
    print(f"Generating {args.num_users} users using model {args.model}...")
    
    def generate_single_user(index):
        # Add a small random seed/salt in prompt to ensure diversity
        prompt = prompt_template + f"\n\nGenerate user number {index+1} with a unique persona."
        response = rate_limited_call_gemini(
            prompt=prompt,
            model=args.model,
            temperature=1.0,
            response_mime_type="application/json"
        )
        user_data = parse_json_response(response)
        
        # Ensure a persona_id exists
        if "persona_id" not in user_data or not user_data["persona_id"]:
            user_data["persona_id"] = f"user_{str(uuid.uuid4())[:8]}"
        return user_data
        
    with ThreadPoolExecutor(max_workers=EVALUATOR_MAX_WORKERS) as executor:
        futures = {executor.submit(generate_single_user, i): i for i in range(args.num_users)}
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="Generating users"):
            try:
                user_data = future.result()
                users.append(user_data)
            except Exception as e:
                print(f"\nFailed to generate a user: {e}")

    # Save to JSONL
    jsonl_path = os.path.join(GENERATED_DIR, "users.jsonl")
    with open(jsonl_path, "w") as f:
        for u in users:
            f.write(json.dumps(u) + "\n")
            
    # Also save to simplified sample_personas for the main project
    sample_personas_path = os.path.join(PROJECT_ROOT, "experiments", "sample_personas.generated.jsonl")
    with open(sample_personas_path, "w") as f:
        for u in users:
            simplified = {
                "persona_id": u["persona_id"],
                "description": u.get("short_name", ""),
                "attributes": {
                    "demographics": u.get("demographics", {}),
                    "latent_profile": u.get("latent_profile", {})
                },
                "observable_history": u.get("observable_history", []),
                "distractor_history": u.get("distractor_history", [])
            }
            f.write(json.dumps(simplified) + "\n")

    # Save to CSV
    csv_path = os.path.join(GENERATED_DIR, "users.csv")
    if users:
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["persona_id", "short_name", "location", "observable_history_count"])
            for u in users:
                loc = u.get("demographics", {}).get("location", "")
                history_count = len(u.get("observable_history", []))
                writer.writerow([u.get("persona_id"), u.get("short_name"), loc, history_count])

    # Save to MD
    md_path = os.path.join(GENERATED_DIR, "users_preview.md")
    with open(md_path, "w") as f:
        f.write("# Generated Users Preview\n\n")
        for u in users:
            f.write(f"## {u.get('short_name', 'Unnamed')} ({u.get('persona_id')})\n")
            f.write(f"**Location:** {u.get('demographics', {}).get('location', 'Unknown')}\n\n")
            f.write("### Latent Profile\n")
            for domain, prof in u.get("latent_profile", {}).items():
                # Extract simple summary if possible
                f.write(f"- **{domain}:** {json.dumps(prof)}\n")
            f.write("\n### Observable History (Sample)\n")
            for h in u.get("observable_history", [])[:5]:
                f.write(f"- [{h.get('domain')}] {h.get('type')}: {h.get('content')}\n")
            f.write("\n### Distractor History (Sample)\n")
            for h in u.get("distractor_history", [])[:2]:
                f.write(f"- [{h.get('domain')}] {h.get('type')}: {h.get('content')}\n")
            f.write("\n---\n\n")

    print(f"Done! {len(users)} users saved to generated directory and experiments/sample_personas.generated.jsonl")

if __name__ == "__main__":
    main()
