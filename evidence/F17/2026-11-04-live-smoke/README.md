# F17 · First live smoke runs (2026-11-04)

## Result

**The live path works.** One call to Claude Haiku 4.5 through the AU geographic inference profile
(`au.anthropic.claude-haiku-4-5-20251001-v1:0`, source region `ap-southeast-2`, routing only to Sydney and Melbourne)
returned schema-valid JSON with `stop_reason: end_turn`.

| Measure | Value |
|---|---|
| Calls | 1 of 1 allowed (cap 1, budget USD 0.25) |
| Tokens | 1,038 input, 153 output |
| Latency | 3.6 s |
| Estimated cost | USD 0.002 (planning price; the AWS bill is authoritative) |
| Regression case REG-01 | category matched the rules baseline; priority did not |

The recorded `status` is `fail` for one reason only: `request_id_recorded` was false. Bedrock returns its request id
in the `x-amzn-requestid` header, which the SDK's `_request_id` field does not read. The provider now reads that
header through the SDK's raw-response path, and the capped client applies the same call and budget check to it. That
fix is covered by offline tests; no further live call was made to confirm it.

One case says nothing about classification quality. The priority difference on REG-01 is noted, not interpreted.

## How we got here

| Attempt | Model profile | Outcome | Cause | Cost |
|---|---|---|---|---|
| 1 | `au.anthropic.claude-haiku-5-5` | `client_error:PermissionDeniedError` (403) | The AWS account was on the Free plan, which excludes AWS Marketplace offers that can incur charges; Claude on Bedrock is billed through AWS Marketplace. The same model returned "not available for this account" for the account root in the console playground. | none |
| — | `au.anthropic.claude-haiku-5-5` (console, after the owner upgraded to the paid plan) | still "not available for this account" | The newest model generation is not yet enabled for this new account; AWS directs such cases to AWS Sales. | none |
| — | `au.anthropic.claude-haiku-4-5-20251001-v1:0` (console) | replied | Previous-generation Haiku is available on the paid plan; this first use also started its Marketplace subscription. | < USD 0.001 |
| 2 | `au.anthropic.claude-haiku-4-5-20251001-v1:0` | `ok` | — | ≈ USD 0.002 |

Code changes between the attempts:

- Failed calls now record the HTTP status and the service message, with any echo of the request text removed.
- The residency guard accepts versioned AU profile ids (`...-v1:0`); anything not starting `au.anthropic.claude-` is
  still refused.
- Haiku 4.5 has a planning price and rejects `output_config.effort`, so its requests omit effort and keep the JSON schema.
- The least-privilege IAM policy gained the Haiku 4.5 AU profile and its two AU foundation-model ARNs.

## Setup facts learned

- Reading `aws login` credentials needs `botocore[crt]` alongside `anthropic[bedrock]==1.17.0`; without it botocore raises
  `MissingDependencyException` before any request is sent.
- Keep the Anthropic Python SDK below 2.0.0 while using Haiku 4.5 on Bedrock: 2.0.0 sends API version `2026-10-21`, which
  Bedrock accepts only for Claude 4.7 and later models.
- Whether AWS promotional credits offset Marketplace-billed Claude usage is still to be confirmed on the AWS bill.

## Claim boundary

A smoke run proves the wiring (credentials, AU routing, Marketplace subscription, structured output, cost capture). It is
not evidence of accuracy, safety or cost at scale. Only model inference ran in Australia; the hosted demo runs elsewhere.
