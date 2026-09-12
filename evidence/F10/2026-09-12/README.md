# F10 · Power BI Desktop round-trip and canonicalization

## Result

**PASS — repository output remains deterministic after a real Desktop open/refresh cycle.** Power BI Desktop's
post-save normalization was classified, the portable metadata was absorbed into the generator, machine-specific
state was excluded, and the canonical project passed repository, Microsoft, Desktop and live-model checks again.

This evidence extends the 2026-09-10 Sprint 2.5B Review. It supports a portable local PBIP artefact; it does not prove
Power BI Service/Fabric deployment, scheduled refresh, real council performance or production readiness.

## Finding retained

Closing Power BI Desktop after the original Review rewrote 47 controlled files and added `.pbi` state, an `en-AU`
culture file and `diagramLayout.json`. The first attempt to accept Desktop's output made Microsoft's report validator
fail with `PBIR_JSON_FILE_NO_SCHEMA`, because Desktop had removed the PBIR entry file's `$schema`.

The repository therefore treats its generator as the canonical serialization boundary:

- `localSettings.json` and `cache.abf` are local-only and ignored;
- `editorSettings.json`, `definition/cultures/en-AU.tmdl` and `diagramLayout.json` are portable and generated;
- Desktop's report/pages schema and semantic-model compatibility upgrades are generated;
- PBIP/PBIR `$schema` fields are restored before validation and commit.

After any Desktop edit or refresh, the required sequence is generator → generator check → Microsoft validator → full
verification. The canonical build now contains 51 controlled files and 88 structural checks.

## Verification

- Microsoft report validator: 0 errors, 0 warnings.
- Power BI Desktop 2.157.1354.0 opened the canonical project.
- Modeling MCP refresh: 7 successful Import partitions, 0 failures.
- Live DAX: 13 of 13 reference values reconciled; eligible/matched asset decisions remained 126/108.
- Repository recovery verification: 28 tests passed, 2 known upstream warnings; 12 self-authored regression cases had 0
  failures; all 8 analytics mart reconciliations passed.
- Both refreshed pages were visually inspected and captured again.

## Hosted portability finding

Public v0.5.0 main and tag workflows both failed in a fresh Windows checkout because the seven generated TMDL table
partitions embedded CRLF bytes from the local mart while Git stored the same generated CSV files with LF endings. The
failure is preserved in main [run 34673442580](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34673442580)
and tag [run 34673442408](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34673442408); the v0.5.0 tag was not
moved or deleted.

The recovery generator canonicalizes embedded generated CSV to LF on every operating system, calculates manifest
hashes over the same canonical bytes, checks that manifest under `--check`, and adds a CRLF/LF equivalence test. Local
recovery verification passes 28 tests. Recovery is released under a new patch version rather than rewriting v0.5.0.

The staged-tree fresh-checkout preflight passed before release. Public v0.5.1 then passed both
[main run 34673725103](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34673725103) and immutable
[tag run 34673726741](https://github.com/Zeeekrom/rivulet-localops/actions/runs/34673726741). These hosted runs verify
repository checkout/build/test portability; they do not run Power BI Desktop or deploy the application.

## Evidence files

- `result.json` — machine-readable result and exact live values.
- `commands.txt` — command and runtime-check outline.
- `versions.txt` — runtime/tool versions.
- `screenshots/` — refreshed report pages with SHA-256 values recorded in `result.json`.
