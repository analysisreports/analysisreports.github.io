#!/usr/bin/env python3
"""Validate country-relationship TXT shelves against their JSON twins."""

import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple

from update_country_relationships import parse_country_relationships


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SHELVES = (
    ("us", "GEO_US", 73),
    ("ru", "GEO_RU", 33),
    ("cn", "GEO_CN", 34),
    ("ir", "GEO_IR", 25),
)


def emit_error(path: str, message: str, line: int = 1) -> None:
    relative_path = os.path.relpath(path, ROOT_DIR).replace(os.sep, "/")
    print(f"::error file={relative_path},line={line}::{message}")


def parse_error_line(message: str) -> int:
    match = re.search(r"\[Line\s+(\d+)\]", message)
    return int(match.group(1)) if match else 1


def compare_shelf(
    txt_path: str,
    json_path: str,
    expected_hub: str,
    expected_count: int,
) -> List[str]:
    with open(txt_path, "r", encoding="utf-8") as handle:
        txt_content = handle.read()

    try:
        parsed_hubs = parse_country_relationships(txt_content)
    except Exception as exc:
        message = str(exc)
        emit_error(txt_path, message, parse_error_line(message))
        return [message]

    errors: List[str] = []
    if set(parsed_hubs) != {expected_hub}:
        message = (
            f"{os.path.basename(txt_path)} must contain exactly hub {expected_hub}; "
            f"found {sorted(parsed_hubs)}"
        )
        errors.append(message)
        emit_error(txt_path, message)

    parsed_dyads = parsed_hubs.get(expected_hub, {}).get("dyads", {})
    if len(parsed_dyads) != expected_count:
        message = (
            f"{expected_hub} expected {expected_count} dyads, "
            f"but TXT contains {len(parsed_dyads)}"
        )
        errors.append(message)
        emit_error(txt_path, message)

    try:
        with open(json_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        message = f"Cannot read JSON twin: {exc}"
        errors.append(message)
        emit_error(json_path, message)
        return errors

    hub_payload = payload.get("sovereign_hub", {})
    json_dyads = hub_payload.get("dyads", {})
    if hub_payload.get("hub_id") != expected_hub:
        message = (
            f"JSON hub_id '{hub_payload.get('hub_id')}' does not match expected "
            f"'{expected_hub}'"
        )
        errors.append(message)
        emit_error(json_path, message)

    missing = sorted(set(parsed_dyads) - set(json_dyads))
    extra = sorted(set(json_dyads) - set(parsed_dyads))
    if missing:
        message = f"JSON twin is missing dyads: {', '.join(missing)}"
        errors.append(message)
        emit_error(json_path, message)
    if extra:
        message = f"JSON twin contains dyads absent from TXT: {', '.join(extra)}"
        errors.append(message)
        emit_error(json_path, message)

    for dyad_id in sorted(set(parsed_dyads).intersection(json_dyads)):
        expected = parsed_dyads[dyad_id]
        actual = json_dyads[dyad_id]
        if expected == actual:
            continue

        fields = sorted(
            key
            for key in set(expected).union(actual)
            if expected.get(key) != actual.get(key)
        )
        line = 1
        marker = f"Dyad ID: {dyad_id}"
        marker_position = txt_content.find(marker)
        if marker_position >= 0:
            line = txt_content.count("\n", 0, marker_position) + 1
        message = (
            f"TXT/JSON mismatch for {dyad_id}; fields differ: "
            f"{', '.join(fields)}. Regenerate the JSON twin after validating the edit."
        )
        errors.append(message)
        emit_error(txt_path, message, line)

    return errors


def audit_sources() -> List[str]:
    errors: List[str] = []
    for slug, hub_id, expected_count in SHELVES:
        txt_path = os.path.join(
            ROOT_DIR, f"llms-country-relationships-{slug}.txt"
        )
        json_path = os.path.join(
            ROOT_DIR, f"llms-country-relationships-{slug}.json"
        )
        errors.extend(
            compare_shelf(txt_path, json_path, hub_id, expected_count)
        )
    return errors


def main() -> int:
    print("=" * 72)
    print("COUNTRY RELATIONSHIPS SOURCE / JSON TWIN GUARD")
    print("=" * 72)
    errors = audit_sources()
    if errors:
        print(f"[FAIL] {len(errors)} country-relationship source issue(s) detected.")
        for error in errors:
            print(f"  [!] {error}")
        return 1

    print("[SUCCESS] 4 TXT shelves parsed successfully.")
    print("[SUCCESS] 165 dyads exactly match their JSON twins.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
