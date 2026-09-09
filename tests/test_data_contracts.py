import json
from pathlib import Path

import pytest

from rivulet_localops.data_contracts import QualityCheck, load_source_manifest, validate_source_snapshot
from rivulet_localops.source_quality import profile_sources


def test_hobart_manifest_matches_the_versioned_snapshot() -> None:
    project_root = Path(__file__).resolve().parents[1]
    manifest = load_source_manifest(project_root / "data" / "source_manifests" / "D1_hobart_litter_bins.json")

    assert manifest.source_id == "D1"
    assert manifest.record_count == 727
    assert manifest.data_truth_class == "real_public_reference"
    assert manifest.crs == "EPSG:4326"
    validate_source_snapshot(project_root, manifest)


def test_public_source_cannot_be_relabelled_as_synthetic() -> None:
    project_root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (project_root / "data" / "source_manifests" / "D1_hobart_litter_bins.json").read_text(encoding="utf-8")
    )
    payload["data_truth_class"] = "synthetic_operational"

    with pytest.raises(ValueError, match="real public reference"):
        from rivulet_localops.data_contracts import SourceManifest

        SourceManifest.model_validate(payload)


def test_quality_check_rate_must_match_counts() -> None:
    with pytest.raises(ValueError, match="failure_rate"):
        QualityCheck(
            check_id="bad-rate",
            source_id="D1",
            dimension="completeness",
            status="fail",
            severity="high",
            rows_evaluated=10,
            failed_rows=1,
            failure_rate=0.5,
            detail="Demonstrate a contradictory quality record.",
        )


def test_versioned_public_sources_have_no_blocking_quality_failures() -> None:
    project_root = Path(__file__).resolve().parents[1]
    report = profile_sources(project_root)

    assert report["check_counts"]["blocking"] == 0
    assert report["source_summaries"]["D1"]["record_count"] == 727
    assert report["source_summaries"]["D2"]["record_count"] == 24_197
    assert report["source_summaries"]["D2"]["encoding"] == "Windows-1252"
    assert report["source_summaries"]["D2"]["exact_duplicate_rows"] == 0
    assert report["source_summaries"]["D2"]["natural_grain_duplicate_rows"] == 1
    assert report["source_summaries"]["D2"]["group_codes_with_multiple_labels"] == 2
    assert report["source_summaries"]["D2"]["category_codes_with_multiple_labels"] == 35
