# F17 · AU-resident model provider — offline slice

## Result

**PASS — 8 of 8 offline checks. No model was called and no cost was incurred.** The Amazon Bedrock Claude
provider exists behind the existing `TriageProvider` boundary, but live calls are **locked in code**: the client
factory refuses to build a network client and the provider accepts only clients that declare themselves offline
fakes. The Anthropic/AWS SDKs are not installed, and a test fails if they appear.

| Check | Result |
|---|---|
| Live calls locked in code (`LIVE_MODEL_CALLS_LOCKED = True`); `--live` exits 3 | pass |
| Residency guard rejects `global.`, `us.`, `apac.`, bare `anthropic.` profiles and non-AU regions | pass |
| Offline model path matches the rules baseline on the 12 regression cases | pass |
| Offline model path matches the baseline Gate status on all 59 frozen cases, both policies | pass |
| Refusal, truncation, invalid JSON, schema violation and timeout each escalate all 59 cases | pass |
| Current-policy unsafe passes on the model path are the two registered residuals | pass |
| Text that names tools still yields only a structured diagnosis | pass |
| Every observed call came from the offline fake | pass |

| Policy | Baseline pass / reject / escalate | Offline model path | Any failure mode |
|---|---|---|---|
| v0.1.0 | 31 / 7 / 21 | 31 / 7 / 21 | 0 / 0 / 59 |
| v0.2.0 | 13 / 6 / 40 | 13 / 6 / 40 | 0 / 0 / 59 |

## What was built

- `src/rivulet_localops/providers/bedrock.py`: AU Bedrock provider. The model returns a fixed JSON schema
  (category, confidence, priority, verbatim evidence, missing information, review and injection flags,
  rationale); our Pydantic model validates it again. Asset matching stays deterministic. Quotes not found
  verbatim in the request are dropped. A P1, low confidence, an injection flag or a model review flag forces
  human review. Any client error, refusal, truncation or invalid output returns a `fail_closed` diagnosis that
  the Gate always escalates.
- Residency: only `au.anthropic.claude-*` profiles in `ap-southeast-2` or `ap-southeast-4`, and the client
  endpoint must be `bedrock-runtime.<that region>.amazonaws.com`. Bedrock API keys and long-lived access keys
  are refused; only short-term IAM Identity Center credentials are accepted.
- Request text is sent as one JSON string marked untrusted; coordinates are never sent to the model.
- `create_app(provider=...)` accepts an injected provider. The ledger records its identity
  (`aws-bedrock-au-claude`, `0.1.0+<model id>`, `model_assisted`) and its kill switch blocks calls. The public
  demo still builds only the rules provider.
- `scripts/run_model_comparison.py` runs the harness; `scripts/verify.ps1` now runs it on every verification.

## Claim boundary

The model path here is an offline fake that repeats the rules baseline, so agreement shows the wiring works,
not that a model classifies well. Accuracy, latency, token use and injection behaviour of a real model remain
unmeasured until the human Product Owner unlocks live calls and approves a paid run. Planning estimate for one
full run (73 calls, assumed 3,000 input and 1,000 output tokens per call, list price plus the 10% regional
premium): about USD 2.57 on Opus 5.5, 1.28 on Sonnet 5.5 and 0.06 on Haiku 5.5. The Bedrock pricing page is
authoritative.

## Unlock conditions (human only)

1. The human Product Owner reviews the F17 charter, chooses the model tier and a budget.
2. They provide an AWS account with Sydney model access and a least-privilege IAM user limited by
   `infra/aws/bedrock-au-invoke-policy.json`, signing in with short-term `aws login` credentials (completed
   2026-11-03; no long-lived keys exist).
3. They change `LIVE_MODEL_CALLS_LOCKED` and its test by hand, in their own commit; no automated process or
   delegated helper may lift the lock.
