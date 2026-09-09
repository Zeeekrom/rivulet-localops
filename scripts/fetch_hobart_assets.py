"""Download the public City of Hobart litter-bin layer as EPSG:4326 GeoJSON."""

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


LAYER_URL = "https://services1.arcgis.com/NHqdsnvwfSTg42I8/arcgis/rest/services/ASSETS_Litter_Bins_public/FeatureServer/0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "hobart_litter_bins.geojson"
METADATA_PATH = PROJECT_ROOT / "data" / "hobart_litter_bins.metadata.json"


def fetch_json(url: str) -> dict:
    with urlopen(url, timeout=60) as response:  # nosec B310: fixed public HTTPS endpoint
        return json.load(response)


def main() -> None:
    parameters = {
        "where": "1=1",
        "outFields": "OBJECTID,GlobalID,Bin_Type,Description,Responsible_Unit,last_edited_date",
        "returnGeometry": "true",
        "outSR": "4326",
        "resultRecordCount": "1000",
        "f": "geojson",
    }
    payload = fetch_json(f"{LAYER_URL}/query?{urlencode(parameters)}")
    features = payload.get("features", [])
    if not features:
        raise RuntimeError("ArcGIS query returned no features")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    metadata = {
        "source": LAYER_URL,
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "output_crs": "EPSG:4326",
        "feature_count": len(features),
        "purpose": "Public-asset matching in an independent educational prototype",
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Downloaded {len(features)} features to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
