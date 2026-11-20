#!/usr/bin/env python3
"""Strict field-level guard for llms-models.txt and its JSON twin."""

from __future__ import annotations

import json
import math
import os
import re
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JSON_PATH = os.path.join(ROOT_DIR, "llms-models.json")
TXT_PATH = os.path.join(ROOT_DIR, "llms-models.txt")


@dataclass
class Issue:
    file: str
    line: int
    field: str
    message: str

    def report(self) -> None:
        rel = os.path.relpath(self.file, ROOT_DIR).replace(os.sep, "/")
        print(f"{rel}:{self.line}: {self.field}: {self.message}")
        print(f"::error file={rel},line={self.line},title=Models source guard::{self.field}: {self.message}")


def lines(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().splitlines()


def parse_json_field(raw: str) -> Any:
    return json.loads(raw)


def display_value(value: Any) -> str:
    return str(value)


def parse_txt_models(path: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    source = lines(path)
    table: dict[str, dict[str, Any]] = {}
    details: dict[str, dict[str, Any]] = {}
    duplicate_lines: dict[str, int] = {}

    table_re = re.compile(
        r"^\|\s+\*\*(MODEL_[0-9.]+)\*\*\s+\|\s*(.*?)\s+\|\s+\*\*(.*?)\*\*\s+\|\s*(.*?)\s+"
        r"\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|$"
    )
    detail_re = re.compile(r"^#### \[(MODEL_[0-9.]+)\] (.+)$")
    field_res = {
        "formula_ref": re.compile(r"^- \*\*Reference Formula:\*\* (.+)$"),
        "status_value": re.compile(r"^- \*\*Evaluated Status:\*\* `([^`]+)` \(Primary Value: (.+)\)$"),
        "inputs": re.compile(r"^- \*\*Inputs Evaluated:\*\* `(.+?)`$"),
        "rate_disparities": re.compile(r"^- \*\*Policy Disparities:\*\* `(.+?)`$"),
        "metrics": re.compile(r"^- \*\*Secondary Metrics:\*\* `(.+?)`$"),
        "components": re.compile(r"^- \*\*Component Weights:\*\* `(.+?)`$"),
        "interpretation": re.compile(r"^- \*\*Economic Synthesis:\*\* (.+)$"),
    }

    current: dict[str, Any] | None = None
    for line_no, line in enumerate(source, 1):
        table_match = table_re.match(line)
        if table_match:
            model_id = table_match.group(1)
            if model_id in table:
                duplicate_lines[model_id] = line_no
            table[model_id] = {
                "line": line_no,
                "model_id": model_id,
                "model_name": table_match.group(2),
                "primary_value_text": table_match.group(3),
                "unit": table_match.group(4),
                "status": table_match.group(5),
                "driver": table_match.group(6),
            }
            continue

        detail_match = detail_re.match(line)
        if detail_match:
            model_id = detail_match.group(1)
            if model_id in details:
                duplicate_lines[model_id] = line_no
            current = {
                "line": line_no,
                "model_id": model_id,
                "model_name": detail_match.group(2),
            }
            details[model_id] = current
            continue

        if current is None:
            continue
        for field, pattern in field_res.items():
            match = pattern.match(line)
            if match:
                current[field] = match.groups() if len(match.groups()) > 1 else match.group(1)
                break

    ordered = []
    for model_id, detail in details.items():
        ordered.append({"model_id": model_id, "line": detail["line"], "table": table.get(model_id), "detail": detail})
    return ordered, duplicate_lines


def formula_model_exists(formula_ref: str) -> bool:
    parsed = urlparse(formula_ref)
    filename = os.path.basename(unquote(parsed.path))
    anchor = unquote(parsed.fragment)
    if parsed.netloc != "analysisreports.github.io" or not filename.startswith("llms-formulas"):
        return False
    path = os.path.join(ROOT_DIR, filename)
    if not os.path.isfile(path) or not re.fullmatch(r"\d+(?:\.\d+)*", anchor):
        return False
    with open(path, "r", encoding="utf-8") as handle:
        return bool(re.search(rf"(?m)^###\s+{re.escape(anchor)}\.\s+", handle.read()))


def add_compare(issues: list[Issue], line: int, field: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        issues.append(Issue(TXT_PATH, line, field, f"TXT {actual!r} differs from JSON {expected!r}"))


def verify_models(json_path: str = JSON_PATH, txt_path: str = TXT_PATH) -> list[Issue]:
    global JSON_PATH, TXT_PATH
    JSON_PATH, TXT_PATH = json_path, txt_path
    issues: list[Issue] = []
    with open(JSON_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    models = payload.get("models")
    metadata = payload.get("metadata", {})
    if not isinstance(models, list):
        return [Issue(JSON_PATH, 1, "models", "models must be a list")]

    if metadata.get("total_models_active") != len(models):
        issues.append(
            Issue(JSON_PATH, 1, "metadata.total_models_active", f"declared {metadata.get('total_models_active')} but found {len(models)}")
        )

    txt_models, duplicate_lines = parse_txt_models(TXT_PATH)
    json_by_id = {model.get("model_id"): model for model in models if isinstance(model, dict)}
    txt_by_id = {item["model_id"]: item for item in txt_models}

    for model_id, line_no in duplicate_lines.items():
        issues.append(Issue(TXT_PATH, line_no, "model_id", f"duplicate model {model_id}"))
    if len(json_by_id) != len(models):
        issues.append(Issue(JSON_PATH, 1, "model_id", "duplicate or missing model_id in JSON models"))
    for model_id in sorted(set(json_by_id) - set(txt_by_id)):
        issues.append(Issue(TXT_PATH, 1, "models", f"JSON model {model_id} is missing from TXT details"))
    for model_id in sorted(set(txt_by_id) - set(json_by_id)):
        issues.append(Issue(TXT_PATH, txt_by_id[model_id]["line"], "model_id", f"TXT model {model_id} is missing from JSON"))

    json_sync = str(metadata.get("last_updated") or "")
    sync_match = re.search(r"> \*\*Last Calibrated Sync:\*\* (.+)$", "\n".join(lines(TXT_PATH)), re.MULTILINE)
    if not sync_match:
        issues.append(Issue(TXT_PATH, 1, "last_sync", "calibrated sync timestamp is missing"))
    else:
        expected_sync = json_sync[:16].replace("T", " ") + " UTC"
        add_compare(issues, 12, "last_sync", sync_match.group(1), expected_sync)

    for index, model in enumerate(models, 1):
        model_id = model.get("model_id")
        line = 1
        if not model_id or not re.fullmatch(r"MODEL_\d+(?:\.\d+)*", model_id):
            issues.append(Issue(JSON_PATH, 1, f"models[{index}].model_id", f"invalid ID {model_id!r}"))
            continue
        formula_ref = model.get("formula_ref", "")
        if not formula_model_exists(formula_ref):
            issues.append(Issue(JSON_PATH, 1, f"{model_id}.formula_ref", f"formula reference does not resolve: {formula_ref!r}"))

        primary = model.get("primary_value")
        if isinstance(primary, bool) or (isinstance(primary, (int, float)) and not math.isfinite(primary)):
            issues.append(Issue(JSON_PATH, 1, f"{model_id}.primary_value", "value must be finite numeric or explicit null"))
        if primary is None and not re.search(r"UNAVAILABLE|UNCLASSIFIED|NO_DATA|INSUFFICIENT", str(model.get("status", ""))):
            issues.append(Issue(JSON_PATH, 1, f"{model_id}.primary_value", "null requires an explicit unavailable/unclassified status"))

        parsed = txt_by_id.get(model_id)
        if not parsed:
            continue
        table = parsed["table"]
        detail = parsed["detail"]
        line = int(detail["line"])
        if table is None:
            issues.append(Issue(TXT_PATH, line, "summary_table", f"summary row missing for {model_id}"))
        else:
            table_line = int(table["line"])
            add_compare(issues, table_line, "model_name", table["model_name"], model.get("model_name"))
            add_compare(issues, table_line, "primary_value", table["primary_value_text"], display_value(primary))
            add_compare(issues, table_line, "unit", table["unit"], model.get("unit"))
            add_compare(issues, table_line, "status", table["status"], model.get("status"))

        add_compare(issues, line, "model_name", detail.get("model_name"), model.get("model_name"))
        add_compare(issues, line, "formula_ref", detail.get("formula_ref"), formula_ref)
        expected_status_value = (model.get("status"), f"{primary} {model.get('unit')}")
        add_compare(issues, line, "evaluated_status", detail.get("status_value"), expected_status_value)
        add_compare(issues, line, "interpretation", detail.get("interpretation"), model.get("interpretation"))
        for field, label in (
            ("inputs", "inputs"),
            ("metrics", "metrics"),
            ("components", "components"),
            ("rate_disparities", "rate_disparities"),
        ):
            if field in model and field in detail:
                try:
                    parsed_value = parse_json_field(str(detail[field]))
                except json.JSONDecodeError as exc:
                    issues.append(Issue(TXT_PATH, line, label, f"invalid JSON text: {exc}"))
                else:
                    add_compare(issues, line, label, parsed_value, model[field])
            elif (field in model) != (field in detail):
                issues.append(Issue(TXT_PATH, line, label, "field presence differs between TXT and JSON"))
    return issues


def main() -> int:
    issues = verify_models()
    if issues:
        print(f"[FAIL] Models source guard found {len(issues)} issue(s).")
        for issue in issues:
            issue.report()
        return 1
    print("[PASS] Models source guard: llms-models.txt and llms-models.json are fully synchronized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
