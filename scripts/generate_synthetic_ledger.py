"""Generate a deterministic, explicitly synthetic operational ledger for analytics."""

import json
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rivulet_localops.assets import AssetRepository  # noqa: E402
from rivulet_localops.data_contracts import (  # noqa: E402
    SourceField,
    SourceManifest,
    sha256_file,
    write_source_manifest,
)
from rivulet_localops.gate import DeterministicPolicyGate  # noqa: E402
from rivulet_localops.ledger import SQLiteEventLedger  # noqa: E402
from rivulet_localops.models import (  # noqa: E402
    Coordinates,
    DecisionSubmissionRequest,
    DiagnoseRequest,
    ProviderControlRequest,
    ReviewRequest,
)
from rivulet_localops.policy import load_policy_pack  # noqa: E402
from rivulet_localops.providers import RulesTriageProvider  # noqa: E402


GENERATOR_VERSION = "1.0.0"
SEED_LABEL = "rivulet-synthetic-ledger-v1"
GENERATED_AT = datetime(2026, 9, 9, tzinfo=UTC)
OUTPUT_DIR = PROJECT_ROOT / "data" / "generated" / "ledger_v1"
SQLITE_PATH = OUTPUT_DIR / "rivulet_synthetic.sqlite3"
JSONL_PATH = OUTPUT_DIR / "ledger_events.jsonl"
MANIFEST_PATH = PROJECT_ROOT / "data" / "source_manifests" / "D6_synthetic_ledger.json"


class DeterministicIds:
    def __init__(self, seed_label: str):
        self.seed_label = seed_label
        self.counter = 0

    def __call__(self) -> str:
        self.counter += 1
        return str(uuid5(NAMESPACE_URL, f"{self.seed_label}:{self.counter:05d}"))


class MutableClock:
    def __init__(self, value: datetime):
        self.value = value

    def set(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def _asset_points() -> list[Coordinates]:
    payload = json.loads((PROJECT_ROOT / "data" / "hobart_litter_bins.geojson").read_text(encoding="utf-8"))
    points: list[Coordinates] = []
    for feature in payload["features"]:
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        points.append(Coordinates(latitude=latitude, longitude=longitude))
    return points


def _scenario(index: int, point: Coordinates) -> tuple[DiagnoseRequest, str]:
    selector = index % 10
    if selector == 0:
        return DiagnoseRequest(text="Synthetic report: overflowing bin beside the public asset.", coordinates=point), "create_draft_work_order"
    if selector == 1:
        return DiagnoseRequest(text="Synthetic report: dumped rubbish beside the litter bin.", coordinates=point), "create_draft_work_order"
    if selector == 2:
        return DiagnoseRequest(text="Synthetic report: a missed collection requires follow-up."), "create_draft_work_order"
    if selector == 3:
        return DiagnoseRequest(text="Synthetic report: please advise about a council service."), "create_draft_work_order"
    if selector == 4:
        return DiagnoseRequest(
            text="Synthetic report: illegal dumping at a remote test point.",
            coordinates=Coordinates(latitude=-42.0, longitude=146.0),
        ), "create_draft_work_order"
    if selector == 5:
        return DiagnoseRequest(text="Synthetic report: large pothole on a test road.", coordinates=point), "create_draft_work_order"
    if selector == 6:
        return DiagnoseRequest(text="Synthetic report: rubbish is on fire beside the bin.", coordinates=point), "create_draft_work_order"
    if selector == 7:
        return DiagnoseRequest(text="Synthetic report: litter and garbage beside the public bin.", coordinates=point), "create_draft_work_order"
    if selector == 8:
        return DiagnoseRequest(text="Synthetic report: recycling waste left beside the bin.", coordinates=point), "create_draft_work_order"
    return DiagnoseRequest(text="Synthetic report: overflowing bin beside the public asset.", coordinates=point), "close_live_case"


def _review_for(index: int, status: str) -> ReviewRequest | None:
    if index % 3 == 2:
        return None
    reviewer = f"reviewer:{(index % 4) + 1}"
    if status == "pass":
        if index % 8 == 0:
            return ReviewRequest(
                reviewer_id=reviewer,
                action="override",
                reason="Synthetic independent review adjusted the priority for demonstration.",
                corrected_priority="P2",
            )
        return ReviewRequest(
            reviewer_id=reviewer,
            action="accept",
            reason="Synthetic independent review accepted the evidence and Gate outcome.",
        )
    if index % 4 == 1:
        return ReviewRequest(
            reviewer_id=reviewer,
            action="override",
            reason="Synthetic independent review supplied a corrected category for demonstration.",
            corrected_category="waste_litter",
        )
    return ReviewRequest(
        reviewer_id=reviewer,
        action="escalate",
        reason="Synthetic independent review retained escalation for human handling.",
    )


def _write_jsonl(ledger: SQLiteEventLedger) -> int:
    with closing(ledger._connect()) as connection:  # noqa: SLF001 - export the persisted event contract
        rows = connection.execute("SELECT * FROM ledger_events ORDER BY sequence").fetchall()
    with JSONL_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    return len(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for generated_path in (SQLITE_PATH, Path(f"{SQLITE_PATH}-wal"), Path(f"{SQLITE_PATH}-shm"), JSONL_PATH):
        if generated_path.exists():
            generated_path.unlink()

    ids = DeterministicIds(SEED_LABEL)
    clock = MutableClock(datetime(2025, 9, 1, 9, tzinfo=UTC))
    policy = load_policy_pack(PROJECT_ROOT / "data" / "policies" / "waste_litter_demo_v0.1.0.json")
    assets = AssetRepository(PROJECT_ROOT / "data" / "hobart_litter_bins.geojson")
    provider = RulesTriageProvider(assets, policy.evidence.max_asset_distance_metres, id_factory=ids)
    gate = DeterministicPolicyGate(policy, id_factory=ids, clock=clock)
    ledger = SQLiteEventLedger(SQLITE_PATH, id_factory=ids, clock=clock)
    points = _asset_points()

    decision_count = 0
    review_count = 0
    manual_fallback_count = 0
    for month_index in range(12):
        year = 2025 + (8 + month_index) // 12
        month = (8 + month_index) % 12 + 1
        for within_month in range(15):
            index = month_index * 15 + within_month
            event_time = datetime(year, month, within_month + 1, 9, tzinfo=UTC)
            clock.set(event_time)
            request, proposed_action = _scenario(index, points[(index * 17) % len(points)])
            submission = DecisionSubmissionRequest(
                request=request,
                proposed_action=proposed_action,
                accountable_owner_id=f"owner:{(index % 5) + 1}",
                correlation_id=f"synthetic-{index + 1:04d}",
            )
            diagnosis = provider.diagnose(request)
            gate_decision = gate.evaluate(submission, diagnosis)
            record = ledger.record_decision(submission, gate_decision)
            decision_count += 1

            review = _review_for(index, gate_decision.status)
            if review is not None:
                clock.set(event_time + timedelta(hours=4 + (index % 9)))
                ledger.record_review(record.decision_id, review)
                review_count += 1

        if month_index in {2, 5, 8, 11}:
            clock.set(datetime(year, month, 20, 9, tzinfo=UTC))
            ledger.set_provider_status(
                "deterministic-rules",
                ProviderControlRequest(
                    disabled=True,
                    operator_id="operator:demo",
                    reason="Synthetic resilience exercise: provider disabled for manual fallback testing.",
                ),
            )
            for fallback_index in range(2):
                clock.set(datetime(year, month, 20, 10 + fallback_index, tzinfo=UTC))
                submission = DecisionSubmissionRequest(
                    request=DiagnoseRequest(text="Synthetic request received during the provider outage exercise."),
                    accountable_owner_id="owner:manual",
                    correlation_id=f"synthetic-fallback-{month_index:02d}-{fallback_index}",
                )
                ledger.record_manual_fallback(submission, "deterministic-rules")
                manual_fallback_count += 1
            clock.set(datetime(year, month, 20, 13, tzinfo=UTC))
            ledger.set_provider_status(
                "deterministic-rules",
                ProviderControlRequest(
                    disabled=False,
                    operator_id="operator:demo",
                    reason="Synthetic resilience exercise complete; deterministic provider restored.",
                ),
            )

    integrity = ledger.verify_integrity()
    if not integrity.ok:
        raise RuntimeError(integrity.message)
    event_count = _write_jsonl(ledger)
    manifest = SourceManifest(
        source_id="D6",
        title="Rivulet fixed-seed synthetic operational ledger",
        publisher="Rivulet LocalOps portfolio project",
        landing_page="https://github.com/Zeeekrom/rivulet-localops/tree/main/data/generated/ledger_v1",
        download_url="https://github.com/Zeeekrom/rivulet-localops/raw/main/data/generated/ledger_v1/ledger_events.jsonl",
        license_name="MIT (project-generated synthetic data)",
        license_url="https://opensource.org/license/mit",
        retrieved_at_utc=GENERATED_AT,
        source_last_modified_utc=GENERATED_AT,
        raw_relative_path="data/generated/ledger_v1/ledger_events.jsonl",
        content_sha256=sha256_file(JSONL_PATH),
        record_count=event_count,
        grain="One append-only synthetic ledger event per JSONL row, ordered by ledger sequence.",
        data_truth_class="synthetic_operational",
        schema_version="rivulet-ledger-event-v1",
        encoding="UTF-8",
        fields=[
            SourceField(name="sequence", data_type="integer", nullable=False, description="Global event order."),
            SourceField(name="event_id", data_type="uuid", nullable=False, description="Deterministic event identifier."),
            SourceField(name="event_type", data_type="text", nullable=False, description="Ledger event type."),
            SourceField(name="occurred_at", data_type="datetime", nullable=False, description="Synthetic UTC event time."),
            SourceField(name="actor_id", data_type="text", nullable=False, description="Synthetic actor identifier."),
            SourceField(name="correlation_id", data_type="text", nullable=False, description="Synthetic request correlation identifier."),
            SourceField(name="entity_id", data_type="text", nullable=False, description="Decision or provider entity identifier."),
            SourceField(name="payload", data_type="json", nullable=False, description="Versioned event payload."),
            SourceField(name="previous_event_hash", data_type="sha256", nullable=True, description="Previous hash-chain link."),
            SourceField(name="event_hash", data_type="sha256", nullable=False, description="Current event hash."),
        ],
        limitations=[
            "Every request, person identifier, timestamp and operational outcome is synthetic and fixed-seed.",
            "The dataset demonstrates data modelling, controls and reconciliation; it is not evidence of council volume, SLA performance, workforce productivity or model accuracy.",
            "The generator intentionally creates pass, reject, escalate, override and manual-fallback paths for coverage rather than natural prevalence.",
        ],
    )
    write_source_manifest(MANIFEST_PATH, manifest)
    print(json.dumps({
        "generator_version": GENERATOR_VERSION,
        "seed_label": SEED_LABEL,
        "decision_count": decision_count,
        "review_count": review_count,
        "manual_fallback_count": manual_fallback_count,
        "event_count": event_count,
        "integrity_ok": integrity.ok,
        "head_hash": integrity.head_hash,
        "jsonl_sha256": manifest.content_sha256,
    }, indent=2))


if __name__ == "__main__":
    main()
