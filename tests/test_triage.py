import json
from pathlib import Path

from fastapi.testclient import TestClient

from rivulet_localops.assets import AssetRepository
from rivulet_localops.main import create_app
from rivulet_localops.models import Coordinates, DiagnoseRequest
from rivulet_localops.providers import RulesTriageProvider


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


def test_explainable_waste_diagnosis_matches_asset(tmp_path: Path) -> None:
    provider = RulesTriageProvider(AssetRepository(_asset_file(tmp_path)))
    result = provider.diagnose(DiagnoseRequest(
        text="The public bin is overflowing beside the footpath",
        coordinates=Coordinates(latitude=-42.88675, longitude=147.31912),
    ))

    assert result.category.code == "waste_litter"
    assert result.priority.code == "P2"
    assert result.asset_match is not None
    assert result.asset_match.distance_metres < 2
    assert result.human_review_required is False
    assert any("Category evidence" in item for item in result.explanation)


def test_emergency_is_escalated_for_human_review(tmp_path: Path) -> None:
    provider = RulesTriageProvider(AssetRepository(_asset_file(tmp_path)))
    result = provider.diagnose(DiagnoseRequest(text="Water is flooding inside and a person is trapped"))

    assert result.category.code == "stormwater_drainage"
    assert result.priority.code == "P1"
    assert result.human_review_required is True
    assert "emergency services" in " ".join(result.missing_information)


def test_api_health_and_diagnose(tmp_path: Path) -> None:
    client = TestClient(create_app(_asset_file(tmp_path), ledger_path=tmp_path / "ledger.sqlite3"))
    health = client.get("/health")
    response = client.post("/api/v1/diagnose", json={"text": "A parking meter has stopped working"})

    assert health.status_code == 200
    assert health.json()["asset_count"] == 1
    assert response.status_code == 200
    assert response.json()["category"]["code"] == "parking"
