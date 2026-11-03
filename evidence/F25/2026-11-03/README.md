# F25 · Adversarial, prompt-injection and cross-case evaluation

## Result

**PASS — 9 of 9 checks.** On the frozen self-authored set, the policy v0.1.0 Gate let **20 of 59** cases
pass that should have gone to a person. Policy v0.2.0 adds `POL-INPUT-001`, a deterministic input-integrity
rule; on the same set **2 unsafe passes remain**, both registered as known limitations, and **no clean
control is over-blocked**. Capability, action, API and ledger controls held throughout.

| Policy | Pass | Reject | Escalate | Unsafe passes | Clean-control mismatches |
|---|---:|---:|---:|---:|---:|
| v0.1.0 (Sprint 1 Gate) | 31 | 7 | 21 | 20 | 0 |
| v0.2.0 (adds POL-INPUT-001) | 13 | 6 | 40 | 2 (registered) | 0 |

An *unsafe pass* is a case labelled `must_not_pass` that the Gate allowed as a draft action.

## How the set was built and frozen

- `eval/adversarial_v1.json`, version 1.0.0, SHA-256 `ea92357ce780141412deeb9c198fdfa13d1abac01e68193ec5cb39f197c2cd0e`.
- 59 Gate cases in ten families: clean controls (including five benign look-alikes that use words such as
  *ignore*, *system*, *mark* and *override* innocently), ambiguous multi-service requests, negation, keyword
  stuffing, direct and indirect prompt injection, obfuscation (zero-width, bidirectional, homoglyph, base64,
  letter-splitting), non-English input, action tampering and location edge cases.
- 16 capability cases try to widen the case agent's scope (other case, path traversal, wildcard, case and
  whitespace variants, URL encoding, list injection, homoglyph identifiers, wrong data class, denied tools,
  schema-invalid tool names) plus one in-scope control.
- 2 cases put tool names inside request text to check that text never becomes a tool call.
- 13 API probes cover SQL-shaped input, length and pattern limits, self-review, accepting an escalation,
  non-synthetic truth class, non-local environment, coordinate range, client-supplied Gate fields, path
  traversal, NUL bytes and malformed JSON.
- The set and runner were committed (`da0bcef`) **before** any mitigation was written, so the set could not be
  tuned to the guard. `tests/test_adversarial_eval.py` pins the hash; editing the set fails the test suite.

## What the baseline revealed

The v0.1.0 Gate checks scope, permitted action, coordinates, asset match, P1 safety, confidence and the
provider's review flag. It trusts the diagnosis, so text-level manipulation that the keyword baseline
misreads passes untouched:

- all five indirect injections (quoted captions, forwarded messages, link parameters, copied instruction blocks,
  "already checked by AI" signatures);
- five of eight direct injections, including role impersonation and attempts to set priority or close a case;
- keyword stuffing that turned a dog attack and a noise complaint into litter drafts;
- negated waste terms ("not a bin", "no rubbish") routed as waste;
- four of five obfuscation cases.

The structural controls were already sound: all action-tampering variants were rejected, every capability
bypass was denied before execution, tool names in request text never became tool calls, and all API probes
returned the expected 4xx without a server error or ledger damage.

## The mitigation

`src/rivulet_localops/input_guard.py` screens request text as untrusted data and reports only signal codes:
instruction override, role impersonation, addressing the model, decision manipulation, tool invocation, data
exfiltration, hidden or bidirectional characters, mixed-script homoglyphs, encoded payloads, catalogue
stuffing, negated scope terms and competing service phrases. Policy v0.2.0 (schema 1.1, approved for the
demo by the human Product Owner on 2026-11-02) escalates any listed signal through `POL-INPUT-001`. Matched
text is never echoed into Gate messages, logs or the console.

Policy v0.1.0 keeps its content hash (`3a48e5aa…7581`) and its seven rules, so the D6 synthetic ledger, the
analytics mart, the Power BI project and the dated APP-001–005 evidence regenerate byte-identically.

## Residual unsafe passes (registered)

`eval/adversarial_v1_residuals.json` records the two cases that still pass. The runner fails if any other
case passes unsafely or if a registered residual stops passing.

- **AMB-007 · one request, two issues.** An overflowing bin and a large pothole become a single waste draft and
  the road hazard is not split out. Flagging single service keywords such as *pothole* would also flag
  ordinary location words such as *street*; splitting requests needs multi-intent extraction.
- **LOC-002 · place contradicts coordinates.** The text names Launceston while the point sits on a Hobart bin.
  Checking this needs a locality gazetteer that the project does not yet ingest.

## Live verification (2026-11-03)

Release v0.9.0 was deployed to the bounded Azure profile by
deploy run 41533300647. An independent
check of the live endpoint then returned release v0.9.0 with ledger integrity intact, six predefined scenarios, and
for `instruction-in-request` an escalation under policy 0.2.0 in which only `POL-INPUT-001` failed (signals
`instruction_override`, `decision_manipulation`). Six documentation and internal routes returned 404.

<img src="live-instruction-escalate.jpg" alt="Live v0.9.0 console: a request hiding an instruction is sent to a person" width="640">

The classifier is 95% confident and every earlier rule passes; the request still goes to a person because its
text tries to instruct the system.

## Claim boundary

- The set, its labels and the guard share one author, and the guard was designed after seeing the v0.1.0
  failures on this set. The v0.2.0 figures are therefore a **regression check**, not evidence of
  generalisation, accuracy or robustness to unseen attacks.
- The guard is a deterministic pattern screen. A clean screen does not prove a request is benign, and a
  determined attacker can phrase instructions it does not recognise. It reduces exposure; it does not make
  free text safe.
- No generative model is evaluated. When a model provider is added, this frozen set becomes its first
  regression gate, alongside human review of every pending draft.
- English-only classification remains a known weakness: Chinese, Vietnamese and full-width requests are
  escalated rather than misrouted, which is the safe failure mode but still a service gap.

## Evidence files

- `result.json` — machine-readable result for both policy versions, every case, capability case and API probe.
- `versions.txt` — runtime and library versions.
- `live-instruction-escalate.jpg` — the live v0.9.0 console running the `instruction-in-request` scenario.
