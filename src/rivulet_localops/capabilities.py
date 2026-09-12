import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models import AgentCapabilityProfile, AgentToolPermission, ProviderReference


class AgentCapabilityDefinition(BaseModel):
    agent_id: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")
    agent_version: str = Field(min_length=1, max_length=50)
    owner_id: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9._:@-]+$")
    purpose: str = Field(min_length=10, max_length=500)
    automation_level: Literal["L0_shadow_read_only"]
    enabled: bool
    grant_ttl_seconds: int = Field(ge=30, le=900)
    max_tool_calls: int = Field(ge=1, le=10)
    credential_mode: Literal["none"]
    provider: ProviderReference
    allowed_tools: list[AgentToolPermission] = Field(min_length=1, max_length=10)
    explicitly_denied_tools: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_tool_names(self) -> "AgentCapabilityDefinition":
        allowed = [item.tool_name for item in self.allowed_tools]
        if len(allowed) != len(set(allowed)):
            raise ValueError("allowed tool names must be unique")
        if set(allowed) & set(self.explicitly_denied_tools):
            raise ValueError("a tool cannot be both allowed and explicitly denied")
        return self


class CapabilityRegistry(BaseModel):
    registry_id: str = Field(min_length=3, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    status: Literal["approved_for_demo"]
    is_synthetic: Literal[True]
    agents: list[AgentCapabilityDefinition] = Field(min_length=1, max_length=20)
    content_hash: str = Field(min_length=64, max_length=64, exclude=True)

    @model_validator(mode="after")
    def validate_agent_ids(self) -> "CapabilityRegistry":
        agent_ids = [item.agent_id for item in self.agents]
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("agent IDs must be unique")
        return self

    def get(self, agent_id: str) -> AgentCapabilityDefinition | None:
        return next((item for item in self.agents if item.agent_id == agent_id), None)

    def profile(self, agent_id: str) -> AgentCapabilityProfile | None:
        definition = self.get(agent_id)
        if definition is None:
            return None
        data_classes = sorted(
            {data_class for permission in definition.allowed_tools for data_class in permission.allowed_data_classes}
        )
        return AgentCapabilityProfile(
            registry_id=self.registry_id,
            registry_version=self.version,
            registry_hash=self.content_hash,
            agent_id=definition.agent_id,
            agent_version=definition.agent_version,
            owner_id=definition.owner_id,
            purpose=definition.purpose,
            automation_level=definition.automation_level,
            enabled=definition.enabled,
            grant_ttl_seconds=definition.grant_ttl_seconds,
            max_tool_calls=definition.max_tool_calls,
            credential_mode=definition.credential_mode,
            provider=definition.provider,
            allowed_tools=definition.allowed_tools,
            allowed_data_classes=data_classes,
            explicitly_denied_tools=definition.explicitly_denied_tools,
            default_policy_deny=True,
        )


def load_capability_registry(path: Path) -> CapabilityRegistry:
    raw = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return CapabilityRegistry.model_validate({**raw, "content_hash": content_hash})
