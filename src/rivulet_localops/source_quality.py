"""High-signal quality checks for the first public reference sources."""

import calendar
import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .data_contracts import QualityCheck, SourceManifest, load_source_manifest, sha256_file


def _check(
    *,
    check_id: str,
    source_id: str,
    dimension: str,
    severity: str,
    rows_evaluated: int,
    failed_rows: int,
    detail: str,
    warn_only: bool = False,
) -> QualityCheck:
    if failed_rows == 0:
        status = "pass"
    elif warn_only:
        status = "warn"
    else:
        status = "fail"
    return QualityCheck(
        check_id=check_id,
        source_id=source_id,
        dimension=dimension,
        status=status,
        severity=severity,
        rows_evaluated=rows_evaluated,
        failed_rows=failed_rows,
        failure_rate=(failed_rows / rows_evaluated if rows_evaluated else 0.0),
        detail=detail,
    )


def _decode(path: Path, encoding: str) -> str:
    codec = "cp1252" if encoding == "Windows-1252" else "utf-8-sig"
    return path.read_text(encoding=codec)


def _manifest_checks(project_root: Path, manifest: SourceManifest) -> list[QualityCheck]:
    raw_path = project_root / manifest.raw_relative_path
    exists = raw_path.is_file()
    hash_failed = int(not exists or sha256_file(raw_path) != manifest.content_sha256)
    return [
        _check(
            check_id=f"{manifest.source_id.lower()}-snapshot-hash",
            source_id=manifest.source_id,
            dimension="integrity",
            severity="critical",
            rows_evaluated=1,
            failed_rows=hash_failed,
            detail="Raw snapshot exists and its SHA-256 matches the source manifest.",
        )
    ]


def profile_hobart_assets(project_root: Path, manifest: SourceManifest) -> tuple[list[QualityCheck], dict[str, Any]]:
    path = project_root / manifest.raw_relative_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features", [])
    asset_keys: list[str] = []
    invalid_geometry = 0
    missing_business_key = 0
    missing_description = 0

    for feature in features:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        global_id = str(properties.get("GlobalID") or "").strip()
        object_id = str(properties.get("OBJECTID") or feature.get("id") or "").strip()
        key = global_id or object_id
        if not key:
            missing_business_key += 1
        else:
            asset_keys.append(key.casefold())
        if not str(properties.get("Description") or "").strip():
            missing_description += 1
        if (
            geometry.get("type") != "Point"
            or len(coordinates) < 2
            or not (-180 <= float(coordinates[0]) <= 180)
            or not (-90 <= float(coordinates[1]) <= 90)
        ):
            invalid_geometry += 1

    duplicate_keys = sum(count - 1 for count in Counter(asset_keys).values() if count > 1)
    checks = _manifest_checks(project_root, manifest)
    checks.extend([
        _check(
            check_id="d1-record-count",
            source_id="D1",
            dimension="volume",
            severity="high",
            rows_evaluated=1,
            failed_rows=int(len(features) != manifest.record_count),
            detail=f"Observed {len(features)} features; manifest declares {manifest.record_count}.",
        ),
        _check(
            check_id="d1-business-key-complete",
            source_id="D1",
            dimension="completeness",
            severity="critical",
            rows_evaluated=len(features),
            failed_rows=missing_business_key,
            detail="Every feature has GlobalID, OBJECTID or feature id for an asset business key.",
        ),
        _check(
            check_id="d1-business-key-unique",
            source_id="D1",
            dimension="uniqueness",
            severity="critical",
            rows_evaluated=len(features),
            failed_rows=duplicate_keys,
            detail="Preferred GlobalID/fallback OBJECTID asset keys are unique after case normalization.",
        ),
        _check(
            check_id="d1-geometry-valid",
            source_id="D1",
            dimension="validity",
            severity="critical",
            rows_evaluated=len(features),
            failed_rows=invalid_geometry,
            detail="Every feature is a Point with valid EPSG:4326 longitude and latitude ranges.",
        ),
        _check(
            check_id="d1-description-present",
            source_id="D1",
            dimension="completeness",
            severity="low",
            rows_evaluated=len(features),
            failed_rows=missing_description,
            detail="Description is optional context; missing values are retained as null.",
            warn_only=True,
        ),
    ])
    return checks, {
        "record_count": len(features),
        "unique_asset_keys": len(set(asset_keys)),
        "missing_descriptions": missing_description,
        "crs": manifest.crs,
    }


def profile_townsville_requests(
    project_root: Path,
    manifest: SourceManifest,
) -> tuple[list[QualityCheck], dict[str, Any]]:
    path = project_root / manifest.raw_relative_path
    reader = csv.DictReader(_decode(path, manifest.encoding).splitlines())
    rows = list(reader)
    expected_columns = [field.name for field in manifest.fields]
    shape_failed = int(reader.fieldnames != expected_columns)
    blank_rows = 0
    invalid_rows = 0
    inconsistent_period_rows = 0
    negative_count_rows = 0
    future_period_rows = 0
    parsed: list[tuple[dict[str, str], date, int]] = []
    exact_rows: list[tuple[str, ...]] = []
    natural_keys: list[tuple[str, str, date]] = []
    group_descriptions: dict[str, set[str]] = defaultdict(set)
    category_descriptions: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        normalized = {column: (row.get(column) or "").strip() for column in expected_columns}
        exact_rows.append(tuple(normalized[column] for column in expected_columns))
        if any(not normalized[column] for column in expected_columns):
            blank_rows += 1
        try:
            period = datetime.strptime(normalized["Date"], "%d/%m/%Y").date()
            year = int(normalized["Year"])
            month = int(normalized["Month"])
            request_count = int(normalized["Request Count"])
        except (ValueError, TypeError):
            invalid_rows += 1
            continue
        if period.day != 1 or period.year != year or period.month != month:
            inconsistent_period_rows += 1
        if request_count < 0:
            negative_count_rows += 1
        if period > manifest.retrieved_at_utc.date():
            future_period_rows += 1
        parsed.append((normalized, period, request_count))
        natural_keys.append((normalized["Group Code"].casefold(), normalized["Category Code"].casefold(), period))
        group_descriptions[normalized["Group Code"].casefold()].add(normalized["Group Description"].casefold())
        category_descriptions[normalized["Category Code"].casefold()].add(normalized["Category Description"].casefold())

    exact_duplicates = sum(count - 1 for count in Counter(exact_rows).values() if count > 1)
    grain_duplicates = sum(count - 1 for count in Counter(natural_keys).values() if count > 1)
    group_label_conflicts = sum(len(values) > 1 for values in group_descriptions.values())
    category_label_conflicts = sum(len(values) > 1 for values in category_descriptions.values())
    periods = [period for _, period, _ in parsed]
    latest_period = max(periods)
    latest_period_end = latest_period.replace(day=calendar.monthrange(latest_period.year, latest_period.month)[1])
    freshness_lag_days = (manifest.retrieved_at_utc.date() - latest_period_end).days
    stale = int(freshness_lag_days > 62)

    checks = _manifest_checks(project_root, manifest)
    checks.extend([
        _check(
            check_id="d2-column-shape",
            source_id="D2",
            dimension="shape",
            severity="critical",
            rows_evaluated=1,
            failed_rows=shape_failed,
            detail=f"Observed columns match the {len(expected_columns)} manifest fields in order.",
        ),
        _check(
            check_id="d2-record-count",
            source_id="D2",
            dimension="volume",
            severity="high",
            rows_evaluated=1,
            failed_rows=int(len(rows) != manifest.record_count),
            detail=f"Observed {len(rows)} rows; manifest declares {manifest.record_count}.",
        ),
        _check(
            check_id="d2-required-completeness",
            source_id="D2",
            dimension="completeness",
            severity="high",
            rows_evaluated=len(rows),
            failed_rows=blank_rows,
            detail="All eight source fields are non-blank per aggregate row.",
        ),
        _check(
            check_id="d2-type-validity",
            source_id="D2",
            dimension="validity",
            severity="critical",
            rows_evaluated=len(rows),
            failed_rows=invalid_rows,
            detail="Date parses as DD/MM/YYYY and Year, Month and Request Count parse as integers.",
        ),
        _check(
            check_id="d2-period-consistency",
            source_id="D2",
            dimension="consistency",
            severity="high",
            rows_evaluated=len(rows),
            failed_rows=inconsistent_period_rows,
            detail="Date is the first day of the Year/Month supplied on the same row.",
        ),
        _check(
            check_id="d2-count-nonnegative",
            source_id="D2",
            dimension="validity",
            severity="critical",
            rows_evaluated=len(rows),
            failed_rows=negative_count_rows,
            detail="Published aggregate request counts are non-negative integers.",
        ),
        _check(
            check_id="d2-exact-row-unique",
            source_id="D2",
            dimension="uniqueness",
            severity="high",
            rows_evaluated=len(rows),
            failed_rows=exact_duplicates,
            detail="No duplicate full source rows after trimming whitespace.",
        ),
        _check(
            check_id="d2-normalized-key-collision",
            source_id="D2",
            dimension="uniqueness",
            severity="medium",
            rows_evaluated=len(rows),
            failed_rows=grain_duplicates,
            detail=(
                "Counts publisher rows that collide on case-normalized Group Code + Category Code + Date. "
                "Rows remain separate and are never silently merged; downstream facts use a deterministic "
                "full-row key and retain the raw codes."
            ),
            warn_only=True,
        ),
        _check(
            check_id="d2-no-future-period",
            source_id="D2",
            dimension="timeliness",
            severity="high",
            rows_evaluated=len(rows),
            failed_rows=future_period_rows,
            detail="No source period is later than the retrieval date.",
        ),
        _check(
            check_id="d2-monthly-freshness",
            source_id="D2",
            dimension="timeliness",
            severity="medium",
            rows_evaluated=1,
            failed_rows=stale,
            detail=f"Latest period ends {latest_period_end.isoformat()}; retrieval lag is {freshness_lag_days} days (warn above 62).",
            warn_only=True,
        ),
        _check(
            check_id="d2-group-label-stability",
            source_id="D2",
            dimension="consistency",
            severity="low",
            rows_evaluated=len(group_descriptions),
            failed_rows=group_label_conflicts,
            detail="Counts normalized group codes that map to more than one description across history.",
            warn_only=True,
        ),
        _check(
            check_id="d2-category-label-stability",
            source_id="D2",
            dimension="consistency",
            severity="low",
            rows_evaluated=len(category_descriptions),
            failed_rows=category_label_conflicts,
            detail="Counts normalized category codes that map to more than one description across history.",
            warn_only=True,
        ),
    ])
    return checks, {
        "record_count": len(rows),
        "encoding": manifest.encoding,
        "date_min": min(periods).isoformat(),
        "date_max": latest_period.isoformat(),
        "freshness_lag_days_from_period_end": freshness_lag_days,
        "distinct_group_codes": len(group_descriptions),
        "distinct_category_codes": len(category_descriptions),
        "published_request_count_total": sum(count for _, _, count in parsed),
        "exact_duplicate_rows": exact_duplicates,
        "natural_grain_duplicate_rows": grain_duplicates,
        "group_codes_with_multiple_labels": group_label_conflicts,
        "category_codes_with_multiple_labels": category_label_conflicts,
    }


def profile_sources(project_root: Path) -> dict[str, Any]:
    d1 = load_source_manifest(project_root / "data" / "source_manifests" / "D1_hobart_litter_bins.json")
    d2 = load_source_manifest(project_root / "data" / "source_manifests" / "D2_townsville_rfs.json")
    d1_checks, d1_summary = profile_hobart_assets(project_root, d1)
    d2_checks, d2_summary = profile_townsville_requests(project_root, d2)
    checks = d1_checks + d2_checks
    blocking = [check for check in checks if check.status == "fail" and check.severity in {"critical", "high"}]
    return {
        "profile_version": "1.0",
        "profiled_at_utc": max(d1.retrieved_at_utc, d2.retrieved_at_utc).astimezone(UTC).isoformat(),
        "status": "fail" if blocking else "pass_with_warnings" if any(c.status == "warn" for c in checks) else "pass",
        "source_summaries": {"D1": d1_summary, "D2": d2_summary},
        "check_counts": {
            "total": len(checks),
            "pass": sum(check.status == "pass" for check in checks),
            "warn": sum(check.status == "warn" for check in checks),
            "fail": sum(check.status == "fail" for check in checks),
            "blocking": len(blocking),
        },
        "checks": [check.model_dump(mode="json") for check in checks],
    }
