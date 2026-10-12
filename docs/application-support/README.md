# Application Support knowledge base

This area documents the internal Rivulet application profile. It is operational evidence, not a second product or an
ITSM ticketing system. All recorded incidents are isolated synthetic exercises unless a report explicitly identifies a
hosted observation.

## Entry points

- Internal UI: `/ops/support`
- Component health: `/ops/v1/health`
- Support Bundle: `/ops/v1/support/bundle`
- Redacted structured logs: `/ops/v1/operations/logs`
- Runbook index: `/ops/v1/runbooks`

## Evidence boundary

The public demo does not register these routes. Support Bundles contain only allowlisted configuration summaries and
operational fields; they never contain request bodies, credentials, environment-variable dumps, database paths or
resident records.
