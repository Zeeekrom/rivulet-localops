# Security and Responsible Use

Rivulet LocalOps is a local portfolio demonstrator and must not receive real resident, employee or other personal information.

## Current controls

- deterministic policy Gate before a decision record is created;
- explicit synthetic-data and synthetic-policy labels;
- append-only application events with a SHA-256 hash chain;
- separate accountable-owner and reviewer fields;
- blocked self-review and blocked direct acceptance of failed Gate decisions;
- persistent provider kill switch and manual fallback;
- fail-closed automated processing after ledger-integrity failure;
- automated negative tests.

## Not yet provided

- authentication, RBAC or verified human identity;
- encryption key management or a managed secret store;
- external immutable audit storage;
- production retention, privacy or records-management controls;
- an out-of-band operations plane;
- an external business-system connector;
- production monitoring, backup or restore evidence.

Do not report sensitive vulnerabilities in a public issue. Use GitHub's private vulnerability-reporting channel if it is enabled for this repository. Never include live credentials, personal data or identifiable council security details in a report.
