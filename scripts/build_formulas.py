#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_formulas.py
-----------------
Master Quantitative Formulas Compiler & Federated Router Engine.

Architecture: Bottom-Up Compilation (Shelves -> Master Router SSOT)
Tıpkı build_graph.py gibi:
1. 4 Uzmanlık Rafını (SSOT) okur:
   - llms-formulas-rates-liquidity.txt
   - llms-formulas-macro-labor.txt
   - llms-formulas-commodities-shock.txt
   - llms-formulas-geopolitics.txt
2. Bölüm 0.1–0.7 Genel Metodoloji çekirdeğini korur.
3. Master Router Tablosu ve 62 Modelin Fihristini derler.
4. llms-formulas.txt dosyasını hafif Master Router & Fihrist (~28 KB) olarak üretir.

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-formulas.txt
"""

import os
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_FILE = os.path.join(ROOT_DIR, "llms-formulas.txt")

SHELVES = [
    {
        "id": "rates-liquidity",
        "file": os.path.join(ROOT_DIR, "llms-formulas-rates-liquidity.txt"),
        "filename": "llms-formulas-rates-liquidity.txt",
        "title": "Rates, Yield Curves, Liquidity & Monetary Transmission",
        "scope": "Central bank policy stance, yield curves, repo friction, Fed/ECB liquidity, credit spreads, carry trades",
        "tier": "TIER 1 & 2: RATES, LIQUIDITY & POLICY"
    },
    {
        "id": "macro-labor",
        "file": os.path.join(ROOT_DIR, "llms-formulas-macro-labor.txt"),
        "filename": "llms-formulas-macro-labor.txt",
        "title": "Macroeconomic Fundamentals, Labor Dynamics, Valuation & Cycles",
        "scope": "Inflation persistence, labor momentum, housing bubble, consumption collapse, equity valuation, release countdown",
        "tier": "TIER 1, 2 & 4: MACRO, LABOR & VALUATION"
    },
    {
        "id": "commodities-shock",
        "file": os.path.join(ROOT_DIR, "llms-formulas-commodities-shock.txt"),
        "filename": "llms-formulas-commodities-shock.txt",
        "title": "Commodities, Energy Shocks, Supply Chains & Asset Stress",
        "scope": "Crude benchmarks, 3:2:1 crack spread, natgas disconnect, chip stress, supply chain logistics, safe haven flight",
        "tier": "TIER 2: COMMODITIES, ENERGY & SUPPLY CHAIN"
    },
    {
        "id": "geopolitics",
        "file": os.path.join(ROOT_DIR, "llms-formulas-geopolitics.txt"),
        "filename": "llms-formulas-geopolitics.txt",
        "title": "Geopolitical Tension, Alliances, Strategic Chokepoints & Intelligence",
        "scope": "Bilateral dynamic polarities, Mecca Pact dynamics, maritime chokepoints, conflict heat, market impact, intelligence confidence",
        "tier": "TIER 3: GEOPOLITICAL DYNAMICS, ALLIANCES & RISK"
    }
]

def extract_models_from_shelf(shelf):
    with open(shelf["file"], "r", encoding="utf-8") as f:
        content = f.read()

    # Pattern to match:
    # ### <num>. <title>
    # followed by optional fields: Purpose, Data Series Keys, Target
    pattern = re.compile(
        r'(?m)^###\s+([0-9]+(?:\.[0-9]+)*)\.\s*(.*?)\n'
        r'(?:-\s*Purpose:\s*(.*?)\n)?'
        r'(?:-\s*Target:\s*(.*?)\n)?'
    )

    models = []
    for m in pattern.finditer(content):
        num = m.group(1)
        title = m.group(2).strip()
        purpose = m.group(3).strip() if m.group(3) else ""
        target = m.group(4).strip() if m.group(4) else ""
        models.append({
            "number": num,
            "title": title,
            "purpose": purpose,
            "target": target,
            "shelf": shelf
        })
    return models

def build_master_router():
    # 1. Read existing Section 0.1-0.7 from llms-formulas.txt (or scratch backup if already truncated)
    sec0_content = ""
    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        current_master = f.read()

    if "## 🏛️ TIER 1" in current_master:
        tier1_idx = current_master.find("## 🏛️ TIER 1")
        sec0_content = current_master[:tier1_idx].strip()
    else:
        backup_path = os.path.join(ROOT_DIR, "scratch", "sec0_backup.txt")
        if os.path.exists(backup_path):
            with open(backup_path, "r", encoding="utf-8") as bf:
                sec0_content = bf.read().strip()
        else:
            raise RuntimeError("Cannot locate Section 0.1-0.7 methodology core!")

    # 2. Extract models from all 4 shelves
    all_models = []
    shelf_stats = {}
    for shelf in SHELVES:
        m_list = extract_models_from_shelf(shelf)
        shelf_stats[shelf["id"]] = len(m_list)
        all_models.extend(m_list)

    total_models = len(all_models)
    print(f"[*] Extracted {total_models} models across 4 domain shelves: {shelf_stats}")

    # 3. Sort models naturally (numerical order)
    def model_sort_key(m):
        parts = m["number"].split(".")
        return [int(p) for p in parts]

    all_models.sort(key=model_sort_key)

    # 4. Generate Master Router Header & Guidance
    router_table = [
        "## 🗂️ MASTER ROUTING DIRECTIVE & FEDERATED SHELF MAP",
        "> HIGH-PRIORITY LLM REASONING DIRECTIVE: Fetch domain-specific formula shelves directly.",
        "> Do NOT traverse deprecated monolithic representations. Query target shelf endpoints below.",
        "",
        "| Shelf Domain | Target Endpoint | Scope | Models | Size |",
        "| :--- | :--- | :--- | :---: | :---: |"
    ]

    for shelf in SHELVES:
        f_size_kb = os.path.getsize(shelf["file"]) / 1024.0
        m_count = shelf_stats[shelf["id"]]
        endpoint_url = f"https://analysisreports.github.io/{shelf['filename']}"
        router_table.append(
            f"| **{shelf['title']}** | [`{shelf['filename']}`]({endpoint_url}) | {shelf['scope']} | **{m_count}** | ~{f_size_kb:.1f} KB |"
        )

    router_table_str = "\n".join(router_table)

    # 5. Generate Compact Index Entries for each Model
    index_entries = [
        "---",
        "",
        "## 🧭 CANONICAL MODEL INDEX (ROUTER & ENDPOINT CROSS-REFERENCE)",
        "> All model implementations, mathematical formulas, and Python executable logic are hosted in the domain shelves.",
        "> Use the exact anchors below to navigate to authoritative definitions.",
        ""
    ]

    for m in all_models:
        num = m["number"]
        title = m["title"]
        shelf = m["shelf"]
        endpoint = f"https://analysisreports.github.io/{shelf['filename']}#{num}"
        purpose_line = f"  - Purpose: {m['purpose']}" if m['purpose'] else ""
        target_line = f"\n  - Target: {m['target']}" if m['target'] else ""
        
        entry = (
            f"### {num}. {title}\n"
            f"- Domain Shelf: [`{shelf['filename']}#{num}`]({endpoint})\n"
            f"- Shelf Category: {shelf['title']}"
        )
        if purpose_line:
            entry += f"\n{purpose_line}"
        if target_line:
            entry += f"{target_line}"
        
        index_entries.append(entry)
        index_entries.append("")

    full_master_text = (
        sec0_content + "\n\n---\n\n" +
        router_table_str + "\n\n" +
        "\n".join(index_entries)
    ).strip() + "\n"

    # Write compiled master file
    with open(MASTER_FILE, "w", encoding="utf-8") as f:
        f.write(full_master_text)

    new_size_kb = len(full_master_text.encode("utf-8")) / 1024.0
    print(f"[SUCCESS] Compiled {os.path.basename(MASTER_FILE)} into Master Router ({total_models} models, {new_size_kb:.1f} KB)")

if __name__ == "__main__":
    build_master_router()
