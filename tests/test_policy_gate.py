import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from rivulet_localops.main import DEFAULT_POLICY_PATH, create_app
from rivulet_localops.policy import load_policy_pack


def _asset_file(tmp_path: Path) -> Path:
    path = tmp_path / "assets.geojson"
    path.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "id": 1,
            "geometry": {"type": "Point", "coordinates": [147.319119, -42.886751]},
            "properties": {"OBJECTID": 1, "Description": "25lt Drop Plastic"},
        }],
    }), encoding="utf-8")
    return path


def _submit(client: TestClient, text: str, *, coordinates: dict[str, float] | None = None, action: str = "create_draft_work_order"):
    request: dict[str, object] = {"text": text}
    if coordinates is not None:
        request["coordinates"] = coordinates
    return client.post("/api/v1/submit", json={
        "request": request,
        "proposed_action": action,
        "accountable_owner_id": "owner.demo",
    })


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(_asset_file(tmp_path), ledger_path=tmp_path / "ledger.sqlite3"))


def test_demo_policy_is_explicitly_synthetic_and_approved() -> None:
    policy = load_policy_pack(DEFAULT_POLICY_PATH)

    assert policy.status == "approved_for_demo"
    assert policy.authority == "human_product_owner"
    assert policy.is_synthetic is True
    assert policy.scope_categories == ["waste_litter"]
    assert policy.permitted_actions == ["create_draft_work_order"]


def test_policy_loader_rejects_an_unlabelled_non_synthetic_policy(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    payload["is_synthetic"] = False
    path = tmp_path / "unsafe-policy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_policy_pack(path)


def test_valid_waste_draft_passes_with_traceable_policy(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = _submit(
        client,
        "The public bin is overflowing beside the footpath",
        coordinates={"latitude": -42.88675, "longitude": 147.31912},
    )

    assert response.status_code == 200
    record = response.json()
    result = record["gate_decision"]
    assert result["status"] == "pass"
    assert result["can_execute"] is True
    assert record["accountable_owner_id"] == "owner.demo"
    assert record["data_truth_class"] == "synthetic"
    assert result["policy"]["policy_id"] == "rivulet.synthetic.waste-litter"
    assert result["policy"]["version"] == "0.1.0"
    assert result["policy"]["is_synthetic"] is True
    assert len(result["policy"]["content_hash"]) == 64
    assert all(rule["outcome"] != "fail" for rule in result["rule_results"])


def test_missing_coordinates_are_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = _submit(client, "The public bin is overflowing beside the footpath")

    result = response.json()["gate_decision"]
    assert result["status"] == "reject"
    assert result["can_execute"] is False
    assert "coordinates.latitude and coordinates.longitude" in result["missing_information"]
    location_rule = next(rule for rule in result["rule_results"] if rule["rule_id"] == "POL-LOCATION-001")
    assert location_rule["outcome"] == "fail"


def test_emergency_is_escalated(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = _submit(client, "Water is flooding inside and a person is trapped")

    result = response.json()["gate_decision"]
    assert result["status"] == "escalate"
    assert result["can_execute"] is False
    assert any("Priority P1" in reason for reason in result["escalation_reasons"])


def test_out_of_scope_category_is_escalated(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = _submit(client, "A parking meter has stopped working")

    result = response.json()["gate_decision"]
    assert result["status"] == "escalate"
    assert any("outside the approved" in reason for reason in result["escalation_reasons"])


def test_unapproved_real_submission_action_is_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = _submit(
        client,
        "The public bin is overflowing beside the footpath",
        coordinates={"latitude": -42.88675, "longitude": 147.31912},
        action="submit_work_order",
    )

    result = response.json()["gate_decision"]
    assert result["status"] == "reject"
    assert result["can_execute"] is False
    assert any("not permitted" in reason for reason in result["rejection_reasons"])


def test_low_confidence_waste_classification_is_escalated(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = _submit(
        client,
        "There is rubbish outside",
        coordinates={"latitude": -42.88675, "longitude": 147.31912},
    )

    result = response.json()["gate_decision"]
    assert result["diagnosis"]["category"]["code"] == "waste_litter"
    assert result["status"] == "escalate"
    assert any("below the policy threshold" in reason for reason in result["escalation_reasons"])
