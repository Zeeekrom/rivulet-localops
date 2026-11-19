# F32–F35 · Policy v0.5.0 proposal (main record)

## Result

**Every acceptance check passes. No model was called and nothing was spent.** Policy v0.5.0 (schema 1.4) keeps every
v0.4.0 rule and changes three things:

1. **F32 · Wider multi-issue lexicon.** `POL-SINGLE-ISSUE-001` uses issue lexicon 1.1.1. On a second blind set it never
   saw, it spots **11 of 20** multi-issue requests, up from 5 of 20 with lexicon 1.0.0, and still flags **0 of 20**
   single-issue requests.
2. **F34 · Priority wording lives in the policy pack.** Water across a road and a dog at large become urgent (P2);
   night-time construction noise stays routine (P3). The levels follow published council service standards
   (`evidence/F34/2026-11-20/README.md`).
3. **F35 · Address check.** `POL-ADDRESS-001` sends a request to a person when the Hobart street or street address in its
   text is far from its coordinates, checked against 27,967 official LIST address points
   (`evidence/F35/2026-11-20/README.md`).

**F33 is measured and not adopted.** Rules classifier 0.2.0 picked the right category for many more single-issue
requests, but on the blind set it let **2 of 20** multi-issue requests pass as single waste drafts, so v0.5.0 keeps
classifier 0.1.0 (`evidence/F33/2026-11-20/README.md`).

Policy v0.5.0 **awaits the product owner's approval**. Until then the app and the public demo keep running v0.4.0.

| Check | Result |
|---|---|
| Frozen adversarial set (59 cases, `f25.json`) | No status changes from v0.4.0; 0 unsafe passes; residual register empty; category errors unchanged. AMB-001 and AMB-008 are now also named as two jobs |
| Regression set (12 cases) | Categories 12 of 12. Priorities 10 of 12: the two changes are exactly the F34 decisions ("water over the road", "stray dog … near the playground" go P3 → P2) |
| Own multi-issue set (seen, `multi-issue.json`) | 30 of 30 |
| First blind set (seen since 11-19, `blind-v1.json`) | 31 of 32; not a fair measure any more, shown for completeness |
| **Second blind set (unseen, run once)** | **28 of 40**: 11 of 20 multi-issue sent to a person (8 with every service named), 0 of 20 single-issue wrongly flagged |
| Demo scenarios (6) | Unchanged |
| Older policies | v0.1.0–v0.4.0 keep their content hashes; schema 1.4 sections are required together and refused on older schemas |
| Verification | 254 tests; `verify.ps1` passes |

## The second blind set

The F31 blind set had been read while widening the lexicon, so a fresh agent wrote a new one: 40 requests (20
multi-issue, 20 single-issue, 14 of the multi-issue ones without waste, 4 with three services), from the labelling rule
and the eight service descriptions only. It saw no code, no lexicon, no earlier case. Its labels were kept; it flagged
MC-05, MC-19 and MC-29 as debatable.

Order of events (commit times, 2026-11-20 AEDT):

| Time | Commit | What |
|---|---|---|
| 08:53 | `ab4677b`, `8ba3491` | Lexicon 1.1.0 written and frozen |
| 09:00 | `a24cced` | Classifier 0.2.0 committed |
| 09:00 | `c04ee23` | Second blind set frozen (SHA-256 pinned by a test) |
| 09:14 | `247d70a`, `436927c` | Lexicon 1.1.1 (adds graffiti, from the F25 diff on AMB-008, not from the blind set), address rule, proposed policy |
| after | this record | Blind set run once (`blind-v2-first-run.json`) |

The set's own note names lexicon 1.1.0. Lexicon 1.1.1 differs only by the word *graffiti*, which appears in none of the
40 blind requests: 1.1.0 and 1.1.1 give identical results on this set.

| Lexicon on the second blind set | Multi-issue spotted | … with every service named | Single-issue wrongly flagged |
|---|---|---|---|
| 1.0.0 (policy v0.4.0) | 5 of 20 | 2 of 20 | 0 of 20 |
| 1.1.0 / 1.1.1 (policy v0.5.0) | **11 of 20** | **8 of 20** | **0 of 20** |

The single run was made with the proposal as it then stood (classifier 0.2.0). After F33 was dropped, the same set was
evaluated with the final v0.5.0 (`blind-v2-final-policy.json`): the multi-issue rule reads only the lexicon, so its
outcomes are identical case by case; only the diagnosed category of single-issue requests differs.

**What the lexicon still misses** (12 of 40 wrong, all multi-issue: 9 read as one issue, and MC-16, MC-25 and MC-38
flagged as several but with a service wrong or missing, for example "dumped a trailer load of green waste" read as an
abandoned trailer): a toilet block that is
"feral" with "no water in the taps", a van "parked in the loading zone" for days, a caravan "parked on the street for over
a month", "doof doof music", a limb "went straight through the shelter roof", play equipment "wrecked", a parking meter
that is "busted", a reserve "massively overgrown" next to a boat trailer "left on the nature strip". These are ordinary
phrasings; the lexicon was **not** changed after this run. Every one of the 20 multi-issue requests still reached a
person under v0.5.0, because other rules escalated them; the multi-issue rule adds the instruction to split.

## Claim boundary

All sets are synthetic. The blind sets were written by agents, not residents, and say nothing about real request
volumes or how often people report two problems at once. A deterministic lexicon will keep missing wording it does not
list; the durable fix is a model that lists the issues, with this rule as the floor (not attempted: paid calls are
locked).
