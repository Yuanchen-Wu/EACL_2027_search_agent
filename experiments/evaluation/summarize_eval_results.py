import argparse
import csv
import json
import os
import sys

def mean(values: list) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)

def format_float(val: float) -> str:
    return f"{val:.2f}"

def write_csv(path: str, headers: list, rows: list):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

def read_jsonl(path: str) -> list:
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows

def aggregate(runs: list, group_keys: list):
    """Group by keys and calculate means."""
    groups = {}
    for r in runs:
        if "error" in r:
            continue
        key = tuple(r.get(k, "unknown") for k in group_keys)
        if key not in groups:
            groups[key] = {
                "n": 0,
                "intent_satisfaction": [],
                "personalization_target_use": [],
                "overpersonalization": [],
                "specificity": [],
                "safety": [],
                "overall": []
            }
        groups[key]["n"] += 1
        scores = r.get("scores", {})
        for metric in ["intent_satisfaction", "personalization_target_use", "overpersonalization", "specificity", "safety", "overall"]:
            groups[key][metric].append(scores.get(metric, 1))
            
    results = []
    for key, data in groups.items():
        res = list(key)
        res.append(data["n"])
        for metric in ["intent_satisfaction", "personalization_target_use", "overpersonalization", "specificity", "safety", "overall"]:
            res.append(format_float(mean(data[metric])))
        results.append(res)
        
    return sorted(results)

def main():
    parser = argparse.ArgumentParser()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    parser.add_argument("--scores_path", type=str, default=os.path.join(script_dir, "generated", "final_response_scores.jsonl"))
    parser.add_argument("--output_dir", type=str, default=os.path.join(script_dir, "generated"))
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    
    runs = read_jsonl(args.scores_path)
    if not runs:
        print(f"Error: Scores file {args.scores_path} not found or empty.")
        sys.exit(1)
        
    print(f"Loaded {len(runs)} evaluation records.")
    
    headers_base = ["n", "mean_intent_satisfaction", "mean_personalization_target_use", "mean_overpersonalization", "mean_specificity", "mean_safety", "mean_overall"]
    
    # 1. By variant
    by_variant = aggregate(runs, ["variant"])
    write_csv(os.path.join(args.output_dir, "summary_by_variant.csv"), ["variant"] + headers_base, by_variant)
    
    # 2. By variant, domain
    by_variant_domain = aggregate(runs, ["variant", "domain"])
    write_csv(os.path.join(args.output_dir, "summary_by_variant_domain.csv"), ["variant", "domain"] + headers_base, by_variant_domain)
    
    # 3. By variant, query_type
    by_variant_qt = aggregate(runs, ["variant", "query_type"])
    write_csv(os.path.join(args.output_dir, "summary_by_variant_query_type.csv"), ["variant", "query_type"] + headers_base, by_variant_qt)

    # 4. Generate Markdown Summary
    md_path = os.path.join(args.output_dir, "summary.md")
    
    # Helper to get a metric for a variant from by_variant
    def get_metric(variant: str, metric_idx: int) -> float:
        for row in by_variant:
            if row[0] == variant:
                return float(row[metric_idx])
        return 0.0

    # metric indices in by_variant (variant is 0, n is 1)
    OVERALL_IDX = 7
    PT_USE_IDX = 3
    OVERPERS_IDX = 4

    with open(md_path, "w") as f:
        f.write("# Final Response Evaluation Summary\n\n")
        
        f.write("## Overall Results by Variant\n")
        f.write("| Variant | N | Intent | Pers. Target Use | Overpersonalization | Specificity | Safety | Overall |\n")
        f.write("|---------|---|--------|------------------|---------------------|-------------|--------|---------|\n")
        for row in by_variant:
            f.write(f"| {' | '.join(str(x) for x in row)} |\n")
        f.write("\n")
        
        f.write("## Contrasts\n")
        try:
            v0 = get_metric("V0_generic_single", OVERALL_IDX)
            v1 = get_metric("V1_generic_fanout", OVERALL_IDX)
            v2 = get_metric("V2_synthesis_only_personalization", OVERALL_IDX)
            v3 = get_metric("V3_personalized_fanout", OVERALL_IDX)
            v4 = get_metric("V4_mixed_fanout", OVERALL_IDX)
            
            f.write(f"- **V2 - V1 on overall:** {v2 - v1:+.2f} (Synthesis-only personalization vs generic fanout)\n")
            f.write(f"- **V3 - V2 on overall:** {v3 - v2:+.2f} (Personalized fanout vs Synthesis-only)\n")
            f.write(f"- **V4 - V3 on overall:** {v4 - v3:+.2f} (Mixed fanout vs Personalized fanout)\n")
            f.write(f"- **V4 - V1 on overall:** {v4 - v1:+.2f} (Mixed fanout vs Generic fanout)\n")
            
            v3_pt = get_metric("V3_personalized_fanout", PT_USE_IDX)
            v2_pt = get_metric("V2_synthesis_only_personalization", PT_USE_IDX)
            f.write(f"- **V3 - V2 on personalization_target_use:** {v3_pt - v2_pt:+.2f}\n")
            
            v4_op = get_metric("V4_mixed_fanout", OVERPERS_IDX)
            v3_op = get_metric("V3_personalized_fanout", OVERPERS_IDX)
            op_diff = v4_op - v3_op
            op_text = "more" if op_diff > 0 else "less"
            f.write(f"- **V4 - V3 on overpersonalization:** {op_diff:+.2f} ({op_text} overpersonalization. *Note: lower is better for this metric*)\n\n")
        except Exception as e:
            f.write(f"*Could not compute all contrasts: {e}*\n\n")

        f.write("## Results by Domain\n")
        f.write("| Variant | Domain | N | Intent | Pers. Target Use | Overpersonalization | Specificity | Safety | Overall |\n")
        f.write("|---------|--------|---|--------|------------------|---------------------|-------------|--------|---------|\n")
        for row in by_variant_domain:
            f.write(f"| {' | '.join(str(x) for x in row)} |\n")
        f.write("\n")
        
        f.write("## Results by Query Type\n")
        f.write("| Variant | Query Type | N | Intent | Pers. Target Use | Overpersonalization | Specificity | Safety | Overall |\n")
        f.write("|---------|------------|---|--------|------------------|---------------------|-------------|--------|---------|\n")
        for row in by_variant_qt:
            f.write(f"| {' | '.join(str(x) for x in row)} |\n")
        f.write("\n")

    print(f"Summary generated at {args.output_dir}")

if __name__ == "__main__":
    main()
