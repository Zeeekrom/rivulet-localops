# F22 · Local container acceptance of the published v0.9.0 image

## Result

**PASS — 14 of 14 checks.** The exact public release image `ghcr.io/zeeekrom/rivulet-localops:v0.9.0`
(index digest `sha256:71a3aadb594ad2fca67961622b992b1ff29ecbe1c538945456f2133caadfa81b`) was pulled, started on a
loopback port with Docker Desktop and exercised through its HTTP boundary. This closes the gap left at v0.8.0, when a
Docker Desktop runtime-socket fault blocked any local container run and the project relied on hosted builds alone.

## What was checked

| Check | Result |
|---|---|
| Pulled image digest equals the published v0.9.0 index digest | Pass |
| Image declares `10001:10001`; the running process is uid 10001 | Pass |
| Container health check reaches `healthy` | Pass |
| `/healthz` reports `ok`, release v0.9.0 and an intact ledger | Pass |
| `/` serves the console with five browser security headers | Pass |
| All six predefined scenarios match their fixtures with an intact ledger | Pass |
| `instruction-in-request` escalates with `POL-INPUT-001` as the only failed rule | Pass |
| A 1,025-byte body returns 413 with the security headers | Pass |
| `/docs`, `/openapi.json`, `/api/v1/submit`, `/ops/v1/ledger/integrity`, `/ops/v1/support/bundle`, `/ops/support` return 404 | Pass |
| The container is stopped and removed afterwards | Pass |

The safety-escalation scenario ("on fire and presents immediate danger") failed only `POL-SAFETY-001` and
`POL-REVIEW-001`; the input-integrity rule did not fire on it.

## How it is reproduced

`scripts/run_local_container_check.py` replaces the manual curl steps used for the 2026-09-16 run. It pulls the image,
compares the digest, checks the declared and runtime user, waits for health, runs every scenario returned by the
bootstrap endpoint, probes the size limit, headers and forbidden routes, and always removes the container.

## Docker Desktop status

Docker Desktop 4.96.3 with Engine 29.9.2 started normally. The AF_UNIX runtime-socket failure recorded with
APP-004 on 2026-10-12 did not recur; no reset or data deletion was performed by the project to get here.

## Claim boundary

- A local run of one published image on one Windows host. It checks the container boundary and the predefined
  synthetic scenarios; it is not a penetration test, a production-security claim or an Azure deployment.
- The runtime ledger lives inside the container and was discarded with it.

## Evidence files

- `result.json` — machine-readable checks and observations.
- `versions.txt` — tool and runtime versions.
