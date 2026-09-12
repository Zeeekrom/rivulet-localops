# F10 · Power BI provenance and decision-assurance thin slice

## Result

**PASS — Sprint 2.5B Build/Check evidence.** The generated PBIP opened in Power BI Desktop, all seven Import
partitions refreshed, the two report pages rendered with non-blank values, and the thirteen published reference
metrics reconciled exactly against the versioned mart outputs.

This evidence supports a portfolio-grade local Power BI artefact. It does not prove Power BI Service/Fabric
deployment, scheduled refresh, real council performance, model accuracy, SLA achievement or production readiness.

## What was verified

- Deterministic generation produced 48 PBIP/PBIR/TMDL files from seven versioned mart CSVs.
- The Microsoft `powerbi-report-author` validator returned 0 errors and 0 warnings.
- The offline Microsoft Power BI Modeling MCP parser loaded 7 tables, 29 measures and 8 relationships.
- Power BI Desktop 2.157.1354.0 opened `RivuletAssurance.pbip`; Desktop Bridge reported the expected file, no
  unsaved changes and both PBIR pages.
- A full XMLA refresh succeeded for 7 of 7 Import partitions.
- A live DAX query returned the expected public-source, quality and synthetic-control metrics. In particular,
  eligible asset decisions were 126, matched decisions were 108 and the asset-match rate was 0.8571428571.
- Visual inspection confirmed populated cards/charts/tables, a visible truth-class filter and explicit real-versus-
  synthetic limitation banners on both pages.
- The repository verification pipeline completed with 26 tests and the 12-case self-authored regression fixture.

## Defects exposed during the check

The failed attempts were retained as findings rather than hidden:

1. A generic AJV pass could not resolve Microsoft's absolute schema IDs and relative references on Windows. The
   project now uses Microsoft's report-authoring validator for the PBIR gate.
2. Initial Microsoft validation found 83 errors and 2 warnings: missing report platform metadata, missing visual
   `nativeQueryRef` values, invalid title colour property, matrices without a Values role, and a title below the
   minimum height. All were fixed in the generator before the successful validation.
3. Desktop first opened as `Untitled` because the semantic model lacked its own `.platform` metadata. Adding the
   deterministic SemanticModel platform file allowed Desktop Bridge to bind the PBIP correctly.
4. Desktop then rejected two active paths between Review and Date. The Review-to-Decision lineage relationship is
   now intentionally inactive; review-date filtering uses the direct Date relationship.
5. The first rendered pages contained blanks because PBIP stores model definitions, not an imported data cache. A
   full seven-partition refresh is therefore a required opening step.
6. The first DAX reconciliation exposed an asset-match rate above 100%, then a 100% result after a partial fix,
   because CSV empty strings are countable text. The final measure uses the mart's actual eligibility scope and
   `LEN(asset_key) > 0`, yielding 108 / 126 = 85.71%. Zero blocking failures are explicitly coalesced to 0.

## Evidence files

- `result.json` — machine-readable outcome and reconciled values.
- `commands.txt` — reproducible command sequence and live-model validation outline.
- `versions.txt` — runtime/tool versions used.
- `screenshots/Data provenance & quality.png` — refreshed provenance/quality page.
- `screenshots/Gate & decision assurance.png` — refreshed Gate/decision page.

PBIP and enhanced PBIR remain Power BI preview features. The generated source is validated in CI, while Desktop
refresh and screenshot capture remain a local Review gate.
