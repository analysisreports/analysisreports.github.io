#!/usr/bin/env python3
"""Strict source-integrity guards for the canonical TXT control plane."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Iterable


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FORMULA_FILES = (
    "llms-formulas-rates-liquidity.txt",
    "llms-formulas-macro-labor.txt",
    "llms-formulas-commodities-shock.txt",
    "llms-formulas-geopolitics.txt",
)
ENTITY_PATTERN = re.compile(
    r"^(INST_|GOV_|GEO_|REG_|PROXY_|ORG_|BLOC_|CHOKE_|CORRIDOR_|BASIN_|ZONE_|"
    r"STAT_|REG_AGENCY_|MKT_|SEC_|ENERGY_|COMMODITY_|IND_)[A-Z0-9_]+$"
)


@dataclass
class Issue:
    file: str
    line: int
    field: str
    message: str

    def report(self) -> None:
        rel = os.path.relpath(self.file, ROOT_DIR).replace(os.sep, "/")
        print(f"{rel}:{self.line}: {self.field}: {self.message}")
        print(
            f"::error file={rel},line={self.line},title=Special source guard::{self.field}: {self.message}"
        )


def read_lines(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().splitlines()


def verify_entities() -> list[Issue]:
    path = os.path.join(ROOT_DIR, "llms-entities-id.txt")
    issues: list[Issue] = []
    seen: dict[str, int] = {}
    for line_no, raw in enumerate(read_lines(path), 1):
        line = raw.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        entity, sep, aliases = line.partition("|")
        entity = entity.strip()
        if not ENTITY_PATTERN.fullmatch(entity):
            issues.append(Issue(path, line_no, "entity_id", f"invalid canonical ID {entity!r}"))
        if entity in seen:
            issues.append(
                Issue(path, line_no, "entity_id", f"duplicate ID {entity!r}; first declared at line {seen[entity]}")
            )
        else:
            seen[entity] = line_no
        declaration = aliases.strip()
        if entity.startswith("IND_") and declaration.startswith("Aliases:"):
            if not declaration.split(":", 1)[1].strip():
                issues.append(Issue(path, line_no, "aliases", "at least one alias is required"))
        elif entity.startswith("IND_"):
            if not re.match(r"^Source:\s*[^|]+?\s*\|\s*Name:\s*\S", declaration):
                issues.append(
                    Issue(path, line_no, "indicator_entity", "IND rows must contain non-empty 'Source:' and 'Name:' fields")
                )
        elif not declaration.startswith("Aliases:"):
            issues.append(Issue(path, line_no, "aliases", "declaration must contain 'Aliases:'"))
        elif not declaration.split(":", 1)[1].strip():
            issues.append(Issue(path, line_no, "aliases", "at least one alias is required"))
    if not seen:
        issues.append(Issue(path, 1, "entities", "no canonical entities found"))
    return issues


def verify_indicators() -> list[Issue]:
    path = os.path.join(ROOT_DIR, "llms-indicators.txt")
    issues: list[Issue] = []
    seen: dict[str, int] = {}
    entry = re.compile(
        r"^\d+\.\s+\*\*([^*]+)\*\*\s+\((.+)\)\s+\|\s+Freq:\s+([^|]+?)\s+\|\s+Units:\s+([^|]+?)\s+\|\s+Source:\s+(.+)$"
    )
    for line_no, raw in enumerate(read_lines(path), 1):
        if not re.match(r"^\d+\.\s+", raw):
            continue
        match = entry.match(raw)
        if not match:
            issues.append(Issue(path, line_no, "registry_row", "indicator row no longer matches the canonical format"))
            continue
        series_id, description, frequency, units, source = (part.strip() for part in match.groups())
        if series_id in seen:
            issues.append(
                Issue(path, line_no, "series_id", f"duplicate series {series_id!r}; first declared at line {seen[series_id]}")
            )
        else:
            seen[series_id] = line_no
        for field, value in (
            ("description", description),
            ("frequency", frequency),
            ("units", units),
            ("source", source),
        ):
            if not value:
                issues.append(Issue(path, line_no, field, "value is empty"))
    if not seen:
        issues.append(Issue(path, 1, "indicators", "no indicator registry rows found"))
    return issues


def parse_formula_models(path: str) -> tuple[dict[str, dict[str, object]], list[Issue]]:
    lines = read_lines(path)
    starts = [
        (index, match.group(1).strip(), match.group(2).strip())
        for index, line in enumerate(lines)
        if (match := re.match(r"^###\s+([0-9]+(?:\.[0-9]+)*)\.\s+(.+)$", line))
    ]
    issues: list[Issue] = []
    models: dict[str, dict[str, object]] = {}
    for pos, (start, model_id, title) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start + 1 : end])
        if model_id in models:
            previous_line = int(models[model_id]["line"])
            issues.append(
                Issue(path, start + 1, "model_id", f"duplicate model {model_id}; first declared at line {previous_line}")
            )
            continue
        models[model_id] = {"line": start + 1, "title": title, "body": body}
        for field in ("purpose", "formula", "interpretation"):
            labels = {
                "purpose": ("Purpose",),
                "formula": (
                    "Formula",
                    "Mathematical Formulation",
                    "Threshold Logic & Rules",
                    "Trigger Formulas",
                ),
                "interpretation": ("Interpretation",),
            }[field]
            label_pattern = "|".join(re.escape(label) for label in labels)
            marker = re.search(
                rf"(?m)^-\s*(?:{label_pattern}):\s*(.*)$|^#{{1,6}}\s*(?:{label_pattern})\s*$",
                body,
            )
            has_content = bool(marker and (marker.group(1) or "").strip())
            if marker and not has_content:
                remainder = body[marker.end() :]
                next_block = re.search(r"(?m)^-\s*[A-Za-z ]+:", remainder)
                candidate = remainder[: next_block.start()] if next_block else remainder
                has_content = bool(re.search(r"\S", re.sub(r"^```(?:python)?$", "", candidate, flags=re.MULTILINE)))
            if not marker or not has_content:
                issues.append(Issue(path, start + 1, field, f"model {model_id} is missing a non-empty {field} block"))
    return models, issues


def verify_formulas() -> list[Issue]:
    issues: list[Issue] = []
    shelf_models: dict[str, dict[str, object]] = {}
    for filename in FORMULA_FILES:
        path = os.path.join(ROOT_DIR, filename)
        models, found = parse_formula_models(path)
        shelf_models.update(models)
        issues.extend(found)
        if not models:
            issues.append(Issue(path, 1, "models", "no formula models found"))

    master = os.path.join(ROOT_DIR, "llms-formulas.txt")
    master_ids: dict[str, int] = {}
    for line_no, line in enumerate(read_lines(master), 1):
        match = re.match(r"^###\s+([0-9]+(?:\.[0-9]+)*)\.\s+", line)
        if match and "RESERVED / ARCHITECTURALLY CONSOLIDATED" not in line:
            master_ids[match.group(1)] = line_no
    for model_id, model in shelf_models.items():
        if model_id not in master_ids:
            issues.append(
                Issue(
                    master,
                    int(model["line"]),
                    "router_index",
                    f"master router is missing model {model_id}; rebuild llms-formulas.txt",
                )
            )
    for model_id, line_no in master_ids.items():
        if not model_id.startswith("0.") and model_id not in shelf_models:
            issues.append(Issue(master, line_no, "router_index", f"master-only model {model_id} has no authoritative shelf"))
    return issues


def compare(actual: object, expected: object, path: str, line: int, field: str, issues: list[Issue]) -> None:
    if actual != expected:
        issues.append(Issue(path, line, field, f"TXT value {actual!r} differs from JSON value {expected!r}"))


def verify_news() -> list[Issue]:
    text_path = os.path.join(ROOT_DIR, "llms-news.txt")
    json_path = os.path.join(ROOT_DIR, "llms-news.json")
    with open(json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    lines = read_lines(text_path)
    header_re = re.compile(
        r"^\[(DISPATCH_\d+_\d+)\]\s+SEVERITY:\s+([^|]+?)\s+\|\s+STATUS:\s+([^|]+?)\s+\|\s+ENTITY:\s+(\S+)\s+\(([^)]+)\)$"
    )
    parsed = []
    for index, line in enumerate(lines):
        match = header_re.match(line)
        if not match:
            continue
        source = ""
        published = ""
        headline = ""
        for child in lines[index + 1 : index + 4]:
            source_match = re.match(r"^\s*-\s+SOURCE\s*:\s*(.*?)\s*\|\s*Published:\s*(.+)$", child)
            headline_match = re.match(r"^\s*-\s+HEADLINE\s*:\s*(.+)$", child)
            if source_match:
                source, published = source_match.groups()
            elif headline_match:
                headline = headline_match.group(1)
        parsed.append(
            {
                "line": index + 1,
                "dispatch_id": match.group(1),
                "event_severity": match.group(2).strip(),
                "institutional_status": match.group(3).strip(),
                "primary_entity": match.group(4),
                "related_entities": [item.strip() for item in match.group(5).split(",")],
                "source_authority": source,
                "published_utc": published,
                "headline": headline,
            }
        )
    issues: list[Issue] = []
    dispatches = data.get("dispatches", [])
    if len(parsed) != len(dispatches):
        issues.append(Issue(text_path, 1, "dispatch_count", f"TXT has {len(parsed)} dispatches; JSON has {len(dispatches)}"))
    for index, dispatch in enumerate(dispatches):
        if index >= len(parsed):
            break
        txt = parsed[index]
        for field in (
            "dispatch_id",
            "event_severity",
            "institutional_status",
            "primary_entity",
            "related_entities",
            "source_authority",
            "published_utc",
            "headline",
        ):
            compare(txt[field], dispatch.get(field), text_path, int(txt["line"]), f"dispatch.{field}", issues)
    if data.get("metadata", {}).get("total_dispatches") != len(dispatches):
        issues.append(
            Issue(json_path, 1, "metadata.total_dispatches", "metadata count differs from dispatch array length")
        )
    return issues


def verify_sitrep() -> list[Issue]:
    text_path = os.path.join(ROOT_DIR, "llms-sitrep.txt")
    json_path = os.path.join(ROOT_DIR, "llms-sitrep.json")
    with open(json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    lines = read_lines(text_path)
    issues: list[Issue] = []

    flash_re = re.compile(r"^FLASH_(\d+)\s+\[([^|]+)\s*\|\s*([^\]]+)\]:\s*(.+)$")
    txt_flashes = []
    for index, line in enumerate(lines):
        match = flash_re.match(line)
        if not match:
            continue
        causal = impact = ""
        for child in lines[index + 1 : index + 3]:
            causal_match = re.match(r"^\s*-\s*Causal Chain\s*:\s*(.+)$", child)
            impact_match = re.match(r"^\s*-\s*Systemic Impact:\s*(.+)$", child)
            if causal_match:
                causal = causal_match.group(1)
            elif impact_match:
                impact = impact_match.group(1)
        txt_flashes.append(
            {
                "line": index + 1,
                "number": int(match.group(1)),
                "source": match.group(2).strip(),
                "entity_id": match.group(3).strip(),
                "event": match.group(4).strip(),
                "causal_chain": causal,
                "systemic_impact": impact,
            }
        )
    flashes = data.get("top_systemic_flashes", [])
    if len(txt_flashes) != len(flashes):
        issues.append(Issue(text_path, 1, "flash_count", f"TXT has {len(txt_flashes)} flashes; JSON has {len(flashes)}"))
    for index, flash in enumerate(flashes):
        if index >= len(txt_flashes):
            break
        txt = txt_flashes[index]
        compare(txt["number"], index + 1, text_path, int(txt["line"]), "flash.sequence", issues)
        for field in ("source", "entity_id", "event", "causal_chain", "systemic_impact"):
            compare(txt[field], flash.get(field), text_path, int(txt["line"]), f"flash.{field}", issues)

    rule_re = re.compile(r"^\[(RULE_[A-Z0-9_]+)\]\s+Domain:\s*(.*?)\s*\|\s*Formula:\s*(.+)$")
    txt_rules = {}
    for index, line in enumerate(lines):
        match = rule_re.match(line)
        if not match:
            continue
        values = {
            "line": index + 1,
            "rule_id": match.group(1),
            "domain": match.group(2).strip(),
            "formula_link": match.group(3).strip(),
        }
        for child in lines[index + 1 : index + 4]:
            signal = re.match(r"^\s*-\s*TELEMETRY SIGNAL\s*:\s*(.+)$", child)
            bias = re.match(r"^\s*-\s*MEDIA CLAIM BIAS\s*:\s*(.+)$", child)
            reality = re.match(r"^\s*-\s*GROUND TRUTH REAL\s*:\s*(.+)$", child)
            if signal:
                values["telemetry_signal"] = signal.group(1)
            elif bias:
                values["media_claim_bias"] = bias.group(1)
            elif reality:
                values["ground_truth_reality"] = reality.group(1)
        txt_rules[values["rule_id"]] = values

    rules = data.get("systemic_contagion_rules", [])
    if len(txt_rules) != len(rules):
        issues.append(Issue(text_path, 1, "rule_count", f"TXT has {len(txt_rules)} rules; JSON has {len(rules)}"))
    for rule in rules:
        rule_id = rule.get("rule_id")
        txt = txt_rules.get(rule_id)
        if not txt:
            issues.append(Issue(text_path, 1, "rule_id", f"JSON rule {rule_id!r} is missing from TXT"))
            continue
        for field in ("domain", "formula_link", "telemetry_signal", "media_claim_bias", "ground_truth_reality"):
            compare(txt.get(field), rule.get(field), text_path, int(txt["line"]), f"rule.{field}", issues)
    return issues


def main() -> int:
    issues = [
        *verify_entities(),
        *verify_indicators(),
        *verify_formulas(),
        *verify_news(),
        *verify_sitrep(),
    ]
    if issues:
        print(f"[FAIL] Special source guard found {len(issues)} issue(s).")
        for issue in issues:
            issue.report()
        return 1
    print("[PASS] Special source guard: entities, indicators, formulas, News and SITREP are synchronized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
