# Rivulet Power BI thin slice

This directory contains the version-controlled Power BI Project for Sprint 2.5B:

- `RivuletAssurance.pbip` opens the report and semantic model in Power BI Desktop.
- `RivuletAssurance.Report/` uses the enhanced PBIR JSON report format.
- `RivuletAssurance.SemanticModel/` uses TMDL for the Import model, measures and relationships.
- `reference_metrics.csv` pins the expected values used for DAX/reference reconciliation.
- `build_manifest.json` pins the source CSV hashes used to generate the project.

## Build and validate

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\build_powerbi_project.py
.\.venv\Scripts\python.exe scripts\validate_powerbi_project.py
.\.venv\Scripts\python.exe scripts\build_powerbi_project.py --check
npx --yes --package @microsoft/powerbi-report-authoring-cli powerbi-report-author validate "analytics\powerbi\RivuletAssurance.Report" --pretty
```

The builder reads seven versioned tables from `data/mart/v1/csv/`, canonicalizes CSV line endings to LF, and embeds
that stable representation in Power Query Import partitions. This avoids machine-specific file paths, credentials and
Windows/Git newline drift while keeping the PBIP deterministic. Run the builder after rebuilding the mart; `--check`
fails when either the committed project or its source-hash manifest is stale.

Power BI Desktop writes machine-specific state under `.pbi`. `localSettings.json` and `cache.abf` are ignored, while
`editorSettings.json`, `definition/cultures/en-AU.tmdl`, and `diagramLayout.json` are generated and versioned because
they are portable model metadata. Desktop 2.157 also removes `$schema` from PBIP/PBIR entry files when it saves; the
generator deliberately restores those fields because Microsoft's report validator rejects a PBIR definition without
its schema. After a Desktop edit or refresh, rerun the generator before validator/commit.

Open `RivuletAssurance.pbip` in a current Power BI Desktop with the PBIP and enhanced PBIR preview features enabled,
then select **Refresh**. The two pages are:

1. **Data provenance & quality** — source register, visible truth-class filter, quality outcomes and warnings.
2. **Gate & decision assurance** — Gate mix, review/override, non-pass rules, manual fallback and review lag.

## Claim boundary

D1/D2 are real public reference data with different grains. D2 is Townsville monthly aggregate context, not Hobart
demand. D6 and every decision, review, Gate and fallback metric are fixed-seed synthetic operational fixtures. They
verify calculations and control paths; they do not measure council performance, model accuracy, SLA achievement or
benefit.

PBIP/PBIR remain preview features in Power BI Desktop. Structural validation and deterministic regeneration do not
replace opening, refreshing and visually reviewing the report in Desktop. Sprint 2.5B Desktop refresh, DAX
reconciliation and screenshots are recorded in `evidence/F10/2026-09-10/`; Desktop round-trip/canonicalization evidence
is recorded in `evidence/F10/2026-09-12/`. A future source or layout change requires the same Review gate again.
