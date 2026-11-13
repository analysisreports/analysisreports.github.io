#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check that newly introduced workflow items include their required artifacts."""

import json
import os
import re
import subprocess
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENTITY_FILE = "llms-entities-id.txt"
RELATIONSHIP_TEXT = "llms-relationships.txt"
RELATIONSHIP_JSON = "llms-relationships.json"
GRAPH_FILE = "llms-graph.json"
MODEL_JSON = "llms-models.json"
SERIES_PROVIDERS = {
    "llms-fred-series.json": "llms-fred-series.txt",
    "llms-ecb-series.json": "llms-ecb-series.txt",
    "llms-worldbank-series.json": "llms-worldbank-series.txt",
    "llms-imf-series.json": "llms-imf-series.txt",
    "llms-nyfed-series.json": "llms-nyfed-series.txt",
    "llms-eia-series.json": "llms-eia-series.txt",
}


def parse_json(content, path):
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc


def entity_ids(content):
    return {
        match.group(1)
        for line in content.splitlines()
        if (match := re.match(r"^\s*([A-Z][A-Z0-9_]+)\s*\|", line))
    }


def relationship_rows(content):
    table = content.split("| Actor Pair | P_baseline (Structural)", 1)
    if len(table) != 2:
        raise ValueError(f"{RELATIONSHIP_TEXT}: dynamic polarity table not found")
    rows = {}
    for line in table[1].splitlines():
        if line.startswith("**Model 25.19 relationship contributions:"):
            break
        match = re.match(r"^\|\s*\*\*([A-Z][A-Z0-9_]+)\*\*\s*\|", line)
        if match:
            if match.group(1) in rows:
                raise ValueError(f"{RELATIONSHIP_TEXT}: duplicate pair {match.group(1)}")
            rows[match.group(1)] = [part.strip() for part in line.strip("|").split("|")][1:]
    return rows


def model_ids(content):
    return {
        item["model_id"]: item
        for item in parse_json(content, MODEL_JSON).get("models", [])
        if isinstance(item, dict) and isinstance(item.get("model_id"), str)
    }


def series_ids(content, path):
    series = parse_json(content, path).get("series", {})
    if not isinstance(series, dict):
        raise ValueError(f"{path}: 'series' must be a JSON object")
    return set(series)


def file_at(revision, path):
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=ROOT_DIR, capture_output=True, text=True, encoding="utf-8",
    )
    return result.stdout if result.returncode == 0 else None


def audit(base_files, current_files):
    errors = []
    base_entities = entity_ids(base_files[ENTITY_FILE])
    current_entities = entity_ids(current_files[ENTITY_FILE])
    current_graph = parse_json(current_files[GRAPH_FILE], GRAPH_FILE)
    graph_nodes = {
        node.get("id") for node in current_graph.get("nodes", [])
        if isinstance(node, dict)
    }
    graph_edges = current_graph.get("edges", [])
    base_rel_data = parse_json(base_files[RELATIONSHIP_JSON], RELATIONSHIP_JSON)
    current_rel_data = parse_json(current_files[RELATIONSHIP_JSON], RELATIONSHIP_JSON)
    base_rels = {item["id"]: item for item in base_rel_data.get("relationships", [])}
    current_rels = {item["id"]: item for item in current_rel_data.get("relationships", [])}
    base_rows = relationship_rows(base_files[RELATIONSHIP_TEXT])
    current_rows = relationship_rows(current_files[RELATIONSHIP_TEXT])

    new_pairs = (set(current_rels) - set(base_rels)) | (set(current_rows) - set(base_rows))
    for pair_id in sorted(new_pairs):
        if pair_id not in current_rels or pair_id not in current_rows:
            errors.append(f"New relationship {pair_id} must appear in both relationship TXT and JSON.")
            continue
        relation = current_rels[pair_id]
        fields = (
            ("p_baseline", 2), ("dynamic_delta", 6), ("mecca_pact_delta", 2),
            ("legacy_dynamic_delta", 2), ("p_net", 2),
        )
        expected = []
        for field, precision in fields:
            if field not in relation:
                errors.append(f"New relationship {pair_id}: JSON field {field} is missing.")
                expected.append(None)
                continue
            value = relation[field]
            expected.append(
                ("N/A (Mecca Pact)" if field == "legacy_dynamic_delta" else "null")
                if value is None else f"{value:+.{precision}f}"
            )
        expected.extend([relation.get("regime_state"), relation.get("primary_driver")])
        if current_rows[pair_id] != expected:
            errors.append(f"New relationship {pair_id}: dynamic TXT row does not match JSON.")
        source, target = relation.get("source_entity"), relation.get("target_entity")
        for entity in (source, target):
            if entity not in current_entities:
                errors.append(f"New relationship {pair_id}: {entity!r} is missing from {ENTITY_FILE}.")
            if entity not in graph_nodes:
                errors.append(f"New relationship {pair_id}: graph node {entity!r} is missing.")
        if source and target and not any(
            {edge.get("source"), edge.get("target")} == {source, target}
            and edge.get("type") in {"POLARITY_COUPLING", "PATRON_COUPLING"}
            for edge in graph_edges if isinstance(edge, dict)
        ):
            errors.append(f"New relationship {pair_id}: graph coupling edge is missing.")

    new_entities = current_entities - base_entities
    for entity in sorted(new_entities):
        if entity.startswith(("GEO_", "PROXY_", "BLOC_", "CHOKE_", "CORRIDOR_")):
            if entity not in graph_nodes:
                errors.append(f"New canonical entity {entity} is missing from graph nodes.")
            elif not any(
                entity in (edge.get("source"), edge.get("target"))
                and edge.get("source") != edge.get("target")
                for edge in graph_edges if isinstance(edge, dict)
            ):
                errors.append(f"New canonical entity {entity} has no graph edge.")

    new_models = set(model_ids(current_files[MODEL_JSON])) - set(model_ids(base_files[MODEL_JSON]))
    for model_id in sorted(new_models):
        if model_id not in graph_nodes:
            errors.append(f"New model {model_id} is missing from graph nodes.")
        if not any(
            edge.get("target") == model_id and edge.get("type") == "INGESTS_SERIES"
            for edge in graph_edges if isinstance(edge, dict)
        ):
            errors.append(f"New model {model_id} has no graph INGESTS_SERIES edge.")
        number = re.escape(model_id.removeprefix("MODEL_"))
        for path, pattern in (
            ("llms-formulas.txt", rf"(?m)^###\s+{number}\.\s"),
            ("llms-full.txt", rf"(?m)^\s*-\s+{number}\.\s"),
            ("llms-models.txt", re.escape(model_id)),
        ):
            if not re.search(pattern, current_files[path]):
                errors.append(f"New model {model_id} is missing from {path}.")

    for provider_json, provider_text in SERIES_PROVIDERS.items():
        added = series_ids(current_files[provider_json], provider_json) - series_ids(
            base_files[provider_json], provider_json
        )
        if added:
            for path in (provider_text, "llms-indicators.txt"):
                missing = sorted(
                    series_id for series_id in added
                    if not re.search(
                        rf"(?<![A-Z0-9_]){re.escape(series_id)}(?![A-Z0-9_])",
                        current_files[path],
                    )
                )
                if missing:
                    errors.append(f"New series missing from {path}: {', '.join(missing)}")

    return errors


def main():
    base = os.environ.get("WORKFLOW_BASE_SHA")
    if not base:
        print("[FAIL] WORKFLOW_BASE_SHA is required for change-aware checks.", file=sys.stderr)
        return 2
    try:
        required = {
            ENTITY_FILE, RELATIONSHIP_TEXT, RELATIONSHIP_JSON, GRAPH_FILE, MODEL_JSON,
            "llms-indicators.txt", "llms-formulas.txt", "llms-full.txt", "llms-models.txt",
            *SERIES_PROVIDERS.keys(), *SERIES_PROVIDERS.values(),
        }
        base_files = {path: file_at(base, path) for path in required}
        current_files = {
            path: open(os.path.join(ROOT_DIR, path), encoding="utf-8").read()
            for path in required
        }
        missing = [path for path, content in base_files.items() if content is None]
        if missing:
            raise ValueError(f"Base revision is missing required files: {', '.join(sorted(missing))}")
        errors = audit(base_files, current_files)
    except (OSError, subprocess.CalledProcessError, ValueError, TypeError, KeyError) as exc:
        print(f"[FAIL] Workflow verification could not complete: {exc}", file=sys.stderr)
        return 2

    if errors:
        print("[FAIL] Workflow steps are incomplete:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("[PASS] Checked new relationship, entity, model snapshot and provider series references.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
