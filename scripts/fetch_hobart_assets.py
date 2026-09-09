"""Download the public City of Hobart litter-bin layer as EPSG:4326 GeoJSON."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


LAYER_URL = "https://services1.arcgis.com/NHqdsnvwfSTg42I8/arcgis/rest/services/ASSETS_Litter_Bins_public/FeatureServer/0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rivulet_localops.data_contracts import SourceField, SourceManifest, sha256_file, write_source_manifest  # noqa: E402


OUTPUT_PATH = PROJECT_ROOT / "data" / "hobart_litter_bins.geojson"
METADATA_PATH = PROJECT_ROOT / "data" / "hobart_litter_bins.metadata.json"
MANIFEST_PATH = PROJECT_ROOT / "data" / "source_manifests" / "D1_hobart_litter_bins.json"


def fetch_json(url: str) -> dict:
    with urlopen(url, timeout=60) as response:  # nosec B310: fixed public HTTPS endpoint
        return json.load(response)


def main() -> None:
    retrieved_at = datetime.now(UTC)
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
        "retrieved_at_utc": retrieved_at.isoformat(),
        "output_crs": "EPSG:4326",
        "feature_count": len(features),
        "purpose": "Public-asset matching in an independent educational prototype",
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    write_source_manifest(MANIFEST_PATH, SourceManifest(
        source_id="D1",
        title="City of Hobart ASSETS Litter Bins public feature layer",
        publisher="City of Hobart",
        landing_page="https://www.arcgis.com/home/item.html?id=285f4104635744b1a1b952c3934f2165",
        download_url=LAYER_URL,
        license_name="Creative Commons Attribution 4.0 International",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        retrieved_at_utc=retrieved_at,
        raw_relative_path=OUTPUT_PATH.relative_to(PROJECT_ROOT).as_posix(),
        content_sha256=sha256_file(OUTPUT_PATH),
        record_count=len(features),
        grain="One point feature per public litter-bin asset in the retrieved feature-layer snapshot.",
        data_truth_class="real_public_reference",
        schema_version="hobart-litter-bin-geojson-v1",
        encoding="UTF-8",
        crs="EPSG:4326",
        fields=[
            SourceField(name="OBJECTID", data_type="integer", nullable=False, description="ArcGIS object identifier."),
            SourceField(name="GlobalID", data_type="text", nullable=True, description="Preferred asset business key."),
            SourceField(name="Bin_Type", data_type="text", nullable=True, description="Publisher-supplied bin type."),
            SourceField(name="Description", data_type="text", nullable=True, description="Publisher-supplied description."),
            SourceField(name="Responsible_Unit", data_type="text", nullable=True, description="Responsible unit when present."),
            SourceField(name="last_edited_date", data_type="timestamp", nullable=True, description="Source edit time."),
            SourceField(name="geometry", data_type="GeoJSON Point", nullable=False, description="EPSG:4326 point."),
        ],
        limitations=[
            "Public asset reference data; not evidence of request volume, performance or condition.",
            "Missing optional attributes remain null and are not inferred.",
            "Each refresh requires a new timestamp, hash, count and schema-drift check.",
        ],
    ))
    print(f"Downloaded {len(features)} features to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
