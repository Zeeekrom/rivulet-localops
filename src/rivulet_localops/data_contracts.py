"""Machine-readable source contracts and reusable data-quality records."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


DataTruthClass = Literal["real_public_reference", "synthetic_operational"]
QualityStatus = Literal["pass", "warn", "fail"]
QualityDimension = Literal[
    "completeness",
    "uniqueness",
    "validity",
    "consistency",
    "integrity",
    "timeliness",
    "volume",
    "shape",
]


class SourceField(BaseModel):
    name: str = Field(min_length=1)
    data_type: str = Field(min_length=1)
    nullable: bool
    description: str = Field(min_length=1)


class SourceManifest(BaseModel):
    manifest_version: Literal["1.0"] = "1.0"
    source_id: str = Field(pattern=r"^D[1-9][0-9]*$")
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    landing_page: HttpUrl
    download_url: HttpUrl
    license_name: str = Field(min_length=1)
    license_url: HttpUrl
    retrieved_at_utc: datetime
    source_last_modified_utc: datetime | None = None
    raw_relative_path: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    record_count: int = Field(gt=0)
    grain: str = Field(min_length=1)
    data_truth_class: DataTruthClass
    schema_version: str = Field(min_length=1)
    encoding: str = Field(min_length=1)
    crs: str | None = None
    fields: list[SourceField] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def require_public_reference_for_downloaded_sources(self) -> "SourceManifest":
        if self.source_id in {"D1", "D2"} and self.data_truth_class != "real_public_reference":
            raise ValueError("D1 and D2 must remain real public reference data")
        if self.retrieved_at_utc.tzinfo is None or self.retrieved_at_utc.utcoffset() is None:
            raise ValueError("retrieved_at_utc must include a UTC offset")
        if (
            self.source_last_modified_utc is not None
            and (self.source_last_modified_utc.tzinfo is None or self.source_last_modified_utc.utcoffset() is None)
        ):
            raise ValueError("source_last_modified_utc must include a UTC offset")
        return self


class QualityCheck(BaseModel):
    check_id: str = Field(min_length=1)
    source_id: str = Field(pattern=r"^D[1-9][0-9]*$")
    dimension: QualityDimension
    status: QualityStatus
    severity: Literal["critical", "high", "medium", "low"]
    rows_evaluated: int = Field(ge=0)
    failed_rows: int = Field(ge=0)
    failure_rate: float = Field(ge=0, le=1)
    detail: str = Field(min_length=1)

    @model_validator(mode="after")
    def failure_counts_are_consistent(self) -> "QualityCheck":
        if self.failed_rows > self.rows_evaluated:
            raise ValueError("failed_rows cannot exceed rows_evaluated")
        expected_rate = self.failed_rows / self.rows_evaluated if self.rows_evaluated else 0.0
        if abs(self.failure_rate - expected_rate) > 0.000001:
            raise ValueError("failure_rate must equal failed_rows / rows_evaluated")
        return self


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_source_manifest(path: Path) -> SourceManifest:
    return SourceManifest.model_validate_json(path.read_text(encoding="utf-8"))


def write_source_manifest(path: Path, manifest: SourceManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_source_snapshot(project_root: Path, manifest: SourceManifest) -> None:
    raw_path = project_root / manifest.raw_relative_path
    if not raw_path.is_file():
        raise FileNotFoundError(f"Source snapshot is missing: {manifest.raw_relative_path}")
    actual_hash = sha256_file(raw_path)
    if actual_hash != manifest.content_sha256:
        raise ValueError(
            f"Source snapshot hash mismatch for {manifest.source_id}: "
            f"expected {manifest.content_sha256}, got {actual_hash}"
        )
