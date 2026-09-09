import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class EvidenceRequirements(BaseModel):
    require_coordinates_for: list[str]
    require_asset_match_for: list[str]
    max_asset_distance_metres: float = Field(gt=0)


class GateThresholds(BaseModel):
    minimum_category_confidence: float = Field(ge=0, le=1)
    escalate_priorities: list[Literal["P1", "P2", "P3", "P4"]]


class PolicyPack(BaseModel):
    schema_version: Literal["1.0"]
    policy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: Literal["approved_for_demo"]
    is_synthetic: Literal[True]
    authority: Literal["human_product_owner"]
    approved_at: datetime
    scope_categories: list[str] = Field(min_length=1)
    permitted_actions: list[str] = Field(min_length=1)
    evidence: EvidenceRequirements
    thresholds: GateThresholds
    source_note: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_timezone_and_consistent_evidence_scope(self) -> "PolicyPack":
        if self.approved_at.tzinfo is None:
            raise ValueError("approved_at must include a timezone")
        evidence_categories = set(self.evidence.require_coordinates_for) | set(self.evidence.require_asset_match_for)
        unknown_categories = evidence_categories - set(self.scope_categories)
        if unknown_categories:
            raise ValueError(f"evidence requirements reference categories outside policy scope: {sorted(unknown_categories)}")
        return self

    @property
    def content_hash(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_policy_pack(path: Path) -> PolicyPack:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return PolicyPack.model_validate(payload)
