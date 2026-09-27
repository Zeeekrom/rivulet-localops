# F23 · Azure cloud-safe demo deployment acceptance

## Result

**PASS WITH RETAINED RECOVERY FAILURES.** Rivulet LocalOps v0.7.1 is running as a public HTTPS Azure Container App in
New Zealand North:

- [Live assurance console](https://rivulet-demo.ambitiousocean-bb774a66.newzealandnorth.azurecontainerapps.io/)
- [Successful deployment gate](https://github.com/Zeeekrom/rivulet-localops/actions/runs/35995289399)
- [Post-fix hosted verification](https://github.com/Zeeekrom/rivulet-localops/actions/runs/35995184675)

The app uses an anonymously pullable GHCR image, an Azure Container Apps Consumption environment and a GitHub
environment federated to a user-assigned managed identity. Authentication is GitHub OIDC only: no client secret was
created, and the identity has Contributor only on the dedicated demo resource group.

## Live controls verified

- Azure reports both the managed environment and app as `Succeeded`; the app reports `Running` with release
  `v0.7.1` and profile `public_demo`.
- HTTPS ingress is external, insecure HTTP is disallowed, and the workload is capped at 0.25 CPU / 0.5 GiB with
  `minReplicas: 0` and `maxReplicas: 1`.
- `/healthz` and `/demo/v1/bootstrap` succeed; bootstrap exposes five server-owned scenarios and no visitor free text.
- A passing scenario returns `pass`; the blocked-shell scenario returns `deny` with ledger integrity true.
- `/docs`, `/openapi.json`, `/api/v1/submit` and `/ops/v1/ledger/integrity` each return `404`.
- A 1,025-byte request is rejected with `413`; the browser surface returns CSP, frame-deny and nosniff headers.
- Desktop and 390 × 844 mobile rendering were visually reviewed against the live endpoint. A live controlled-path run
  rendered the Gate result, two tool receipts, seven policy checks, no stored raw input and a verified hash chain.
- The corrected default-branch workflow repeated OIDC login, ARM what-if, idempotent deployment, health, four negative
  route checks and the capability-deny assertion in one hosted run.

## Retained recovery evidence

1. [Run 35994259185](https://github.com/Zeeekrom/rivulet-localops/actions/runs/35994259185) failed before deployment
   because Azure had the conventional name-based OIDC subject while this repository emits a custom ID-bound subject.
   Updating the same federated credential fixed the mismatch without adding a secret or widening role scope.
2. [Run 35994416800](https://github.com/Zeeekrom/rivulet-localops/actions/runs/35994416800) completed ARM deployment but
   its post-deploy assertions called `python`, which is absent from the `azure/cli@v3` container. The workflow now uses
   the image-provided `jq`; the successful third run proves the recovery.
3. Earlier preflight failures are also retained in the project log: Entra app registration was tenant-denied,
   Australia East was subscription-policy-denied, and `appLogsConfiguration.destination: none` was invalid Bicep API
   input. The final design uses a user-assigned managed identity, New Zealand North and an omitted log destination.

## Cost and lifecycle boundary

- The subscription is Azure for Students with spending limit on, but the Sponsorship portal does not expose an active
  sponsorship balance. This evidence does not claim that remaining credit or every Azure component is free.
- The app is configured for scale-to-zero and one maximum replica. Configuration is proven; actual zero-replica idle
  transition and a billing statement were not tested.
- Log Analytics is intentionally not attached. This reduces demo overhead but means platform-log retention is not part
  of this slice.
- Resources carry `expiresOn: 2026-10-24`. Expiry is a governance tag, not automatic deletion.

## Claim boundary

This is a public portfolio sandbox using real public reference snapshots and fixed synthetic operational fixtures. It
proves a bounded deployment path and selected controls, not production readiness, real council adoption, authenticated
end users, durable audit storage, model accuracy or a generative AI integration. The runtime ledger is ephemeral and
may reset on scale-to-zero or revision replacement.

## Evidence files

- `result.json` — machine-readable deployment, hosted-run and boundary results.
- `commands.txt` — sanitized reproduction commands with identifiers omitted.
- `versions.txt` — tested release, image and tool versions.
