# Experiment Specification: Personalization-Placement Ablation

## Research Question
Where should persona/context be injected in a search-agent pipeline: query fan-out, final synthesis, both, or mixed fan-out?

## Variants
- **V0_generic_single**: Raw query only, no persona in fan-out or synthesis.
- **V1_generic_fanout**: Generic fan-out, no persona in synthesis.
- **V2_synthesis_only_personalization**: Generic fan-out, persona in synthesis only.
- **V3_personalized_fanout**: Persona-aware fan-out plus persona-aware synthesis.
- **V4_mixed_fanout**: Mixed fan-out (generic + personalized + constraint + disconfirming) plus persona-aware synthesis.

## Macro-Domains & Archetypes
The benchmark evaluates across three diverse macro-domains. Each macro-domain has six specific, realistic persona archetypes containing stated demographics, a latent profile (reserved for evaluation), and a chronological history comprising both relevant observable history and unrelated distractor history.

### 1. Education
- `budget_nonstem_student`: Budget-constrained non-STEM student.
- `budget_highstem_phd`: Budget-conscious high-STEM PhD candidate / research intern.
- `modbudget_nonstem_switcher`: Moderate-budget non-STEM career switcher.
- `highbudget_highstem_pro`: High-budget high-STEM professional.
- `family_modbudget`: Family-constrained moderate-budget user.
- `intl_newgrad`: International student / new-grad job seeker.

### 2. Legal Information (Non-Counseling)
- `tenant_low_income_eviction_risk`: Low-income renter worried about housing stability.
- `immigrant_worker_visa_uncertain`: Immigrant worker confused about visa/employment status.
- `small_business_owner_contracts`: Freelancer/owner handling compliance and contracts.
- `divorced_parent_custody_schedule`: Divorced parent navigating custody scheduling.
- `employee_noncompete_layoff`: Laid-off employee reviewing severance and non-compete terms.
- `privacy_conscious_online_creator`: Creator navigating copyright, DMCA, and speech privacy.

### 3. Personal Finance (Non-Advisory)
- `paycheck_to_paycheck_credit_rebuild`: Paycheck-to-paycheck user rebuilding credit.
- `high_income_low_time_tech_worker`: Busy tech professional managing equity and taxes.
- `first_gen_college_grad_student_loans`: First-gen graduate balancing student loans and savings.
- `young_family_homebuyer`: Moderate-income family planning first home purchase.
- `near_retirement_catchup`: Late-career worker catching up on retirement assets.
- `freelancer_irregular_income_taxes`: Self-employed worker managing irregular cash flows and quarterly taxes.

---

## Task Types & Domain-Specific Categories
Each query belongs to a dominant-bottleneck task type:

1. **`retrieval_sensitive`**: The main bottleneck is retrieving the right evidence (e.g., specific rules, budget-friendly options, or local resources).
2. **`synthesis_sensitive`**: The main bottleneck is adapting the explanation, prioritization, framing, or action plan to the user's background and constraints.

> [!NOTE]
> The task type is a dominant-bottleneck label used for post-hoc analysis. It is NOT binary, and it must NEVER be used to branch the agent's generation behavior at runtime.

### Category Mappings:
| Macro-Domain | Retrieval-Sensitive Category | Synthesis-Sensitive Category |
|---|---|---|
| **Education** | `travel_dining`, `shopping_product_recommendation` | `technical_explanation`, `personal_decision_strategy` |
| **Legal Info** | `jurisdiction_resource_lookup`, `form_policy_deadline_lookup` | `legal_issue_explanation`, `legal_decision_strategy` |
| **Personal Finance** | `product_or_program_comparison`, `current_rule_limit_lookup` | `financial_concept_explanation`, `financial_decision_strategy` |

---

## Key Diagnostic Features

### 1. Level-2 Under-specified Queries
Benchmark queries are intentionally written to be natural and under-specified (e.g., *"What GPU should I buy?"* rather than *"What under-$500 CUDA GPU should I buy as a PhD student?"*). This tests whether the agent can successfully infer constraints from the user context rather than relying on explicit query wording.

### 2. Distractor History
User histories include 3-5 plausible but completely unrelated distractor queries (e.g., shopping or appliance queries mixed with eviction risks or loan repayments). A robust agent must avoid over-personalizing search or final answers based on these distractors.

### 3. Domain Safety & Caveats
High-stakes domains (legal and finance) enforce strict safety rules:
- **Legal Info**: Answers must provide educational checklists and jurisdiction-aware caveats, avoid definitive legal conclusions, and recommend consulting qualified legal counsel for high-stakes decisions.
- **Personal Finance**: Answers must explain tradeoffs, avoid guaranteed return claims, acknowledge missing constraints, and avoid pushing specific commercial products.

---

## Multi-Stage Evaluation Protocol
The pipeline includes three distinct evaluators:
1. **Fan-out Query Evaluation** (`fanout_scores.jsonl`): Assesses the quality, diversity, and realism of generated search sub-queries.
2. **Retrieval-Level Evaluation** (`retrieval_scores.jsonl`): Assesses evidence relevance, persona constraint coverage, source quality, and distractor robustness of the retrieved search results *before* synthesis.
3. **Final Response Evaluation** (`final_response_scores.jsonl`): Assesses intent satisfaction, personalization utility, groundedness, and domain-specific safety.
