import argparse
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add src to path so we can import from search_agent
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from search_agent.llm_gemini import call_gemini

def write_jsonl(path, data):
    with open(path, 'w') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')

PERSONA_ARCHETYPES = [
    {
        "id_prefix": "budget_nonstem_student",
        "description": "budget-constrained non-STEM student",
        "observable_history": ["how to save money in college", "best free things to do near campus", "liberal arts major career paths"]
    },
    {
        "id_prefix": "budget_highstem_phd",
        "description": "budget-conscious high-STEM PhD / research intern",
        "observable_history": ["pytorch memory optimization", "cheap cloud GPU instances", "how to live on a stipend"]
    },
    {
        "id_prefix": "modbudget_nonstem_switcher",
        "description": "moderate-budget non-STEM career switcher",
        "observable_history": ["bootcamps vs self-taught coding", "product management interview prep", "resume tips for transitioning teachers"]
    },
    {
        "id_prefix": "highbudget_highstem_pro",
        "description": "high-budget high-STEM professional",
        "observable_history": ["kubernetes scaling best practices", "top tier noise cancelling headphones", "business class flight deals"]
    },
    {
        "id_prefix": "family_modbudget",
        "description": "family-constrained moderate-budget user",
        "observable_history": ["kid friendly weekend trips", "affordable family meal prep", "balancing work and parenting"]
    },
    {
        "id_prefix": "intl_newgrad",
        "description": "international student / new-grad job seeker",
        "observable_history": ["H1B visa process for software engineers", "OPT extension timeline", "companies that sponsor international students"]
    }
]

def generate_personas(num_users):
    personas = []
    for i in range(num_users):
        arch = PERSONA_ARCHETYPES[i % len(PERSONA_ARCHETYPES)]
        pid = f"{arch['id_prefix']}_{str(uuid.uuid4())[:6]}"
        personas.append({
            "persona_id": pid,
            "description": arch["description"],
            "attributes": {
                "demographics": {"profile": arch["description"]},
                "latent_profile": {}
            },
            "observable_history": [{"timestamp": "2023-10-01T10:00:00Z", "content": q} for q in arch["observable_history"]],
            "distractor_history": []
        })
    return personas

QUERY_GEN_PROMPT = """You are generating synthetic probing queries for a search agent benchmark.
The goal is to generate queries conditioned on the user's persona, such that the expected personalization behavior is clear.

Persona: {persona_desc}
Task Type: {task_type}
Task Category: {task_category}

Expected personalization stage for this task type: {expected_stage}

The query must:
- be natural for the persona,
- require or strongly justify search,
- expose a personalization opportunity,
- include non-empty `persona_relevant_dimensions`,
- include metadata explaining the hidden target.

Output ONLY valid JSON representing the query record. No markdown wrappers.
The JSON must follow this exact schema:
{{
  "query_id": "...",
  "persona_id": "{persona_id}",
  "query": "...",
  "task_type": "{task_type}",
  "task_category": "{task_category}",
  "search_required": true,
  "expected_personalization_stage": "{expected_stage}",
  "persona_relevant_dimensions": ["..."],
  "metadata": {{
    "why_search_required": "...",
    "why_persona_dependent": "...",
    "must_use": ["..."],
    "should_not_use": ["..."],
    "desired_fanout_keywords": ["..."],
    "desired_synthesis_behavior": ["..."]
  }}
}}

Examples of good outputs:

Example 1: retrieval-sensitive travel/dining (Persona: budget-constrained non-STEM student)
{{
  "query_id": "q_budget_student_travel_001",
  "persona_id": "budget_nonstem_student",
  "query": "Find a good affordable dinner place near campus this weekend that I can get to without driving.",
  "task_type": "retrieval_sensitive",
  "task_category": "travel_dining",
  "search_required": true,
  "expected_personalization_stage": "fanout_retrieval",
  "persona_relevant_dimensions": ["financial_background", "travel_dining_preferences", "transportation_constraint"],
  "metadata": {{
    "why_search_required": "The answer depends on current local restaurant options, prices, hours, and distance.",
    "why_persona_dependent": "The user is budget-constrained and does not want to drive, so search should prioritize affordable nearby options.",
    "must_use": ["affordable", "nearby", "no car / walkable or transit-accessible"],
    "should_not_use": ["expensive tasting menus", "places requiring a long drive", "generic citywide restaurant lists"],
    "desired_fanout_keywords": ["affordable dinner near campus", "walkable restaurants near campus", "cheap highly rated casual dinner"],
    "desired_synthesis_behavior": ["rank by affordability and convenience", "briefly explain why each option fits the user's constraints"]
  }}
}}

Example 2: retrieval-sensitive shopping/product recommendation (Persona: budget-conscious high-STEM PhD / research intern)
{{
  "query_id": "q_highstem_budget_laptop_001",
  "persona_id": "budget_highstem_phd",
  "query": "What laptop should I buy right now for ML research and coding if I care about value for money?",
  "task_type": "retrieval_sensitive",
  "task_category": "shopping_product_recommendation",
  "search_required": true,
  "expected_personalization_stage": "fanout_retrieval",
  "persona_relevant_dimensions": ["financial_background", "stem_background", "shopping_product_preferences"],
  "metadata": {{
    "why_search_required": "The answer depends on current laptop models, prices, specs, and reviews.",
    "why_persona_dependent": "The user has high technical needs but is value-conscious, so fan-out should retrieve technically capable but cost-effective options.",
    "must_use": ["ML/coding workload", "RAM/CPU/GPU tradeoffs", "value for money"],
    "should_not_use": ["generic student laptop lists", "luxury-only recommendations", "non-technical buying advice"],
    "desired_fanout_keywords": ["best value laptop for machine learning coding", "laptop 32GB RAM data science value", "MacBook vs ThinkPad for ML research"],
    "desired_synthesis_behavior": ["explain technical tradeoffs", "prioritize value rather than pure premium specs"]
  }}
}}

Example 3: synthesis-sensitive technical explanation (Persona: budget-constrained non-STEM student)
{{
  "query_id": "q_nonstem_attention_001",
  "persona_id": "budget_nonstem_student",
  "query": "Using current beginner-friendly ML learning resources, explain how attention in transformers works for someone with my background.",
  "task_type": "synthesis_sensitive",
  "task_category": "technical_explanation",
  "search_required": true,
  "expected_personalization_stage": "final_synthesis",
  "persona_relevant_dimensions": ["stem_background", "technical_explanation_preferences"],
  "metadata": {{
    "why_search_required": "The answer should be grounded in current high-quality educational resources.",
    "why_persona_dependent": "The core evidence can be similar, but the explanation must use simple analogies and avoid math-heavy notation.",
    "must_use": ["attention intuition", "queries/keys/values at a high level", "simple analogy"],
    "should_not_use": ["dense matrix notation", "assuming deep learning background", "overly technical derivation"],
    "desired_fanout_keywords": ["beginner transformer attention explanation", "attention mechanism simple analogy", "query key value attention tutorial"],
    "desired_synthesis_behavior": ["use plain language", "explain with an analogy", "avoid equations unless clearly explained"]
  }}
}}

Example 4: synthesis-sensitive personal decision strategy (Persona: international student / new-grad job seeker)
{{
  "query_id": "q_international_newgrad_strategy_001",
  "persona_id": "international_newgrad",
  "query": "Based on current machine learning engineer job requirements, should I focus next on side projects, interview prep, or more coursework?",
  "task_type": "synthesis_sensitive",
  "task_category": "personal_decision_strategy",
  "search_required": true,
  "expected_personalization_stage": "final_synthesis",
  "persona_relevant_dimensions": ["career_stage", "stem_background", "financial_background", "decision_strategy_context"],
  "metadata": {{
    "why_search_required": "The answer depends on current job requirements and hiring expectations.",
    "why_persona_dependent": "The user needs prioritization under time, budget, and job-search constraints.",
    "must_use": ["current MLE job expectations", "projects vs interview prep tradeoff", "new-grad constraints"],
    "should_not_use": ["generic motivational advice", "assuming unlimited time or money", "advice disconnected from current hiring requirements"],
    "desired_fanout_keywords": ["machine learning engineer new grad requirements", "MLE internship interview prep projects", "ML engineer portfolio projects hiring"],
    "desired_synthesis_behavior": ["give a prioritized plan", "make tradeoffs explicit", "adapt advice to user constraints"]
  }}
}}
"""

def generate_query_for_persona(persona, task_type, task_category):
    expected_stage = "fanout_retrieval" if task_type == "retrieval_sensitive" else "final_synthesis"
    prompt = QUERY_GEN_PROMPT.format(
        persona_desc=persona["description"],
        persona_id=persona["persona_id"],
        task_type=task_type,
        task_category=task_category,
        expected_stage=expected_stage
    )
    
    response = call_gemini(prompt)
    try:
        if response.startswith("```json"):
            response = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(response)
        data["query_id"] = f"q_{str(uuid.uuid4())[:8]}"
        return data
    except Exception as e:
        print(f"Failed to parse generation for {persona['persona_id']} - {task_category}: {e}")
        return None

def generate_queries(personas, queries_per_category):
    queries = []
    task_categories = {
        "retrieval_sensitive": [
            "travel_dining", 
            "shopping_product_recommendation"
        ],
        "synthesis_sensitive": [
            "technical_explanation",
            "personal_decision_strategy"
        ]
    }
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for p in personas:
            for t_type, categories in task_categories.items():
                for cat in categories:
                    for _ in range(queries_per_category):
                        futures.append(executor.submit(generate_query_for_persona, p, t_type, cat))
                        
        for future in as_completed(futures):
            res = future.result()
            if res:
                queries.append(res)
                
    return queries

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num_users", type=int, default=6)
    parser.add_argument("--queries_per_category", type=int, default=1)
    args = parser.parse_args()

    personas_path = os.path.join(PROJECT_ROOT, "data", "generated", "synthetic_personas_v1.jsonl")
    queries_path = os.path.join(PROJECT_ROOT, "data", "generated", "synthetic_queries_v1.jsonl")
    
    os.makedirs(os.path.dirname(personas_path), exist_ok=True)
    
    personas = generate_personas(args.num_users)
    queries = generate_queries(personas, args.queries_per_category)
    
    write_jsonl(personas_path, personas)
    write_jsonl(queries_path, queries)
    
    print(f"Saved {len(personas)} personas to {personas_path}")
    print(f"Saved {len(queries)} queries to {queries_path}")

if __name__ == "__main__":
    main()
