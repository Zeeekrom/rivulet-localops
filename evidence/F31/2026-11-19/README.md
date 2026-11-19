# F31 · One request, one issue (AMB-007)

## Result

**PASS on every acceptance check. No model was called and no cost was incurred.** Policy v0.4.0 adds
`POL-SINGLE-ISSUE-001`: when the text of one request reports problems for two or more council services, the Gate sends
it to a person who splits it into one request per issue. AMB-007, the last registered residual on the frozen
adversarial set, now goes to a person, and nothing else on that set changes.

Policy v0.4.0 **awaits the product owner's approval**. Until then the app and the public demo keep running v0.3.0.

| Check | Result |
|---|---|
| New set frozen before the rule | `eval/multi_issue_v1.json`, 30 cases, committed in `c661efb` (21:04) before the rule in `e01c4cd` (21:11); a test pins its SHA-256 |
| Dev split (may guide the rule) | 15 of 15: 8 of 8 multi-issue cases sent to a person with every expected service named; 0 of 7 single-issue cases flagged |
| Test split (run once, after the rule was committed) | 15 of 15: 8 of 8 multi-issue cases sent to a person with every expected service named; 0 of 7 single-issue cases flagged |
| Frozen adversarial set (59 cases) | Only AMB-007 changes, pass to escalate; 0 unsafe passes under v0.4.0; clean controls unchanged; residual register empty |
| Regression set (12 cases) | Diagnosis unchanged, 12 of 12 category and priority; none of the 12 texts is read as two issues |
| Model path (offline fake) | A model that reports only the bin still cannot get AMB-007 past the Gate |
| Older policies | v0.1.0, v0.2.0 and v0.3.0 keep their content hashes; schema 1.3 is required for the new section |
| Verification | 229 tests |

## Blind check (written by a separate agent)

After the product owner approved policy v0.4.0, a separate agent wrote 32 requests (16 multi-issue, 16 single-issue)
from the labelling rule and the eight service descriptions only. It never saw the lexicon, the rule code or the earlier
cases, and wrote the way Hobart residents write: long sentences, lists, informal wording, typos. Its labels were kept as
written. The set was frozen in `e002bae` before the rule ran on it, and it was run once (`blind.json`).

| | Result |
|---|---|
| Single-issue requests wrongly flagged | **0 of 16** |
| Multi-issue requests the rule flagged | **5 of 16**; all expected services named in 3 |
| Multi-issue requests that still reached a person | **16 of 16** (15 were already escalated by earlier rules; the new rule caught MB-01) |

**The lexicon generalises poorly to wording it was not written for.** On the author's own set it found 16 of 16; on
independent wording it found 5 of 16. The misses are ordinary phrasings the lexicon does not list: a drain "on the
corner of Lord St and Sandy Bay Rd is completely blocked" (too many words between), a street light that "has been out
for over a week", path lights that "aren't working", a dog that "barks from 6am", music "blaring", "dumped a car",
pavers "lifted", "missing" or "smashed", a swing "hanging by one chain". No request was wrongly flagged, and no
multi-issue request passed as a single draft, but for 11 of 16 the person is not told the request needs splitting.

The lexicon was **not** changed after this run, so the blind set stays a fair measure. A better detector needs either a
much broader lexicon measured on a new blind set, or a model that lists the issues (the multi-intent extraction the
F25 residual note called for), with this rule as the deterministic floor.

## How it works

Real intake systems file one issue per request. NYC 311 defines a request as "a report about one issue at a specific
location" and asks people with several problems at one place to call. FixMyStreet councils such as Bromley and
Gloucestershire ask for separate issues on separate reports, because each report sits in one category. Rivulet does
not split a request itself, which would decide for the resident; it sends the request to a person and names the
services involved.

The rule reads the raw request text, independent of the provider, against a lexicon of **problem wording** for each of
the eight service categories: an overflowing bin, a pothole, a blocked drain, a fallen tree, a stray dog, a car parked
across a driveway, a broken toilet, loud music. Place nouns (road, footpath, park, drain, toilet, car park, parking
meter) are not in it, because they usually say where something is. "Litter bin" names a kind of bin. Several items of
the same kind are one issue. The message lists lexicon labels only, never the request text.

## What the numbers do and do not show

- **Most multi-issue requests were already going to a person.** Under v0.3.0, 15 of the 16 multi-issue cases in the new
  set were already escalated by other rules (the category was outside the waste policy, a competing service phrase, or
  low confidence); only MI-D01 and, on the frozen set, AMB-007 passed as a single draft. Both have a waste diagnosis and
  a second issue named by a single word ("pothole"). For the rest the decision is unchanged and the reason is new: the
  person now sees which services to split.
- **The author of the set also wrote the lexicon.** Freezing proves the set was not edited after the rule existed; it
  does not make the author blind to it. All 30 cases are self-authored and synthetic, so they say nothing about how
  often real requests contain several issues or how much of real wording the lexicon covers.
- **The lexicon is hand-written.** It will miss problem wording it does not list, and a missed second issue falls back
  to the earlier rules and to the reviewer who sees every pending draft.

## Side finding (not changed in F31)

Seven of the 14 single-issue cases go to a person under both v0.3.0 and v0.4.0, for reasons that predate F31: keyword
diagnosis takes a place noun as the category ("street", "stormwater drain", "parking meter", "community hall"), and the
v0.2.0 input screen treats another service's phrase used as a landmark as a competing service. This errs on the safe
side but adds human work. Using the same problem-wording idea in diagnosis is a candidate for a later slice.

## Files

- `multi-issue.json`: every case with the services found, the rule outcome and the Gate result under v0.3.0 and v0.4.0.
- `blind.json`: the blind set run, case by case.
- `result.json`: the acceptance summary.
