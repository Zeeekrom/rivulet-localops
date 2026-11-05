# F27 · Location and jurisdiction layer (2026-11-05)

## Result

**PASS: 10 of 10 checks.** The Gate now knows where a request is (which municipality and locality the point falls in),
whose it is (City of Hobart or another council) and whether the place names in the text agree with the point. On the
frozen adversarial set, the new policy changes exactly one decision: LOC-002 ("Overflowing bin outside the Launceston
mall" with a Hobart point) moves from pass to escalate. No other case changes, clean controls included. No model was called.

| Check | Result |
|---|---|
| Point lookup agrees with the LIST service's own answers on 14 sample points | pass (14/14) |
| Reference snapshots match their manifests (hash, record count) | pass |
| Frozen set unchanged (`adversarial_v1.json`, SHA-256 `ea92357c…`) | pass |
| Policy v0.3.0 changes only LOC-002 (pass → escalate) | pass |
| Clean controls not over-blocked | pass |
| Current-policy unsafe passes are the registered residuals (only AMB-007 remains) | pass |
| Offline model path under v0.3.0 has the same single residual | pass |
| Eight labelled probes behave as specified | pass |
| Three canaries fail as expected | pass |
| Policy v0.1.0 and v0.2.0 hashes unchanged | pass |

## Why this layer, and where the idea comes from

LOC-002 was the symptom of a missing layer, not of a missing word list. Working intake systems all hold reference data
about places and jurisdictions:

- The City of Hobart's own request forms take the suburb from a list and send people elsewhere when the suburb is not in
  the municipality.
- FixMyStreet asks a boundary service (MapIt) which areas contain the pin, then picks the bodies and categories for
  those areas.
- Snap Send Solve routes each report by GPS to the responsible council or authority.
- Open311 GeoReport v2 takes location as coordinates, an address string or an address id, with a jurisdiction id.

A local student project at the UTAS 2026 Semester 2 ICT Expo (Tasmanian Leaders Impact Dashboard) already checked
addresses against the LIST's address points and municipal boundaries and summarised results by municipality. F27 reuses
that approach rather than inventing one.

## What was built

- **Reference data (D7, D8).** The LIST Local Government Areas (29 municipalities) and Locality and Postcode Areas
  (777 official localities), CC BY 3.0 AU, "the LIST © State of Tasmania". The snapshot is simplified on the server to
  about 20-30 m. Each manifest records the licence, the newest feature date and the capture date.
- **Point lookup.** Even-odd point-in-polygon on the snapshot. Each point is in the council's municipality, in another
  municipality, or outside every Tasmanian municipality.
- **Place names.** Taken from the same official locality and municipality names, never from a hand-written list. A name
  followed by a street type ("Cambridge Road") is a street, not a place. Official names that are also ordinary words
  ("Plenty", "Forest", "Penguin") count only after a location cue such as "in" or "near". A locality that straddles
  municipal borders keeps every municipality it overlaps; Wellington Park spans five.
- **Policy v0.3.0 (schema 1.2).** It adds two rules, which can only reject or escalate:
  - **POL-JURISDICTION-001:** a point in another Tasmanian municipality is rejected, with a referral to that council. A
    point outside every municipality is escalated.
  - **POL-PLACE-001:** an official place in the text that lies in another municipality, more than 2,000 m from the point,
    is escalated.
- **Same Gate for both paths.** The rules and the model path both reach these rules through the Gate.
- **Runtime policy.** The app now runs v0.3.0.

## Audit and probes

- **Audit rows.** `result.json` has one row per frozen case: the location state, municipality, locality, official
  places named, each rule's effect, and the status under v0.2.0 and v0.3.0.
  - Location states across the 59 cases: 55 in the council's municipality, 1 in another municipality (the "remote"
    preset, in West Coast), 1 outside Tasmania (null island) and 2 without coordinates.
- **Labelled probes (P-01 to P-08).** These cover:
  - a consistent suburb (Sandy Bay) and points in Glenorchy and Launceston, which are rejected with referrals;
  - Glenorchy named 2.8 km away from a Hobart point, which is escalated;
  - a street named after a locality, an ordinary word, a park spanning several municipalities, and a point mid-river,
    which is escalated.
- **Canaries.**
  - C-01: setting the jurisdiction to Launceston rejects the Hobart point.
  - C-02: widening the tolerance to 50 km stops the Glenorchy conflict but still catches Launceston.
  - C-03: under v0.2.0, LOC-002 still passes, so the change comes from the new rules.

## Limits

- **Snapshot.** The data is a dated snapshot of official boundaries, simplified to about 20-30 m. A point that close to a
  border may be assigned to the neighbour. The newest-feature time assumes Australian Eastern Standard Time when no time
  zone database is installed.
- **Place-name coverage.** Recognition covers official localities and municipalities only. Landmarks, streets and
  informal names are not recognised; ambiguous ordinary-word names are read conservatively.
- **Out of scope.** Parcel-level address checks against LIST address points, G-NAF, live geocoding, and referrals for
  assets owned by the state or utilities.
- **Evidence status.** The frozen set is self-authored synthetic text. These are regression results for the Gate, not a
  measure of real-world location accuracy.
