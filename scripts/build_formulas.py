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
2. Rafların Enterprise Metadata başlıklarını standartlaştırır / zenginleştirir.
3. Bölüm 0.1–0.7 Genel Metodoloji çekirdeğini korur.
4. Master Router Tablosu ve 62 Modelin Fihristini derler.
5. llms-formulas.txt dosyasını hafif Master Router & Fihrist (~53 KB) olarak üretir.

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
        "scope": "Central bank policy stances, yield curve slopes, repo liquidity friction, credit spreads, carry trades, and committee dispersion.",
        "tier": "TIER 1 & 2: RATES, LIQUIDITY & POLICY"
    },
    {
        "id": "macro-labor",
        "file": os.path.join(ROOT_DIR, "llms-formulas-macro-labor.txt"),
        "filename": "llms-formulas-macro-labor.txt",
        "title": "Macroeconomic Fundamentals, Labor Dynamics, Valuation & Cycles",
        "scope": "Inflation persistence, labor market momentum, housing bubble risks, consumption collapse, equity valuation, and release countdowns.",
        "tier": "TIER 1, 2 & 4: MACRO, LABOR & VALUATION"
    },
    {
        "id": "commodities-shock",
        "file": os.path.join(ROOT_DIR, "llms-formulas-commodities-shock.txt"),
        "filename": "llms-formulas-commodities-shock.txt",
        "title": "Commodities, Energy Shocks, Supply Chains & Asset Stress",
        "scope": "Crude benchmarks, 3:2:1 crack spread, natgas disconnect, chip stress, supply chain logistics, and safe haven flight.",
        "tier": "TIER 2: COMMODITIES, ENERGY & SUPPLY CHAIN"
    },
    {
        "id": "geopolitics",
        "file": os.path.join(ROOT_DIR, "llms-formulas-geopolitics.txt"),
        "filename": "llms-formulas-geopolitics.txt",
        "title": "Geopolitical Tension, Alliances, Strategic Chokepoints & Intelligence",
        "scope": "Bilateral dynamic polarities, Mecca Pact dynamics, maritime chokepoints, conflict heat, market impact, and intelligence confidence.",
        "tier": "TIER 3: GEOPOLITICAL DYNAMICS, ALLIANCES & RISK"
    }
]

def generate_shelf_header(shelf, model_numbers):
    models_str = ", ".join(model_numbers)
    return f"""# Ersoy Toptaş Quantitative Models: {shelf['title']} ({shelf['filename']})
> Canonical Domain Sub-Engine for AI Agents & LLM Quantitative Reasoning.
> Author: Ersoy Toptaş | Version: 2026-Q4 | License: CC BY-NC-ND 4.0 | Motto: Think simple, act big
> Endpoint: https://analysisreports.github.io/{shelf['filename']}
> Master Router & Methodology: https://analysisreports.github.io/llms-formulas.txt
> Root Index: https://analysisreports.github.io/llms.txt
> Master Directory: https://analysisreports.github.io/llms-full.txt
> Indicators Dictionary: https://analysisreports.github.io/llms-indicators.txt
> Dynamic Relationships: https://analysisreports.github.io/llms-relationships.txt
> Knowledge Graph: https://analysisreports.github.io/llms-graph.json
> Author Profile: https://analysisreports.github.io/llms-about.txt
> Editorial Frontends: https://www.ersoytoptas.tr/ | https://en.ersoytoptas.tr/
> Shelf Scope: {shelf['scope']}
> Zero-Fallback Directive: Strict deterministic execution. Missing or non-finite inputs strictly return None (null).
> Models Contained: {len(model_numbers)} Domain Models ({models_str})

---
"""

def extract_models_and_body_from_shelf(shelf):
    with open(shelf["file"], "r", encoding="utf-8") as f:
        content = f.read()

    # Locate first model section
    first_m = re.search(r'(?m)^###\s+[0-9]', content)
    body = content[first_m.start():] if first_m else ""

    # Sanitize legacy monolithic TIER headers and trailing dividers
    body = re.sub(r'(?m)^##\s+.*TIER\s+[1-4]:.*(?:\n|$)', '', body)
    body = re.sub(r'(?m)\n---\s*\n(?=\s*---)', '', body)  # Clean consecutive dividers
    body = re.sub(r'\n---\s*$', '', body.strip())          # Clean trailing divider

    pattern = re.compile(
        r'(?m)^###\s+([0-9]+(?:\.[0-9]+)*)\.\s*(.*?)\n'
        r'(?:-\s*Purpose:\s*(.*?)\n)?'
        r'(?:-\s*Target:\s*(.*?)\n)?'
    )

    models = []
    for m in pattern.finditer(body):
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
    return models, body

def update_shelf_headers(shelf, models, body):
    model_numbers = [m["number"] for m in models]
    new_header = generate_shelf_header(shelf, model_numbers)
    new_content = new_header + "\n" + body.strip() + "\n"
    with open(shelf["file"], "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"[*] Updated enterprise header for {shelf['filename']} ({len(models)} models)")

def build_master_router():
    sec0_content = ""
    with open(MASTER_FILE, "r", encoding="utf-8") as f:
        current_master = f.read()

    if "## 🗂️ MASTER ROUTING DIRECTIVE" in current_master:
        router_idx = current_master.find("## 🗂️ MASTER ROUTING DIRECTIVE")
        # Remove trailing divider
        sec0_content = current_master[:router_idx].strip()
        if sec0_content.endswith("---"):
            sec0_content = sec0_content[:-3].strip()
    elif "## 🏛️ TIER 1" in current_master:
        tier1_idx = current_master.find("## 🏛️ TIER 1")
        sec0_content = current_master[:tier1_idx].strip()
    else:
        raise RuntimeError("Cannot locate Section 0.1-0.7 methodology core!")

    all_models = []
    shelf_stats = {}
    for shelf in SHELVES:
        m_list, body = extract_models_and_body_from_shelf(shelf)
        shelf_stats[shelf["id"]] = len(m_list)
        all_models.extend(m_list)
        update_shelf_headers(shelf, m_list, body)

    total_models = len(all_models)
    print(f"[*] Processed {total_models} models across 4 domain shelves: {shelf_stats}")

    def model_sort_key(m):
        parts = m["number"].split(".")
        return [int(p) for p in parts]

    all_models.sort(key=model_sort_key)

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

    with open(MASTER_FILE, "w", encoding="utf-8") as f:
        f.write(full_master_text)

    new_size_kb = len(full_master_text.encode("utf-8")) / 1024.0
    print(f"[SUCCESS] Compiled {os.path.basename(MASTER_FILE)} into Master Router ({total_models} models, {new_size_kb:.1f} KB)")

if __name__ == "__main__":
    build_master_router()
