# F22 · Cloud-safe web demo local acceptance

## Result

**LOCAL + HOSTED BUILD/CHECK PASS — Azure deployment remains pending.** The React/TypeScript assurance console, its separate
FastAPI `public_demo` surface, the multi-stage Linux container and the Azure Bicep template all build locally. The
container was then started as the image-declared non-root user and exercised through its real HTTP boundary.

The local review covered a passing Gate scenario and a denied shell-capability scenario. It also verified that the
public profile does not load documentation, OpenAPI, the internal submission API or the operational ledger API. The
temporary validation container was stopped and removed after the checks.

## Controls verified

- Production Vite build succeeds with 17 transformed modules; npm audit reports zero known vulnerabilities.
- Runtime Python dependencies are exact-pinned in `requirements-runtime.lock`; the container does not resolve the
  broader application dependency ranges during its build.
- Docker build context is 784.82 kB after excluding local `node_modules`, build output and browser artefacts. An
  earlier build correctly failed because the new runtime lock was missing from the allow-list; the allow-list was
  fixed and the failure is retained in `result.json`.
- The image declares `10001:10001`, starts healthy, serves `/` and `/demo/v1/bootstrap`, and returns the expected
  `pass` and `deny` scenario outcomes.
- Oversized input returns `413` with the same browser security headers as ordinary responses.
- `/docs`, `/openapi.json`, `/api/v1/submit` and `/ops/v1/ledger/integrity` each return `404`.
- `az bicep build --file infra/azure/main.bicep --stdout` succeeds with Bicep 0.47.16.
- The full repository verification passes: 40 tests, 8/8 mart reconciliations, 51-file Power BI generator check,
  88/88 Power BI validator checks, the 12-case regression fixture and F18 capability review.

## Docker Desktop recovery

Docker Desktop 4.54.0 could not start because its Windows AF_UNIX listener path for the inference/secrets service was
rejected. The installation was updated in place to Docker Desktop 4.91.0; no factory reset, image/volume purge or user
data deletion was performed. Engine 29.8.0 then started and completed this container acceptance. The observed symptom
matches [docker/desktop-feedback issue 625](https://github.com/docker/desktop-feedback/issues/625); this link is
diagnostic context, while the successful local build/run is the project evidence.

## Claim boundary

- This proves a local container build and HTTP boundary check, not an Azure deployment or production security.
- Scenario inputs and operational metrics are fixed synthetic fixtures. D1/D2 remain real public reference data, but
  the demo cannot support claims about council performance, model accuracy or a live council workflow.
- The public demo uses the deterministic-rules L0 provider and no model credential; it is not generative AI.
- The runtime ledger is ephemeral and resets when a container instance is replaced or scaled to zero.
- Azure Student balance/expiry and live endpoint remain open gates. The hosted release result is recorded below; it
  does not turn this local acceptance into an Azure deployment claim.

## Hosted release update (verified 2026-09-24)

The immutable v0.7.0 release commit passed GitHub Actions in fresh hosted checkouts on
[main run 35092219320](https://github.com/Zeeekrom/rivulet-localops/actions/runs/35092219320) and
[tag run 35092221720](https://github.com/Zeeekrom/rivulet-localops/actions/runs/35092221720). The container workflow
[run 35092221757](https://github.com/Zeeekrom/rivulet-localops/actions/runs/35092221757) published an anonymously
pullable GHCR OCI index with provenance and SBOM attestation. These runs close the hosted build gate, not the Azure
deployment gate.

## Evidence files

- `result.json` — machine-readable local acceptance and retained failure.
- `commands.txt` — reproduction commands.
- `versions.txt` — tested tool/runtime versions.
- `desktop-pass.png` — rendered 1440 px passing-scenario review.
- `mobile-deny.png` — rendered 390 px denied-capability review.
