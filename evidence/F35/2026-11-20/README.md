# F35 · Address check against LIST address points

## Result

**12 of 12 probes correct; no change on the frozen adversarial set or the demo scenarios.** `POL-ADDRESS-001` (policy
schema 1.4) sends a request to a person when a Hobart street, or a street address, named in its text lies far from its
coordinates. `result.json` is produced by `scripts/run_address_eval.py`.

| Check | Result |
|---|---|
| Reference data (D9) | 27,967 LIST address points inside the City of Hobart, 681 streets, CC BY 3.0 AU (the LIST © State of Tasmania). Downloaded twice with identical content |
| Probes (real addresses) | 12 of 12: matching address passes; same address 1.8 km away escalates; street-only check; unit "3/40"; number inside a published range; number not on file falls back to the street; "Mt" for Mount; apostrophes; streets outside Hobart and plain names ignored; no coordinates or a point outside Hobart → not applicable |
| Tolerances | 200 m for a numbered address, 300 m for a street |
| Streets where a correct pin could still be escalated | 10 of 681 (1.5%): long roads with few addresses (Waterworks Rd, Proctors Rd, Pinnacle Rd, Huon Rd …), whose largest gap between address points exceeds 600 m |
| Speed | Loads in 0.1 s; about 1 ms per request |
| Synthetic sets | Three single-issue requests in the multi-issue sets now escalate: their text names a street 0.3–1.0 km from the set's fixed test point, which is the mismatch the rule exists to catch |

## How it works

Councils geocode a typed address and compare it with the pin before sending anyone. The rule does the same offline.
Only street names that exist in the snapshot are recognised, each followed by its street type ("Davey St", "Sandy Bay
Road"), so ordinary words are not read as streets. A number written directly before the street is looked up too,
including units ("3/40") and ranges ("11–17", same side of the street).

- A numbered address on file is compared with the pin (200 m).
- Otherwise the pin is compared with the nearest address point of that street (300 m).
- The rule can only escalate. It runs only when the pin is inside Hobart; outside, the jurisdiction rule already refers
  the request to the right council.

## Limits

- The snapshot covers Hobart only, so a street named in another municipality is ignored rather than flagged.
- Address points mark a property's geocode, not its frontage; a very large parcel can put a correct pin more than 200 m
  from its own address point.
- The LIST publishes no change date per address point (`ALTERED_ON` is empty on all 305,577), so the capture date is the
  only date recorded.
