import argparse
import json
import os
import sys
import uuid
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add src to path so we can import from search_agent
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from search_agent.llm_gemini import call_gemini

def write_jsonl(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

def generate_timestamps(n_obs: int, n_dist: int):
    base_time = datetime.datetime(2026, 6, 1, 9, 0, 0)
    total_items = n_obs + n_dist
    timestamps = []
    for i in range(total_items):
        t = base_time + datetime.timedelta(hours=12 * i)
        timestamps.append(t.strftime("%Y-%m-%dT%H:%M:%SZ"))
    
    obs_ts = []
    dist_ts = []
    for idx, ts in enumerate(timestamps):
        if idx % 2 == 0:
            if len(obs_ts) < n_obs:
                obs_ts.append(ts)
            else:
                dist_ts.append(ts)
        else:
            if len(dist_ts) < n_dist:
                dist_ts.append(ts)
            else:
                obs_ts.append(ts)
    return obs_ts, dist_ts

ARCHETYPES_BY_DOMAIN = {
    "education": [
        {
            "id_prefix": "budget_nonstem_student",
            "description": "budget-constrained non-STEM student",
            "demographics": {"profile": "budget-constrained non-STEM student", "education_level": "Undergraduate", "field_of_study": "History", "annual_budget": "$1,200 for learning resources"},
            "latent_profile": {"budget_constraint": "high", "technical_background": "low", "learning_preference": "conceptual, visual, no-code/low-code"},
            "observable_history": [
                "how to save money in college",
                "best free things to do near campus",
                "liberal arts major career paths",
                "affordable textbook rentals online",
                "free study planner apps"
            ],
            "distractor_history": [
                "best cheap air fryer",
                "how to fix squeaky door",
                "bus routes downtown"
            ]
        },
        {
            "id_prefix": "budget_highstem_phd",
            "description": "budget-conscious high-STEM PhD / research intern",
            "demographics": {"profile": "budget-conscious high-STEM PhD / research intern", "education_level": "PhD Candidate", "field_of_study": "Computer Science", "annual_budget": "limited stipend"},
            "latent_profile": {"budget_constraint": "high", "technical_background": "high", "learning_preference": "rigorous, mathematical, self-hosted, open-source"},
            "observable_history": [
                "pytorch memory optimization",
                "cheap cloud GPU instances",
                "how to live on a stipend",
                "arxiv paper summary tool open source",
                "latex template for thesis"
            ],
            "distractor_history": [
                "best coffee beans medium roast",
                "noise cancelling headphones under 100",
                "local bouldering gym reviews"
            ]
        },
        {
            "id_prefix": "modbudget_nonstem_switcher",
            "description": "moderate-budget non-STEM career switcher",
            "demographics": {"profile": "moderate-budget non-STEM career switcher", "education_level": "Post-graduate / Career Switcher", "field_of_study": "Product Management (formerly Education)", "annual_budget": "$5,000 for bootcamps or courses"},
            "latent_profile": {"budget_constraint": "moderate", "technical_background": "medium-low", "learning_preference": "structured, industry-aligned, job-prep focused"},
            "observable_history": [
                "bootcamps vs self-taught coding",
                "product management interview prep",
                "resume tips for transitioning teachers",
                "part-time MBA program reviews",
                "agile certification comparison"
            ],
            "distractor_history": [
                "best espresso machine under 500",
                "ergonomic office chair reviews",
                "standing desk converter"
            ]
        },
        {
            "id_prefix": "highbudget_highstem_pro",
            "description": "high-budget high-STEM professional",
            "demographics": {"profile": "high-budget high-STEM professional", "education_level": "Master's / Professional", "field_of_study": "Software Engineering", "annual_budget": "Sponsored by employer / high personal budget"},
            "latent_profile": {"budget_constraint": "none", "technical_background": "high", "learning_preference": "advanced, fast-paced, enterprise-scale, authoritative sources"},
            "observable_history": [
                "kubernetes scaling best practices",
                "top tier noise cancelling headphones",
                "business class flight deals",
                "system design interview for staff engineers",
                "enterprise architecture patterns"
            ],
            "distractor_history": [
                "best golf courses nearby",
                "mechanical keyboard custom build",
                "smart home hub comparison"
            ]
        },
        {
            "id_prefix": "family_modbudget",
            "description": "family-constrained moderate-budget user",
            "demographics": {"profile": "family-constrained moderate-budget user", "education_level": "Bachelor's", "field_of_study": "Business Administration", "annual_budget": "Moderate family budget, high time constraint"},
            "latent_profile": {"budget_constraint": "moderate", "time_constraint": "high", "learning_preference": "flexible, bite-sized, family-compatible, practical"},
            "observable_history": [
                "kid friendly weekend trips",
                "affordable family meal prep",
                "balancing work and parenting",
                "online degrees for working parents",
                "flexible study schedules"
            ],
            "distractor_history": [
                "best family minivan",
                "dishwasher detergent reviews",
                "easy weeknight dinner recipes"
            ]
        },
        {
            "id_prefix": "intl_newgrad",
            "description": "international student / new-grad job seeker",
            "demographics": {"profile": "international student / new-grad job seeker", "education_level": "Master's", "field_of_study": "Data Science", "annual_budget": "limited savings, high visa urgency"},
            "latent_profile": {"budget_constraint": "high", "visa_urgency": "high", "learning_preference": "placement-focused, interview-heavy, immigration-aware"},
            "observable_history": [
                "H1B visa process for software engineers",
                "OPT extension timeline",
                "companies that sponsor international students",
                "leetcode medium pattern guide",
                "cold emailing recruiters templates"
            ],
            "distractor_history": [
                "cheap international calling app",
                "best winter coats for students",
                "affordable gyms near me"
            ]
        }
    ],
    "legal_info": [
        {
            "id_prefix": "tenant_low_income_eviction_risk",
            "description": "Low-income renter worried about housing stability, limited budget, prefers free/low-cost legal aid and practical next steps.",
            "demographics": {"profile": "Low-income renter", "income_level": "Low", "housing_status": "Renting", "location": "Under-specified (needs local resources)"},
            "latent_profile": {"legal_context": "housing / tenant rights", "budget_constraint": "low", "risk_level": "high", "preferred_support": "legal aid, government resources, tenant union resources", "avoid": "expensive private attorney-first advice"},
            "observable_history": [
                "tenant rights notice to quit",
                "free legal aid eviction help",
                "rent assistance program near me",
                "security deposit not returned",
                "how to dispute landlord charges"
            ],
            "distractor_history": [
                "best cheap air fryer",
                "bus routes downtown",
                "how to fix squeaky door"
            ]
        },
        {
            "id_prefix": "immigrant_worker_visa_uncertain",
            "description": "Immigrant worker confused about employment, visa timing, and workplace documentation; needs jurisdiction/status-sensitive information.",
            "demographics": {"profile": "Immigrant worker", "visa_status": "Employment-based visa (H1B/L1/OPT)", "workplace": "Tech/Services"},
            "latent_profile": {"legal_context": "immigration + employment", "risk_level": "high", "needs": "official sources, deadlines, documentation checklist", "avoid": "confident immigration advice without caveats"},
            "observable_history": [
                "work authorization renewal timeline",
                "employer sponsorship documents",
                "changing jobs on work visa",
                "unpaid wages immigrant worker rights",
                "uscis processing times"
            ],
            "distractor_history": [
                "best hiking shoes",
                "cheap international calling app",
                "learn guitar beginner"
            ]
        },
        {
            "id_prefix": "small_business_owner_contracts",
            "description": "Small business owner/freelancer handling client contracts, invoices, liability, and basic compliance without in-house counsel.",
            "demographics": {"profile": "Small business owner / Freelancer", "business_type": "Single-member LLC / Sole proprietorship", "industry": "Creative/Consulting"},
            "latent_profile": {"legal_context": "contracts / small business", "budget_constraint": "moderate", "needs": "templates, clauses, dispute prevention, when to hire attorney", "avoid": "one-size-fits-all contract advice"},
            "observable_history": [
                "freelance contract template",
                "LLC liability basics",
                "client refusing to pay invoice",
                "small business terms and conditions",
                "indemnity clause explanation"
            ],
            "distractor_history": [
                "espresso machine comparison",
                "office chair under 200",
                "best podcast microphone"
            ]
        },
        {
            "id_prefix": "divorced_parent_custody_schedule",
            "description": "Parent trying to understand custody scheduling, child support basics, and documentation; emotionally sensitive but needs practical information.",
            "demographics": {"profile": "Divorced parent", "dependents": "1 or more children", "relationship_status": "Divorced/Separated"},
            "latent_profile": {"legal_context": "family law", "risk_level": "high", "needs": "jurisdiction-aware general info, documentation, mediation/legal aid options", "avoid": "escalating conflict unnecessarily"},
            "observable_history": [
                "joint custody holiday schedule examples",
                "child support modification documents",
                "parenting plan template",
                "co-parent communication app court",
                "mediation vs family court"
            ],
            "distractor_history": [
                "kid friendly dinner ideas",
                "used minivan reviews",
                "summer camp near me"
            ]
        },
        {
            "id_prefix": "employee_noncompete_layoff",
            "description": "Recently laid-off employee trying to understand severance, non-compete/non-solicit terms, unemployment, and negotiation options.",
            "demographics": {"profile": "Laid-off employee", "former_role": "Professional/Office", "employment_status": "Unemployed / Severance period"},
            "latent_profile": {"legal_context": "employment law", "risk_level": "medium_high", "needs": "state-specific enforceability, practical negotiation checklist", "avoid": "telling user to sign or refuse without lawyer review"},
            "observable_history": [
                "severance agreement review",
                "non compete enforceability by state",
                "unemployment eligibility after layoff",
                "negotiate severance package",
                "non solicit clause vs non compete"
            ],
            "distractor_history": [
                "resume format 2026",
                "best running shoes",
                "cheap moving boxes"
            ]
        },
        {
            "id_prefix": "privacy_conscious_online_creator",
            "description": "Online creator worried about copyright, takedowns, privacy, defamation, and platform policies.",
            "demographics": {"profile": "Online creator / Influencer", "platforms": "YouTube/TikTok/Substack", "content_type": "Video / Writing"},
            "latent_profile": {"legal_context": "copyright / privacy / online speech", "risk_level": "medium", "needs": "platform policy + legal information distinction", "avoid": "encouraging aggressive legal threats"},
            "observable_history": [
                "DMCA takedown counter notice",
                "using music in YouTube video",
                "defamation online comments",
                "doxxing legal options",
                "fair use guidelines for commentary"
            ],
            "distractor_history": [
                "camera lens for vlogging",
                "thumbnail design tips",
                "best portable light"
            ]
        }
    ],
    "personal_finance": [
        {
            "id_prefix": "paycheck_to_paycheck_credit_rebuild",
            "description": "User living paycheck-to-paycheck, trying to rebuild credit and avoid fees/debt traps.",
            "demographics": {"profile": "Paycheck-to-paycheck worker", "income_level": "Low-moderate", "financial_health": "Rebuilding credit", "savings": "Minimal (< $500)"},
            "latent_profile": {"financial_context": "credit rebuilding / budgeting", "risk_tolerance": "low", "liquidity_constraint": "high", "needs": "low-fee options, emergency fund, debt prioritization", "avoid": "high-risk investing, expensive products"},
            "observable_history": [
                "how to improve credit score after missed payments",
                "secured credit card no annual fee",
                "budgeting when income is irregular",
                "avoid overdraft fees",
                "credit builder loans worth it"
            ],
            "distractor_history": [
                "cheap meal prep",
                "used bike repair",
                "free local events"
            ]
        },
        {
            "id_prefix": "high_income_low_time_tech_worker",
            "description": "High-income busy professional with stock compensation, taxes, and automation needs; willing to pay for convenience but wants rational tradeoffs.",
            "demographics": {"profile": "High-income tech worker", "income_level": "High", "compensation": "Base salary + RSUs / Equity", "time_availability": "Very low"},
            "latent_profile": {"financial_context": "high income / equity compensation", "risk_tolerance": "medium_high", "time_constraint": "high", "needs": "tax-aware planning, automation, fee comparison", "avoid": "generic beginner budgeting advice"},
            "observable_history": [
                "RSU tax withholding",
                "backdoor Roth IRA",
                "automated investing vs advisor",
                "mega backdoor Roth 401k",
                "tax loss harvesting guide"
            ],
            "distractor_history": [
                "noise cancelling headphones",
                "business class flight deals",
                "meal delivery reviews"
            ]
        },
        {
            "id_prefix": "first_gen_college_grad_student_loans",
            "description": "New graduate with student loans, first full-time job, limited family financial guidance.",
            "demographics": {"profile": "First-generation college graduate", "education_level": "Bachelor's", "employment_status": "Entry-level professional", "debt": "Student loans ($30k+)"},
            "latent_profile": {"financial_context": "early-career / student loans", "risk_tolerance": "low_medium", "needs": "debt repayment vs emergency fund vs retirement tradeoff", "avoid": "assuming high financial literacy"},
            "observable_history": [
                "SAVE plan student loans",
                "student loan repayment calculator",
                "first job 401k contribution",
                "rent affordability rule",
                "what is a high yield savings account"
            ],
            "distractor_history": [
                "work wardrobe budget",
                "cheap apartment decor",
                "meal prep for beginners"
            ]
        },
        {
            "id_prefix": "young_family_homebuyer",
            "description": "Moderate-income family considering buying a home, daycare costs, insurance, and emergency reserves.",
            "demographics": {"profile": "Young family / Aspiring homebuyer", "dependents": "Toddler / Infant", "income_level": "Moderate", "goal": "Purchase first home in 1-2 years"},
            "latent_profile": {"financial_context": "family budgeting / homebuying", "risk_tolerance": "low_medium", "constraints": "dependents, emergency fund, housing stability", "avoid": "house-poor recommendation"},
            "observable_history": [
                "mortgage preapproval checklist",
                "rent vs buy calculator",
                "childcare tax credit",
                "term life insurance for parents",
                "how much down payment for house"
            ],
            "distractor_history": [
                "stroller comparison",
                "family vacation ideas",
                "weeknight dinner recipes"
            ]
        },
        {
            "id_prefix": "near_retirement_catchup",
            "description": "Late-career user close to retirement, worried about catch-up savings, Social Security timing, Medicare, and portfolio risk.",
            "demographics": {"profile": "Near-retirement worker", "age": "58-62", "retirement_timeline": "5-7 years", "career_stage": "Late career"},
            "latent_profile": {"financial_context": "retirement planning", "risk_tolerance": "low_medium", "needs": "sequence risk, tax buckets, healthcare costs", "avoid": "aggressive growth-only advice"},
            "observable_history": [
                "Social Security claiming age",
                "401k catch up contribution limit",
                "Medicare enrollment timeline",
                "retirement withdrawal sequence risk",
                "conservative portfolio allocation age 60"
            ],
            "distractor_history": [
                "walking shoes for seniors",
                "garden planning",
                "cruise packing list"
            ]
        },
        {
            "id_prefix": "freelancer_irregular_income_taxes",
            "description": "Freelancer/gig worker with irregular income, quarterly taxes, insurance, and business expense tracking.",
            "demographics": {"profile": "Freelancer / Self-employed", "employment_type": "1099 contractor", "income_stability": "Irregular / Variable"},
            "latent_profile": {"financial_context": "self-employment / taxes", "risk_tolerance": "medium", "needs": "cash-flow buffers, tax deadlines, retirement account comparison", "avoid": "assuming W2 paycheck stability"},
            "observable_history": [
                "quarterly estimated tax payment",
                "self employed health insurance deduction",
                "SEP IRA vs solo 401k",
                "track business expenses app",
                "how to budget with variable income"
            ],
            "distractor_history": [
                "laptop stand review",
                "coworking space near me",
                "invoice template design"
            ]
        }
    ]
}

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

QUERY_GEN_PROMPT = """You are generating synthetic probing queries for a search agent benchmark.
The goal is to generate a natural, UNDER-SPECIFIED (Level-2 ambiguous) query conditioned on the user's persona, such that the expected personalization behavior is clear, but the query itself does NOT explicitly reveal all constraints.

Persona details:
- ID: {persona_id}
- Domain: {macro_domain}
- Description: {persona_desc}
- Stated Demographics: {persona_demographics}
- Stated History (Observable + Distractor): {persona_history}

Task Type: {task_type}
Task Category: {task_category}
Expected personalization stage for this task type: {expected_stage}

CRITICAL GENERATION RULES:
1. The surface query must be natural and UNDER-SPECIFIED. Do not copy or leak all personalization constraints into the query.
2. The surface query may include at most one obvious constraint.
3. At least two important personalization constraints must be inferable ONLY from the persona/history, NOT from the query itself. The query must sound natural and ambiguous.
4. Every query must be search-worthy (requires looking up external facts/resources).
5. Every query must include non-empty `persona_relevant_dimensions`.
6. Every query must include both:
   - metadata.positive_persona_signals: What signals from demographics/history the agent should pay attention to.
   - metadata.distractor_signals_to_ignore: What signals from demographics/history are unrelated and should be ignored.
7. Every query must include:
   - metadata.gold_retrieval_intent: Detailed description of what a good search retrieval should target.
   - metadata.gold_synthesis_intent: Detailed description of how the final synthesis should adapt to the user's latent profile and constraints.
8. Every query must include:
   - metadata.risk_level: low|medium|high
   - metadata.safety_expectations: Detailed safety guidelines for the domain.

DOMAIN-SPECIFIC SAFETY & CONTENT RULES:
- For legal_info:
  * The query should NOT ask for illegal conduct.
  * The final answer should distinguish legal information from legal advice, provide jurisdiction-aware source-seeking, issue-spotting, and next-step checklists.
  * It must avoid pretending to be a lawyer, avoid definitive legal conclusions, and recommend consulting a qualified lawyer/legal aid when the decision is high-stakes (risk_level: high).
  * Search/Retrieval should prefer official government/court/legal aid sources when relevant.
- For personal_finance:
  * Avoid stock-picking, get-rich-quick tasks, or specific stock recommendations.
  * Focus on consumer finance, retirement, taxes, credit, loans, mortgages, insurance, and budgeting.
  * The final answer should give educational financial information, explain tradeoffs, ask for missing constraints when necessary, and avoid making personalized investment recommendations as if it were a fiduciary/advisor. It should avoid risky product pushing, overconfident return predictions, and one-size-fits-all advice.
  * Search/Retrieval should prefer official, regulatory, established consumer finance, or reputable financial education sources where appropriate.

Output ONLY valid JSON representing the query record. No markdown wrappers.
The JSON must follow this exact schema:
{{
  "query_id": "...",
  "persona_id": "{persona_id}",
  "query": "...",
  "task_type": "{task_type}",
  "task_category": "{task_category}",
  "macro_domain": "{macro_domain}",
  "search_required": true,
  "expected_personalization_stage": "{expected_stage}",
  "persona_relevant_dimensions": ["..."],
  "metadata": {{
    "why_search_required": "...",
    "why_persona_dependent": "...",
    "must_use": ["..."],
    "should_not_use": ["..."],
    "desired_fanout_keywords": ["..."],
    "desired_synthesis_behavior": ["..."],
    "positive_persona_signals": ["..."],
    "distractor_signals_to_ignore": ["..."],
    "gold_retrieval_intent": "...",
    "gold_synthesis_intent": "...",
    "risk_level": "low|medium|high",
    "safety_expectations": "..."
  }}
}}

EXAMPLES OF GOOD OUTPUTS ACROSS DOMAINS:

=== LEGAL retrieval-sensitive example ===
Persona: tenant_low_income_eviction_risk
Task Type: retrieval_sensitive
Task Category: jurisdiction_resource_lookup
Expected Stage: fanout_retrieval
JSON:
{{
  "query_id": "q_legal_retrieval_001",
  "persona_id": "tenant_low_income_eviction_risk",
  "query": "What should I look up first if my landlord gave me a notice and I’m not sure what it means?",
  "task_type": "retrieval_sensitive",
  "task_category": "jurisdiction_resource_lookup",
  "macro_domain": "legal_info",
  "search_required": true,
  "expected_personalization_stage": "fanout_retrieval",
  "persona_relevant_dimensions": ["housing_status", "income_level", "legal_context"],
  "metadata": {{
    "why_search_required": "Depends on local tenant rights laws, local eviction processes, and available legal aid organizations.",
    "why_persona_dependent": "The user is a low-income renter facing potential eviction, so search needs to target free/low-cost legal aid and tenant unions in the local jurisdiction, rather than expensive private attorneys.",
    "must_use": ["notice to quit meaning", "eviction process", "free tenant legal aid", "local rent assistance"],
    "should_not_use": ["private real estate defense attorney", "generic commercial landlord-tenant law portals", "high-fee legal consulting"],
    "desired_fanout_keywords": ["tenant rights notice to quit legal aid", "free eviction help near me", "local tenant union rent assistance", "court self help tenant eviction notice"],
    "desired_synthesis_behavior": ["explain what a notice to quit means broadly", "list step-by-step checklist of what to do", "provide pointers to free legal aid and local tenant organizations", "warn about key deadlines and advise consulting local tenant aid"],
    "positive_persona_signals": ["tenant rights notice to quit", "free legal aid eviction help", "rent assistance program near me"],
    "distractor_signals_to_ignore": ["best cheap air fryer", "how to fix squeaky door", "bus routes downtown"],
    "gold_retrieval_intent": "Find official court or local legal aid resources explaining tenant rights upon receiving an eviction notice/notice to quit, specifically focusing on low-income support options.",
    "gold_synthesis_intent": "Clearly explain the distinction between a landlord notice and a court filing, outline a practical next-steps checklist, and strongly guide the user to local free legal resources and tenant unions, keeping the tone supportive and objective.",
    "risk_level": "high",
    "safety_expectations": "Do not give definitive legal advice on whether they will be evicted. Emphasize that rules vary by state/city, outline the generic process, and urge them to contact local tenant aid immediately due to high stakes."
  }}
}}

=== LEGAL synthesis-sensitive example ===
Persona: employee_noncompete_layoff
Task Type: synthesis_sensitive
Task Category: legal_decision_strategy
Expected Stage: final_synthesis
JSON:
{{
  "query_id": "q_legal_synthesis_001",
  "persona_id": "employee_noncompete_layoff",
  "query": "Can you explain what I should pay attention to before signing this kind of agreement?",
  "task_type": "synthesis_sensitive",
  "task_category": "legal_decision_strategy",
  "macro_domain": "legal_info",
  "search_required": true,
  "expected_personalization_stage": "final_synthesis",
  "persona_relevant_dimensions": ["employment_status", "legal_context"],
  "metadata": {{
    "why_search_required": "Requires retrieving current legal standards around non-compete enforceability, severance agreement terms, and negotiation strategies.",
    "why_persona_dependent": "The user was recently laid off and has a severance agreement with a non-compete. The explanation must prioritize severance negotiation and state-specific non-compete enforceability guidelines.",
    "must_use": ["severance agreement review", "non-compete enforceability", "release of claims", "unemployment eligibility"],
    "should_not_use": ["standard new-hire employment contract review", "generic motivation", "definitive advice to sign or not sign"],
    "desired_fanout_keywords": ["severance agreement non compete clause enforceability", "laid off employee severance negotiation checklist", "unemployment benefits eligibility severance package"],
    "desired_synthesis_behavior": ["explain what to look for in a severance agreement", "detail non-compete/non-solicit distinction and state-level enforceability trends", "outline practical negotiation checklist", "recommend consulting an employment lawyer before signing"],
    "positive_persona_signals": ["severance agreement review", "non compete enforceability by state", "unemployment eligibility after layoff"],
    "distractor_signals_to_ignore": ["resume format 2026", "best running shoes", "cheap moving boxes"],
    "gold_retrieval_intent": "Find general legal guides on reviewing severance packages, negotiating severance, and how state laws govern non-compete enforceability after a layoff.",
    "gold_synthesis_intent": "Synthesize a comprehensive guide for reviewing a severance package post-layoff, explaining the legal implications of non-competes, highlighting the trade-offs of releasing claims, and giving a step-by-step negotiation strategy.",
    "risk_level": "medium_high",
    "safety_expectations": "Clearly state that this is educational information, not legal counsel. Encourage reviewing the agreement with an employment attorney, especially regarding state-specific non-compete laws."
  }}
}}

=== FINANCE retrieval-sensitive example ===
Persona: paycheck_to_paycheck_credit_rebuild
Task Type: retrieval_sensitive
Task Category: product_or_program_comparison
Expected Stage: fanout_retrieval
JSON:
{{
  "query_id": "q_finance_retrieval_001",
  "persona_id": "paycheck_to_paycheck_credit_rebuild",
  "query": "What card or account should I compare if I’m trying to get back on track?",
  "task_type": "retrieval_sensitive",
  "task_category": "product_or_program_comparison",
  "macro_domain": "personal_finance",
  "search_required": true,
  "expected_personalization_stage": "fanout_retrieval",
  "persona_relevant_dimensions": ["financial_health", "income_level", "liquidity_constraint"],
  "metadata": {{
    "why_search_required": "Requires searching current financial products (secured credit cards, credit-builder accounts) and their interest rates/fees.",
    "why_persona_dependent": "The user is rebuilding credit on a tight budget. Search must focus on no-fee secured cards and low-fee credit-builder tools, avoiding high-fee products or premium cards.",
    "must_use": ["secured credit card no annual fee", "credit builder account", "no overdraft fee checking", "low interest rate / credit building"],
    "should_not_use": ["premium rewards credit cards", "high-fee credit cards", "unsecured high-interest subprime cards", "investment brokerage accounts"],
    "desired_fanout_keywords": ["best secured credit cards no annual fee", "credit builder accounts low fees", "how to build credit score cards", "avoid overdraft fees checking accounts"],
    "desired_synthesis_behavior": ["compare no-annual-fee secured cards", "explain how credit-builder accounts work", "warn against subprime fee-harvester cards", "prioritize building a small emergency fund"],
    "positive_persona_signals": ["how to improve credit score after missed payments", "secured credit card no annual fee", "avoid overdraft fees"],
    "distractor_signals_to_ignore": ["cheap meal prep", "used bike repair", "free local events"],
    "gold_retrieval_intent": "Find reputable, low-cost secured credit cards and credit-builder programs with transparent terms and no annual fees.",
    "gold_synthesis_intent": "Present a clear comparison of credit-building options tailored to a tight budget, explaining how they work and warning about fees or interest trap risks, keeping advice educational.",
    "risk_level": "low",
    "safety_expectations": "Do not promise credit score increases or push specific commercial products. Focus on educational advice, emphasizing low fees and responsible payment habits."
  }}
}}

=== FINANCE synthesis-sensitive example ===
Persona: first_gen_college_grad_student_loans
Task Type: synthesis_sensitive
Task Category: financial_decision_strategy
Expected Stage: final_synthesis
JSON:
{{
  "query_id": "q_finance_synthesis_001",
  "persona_id": "first_gen_college_grad_student_loans",
  "query": "How should I think about which money goal to prioritize first?",
  "task_type": "synthesis_sensitive",
  "task_category": "financial_decision_strategy",
  "macro_domain": "personal_finance",
  "search_required": true,
  "expected_personalization_stage": "final_synthesis",
  "persona_relevant_dimensions": ["career_stage", "financial_context", "financial_literacy"],
  "metadata": {{
    "why_search_required": "Requires retrieving current student loan repayment programs (like SAVE), standard 401k match guidelines, and interest rate contexts.",
    "why_persona_dependent": "The user is an early-career graduate with student loans and limited financial guidance. The response must explain how to balance emergency savings, employer 401k match, and student loan repayment in a simple, beginner-friendly way without assuming advanced knowledge.",
    "must_use": ["emergency fund basics", "employer 401k match priority", "student loan repayment vs investing", "rent budgeting"],
    "should_not_use": ["advanced investment strategies", "complex tax-shelter advice", "assuming high financial literacy"],
    "desired_fanout_keywords": ["prioritize emergency fund vs student loans vs 401k", "student loan SAVE plan repayment guidelines", "beginner financial order of operations"],
    "desired_synthesis_behavior": ["provide a clear, step-by-step priority list (order of operations)", "explain the 'free money' of 401k match simply", "weigh paying down loans vs saving", "keep the language accessible and reassuring"],
    "positive_persona_signals": ["SAVE plan student loans", "student loan repayment calculator", "first job 401k contribution"],
    "distractor_signals_to_ignore": ["work wardrobe budget", "cheap apartment decor", "meal prep for beginners"],
    "gold_retrieval_intent": "Find reputable personal finance frameworks on the 'financial order of operations' for recent graduates balancing debt and savings.",
    "gold_synthesis_intent": "Create an easy-to-follow financial prioritization guide for a recent graduate, comparing student loan repayment options with building emergency reserves and capturing 401k matching.",
    "risk_level": "low_medium",
    "safety_expectations": "Emphasize that this is financial education, not fiduciary advice. Encourage checking their specific loan interest rates and employer benefit details."
  }}
}}

=== EDUCATION retrieval-sensitive example ===
Persona: budget_highstem_phd
Task Type: retrieval_sensitive
Task Category: shopping_product_recommendation
Expected Stage: fanout_retrieval
JSON:
{{
  "query_id": "q_edu_retrieval_001",
  "persona_id": "budget_highstem_phd",
  "query": "What GPU should I buy for local ML experiments?",
  "task_type": "retrieval_sensitive",
  "task_category": "shopping_product_recommendation",
  "macro_domain": "education",
  "search_required": true,
  "expected_personalization_stage": "fanout_retrieval",
  "persona_relevant_dimensions": ["stem_background", "financial_background", "shopping_product_preferences"],
  "metadata": {{
    "why_search_required": "Depends on current GPU pricing, VRAM specs, CUDA compatibility, and market availability.",
    "why_persona_dependent": "The user has high technical needs (ML research) but a tight stipend budget, so search needs to find cost-effective, VRAM-heavy options (like used RTX 3090 or specific RTX 40-series cards) rather than luxury workstations or gaming-only rankings.",
    "must_use": ["VRAM capacity", "CUDA compatibility", "cost-effective/used market options", "value for money for deep learning"],
    "should_not_use": ["premium pre-built gaming PCs", "extremely expensive enterprise GPUs like H100", "generic gaming benchmarks"],
    "desired_fanout_keywords": ["best budget GPU for deep learning 24GB VRAM", "used RTX 3090 for machine learning value", "RTX 4060 Ti 16GB ML performance price"],
    "desired_synthesis_behavior": ["highlight VRAM as the primary bottleneck for LLM/ML", "compare price-per-GB of VRAM across recommended GPUs", "suggest looking at the used market for older 24GB cards", "give clear technical justifications for each recommendation"],
    "positive_persona_signals": ["pytorch memory optimization", "cheap cloud GPU instances", "how to live on a stipend"],
    "distractor_signals_to_ignore": ["best coffee beans medium roast", "noise cancelling headphones under 100", "local bouldering gym reviews"],
    "gold_retrieval_intent": "Find technical reviews and pricing benchmarks comparing budget-friendly GPUs for local machine learning workloads, emphasizing VRAM and CUDA support.",
    "gold_synthesis_intent": "Analyze and compare value GPU options for deep learning, explaining why VRAM matters, and providing a clear performance-to-cost recommendation tailored to a student stipend.",
    "risk_level": "low",
    "safety_expectations": "Ensure technical accuracy regarding CUDA and PyTorch support. Do not recommend outdated cards that lack driver support."
  }}
}}

=== EDUCATION synthesis-sensitive example ===
Persona: budget_nonstem_student
Task Type: synthesis_sensitive
Task Category: technical_explanation
Expected Stage: final_synthesis
JSON:
{{
  "query_id": "q_edu_synthesis_001",
  "persona_id": "budget_nonstem_student",
  "query": "Can you explain APIs in a way that helps me finish a class project?",
  "task_type": "synthesis_sensitive",
  "task_category": "technical_explanation",
  "macro_domain": "education",
  "search_required": true,
  "expected_personalization_stage": "final_synthesis",
  "persona_relevant_dimensions": ["stem_background", "technical_explanation_preferences"],
  "metadata": {{
    "why_search_required": "Requires finding current educational explanations, simple APIs for projects, and beginner-friendly tutorials.",
    "why_persona_dependent": "The user is a non-STEM student. The retrieved evidence might be standard technical documentation, but the final synthesis must explain the concepts using everyday analogies (like a restaurant waiter) and no-code/low-code terms, avoiding heavy programming jargon.",
    "must_use": ["simple waiter/restaurant analogy", "request and response basics", "how to use a simple API without coding expertise"],
    "should_not_use": ["complex HTTP header specifications", "programming language-specific code snippets in Python/JS", "advanced security/oauth details"],
    "desired_fanout_keywords": ["what is an API simple explanation beginners", "API analogy restaurant waiter", "no code API tutorial for students"],
    "desired_synthesis_behavior": ["use a clear, relatable analogy", "explain the core flow (Request -> Process -> Response) in plain English", "list a few fun, free, simple APIs they can try (like weather or cat facts)", "keep the tone encouraging and non-technical"],
    "positive_persona_signals": ["how to save money in college", "free study planner apps"],
    "distractor_signals_to_ignore": ["best cheap air fryer", "how to fix squeaky door", "bus routes downtown"],
    "gold_retrieval_intent": "Find highly rated, beginner-friendly educational articles or videos explaining APIs to non-technical students.",
    "gold_synthesis_intent": "Synthesize a highly intuitive, jargon-free explanation of APIs, utilizing a clear analogy and showing how a non-programmer can understand and interact with them.",
    "risk_level": "low",
    "safety_expectations": "Ensure the explanation is conceptually accurate despite the simplification. Encourage experimenting with free, safe public APIs."
  }}
}}
"""

def generate_personas_for_domain(domain: str, num_users: int) -> list:
    archs = ARCHETYPES_BY_DOMAIN[domain]
    personas = []
    for i in range(num_users):
        arch = archs[i % len(archs)]
        # Use clean text-based ID. Append index only if we need to create duplicates beyond the 6 archetypes.
        if num_users <= len(archs):
            pid = arch['id_prefix']
        else:
            pid = f"{arch['id_prefix']}_{i+1}"
        
        # Generate interleaved timestamps
        n_obs = len(arch["observable_history"])
        n_dist = len(arch["distractor_history"])
        obs_ts, dist_ts = generate_timestamps(n_obs, n_dist)
        
        obs_history = [
            {"timestamp": obs_ts[idx], "content": q} 
            for idx, q in enumerate(arch["observable_history"])
        ]
        dist_history = [
            {"timestamp": dist_ts[idx], "content": q} 
            for idx, q in enumerate(arch["distractor_history"])
        ]
        
        personas.append({
            "persona_id": pid,
            "macro_domain": domain,
            "description": arch["description"],
            "attributes": {
                "demographics": arch["demographics"],
                "latent_profile": arch["latent_profile"]
            },
            "observable_history": obs_history,
            "distractor_history": dist_history
        })
    return personas

def generate_query_for_persona(persona, task_type, task_category):
    expected_stage = "fanout_retrieval" if task_type == "retrieval_sensitive" else "final_synthesis"
    demographics_str = json.dumps(persona["attributes"].get("demographics", {}), ensure_ascii=False)
    
    # Interleave history for the prompt view
    merged_history = list(persona["observable_history"]) + list(persona["distractor_history"])
    merged_history = sorted(merged_history, key=lambda h: str(h.get("timestamp", "")))
    history_lines = []
    for h in merged_history:
        ts = h.get("timestamp", "")
        content = h.get("content", "")
        history_lines.append(f"[{ts}] {content}")
    history_str = "\n".join(history_lines)
    
    prompt = QUERY_GEN_PROMPT.format(
        persona_id=persona["persona_id"],
        macro_domain=persona["macro_domain"],
        persona_desc=persona["description"],
        persona_demographics=demographics_str,
        persona_history=history_str,
        task_type=task_type,
        task_category=task_category,
        expected_stage=expected_stage
    )
    
    response = call_gemini(prompt)
    try:
        if response.startswith("```json"):
            response = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(response)
        data["persona_id"] = persona["persona_id"]
        data["macro_domain"] = persona["macro_domain"]
        return data
    except Exception as e:
        print(f"Failed to parse generation for {persona['persona_id']} - {task_category}: {e}")
        return None

def generate_queries_for_personas(personas, queries_per_category):
    queries = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for p in personas:
            domain = p["macro_domain"]
            task_categories = DOMAINS_CATEGORIES[domain]
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
    parser.add_argument("--macro_domain", default="education", choices=["education", "legal_info", "personal_finance", "all"])
    args = parser.parse_args()

    domains_to_generate = []
    if args.macro_domain == "all":
        domains_to_generate = ["education", "legal_info", "personal_finance"]
    else:
        domains_to_generate = [args.macro_domain]

    all_generated_personas = []
    all_generated_queries = []

    # Generate all personas and queries
    for domain in domains_to_generate:
        print(f"\nGenerating data for domain: {domain}...")
        personas = generate_personas_for_domain(domain, args.num_users)
        queries = generate_queries_for_personas(personas, args.queries_per_category)
        
        all_generated_personas.extend(personas)
        all_generated_queries.extend(queries)

    # Assign clean, globally sequential query IDs
    for idx, q in enumerate(all_generated_queries, start=1):
        q["query_id"] = f"q_{idx}"

    # Write unified root-level files
    root_personas_path = os.path.join(PROJECT_ROOT, "data", "synthetic_personas_v1.jsonl")
    root_queries_path = os.path.join(PROJECT_ROOT, "data", "synthetic_queries_v1.jsonl")
    
    write_jsonl(root_personas_path, all_generated_personas)
    write_jsonl(root_queries_path, all_generated_queries)
    print(f"\n[Unified] Saved all {len(all_generated_personas)} personas to {root_personas_path}")
    print(f"[Unified] Saved all {len(all_generated_queries)} queries to {root_queries_path}")

    # Write domain-specific files
    for domain in domains_to_generate:
        domain_personas = [p for p in all_generated_personas if p["macro_domain"] == domain]
        domain_queries = [q for q in all_generated_queries if q["macro_domain"] == domain]
        
        domain_personas_path = os.path.join(PROJECT_ROOT, "data", domain, f"{domain}_synthetic_personas_v1.jsonl")
        domain_queries_path = os.path.join(PROJECT_ROOT, "data", domain, f"{domain}_synthetic_queries_v1.jsonl")
        
        write_jsonl(domain_personas_path, domain_personas)
        write_jsonl(domain_queries_path, domain_queries)
        
        print(f"[{domain}] Saved {len(domain_personas)} personas to {domain_personas_path}")
        print(f"[{domain}] Saved {len(domain_queries)} queries to {domain_queries_path}")

if __name__ == "__main__":
    main()
