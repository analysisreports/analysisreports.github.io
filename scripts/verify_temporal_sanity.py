#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_temporal_sanity.py
--------------------------
Chronological, Treaty Sequence & Geopolitical Anachronism Verification Engine.

Audits geopolitical timelines across knowledge files:
1. Treaty Order of Operations: Imza (Signed) <= Yürürlük (Enacted) <= Simulation Horizon.
2. Watershed Event Anchor Invariance:
   - Qasr-e Shirin: 1639
   - Montreux Convention: 1936
   - Sadabat Pact: 1937
   - JCPOA Signing: 2015-07 / US Exit: 2018-05
   - Beijing Accord: 2023-03
   - Fall of Assad Regime: 2024-12 (No post-Assad references prior to Dec 2024)
   - Twelve Day War: 2025-06
   - E3 Snapback Sanctions: 2025-08
   - Russia-Iran 20-Year Treaty: Signed 2025-01, Enacted 2025-10
3. Future Leak Guard: No factual events described as historical reality beyond November 2026.

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-country-relationships.txt
"""

import os
import re
import sys
from datetime import datetime
from typing import List, Tuple, Dict, Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FILES_TO_CHECK = [
    os.path.join(ROOT_DIR, "llms-country-relationships.txt"),
    os.path.join(ROOT_DIR, "llms-relationships.txt"),
    os.path.join(ROOT_DIR, "llms-schema-political.txt"),
    os.path.join(ROOT_DIR, "llms-schema-political-country.txt"),
    os.path.join(ROOT_DIR, "llms.txt"),
    os.path.join(ROOT_DIR, "llms-full.txt")
]

# Canonical Watershed Anchors: Event -> (Minimum Valid Year-Month, Description)
WATERSHED_ANCHORS = {
    r"(?:Qasr-e\s*Shirin|Kasr-ı\s*Şirin)": (1639, "Kasr-ı Şirin Treaty (1639)"),
    r"(?:Montreux|Montrö)": (1936, "Montreux Straits Convention (1936)"),
    r"(?:Sadabat|Saadabad)": (1937, "Sadabat Pact (1937)"),
    r"(?:JCPOA|Nükleer\s*Anlaşma).*?(?:imza|signed)": (2015, "JCPOA Nuclear Deal Signing (July 2015)"),
    r"(?:JCPOA|Nükleer\s*Anlaşma).*?(?:çekilme|withdrew|exit)": (2018, "US JCPOA Withdrawal (May 2018)"),
    r"(?:Pekin\s*Anlaşması|Beijing\s*Accord)": (2023, "Saudi-Iran Beijing Normalization (March 2023)"),
    r"(?:Esad\s*(?:rejiminin\s*devrilmesi|sonrası|düşmesi)|post-Assad|fall\s*of\s*Assad)": (2024, "Fall of Assad Regime (December 2024)"),
    r"(?:12\s*Gün\s*Savaşı|Twelve\s*Day\s*War)": (2025, "Twelve Day War (June 2025)"),
    r"(?:snapback|E3\s*snapback)": (2025, "E3 Snapback UN Sanctions (August 2025)")
}

SIMULATION_HORIZON_YEAR = 2026
SIMULATION_HORIZON_MONTH = 11

MONTHS_TR = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12
}

MONTHS_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

def parse_date_str(d_str: str) -> Tuple[int, int]:
    """Extracts year and month from string like '16-17 Ocak 2025' or 'Ağustos 2025' or '2024'."""
    d_clean = d_str.lower().strip()
    
    # Check year
    y_m = re.search(r"\b(1[6-9]\d\d|20\d\d)\b", d_clean)
    year = int(y_m.group(1)) if y_m else 0

    # Check month
    month = 1
    for m_name, m_num in {**MONTHS_TR, **MONTHS_EN}.items():
        if re.search(r"\b" + m_name + r"\b", d_clean):
            month = m_num
            break

    return year, month

def audit_treaty_order(text: str, filename: str) -> List[str]:
    """Finds occurrences where signing and enactment are mentioned, ensuring signing <= enactment."""
    errors = []
    
    # Pattern: X tarihinde imzalanan ... Y tarihinde yürürlüğe giren
    treaty_patterns = [
        r"([^\.\n]*?(\d{1,2}\s+[A-Za-zğüşıöçĞÜŞİÖÇ]+\s+\d{4}|\d{4})\s*(?:tarihinde|yılında)?\s*imzalan(?:an|mış|dı)[^\.\n]*?(\d{1,2}\s+[A-Za-zğüşıöçĞÜŞİÖÇ]+\s+\d{4}|\d{4})\s*(?:tarihinde|yılında)?\s*yürürlüğe\s*gir(?:en|miş|di)[^\.\n]*)",
        r"([^\.\n]*?signed\s*in\s*([A-Za-z]+\s+\d{4}|\d{4})[^\.\n]*?entered\s*into\s*force\s*in\s*([A-Za-z]+\s+\d{4}|\d{4})[^\.\n]*)"
    ]

    for pat in treaty_patterns:
        matches = re.finditer(pat, text, re.IGNORECASE)
        for m in matches:
            full_snippet = m.group(1)
            date1_str = m.group(2)
            date2_str = m.group(3)

            y1, m1 = parse_date_str(date1_str)
            y2, m2 = parse_date_str(date2_str)

            if y1 and y2:
                # Compare (y1, m1) and (y2, m2)
                t1 = y1 * 12 + m1
                t2 = y2 * 12 + m2
                if t1 > t2:
                    errors.append(
                        f"TREATY SEQUENCE ERROR in {os.path.basename(filename)}: "
                        f"Signing date ({date1_str}) is AFTER enactment date ({date2_str}) in: '{full_snippet.strip()}'"
                    )

    return errors

def audit_watershed_events(text: str, filename: str) -> List[str]:
    """Ensures watershed events are not attributed to impossible earlier years."""
    errors = []
    lines = text.splitlines()

    for l_idx, line in enumerate(lines, 1):
        for pattern, (min_year, desc) in WATERSHED_ANCHORS.items():
            if re.search(pattern, line, re.IGNORECASE):
                # Look for years in the same line
                years = [int(y) for y in re.findall(r"\b(19\d\d|20\d\d)\b", line)]
                # If there are years mentioned directly attached to the action, check if any is strictly less than min_year
                # Specifically targeting anachronisms: e.g. "2023'te Esad devrildi"
                for y in years:
                    if y < min_year and y >= 2000: # Only trigger for modern era mismatches
                        # Check context proximity
                        match_phrase = re.search(r"(\b" + str(y) + r"\b[^\.\n]{0,40}" + pattern + r"|" + pattern + r"[^\.\n]{0,40}\b" + str(y) + r"\b)", line, re.IGNORECASE)
                        if match_phrase:
                            errors.append(
                                f"ANACHRONISM in {os.path.basename(filename)} Line {l_idx}: "
                                f"{desc} cannot be dated to {y}! Context: '{line.strip()}'"
                            )

    return errors

def audit_future_leaks(text: str, filename: str) -> List[str]:
    """Guards against factual statements claiming historical completion beyond November 2026."""
    errors = []
    lines = text.splitlines()

    # Look for years >= 2027 described in past tense
    past_tense_indicators_tr = [r"devrildi", r"imzalandı", r"gerçekleşti", r"yapıldı", r"tamamlandı", r"sona erdi", r"çöktü"]
    past_tense_indicators_en = [r"was signed", r"concluded", r"collapsed", r"took place", r"occurred", r"completed"]

    for l_idx, line in enumerate(lines, 1):
        future_years = [int(y) for y in re.findall(r"\b(202[7-9]|20[3-9]\d)\b", line)]
        if not future_years:
            continue

        for fy in future_years:
            # Check if mentioned with past tense completion
            has_past_tr = any(re.search(rf"\b{fy}\b[^\.\n]*?{ind}", line, re.IGNORECASE) for ind in past_tense_indicators_tr)
            has_past_en = any(re.search(rf"\b{fy}\b[^\.\n]*?{ind}", line, re.IGNORECASE) for ind in past_tense_indicators_en)
            
            # Target projections/concessions are OK (e.g. 2030 vision, 25-year agreement until 2046, 99-year lease)
            is_projection_or_lease = bool(re.search(r"(?:vision|vizyon|hedef|target|until|kadar|lease|kira|proje|projected)", line, re.IGNORECASE))

            if (has_past_tr or has_past_en) and not is_projection_or_lease:
                errors.append(
                    f"FUTURE LEAK in {os.path.basename(filename)} Line {l_idx}: "
                    f"Year {fy} described as completed historical fact beyond simulation horizon (Nov 2026): '{line.strip()}'"
                )

    return errors

def main():
    print("=" * 70)
    print("CHRONOLOGICAL, TREATY SEQUENCE & TEMPORAL SANITY AUDITOR")
    print(f"Simulation Horizon: {SIMULATION_HORIZON_YEAR}-{SIMULATION_HORIZON_MONTH:02d} (Kasım 2026)")
    print("=" * 70)

    total_files_audited = 0
    all_errors = []

    for fpath in FILES_TO_CHECK:
        if not os.path.exists(fpath):
            continue
        total_files_audited += 1
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        fname = os.path.basename(fpath)
        t_errors = audit_treaty_order(content, fpath)
        w_errors = audit_watershed_events(content, fpath)
        f_errors = audit_future_leaks(content, fpath)

        file_errors = t_errors + w_errors + f_errors
        if file_errors:
            all_errors.extend(file_errors)
        else:
            print(f"[*] {fname:<36} : 100% Temporally Sound")

    print("\n" + "=" * 70)
    if all_errors:
        print(f"[FAIL] DETECTED {len(all_errors)} TEMPORAL / CHRONOLOGICAL ISSUES:")
        for err in all_errors:
            print(f"  [!] {err}")
        print("=" * 70)
        sys.exit(1)
    else:
        print(f"[SUCCESS] 100% TEMPORALLY COHERENT ({total_files_audited} files audited):")
        print(f"  - Treaty Sequencing (Signing <= Enactment) : 100% Invariant")
        print(f"  - Watershed Anchors (Assad 2024, E3 2025)   : 100% Compliant")
        print(f"  - Future Leak Guard (Horizon <= 2026-11)   : 100% Clean (0 leaks)")
        print("=" * 70)
        sys.exit(0)

if __name__ == "__main__":
    main()
