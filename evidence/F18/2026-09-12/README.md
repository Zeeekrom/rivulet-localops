# F18 · Read-only case-agent capability enforcement

## Result

**PASS — 12 of 12 bounded-capability checks passed.** A server-owned `case-agent` identity can run one local,
read-only diagnosis using only the current synthetic case and the approved Hobart public-asset lookup. Requests for
shell execution, another case, a restricted data class, an excessive tool-call budget, a mismatched provider identity,
or a disabled provider are denied or failed closed before provider execution and appended to the existing hash-chained ledger.

This is the Sprint 3 L0 control-plane slice. It deliberately uses the existing deterministic-rules provider, requires
no model credential, performs no connector write and does not claim to be generative AI.

## Controls verified

- Versioned, hash-bound capability registry with a named demo owner and server-selected `case-agent` identity.
- Deny-by-default tool and data enforcement; only `case.read` and `asset.lookup` are allowed.
- Current-case resource binding; a proposed read of another case is denied.
- Five-minute invocation grant and four-call budget; expiry and budget have negative tests.
- Provider identity/version binding before execution and the existing provider kill switch.
- Completed, denied and failed invocations record agent/owner/purpose/request IDs, registry/provider/policy versions, grant
  times, tool decisions, input/output hashes, latency, termination reason and ledger hashes.
- Agent audit payloads omit the raw request text; the review confirmed all seven invocation records are queryable and
  the ledger remains valid.

## Review outcome

The disposable review generated seven agent invocations: one completed, five denied and one failed before execution.
Together with the provider control event, the temporary ledger contained eight valid hash-chained events. The full
repository suite contains 35 tests; the seven focused agent tests include identity disablement and grant expiry in
addition to the review scenarios.

## Claim boundary

- Caller authentication and production RBAC are not implemented; the operations API remains local and unauthenticated.
- `request_id` scope enforcement is a control-contract test, not authorization against a real multi-user case store.
- The registry is a versioned demo file with a recorded hash, not a signed policy or external identity system.
- A plain SHA-256 input hash is not a privacy-preserving commitment for future personal data; the current API accepts
  only synthetic requests, and production design must use access control, minimisation and a keyed/protected scheme.
- Prompt-injection/adversarial-model evaluation, a real model provider and connector writes remain later gates.

## Evidence files

- `result.json` — machine-readable review result.
- `commands.txt` — reproduction commands.
- `versions.txt` — runtime and library versions.
