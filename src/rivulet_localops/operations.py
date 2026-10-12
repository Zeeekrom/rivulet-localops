from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sqlite3
import threading
from collections import Counter, deque
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Literal, Mapping
from uuid import uuid4

from pydantic import BaseModel, Field

from . import __version__
from .ledger import SQLiteEventLedger
from .models import IntegrityReport, ProviderReference


ComponentStatus = Literal["healthy", "degraded", "unavailable"]
_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:@-]{8,100}$")
_RELEASE = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
_STATUS_ORDER: dict[ComponentStatus, int] = {"healthy": 0, "degraded": 1, "unavailable": 2}


def utc_now() -> datetime:
    return datetime.now(UTC)


def safe_identifier(value: str | None, prefix: str) -> str:
    if value and _IDENTIFIER.fullmatch(value):
        return value
    return f"{prefix}-{uuid4().hex}"


def release_label(environment: Mapping[str, str] | None = None) -> str:
    source = environment if environment is not None else os.environ
    candidate = source.get("RIVULET_RELEASE", f"v{__version__}")
    return candidate if _RELEASE.fullmatch(candidate) else f"v{__version__}"


def error_category(error: BaseException) -> str:
    name = type(error).__name__
    if name == "LedgerIntegrityError":
        return "ledger_integrity"
    if isinstance(error, PermissionError):
        return "permission_denied"
    if isinstance(error, FileNotFoundError):
        return "configuration_missing"
    if isinstance(error, sqlite3.Error):
        return "database_error"
    if isinstance(error, TimeoutError):
        return "dependency_timeout"
    return "unhandled_error"


class OperationalLogRecord(BaseModel):
    timestamp: datetime
    level: Literal["info", "warning", "error"]
    event_name: str
    component_name: str
    correlation_id: str
    request_id: str
    route: str
    method: str
    status_code: int = Field(ge=100, le=599)
    elapsed_ms: float = Field(ge=0)
    policy_version: str | None = None
    provider: str | None = None
    provider_version: str | None = None
    gate_result: str | None = None
    ledger_event_id: str | None = None
    error_category: str | None = None


class OperationalLogBuffer:
    """Bounded allowlist-only operational records; request bodies and headers are never stored."""

    def __init__(self, capacity: int = 500):
        if capacity < 10 or capacity > 10_000:
            raise ValueError("operational log capacity must be between 10 and 10000")
        self.capacity = capacity
        self._records: deque[OperationalLogRecord] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def append(self, **fields: Any) -> OperationalLogRecord:
        record = OperationalLogRecord(timestamp=utc_now(), **fields)
        with self._lock:
            self._records.append(record)
        return record

    def recent(self, limit: int = 100) -> list[OperationalLogRecord]:
        bounded_limit = min(max(limit, 1), 200)
        with self._lock:
            return list(self._records)[-bounded_limit:]


class ComponentHealth(BaseModel):
    component: str
    status: ComponentStatus
    summary: str
    checked_at: datetime
    details: dict[str, str | int | bool | None] = Field(default_factory=dict)


class InternalHealthReport(BaseModel):
    status: ComponentStatus
    checked_at: datetime
    release: str
    application_version: str
    profile: Literal["internal"] = "internal"
    components: list[ComponentHealth]


class DeploymentSummary(BaseModel):
    release: str
    deployment_id: str | None
    revision: str | None
    deployed_at: str | None
    source: str


class IncidentSummary(BaseModel):
    incident_id: str
    title: str
    environment: Literal["synthetic_experiment"] = "synthetic_experiment"
    status: Literal["runbook_available", "verified"]
    severity: Literal["SEV-2", "SEV-3"]


class SupportBundle(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    application_version: str
    release: str
    environment: str
    health: InternalHealthReport
    policy_pack_version: str
    ledger_integrity: IntegrityReport
    recent_error_summaries: list[dict[str, str | int]]
    recent_deployment: DeploymentSummary
    configuration_summary: dict[str, str | int | bool]
    redacted_operational_logs: list[OperationalLogRecord]
    recent_incidents: list[IncidentSummary]
    exported_at: datetime
    checksum_algorithm: Literal["sha256"] = "sha256"
    checksum: str = Field(min_length=64, max_length=64)


INCIDENTS: tuple[tuple[str, str, str], ...] = (
    ("APP-001", "API unavailable or degraded", "SEV-2"),
    ("APP-002", "Detectable deployment failure and rollback", "SEV-2"),
    ("APP-003", "Ledger integrity failure and restore", "SEV-2"),
    ("APP-004", "Configuration or permission failure", "SEV-3"),
    ("APP-005", "Provider unavailable and manual fallback", "SEV-2"),
)


class ApplicationOperations:
    def __init__(
        self,
        *,
        ledger: SQLiteEventLedger,
        policy_version: str,
        provider_reference: ProviderReference,
        operational_log: OperationalLogBuffer,
        asset_count: int,
        environment: Mapping[str, str] | None = None,
        health_overrides: Mapping[str, ComponentStatus] | None = None,
    ):
        self.ledger = ledger
        self.policy_version = policy_version
        self.provider_reference = provider_reference
        self.operational_log = operational_log
        self.asset_count = asset_count
        self.environment = dict(environment if environment is not None else os.environ)
        self.health_overrides = dict(health_overrides or {})

    def _component(
        self,
        name: str,
        status: ComponentStatus,
        summary: str,
        **details: str | int | bool | None,
    ) -> ComponentHealth:
        effective = self.health_overrides.get(name, status)
        effective_summary = "Synthetic health override is active." if effective != status else summary
        return ComponentHealth(
            component=name,
            status=effective,
            summary=effective_summary,
            checked_at=utc_now(),
            details=details,
        )

    def health(self) -> InternalHealthReport:
        components: list[ComponentHealth] = [
            self._component("api", "healthy", "API request handling is available."),
        ]
        try:
            integrity = self.ledger.verify_integrity()
            ledger_status: ComponentStatus = "healthy" if integrity.ok else "unavailable"
            components.append(
                self._component(
                    "database_ledger",
                    ledger_status,
                    "Hash chain is valid." if integrity.ok else "Hash chain verification failed; writes fail closed.",
                    integrity_ok=integrity.ok,
                    event_count=integrity.event_count,
                )
            )
        except (OSError, sqlite3.Error):
            integrity = IntegrityReport(
                ok=False,
                event_count=0,
                head_hash=None,
                first_invalid_sequence=None,
                message="Ledger could not be checked.",
            )
            components.append(
                self._component(
                    "database_ledger",
                    "unavailable",
                    "Ledger could not be checked.",
                    integrity_ok=False,
                    event_count=0,
                )
            )

        components.append(
            self._component(
                "policy_pack",
                "healthy",
                "Versioned policy pack is loaded.",
                version=self.policy_version,
            )
        )

        if integrity.ok:
            try:
                provider_status = self.ledger.get_provider_status(self.provider_reference.provider)
                components.append(
                    self._component(
                        "provider",
                        "degraded" if provider_status.disabled else "healthy",
                        "Provider is disabled; manual fallback is active."
                        if provider_status.disabled
                        else "Deterministic provider is available.",
                        provider=self.provider_reference.provider,
                        version=self.provider_reference.version,
                        manual_fallback=provider_status.disabled,
                    )
                )
            except (OSError, sqlite3.Error):
                components.append(self._component("provider", "unavailable", "Provider control state is unreadable."))
        else:
            components.append(
                self._component("provider", "unavailable", "Provider is blocked because ledger integrity is unavailable.")
            )

        release = release_label(self.environment)
        raw_release = self.environment.get("RIVULET_RELEASE", release)
        valid_release = bool(_RELEASE.fullmatch(raw_release))
        parent_writable = os.access(self.ledger.path.parent, os.W_OK)
        configuration_status: ComponentStatus = "healthy" if valid_release and parent_writable else "unavailable"
        components.append(
            self._component(
                "configuration",
                configuration_status,
                "Required runtime configuration is valid."
                if configuration_status == "healthy"
                else "Required runtime configuration or ledger permissions are invalid.",
                release_label_valid=valid_release,
                ledger_directory_writable=parent_writable,
            )
        )

        python_supported = tuple(map(int, platform.python_version_tuple()[:2])) >= (3, 11)
        components.append(
            self._component(
                "dependencies",
                "healthy" if python_supported else "degraded",
                "Runtime dependencies meet the supported baseline."
                if python_supported
                else "Python runtime is outside the supported baseline.",
                python=platform.python_version(),
                sqlite=sqlite3.sqlite_version,
            )
        )
        components.append(
            self._component(
                "build_version",
                "healthy" if release.lstrip("v") == __version__ else "degraded",
                "Release label matches the application package."
                if release.lstrip("v") == __version__
                else "Release label differs from the application package.",
                application_version=__version__,
                release=release,
            )
        )

        overall = max((component.status for component in components), key=_STATUS_ORDER.__getitem__)
        return InternalHealthReport(
            status=overall,
            checked_at=utc_now(),
            release=release,
            application_version=__version__,
            components=components,
        )

    def deployment(self) -> DeploymentSummary:
        return DeploymentSummary(
            release=release_label(self.environment),
            deployment_id=self.environment.get("RIVULET_DEPLOYMENT_ID"),
            revision=self.environment.get("RIVULET_REVISION"),
            deployed_at=self.environment.get("RIVULET_DEPLOYED_AT"),
            source=self.environment.get("RIVULET_DEPLOYMENT_SOURCE", "local_or_unspecified"),
        )

    def incidents(self) -> list[IncidentSummary]:
        verified = {
            item.strip()
            for item in self.environment.get("RIVULET_VERIFIED_INCIDENTS", "").split(",")
            if item.strip()
        }
        return [
            IncidentSummary(
                incident_id=incident_id,
                title=title,
                status="verified" if incident_id in verified else "runbook_available",
                severity=severity,
            )
            for incident_id, title, severity in INCIDENTS
        ]

    def configuration_summary(self) -> dict[str, str | int | bool]:
        non_root: str | bool
        if hasattr(os, "geteuid"):
            non_root = os.geteuid() != 0
        else:
            non_root = "not_applicable_on_windows"
        return {
            "deployment_profile": self.environment.get("RIVULET_DEPLOYMENT_PROFILE", "internal"),
            "audit_backend": "sqlite_append_only_sha256_chain",
            "operational_log_capacity": self.operational_log.capacity,
            "runtime_non_root": non_root,
            "secrets_in_support_bundle": False,
            "request_bodies_in_operational_logs": False,
            "asset_count": self.asset_count,
        }

    def _recent_error_summaries(self) -> list[dict[str, str | int]]:
        errors = [record for record in self.operational_log.recent(200) if record.error_category]
        counts = Counter((record.component_name, record.error_category or "unknown") for record in errors)
        latest: dict[tuple[str, str], datetime] = {}
        for record in errors:
            key = (record.component_name, record.error_category or "unknown")
            latest[key] = max(latest.get(key, record.timestamp), record.timestamp)
        return [
            {
                "component": component,
                "error_category": category,
                "count": count,
                "latest_at": latest[(component, category)].isoformat(),
            }
            for (component, category), count in sorted(counts.items())
        ]

    def support_bundle(self) -> SupportBundle:
        health = self.health()
        integrity_component = next(item for item in health.components if item.component == "database_ledger")
        integrity = self.ledger.verify_integrity() if integrity_component.details.get("integrity_ok") else IntegrityReport(
            ok=False,
            event_count=int(integrity_component.details.get("event_count", 0)),
            head_hash=None,
            first_invalid_sequence=None,
            message="Ledger integrity is unavailable.",
        )
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "application_version": __version__,
            "release": release_label(self.environment),
            "environment": self.environment.get("RIVULET_ENVIRONMENT", "local"),
            "health": health.model_dump(mode="json"),
            "policy_pack_version": self.policy_version,
            "ledger_integrity": integrity.model_dump(mode="json"),
            "recent_error_summaries": self._recent_error_summaries(),
            "recent_deployment": self.deployment().model_dump(mode="json"),
            "configuration_summary": self.configuration_summary(),
            "redacted_operational_logs": [
                record.model_dump(mode="json") for record in self.operational_log.recent(100)
            ],
            "recent_incidents": [incident.model_dump(mode="json") for incident in self.incidents()],
            "exported_at": utc_now().isoformat(),
            "checksum_algorithm": "sha256",
        }
        payload["checksum"] = "0" * 64
        bundle = SupportBundle.model_validate(payload)
        canonical = json.dumps(
            bundle.model_dump(mode="json", exclude={"checksum"}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return bundle.model_copy(update={"checksum": hashlib.sha256(canonical.encode("utf-8")).hexdigest()})


def operation_timer() -> float:
    return monotonic()


def elapsed_ms(started_at: float) -> float:
    return round((monotonic() - started_at) * 1000, 3)
