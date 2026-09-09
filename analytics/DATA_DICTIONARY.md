# Analytics mart data dictionary

> Mart version: `1.0.0` · Build: `python scripts/build_analytics_mart.py`

This mart is deliberately split into two truth classes. `real_public_reference` contains public reference data from
City of Hobart assets (D1) and Townsville aggregate request counts (D2). `synthetic_operational` contains fixed-seed
Rivulet decisions, reviews and control events (D6). A visual may compare system structure across those sources, but it
must not present D2 as Hobart demand or D6 as observed council performance.

## Relationship map

```text
dim_source ──< dim_asset
    │          └──< fact_decision >── dim_category
    │                    │   │        dim_policy
    │                    │   └──────> dim_provider
    │                    ├──< fact_gate_rule
    │                    └──< fact_review
    ├──< fact_manual_fallback >────── dim_provider
    ├──< fact_reference_request_volume >── dim_townsville_category_variant
    └──< fact_quality_check

dim_date ──< every dated fact
```

## Fact grains

| Table | Grain | Truth class | Primary use |
|---|---|---|---|
| `fact_reference_request_volume` | One publisher-supplied D2 CSV row | Real public reference | Monthly service-volume context; aggregate only |
| `fact_decision` | One D6 `decision.created` event | Synthetic operational | Gate status, category, priority, owner and evidence |
| `fact_gate_rule` | One decision × deterministic policy rule | Synthetic operational | Explain why a decision passed, rejected or escalated |
| `fact_review` | One append-only D6 review event | Synthetic operational | Independent review and override history |
| `fact_manual_fallback` | One D6 submission routed to manual handling | Synthetic operational | Kill-switch/fallback evidence |
| `fact_quality_check` | One automated D1/D2 quality assertion | Real public reference | Source health and warnings |

## Important modelling decisions

- D2 rows have a deterministic key that includes their source row number and all raw fields. One normalized
  group/category/month key collision is therefore retained as two published rows rather than silently summed.
- `dim_townsville_category_variant` is keyed from normalized group/category codes **and descriptions**. Category code
  alone is unsafe because the snapshot contains historical label drift.
- `dim_asset` uses D1 publisher identifiers. A decision may have no asset key when coordinates are absent or no asset
  falls inside the policy radius.
- D6 IDs and times are reproducible fixtures. The resulting rates test calculations and dashboard plumbing; they are
  not empirical accuracy, demand, benefit, productivity or SLA evidence.

The exact KPI formulas, denominators, null treatment and caveats are in `metric_dictionary.csv`. No performance target
is set because the project has no validated operational baseline or authorized stakeholder target.
