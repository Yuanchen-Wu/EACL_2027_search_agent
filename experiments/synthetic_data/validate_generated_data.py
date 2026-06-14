import json
import os
import sys

GENERATED_DIR = os.path.join(os.path.dirname(__file__), "generated")
USERS_FILE = os.path.join(GENERATED_DIR, "users.jsonl")
QUERIES_FILE = os.path.join(GENERATED_DIR, "queries.jsonl")

VALID_DOMAINS = {"ecommerce", "health_medical", "education", "travel"}
VALID_QUERY_TYPES = {"personalization_required", "personalization_helpful", "overpersonalization_trap"}

def main():
    users = []
    queries = []
    errors = []

    # 1. Parse Users
    user_ids = set()
    if not os.path.exists(USERS_FILE):
        errors.append(f"Users file missing: {USERS_FILE}")
    else:
        with open(USERS_FILE, "r") as f:
            for line_idx, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    user = json.loads(line)
                    
                    if "persona_id" not in user:
                        errors.append(f"User line {line_idx}: missing persona_id")
                        continue
                        
                    pid = user["persona_id"]
                    if pid in user_ids:
                        errors.append(f"Duplicate persona_id: {pid}")
                    user_ids.add(pid)
                    users.append(user)
                    
                    # required fields
                    for req in ["short_name", "demographics", "latent_profile", "observable_history", "distractor_history"]:
                        if req not in user:
                            errors.append(f"User {pid}: missing {req}")
                            
                except json.JSONDecodeError:
                    errors.append(f"User line {line_idx}: JSON parse error")

    # 2. Parse Queries
    example_ids = set()
    queries_by_domain = {}
    queries_by_type = {}
    
    if not os.path.exists(QUERIES_FILE):
        errors.append(f"Queries file missing: {QUERIES_FILE}")
    else:
        with open(QUERIES_FILE, "r") as f:
            for line_idx, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    query = json.loads(line)
                    
                    if "example_id" not in query:
                        errors.append(f"Query line {line_idx}: missing example_id")
                        continue
                        
                    eid = query["example_id"]
                    if eid in example_ids:
                        errors.append(f"Duplicate example_id: {eid}")
                    example_ids.add(eid)
                    queries.append(query)
                    
                    # Track stats
                    d = query.get("domain")
                    qt = query.get("query_type")
                    queries_by_domain[d] = queries_by_domain.get(d, 0) + 1
                    queries_by_type[qt] = queries_by_type.get(qt, 0) + 1
                    
                    # Validation
                    pid = query.get("persona_id")
                    if pid not in user_ids:
                        errors.append(f"Query {eid}: Invalid persona_id reference: {pid}")
                        
                    if d not in VALID_DOMAINS:
                        errors.append(f"Query {eid}: Invalid domain: {d}")
                        
                    if qt not in VALID_QUERY_TYPES:
                        errors.append(f"Query {eid}: Invalid query_type: {qt}")
                        
                    if not query.get("ambiguous_query"):
                        errors.append(f"Query {eid}: ambiguous_query is empty")
                        
                    if not query.get("clear_hidden_intent"):
                        errors.append(f"Query {eid}: clear_hidden_intent is empty")
                        
                    targets = query.get("personalization_targets", {})
                    must_use = targets.get("must_use", [])
                    should_not_use = targets.get("should_not_use", [])
                    keywords = targets.get("desired_fanout_keywords", [])
                    
                    if qt != "overpersonalization_trap" and not must_use:
                        errors.append(f"Query {eid}: missing must_use items for {qt}")
                        
                    if not should_not_use:
                        errors.append(f"Query {eid}: missing should_not_use items")
                        
                    if not keywords:
                        errors.append(f"Query {eid}: missing desired_fanout_keywords")
                        
                except json.JSONDecodeError:
                    errors.append(f"Query line {line_idx}: JSON parse error")

    summary = {
        "num_users": len(users),
        "num_queries": len(queries),
        "queries_by_domain": queries_by_domain,
        "queries_by_type": queries_by_type,
        "errors": errors
    }
    
    print(json.dumps(summary, indent=2))
    
    if errors:
        sys.exit(1)
    else:
        print("\nAll validations passed!")

if __name__ == "__main__":
    main()
