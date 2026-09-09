# F06 · Public-source contract and quality gate

## Outcome

PASS WITH WARNINGS. D1 and D2 snapshots are hash-pinned, schema-contracted and reproducibly profiled. Nineteen checks
ran: 15 pass, 4 warn, 0 fail and 0 blocking.

## Sources and observed grain

- D1: City of Hobart public litter-bin assets, 727 point features, EPSG:4326.
- D2: Townsville City Council public request-for-service CSV, 24,197 monthly aggregate rows from July 2018 through
  July 2026 and 1,213,852 published requests in aggregate. It is reference context, not Hobart operational data.

The D2 file is Windows-1252 rather than UTF-8. The first strict UTF-8 ingest failed on byte `0x96`; the fetcher now
uses strict UTF-8 first and an explicit Windows-1252 fallback while recording the detected encoding in the manifest.

## Quality finding that changed the model

The initial gate treated case-normalized `Group Code + Category Code + Date` as a unique fact grain and correctly
failed. Investigation found two different publisher rows for November 2019 whose category codes differ only by case
(`CSPlnAdvce` and `csplnadvce`) and whose counts are 1 and 77. There are no exact duplicate rows, but 2 normalized
group codes and 35 normalized category codes map to multiple labels across history.

The remediation is not to merge the rows. The mart preserves every source row, uses a deterministic source-row key,
retains raw codes/descriptions and keys the category-variant dimension by code plus description. The normalized-key
collision remains visible as a warning and is pinned by tests.

## Claim boundary

Passing this gate means the exact snapshots conform to the declared contracts and have no blocking defects for the
planned reference analysis. It does not prove source correctness, completeness of council operations or transferability
from Townsville to Hobart.
