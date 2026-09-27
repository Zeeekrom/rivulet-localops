# Sprint Evidence

| Evidence field | Value |
|---|---|
| Date | 2026-09-24 |
| Release | v0.7.1 |
| Environment | Python 3.12 and Node 24 locally; Docker Desktop 4.91.0 / Engine 29.8.0; GitHub-hosted verification; Azure Container Apps in New Zealand North |

This document records implemented results verified locally, by GitHub Actions and—only for the bounded public profile—on Azure. It does not claim real-user validation, production adoption or generative-model accuracy.

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

## Sprint 2.5B — Power BI provenance and assurance thin slice

Goal: make data provenance, quality, Gate outcomes and human-control paths inspectable without mixing public reference
data with synthetic operational fixtures.

| Acceptance item | Result |
|---|---|
| Deterministic PBIP/PBIR/TMDL project | 51 controlled files; build check passes |
| Report/model structure | 2 pages, 27 visuals, 7 Import tables, 29 measures, 8 relationships |
| Microsoft report validation | 0 errors, 0 warnings |
| Desktop Import refresh | 7 of 7 partitions succeeded |
| Live DAX/reference reconciliation | 13 of 13 exact; eligible/matched asset decisions 126/108 |
| Truth and claim boundaries | Visible on both pages; public reference and synthetic operational facts remain distinct |
| Desktop round-trip | Portable editor/culture/layout metadata generated; local cache/settings ignored; repository schemas restored before validation |
| Full local verification | 28 tests passed; 12-case regression unchanged; 8 of 8 mart reconciliations pass |

The first attempt to accept Desktop's normalized files was intentionally retained as a failed finding: Desktop removed
the PBIR `$schema`, causing `PBIR_JSON_FILE_NO_SCHEMA`. The generator is now the canonical serialization gate after
every Desktop edit or refresh. See [`F10 initial Review`](../evidence/F10/2026-09-10/README.md) and
[`F10 round-trip`](../evidence/F10/2026-09-12/README.md).

## Sprint 3 — Bounded read-only case-agent

Goal: prove that agent identity, provider, tool, data and resource permissions can fail closed independently of a
generative model.

| Acceptance item | Result |
|---|---|
| Server-selected agent identity and named demo owner | Pass |
| Versioned capability registry with canonical content hash | Pass |
| Five-minute invocation grant and four-call budget | Pass |
| Minimal allowlist | `case.read` for the current synthetic case; `asset.lookup` for the Hobart public reference |
| Shell and unlisted tool request | Denied and audited |
| Cross-case resource request | Denied and audited |
| Restricted data-class request | Denied and audited |
| Excess tool-call budget | Denied before provider execution |
| Provider identity/version mismatch | Failed closed before provider execution |
| Provider kill switch | HTTP 503 manual fallback and denied audit |
| Raw request text in agent audit payload | Absent |
| Full local verification | 35 tests passed; F18 12 of 12 checks; ledger integrity pass |

The disposable F18 review produced seven agent invocations: one completed, five denied and one failed before
execution. Along with one provider-control event, all eight ledger events formed a valid hash chain. See
[`evidence/F18/2026-09-12`](../evidence/F18/2026-09-12/README.md).

This is an L0 local control harness over the deterministic-rules provider, with credential mode `none`. It does not
authenticate callers, prove real object-level authorization, use a generative model, run the Gate, make a human
decision or execute a connector.

## Sprint 3.5 — Cloud-safe web demo (Review accepted)

Goal: turn the accepted controls into a public-facing portfolio console without exposing the internal application.

| Acceptance item | Result |
|---|---|
| React/TypeScript production build | Pass; 17 modules, 238.71 kB JS / 73.37 kB gzip, 22.21 kB CSS / 5.81 kB gzip |
| Separate public FastAPI profile | Pass; health/bootstrap/predefined scenario routes only |
| Visitor free text or arbitrary tool call | Intentionally absent |
| Scenario coverage | `pass`, `reject`, `escalate`, shell deny and cross-case deny |
| Internal/docs route boundary | 4 of 4 tested routes return 404 from the running container |
| Container identity and health | Pass; `10001:10001`, healthy |
| Oversized request | 413 with browser security headers |
| Bicep build | Pass with Bicep 0.47.16 |
| Azure policy-aware deployment | Pass; New Zealand North, HTTPS-only, 0.25 CPU/0.5 GiB, min 0/max 1, no client secret |
| Full local verification | 40 tests, 8/8 mart reconciliations, 51-file/88-check Power BI validation, regression and F18 pass |
| Live Azure endpoint | Pass; health/bootstrap/pass/deny, 4 negative routes, 413/security headers and desktop/mobile rendering |

See [`evidence/F22/2026-09-16`](../evidence/F22/2026-09-16/README.md). Docker Desktop 4.54.0 first failed
on its Windows AF_UNIX inference/secrets listener; it was updated in place to 4.91.0 without a factory reset. The first
reproducible-image build then exposed a missing runtime-lock allow-list entry, which was fixed before acceptance. Both
failed attempts are retained in F22 rather than overwritten by the successful run.

See [`evidence/F23/2026-09-24`](../evidence/F23/2026-09-24/README.md) for the live endpoint and the complete recovery
chain. The first deploy run failed closed on a custom GitHub OIDC subject mismatch. The second created the app but its
post-deploy assertion used a missing `python` command in the Azure CLI action image. The default-branch workflow now
uses `jq`; the third hosted run passed OIDC, what-if, idempotent deployment, health, four route denials and blocked-shell
denial. F23 does not prove production readiness, actual idle scale-to-zero, zero cost or remaining Student credit.

## Hosted CI evidence

Prior v0.3.x locked installs and checks completed successfully in GitHub Actions. The first v0.4.0 hosted run failed
because Git line-ending normalization changed D1/D2 snapshot bytes after their manifest hashes were created. v0.4.1
marks byte-hashed upstream snapshots as non-text so fresh checkouts preserve exact bytes. The failed run remains public
evidence and the v0.4.0 tag was not rewritten. Public commit `901358e9e468` passed both the main workflow
([run 34479182180](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34479182180)) and the `v0.4.1` tag workflow
([run 34479185154](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34479185154)). A hosted workflow runs on a
disposable runner; it does not deploy the API or prove production operations.

The v0.5.0 main and tag workflows both failed in a fresh Windows checkout because seven TMDL partitions embedded CRLF
CSV bytes while Git supplied LF CSV bytes: [main run 34673442580](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34673442580)
and [tag run 34673442408](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34673442408). The tag remains
unchanged. v0.5.1 canonicalizes embedded generated CSV to LF, hashes and checks that same representation, and adds a
CRLF/LF equivalence test. The staged-tree fresh-checkout preflight passed before release; v0.5.1 then passed
[main run 34673725103](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34673725103) and immutable
[tag run 34673726741](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34673726741). Local Desktop
refresh/DAX/screenshots cannot run on the hosted runner and remain separately versioned F10 evidence.

The v0.6.0 Sprint 3 release commit `d29260d3c3ecde57e2dfd2a7015ec56006594d48` passed both
[main run 34688891241](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34688891241) and immutable
[tag run 34688892353](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34688892353). Those hosted runs
reproduced the 35-test suite and deterministic evaluation in fresh Windows checkouts; they are not application
deployment or production-security evidence.

The v0.7.0 release passed hosted
[main verify 35092219320](https://github.com/Zeeekrom/rivulet-localops/actions/runs/35092219320),
[tag verify 35092221720](https://github.com/Zeeekrom/rivulet-localops/actions/runs/35092221720) and
[container/SBOM 35092221757](https://github.com/Zeeekrom/rivulet-localops/actions/runs/35092221757). The immutable tag
is retained. Azure preflight then showed the Student policy rejects Australia East, tenant users cannot register Entra
apps, and the API requires an omitted logging block rather than `destination: 'none'`. v0.7.1 uses an exact-RG managed
identity federation and New Zealand North. Its main/tag/container runs `35993932294`/`35993936061`/`35993936049`,
post-fix main run `35995184675` and successful deploy run `35995289399` are recorded in F23. Failed deploy runs
`35994259185` and `35994416800` remain public recovery evidence.

## Reproduction

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\scripts\verify.ps1
```

Observed release output:

```text
40 passed
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
| Agent capability registry | Synthetic control configuration | Demo identity, owner, provider binding and allowlists; not an external identity or signed policy system |
| Priority targets | Demonstration rules | Never described as observed service performance |

## Claim ledger

| Claim | Supported now? | Boundary |
|---|---|---|
| The local workflow is reproducible | Yes | Clean Python environment and automated checks |
| The Gate blocks defined unsafe or incomplete cases | Yes | Only the coded synthetic policy and fixtures |
| Decision/review history is append-only through the application API | Yes | Local SQLite implementation |
| The hash chain detects tested in-place modification | Yes | Not an immutable external audit store |
| Provider automation can be stopped and manually routed | Yes | Same-process local operations control |
| The bounded agent rejects the tested unauthorized capabilities | Yes | Local synthetic-case contract and deterministic provider only |
| Identities are authenticated and authorised | No | IDs are asserted fields only |
| The classifier is effective on real council requests | No | No real requests or independent labels |
| The system is production-ready or council-approved | No | Independent portfolio prototype |
| The bounded public profile is deployed to Azure | Yes | One New Zealand North Container Apps revision; F23, not a production-readiness claim |
| The system is deployed to an enterprise Windows environment | No | Windows lab remains a later slice |
| The public profile excludes tested internal routes | Yes | Local container and live Azure endpoint; four named negative routes, not a general penetration test |
| Synthetic D6 rates describe council performance | No | Fixed scenario mix validates calculations and control-path coverage only |

## Known verification warning

The current dependency set emits two upstream deprecation warnings from the FastAPI/Starlette TestClient compatibility layer. They do not fail the suite, but dependency migration should be handled as a tracked maintenance change rather than hidden.
