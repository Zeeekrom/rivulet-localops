# Data provenance

| Component | Status | Source and permitted use in this prototype |
|---|---|---|
| Litter-bin locations and attributes | Real public asset data | City of Hobart ArcGIS open-data service; retrieved by `scripts/fetch_hobart_assets.py` |
| Individual resident request text | Synthetic or manually authored evaluation examples | No real resident records are included |
| Triage category and priority labels | Project policy baseline | Demonstration decisions, not adopted council policy |
| Submission Gate policy | Synthetic, versioned policy pack | `policies/waste_litter_demo_v0.1.0.json`; approved only for this portfolio demonstration and not adopted council policy |
| Decision, review and provider-control events | Synthetic runtime data | Local SQLite file under `data/runtime/`; ignored by Git and never presented as council operational history |
| Response times, staffing and outcomes | Not yet implemented; must be synthetic unless supplied and approved by a council | Must never be presented as observed Hobart performance |

The retrieval script requests `outSR=4326`; this avoids silently treating the source service's projected coordinates as latitude/longitude. The accompanying metadata JSON records retrieval time, endpoint, CRS and feature count.
