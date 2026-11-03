# F24 · Plain-language overview console

## Result

**LOCAL BUILD/CHECK PASS.** The public web console was redesigned from a landing-page layout into a one-screen
operations overview that a non-technical reader can follow. The page was built for production, served by the unchanged
`public_demo` API profile on a local port, and captured in three states.

Release `v0.7.2` changes the front-end and the release label only. The API routes, the policy, the agent capability
registry, the ledger and the five server-owned scenarios are unchanged.

## What changed in the interface

- The hero banner and the separate architecture strip were removed. The page now opens with four summary figures.
- A five-step strip explains what happens to every request in plain words.
- Outcomes use everyday wording: passed, sent to a person, blocked, stopped.
- A scenario result leads with the outcome and the reason. The seven policy rules, the agent receipts and the record
  hashes remain on the page behind two disclosure controls.
- Outcome colours were checked with a colour-vision-deficiency validator, and every coloured mark has a text label.

## Controls verified

- Production build succeeds: TypeScript check plus Vite, 17 transformed modules.
- `GET /healthz` reports release `v0.7.2` with a valid, empty runtime ledger.
- `/docs`, `/openapi.json`, `/api/v1/submit` and `/ops/v1/ledger/integrity` each return `404` on the local public profile.
- The "Evidence complete" scenario returns `pass`, "Safety escalation" returns `escalate`, and "Capability denied"
  returns `deny`. Each matches its fixture.
- Every figure still carries its source class: D1 and D2 as real public data, D6 as synthetic test data.
- The claim boundary and the ephemeral-ledger notice are still shown on the page.
- The page reflows to one column at phone width.

## Claim boundary

- This is a local check of a redesigned interface. The container image and the Azure deployment for `v0.7.2` are not
  covered here; see the hosted workflow runs recorded in `docs/SPRINT_EVIDENCE.md`.
- The live Azure demo keeps serving the previous release until a deployment is run for `v0.7.2`.
- Scenario inputs and operational metrics are fixed synthetic fixtures. The interface cannot support claims about
  council performance, model accuracy or a live council workflow.
- No reader study was run. "Easier for a non-technical reader" is a design intent, not a measured result.

## Evidence files

- `result.json` — machine-readable summary of the checks.
- `desktop-pass.png` — full page at 1440 px after the passing scenario.
- `desktop-escalate.png` — full page at 1440 px after the escalation scenario.
- `mobile-deny.png` — full page at 390 px after a denied capability.
