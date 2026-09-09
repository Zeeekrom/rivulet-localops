"""Fetch the official Townsville monthly request-count CSV and source metadata."""

import csv
import io
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rivulet_localops.data_contracts import (  # noqa: E402
    SourceField,
    SourceManifest,
    sha256_file,
    write_source_manifest,
)


PACKAGE_ID = "ec957baf-a033-4143-add2-5d43ca8103fb"
RESOURCE_ID = "b44988c1-b09d-42be-b3a5-ce668f876c83"
LANDING_PAGE = "https://data.gov.au/data/dataset/townsville-city-council-customer-request-management-request-for-service"
DOWNLOAD_URL = (
    "https://data.gov.au/data/dataset/ec957baf-a033-4143-add2-5d43ca8103fb/resource/"
    "b44988c1-b09d-42be-b3a5-ce668f876c83/download/crm-request-for-service.csv"
)
PACKAGE_API = f"https://data.gov.au/data/api/3/action/package_show?id={PACKAGE_ID}"
EXPECTED_COLUMNS = [
    "Group Code",
    "Group Description",
    "Category Code",
    "Category Description",
    "Year",
    "Month",
    "Date",
    "Request Count",
]


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Rivulet-LocalOps/0.3 source snapshot"})
    with urlopen(request, timeout=120) as response:  # nosec B310: fixed official HTTPS endpoints
        return response.read()


def _decode_csv(payload: bytes) -> tuple[str, str]:
    try:
        return payload.decode("utf-8-sig"), "UTF-8 with optional BOM"
    except UnicodeDecodeError:
        return payload.decode("cp1252"), "Windows-1252"


def _as_utc_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    if value.endswith("Z") or "+" in value[10:]:
        return value
    return f"{value}Z"


def main() -> None:
    retrieved_at = datetime.now(UTC)
    csv_bytes = _download(DOWNLOAD_URL)
    text, encoding = _decode_csv(csv_bytes)
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != EXPECTED_COLUMNS:
        raise RuntimeError(f"Unexpected Townsville schema: {reader.fieldnames}")
    rows = list(reader)
    if not rows:
        raise RuntimeError("Townsville request resource returned no rows")

    metadata = json.loads(_download(PACKAGE_API))
    if metadata.get("success") is not True:
        raise RuntimeError("data.gov.au package API did not return success=true")
    package = metadata["result"]
    resource = next((item for item in package["resources"] if item["id"] == RESOURCE_ID), None)
    if resource is None:
        raise RuntimeError(f"Resource {RESOURCE_ID} is missing from package metadata")

    snapshot_date = retrieved_at.date().isoformat()
    raw_path = PROJECT_ROOT / "data" / "raw" / "townsville_rfs" / snapshot_date / "crm-request-for-service.csv"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(csv_bytes)

    manifest = SourceManifest(
        source_id="D2",
        title=package["title"],
        publisher=package["organization"]["title"],
        landing_page=LANDING_PAGE,
        download_url=DOWNLOAD_URL,
        license_name=package["license_title"],
        license_url=package["license_url"].replace("http://", "https://"),
        retrieved_at_utc=retrieved_at,
        source_last_modified_utc=_as_utc_timestamp(resource.get("last_modified")),
        raw_relative_path=raw_path.relative_to(PROJECT_ROOT).as_posix(),
        content_sha256=sha256_file(raw_path),
        record_count=len(rows),
        grain=(
            "One publisher-supplied monthly aggregate row. Case-normalized Group Code + Category Code + "
            "Date is not guaranteed unique; downstream facts use a deterministic full-row key."
        ),
        data_truth_class="real_public_reference",
        schema_version="townsville-rfs-csv-v1",
        encoding=encoding,
        fields=[
            SourceField(name="Group Code", data_type="text", nullable=False, description="Townsville service group code."),
            SourceField(name="Group Description", data_type="text", nullable=False, description="Townsville service group label."),
            SourceField(name="Category Code", data_type="text", nullable=False, description="Townsville request category code."),
            SourceField(name="Category Description", data_type="text", nullable=False, description="Townsville request category label."),
            SourceField(name="Year", data_type="integer", nullable=False, description="Calendar year supplied by the publisher."),
            SourceField(name="Month", data_type="integer", nullable=False, description="Calendar month number supplied by the publisher."),
            SourceField(name="Date", data_type="date", nullable=False, description="First day of the aggregate month in DD/MM/YYYY form."),
            SourceField(name="Request Count", data_type="integer", nullable=False, description="Published aggregate request count."),
        ],
        limitations=[
            "This is aggregate Townsville data, not individual request or Hobart operational data.",
            "Group and category taxonomies belong to Townsville and are not silently mapped to Rivulet categories.",
            "Code casing and code-to-label mappings can drift; preserve raw rows and do not use category code alone as a dimension key.",
            "The publisher may revise historical rows; every refresh requires a new dated snapshot and hash.",
        ],
    )
    manifest_path = PROJECT_ROOT / "data" / "source_manifests" / "D2_townsville_rfs.json"
    write_source_manifest(manifest_path, manifest)
    print(json.dumps({
        "source_id": manifest.source_id,
        "rows": manifest.record_count,
        "sha256": manifest.content_sha256,
        "raw_path": manifest.raw_relative_path,
        "manifest_path": manifest_path.relative_to(PROJECT_ROOT).as_posix(),
    }, indent=2))


if __name__ == "__main__":
    main()
