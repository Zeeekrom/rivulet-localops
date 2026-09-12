import re
from collections.abc import Callable
from uuid import uuid4

from rivulet_localops.assets import AssetRepository
from rivulet_localops.models import (
    CategoryResult,
    DiagnoseRequest,
    DiagnoseResponse,
    EngineInfo,
    PriorityResult,
    ProviderReference,
)
from rivulet_localops.taxonomy import CATEGORIES, GENERAL_CATEGORY, Category


EMERGENCY_TERMS = (
    "immediate danger",
    "person trapped",
    "fallen power line",
    "sewage inside",
    "flooding inside",
    "on fire",
)
URGENT_TERMS = (
    "blocked road",
    "overflowing bin",
    "bin is overflowing",
    "fallen tree",
    "dog attack",
    "large pothole",
    "trip hazard",
    "sharp",
    "unsafe",
)
LOCATION_HINTS = (" street", " st ", " road", " rd ", " avenue", " park", " near ", " outside ", " beside ")


def _normalise(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def _category_scores(text: str) -> list[tuple[int, Category, list[str]]]:
    scores: list[tuple[int, Category, list[str]]] = []
    for category in CATEGORIES:
        matched_phrases = [term for term in category.phrases if term in text]
        matched_keywords = [term for term in category.keywords if f" {term} " in text]
        matched = list(dict.fromkeys(matched_phrases + matched_keywords))
        score = 3 * len(matched_phrases) + len(matched_keywords)
        scores.append((score, category, matched))
    return sorted(scores, key=lambda item: item[0], reverse=True)


def _classify(text: str) -> tuple[CategoryResult, float, bool]:
    scores = _category_scores(text)
    top_score, category, matched = scores[0]
    second_score = scores[1][0]
    if top_score == 0:
        return CategoryResult(code=GENERAL_CATEGORY.code, label=GENERAL_CATEGORY.label, confidence=0.3, matched_terms=[]), 0.3, True

    confidence = min(0.95, 0.5 + 0.08 * top_score + 0.08 * (top_score - second_score))
    ambiguous = second_score == top_score or confidence < 0.65
    return (
        CategoryResult(
            code=category.code,
            label=category.label,
            confidence=round(confidence, 2),
            matched_terms=matched,
        ),
        confidence,
        ambiguous,
    )


def _priority(text: str, category_code: str) -> tuple[PriorityResult, bool]:
    emergency = next((term for term in EMERGENCY_TERMS if term in text), None)
    if emergency:
        return PriorityResult(code="P1", label="Emergency referral", target_hours=1, policy_rule=f"Emergency safety phrase detected: '{emergency}'"), True

    urgent = next((term for term in URGENT_TERMS if term in text), None)
    if urgent:
        return PriorityResult(code="P2", label="Urgent", target_hours=8, policy_rule=f"Urgent hazard phrase detected: '{urgent}'"), False

    if category_code == "general_enquiry":
        return PriorityResult(code="P4", label="Routine enquiry", target_hours=120, policy_rule="No operational fault or hazard was confidently identified"), False

    return PriorityResult(code="P3", label="Standard", target_hours=72, policy_rule="Operational issue identified with no explicit urgent hazard phrase"), False


class RulesTriageProvider:
    reference = ProviderReference(provider="deterministic-rules", version="0.1.0", mode="baseline")

    def __init__(
        self,
        assets: AssetRepository,
        asset_match_radius_metres: float = 500,
        id_factory: Callable[[], str] | None = None,
    ):
        self.assets = assets
        self.asset_match_radius_metres = asset_match_radius_metres
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def diagnose(self, request: DiagnoseRequest) -> DiagnoseResponse:
        text = _normalise(request.text)
        category, confidence, ambiguous = _classify(text)
        priority, emergency = _priority(text, category.code)

        asset_match = None
        if category.code == "waste_litter" and request.coordinates is not None:
            asset_match = self.assets.nearest_litter_bin(
                request.coordinates,
                max_distance_metres=self.asset_match_radius_metres,
            )

        missing: list[str] = []
        if request.coordinates is None and not any(hint in text for hint in LOCATION_HINTS):
            missing.append("Exact location or nearby landmark")
        if ambiguous:
            missing.append("A clearer description of the affected council service")
        if emergency:
            missing.append("Confirmation that emergency services have been contacted if anyone is at immediate risk")

        explanation = []
        if category.matched_terms:
            explanation.append(f"Category evidence: {', '.join(category.matched_terms)}")
        else:
            explanation.append("No category term passed the baseline matching threshold")
        explanation.append(f"Priority evidence: {priority.policy_rule}")
        if request.coordinates and category.code == "waste_litter":
            if asset_match:
                explanation.append(f"Nearest public litter-bin asset is {asset_match.distance_metres:.1f} metres from the supplied point")
            else:
                explanation.append(
                    "No public litter-bin asset was found within "
                    f"{self.asset_match_radius_metres:g} metres of the supplied point"
                )

        review_required = emergency or ambiguous or (category.code == "waste_litter" and request.coordinates is not None and asset_match is None)
        return DiagnoseResponse(
            diagnosis_id=self._id_factory(),
            category=category,
            priority=priority,
            asset_match=asset_match,
            explanation=explanation,
            missing_information=missing,
            human_review_required=review_required,
            engine=EngineInfo(**self.reference.model_dump()),
            disclaimer="Decision support only. A council officer must confirm emergency, enforcement and ambiguous cases.",
        )
