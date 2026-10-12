# APP-002 evidence · 2026-10-12

The local result verifies release-mismatch detection and deliberately keeps `hosted_rollback_verified=false` because
that file represents only the local fixture. Hosted evidence is recorded separately:

- `azure-v0.8.0-deploy.json`: independent observation after successful deployment run `38205416715`;
- `github-run-38205693603/`: first hosted drill; candidate checks completed, the injected failure fired, and rollback
  failed because the Azure CLI command contained an unsupported argument;
- `azure-v0.8.0-recovery.json`: independent observation after safety-recovery run `38205872737` restored v0.8.0;
- `github-run-38206163289/`: corrected hosted drill with candidate result, pre-deploy state and recovered-release result;
- `azure-v0.8.0-rollback-verified.json`: independent observation after the corrected drill left v0.8.0 healthy;
- `github-run-*`: unmodified JSON artifacts downloaded from the named GitHub Actions runs.

The failed drill is retained as evidence. Only corrected run `38206163289` counts as successful hosted rollback
verification.
