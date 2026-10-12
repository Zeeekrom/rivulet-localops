from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


BOUNDARY_PATHS = (
    "docs",
    "openapi.json",
    "api/v1/submit",
    "ops/v1/ledger/integrity",
    "ops/v1/support/bundle",
    "ops/support",
)


def _request(url: str, *, method: str = "GET", timeout: float = 20) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers.items()), error.read()


def evaluate_health_payload(payload: dict[str, Any], expected_release: str) -> list[str]:
    failures: list[str] = []
    if payload.get("status") != "ok":
        failures.append("public health status is not ok")
    if payload.get("profile") != "public_demo":
        failures.append("deployment profile is not public_demo")
    if payload.get("release") != expected_release:
        failures.append(f"release mismatch: expected {expected_release}, observed {payload.get('release')}")
    if payload.get("ledger_integrity_ok") is not True:
        failures.append("runtime ledger integrity is not valid")
    return failures


def verify(url: str, expected_release: str, *, force_failure_after_checks: bool = False) -> dict[str, Any]:
    base = url.rstrip("/")
    checked_at = datetime.now(UTC).isoformat()
    status, headers, raw_health = _request(f"{base}/healthz")
    failures: list[str] = []
    try:
        health = json.loads(raw_health)
    except json.JSONDecodeError:
        health = {}
        failures.append("health response is not JSON")
    if status != 200:
        failures.append(f"health endpoint returned HTTP {status}")
    failures.extend(evaluate_health_payload(health, expected_release))

    security_headers = {
        "x-content-type-options": headers.get("X-Content-Type-Options"),
        "x-frame-options": headers.get("X-Frame-Options"),
        "content-security-policy": headers.get("Content-Security-Policy"),
    }
    if security_headers["x-content-type-options"] != "nosniff":
        failures.append("X-Content-Type-Options header is missing or invalid")
    if security_headers["x-frame-options"] != "DENY":
        failures.append("X-Frame-Options header is missing or invalid")

    boundaries: dict[str, int] = {}
    for path in BOUNDARY_PATHS:
        boundary_status, _, _ = _request(f"{base}/{path}")
        boundaries[path] = boundary_status
        if boundary_status != 404:
            failures.append(f"public boundary /{path} returned HTTP {boundary_status}")

    scenario_status, _, raw_scenario = _request(
        f"{base}/demo/v1/scenarios/blocked-shell/run",
        method="POST",
    )
    try:
        scenario = json.loads(raw_scenario)
    except json.JSONDecodeError:
        scenario = {}
        failures.append("capability-deny response is not JSON")
    if scenario_status != 200:
        failures.append(f"capability-deny scenario returned HTTP {scenario_status}")
    if scenario.get("observed_outcome") != "deny" or scenario.get("ledger_integrity_ok") is not True:
        failures.append("capability-deny scenario did not fail closed with a valid ledger")

    if force_failure_after_checks:
        failures.append("synthetic rollback drill requested a post-check failure")

    return {
        "schema_version": "1.0",
        "truth_class": "deployment_observation",
        "checked_at": checked_at,
        "url": base,
        "expected_release": expected_release,
        "observed_health": health,
        "security_headers": security_headers,
        "boundary_statuses": boundaries,
        "capability_deny": {
            "http_status": scenario_status,
            "observed_outcome": scenario.get("observed_outcome"),
            "ledger_integrity_ok": scenario.get("ledger_integrity_ok"),
        },
        "forced_failure": force_failure_after_checks,
        "passed": not failures,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a deployed Rivulet public demo and its boundary.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-release", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force-failure-after-checks", action="store_true")
    args = parser.parse_args()

    try:
        result = verify(
            args.url,
            args.expected_release,
            force_failure_after_checks=args.force_failure_after_checks,
        )
    except (OSError, TimeoutError) as error:
        result = {
            "schema_version": "1.0",
            "truth_class": "deployment_observation",
            "checked_at": datetime.now(UTC).isoformat(),
            "url": args.url.rstrip("/"),
            "expected_release": args.expected_release,
            "passed": False,
            "failures": [f"request failed: {type(error).__name__}"],
        }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
