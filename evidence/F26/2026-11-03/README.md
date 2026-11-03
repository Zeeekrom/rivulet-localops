# F26 · SAST, dependency and container-vulnerability gates

## Result

**PASS — 5 of 5 local checks, plus the hosted image gate.** Every push now runs Bandit SAST, pip-audit over
all three Python lock files and a Trivy scan of the built container image, and the release workflow scans the
candidate image **before** it can be pushed to GHCR. Each gate also runs against a deliberately vulnerable
canary, so a passing gate is shown to be capable of failing.

| Gate | Scope | Result | Canary |
|---|---|---|---|
| Bandit 1.9.4 (SAST) | `src/` and `scripts/`, 6,515 lines | 0 unsuppressed findings; 6 documented suppressions | `subprocess.call(..., shell=True)` → B602 HIGH |
| pip-audit 2.10.1 (SCA) | runtime, dev and security locks, 56 pinned packages | 0 known vulnerabilities | `PyYAML==5.3.1` → PYSEC-2021-142 |
| npm audit (existing) | web console lockfile | 0 high or critical | — |
| Trivy v0.76.1 (image) | Debian 13.7 base plus Python packages | 0 fixable HIGH/CRITICAL | `PyYAML==5.3.1` → 1 CRITICAL |

## What the gates found on their first runs

The gates were not green on arrival; these were fixed rather than suppressed:

- **pip-audit:** `certifi 2026.7.22` (PYSEC-2026-4320) and `pytest 8.4.2` (PYSEC-2026-1845) in the dev lock.
  Upgraded to `certifi 2026.10.23` and `pytest 9.2.0`; the runtime image never contained either package.
- **npm audit:** `vite 8.3.0` gained six high-severity advisories on 2026-11-03 (including
  GHSA-587h-7wmj-h5pm in `launch-editor`). Upgraded to `vite 8.3.5`, the same major version.
- **Bandit, B310 (medium):** the deployment verifier passed any URL scheme to `urlopen`. It now accepts only
  `https`, or `http` on a loopback host.
- **Bandit, B108 (medium):** the public demo's default ledger path was a predictable file in shared `/tmp`.
  It now defaults to the git-ignored project `data/runtime/`; the container keeps its explicit owned path.
- **Bandit, B608 (medium):** the analytics mart builds `CREATE`/`INSERT` statements from contract table and
  column names. Identifiers are now validated against `[a-z_][a-z0-9_]*`; values were already bound parameters.
- **Bandit, B105 (low, false positive):** a counter dictionary key `"pass": 0` read as a password. Rewritten.

## Suppressions

Every `# nosec` names a test and has a reason on the line above; `scripts/run_security_gates.py` fails if a
suppression omits the test ID.

| File | Test | Reason |
|---|---|---|
| `src/rivulet_localops/analytics_mart.py` | B608 | Identifiers validated from the fixed mart contract; values parameterised |
| `scripts/fetch_hobart_assets.py` | B310 | Fixed public HTTPS endpoint, not caller-supplied |
| `scripts/fetch_townsville_rfs.py` | B310 | Fixed official HTTPS endpoints, not caller-supplied |
| `scripts/verify_public_deployment.py` | B310 | Scheme restricted to https or loopback http just before the call |
| `scripts/run_security_gates.py` | B404, B603 | Fixed argument lists for the scanners; no shell and no caller input |

## Supply-chain decisions

- On 2026-03-19 an attacker force-pushed 76 of 77 `aquasecurity/trivy-action` tags and all `setup-trivy`
  tags to credential-stealing code (GHSA-69fq-xp46-6x23). The workflows therefore pin `trivy-action` to the
  signed v0.36.0 commit `ed142fd0673e97e23eac54620cfb913e5ce36c25`, which itself pins the patched
  `setup-trivy` v0.2.6 by hash.
- That action defaults to Trivy v0.70.0, which is affected by GHSA-mcj4-mphf-j9ff (below 0.71.1). The
  workflows set Trivy v0.76.1 explicitly.
- All other third-party actions (`docker/*`, `azure/*`) are now pinned to the commit behind their current
  release tag, with the version in a comment. GitHub-owned `actions/*` remain on major tags.
- Scanner versions and their full dependency closure are pinned in `requirements-security.lock`, which is
  never installed into the runtime image.

## Defect found while verifying

`scripts/verify.ps1` re-ran the APP-001–005 support exercises with `--date 2026-10-12` and wrote the output
back into the dated evidence folders. While the version stayed at 0.8.0 the files were byte-identical, which
hid the problem; the 0.9.0 bump made the 2026-10-12 evidence claim version 0.9.0. The rewritten files were
restored from git and the gate now writes those regression runs to a temporary folder.

## Hosted verification

The Trivy image scan and canary first ran on the private development repository on 2026-11-02 (run
41449721415): image `rivulet-localops:ci` on Debian 13.7 reported 0 fixable HIGH/CRITICAL findings, and the
seeded canary reported 1 CRITICAL, as expected. For the public v0.9.0 release (commit `c9ed08d`), hosted
main verify 41532906065 and
tag verify 41532909133 passed both the
Windows test job and the Linux security job, and the
container workflow 41532909073 scanned the
candidate image before publishing it: 0 fixable HIGH/CRITICAL in the Debian 13.7 layer and in every Python package.
Only then was `ghcr.io/zeeekrom/rivulet-localops:v0.9.0` pushed (index digest
`sha256:71a3aadb594ad2fca67961622b992b1ff29ecbe1c538945456f2133caadfa81b`, anonymously pullable).

## Claim boundary

- Bandit and pip-audit catch known Python anti-patterns and published advisories for pinned packages. A
  clean result is not a penetration test and does not cover business-logic flaws; F25 covers part of that.
- `ignore-unfixed` means vulnerabilities without an available fix are not blocking; they are visible in the
  scan output but do not fail the gate.
- Results depend on the advisory data available on the run date; a later run can fail on the same code, as
  the vite advisories did.
- TypeScript source is covered by npm audit only, not by a SAST tool.

## Evidence files

- `result.json` — machine-readable local gate result, including canaries and suppressions.
- `versions.txt` — runtime and scanner versions.
