"""Build the versioned analytics mart from contracted public and synthetic sources."""

import csv
import hashlib
import io
import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any

from .data_contracts import load_source_manifest, validate_source_snapshot
from .source_quality import profile_sources


MART_VERSION = "1.0.0"


def _hash_key(*parts: object) -> str:
    value = "|".join("" if part is None else str(part).strip().casefold() for part in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _date_key(value: date) -> int:
    return value.year * 10_000 + value.month * 100 + value.day


def _read_townsville(project_root: Path, relative_path: str) -> list[dict[str, str]]:
    path = project_root / relative_path
    text = path.read_text(encoding="cp1252")
    return list(csv.DictReader(io.StringIO(text)))


def _read_events(project_root: Path, relative_path: str) -> list[dict[str, Any]]:
    path = project_root / relative_path
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _asset_rows(project_root: Path) -> list[dict[str, Any]]:
    payload = json.loads((project_root / "data" / "hobart_litter_bins.geojson").read_text(encoding="utf-8"))
    rows = []
    for feature in payload["features"]:
        properties = feature.get("properties") or {}
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        asset_key = str(properties.get("GlobalID") or properties.get("OBJECTID") or feature.get("id"))
        rows.append({
            "asset_key": asset_key,
            "source_key": "D1",
            "asset_type": "litter_bin",
            "description": properties.get("Description"),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "data_truth_class": "real_public_reference",
        })
    return sorted(rows, key=lambda row: row["asset_key"].casefold())


def _reference_rows(raw_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    variants: dict[str, dict[str, Any]] = {}
    facts: list[dict[str, Any]] = []
    for row_number, raw in enumerate(raw_rows, start=1):
        values = {key: (value or "").strip() for key, value in raw.items()}
        group_code_normalized = values["Group Code"].casefold()
        category_code_normalized = values["Category Code"].casefold()
        variant_key = _hash_key(
            group_code_normalized,
            values["Group Description"],
            category_code_normalized,
            values["Category Description"],
        )
        variants.setdefault(variant_key, {
            "category_variant_key": variant_key,
            "source_key": "D2",
            "group_code_normalized": group_code_normalized,
            "group_description": values["Group Description"],
            "category_code_normalized": category_code_normalized,
            "category_description": values["Category Description"],
            "data_truth_class": "real_public_reference",
        })
        period = datetime.strptime(values["Date"], "%d/%m/%Y").date()
        facts.append({
            "source_row_key": _hash_key("D2", row_number, *[values[key] for key in raw.keys()]),
            "source_row_number": row_number,
            "source_key": "D2",
            "date_key": _date_key(period),
            "category_variant_key": variant_key,
            "group_code_raw": values["Group Code"],
            "group_description_raw": values["Group Description"],
            "category_code_raw": values["Category Code"],
            "category_description_raw": values["Category Description"],
            "request_count": int(values["Request Count"]),
            "data_truth_class": "real_public_reference",
        })
    return sorted(variants.values(), key=lambda row: row["category_variant_key"]), facts


def _operational_rows(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    decisions: list[dict[str, Any]] = []
    gate_rules: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    fallbacks: list[dict[str, Any]] = []
    categories: dict[str, dict[str, Any]] = {}
    policies: dict[str, dict[str, Any]] = {}
    providers: dict[str, dict[str, Any]] = {}
    decision_times: dict[str, datetime] = {}

    for event in events:
        payload = event["payload"]
        occurred = datetime.fromisoformat(event["occurred_at"])
        if event["event_type"] == "decision.created":
            gate = payload["gate_decision"]
            diagnosis = gate["diagnosis"]
            category = diagnosis["category"]
            policy = payload["policy"]
            provider = payload["provider"]
            asset = payload["evidence"].get("asset_match")
            policy_key = _hash_key(policy["policy_id"], policy["version"], policy["content_hash"])
            provider_key = _hash_key(provider["provider"], provider["version"], provider["mode"])
            categories.setdefault(category["code"], {
                "category_key": category["code"],
                "category_label": category["label"],
                "taxonomy": "rivulet_demo_v1",
                "data_truth_class": "synthetic_operational",
            })
            policies.setdefault(policy_key, {
                "policy_key": policy_key,
                "policy_id": policy["policy_id"],
                "policy_version": policy["version"],
                "policy_title": policy["title"],
                "policy_content_hash": policy["content_hash"],
                "is_synthetic": int(policy["is_synthetic"]),
            })
            providers.setdefault(provider_key, {
                "provider_key": provider_key,
                "provider_id": provider["provider"],
                "provider_version": provider["version"],
                "provider_mode": provider["mode"],
            })
            decision_times[event["entity_id"]] = occurred
            decisions.append({
                "decision_key": event["entity_id"],
                "ledger_event_key": event["event_id"],
                "source_key": "D6",
                "date_key": _date_key(occurred.date()),
                "occurred_at_utc": occurred.isoformat(),
                "correlation_id": event["correlation_id"],
                "accountable_owner_id": payload["accountable_owner_id"],
                "policy_key": policy_key,
                "provider_key": provider_key,
                "environment_key": payload["environment"],
                "category_key": category["code"],
                "priority_code": diagnosis["priority"]["code"],
                "category_confidence": category["confidence"],
                "gate_status": gate["status"],
                "can_execute": int(gate["can_execute"]),
                "human_review_required": int(diagnosis["human_review_required"]),
                "proposed_action": payload["proposed_action"],
                "coordinates_supplied": int(payload["request"].get("coordinates") is not None),
                "asset_key": asset["source_id"] if asset else None,
                "asset_distance_metres": asset["distance_metres"] if asset else None,
                "data_truth_class": "synthetic_operational",
            })
            for rule in gate["rule_results"]:
                gate_rules.append({
                    "gate_rule_key": _hash_key(event["entity_id"], rule["rule_id"]),
                    "decision_key": event["entity_id"],
                    "rule_id": rule["rule_id"],
                    "rule_outcome": rule["outcome"],
                    "rule_effect": rule["effect"],
                    "rule_message": rule["message"],
                    "data_truth_class": "synthetic_operational",
                })
        elif event["event_type"] == "decision.reviewed":
            decision_time = decision_times[event["entity_id"]]
            reviews.append({
                "review_key": event["event_id"],
                "decision_key": event["entity_id"],
                "date_key": _date_key(occurred.date()),
                "occurred_at_utc": occurred.isoformat(),
                "reviewer_id": event["actor_id"],
                "review_action": payload["action"],
                "review_lag_minutes": round((occurred - decision_time).total_seconds() / 60, 2),
                "corrected_category": payload.get("corrected_category"),
                "corrected_priority": payload.get("corrected_priority"),
                "replacement_action": payload.get("replacement_action"),
                "data_truth_class": "synthetic_operational",
            })
        elif event["event_type"] == "decision.manual_fallback":
            provider_key = next(
                (key for key, value in providers.items() if value["provider_id"] == payload["provider_id"]),
                _hash_key(payload["provider_id"], "0.1.0", "baseline"),
            )
            providers.setdefault(provider_key, {
                "provider_key": provider_key,
                "provider_id": payload["provider_id"],
                "provider_version": "0.1.0",
                "provider_mode": "baseline",
            })
            fallbacks.append({
                "fallback_key": event["event_id"],
                "source_key": "D6",
                "date_key": _date_key(occurred.date()),
                "occurred_at_utc": occurred.isoformat(),
                "correlation_id": event["correlation_id"],
                "accountable_owner_id": payload["accountable_owner_id"],
                "provider_key": provider_key,
                "reason": payload["reason"],
                "data_truth_class": "synthetic_operational",
            })

    latest_review: dict[str, dict[str, Any]] = {}
    for review in reviews:
        latest_review[review["decision_key"]] = review
    for decision in decisions:
        review = latest_review.get(decision["decision_key"])
        decision["review_state"] = "reviewed" if review else "pending"
        decision["current_review_action"] = review["review_action"] if review else None

    return {
        "dim_category": sorted(categories.values(), key=lambda row: row["category_key"]),
        "dim_policy": sorted(policies.values(), key=lambda row: row["policy_key"]),
        "dim_provider": sorted(providers.values(), key=lambda row: row["provider_key"]),
        "fact_decision": decisions,
        "fact_gate_rule": gate_rules,
        "fact_review": reviews,
        "fact_manual_fallback": fallbacks,
    }


TABLE_SCHEMAS = {
    "dim_source": """source_key TEXT PRIMARY KEY, title TEXT NOT NULL, publisher TEXT NOT NULL,
        data_truth_class TEXT NOT NULL, record_count INTEGER NOT NULL, snapshot_utc TEXT NOT NULL,
        license_name TEXT NOT NULL, landing_page TEXT NOT NULL""",
    "dim_date": """date_key INTEGER PRIMARY KEY, calendar_date TEXT NOT NULL UNIQUE, year INTEGER NOT NULL,
        quarter INTEGER NOT NULL, month INTEGER NOT NULL, month_name TEXT NOT NULL""",
    "dim_asset": """asset_key TEXT PRIMARY KEY, source_key TEXT NOT NULL REFERENCES dim_source(source_key),
        asset_type TEXT NOT NULL, description TEXT, latitude REAL NOT NULL, longitude REAL NOT NULL,
        data_truth_class TEXT NOT NULL""",
    "dim_townsville_category_variant": """category_variant_key TEXT PRIMARY KEY,
        source_key TEXT NOT NULL REFERENCES dim_source(source_key), group_code_normalized TEXT NOT NULL,
        group_description TEXT NOT NULL, category_code_normalized TEXT NOT NULL,
        category_description TEXT NOT NULL, data_truth_class TEXT NOT NULL""",
    "dim_category": """category_key TEXT PRIMARY KEY, category_label TEXT NOT NULL, taxonomy TEXT NOT NULL,
        data_truth_class TEXT NOT NULL""",
    "dim_policy": """policy_key TEXT PRIMARY KEY, policy_id TEXT NOT NULL, policy_version TEXT NOT NULL,
        policy_title TEXT NOT NULL, policy_content_hash TEXT NOT NULL, is_synthetic INTEGER NOT NULL""",
    "dim_provider": """provider_key TEXT PRIMARY KEY, provider_id TEXT NOT NULL, provider_version TEXT NOT NULL,
        provider_mode TEXT NOT NULL""",
    "dim_environment": """environment_key TEXT PRIMARY KEY, environment_label TEXT NOT NULL,
        data_truth_class TEXT NOT NULL""",
    "fact_reference_request_volume": """source_row_key TEXT PRIMARY KEY, source_row_number INTEGER NOT NULL,
        source_key TEXT NOT NULL REFERENCES dim_source(source_key), date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
        category_variant_key TEXT NOT NULL REFERENCES dim_townsville_category_variant(category_variant_key),
        group_code_raw TEXT NOT NULL, group_description_raw TEXT NOT NULL, category_code_raw TEXT NOT NULL,
        category_description_raw TEXT NOT NULL, request_count INTEGER NOT NULL CHECK(request_count >= 0),
        data_truth_class TEXT NOT NULL""",
    "fact_decision": """decision_key TEXT PRIMARY KEY, ledger_event_key TEXT NOT NULL UNIQUE,
        source_key TEXT NOT NULL REFERENCES dim_source(source_key), date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
        occurred_at_utc TEXT NOT NULL, correlation_id TEXT NOT NULL, accountable_owner_id TEXT NOT NULL,
        policy_key TEXT NOT NULL REFERENCES dim_policy(policy_key), provider_key TEXT NOT NULL REFERENCES dim_provider(provider_key),
        environment_key TEXT NOT NULL REFERENCES dim_environment(environment_key),
        category_key TEXT NOT NULL REFERENCES dim_category(category_key), priority_code TEXT NOT NULL,
        category_confidence REAL NOT NULL, gate_status TEXT NOT NULL, can_execute INTEGER NOT NULL,
        human_review_required INTEGER NOT NULL, proposed_action TEXT NOT NULL, coordinates_supplied INTEGER NOT NULL,
        asset_key TEXT REFERENCES dim_asset(asset_key), asset_distance_metres REAL, review_state TEXT NOT NULL,
        current_review_action TEXT, data_truth_class TEXT NOT NULL""",
    "fact_gate_rule": """gate_rule_key TEXT PRIMARY KEY, decision_key TEXT NOT NULL REFERENCES fact_decision(decision_key),
        rule_id TEXT NOT NULL, rule_outcome TEXT NOT NULL, rule_effect TEXT NOT NULL, rule_message TEXT NOT NULL,
        data_truth_class TEXT NOT NULL""",
    "fact_review": """review_key TEXT PRIMARY KEY, decision_key TEXT NOT NULL REFERENCES fact_decision(decision_key),
        date_key INTEGER NOT NULL REFERENCES dim_date(date_key), occurred_at_utc TEXT NOT NULL, reviewer_id TEXT NOT NULL,
        review_action TEXT NOT NULL, review_lag_minutes REAL NOT NULL, corrected_category TEXT,
        corrected_priority TEXT, replacement_action TEXT, data_truth_class TEXT NOT NULL""",
    "fact_manual_fallback": """fallback_key TEXT PRIMARY KEY, source_key TEXT NOT NULL REFERENCES dim_source(source_key),
        date_key INTEGER NOT NULL REFERENCES dim_date(date_key), occurred_at_utc TEXT NOT NULL,
        correlation_id TEXT NOT NULL, accountable_owner_id TEXT NOT NULL,
        provider_key TEXT NOT NULL REFERENCES dim_provider(provider_key), reason TEXT NOT NULL,
        data_truth_class TEXT NOT NULL""",
    "fact_quality_check": """quality_check_key TEXT PRIMARY KEY, source_key TEXT NOT NULL REFERENCES dim_source(source_key),
        profiled_at_utc TEXT NOT NULL, quality_dimension TEXT NOT NULL, status TEXT NOT NULL, severity TEXT NOT NULL,
        rows_evaluated INTEGER NOT NULL, failed_rows INTEGER NOT NULL, failure_rate REAL NOT NULL, detail TEXT NOT NULL""",
}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"Refusing to write an empty mart table: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _build_dates(rows_by_table: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    date_keys: set[int] = set()
    for rows in rows_by_table.values():
        for row in rows:
            if "date_key" in row:
                date_keys.add(int(row["date_key"]))
    result = []
    for key in sorted(date_keys):
        value = datetime.strptime(str(key), "%Y%m%d").date()
        result.append({
            "date_key": key,
            "calendar_date": value.isoformat(),
            "year": value.year,
            "quarter": (value.month - 1) // 3 + 1,
            "month": value.month,
            "month_name": value.strftime("%B"),
        })
    return result


def _metrics(rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    decisions = rows["fact_decision"]
    reviews = rows["fact_review"]
    fallbacks = rows["fact_manual_fallback"]
    by_status = defaultdict(int)
    for decision in decisions:
        by_status[decision["gate_status"]] += 1
    eligible_asset = [
        row for row in decisions if row["category_key"] == "waste_litter" and row["coordinates_supplied"]
    ]
    return {
        "metric_context": "Fixed-seed synthetic operational regression dataset; not council performance evidence.",
        "data_truth_class": "synthetic_operational",
        "submission_attempt_count": len(decisions) + len(fallbacks),
        "decision_count": len(decisions),
        "gate_pass_rate": by_status["pass"] / len(decisions),
        "gate_reject_rate": by_status["reject"] / len(decisions),
        "gate_escalate_rate": by_status["escalate"] / len(decisions),
        "review_rate": len({row["decision_key"] for row in reviews}) / len(decisions),
        "override_rate_of_reviewed": sum(row["review_action"] == "override" for row in reviews) / len(reviews),
        "manual_fallback_rate": len(fallbacks) / (len(decisions) + len(fallbacks)),
        "median_review_lag_minutes": median(row["review_lag_minutes"] for row in reviews),
        "asset_match_rate_of_eligible": sum(row["asset_key"] is not None for row in eligible_asset) / len(eligible_asset),
    }


def build_analytics_mart(project_root: Path, output_dir: Path) -> dict[str, Any]:
    manifests = {
        source_id: load_source_manifest(project_root / "data" / "source_manifests" / filename)
        for source_id, filename in {
            "D1": "D1_hobart_litter_bins.json",
            "D2": "D2_townsville_rfs.json",
            "D6": "D6_synthetic_ledger.json",
        }.items()
    }
    for manifest in manifests.values():
        validate_source_snapshot(project_root, manifest)

    quality = profile_sources(project_root)
    if quality["check_counts"]["blocking"]:
        raise ValueError("Public source quality contains a blocking failure")
    townsville = _read_townsville(project_root, manifests["D2"].raw_relative_path)
    variants, reference_facts = _reference_rows(townsville)
    events = _read_events(project_root, manifests["D6"].raw_relative_path)
    operational = _operational_rows(events)

    rows: dict[str, list[dict[str, Any]]] = {
        "dim_source": [
            {
                "source_key": manifest.source_id,
                "title": manifest.title,
                "publisher": manifest.publisher,
                "data_truth_class": manifest.data_truth_class,
                "record_count": manifest.record_count,
                "snapshot_utc": manifest.retrieved_at_utc.isoformat(),
                "license_name": manifest.license_name,
                "landing_page": str(manifest.landing_page),
            }
            for manifest in manifests.values()
        ],
        "dim_asset": _asset_rows(project_root),
        "dim_townsville_category_variant": variants,
        "dim_environment": [{
            "environment_key": "local",
            "environment_label": "Local portfolio demonstration",
            "data_truth_class": "synthetic_operational",
        }],
        "fact_reference_request_volume": reference_facts,
        "fact_quality_check": [
            {
                "quality_check_key": check["check_id"],
                "source_key": check["source_id"],
                "profiled_at_utc": quality["profiled_at_utc"],
                "quality_dimension": check["dimension"],
                "status": check["status"],
                "severity": check["severity"],
                "rows_evaluated": check["rows_evaluated"],
                "failed_rows": check["failed_rows"],
                "failure_rate": check["failure_rate"],
                "detail": check["detail"],
            }
            for check in quality["checks"]
        ],
        **operational,
    }
    rows["dim_date"] = _build_dates(rows)

    output_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = output_dir / "rivulet_analytics.sqlite3"
    if sqlite_path.exists():
        sqlite_path.unlink()
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        for table, schema in TABLE_SCHEMAS.items():
            connection.execute(f"CREATE TABLE {table} ({schema})")
            table_rows = rows[table]
            columns = list(table_rows[0])
            placeholders = ",".join("?" for _ in columns)
            connection.executemany(
                f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
                [[row[column] for column in columns] for row in table_rows],
            )
        foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        connection.commit()
    finally:
        connection.close()
    if foreign_key_violations:
        raise ValueError(f"Mart contains foreign-key violations: {foreign_key_violations[:5]}")

    csv_dir = output_dir / "csv"
    for table, table_rows in rows.items():
        _write_csv(csv_dir / f"{table}.csv", table_rows)

    reconciliations = {
        "d1_asset_rows_match_manifest": len(rows["dim_asset"]) == manifests["D1"].record_count,
        "d2_fact_rows_match_manifest": len(reference_facts) == manifests["D2"].record_count,
        "d2_request_count_matches_profile": (
            sum(row["request_count"] for row in reference_facts)
            == quality["source_summaries"]["D2"]["published_request_count_total"]
        ),
        "d6_event_rows_match_manifest": len(events) == manifests["D6"].record_count,
        "ledger_sequence_is_contiguous": [event["sequence"] for event in events] == list(range(1, len(events) + 1)),
        "quality_gate_has_no_blocking_failures": quality["check_counts"]["blocking"] == 0,
        "foreign_keys_valid": not foreign_key_violations,
        "truth_classes_are_separated": (
            {row["data_truth_class"] for row in reference_facts} == {"real_public_reference"}
            and {row["data_truth_class"] for row in rows["fact_decision"]} == {"synthetic_operational"}
        ),
    }
    if not all(reconciliations.values()):
        raise ValueError(f"Mart reconciliation failed: {reconciliations}")
    report = {
        "mart_version": MART_VERSION,
        "status": "pass",
        "table_rows": {table: len(table_rows) for table, table_rows in rows.items()},
        "reconciliations": reconciliations,
        "metrics": _metrics(rows),
        "claim_boundary": (
            "D1/D2 are real public reference data. D6 and every decision/review/control metric are fixed-seed "
            "synthetic operational data and cannot support claims about real council performance or model accuracy."
        ),
    }
    (output_dir / "build_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
