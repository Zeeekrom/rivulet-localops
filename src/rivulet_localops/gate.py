from datetime import UTC, datetime
from uuid import uuid4

from .models import (
    DecisionSubmissionRequest,
    DiagnoseResponse,
    GateDecision,
    GateRuleResult,
    PolicyReference,
)
from .policy import PolicyPack


class DeterministicPolicyGate:
    """Evaluate a proposed draft action without writing to an external system."""

    def __init__(self, policy: PolicyPack):
        self.policy = policy

    def evaluate(self, submission: DecisionSubmissionRequest, diagnosis: DiagnoseResponse) -> GateDecision:
        category = diagnosis.category.code
        rules: list[GateRuleResult] = []
        missing_information: list[str] = []
        rejection_reasons: list[str] = []
        escalation_reasons: list[str] = []

        in_scope = category in self.policy.scope_categories
        rules.append(GateRuleResult(
            rule_id="POL-SCOPE-001",
            outcome="pass" if in_scope else "fail",
            effect="allow" if in_scope else "escalate",
            message=(
                f"Category '{category}' is within the demonstration policy scope."
                if in_scope
                else f"Category '{category}' is outside policy scope and requires human routing."
            ),
        ))
        if not in_scope:
            escalation_reasons.append(f"Category '{category}' is outside the approved demonstration scope")

        action_allowed = submission.proposed_action in self.policy.permitted_actions
        rules.append(GateRuleResult(
            rule_id="POL-ACTION-001",
            outcome="pass" if action_allowed else "fail",
            effect="allow" if action_allowed else "reject",
            message=(
                f"Action '{submission.proposed_action}' is permitted as a draft-only action."
                if action_allowed
                else f"Action '{submission.proposed_action}' is not permitted by this policy version."
            ),
        ))
        if not action_allowed:
            rejection_reasons.append(f"Proposed action '{submission.proposed_action}' is not permitted")

        needs_coordinates = category in self.policy.evidence.require_coordinates_for
        has_coordinates = submission.request.coordinates is not None
        if needs_coordinates:
            rules.append(GateRuleResult(
                rule_id="POL-LOCATION-001",
                outcome="pass" if has_coordinates else "fail",
                effect="allow" if has_coordinates else "reject",
                message=(
                    "Required latitude and longitude were supplied."
                    if has_coordinates
                    else "Latitude and longitude are required for a waste/litter draft action."
                ),
            ))
            if not has_coordinates:
                missing_information.append("coordinates.latitude and coordinates.longitude")
                rejection_reasons.append("Required location coordinates are missing")
        else:
            rules.append(GateRuleResult(
                rule_id="POL-LOCATION-001",
                outcome="not_applicable",
                effect="allow",
                message=f"The policy has no coordinate rule for category '{category}'.",
            ))

        needs_asset = category in self.policy.evidence.require_asset_match_for
        if needs_asset and has_coordinates:
            asset_matched = diagnosis.asset_match is not None
            rules.append(GateRuleResult(
                rule_id="POL-ASSET-001",
                outcome="pass" if asset_matched else "fail",
                effect="allow" if asset_matched else "escalate",
                message=(
                    "The supplied point matched a public litter-bin asset."
                    if asset_matched
                    else (
                        "No public litter-bin asset was found within "
                        f"{self.policy.evidence.max_asset_distance_metres:g} metres; human verification is required."
                    )
                ),
            ))
            if not asset_matched:
                escalation_reasons.append("No eligible public litter-bin asset matched the supplied coordinates")
        else:
            rules.append(GateRuleResult(
                rule_id="POL-ASSET-001",
                outcome="not_applicable",
                effect="allow",
                message=(
                    "Asset matching cannot be evaluated until coordinates are supplied."
                    if needs_asset
                    else f"The policy has no asset-match rule for category '{category}'."
                ),
            ))

        priority_requires_escalation = diagnosis.priority.code in self.policy.thresholds.escalate_priorities
        rules.append(GateRuleResult(
            rule_id="POL-SAFETY-001",
            outcome="fail" if priority_requires_escalation else "pass",
            effect="escalate" if priority_requires_escalation else "allow",
            message=(
                f"Priority {diagnosis.priority.code} must be escalated to a human."
                if priority_requires_escalation
                else f"Priority {diagnosis.priority.code} does not trigger the emergency escalation rule."
            ),
        ))
        if priority_requires_escalation:
            escalation_reasons.append(f"Priority {diagnosis.priority.code} requires human escalation")

        confidence_passed = diagnosis.category.confidence >= self.policy.thresholds.minimum_category_confidence
        rules.append(GateRuleResult(
            rule_id="POL-CONFIDENCE-001",
            outcome="pass" if confidence_passed else "fail",
            effect="allow" if confidence_passed else "escalate",
            message=(
                f"Category confidence {diagnosis.category.confidence:.2f} meets the "
                f"{self.policy.thresholds.minimum_category_confidence:.2f} threshold."
                if confidence_passed
                else (
                    f"Category confidence {diagnosis.category.confidence:.2f} is below the "
                    f"{self.policy.thresholds.minimum_category_confidence:.2f} threshold."
                )
            ),
        ))
        if not confidence_passed:
            escalation_reasons.append("Category confidence is below the policy threshold")

        review_needed = diagnosis.human_review_required
        rules.append(GateRuleResult(
            rule_id="POL-REVIEW-001",
            outcome="fail" if review_needed else "pass",
            effect="escalate" if review_needed else "allow",
            message=(
                "The diagnosis contains a human-review flag."
                if review_needed
                else "The diagnosis contains no human-review flag."
            ),
        ))
        if review_needed:
            escalation_reasons.append("The diagnosis requires human review")

        if escalation_reasons:
            status = "escalate"
        elif rejection_reasons:
            status = "reject"
        else:
            status = "pass"

        return GateDecision(
            gate_event_id=str(uuid4()),
            evaluated_at=datetime.now(UTC),
            status=status,
            can_execute=status == "pass",
            proposed_action=submission.proposed_action,
            policy=PolicyReference(
                policy_id=self.policy.policy_id,
                version=self.policy.version,
                title=self.policy.title,
                is_synthetic=self.policy.is_synthetic,
                content_hash=self.policy.content_hash,
            ),
            missing_information=missing_information,
            rejection_reasons=rejection_reasons,
            escalation_reasons=escalation_reasons,
            rule_results=rules,
            diagnosis=diagnosis,
        )
