import csv
import sqlite3
from contextlib import closing
from pathlib import Path

from rivulet_localops.analytics_mart import build_analytics_mart
from rivulet_localops.data_contracts import load_source_manifest, validate_source_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_ledger_is_versioned_and_hash_pinned() -> None:
    manifest = load_source_manifest(PROJECT_ROOT / "data" / "source_manifests" / "D6_synthetic_ledger.json")

    assert manifest.data_truth_class == "synthetic_operational"
    assert manifest.record_count == 316
    assert manifest.content_sha256 == "796e8bd0542402da475bd878e2956a4fc157884c34b2d4ac3bb572b81ddcbf2c"
    validate_source_snapshot(PROJECT_ROOT, manifest)


def test_analytics_mart_reconciles_sources_and_truth_classes(tmp_path: Path) -> None:
    output_dir = tmp_path / "mart"
    report = build_analytics_mart(PROJECT_ROOT, output_dir)

    assert report["status"] == "pass"
    assert all(report["reconciliations"].values())
    assert report["table_rows"]["fact_reference_request_volume"] == 24_197
    assert report["table_rows"]["fact_decision"] == 180
    assert report["table_rows"]["fact_review"] == 120
    assert report["table_rows"]["fact_manual_fallback"] == 8
    assert report["metrics"]["gate_pass_rate"] == 0.4

    with closing(sqlite3.connect(output_dir / "rivulet_analytics.sqlite3")) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        reference_truth = connection.execute(
            "SELECT DISTINCT data_truth_class FROM fact_reference_request_volume"
        ).fetchall()
        decision_truth = connection.execute("SELECT DISTINCT data_truth_class FROM fact_decision").fetchall()
        normalized_collisions = connection.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT v.group_code_normalized, v.category_code_normalized, f.date_key
                FROM fact_reference_request_volume AS f
                JOIN dim_townsville_category_variant AS v
                  ON v.category_variant_key = f.category_variant_key
                GROUP BY v.group_code_normalized, v.category_code_normalized, f.date_key
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

    assert reference_truth == [("real_public_reference",)]
    assert decision_truth == [("synthetic_operational",)]
    assert normalized_collisions == 1


def test_metric_dictionary_has_no_invented_targets() -> None:
    with (PROJECT_ROOT / "analytics" / "metric_dictionary.csv").open(encoding="utf-8", newline="") as handle:
        metrics = list(csv.DictReader(handle))

    assert len(metrics) >= 8
    assert all(metric["target"] == "" for metric in metrics)
    assert all(metric["numerator"] and metric["denominator"] for metric in metrics if metric["metric_type"] == "rate")
    assert all(metric["truth_class"] in {"real_public_reference", "synthetic_operational"} for metric in metrics)
