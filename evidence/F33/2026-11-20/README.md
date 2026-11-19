# F33 · Place nouns and the category: measured, not adopted

## Result

**Not adopted.** Rules classifier 0.2.0 is in the code but no policy uses it; policy v0.5.0 keeps classifier 0.1.0.
`comparison.json` is produced by `scripts/run_classifier_comparison.py`.

## The problem

Classifier 0.1.0 scores every category by its words, place nouns included. "Overflowing bin at the community hall"
scores waste for the bin and facilities for the hall; the tie lowers confidence and the request goes to a person even
though it reports one problem.

Classifier 0.2.0 adds one step: when the issue lexicon finds problem wording for **exactly one** service, that service
wins the category, so place nouns stop outvoting it.

## What it did at the Gate

Policy v0.5.0 compared with the same policy using classifier 0.2.0 (built in memory, nothing else changed):

| Set | Classifier | Single-issue: right category | Single-issue: passed | Multi-issue that passed as one draft |
|---|---|---|---|---|
| Own set (seen) | 0.1.0 | 10 of 14 | 6 | 0 |
| | 0.2.0 | 14 of 14 | 8 | 0 |
| First blind set (seen) | 0.1.0 | 6 of 16 | 0 | 0 |
| | 0.2.0 | 14 of 16 | 1 | 0 |
| **Second blind set (unseen)** | 0.1.0 | 11 of 20 | 0 | **0** |
| | 0.2.0 | 17 of 20 | 0 | **2** (MC-07, MC-20) |

Classifier 0.2.0 names the right service far more often, but it saves at most two escalations per set, and on unseen
wording it creates a new failure. In MC-07 ("dunnies … feral, no water in the taps … bins out the front overflow") and
MC-20 (a van "parked in the loading zone" for four days, plus overflowing bins) the lexicon finds only the bins. With
one problem service found, 0.2.0 becomes confident it is a waste request and the Gate passes a waste draft; the toilet
and the van are lost. Classifier 0.1.0 escalates both, because the toilet and van words keep its confidence low.

The project's rule since F28 and F31 is that a change may not let through a request that should reach a person. So
v0.5.0 keeps 0.1.0, and the cost of place nouns (some single-issue requests go to a person) stays.

## What would fix it

The same idea is safe only when the issue detector rarely misses a second problem. Either a model lists the issues
(the multi-intent extraction noted in F25 and F31), or 0.2.0 changes only the category label shown to the officer and
leaves the confidence check alone. Both need a new blind set to measure; the second blind set has now been seen.
