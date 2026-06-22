import argparse
import os
import sys
import yaml
import json
from collections import Counter

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))
sys.path.insert(0, _PROJECT_ROOT)

from search_agent.schemas import QueryRecord, VARIANTS, Persona
from search_agent.run_agent import load_personas
from scripts.run_benchmark import load_queries

DOMAINS_CATEGORIES = {
    "education": {
        "retrieval_sensitive": ["travel_dining", "shopping_product_recommendation"],
        "synthesis_sensitive": ["technical_explanation", "personal_decision_strategy"]
    },
    "legal_info": {
        "retrieval_sensitive": ["jurisdiction_resource_lookup", "form_policy_deadline_lookup"],
        "synthesis_sensitive": ["legal_issue_explanation", "legal_decision_strategy"]
    },
    "personal_finance": {
        "retrieval_sensitive": ["product_or_program_comparison", "current_rule_limit_lookup"],
        "synthesis_sensitive": ["financial_concept_explanation", "financial_decision_strategy"]
    }
}

EXPECTED_ARCHETYPES = {
    "education": {
        "budget_nonstem_student", "budget_highstem_phd", "modbudget_nonstem_switcher",
        "highbudget_highstem_pro", "family_modbudget", "intl_newgrad"
    },
    "legal_info": {
        "tenant_low_income_eviction_risk", "immigrant_worker_visa_uncertain", "small_business_owner_contracts",
        "divorced_parent_custody_schedule", "employee_noncompete_layoff", "privacy_conscious_online_creator"
    },
    "personal_finance": {
        "paycheck_to_paycheck_credit_rebuild", "high_income_low_time_tech_worker", "first_gen_college_grad_student_loans",
        "young_family_homebuyer", "near_retirement_catchup", "freelancer_irregular_income_taxes"
    }
}

def check_path(path_str, name):
    if not os.path.isabs(path_str):
        path_str = os.path.join(_PROJECT_ROOT, path_str)
    exists = os.path.exists(path_str)
    print(f"[{'PASS' if exists else 'FAIL'}] {name}: {path_str}")
    return exists, path_str

def word_overlap(str1, str2):
    w1 = set(str1.lower().replace("?", "").replace(".", "").replace(",", "").split())
    w2 = set(str2.lower().replace("?", "").replace(".", "").replace(",", "").split())
    if not w1 or not w2: return 0.0
    return len(w1.intersection(w2)) / min(len(w1), len(w2))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    print(f"Validating experiment setup using config: {args.config}\n")
    
    with open(args.config, "r") as f:
        config = yaml.safe_load(f)
        
    print("1. Checking Paths & Config")
    print("-" * 40)
    data_config = config.get("data", {})
    outputs_config = config.get("outputs", {})
    
    queries_ok, queries_path = check_path(data_config.get("queries_path", ""), "Queries path")
    personas_ok, personas_path = check_path(data_config.get("personas_path", ""), "Personas path")
    
    retrieval_scores_ok = "retrieval_scores_path" in outputs_config
    print(f"[{'PASS' if retrieval_scores_ok else 'FAIL'}] retrieval_scores_path exists in config")
    
    # Optional outputs
    out_dir = os.path.dirname(outputs_config.get("runs_path", "outputs/test.jsonl"))
    if not os.path.isabs(out_dir): out_dir = os.path.join(_PROJECT_ROOT, out_dir)
    print(f"[INFO] Outputs will be written to: {out_dir}")
    
    print("\n2. Checking Variants")
    print("-" * 40)
    variants = config.get("variants", [])
    for v in variants:
        if v in VARIANTS:
            print(f"[PASS] Valid variant: {v}")
        else:
            print(f"[FAIL] Invalid variant: {v}")
            
    print("\n3. Checking Personas")
    print("-" * 40)
    if personas_ok:
        personas_dict = load_personas(personas_path)
        personas = list(personas_dict.values())
        print(f"Loaded {len(personas)} personas.")
        
        # Check macro_domain and archetypes
        domain_counts = Counter([p.macro_domain for p in personas])
        for domain, count in domain_counts.items():
            print(f"  Domain: {domain} -> {count} personas")
            
        for domain in domain_counts.keys():
            domain_personas = [p for p in personas if p.macro_domain == domain]
            archetype_prefixes = set()
            for p in domain_personas:
                # Find matching prefix from expected
                matched = False
                for prefix in EXPECTED_ARCHETYPES.get(domain, set()):
                    if p.persona_id.startswith(prefix):
                        archetype_prefixes.add(prefix)
                        matched = True
                        break
                if not matched:
                    print(f"  [WARNING] Persona {p.persona_id} does not match any expected archetype prefix for domain {domain}")
            
            missing_archs = EXPECTED_ARCHETYPES.get(domain, set()) - archetype_prefixes
            if missing_archs:
                print(f"  [FAIL] Domain {domain} is missing these archetypes: {missing_archs}")
            else:
                print(f"  [PASS] Domain {domain} has all 6 expected archetypes.")

        # Check history fields
        for p in personas:
            has_obs = len(p.observable_history) > 0
            has_dist = len(p.distractor_history) > 0
            if not has_obs:
                print(f"  [FAIL] Persona {p.persona_id} has empty observable_history")
            if not has_dist:
                print(f"  [FAIL] Persona {p.persona_id} has empty distractor_history")
            if has_obs and has_dist:
                # check chronological interleaving
                timestamps = [h.get("timestamp", "") for h in p.observable_history + p.distractor_history]
                if any(not ts for ts in timestamps):
                    print(f"  [WARNING] Persona {p.persona_id} has history entries missing timestamps")
    else:
        print("Skipping personas check (file not found).")

    print("\n4. Checking Queries & Leakage")
    print("-" * 40)
    if queries_ok:
        queries = load_queries(queries_path)
        print(f"Loaded {len(queries)} queries.")
        
        for q in queries:
            # Data checks
            if not q.macro_domain:
                print(f"  [FAIL] Query {q.query_id} is missing macro_domain")
                continue
                
            if not q.search_required:
                print(f"  [WARNING] Query {q.query_id} has search_required=False")
                
            # Verify task_type and task_category
            domain = q.macro_domain
            valid_cats = DOMAINS_CATEGORIES.get(domain, {})
            all_valid_cats = valid_cats.get("retrieval_sensitive", []) + valid_cats.get("synthesis_sensitive", [])
            
            if q.task_category not in all_valid_cats:
                print(f"  [FAIL] Query {q.query_id} has invalid category {q.task_category} for domain {domain}")
                
            # Verify expected_personalization_stage
            expected_stage = "fanout_retrieval" if q.task_type == "retrieval_sensitive" else "final_synthesis"
            if q.expected_personalization_stage != expected_stage:
                print(f"  [FAIL] Query {q.query_id} has stage {q.expected_personalization_stage}, expected {expected_stage}")
                
            # Verify metadata fields
            meta = q.metadata
            required_meta = [
                "why_search_required", "why_persona_dependent", "must_use", "should_not_use",
                "desired_fanout_keywords", "desired_synthesis_behavior", "positive_persona_signals",
                "distractor_signals_to_ignore", "gold_retrieval_intent", "gold_synthesis_intent",
                "risk_level", "safety_expectations"
            ]
            
            for field in required_meta:
                if field not in meta or not meta[field]:
                    print(f"  [FAIL] Query {q.query_id} is missing metadata field: {field}")
            
            if not q.persona_relevant_dimensions:
                print(f"  [FAIL] Query {q.query_id} has empty persona_relevant_dimensions")

            # Leakage checks
            query_text = q.query
            must_use = meta.get("must_use", [])
            
            # 1. Warn if query text simply repeats the persona description
            persona_id = meta.get("persona_id")
            if persona_id and personas_ok and persona_id in personas_dict:
                p_desc = personas_dict[persona_id].description
                overlap = word_overlap(query_text, p_desc)
                if overlap > 0.5:
                    print(f"  [WARNING] Query {q.query_id} has high word overlap ({overlap:.2%}) with its persona description. Possible leakage/copy-paste.")
            
            # 2. Warn if all must_use constraints are explicitly present in the query text
            all_present = True
            for constraint in must_use:
                # check if constraint words are in the query
                constraint_words = set(constraint.lower().split())
                query_words = set(query_text.lower().split())
                if not constraint_words.intersection(query_words):
                    all_present = False
                    break
            if must_use and all_present:
                print(f"  [WARNING] Query {q.query_id} explicitly contains all 'must_use' constraints. It might not be Level-2 ambiguous.")

            # 3. Warn if the query text contains too many exact latent constraints
            hits = 0
            for constraint in must_use:
                if constraint.lower() in query_text.lower():
                    hits += 1
            if hits > 1:
                print(f"  [WARNING] Query {q.query_id} directly contains {hits} exact 'must_use' constraints in the query text.")

        print("[INFO] Queries validation complete.")
    else:
        print("Skipping queries check (file not found).")
        
    print("\n5. Checking V4 Mixed Fanout Logs (if runs exist)")
    print("-" * 40)
    runs_path = config.get("outputs", {}).get("runs_path")
    if not os.path.isabs(runs_path): runs_path = os.path.join(_PROJECT_ROOT, runs_path)
    
    if os.path.exists(runs_path):
        v4_runs_checked = 0
        v4_failures = 0
        with open(runs_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    run = json.loads(line)
                    if run.get("variant") == "V4_mixed_fanout":
                        v4_runs_checked += 1
                        branches = run.get("fanout_branches", [])
                        btypes = set(b.get("branch_type") for b in branches)
                        expected_btypes = {"generic", "personalized", "constraint", "disconfirming"}
                        missing = expected_btypes - btypes
                        if missing:
                            v4_failures += 1
                            print(f"  [FAIL] Run {run.get('run_id')} (V4) is missing branch types: {missing}")
                            
        if v4_runs_checked > 0:
            print(f"Checked {v4_runs_checked} V4 runs. Failures: {v4_failures}/{v4_runs_checked}")
            if v4_failures == 0:
                print("  [PASS] All V4 runs contain generic, personalized, constraint, and disconfirming branches.")
        else:
            print("No V4 runs found in the run log yet.")
    else:
        print("No run log found at runs_path. Run some benchmark tasks first to populate logs.")

if __name__ == "__main__":
    main()
