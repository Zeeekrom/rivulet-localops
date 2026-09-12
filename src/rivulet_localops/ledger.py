import hashlib
import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import (
    AgentInvocationAuditRecord,
    AgentInvocationListResponse,
    AgentInvocationTrace,
    DecisionEvidence,
    DecisionListResponse,
    DecisionRecord,
    DecisionSubmissionRequest,
    GateDecision,
    IntegrityReport,
    ProviderControlRequest,
    ProviderReference,
    ProviderStatus,
    ReplayResult,
    ReviewRecord,
    ReviewRequest,
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_event_hash TEXT,
    event_hash TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_ledger_event_type ON ledger_events(event_type, sequence);
CREATE INDEX IF NOT EXISTS idx_ledger_entity ON ledger_events(entity_id, sequence);
PRAGMA user_version = 1;
"""


class LedgerIntegrityError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class SQLiteEventLedger:
    """Append-only demonstration ledger with a global SHA-256 hash chain."""

    def __init__(
        self,
        path: Path,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.path = path
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._clock = clock or (lambda: datetime.now(UTC))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @staticmethod
    def _hash_material(
        *,
        sequence: int,
        event_id: str,
        event_type: str,
        occurred_at: str,
        actor_id: str,
        correlation_id: str,
        entity_id: str,
        payload: dict[str, Any],
        previous_event_hash: str | None,
    ) -> str:
        return _canonical_json({
            "sequence": sequence,
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "actor_id": actor_id,
            "correlation_id": correlation_id,
            "entity_id": entity_id,
            "payload": payload,
            "previous_event_hash": previous_event_hash,
        })

    def _verify_rows(self, rows: list[sqlite3.Row]) -> IntegrityReport:
        previous_hash: str | None = None
        expected_sequence = 1
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                return IntegrityReport(
                    ok=False,
                    event_count=len(rows),
                    head_hash=previous_hash,
                    first_invalid_sequence=row["sequence"],
                    message="Ledger payload is not valid JSON.",
                )
            material = self._hash_material(
                sequence=row["sequence"],
                event_id=row["event_id"],
                event_type=row["event_type"],
                occurred_at=row["occurred_at"],
                actor_id=row["actor_id"],
                correlation_id=row["correlation_id"],
                entity_id=row["entity_id"],
                payload=payload,
                previous_event_hash=row["previous_event_hash"],
            )
            if (
                row["sequence"] != expected_sequence
                or row["previous_event_hash"] != previous_hash
                or row["event_hash"] != _sha256(material)
            ):
                return IntegrityReport(
                    ok=False,
                    event_count=len(rows),
                    head_hash=previous_hash,
                    first_invalid_sequence=row["sequence"],
                    message="Ledger hash chain verification failed.",
                )
            previous_hash = row["event_hash"]
            expected_sequence += 1

        return IntegrityReport(
            ok=True,
            event_count=len(rows),
            head_hash=previous_hash,
            first_invalid_sequence=None,
            message="Ledger hash chain is valid.",
        )

    def verify_integrity(self) -> IntegrityReport:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM ledger_events ORDER BY sequence").fetchall()
        return self._verify_rows(rows)

    def event_count(self) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM ledger_events").fetchone()
        return int(row["count"])

    @staticmethod
    def _agent_audit_from_row(row: sqlite3.Row) -> AgentInvocationAuditRecord:
        payload = json.loads(row["payload_json"])
        payload.pop("schema_version", None)
        return AgentInvocationAuditRecord(
            ledger_event_id=row["event_id"],
            ledger_sequence=row["sequence"],
            recorded_at=row["occurred_at"],
            previous_event_hash=row["previous_event_hash"],
            event_hash=row["event_hash"],
            **payload,
        )

    def record_agent_invocation(self, trace: AgentInvocationTrace) -> AgentInvocationAuditRecord:
        event = self._append(
            event_type=f"agent.invocation.{trace.status}",
            actor_id=trace.agent_id,
            correlation_id=trace.correlation_id,
            entity_id=trace.invocation_id,
            payload={"schema_version": "1.0", **trace.model_dump(mode="json")},
        )
        return self._agent_audit_from_row(event)

    def list_agent_invocations(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
    ) -> AgentInvocationListResponse:
        if status is None:
            query = "SELECT * FROM ledger_events WHERE event_type LIKE 'agent.invocation.%' ORDER BY sequence DESC LIMIT ?"
            parameters: tuple[Any, ...] = (limit,)
        else:
            query = "SELECT * FROM ledger_events WHERE event_type = ? ORDER BY sequence DESC LIMIT ?"
            parameters = (f"agent.invocation.{status}", limit)
        with closing(self._connect()) as connection:
            rows = connection.execute(query, parameters).fetchall()
        items = [self._agent_audit_from_row(row) for row in rows]
        return AgentInvocationListResponse(count=len(items), items=items)

    def _append(
        self,
        *,
        event_type: str,
        actor_id: str,
        correlation_id: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> sqlite3.Row:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT * FROM ledger_events ORDER BY sequence").fetchall()
            integrity = self._verify_rows(existing)
            if not integrity.ok:
                raise LedgerIntegrityError(integrity.message)

            sequence = len(existing) + 1
            previous_hash = existing[-1]["event_hash"] if existing else None
            event_id = self._id_factory()
            occurred_at = self._clock().isoformat()
            material = self._hash_material(
                sequence=sequence,
                event_id=event_id,
                event_type=event_type,
                occurred_at=occurred_at,
                actor_id=actor_id,
                correlation_id=correlation_id,
                entity_id=entity_id,
                payload=payload,
                previous_event_hash=previous_hash,
            )
            event_hash = _sha256(material)
            connection.execute(
                """
                INSERT INTO ledger_events (
                    sequence, event_id, event_type, occurred_at, actor_id,
                    correlation_id, entity_id, payload_json, previous_event_hash, event_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sequence,
                    event_id,
                    event_type,
                    occurred_at,
                    actor_id,
                    correlation_id,
                    entity_id,
                    _canonical_json(payload),
                    previous_hash,
                    event_hash,
                ),
            )
            connection.commit()
            return connection.execute("SELECT * FROM ledger_events WHERE event_id = ?", (event_id,)).fetchone()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def record_decision(self, submission: DecisionSubmissionRequest, gate_decision: GateDecision) -> DecisionRecord:
        decision_id = self._id_factory()
        request_payload = submission.request.model_dump(mode="json")
        payload = {
            "schema_version": "1.0",
            "request_hash": _sha256(_canonical_json(request_payload)),
            "request": request_payload,
            "accountable_owner_id": submission.accountable_owner_id,
            "data_truth_class": submission.data_truth_class,
            "source": submission.source,
            "environment": submission.environment,
            "proposed_action": submission.proposed_action,
            "policy": gate_decision.policy.model_dump(mode="json"),
            "provider": gate_decision.diagnosis.engine.model_dump(mode="json"),
            "evidence": {
                "matched_terms": gate_decision.diagnosis.category.matched_terms,
                "asset_match": (
                    gate_decision.diagnosis.asset_match.model_dump(mode="json")
                    if gate_decision.diagnosis.asset_match
                    else None
                ),
            },
            "tool_calls": [],
            "gate_decision": gate_decision.model_dump(mode="json"),
        }
        self._append(
            event_type="decision.created",
            actor_id="system:rivulet-api",
            correlation_id=submission.correlation_id,
            entity_id=decision_id,
            payload=payload,
        )
        record = self.get_decision(decision_id)
        if record is None:
            raise RuntimeError("decision was not readable after it was recorded")
        return record

    def record_manual_fallback(self, submission: DecisionSubmissionRequest, provider_id: str) -> sqlite3.Row:
        request_payload = submission.request.model_dump(mode="json")
        return self._append(
            event_type="decision.manual_fallback",
            actor_id="system:rivulet-api",
            correlation_id=submission.correlation_id,
            entity_id=self._id_factory(),
            payload={
                "schema_version": "1.0",
                "provider_id": provider_id,
                "request_hash": _sha256(_canonical_json(request_payload)),
                "accountable_owner_id": submission.accountable_owner_id,
                "data_truth_class": submission.data_truth_class,
                "source": submission.source,
                "environment": submission.environment,
                "reason": "Provider disabled by kill switch; route to manual handling.",
            },
        )

    @staticmethod
    def _review_from_row(row: sqlite3.Row) -> ReviewRecord:
        payload = json.loads(row["payload_json"])
        return ReviewRecord(
            event_id=row["event_id"],
            ledger_sequence=row["sequence"],
            occurred_at=row["occurred_at"],
            reviewer_id=row["actor_id"],
            action=payload["action"],
            reason=payload["reason"],
            corrected_category=payload.get("corrected_category"),
            corrected_priority=payload.get("corrected_priority"),
            replacement_action=payload.get("replacement_action"),
            previous_event_hash=row["previous_event_hash"],
            event_hash=row["event_hash"],
        )

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        with closing(self._connect()) as connection:
            created = connection.execute(
                "SELECT * FROM ledger_events WHERE entity_id = ? AND event_type = 'decision.created'",
                (decision_id,),
            ).fetchone()
            if created is None:
                return None
            review_rows = connection.execute(
                "SELECT * FROM ledger_events WHERE entity_id = ? AND event_type = 'decision.reviewed' ORDER BY sequence",
                (decision_id,),
            ).fetchall()

        payload = json.loads(created["payload_json"])
        reviews = [self._review_from_row(row) for row in review_rows]
        return DecisionRecord(
            decision_id=decision_id,
            ledger_event_id=created["event_id"],
            ledger_sequence=created["sequence"],
            recorded_at=created["occurred_at"],
            correlation_id=created["correlation_id"],
            request_hash=payload["request_hash"],
            request=payload["request"],
            accountable_owner_id=payload["accountable_owner_id"],
            data_truth_class=payload["data_truth_class"],
            source=payload["source"],
            environment=payload["environment"],
            proposed_action=payload["proposed_action"],
            policy=payload["policy"],
            provider=ProviderReference(**payload["provider"]),
            evidence=DecisionEvidence(**payload["evidence"]),
            tool_calls=payload["tool_calls"],
            gate_decision=payload["gate_decision"],
            previous_event_hash=created["previous_event_hash"],
            event_hash=created["event_hash"],
            review_history=reviews,
            current_review=reviews[-1] if reviews else None,
        )

    def list_decisions(self, *, limit: int = 50, review_state: str | None = None) -> DecisionListResponse:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT entity_id FROM ledger_events WHERE event_type = 'decision.created' ORDER BY sequence DESC LIMIT ?",
                (limit,),
            ).fetchall()
        records = [self.get_decision(row["entity_id"]) for row in rows]
        items = [record for record in records if record is not None]
        if review_state == "pending":
            items = [record for record in items if record.current_review is None]
        elif review_state == "reviewed":
            items = [record for record in items if record.current_review is not None]
        return DecisionListResponse(count=len(items), items=items)

    def record_review(self, decision_id: str, review: ReviewRequest) -> DecisionRecord:
        decision = self.get_decision(decision_id)
        if decision is None:
            raise KeyError(decision_id)
        self._append(
            event_type="decision.reviewed",
            actor_id=review.reviewer_id,
            correlation_id=decision.correlation_id,
            entity_id=decision_id,
            payload={"schema_version": "1.0", **review.model_dump(mode="json", exclude={"reviewer_id"})},
        )
        updated = self.get_decision(decision_id)
        if updated is None:
            raise RuntimeError("decision was not readable after review was recorded")
        return updated

    def get_provider_status(self, provider_id: str) -> ProviderStatus:
        entity_id = f"provider:{provider_id}"
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT * FROM ledger_events
                WHERE entity_id = ? AND event_type = 'provider.control_changed'
                ORDER BY sequence DESC LIMIT 1
                """,
                (entity_id,),
            ).fetchone()
        if row is None:
            return ProviderStatus(
                provider_id=provider_id,
                disabled=False,
                changed_at=None,
                changed_by=None,
                reason="No kill-switch event recorded; provider defaults to enabled.",
                control_event_id=None,
                ledger_sequence=None,
            )
        payload = json.loads(row["payload_json"])
        return ProviderStatus(
            provider_id=provider_id,
            disabled=payload["disabled"],
            changed_at=row["occurred_at"],
            changed_by=row["actor_id"],
            reason=payload["reason"],
            control_event_id=row["event_id"],
            ledger_sequence=row["sequence"],
        )

    def set_provider_status(self, provider_id: str, control: ProviderControlRequest) -> ProviderStatus:
        self._append(
            event_type="provider.control_changed",
            actor_id=control.operator_id,
            correlation_id=self._id_factory(),
            entity_id=f"provider:{provider_id}",
            payload={
                "schema_version": "1.0",
                "disabled": control.disabled,
                "reason": control.reason,
            },
        )
        return self.get_provider_status(provider_id)

    def record_replay(
        self,
        *,
        decision_id: str,
        operator_id: str,
        correlation_id: str,
        comparison: dict[str, bool],
    ) -> ReplayResult:
        event = self._append(
            event_type="decision.replayed",
            actor_id=operator_id,
            correlation_id=correlation_id,
            entity_id=decision_id,
            payload={"schema_version": "1.0", **comparison},
        )
        return ReplayResult(
            decision_id=decision_id,
            replay_event_id=event["event_id"],
            ledger_sequence=event["sequence"],
            **comparison,
        )
