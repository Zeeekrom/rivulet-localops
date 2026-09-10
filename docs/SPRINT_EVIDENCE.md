# Sprint Evidence

| Evidence field | Value |
|---|---|
| Date | 2026-09-09 |
| Release | v0.4.1 |
| Environment | Python 3.12 in a clean local virtual environment and GitHub-hosted `ubuntu-latest`, installed from `requirements-dev.lock` |

This document records implemented results verified locally and by GitHub Actions. Hosted CI is build evidence, not an application cloud deployment. It does not claim real-user validation, production adoption or generative-model accuracy.

## Foundation / Sprint 0

Goal: establish a runnable, explainable service-request diagnosis baseline.

| Acceptance item | Result | Evidence |
|---|---|---|
| Health and diagnosis API | Pass | `GET /health`, `POST /api/v1/diagnose` |
| Deterministic service taxonomy | Pass | Eight categories plus general fallback |
| Explainable priority and missing information | Pass | Response contains matched terms, policy rule, confidence and review flag |
| Public asset integration | Pass | 727-feature Hobart litter-bin GeoJSON snapshot with metadata and EPSG:4326 output |
| Baseline automated tests | Pass | Three original tests |
| Repeatable labelled cases | Pass with claim restriction | 12 self-authored uncomplicated cases; regression only |

## Sprint 1 — Policy Gate

Goal: ensure that a proposed waste/litter draft action cannot proceed unless it satisfies an explicitly approved demonstration policy.

| Acceptance item | Result |
|---|---|
| Versioned, machine-readable policy pack | Pass |
| Policy is impossible to load as unlabelled non-synthetic content | Pass |
| Valid in-scope draft action with location and asset evidence | `pass` |
| Missing coordinates | `reject` with specific missing fields |
| Emergency/high-risk request | `escalate` |
| Out-of-scope category | `escalate` |
| Low category confidence | `escalate` |
| Unapproved real-submission action | `reject` |
| Policy/version/hash and rule-level reasons returned | Pass |
| External business-system write | Intentionally absent |

Sprint 1 verification brought the suite to 11 passing tests. The policy is a synthetic portfolio policy, not adopted council policy.

## Sprint 2 — Accountable decision history

Goal: make every submitted automated suggestion traceable, reviewable, replayable and stoppable.

| Acceptance item | Result |
|---|---|
| Submission creates a queryable event record | Pass |
| Request, policy and event hashes recorded | Pass |
| Provider version, evidence, owner and event context recorded | Pass |
| Pending/reviewed queue | Pass |
| Accept/override/escalate creates a new event | Pass |
| Original Gate result remains unchanged after review | Pass |
| Accountable owner cannot self-review | Pass |
| Rejected/escalated Gate result cannot be directly accepted | Pass |
| Replay compares policy hash/version, provider and rule outcomes | Pass |
| In-place ledger modification is detected | Pass |
| New automated processing stops when integrity fails | Pass |
| Provider kill switch survives application restart | Pass |
| Disabled provider routes submission to a recorded manual fallback | Pass |

Sprint 2 verification brought the suite to 18 passing tests.

### Sprint 2 review finding and patch

The disposable Windows review run initially failed during cleanup because several read-only SQLite connections used
transaction context managers without being explicitly closed. Python's SQLite context manager commits or rolls back a
transaction but does not close the connection. Release `v0.3.1` closes those connections explicitly and adds a reusable
runner covering query, append-only override, replay, kill switch, manual fallback, tamper detection and fail-closed writes.

The rerun passed all review checks and successfully cleaned up both disposable databases. See
[`evidence/F08/2026-09-09`](../evidence/F08/2026-09-09/README.md).

## Sprint 2.5A — Contracted sources and analytics mart

Goal: turn the governed ledger and public reference data into a repeatable, truth-labelled analytical model.

| Acceptance item | Result |
|---|---|
| D1/D2/D6 source manifests and SHA-256 verification | Pass |
| D2 dated official raw snapshot and explicit Windows-1252 decoding | Pass |
| Completeness/uniqueness/validity/consistency/integrity/timeliness/volume/shape profile | 15 pass, 4 warn, 0 fail |
| Normalized D2 key collision preserved rather than silently merged | Pass; pinned by test |
| Fixed-seed D6 generated through provider → Gate → ledger | 316 events; stable hash; integrity pass |
| Star-schema mart | 14 non-empty tables |
| Source/event/count/FK/truth-class reconciliations | 8 of 8 pass |
| KPI numerator/denominator/grain/filter/null/truth caveats | Defined; no invented targets |
| Full local verification | 25 tests passed; 12-case regression unchanged |

See [`evidence/F06/2026-09-09`](../evidence/F06/2026-09-09/README.md) and
[`evidence/F09/2026-09-09`](../evidence/F09/2026-09-09/README.md). The D6 Gate mix and review timing are deliberately
generated regression fixtures. They are not real workload, effectiveness, service-level or productivity evidence.

## Hosted CI evidence

Prior v0.3.x locked installs and checks completed successfully in GitHub Actions. The first v0.4.0 hosted run failed
because Git line-ending normalization changed D1/D2 snapshot bytes after their manifest hashes were created. v0.4.1
marks byte-hashed upstream snapshots as non-text so fresh checkouts preserve exact bytes. The failed run remains public
evidence and the v0.4.0 tag was not rewritten. A hosted workflow runs on a disposable runner; it does not deploy the API
or prove production operations.

## Reproduction

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\scripts\verify.ps1
```

Observed release output:

```text
25 passed
{
  "cases": 12,
  "category_accuracy": 1.0,
  "priority_accuracy": 1.0,
  "failures": []
}
```

The word “accuracy” in the evaluator's JSON field is retained for compatibility with the script. Because the 12 cases are self-authored and uncomplicated, the correct interpretation is “no regression against this small fixture set,” not measured model or production accuracy.

## Data provenance

| Data | Truth status | Public claim |
|---|---|---|
| Hobart litter-bin asset snapshot | Real public reference data | Feature count, retrieval timestamp, endpoint and CRS are recorded in metadata |
| Townsville request-for-service snapshot | Real public aggregate reference data | Monthly aggregate context only; not Hobart demand or individual requests |
| Request and review events | Synthetic demonstration data | Never described as resident or council operational history |
| Gate policy | Synthetic demonstration policy | Never described as official or council-approved policy |
| Priority targets | Demonstration rules | Never described as observed service performance |

## Claim ledger

| Claim | Supported now? | Boundary |
|---|---|---|
| The local workflow is reproducible | Yes | Clean Python environment and automated checks |
| The Gate blocks defined unsafe or incomplete cases | Yes | Only the coded synthetic policy and fixtures |
| Decision/review history is append-only through the application API | Yes | Local SQLite implementation |
| The hash chain detects tested in-place modification | Yes | Not an immutable external audit store |
| Provider automation can be stopped and manually routed | Yes | Same-process local operations control |
| Identities are authenticated and authorised | No | IDs are asserted fields only |
| The classifier is effective on real council requests | No | No real requests or independent labels |
| The system is production-ready or council-approved | No | Independent portfolio prototype |
| The system is deployed to Azure or an enterprise Windows environment | No | Later planned profiles |
| Synthetic D6 rates describe council performance | No | Fixed scenario mix validates calculations and control-path coverage only |

## Known verification warning

The current dependency set emits two upstream deprecation warnings from the FastAPI/Starlette TestClient compatibility layer. They do not fail the suite, but dependency migration should be handled as a tracked maintenance change rather than hidden.
