from scripts.verify_public_deployment import evaluate_health_payload


def test_deployment_health_accepts_matching_safe_public_release() -> None:
    payload = {
        "status": "ok",
        "profile": "public_demo",
        "release": "v0.8.0",
        "ledger_integrity_ok": True,
        "ledger_event_count": 3,
    }

    assert evaluate_health_payload(payload, "v0.8.0") == []


def test_deployment_health_detects_bad_release_and_degraded_integrity() -> None:
    payload = {
        "status": "degraded",
        "profile": "public_demo",
        "release": "v0.7.2",
        "ledger_integrity_ok": False,
    }

    failures = evaluate_health_payload(payload, "v0.8.0")

    assert "public health status is not ok" in failures
    assert "release mismatch: expected v0.8.0, observed v0.7.2" in failures
    assert "runtime ledger integrity is not valid" in failures
