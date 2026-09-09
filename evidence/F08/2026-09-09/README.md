# F08 · Sprint 2 ledger review evidence

## Hypothesis

The local decision ledger can preserve an original Gate decision, append an independent review, reproduce the
decision, detect tampering, stop new automated writes when integrity fails, and route work to a recorded manual
fallback when the provider is disabled.

## Result

Pass after one implementation fix. The first review run showed that read-only ledger connections remained open on
Windows because `sqlite3.Connection` transaction context managers do not close the connection. Temporary evidence
cleanup failed with `WinError 32`. The ledger now wraps read connections with `contextlib.closing`; the tamper test and
review runner also close their direct SQLite connections explicitly.

The rerun passed every review check, the 18-test suite and the 12-case regression check. This finding was a resource-
lifecycle defect, not a hash-chain or Gate-decision failure.

## Claim boundary

- Owner, reviewer and operator identifiers remain asserted demo strings, not authenticated identities or RBAC.
- The SQLite chain is tamper-evident in the tested paths, not WORM storage or an externally signed audit proof.
- A passing decision permits a draft-only action; there is no real council connector.
- Review inputs are synthetic and contain no real resident data.

## Files

- `commands.txt` records the reproducible commands.
- `result.json` records stable pass/fail outcomes without ephemeral IDs or local paths.
- `versions.txt` records the relevant runtime and release versions.
