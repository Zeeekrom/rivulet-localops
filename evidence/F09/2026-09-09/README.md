# F09 · Deterministic analytics mart

## Outcome

PASS. The fixed-seed D6 generator produced 316 hash-chained events: 180 decisions, 120 independent reviews, 8
manual-fallback events and 8 provider-control events. Ledger integrity passed and a second generation produced the same
JSONL SHA-256.

The mart build produced 14 non-empty tables as CSV plus a reproducible SQLite build artifact. Eight reconciliations
passed, including source row counts, D2 aggregate count, contiguous ledger sequence, foreign keys and truth-class
separation. The SQLite files are generated locally and ignored by Git; inspectable source JSONL, CSV tables and build
report are versioned.

## Expected synthetic fixture metrics

- 188 submission attempts; 180 decisions and 8 manual fallbacks.
- Gate mix: 40% pass, 20% reject, 40% escalate.
- Review rate: 66.67%; override rate among reviews: 20.83%.
- Median review lag: 450 minutes.

These values are regression fixtures created by the scenario generator. They demonstrate calculations and control-path
coverage, not model accuracy, council workload, service quality, staffing productivity or an SLA baseline.
