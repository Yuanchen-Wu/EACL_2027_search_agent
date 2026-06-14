# Final Response Evaluation Summary

## Overall Results by Variant
| Variant | N | Intent | Pers. Target Use | Overpersonalization | Specificity | Safety | Overall |
|---------|---|--------|------------------|---------------------|-------------|--------|---------|
| V0_generic_single | 10 | 1.90 | 1.60 | 1.00 | 2.50 | 5.00 | 1.90 |
| V1_generic_fanout | 10 | 2.80 | 2.80 | 1.20 | 3.20 | 5.00 | 2.80 |
| V2_synthesis_only_personalization | 10 | 4.50 | 4.50 | 1.00 | 4.50 | 5.00 | 4.50 |
| V3_personalized_fanout | 10 | 4.90 | 5.00 | 1.60 | 5.00 | 5.00 | 4.80 |
| V4_mixed_fanout | 10 | 5.00 | 5.00 | 1.70 | 5.00 | 5.00 | 4.60 |

## Contrasts
- **V2 - V1 on overall:** +1.70 (Synthesis-only personalization vs generic fanout)
- **V3 - V2 on overall:** +0.30 (Personalized fanout vs Synthesis-only)
- **V4 - V3 on overall:** -0.20 (Mixed fanout vs Personalized fanout)
- **V4 - V1 on overall:** +1.80 (Mixed fanout vs Generic fanout)
- **V3 - V2 on personalization_target_use:** +0.50
- **V4 - V3 on overpersonalization:** +0.10 (more overpersonalization. *Note: lower is better for this metric*)

## Results by Domain
| Variant | Domain | N | Intent | Pers. Target Use | Overpersonalization | Specificity | Safety | Overall |
|---------|--------|---|--------|------------------|---------------------|-------------|--------|---------|
| V0_generic_single | ecommerce | 2 | 1.00 | 1.00 | 1.00 | 2.00 | 5.00 | 1.00 |
| V0_generic_single | education | 4 | 2.00 | 2.00 | 1.00 | 2.50 | 5.00 | 2.00 |
| V0_generic_single | health_medical | 4 | 2.25 | 1.50 | 1.00 | 2.75 | 5.00 | 2.25 |
| V1_generic_fanout | ecommerce | 2 | 2.00 | 2.00 | 1.00 | 2.50 | 5.00 | 2.00 |
| V1_generic_fanout | education | 4 | 2.50 | 2.50 | 1.00 | 3.00 | 5.00 | 2.50 |
| V1_generic_fanout | health_medical | 4 | 3.50 | 3.50 | 1.50 | 3.75 | 5.00 | 3.50 |
| V2_synthesis_only_personalization | ecommerce | 2 | 4.50 | 5.00 | 1.00 | 4.50 | 5.00 | 4.50 |
| V2_synthesis_only_personalization | education | 4 | 4.50 | 4.50 | 1.00 | 4.50 | 5.00 | 4.50 |
| V2_synthesis_only_personalization | health_medical | 4 | 4.50 | 4.25 | 1.00 | 4.50 | 5.00 | 4.50 |
| V3_personalized_fanout | ecommerce | 2 | 5.00 | 5.00 | 2.50 | 5.00 | 5.00 | 4.50 |
| V3_personalized_fanout | education | 4 | 5.00 | 5.00 | 1.00 | 5.00 | 5.00 | 5.00 |
| V3_personalized_fanout | health_medical | 4 | 4.75 | 5.00 | 1.75 | 5.00 | 5.00 | 4.75 |
| V4_mixed_fanout | ecommerce | 2 | 5.00 | 5.00 | 3.50 | 5.00 | 5.00 | 3.50 |
| V4_mixed_fanout | education | 4 | 5.00 | 5.00 | 1.25 | 5.00 | 5.00 | 5.00 |
| V4_mixed_fanout | health_medical | 4 | 5.00 | 5.00 | 1.25 | 5.00 | 5.00 | 4.75 |

## Results by Query Type
| Variant | Query Type | N | Intent | Pers. Target Use | Overpersonalization | Specificity | Safety | Overall |
|---------|------------|---|--------|------------------|---------------------|-------------|--------|---------|
| V0_generic_single | personalization_helpful | 8 | 1.88 | 1.75 | 1.00 | 2.62 | 5.00 | 1.88 |
| V0_generic_single | personalization_required | 2 | 2.00 | 1.00 | 1.00 | 2.00 | 5.00 | 2.00 |
| V1_generic_fanout | personalization_helpful | 8 | 2.62 | 2.62 | 1.25 | 3.12 | 5.00 | 2.62 |
| V1_generic_fanout | personalization_required | 2 | 3.50 | 3.50 | 1.00 | 3.50 | 5.00 | 3.50 |
| V2_synthesis_only_personalization | personalization_helpful | 8 | 4.38 | 4.38 | 1.00 | 4.38 | 5.00 | 4.38 |
| V2_synthesis_only_personalization | personalization_required | 2 | 5.00 | 5.00 | 1.00 | 5.00 | 5.00 | 5.00 |
| V3_personalized_fanout | personalization_helpful | 8 | 4.88 | 5.00 | 1.62 | 5.00 | 5.00 | 4.75 |
| V3_personalized_fanout | personalization_required | 2 | 5.00 | 5.00 | 1.50 | 5.00 | 5.00 | 5.00 |
| V4_mixed_fanout | personalization_helpful | 8 | 5.00 | 5.00 | 1.75 | 5.00 | 5.00 | 4.62 |
| V4_mixed_fanout | personalization_required | 2 | 5.00 | 5.00 | 1.50 | 5.00 | 5.00 | 4.50 |

