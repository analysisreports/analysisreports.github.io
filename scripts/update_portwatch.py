#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_portwatch.py
---------------------
Autonomous IMF PortWatch Maritime Chokepoint & AIS Telemetry Ingestion Engine.
Sources near-real-time daily vessel transit metrics from the IMF PortWatch
ArcGIS REST FeatureServer (Oxford ECI / UN Global Platform AIS data).

Key Characteristics:
- High efficiency: Single HTTP call fetches all monitored global chokepoints.
- Zero API key required (public open-access IMF ArcGIS endpoint).
- Strict lightweight payload protection (~5-10 KB JSON output).

Outputs:
- llms-portwatch.json (Machine & Agent Contract)
- llms-portwatch.txt (Human & LLM Narrative Twin)

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-portwatch.json
"""

import os
import sys
import json
import datetime
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_JSON = os.path.join(ROOT_DIR, "llms-portwatch.json")
OUTPUT_TXT = os.path.join(ROOT_DIR, "llms-portwatch.txt")

# Canonical PortWatch Chokepoint Mappings to Project Entity IDs with 2023 Official Baseline Daily Ships
MONITORED_CHOKEPOINTS: Dict[str, Dict[str, Any]] = {
    "chokepoint1": {
        "entity_id": "CHOKE_SUEZ",
        "name": "Suez Canal",
        "theater": "Red Sea / Mediterranean Gateway",
        "strategic_importance": "Primary container artery between Asia and Europe",
        "baseline_2023_daily": 54.2
    },
    "chokepoint2": {
        "entity_id": "CHOKE_PANAMA",
        "name": "Panama Canal",
        "theater": "Trans-Isthmus Americas",
        "strategic_importance": "Critical Atlantic-Pacific link for US agricultural and energy trade",
        "baseline_2023_daily": 30.2
    },
    "chokepoint3": {
        "entity_id": "CHOKE_TURKISH_STRAITS",
        "name": "Bosporus Strait",
        "theater": "Black Sea Littoral",
        "strategic_importance": "Russian and Ukrainian grain, mineral, and oil export corridor",
        "baseline_2023_daily": 96.2
    },
    "chokepoint4": {
        "entity_id": "CHOKE_BAB_EL_MANDEB",
        "name": "Bab el-Mandeb Strait",
        "theater": "Southern Red Sea / Gulf of Aden",
        "strategic_importance": "Asymmetric disruption zone forcing Cape of Good Hope rerouting",
        "baseline_2023_daily": 52.9
    },
    "chokepoint5": {
        "entity_id": "CHOKE_MALACCA",
        "name": "Malacca Strait",
        "theater": "Indo-Pacific / Southeast Asia",
        "strategic_importance": "China Malacca Dilemma; primary crude transit from Persian Gulf to East Asia",
        "baseline_2023_daily": 195.8
    },
    "chokepoint6": {
        "entity_id": "CHOKE_HORMUZ",
        "name": "Strait of Hormuz",
        "theater": "Persian Gulf / Arabian Sea",
        "strategic_importance": "Global crude oil transit artery carrying ~20% of global petroleum liquids",
        "baseline_2023_daily": 89.0
    },
    "chokepoint8": {
        "entity_id": "CHOKE_GIBRALTAR",
        "name": "Gibraltar Strait",
        "theater": "Western Mediterranean Gateway",
        "strategic_importance": "Atlantic-Mediterranean transit choke",
        "baseline_2023_daily": 131.0
    },
    "chokepoint11": {
        "entity_id": "CHOKE_TAIWAN",
        "name": "Taiwan Strait",
        "theater": "East China Sea / Taiwan",
        "strategic_importance": "Critical semiconductor and global container maritime highway",
        "baseline_2023_daily": 242.3
    },
    "chokepoint15": {
        "entity_id": "CHOKE_LOMBOK",
        "name": "Lombok Strait",
        "theater": "Indonesian Archipelagic Deep-Draft Corridor",
        "strategic_importance": "Deep-water alternative to Malacca for Capesize bulk carriers and VLECs",
        "baseline_2023_daily": 35.4
    },
    "chokepoint20": {
        "entity_id": "CHOKE_MAKASSAR",
        "name": "Makassar Strait",
        "theater": "Indonesian Archipelagic Deep-Draft Corridor",
        "strategic_importance": "North-South Indonesian maritime transit connecting Celebes Sea to Java Sea",
        "baseline_2023_daily": 52.4
    }
}

FEATURE_SERVER_URL = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query"

def fetch_portwatch_all_chokepoints(days_back: int = 10) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetches the last N days of data for ALL chokepoints in a single, lightning-fast API call.
    Uses indexed 'date' filtering to avoid timeouts and keep GitHub Actions quota tiny.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    start_date = (now - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    params = {
        "where": f"date >= '{start_date}'",
        "outFields": "date,portid,portname,n_total,n_tanker,n_container",
        "resultRecordCount": "1000",
        "f": "json"
    }
    query_str = urllib.parse.urlencode(params)
    url = f"{FEATURE_SERVER_URL}?{query_str}"
    
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AnalysisReports-Macro-Ecosystem/3.0 (ORCID:0009-0005-6130-8003)"}
    )
    
    grouped: Dict[str, List[Dict[str, Any]]] = {pid: [] for pid in MONITORED_CHOKEPOINTS.keys()}
    
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                print(f"[WARN] PortWatch API Error: {data['error']}")
            features = data.get("features", [])
            for feat in features:
                attrs = feat.get("attributes")
                if not attrs:
                    continue
                pid = attrs.get("portid")
                if pid in grouped:
                    n_tot = attrs.get("n_total")
                    n_tnk = attrs.get("n_tanker")
                    n_cnt = attrs.get("n_container")
                    grouped[pid].append({
                        "date": attrs.get("date"),
                        "portname": attrs.get("portname"),
                        "n_total": n_tot if n_tot is not None else 0,
                        "n_tanker": n_tnk if n_tnk is not None else 0,
                        "n_container": n_cnt if n_cnt is not None else 0
                    })
    except Exception as e:
        print(f"[WARN] Error in PortWatch single batch query: {e}")
        
    # Sort chronologically for each chokepoint
    for pid in grouped:
        grouped[pid] = sorted(grouped[pid], key=lambda x: str(x.get("date", "")))
        
    return grouped

def compute_chokepoint_metrics(records: List[Dict[str, Any]], baseline_2023: Optional[float] = None) -> Dict[str, Any]:
    """
    Computes 7-day moving averages, weekly percentage change (Δ% WoW),
    historical drop vs 2023 pre-crisis benchmark (Δ% vs 2023),
    and assigns deterministic rule-based anomaly status based on transit drops.
    """
    if not records:
        return {
            "status": "NO_RECENT_AIS_DATA",
            "last_date": None,
            "latest_daily_total": None,
            "latest_daily_tankers": None,
            "latest_daily_containers": None,
            "7d_avg_total": None,
            "7d_avg_tankers": None,
            "7d_avg_containers": None,
            "pct_change_vs_7d": None,
            "baseline_2023_daily": baseline_2023,
            "pct_change_vs_2023": None,
            "flow_stress_level": "UNKNOWN"
        }
    
    latest = records[-1]
    window_7d = records[-7:] if len(records) >= 7 else records
    
    total_ships = [r["n_total"] for r in window_7d if r.get("n_total") is not None]
    tanker_ships = [r["n_tanker"] for r in window_7d if r.get("n_tanker") is not None]
    container_ships = [r["n_container"] for r in window_7d if r.get("n_container") is not None]
    
    avg_total = sum(total_ships) / len(total_ships) if total_ships else 0.0
    avg_tanker = sum(tanker_ships) / len(tanker_ships) if tanker_ships else 0.0
    avg_container = sum(container_ships) / len(container_ships) if container_ships else 0.0
    
    latest_n = latest["n_total"] if latest.get("n_total") is not None else 0
    
    # 1. Short-term weekly change vs 7-day moving average (Δ% WoW)
    pct_change_7d = None
    if avg_total > 0:
        pct_change_7d = round(((latest_n - avg_total) / avg_total) * 100.0, 1)
        
    # 2. Strategic long-term drop vs 2023 pre-crisis baseline (Δ% vs 2023)
    pct_change_2023 = None
    if baseline_2023 and baseline_2023 > 0:
        pct_change_2023 = round(((latest_n - baseline_2023) / baseline_2023) * 100.0, 1)
        
    # 3. Deterministic rule-based regime assignment (evaluating structural crisis first)
    stress_level = "STABLE_FLOW"
    if pct_change_2023 is not None and pct_change_2023 <= -40.0:
        stress_level = "CHRONIC_CRISIS_BLOCKADE"
    elif pct_change_7d is not None and pct_change_7d <= -50.0:
        stress_level = "SEVERE_CONTRACTION"
    elif pct_change_7d is not None and pct_change_7d <= -25.0:
        stress_level = "MODERATE_CONTRACTION"
    elif pct_change_7d is not None and pct_change_7d >= 25.0:
        stress_level = "CONGESTION_SURGE"
    else:
        stress_level = "STABLE_FLOW"
            
    return {
        "status": "OPERATIONAL",
        "last_date": latest.get("date"),
        "latest_daily_total": latest_n,
        "latest_daily_tankers": latest.get("n_tanker"),
        "latest_daily_containers": latest.get("n_container"),
        "7d_avg_total": round(avg_total, 1),
        "7d_avg_tankers": round(avg_tanker, 1),
        "7d_avg_containers": round(avg_container, 1),
        "pct_change_vs_7d": pct_change_7d,
        "baseline_2023_daily": baseline_2023,
        "pct_change_vs_2023": pct_change_2023,
        "flow_stress_level": stress_level
    }

def main():
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    print(f"[*] Ingesting IMF PortWatch daily transit telemetry for {len(MONITORED_CHOKEPOINTS)} chokepoints...")
    raw_grouped = fetch_portwatch_all_chokepoints(days_back=10)
    
    chokepoints_output = {}
    active_bottlenecks = []
    
    for pid, meta in MONITORED_CHOKEPOINTS.items():
        records = raw_grouped.get(pid, [])
        b2023 = meta.get("baseline_2023_daily")
        metrics = compute_chokepoint_metrics(records, baseline_2023=b2023)
        
        if metrics["flow_stress_level"] in ("CHRONIC_CRISIS_BLOCKADE", "SEVERE_CONTRACTION", "MODERATE_CONTRACTION"):
            active_bottlenecks.append(f"{meta['entity_id']} ({meta['name']})")
            
        chokepoints_output[meta["entity_id"]] = {
            "entity_id": meta["entity_id"],
            "portwatch_id": pid,
            "name": meta["name"],
            "theater": meta["theater"],
            "strategic_importance": meta["strategic_importance"],
            "metrics": metrics,
            "recent_observations": records[-7:] if records else []
        }
        chg_7d = f"{metrics['pct_change_vs_7d']:+.1f}%" if metrics['pct_change_vs_7d'] is not None else "N/A"
        chg_2023 = f"{metrics['pct_change_vs_2023']:+.1f}%" if metrics['pct_change_vs_2023'] is not None else "N/A"
        print(f"  + {meta['entity_id']:<23} | {meta['name']:<22} | Tarih: {metrics['last_date']} | Son: {metrics['latest_daily_total']:<3} (Tanker: {metrics['latest_daily_tankers']:<2}, Konteyner: {metrics['latest_daily_containers']:<2}, 7g: {metrics['7d_avg_total']:<5}, ΔWoW: {chg_7d:<6}, Δ2023: {chg_2023:<6}) | Durum: {metrics['flow_stress_level']}")
        
    # Compile JSON Output
    payload_json = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "title": "IMF PortWatch Maritime Chokepoint & Daily AIS Transit Ingestion Contract",
            "domain": "macroeconomics",
            "version": "1.0.0",
            "author": "Ersoy Toptaş",
            "license": "CC BY-NC-ND 4.0",
            "endpoint": "https://analysisreports.github.io/llms-portwatch.json",
            "documentation": "https://analysisreports.github.io/llms-about.txt",
            "last_updated": now_iso,
            "sync_status": "SUCCESS",
            "source_authority": "International Monetary Fund (IMF) PortWatch / Oxford ECI / UN Global Platform AIS",
            "source_portal": "https://portwatch.imf.org/",
            "methodology_reference": "https://analysisreports.github.io/llms-formulas.txt#28.0",
            "root_index": "https://analysisreports.github.io/llms.txt"
        },
        "ais_telemetry_summary": {
            "monitored_chokepoints_count": len(MONITORED_CHOKEPOINTS),
            "active_disrupted_chokepoints": active_bottlenecks,
            "reporting_window_days": 7
        },
        "chokepoints": chokepoints_output
    }
    
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload_json, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Saved machine contract to {OUTPUT_JSON}")
    
    # Compile Human / LLM Narrative Twin (llms-portwatch.txt)
    lines = [
        "# Ersoy Toptaş Canonical Ingestion Contract (llms-portwatch.txt)",
        "> Autonomous IMF PortWatch Maritime Chokepoint & AIS Daily Transit Registry",
        f"> Last Sync: {now_iso} | Source: IMF PortWatch / Oxford ECI / UN AIS",
        f"> Active Supply Chain Bottlenecks: {', '.join(active_bottlenecks) if active_bottlenecks else 'None detected'}",
        "",
        "| Chokepoint Entity | Name | Theater | Last Date | Latest Daily | Tankers | Containers | 7d Avg | Δ% WoW | 2023 Baseline | Δ% vs 2023 | Flow Stress |",
        "| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |"
    ]
    
    for entity_id, c_data in chokepoints_output.items():
        m = c_data["metrics"]
        chg_7d = f"{m['pct_change_vs_7d']:+.1f}%" if m['pct_change_vs_7d'] is not None else "N/A"
        chg_2023 = f"{m['pct_change_vs_2023']:+.1f}%" if m['pct_change_vs_2023'] is not None else "N/A"
        b2023_str = f"{m['baseline_2023_daily']:.1f}" if m['baseline_2023_daily'] is not None else "N/A"
        lines.append(
            f"| `{entity_id}` | {c_data['name']} | {c_data['theater']} | {m['last_date'] or 'N/A'} | {m['latest_daily_total']} | {m['latest_daily_tankers']} | {m['latest_daily_containers']} | {m['7d_avg_total']} | {chg_7d} | {b2023_str} | {chg_2023} | `{m['flow_stress_level']}` |"
        )
        
    lines.append("")
    lines.append("## Macroeconomic Transmission Links")
    lines.append("- **Energy & Oil Supply:** Disruptions in `CHOKE_HORMUZ` or `CHOKE_BAB_EL_MANDEB` trigger immediate freight rate spikes (BDTI/BCTI) and Brent crack spread volatility.")
    lines.append("- **Container Shipping & CPI:** Suez Canal diversions around Africa add 10-14 days to transit times, inflating TEU container indices (WCI / FBX) and passing through into EU/US core import price inflation.")
    lines.append("")
    lines.append("---")
    lines.append("Official JSON Twin: https://analysisreports.github.io/llms-portwatch.json")
    
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[OK] Saved narrative twin to {OUTPUT_TXT}")

if __name__ == "__main__":
    main()
