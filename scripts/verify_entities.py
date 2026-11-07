#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_entities.py
------------------
Entity & Canonical ID Integrity Checker for LLM Ontologies.
Validates all entity references in JSON, Markdown, and TXT files against
the canonical ground-truth defined in llms-entities-id.txt.

Detects:
  - Unknown/unregistered entity identifiers
  - Typographical mistakes and suggests closest valid alternatives via difflib

Author: Ersoy Toptaş & AnalysisReports AI Engine
"""

import os
import re
import sys
import json
import difflib
from typing import Set, List, Dict, Tuple

# Canonical ID prefix pattern defined in llms-entities-id.txt
ENTITY_PREFIXES = (
    "INST_", "GOV_", "GEO_", "REG_", "PROXY_", "ORG_", "BLOC_",
    "CHOKE_", "CORRIDOR_", "BASIN_", "ZONE_", "STAT_", "REG_AGENCY_",
    "MKT_", "SEC_", "IND_"
)

# Regex to capture entity-like tokens
ENTITY_REGEX = re.compile(
    r"\b((?:INST_|GOV_|GEO_|REG_|PROXY_|ORG_|BLOC_|CHOKE_|CORRIDOR_|BASIN_|ZONE_|STAT_|REG_AGENCY_|MKT_|SEC_|IND_)[A-Z0-9_]+)\b"
)


def load_canonical_entities(entities_file: str) -> Set[str]:
    """Reads llms-entities-id.txt and extracts all valid canonical entity IDs."""
    valid_ids: Set[str] = set()
    if not os.path.exists(entities_file):
        print(f"[HATA] Kanonik sözlük dosyası bulunamadı: {entities_file}", file=sys.stderr)
        sys.exit(1)

    with open(entities_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Format: ENTITY_ID | Aliases: ...
            parts = line.split("|")
            entity_id = parts[0].strip()
            if any(entity_id.startswith(prefix) for prefix in ENTITY_PREFIXES):
                valid_ids.add(entity_id)

    return valid_ids


def check_file(file_path: str, valid_entities: Set[str]) -> List[Tuple[int, str, str]]:
    """Scans a file for entity patterns and verifies them against the canonical set."""
    issues = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                # Skip comments in headers
                matches = ENTITY_REGEX.findall(line)
                for matched_id in matches:
                    # Strip trailing underscores if any
                    clean_id = matched_id.rstrip("_")
                    if clean_id not in valid_entities:
                        # Find closest match
                        suggestions = difflib.get_close_matches(clean_id, valid_entities, n=1, cutoff=0.6)
                        suggestion = suggestions[0] if suggestions else "Eşleşen öneri bulunamadı"
                        issues.append((line_no, clean_id, suggestion))
    except Exception as e:
        print(f"[UYARI] Dosya okunamadı: {file_path} -> {e}", file=sys.stderr)

    return issues


def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    entities_file = os.path.join(root_dir, "llms-entities-id.txt")

    print("=" * 70)
    print("CANONICAL ENTITY INTEGRITY CHECKER")
    print("=" * 70)

    valid_entities = load_canonical_entities(entities_file)
    print(f"[*] Toplam {len(valid_entities)} adet geçerli Kanonik Entity ID yüklendi.\n")

    # Files and folders to scan
    target_files = [
        "llms-graph.json",
        "llms-relationships.json",
        "llms-relationships.txt",
        "llms-formulas.txt",
        "llms-indicators.txt",
        "llms-tools.json",
        "WORKFLOW.md",
        "country.json",
        "economy.json",
        "political.json",
        "political-country.json",
    ]

    total_issues = 0

    for relative_path in target_files:
        full_path = os.path.join(root_dir, relative_path)
        if not os.path.exists(full_path):
            continue

        issues = check_file(full_path, valid_entities)
        if issues:
            print(f"[!] HATA: {relative_path} ({len(issues)} uyumsuzluk bulundu):")
            for line_no, invalid_id, suggestion in issues:
                total_issues += 1
                print(f"    - Satır {line_no:>4}: Geçersiz ID -> '{invalid_id}'")
                print(f"      Öneri       -> '{suggestion}'")
            print("-" * 70)
        else:
            print(f"[+] DOĞRULANDI: {relative_path}")

    print("\n" + "=" * 70)
    if total_issues > 0:
        print(f"[SONUÇ] Toplam {total_issues} adet geçersiz veya kayıt dışı Entity ID tespit edildi!")
        print("Lütfen yukarıdaki hataları düzeltin veya 'llms-entities-id.txt' içine ekleyin.")
        print("=" * 70)
        sys.exit(1)
    else:
        print("[SONUÇ] Mükemmel! Tüm Entity ID'leri 'llms-entities-id.txt' ile %100 uyumlu.")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    main()
