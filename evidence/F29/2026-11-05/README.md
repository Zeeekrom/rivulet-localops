# F29 · Hosting that outlives student credits (2026-11-05)

## Result

**Build, offline checks, one approved live guard drill and the first Cloudflare publication pass.** The replay page is
live at https://rivulet-localops-replay.pages.dev.
The portfolio now has three layers that do not depend on the Azure for Students credit:

1. a **static replay page** of the public demo that needs no server and no Azure account;
2. a **free-grant guard** that keeps the live demo inside the Container Apps monthly free grant;
3. a **runbook, Australia East parameters and a budget template** for the move to a pay-as-you-go subscription.

## Static replay page

`vite build --mode replay` builds the same console against a recording of the real public demo profile
(`web/src/replay/recording.json`, recorded 2026-11-05, release label v0.9.0, policy v0.3.0). The page states at the top
that the results were recorded and that nothing runs live.

| Check | Result |
|---|---|
| Recording matches the code (18 id, time and hash fields excluded) | pass; a changed outcome or a missing scenario fails the test |
| Six scenarios shown, outcomes as expected | 6/6 |
| Requests made by the page | 3 static files, 0 API calls, 0 console errors |
| Ordinary build | carries no recording |
| Replay bundle | contains no demo API path; ships a `_headers` file with the same security headers as the live demo |
| Phone width (375 px) | banner and layout readable |

It is published to Cloudflare Pages (free plan) from the private release repository with a Pages-only API token that
the product owner created. The first successful run (41992909717) checked the recording, built the page, uploaded it
and verified the live page, its four security headers and the recording file. Cloudflare answers the default
`Python-urllib` user agent with HTTP 403, so the checker now names itself.

## Free-grant guard

The Consumption plan gives each subscription 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests a month.
At 0.25 vCPU and 0.5 GiB that is about 200 hours of the demo running. The guard reads the month's usage and:

- warns at 70% of the grant;
- switches public ingress off at 90%, so the demo scales to zero;
- switches it back on in a new month, but only if the guard switched it off.

A local read-only run on 2026-11-05 found 641.7 vCPU-seconds and 1,283.5 GiB-seconds used so far this month, which is
**0.36% of the grant** (about 43 minutes of the demo running). The decision was `ok`. The same read-only check ran in
GitHub Actions with the existing deploy identity, which has Contributor on the demo resource group only, and gave the
same result, so the guard needs no new permission.

**Live drill (approved by the product owner, run 41983929963, 56 seconds).** The guard switched public ingress off,
confirmed `/healthz` could no longer be reached, switched ingress back on and confirmed `/healthz` returned 200 at the
same address. An independent check afterwards found the ingress settings, tags, revision, image and replica limits
exactly as before, and the standard post-deployment smoke check passed.

**Schedule.** The product owner turned the scheduled guard on the same day. It runs in `enforce` mode at 03:41 and
15:41 UTC.

What the build found:

- **Azure Monitor reported nothing for the demo in New Zealand North.** The Replicas and Requests metrics were zero or
  empty for every day since 2026-10-05, even while a replica was running. The guard therefore counts Monitor only when
  it shows usage.
- **Cost Management usage quantities work on the student subscription.** They became the main signal. Microsoft lists
  that subscription type as unsupported for budgets, but the usage query worked.
- **Open-month cost amounts ignore the free grant.** Cost Management priced the 0.36% above at AUD 0.042, so the guard
  compares quantities with the grant, not amounts.
- **Cost Management throttles quickly.** The guard retries with backoff and otherwise reports the signal as unavailable.

## Prices (Australia East, Azure Retail Prices API, 2026-11-05)

| Meter | USD |
|---|---|
| vCPU active, per second | 0.000034 |
| Memory, per GiB-second | 0.000004 |
| Requests, per million (after 2 million) | 0.40 |
| One replica awake all month, after the grant | about 20 a month, plus requests |

## Move to pay-as-you-go

The container template takes its region from the deployment. A parameter file for `australiaeast` and a budget template
(AUD 15; alerts at 50%, 80% and 100% actual and 100% forecast) compile offline. Australian regions cannot be tested on
the student subscription, so the move is documented, not performed.

## Limits

The replay page shows recorded results and runs nothing. Prices and grants come from official pages on 2026-11-05; the
bill is authoritative. The grant is per subscription, but the guard sees only the demo's resource group.
