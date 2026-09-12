from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class Coordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class DiagnoseRequest(BaseModel):
    text: str = Field(min_length=5, max_length=4_000)
    coordinates: Coordinates | None = None

    @model_validator(mode="after")
    def reject_blank_text(self) -> "DiagnoseRequest":
        if not self.text.strip():
            raise ValueError("text must contain a service-request description")
        return self


class CategoryResult(BaseModel):
    code: str
    label: str
    confidence: float = Field(ge=0, le=1)
    matched_terms: list[str]


class PriorityResult(BaseModel):
    code: Literal["P1", "P2", "P3", "P4"]
    label: str
    target_hours: int
    policy_rule: str


class AssetMatch(BaseModel):
    asset_type: str
    source_id: str
    description: str | None = None
    latitude: float
    longitude: float
    distance_metres: float = Field(ge=0)
    source: str


class EngineInfo(BaseModel):
    provider: str
    version: str
    mode: str


class DiagnoseResponse(BaseModel):
    diagnosis_id: str
    category: CategoryResult
    priority: PriorityResult
    asset_match: AssetMatch | None
    explanation: list[str]
    missing_information: list[str]
    human_review_required: bool
    engine: EngineInfo
    disclaimer: str


class DecisionSubmissionRequest(BaseModel):
    request: DiagnoseRequest
    proposed_action: str = Field(default="create_draft_work_order", min_length=1, max_length=100)
    accountable_owner_id: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")
    correlation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        min_length=8,
        max_length=100,
        pattern=r"^[A-Za-z0-9._:@-]+$",
    )
    data_truth_class: Literal["synthetic"] = "synthetic"
    source: Literal["portfolio_demo"] = "portfolio_demo"
    environment: Literal["local"] = "local"


class PolicyReference(BaseModel):
    policy_id: str
    version: str
    title: str
    is_synthetic: bool
    content_hash: str = Field(min_length=64, max_length=64)


class GateRuleResult(BaseModel):
    rule_id: str
    outcome: Literal["pass", "fail", "not_applicable"]
    effect: Literal["allow", "reject", "escalate"]
    message: str


class GateDecision(BaseModel):
    gate_event_id: str
    evaluated_at: datetime
    status: Literal["pass", "reject", "escalate"]
    can_execute: bool
    proposed_action: str
    policy: PolicyReference
    missing_information: list[str]
    rejection_reasons: list[str]
    escalation_reasons: list[str]
    rule_results: list[GateRuleResult]
    diagnosis: DiagnoseResponse


class ProviderReference(BaseModel):
    provider: str
    version: str
    mode: str


class DecisionEvidence(BaseModel):
    matched_terms: list[str]
    asset_match: AssetMatch | None


class ReviewRequest(BaseModel):
    reviewer_id: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")
    action: Literal["accept", "override", "escalate"]
    reason: str = Field(min_length=5, max_length=1_000)
    corrected_category: str | None = Field(default=None, min_length=1, max_length=100)
    corrected_priority: Literal["P1", "P2", "P3", "P4"] | None = None
    replacement_action: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_override_details(self) -> "ReviewRequest":
        corrections = (self.corrected_category, self.corrected_priority, self.replacement_action)
        if self.action == "override" and not any(corrections):
            raise ValueError("override requires at least one corrected field")
        if self.action != "override" and any(corrections):
            raise ValueError("corrected fields are only valid for an override")
        return self


class ReviewRecord(BaseModel):
    event_id: str
    ledger_sequence: int = Field(gt=0)
    occurred_at: datetime
    reviewer_id: str
    action: Literal["accept", "override", "escalate"]
    reason: str
    corrected_category: str | None
    corrected_priority: Literal["P1", "P2", "P3", "P4"] | None
    replacement_action: str | None
    previous_event_hash: str | None
    event_hash: str


class DecisionRecord(BaseModel):
    decision_id: str
    ledger_event_id: str
    ledger_sequence: int = Field(gt=0)
    recorded_at: datetime
    correlation_id: str
    request_hash: str
    request: DiagnoseRequest
    accountable_owner_id: str
    data_truth_class: Literal["synthetic"]
    source: Literal["portfolio_demo"]
    environment: Literal["local"]
    proposed_action: str
    policy: PolicyReference
    provider: ProviderReference
    evidence: DecisionEvidence
    tool_calls: list[str]
    gate_decision: GateDecision
    previous_event_hash: str | None
    event_hash: str
    review_history: list[ReviewRecord]
    current_review: ReviewRecord | None


class DecisionListResponse(BaseModel):
    count: int = Field(ge=0)
    items: list[DecisionRecord]


class ProviderControlRequest(BaseModel):
    disabled: bool
    operator_id: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")
    reason: str = Field(min_length=5, max_length=1_000)


class ProviderStatus(BaseModel):
    provider_id: str
    disabled: bool
    changed_at: datetime | None
    changed_by: str | None
    reason: str
    control_event_id: str | None
    ledger_sequence: int | None


class IntegrityReport(BaseModel):
    ok: bool
    event_count: int = Field(ge=0)
    head_hash: str | None
    first_invalid_sequence: int | None
    message: str


class ReplayRequest(BaseModel):
    operator_id: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")


class ReplayResult(BaseModel):
    decision_id: str
    replay_event_id: str
    ledger_sequence: int = Field(gt=0)
    policy_version_match: bool
    policy_hash_match: bool
    provider_version_match: bool
    gate_status_match: bool
    category_match: bool
    priority_match: bool
    rule_outcomes_match: bool
    reproducible: bool


class AgentToolPermission(BaseModel):
    tool_name: str = Field(min_length=3, max_length=100, pattern=r"^[a-z][a-z0-9_.-]+$")
    allowed_data_classes: list[str] = Field(min_length=1, max_length=10)
    resource_templates: list[str] = Field(min_length=1, max_length=10)


class AgentCapabilityProfile(BaseModel):
    registry_id: str
    registry_version: str
    registry_hash: str = Field(min_length=64, max_length=64)
    agent_id: str
    agent_version: str
    owner_id: str
    purpose: str
    automation_level: Literal["L0_shadow_read_only"]
    enabled: bool
    grant_ttl_seconds: int = Field(ge=30, le=900)
    max_tool_calls: int = Field(ge=1, le=10)
    credential_mode: Literal["none"]
    provider: ProviderReference
    allowed_tools: list[AgentToolPermission]
    allowed_data_classes: list[str]
    explicitly_denied_tools: list[str]
    default_policy_deny: Literal[True]


class AgentToolCallRequest(BaseModel):
    tool_name: str = Field(min_length=3, max_length=100, pattern=r"^[a-z][a-z0-9_.-]+$")
    resource: str = Field(min_length=3, max_length=200)
    data_class: str = Field(min_length=3, max_length=100)


class AgentToolReceipt(BaseModel):
    tool_name: str
    resource: str
    data_class: str
    decision: Literal["allow", "deny"]
    executed: bool
    reason: str


class AgentInvocationRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")
    request: DiagnoseRequest
    purpose: Literal["diagnose_case"] = "diagnose_case"
    correlation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        min_length=8,
        max_length=100,
        pattern=r"^[A-Za-z0-9._:@-]+$",
    )
    data_truth_class: Literal["synthetic"] = "synthetic"
    requested_tool_calls: list[AgentToolCallRequest] = Field(default_factory=list, max_length=8)


class AgentInvocationTrace(BaseModel):
    invocation_id: str
    agent_id: str
    agent_version: str
    owner_id: str
    purpose: Literal["diagnose_case"]
    request_id: str
    correlation_id: str
    data_truth_class: Literal["synthetic"]
    automation_level: Literal["L0_shadow_read_only"]
    registry_id: str
    registry_version: str
    registry_hash: str = Field(min_length=64, max_length=64)
    grant_id: str
    grant_issued_at: datetime
    grant_expires_at: datetime
    policy_pack_version: str
    provider: ProviderReference
    credential_mode: Literal["none"]
    allowed_tools: list[str]
    allowed_data_classes: list[str]
    tool_receipts: list[AgentToolReceipt]
    input_hash: str = Field(min_length=64, max_length=64)
    output_hash: str | None = Field(default=None, min_length=64, max_length=64)
    status: Literal["completed", "denied", "failed"]
    gate_result: Literal["not_run_read_only"] = "not_run_read_only"
    human_decision: Literal["pending"] = "pending"
    estimated_provider_cost: Literal[0] = 0
    latency_ms: float = Field(ge=0)
    termination_reason: str
    raw_input_stored: Literal[False] = False


class AgentInvocationAuditRecord(AgentInvocationTrace):
    ledger_event_id: str
    ledger_sequence: int = Field(gt=0)
    recorded_at: datetime
    previous_event_hash: str | None
    event_hash: str


class AgentInvocationResponse(BaseModel):
    diagnosis: DiagnoseResponse
    audit: AgentInvocationAuditRecord


class AgentInvocationListResponse(BaseModel):
    count: int = Field(ge=0)
    items: list[AgentInvocationAuditRecord]
