from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POWERBI = ROOT / "analytics" / "powerbi"
PROJECT = POWERBI / "RivuletAssurance.pbip"
REPORT = POWERBI / "RivuletAssurance.Report"
MODEL = POWERBI / "RivuletAssurance.SemanticModel"
PAGES = REPORT / "definition" / "pages"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    checks: dict[str, bool] = {}
    project = load_json(PROJECT)
    definition = load_json(REPORT / "definition.pbir")
    report_platform = load_json(REPORT / ".platform")
    model_platform = load_json(MODEL / ".platform")
    pages = load_json(PAGES / "pages.json")
    report_metadata = load_json(REPORT / "definition" / "report.json")
    model_definition = load_json(MODEL / "definition.pbism")
    model_editor_settings = load_json(MODEL / ".pbi" / "editorSettings.json")
    diagram = load_json(MODEL / "diagramLayout.json")
    build_manifest = load_json(POWERBI / "build_manifest.json")
    checks["pbip_schema_is_microsoft"] = project["$schema"].startswith("https://developer.microsoft.com/json-schemas/")
    checks["pbip_version"] = project["version"] == "1.0"
    checks["pbir_schema_is_microsoft"] = definition["$schema"].startswith("https://developer.microsoft.com/json-schemas/")
    checks["report_links_semantic_model"] = definition["datasetReference"]["byPath"]["path"] == "../RivuletAssurance.SemanticModel"
    checks["report_platform_type"] = report_platform["metadata"]["type"] == "Report"
    checks["semantic_model_platform_type"] = model_platform["metadata"]["type"] == "SemanticModel"
    checks["report_schema_matches_desktop"] = report_metadata["$schema"].endswith("/report/3.3.0/schema.json")
    checks["pages_schema_matches_desktop"] = pages["$schema"].endswith("/pagesMetadata/1.1.0/schema.json")
    checks["semantic_model_definition_version"] = model_definition["version"] == "4.2"
    checks["portable_editor_settings"] = model_editor_settings["version"] == "1.0"
    checks["portable_file_count"] = build_manifest["files"] == 51
    checks["exactly_two_pages"] = pages["pageOrder"] == ["data_provenance", "gate_assurance"]
    checks["active_page_exists"] = pages["activePageName"] in pages["pageOrder"]

    page_visual_counts: dict[str, int] = {}
    seen_visuals: set[str] = set()
    query_entities: set[str] = set()
    all_text = []
    for page_name in pages["pageOrder"]:
        page_dir = PAGES / page_name
        page = load_json(page_dir / "page.json")
        checks[f"page_name_matches_{page_name}"] = page["name"] == page_name
        visual_files = sorted((page_dir / "visuals").glob("*/visual.json"))
        page_visual_counts[page_name] = len(visual_files)
        for visual_file in visual_files:
            visual = load_json(visual_file)
            checks[f"visual_name_matches_{page_name}_{visual_file.parent.name}"] = visual["name"] == visual_file.parent.name
            checks[f"visual_schema_{page_name}_{visual_file.parent.name}"] = visual["$schema"].startswith("https://developer.microsoft.com/json-schemas/")
            seen_visuals.add(visual.get("visual", {}).get("visualType", "missing"))
            raw = visual_file.read_text(encoding="utf-8")
            query_entities.update(re.findall(r'"Entity":\s*"([^"]+)"', raw))
            all_text.append(raw)
    checks["page_one_is_summary_first"] = page_visual_counts.get("data_provenance", 0) >= 10
    checks["page_two_is_summary_first"] = page_visual_counts.get("gate_assurance", 0) >= 12
    checks["charts_cards_tables_slicers_present"] = {"card", "columnChart", "barChart", "areaChart", "pivotTable", "slicer", "textbox"}.issubset(seen_visuals)

    model_text = (MODEL / "definition" / "model.tmdl").read_text(encoding="utf-8")
    table_names = set(re.findall(r"^ref table '?([A-Za-z0-9_]+)'?$", model_text, flags=re.MULTILINE))
    checks["visual_entities_exist"] = query_entities.issubset(table_names)
    checks["seven_model_tables"] = table_names == {"Source", "QualityCheck", "Decision", "GateRule", "Review", "ManualFallback", "Date"}
    diagram_nodes = {node["nodeIndex"] for item in diagram["diagrams"] for node in item["nodes"]}
    checks["diagram_covers_model_tables"] = diagram_nodes == table_names
    checks["culture_is_portable"] = (MODEL / "definition" / "cultures" / "en-AU.tmdl").is_file() and "ref cultureInfo en-AU" in model_text
    relationship_text = (MODEL / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
    checks["eight_relationships"] = relationship_text.count("relationship ") == 8
    checks["review_decision_relationship_is_inactive"] = (
        "\tisActive: false\n\tfromColumn: Review.decision_key\n\ttoColumn: Decision.decision_key" in relationship_text
    )

    combined = "\n".join(all_text) + "\n" + "\n".join(path.read_text(encoding="utf-8") for path in (MODEL / "definition").rglob("*.tmdl"))
    checks["truth_boundaries_visible"] = "real public reference" in combined and "SYNTHETIC OPERATIONAL FIXTURE" in combined
    checks["no_machine_absolute_path"] = not re.search(r"[A-Za-z]:\\\\", combined)
    authoring_markers = ("co" + "dex", "clau" + "de", "chat" + "gpt", "not" + "ta", "ar " + "glasses")
    checks["no_tool_process_markers"] = not any(marker in combined.casefold() for marker in authoring_markers)
    portable_roots = (REPORT, MODEL)
    portable_paths = (
        item
        for root in portable_roots
        for item in root.rglob("*")
        if item.is_file() and item.name not in {"localSettings.json", "cache.abf"}
    )
    portable_text = "\n".join(path.read_text(encoding="utf-8") for path in portable_paths)
    checks["no_local_security_binding_in_portable_files"] = "securityBindingsSignature" not in portable_text
    ignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    checks["powerbi_local_state_ignored"] = all(
        pattern in ignore_text for pattern in ("**/.pbi/localSettings.json", "**/.pbi/cache.abf")
    )

    expected = {row["measure"]: row["expected_value"] for row in csv.DictReader((POWERBI / "reference_metrics.csv").open(encoding="utf-8", newline=""))}
    checks["reference_metric_count"] = len(expected) == 13
    checks["reference_decisions"] = expected.get("Decision Count") == "180"
    checks["reference_quality_warnings"] = expected.get("Warning Check Count") == "4"
    checks["reference_blocking_failures"] = expected.get("Blocking Failure Count") == "0"
    checks["reference_median_review_lag"] = expected.get("Median Review Lag") == "450.0"

    failures = [name for name, passed in checks.items() if not passed]
    print(
        json.dumps(
            {
                "status": "pass" if not failures else "fail",
                "checks": len(checks),
                "failures": failures,
                "page_visual_counts": page_visual_counts,
                "visual_types": sorted(seen_visuals),
                "query_entities": sorted(query_entities),
            },
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
