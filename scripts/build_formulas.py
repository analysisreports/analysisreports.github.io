#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_formulas.py
-----------------
Master Quantitative Formulas Compiler & Sharding Engine.

Compiles modular formula shelves from the canonical mathematical logic:
1. llms-formulas-rates-liquidity.txt (Rates, yield curves, Fed/ECB liquidity, credit spreads, carry trades)
2. llms-formulas-macro-labor.txt (Inflation, labor, housing, growth, consumption, valuation, release calendars)
3. llms-formulas-commodities-shock.txt (Energy benchmarks, 3:2:1 crack spread, supply chain stress, chips, safe havens)
4. llms-formulas-geopolitics.txt (Dynamic polarity, Mecca Pact, chokepoint severity, strategic tension & confidence)
5. llms-formulas.txt (Master Router & Methodological Guide - Section 0.1-0.7 rules + Routing Index)

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-formulas.txt
"""

import os
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_FORMULAS = os.path.join(ROOT_DIR, "llms-formulas.txt")

# Target Shelves
SHELVES = {
    "rates-liquidity": {
        "file": os.path.join(ROOT_DIR, "llms-formulas-rates-liquidity.txt"),
        "title": "Rates, Yield Curves, Liquidity & Monetary Transmission",
        "scope": "Central bank policy stances, yield curve slopes, repo liquidity, credit spreads, carry trade, and committee dispersion",
        "models": ["1", "2", "4", "5", "6", "7", "9", "10", "11", "12", "13", "14", "15", "25.5", "25.16", "26"]
    },
    "macro-labor": {
        "file": os.path.join(ROOT_DIR, "llms-formulas-macro-labor.txt"),
        "title": "Macroeconomic Fundamentals, Labor Dynamics, Valuation & Cycles",
        "scope": "Inflation persistence, labor market momentum, housing affordability, consumption collapse, valuation metrics, and release calendars",
        "models": ["3", "8", "17", "18", "19", "22", "23", "23.1", "23.2", "23.3", "23.4", "23.5", "23.6", "23.7", "23.8", "25", "25.2", "25.10", "25.11", "25.13", "30"]
    },
    "commodities-shock": {
        "file": os.path.join(ROOT_DIR, "llms-formulas-commodities-shock.txt"),
        "title": "Commodities, Energy Shocks, Supply Chains & Asset Stress",
        "scope": "Crude oil benchmarks, crack spreads, natural gas ratios, semiconductor supply chain stress, and safe haven flight indices",
        "models": ["16", "20", "21", "24", "25.3", "25.6", "25.7", "25.8", "25.9", "25.12", "25.14", "25.17"]
    },
    "geopolitics": {
        "file": os.path.join(ROOT_DIR, "llms-formulas-geopolitics.txt"),
        "title": "Geopolitical Tension, Alliances, Strategic Chokepoints & Intelligence",
        "scope": "Bilateral dynamic polarities, Mecca Pact dynamics, maritime chokepoints, conflict heat, market impact, and evidence confidence scoring",
        "models": ["25.1", "25.15", "25.18", "25.19", "27", "27.1", "28", "28.1", "28.2", "28.3", "28.4", "28.5", "29"]
    }
}

def extract_model_blocks(lines):
    pattern = re.compile(r'^###\s+([0-9]+(?:\.[0-9]+)*)\.\s*(.*)')
    model_indices = []
    for idx, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            num = m.group(1)
            if not num.startswith("0."):
                model_indices.append((idx, num, m.group(2).strip()))
    
    blocks = {}
    for i, (start_idx, num, title) in enumerate(model_indices):
        # Scan backward for divider
        actual_start = start_idx
        if actual_start > 0 and lines[actual_start - 1].strip() == "":
            if actual_start > 1 and lines[actual_start - 2].strip() == "---":
                actual_start -= 2
        
        # End is next model's start or end of tier
        if i < len(model_indices) - 1:
            next_start = model_indices[i + 1][0]
            if next_start > 0 and lines[next_start - 1].strip() == "":
                if next_start > 1 and lines[next_start - 2].strip() == "---":
                    next_start -= 2
            end_idx = next_start
        else:
            end_idx = len(lines)
        
        raw_block = "".join(lines[actual_start:end_idx]).strip()
        blocks[num] = {
            "title": title,
            "content": raw_block
        }
    return blocks

def generate_shelf_file(shelf_key, shelf_info, blocks):
    header = f"""# Ersoy Toptaş Quantitative Models: {shelf_info['title']}
> Canonical Domain Sub-Engine | Author: Ersoy Toptaş | Version: 2026-Q4 | License: CC BY-NC-ND 4.0
> Master Router & Methodology (0.1–0.7): https://analysisreports.github.io/llms-formulas.txt
> Shelf Scope: {shelf_info['scope']}
> Zero-Fallback Rule: Missing or non-finite inputs strictly return None (null).
> Models Contained: {len(shelf_info['models'])} Domain Models ({', '.join(shelf_info['models'])})

---
"""
    body_parts = [header]
    for num in shelf_info["models"]:
        block = blocks.get(num)
        if not block:
            raise ValueError(f"Model {num} not found in extracted blocks!")
        # Ensure standard divider
        content = block["content"]
        if content.startswith("---"):
            content = content[3:].strip()
        body_parts.append(f"\n---\n\n{content}\n")
    
    full_text = "\n".join(body_parts).strip() + "\n"
    with open(shelf_info["file"], "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"[*] Compiled {os.path.basename(shelf_info['file'])} ({len(shelf_info['models'])} models, {len(full_text.encode('utf-8')) / 1024:.1f} KB)")

def main():
    if not os.path.exists(SRC_FORMULAS):
        raise FileNotFoundError(f"Source file {SRC_FORMULAS} not found.")
    
    with open(SRC_FORMULAS, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    blocks = extract_model_blocks(lines)
    print(f"[*] Extracted {len(blocks)} canonical model blocks from {os.path.basename(SRC_FORMULAS)}.")
    
    for shelf_key, shelf_info in SHELVES.items():
        generate_shelf_file(shelf_key, shelf_info, blocks)
    
    print("[SUCCESS] All 4 formula shelves generated successfully.")

if __name__ == "__main__":
    main()
