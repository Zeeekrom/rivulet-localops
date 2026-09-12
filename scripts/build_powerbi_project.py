from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MART = ROOT / "data" / "mart" / "v1" / "csv"
OUTPUT = ROOT / "analytics" / "powerbi"
PROJECT_NAME = "RivuletAssurance"
REPORT_DIR = OUTPUT / f"{PROJECT_NAME}.Report"
MODEL_DIR = OUTPUT / f"{PROJECT_NAME}.SemanticModel"
DEFINITION_DIR = REPORT_DIR / "definition"
NAMESPACE = uuid.UUID("555dc1d0-e58d-5c84-a47a-5e00ffca0dd2")

PBIP_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json"
PBIR_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json"
REPORT_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.4.0/schema.json"
PAGES_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
VERSION_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json"
VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json"


@dataclass(frozen=True)
class Column:
    name: str
    data_type: str


@dataclass(frozen=True)
class Measure:
    name: str
    expression: str
    format_string: str


@dataclass(frozen=True)
class TableSpec:
    name: str
    csv_name: str
    csv_column_count: int
    columns: tuple[Column, ...]
    measures: tuple[Measure, ...]


TABLES = (
    TableSpec(
        "Source",
        "dim_source.csv",
        8,
        (
            Column("source_key", "string"),
            Column("title", "string"),
            Column("publisher", "string"),
            Column("data_truth_class", "string"),
            Column("record_count", "int64"),
            Column("snapshot_utc", "string"),
            Column("license_name", "string"),
            Column("landing_page", "string"),
        ),
        (
            Measure("Source Count", "COUNTROWS(Source)", "#,0"),
            Measure(
                "Public Source Count",
                'CALCULATE([Source Count], Source[data_truth_class] = "real_public_reference")',
                "#,0",
            ),
            Measure("D1 Asset Rows", 'CALCULATE(MAX(Source[record_count]), Source[source_key] = "D1")', "#,0"),
            Measure("D2 Aggregate Rows", 'CALCULATE(MAX(Source[record_count]), Source[source_key] = "D2")', "#,0"),
            Measure("D6 Synthetic Events", 'CALCULATE(MAX(Source[record_count]), Source[source_key] = "D6")', "#,0"),
            Measure("Source Records", "SUM(Source[record_count])", "#,0"),
        ),
    ),
    TableSpec(
        "QualityCheck",
        "fact_quality_check.csv",
        10,
        (
            Column("quality_check_key", "string"),
            Column("source_key", "string"),
            Column("profiled_at_utc", "string"),
            Column("quality_dimension", "string"),
            Column("status", "string"),
            Column("severity", "string"),
            Column("rows_evaluated", "int64"),
            Column("failed_rows", "int64"),
            Column("failure_rate", "double"),
            Column("detail", "string"),
        ),
        (
            Measure("Quality Check Count", "COUNTROWS(QualityCheck)", "#,0"),
            Measure(
                "Warning Check Count",
                'CALCULATE([Quality Check Count], QualityCheck[status] = "warn")',
                "#,0",
            ),
            Measure(
                "Failed Check Count",
                'COALESCE(CALCULATE([Quality Check Count], QualityCheck[status] = "fail"), 0)',
                "#,0",
            ),
            Measure(
                "Blocking Failure Count",
                'COALESCE(CALCULATE([Quality Check Count], QualityCheck[status] = "fail", QualityCheck[severity] = "critical"), 0)',
                "#,0",
            ),
        ),
    ),
    TableSpec(
        "Decision",
        "fact_decision.csv",
        23,
        (
            Column("decision_key", "string"),
            Column("source_key", "string"),
            Column("date_key", "int64"),
            Column("category_key", "string"),
            Column("gate_status", "string"),
            Column("coordinates_supplied", "boolean"),
            Column("asset_key", "string"),
            Column("data_truth_class", "string"),
            Column("review_state", "string"),
            Column("current_review_action", "string"),
        ),
        (
            Measure("Decision Count", "COUNTROWS(Decision)", "#,0"),
            Measure("Pass Decisions", 'CALCULATE([Decision Count], Decision[gate_status] = "pass")', "#,0"),
            Measure("Pass Rate", "DIVIDE([Pass Decisions], [Decision Count])", "0.0%"),
            Measure("Reject Decisions", 'CALCULATE([Decision Count], Decision[gate_status] = "reject")', "#,0"),
            Measure("Reject Rate", "DIVIDE([Reject Decisions], [Decision Count])", "0.0%"),
            Measure(
                "Escalate Decisions",
                'CALCULATE([Decision Count], Decision[gate_status] = "escalate")',
                "#,0",
            ),
            Measure("Escalate Rate", "DIVIDE([Escalate Decisions], [Decision Count])", "0.0%"),
            Measure(
                "Reviewed Decisions",
                'CALCULATE([Decision Count], Decision[review_state] = "reviewed")',
                "#,0",
            ),
            Measure("Review Rate", "DIVIDE([Reviewed Decisions], [Decision Count])", "0.0%"),
            Measure(
                "Override Decisions",
                'CALCULATE([Decision Count], Decision[current_review_action] = "override")',
                "#,0",
            ),
            Measure("Override Rate", "DIVIDE([Override Decisions], [Reviewed Decisions])", "0.0%"),
            Measure(
                "Eligible Asset Decisions",
                'CALCULATE([Decision Count], Decision[category_key] = "waste_litter", Decision[coordinates_supplied] = TRUE())',
                "#,0",
            ),
            Measure(
                "Asset Matched Decisions",
                'CALCULATE([Decision Count], FILTER(Decision, Decision[category_key] = "waste_litter" && Decision[coordinates_supplied] = TRUE() && LEN(Decision[asset_key]) > 0))',
                "#,0",
            ),
            Measure(
                "Asset Match Rate",
                "DIVIDE([Asset Matched Decisions], [Eligible Asset Decisions])",
                "0.0%",
            ),
        ),
    ),
    TableSpec(
        "GateRule",
        "fact_gate_rule.csv",
        7,
        (
            Column("decision_key", "string"),
            Column("rule_id", "string"),
            Column("rule_outcome", "string"),
            Column("rule_effect", "string"),
            Column("data_truth_class", "string"),
        ),
        (
            Measure("Rule Evaluation Count", "COUNTROWS(GateRule)", "#,0"),
            Measure(
                "Non-pass Rule Count",
                'CALCULATE([Rule Evaluation Count], GateRule[rule_outcome] <> "pass")',
                "#,0",
            ),
        ),
    ),
    TableSpec(
        "Review",
        "fact_review.csv",
        11,
        (
            Column("decision_key", "string"),
            Column("date_key", "int64"),
            Column("review_action", "string"),
            Column("review_lag_minutes", "double"),
            Column("data_truth_class", "string"),
        ),
        (
            Measure("Review Count", "COUNTROWS(Review)", "#,0"),
            Measure("Median Review Lag", "MEDIAN(Review[review_lag_minutes])", '#,0 "min"'),
        ),
    ),
    TableSpec(
        "ManualFallback",
        "fact_manual_fallback.csv",
        9,
        (
            Column("fallback_key", "string"),
            Column("source_key", "string"),
            Column("date_key", "int64"),
            Column("reason", "string"),
            Column("data_truth_class", "string"),
        ),
        (Measure("Manual Fallback Count", "COUNTROWS(ManualFallback)", "#,0"),),
    ),
    TableSpec(
        "Date",
        "dim_date.csv",
        6,
        (
            Column("date_key", "int64"),
            Column("calendar_date", "dateTime"),
            Column("year", "int64"),
            Column("month_name", "string"),
        ),
        (),
    ),
)


def stable_uuid(label: str) -> str:
    return str(uuid.uuid5(NAMESPACE, label))


def json_text(value: Any) -> str:
    # Power BI Desktop's canonical PBIP/PBIR serializer omits a final newline.
    # Keeping the generator aligned prevents every Desktop save from appearing
    # as a repository-wide rewrite.
    return json.dumps(value, indent=2, ensure_ascii=False)


def quote_tmdl(value: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        return value
    return "'" + value.replace("'", "''") + "'"


def m_literal_strings(values: list[str]) -> str:
    return "{" + ", ".join(json.dumps(value) for value in values) + "}"


def build_table_tmdl(spec: TableSpec) -> str:
    csv_path = MART / spec.csv_name
    payload = base64.b64encode(csv_path.read_bytes()).decode("ascii")
    bool_columns = [column.name for column in spec.columns if column.data_type == "boolean"]
    typed_columns = [column for column in spec.columns if column.data_type != "boolean"]
    m_types = {
        "string": "type text",
        "int64": "Int64.Type",
        "double": "type number",
        "dateTime": "type date",
    }
    type_pairs = ", ".join(
        "{" + json.dumps(column.name) + ", " + m_types[column.data_type] + "}" for column in typed_columns
    )
    selected = m_literal_strings([column.name for column in spec.columns])
    source_lines = [
        "let",
        f'    Binary = Binary.FromText("{payload}", BinaryEncoding.Base64),',
        (
            "    Raw = Csv.Document(Binary, [Delimiter=\",\", "
            f"Columns={spec.csv_column_count}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),"
        ),
        "    Headers = Table.PromoteHeaders(Raw, [PromoteAllScalars=true]),",
        f"    Selected = Table.SelectColumns(Headers, {selected}),",
        f'    Typed = Table.TransformColumnTypes(Selected, {{{type_pairs}}}, "en-AU")',
    ]
    if bool_columns:
        conversions = ", ".join(
            "{"
            + json.dumps(column)
            + ', each if _ = "1" then true else if _ = "0" then false else null, type logical}'
            for column in bool_columns
        )
        source_lines[-1] += ","
        source_lines.append(f"    Booleans = Table.TransformColumns(Typed, {{{conversions}}})")
        result_name = "Booleans"
    else:
        result_name = "Typed"
    source_lines.extend(["in", f"    {result_name}"])

    lines = [f"table {quote_tmdl(spec.name)}", f"\tlineageTag: {stable_uuid('table:' + spec.name)}", ""]
    for measure in spec.measures:
        lines.extend(
            [
                f"\tmeasure {quote_tmdl(measure.name)} = {measure.expression}",
                f"\t\tformatString: {measure.format_string}",
                f"\t\tlineageTag: {stable_uuid('measure:' + spec.name + ':' + measure.name)}",
                "",
            ]
        )
    for column in spec.columns:
        lines.extend([f"\tcolumn {quote_tmdl(column.name)}", f"\t\tdataType: {column.data_type}"])
        if column.data_type == "int64":
            lines.append("\t\tformatString: 0")
        elif column.data_type == "dateTime":
            lines.append("\t\tformatString: yyyy-mm-dd")
        lines.extend(
            [
                f"\t\tlineageTag: {stable_uuid('column:' + spec.name + ':' + column.name)}",
                "\t\tsummarizeBy: none",
                f"\t\tsourceColumn: {column.name}",
            ]
        )
        lines.extend(["", "\t\tannotation SummarizationSetBy = Automatic", ""])
    lines.extend(
        [
            f"\tpartition {spec.name}-{stable_uuid('partition:' + spec.name)} = m",
            "\t\tmode: import",
            "\t\tsource =",
        ]
    )
    lines.extend("\t\t\t" + line for line in source_lines)
    lines.extend(["", "\tannotation PBI_ResultType = Table", "", "\tannotation PBI_NavigationStepName = Navigation", ""])
    # TMDL serialization from Desktop leaves one blank line at EOF.
    return "\n".join(lines)


def literal(value: str) -> dict[str, Any]:
    return {"expr": {"Literal": {"Value": value}}}


def color(value: str) -> dict[str, Any]:
    return {"solid": {"color": literal(f"'{value}'")}}


def position(x: float, y: float, width: float, height: float, z: int) -> dict[str, Any]:
    return {"x": x, "y": y, "z": z, "height": height, "width": width, "tabOrder": z}


def container_objects(title: str | None = None, background: str = "#FFFFFF") -> dict[str, Any]:
    objects: dict[str, Any] = {
        "background": [
            {
                "properties": {
                    "show": literal("true"),
                    "color": color(background),
                    "transparency": literal("0D"),
                }
            }
        ],
        "border": [
            {
                "properties": {
                    "show": literal("true"),
                    "color": color("#D7DEE8"),
                    "radius": literal("8D"),
                }
            }
        ],
    }
    if title:
        objects["title"] = [
            {
                "properties": {
                    "show": literal("true"),
                    "text": literal("'" + title.replace("'", "''") + "'"),
                    "alignment": literal("'left'"),
                    "fontSize": literal("11D"),
                    "bold": literal("true"),
                    "fontColor": color("#17324D"),
                }
            }
        ]
    return objects


def textbox(name: str, x: float, y: float, width: float, height: float, z: int, text: str, *, size: int, foreground: str, background: str | None = None, bold: bool = False) -> dict[str, Any]:
    visual: dict[str, Any] = {
        "visualType": "textbox",
        "objects": {
            "general": [
                {
                    "properties": {
                        "paragraphs": [
                            {
                                "textRuns": [
                                    {
                                        "value": text,
                                        "textStyle": {
                                            "fontFamily": "Segoe UI",
                                            "fontSize": f"{size}pt",
                                            "color": foreground,
                                            "fontWeight": "bold" if bold else "normal",
                                        },
                                    }
                                ],
                                "horizontalTextAlignment": "left",
                            }
                        ]
                    }
                }
            ]
        },
        "drillFilterOtherVisuals": True,
    }
    if background:
        visual["visualContainerObjects"] = container_objects(background=background)
    return {"$schema": VISUAL_SCHEMA, "name": name, "position": position(x, y, width, height, z), "visual": visual}


def measure_field(entity: str, measure: str) -> dict[str, Any]:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": measure}}


def column_field(entity: str, column_name: str) -> dict[str, Any]:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": column_name}}


def card(name: str, x: float, y: float, width: float, height: float, z: int, entity: str, measure: str, title: str) -> dict[str, Any]:
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": position(x, y, width, height, z),
        "visual": {
            "visualType": "card",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [
                            {
                                "field": measure_field(entity, measure),
                                "queryRef": f"{entity}.{measure}",
                                "nativeQueryRef": measure,
                            }
                        ]
                    }
                }
            },
            "objects": {
                "labels": [{"properties": {"fontSize": literal("28D"), "color": color("#17324D")}}],
                "categoryLabels": [{"properties": {"show": literal("false")}}],
            },
            "visualContainerObjects": container_objects(title),
            "drillFilterOtherVisuals": True,
        },
    }


def chart(name: str, x: float, y: float, width: float, height: float, z: int, visual_type: str, category_entity: str, category_column: str, measure_entity: str, measure: str, title: str, *, ascending: bool = False) -> dict[str, Any]:
    category = column_field(category_entity, category_column)
    measure_ref = measure_field(measure_entity, measure)
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": position(x, y, width, height, z),
        "visual": {
            "visualType": visual_type,
            "query": {
                "queryState": {
                    "Category": {
                        "projections": [
                            {
                                "field": category,
                                "queryRef": f"{category_entity}.{category_column}",
                                "nativeQueryRef": category_column,
                                "active": True,
                            }
                        ]
                    },
                    "Y": {
                        "projections": [
                            {
                                "field": measure_ref,
                                "queryRef": f"{measure_entity}.{measure}",
                                "nativeQueryRef": measure,
                            }
                        ]
                    },
                },
                "sortDefinition": {
                    "sort": [
                        {
                            "field": category if ascending else measure_ref,
                            "direction": "Ascending" if ascending else "Descending",
                        }
                    ],
                    "isDefaultSort": True,
                },
            },
            "visualContainerObjects": container_objects(title),
            "drillFilterOtherVisuals": True,
        },
    }


def slicer(name: str, x: float, y: float, width: float, height: float, z: int, entity: str, column_name: str, title: str) -> dict[str, Any]:
    field = column_field(entity, column_name)
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": position(x, y, width, height, z),
        "visual": {
            "visualType": "slicer",
            "query": {
                "queryState": {
                    "Values": {
                        "projections": [
                            {
                                "field": field,
                                "queryRef": f"{entity}.{column_name}",
                                "nativeQueryRef": column_name,
                                "active": True,
                            }
                        ]
                    }
                },
                "sortDefinition": {
                    "sort": [{"field": field, "direction": "Ascending"}],
                    "isDefaultSort": True,
                },
            },
            "visualContainerObjects": container_objects(title),
            "drillFilterOtherVisuals": True,
        },
    }


def matrix(name: str, x: float, y: float, width: float, height: float, z: int, fields: list[tuple[str, str]], measure: tuple[str, str], title: str) -> dict[str, Any]:
    projections = [
        {
            "field": column_field(entity, column_name),
            "queryRef": f"{entity}.{column_name}",
            "nativeQueryRef": column_name,
            "active": True,
        }
        for entity, column_name in fields
    ]
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": position(x, y, width, height, z),
        "visual": {
            "visualType": "pivotTable",
            "query": {
                "queryState": {
                    "Rows": {"projections": projections},
                    "Values": {
                        "projections": [
                            {
                                "field": measure_field(measure[0], measure[1]),
                                "queryRef": f"{measure[0]}.{measure[1]}",
                                "nativeQueryRef": measure[1],
                            }
                        ]
                    },
                }
            },
            "visualContainerObjects": container_objects(title),
            "drillFilterOtherVisuals": True,
        },
    }


def page_json(page_name: str, display_name: str) -> dict[str, Any]:
    return {
        "$schema": PAGE_SCHEMA,
        "name": page_name,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280,
    }


def page_one_visuals() -> list[dict[str, Any]]:
    visuals: list[dict[str, Any]] = [
        textbox("title", 32, 14, 1216, 52, 100, "Rivulet LocalOps  |  Data provenance & quality", size=22, foreground="#17324D", bold=True),
        textbox("truth_banner", 32, 68, 1216, 42, 110, "TRUTH BOUNDARY  •  D1/D2 are real public reference data  •  D6 is a fixed-seed synthetic operational fixture", size=12, foreground="#FFFFFF", background="#0E7490", bold=True),
    ]
    cards = [
        ("public_sources", "Source", "Public Source Count", "Public sources"),
        ("d1_assets", "Source", "D1 Asset Rows", "D1 asset rows"),
        ("d2_rows", "Source", "D2 Aggregate Rows", "D2 aggregate rows"),
        ("quality_checks", "QualityCheck", "Quality Check Count", "Quality checks"),
        ("quality_warnings", "QualityCheck", "Warning Check Count", "Warnings"),
    ]
    for index, (name, entity, measure, title) in enumerate(cards):
        visuals.append(card(name, 32 + index * 246, 126, 230, 96, 200 + index, entity, measure, title))
    visuals.extend(
        [
            chart("quality_outcomes", 32, 240, 390, 216, 300, "clusteredBarChart", "QualityCheck", "status", "QualityCheck", "Quality Check Count", "Quality outcomes"),
            matrix("source_register", 438, 240, 810, 216, 310, [("Source", "source_key"), ("Source", "publisher"), ("Source", "data_truth_class"), ("Source", "snapshot_utc")], ("Source", "Source Records"), "Source register — counts have different grains"),
            matrix("quality_findings", 32, 474, 910, 214, 400, [("QualityCheck", "source_key"), ("QualityCheck", "quality_dimension"), ("QualityCheck", "status"), ("QualityCheck", "severity"), ("QualityCheck", "detail")], ("QualityCheck", "Quality Check Count"), "Quality findings and warnings"),
            slicer("truth_filter", 958, 474, 290, 100, 410, "Source", "data_truth_class", "Visible truth-class filter"),
            textbox("page_limit", 958, 590, 290, 98, 420, "D2 is Townsville monthly aggregate context, not Hobart demand. Row, asset and event counts are not additive across sources.", size=11, foreground="#7C2D12", background="#FFF7ED", bold=True),
        ]
    )
    return visuals


def page_two_visuals() -> list[dict[str, Any]]:
    visuals: list[dict[str, Any]] = [
        textbox("title", 32, 14, 1216, 52, 100, "Rivulet LocalOps  |  Gate & decision assurance", size=22, foreground="#17324D", bold=True),
        textbox("truth_banner", 32, 68, 1216, 42, 110, "SYNTHETIC OPERATIONAL FIXTURE  •  Control-path regression evidence only  •  Not council performance or model accuracy", size=12, foreground="#FFFFFF", background="#7C3AED", bold=True),
    ]
    cards = [
        ("decisions", "Decision", "Decision Count", "Decisions"),
        ("pass_rate", "Decision", "Pass Rate", "Gate pass rate"),
        ("review_rate", "Decision", "Review Rate", "Review rate"),
        ("override_rate", "Decision", "Override Rate", "Override / reviewed"),
        ("fallbacks", "ManualFallback", "Manual Fallback Count", "Manual fallbacks"),
        ("median_lag", "Review", "Median Review Lag", "Median review lag"),
    ]
    for index, (name, entity, measure, title) in enumerate(cards):
        visuals.append(card(name, 32 + index * 202, 126, 190, 96, 200 + index, entity, measure, title))
    visuals.extend(
        [
            chart("gate_mix", 32, 240, 390, 216, 300, "columnChart", "Decision", "gate_status", "Decision", "Decision Count", "Gate decision mix"),
            chart("non_pass_rules", 438, 240, 500, 216, 310, "barChart", "GateRule", "rule_id", "GateRule", "Non-pass Rule Count", "Non-pass rule outcomes"),
            slicer("gate_filter", 954, 240, 294, 100, 320, "Decision", "gate_status", "Gate status filter"),
            textbox("page_limit", 954, 356, 294, 100, 330, "All rates and lags on this page were deliberately generated. Use them to verify calculations and controls, never as an SLA or benefit claim.", size=11, foreground="#5B21B6", background="#F5F3FF", bold=True),
            chart("decision_trend", 32, 474, 500, 214, 400, "areaChart", "Date", "calendar_date", "Decision", "Decision Count", "Synthetic decisions over time", ascending=True),
            chart("review_actions", 548, 474, 330, 214, 410, "columnChart", "Review", "review_action", "Review", "Review Count", "Review actions"),
            matrix("decision_trace", 894, 474, 354, 214, 420, [("Decision", "decision_key"), ("Decision", "gate_status"), ("Decision", "review_state"), ("Decision", "current_review_action")], ("Decision", "Decision Count"), "Synthetic decision trace"),
        ]
    )
    return visuals


def build_reference_metrics() -> str:
    build_report = json.loads((ROOT / "data" / "mart" / "v1" / "build_report.json").read_text(encoding="utf-8"))
    quality = list(csv.DictReader((MART / "fact_quality_check.csv").open(encoding="utf-8", newline="")))
    sources = {row["source_key"]: row for row in csv.DictReader((MART / "dim_source.csv").open(encoding="utf-8", newline=""))}
    metrics = build_report["metrics"]
    rows = [
        ("Public Source Count", 2, "count", "real_public_reference", "dim_source"),
        ("D1 Asset Rows", int(sources["D1"]["record_count"]), "count", "real_public_reference", "dim_source"),
        ("D2 Aggregate Rows", int(sources["D2"]["record_count"]), "count", "real_public_reference", "dim_source"),
        ("Quality Check Count", len(quality), "count", "mixed_reference_control", "fact_quality_check"),
        ("Warning Check Count", sum(row["status"] == "warn" for row in quality), "count", "mixed_reference_control", "fact_quality_check"),
        ("Blocking Failure Count", sum(row["status"] == "fail" and row["severity"] == "critical" for row in quality), "count", "mixed_reference_control", "fact_quality_check"),
        ("Decision Count", metrics["decision_count"], "count", "synthetic_operational", "fact_decision"),
        ("Pass Rate", metrics["gate_pass_rate"], "ratio", "synthetic_operational", "fact_decision"),
        ("Review Rate", metrics["review_rate"], "ratio", "synthetic_operational", "fact_decision"),
        ("Override Rate", metrics["override_rate_of_reviewed"], "ratio", "synthetic_operational", "fact_decision/fact_review"),
        ("Manual Fallback Count", build_report["table_rows"]["fact_manual_fallback"], "count", "synthetic_operational", "fact_manual_fallback"),
        ("Median Review Lag", metrics["median_review_lag_minutes"], "minutes", "synthetic_operational", "fact_review"),
        ("Asset Match Rate", metrics["asset_match_rate_of_eligible"], "ratio", "synthetic_operational", "fact_decision"),
    ]
    output = ["measure,expected_value,unit,data_truth_class,reference_table"]
    output.extend(",".join(map(str, row)) for row in rows)
    return "\n".join(output) + "\n"


def build_diagram_layout() -> dict[str, Any]:
    """Return the portable model-diagram layout saved by Power BI Desktop."""
    placements = (
        ("Date", 476.46440930897563, 22.749388404332649, 176),
        ("Decision", 339.91454131928782, 254.72866984752773, 300),
        ("GateRule", 50, 460.23228814446065, 248),
        ("ManualFallback", 765.82041282613534, -29.061827317299048, 224),
        ("QualityCheck", 984.19735146068751, 486.06329853859313, 300),
        ("Review", 183.26080350983364, -50, 248),
        ("Source", 694.51029139467823, 251.71135606056447, 300),
    )
    nodes = [
        {
            "location": {"x": x, "y": y},
            "nodeIndex": table,
            "nodeLineageTag": stable_uuid("table:" + table),
            "size": {"height": height, "width": 234},
            "zIndex": 0,
        }
        for table, x, y, height in placements
    ]
    return {
        "version": "1.1.0",
        "diagrams": [
            {
                "ordinal": 0,
                "scrollPosition": {"x": 0, "y": 0},
                "nodes": nodes,
                "name": "All tables",
                "zoomValue": 100,
                "pinKeyFieldsToTop": False,
                "showExtraHeaderInfo": False,
                "hideKeyFieldsWhenCollapsed": False,
                "tablesLocked": False,
            }
        ],
        "selectedDiagram": "All tables",
        "defaultDiagram": "All tables",
    }


def build_files() -> dict[Path, str]:
    files: dict[Path, str] = {}
    files[OUTPUT / f"{PROJECT_NAME}.pbip"] = json_text(
        {
            "$schema": PBIP_SCHEMA,
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{PROJECT_NAME}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        }
    )
    files[REPORT_DIR / "definition.pbir"] = json_text(
        {
            "$schema": PBIR_SCHEMA,
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{PROJECT_NAME}.SemanticModel"}},
        }
    )
    files[REPORT_DIR / ".platform"] = json_text(
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "Report", "displayName": "Rivulet Assurance"},
            "config": {"version": "2.0", "logicalId": stable_uuid("platform:RivuletAssurance.Report")},
        }
    )
    files[MODEL_DIR / ".platform"] = json_text(
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "SemanticModel", "displayName": "Rivulet Assurance"},
            "config": {"version": "2.0", "logicalId": stable_uuid("platform:RivuletAssurance.SemanticModel")},
        }
    )
    files[DEFINITION_DIR / "version.json"] = json_text({"$schema": VERSION_SCHEMA, "version": "2.0.0"})
    files[DEFINITION_DIR / "report.json"] = json_text(
        {
            "$schema": REPORT_SCHEMA,
            "themeCollection": {
                "baseTheme": {
                    "name": "CY23SU04",
                    "reportVersionAtImport": {"visual": "1.8.82", "report": "2.0.82", "page": "1.3.82"},
                    "type": "SharedResources",
                }
            },
            "resourcePackages": [
                {
                    "name": "SharedResources",
                    "type": "SharedResources",
                    "items": [{"name": "CY23SU04", "path": "BaseThemes/CY23SU04.json", "type": "BaseTheme"}],
                }
            ],
            "settings": {
                "defaultDrillFilterOtherVisuals": True,
                "allowChangeFilterTypes": True,
                "useEnhancedTooltips": True,
            },
        }
    )
    page_names = ("data_provenance", "gate_assurance")
    files[DEFINITION_DIR / "pages" / "pages.json"] = json_text(
        {"$schema": PAGES_SCHEMA, "pageOrder": list(page_names), "activePageName": page_names[1]}
    )
    page_specs = (
        (page_names[0], "Data provenance & quality", page_one_visuals()),
        (page_names[1], "Gate & decision assurance", page_two_visuals()),
    )
    for page_name, display_name, visuals in page_specs:
        page_dir = DEFINITION_DIR / "pages" / page_name
        files[page_dir / "page.json"] = json_text(page_json(page_name, display_name))
        for visual in visuals:
            files[page_dir / "visuals" / visual["name"] / "visual.json"] = json_text(visual)

    files[MODEL_DIR / "definition.pbism"] = json_text({"version": "4.2", "settings": {}})
    files[MODEL_DIR / ".pbi" / "editorSettings.json"] = json_text(
        {
            "version": "1.0",
            "autodetectRelationships": True,
            "parallelQueryLoading": True,
            "typeDetectionEnabled": True,
            "relationshipImportEnabled": True,
            "shouldNotifyUserOfNameConflictResolution": True,
        }
    )
    files[MODEL_DIR / "definition" / "database.tmdl"] = "database\n\tcompatibilityLevel: 1606\n"
    table_names = [spec.name for spec in TABLES]
    model_lines = [
        "model Model",
        "\tculture: en-AU",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-AU",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        "annotation PBI_QueryOrder = " + json.dumps(table_names, separators=(",", ":")),
        "",
        'annotation PBI_ProTooling = ["MCP-PBIModeling","DevMode"]',
        "",
    ]
    model_lines.extend(f"ref table {quote_tmdl(name)}" for name in table_names)
    model_lines.extend(["", "ref cultureInfo en-AU", ""])
    files[MODEL_DIR / "definition" / "model.tmdl"] = "\n".join(model_lines)
    for spec in TABLES:
        files[MODEL_DIR / "definition" / "tables" / f"{spec.name}.tmdl"] = build_table_tmdl(spec)
    files[MODEL_DIR / "definition" / "cultures" / "en-AU.tmdl"] = (
        "cultureInfo en-AU\n\n"
        "\tlinguisticMetadata =\n"
        "\t\t\t{\n"
        '\t\t\t  "Version": "1.0.0",\n'
        '\t\t\t  "Language": "en-US"\n'
        "\t\t\t}\n"
        "\t\tcontentType: json\n"
    )
    relationships = [
        ("quality-source", "QualityCheck.source_key", "Source.source_key", True),
        ("decision-source", "Decision.source_key", "Source.source_key", True),
        ("fallback-source", "ManualFallback.source_key", "Source.source_key", True),
        ("gate-decision", "GateRule.decision_key", "Decision.decision_key", True),
        # Keeping this lineage edge inactive avoids two active paths between Review
        # and Date (directly, and via Decision). Current visuals do not depend on it.
        ("review-decision", "Review.decision_key", "Decision.decision_key", False),
        ("decision-date", "Decision.date_key", "Date.date_key", True),
        ("review-date", "Review.date_key", "Date.date_key", True),
        ("fallback-date", "ManualFallback.date_key", "Date.date_key", True),
    ]
    relationship_lines: list[str] = []
    for name, source, target, active in relationships:
        relationship_lines.append(f"relationship {stable_uuid('relationship:' + name)}")
        if not active:
            relationship_lines.append("\tisActive: false")
        relationship_lines.extend([f"\tfromColumn: {source}", f"\ttoColumn: {target}", ""])
    files[MODEL_DIR / "definition" / "relationships.tmdl"] = "\n".join(relationship_lines)
    files[MODEL_DIR / "diagramLayout.json"] = json_text(build_diagram_layout())
    files[OUTPUT / "reference_metrics.csv"] = build_reference_metrics()
    return files


def write_or_check(files: dict[Path, str], check: bool) -> int:
    failures: list[str] = []
    for path, content in files.items():
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                failures.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if check:
        if failures:
            print(json.dumps({"status": "stale", "files": failures}, indent=2))
            return 1
        print(json.dumps({"status": "pass", "files": len(files)}, indent=2))
        return 0
    manifest = {
        "project": str((OUTPUT / f"{PROJECT_NAME}.pbip").relative_to(ROOT)),
        "files": len(files),
        "pages": 2,
        "visuals": len(page_one_visuals()) + len(page_two_visuals()),
        "source_csv_sha256": {
            spec.csv_name: hashlib.sha256((MART / spec.csv_name).read_bytes()).hexdigest() for spec in TABLES
        },
    }
    manifest_path = OUTPUT / "build_manifest.json"
    manifest_path.write_text(json_text(manifest), encoding="utf-8", newline="\n")
    print(json.dumps(manifest, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the deterministic Rivulet Power BI PBIP/PBIR/TMDL project.")
    parser.add_argument("--check", action="store_true", help="Fail if committed generated files differ from a fresh build.")
    args = parser.parse_args()
    return write_or_check(build_files(), args.check)


if __name__ == "__main__":
    raise SystemExit(main())
