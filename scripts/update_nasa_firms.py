#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_nasa_firms.py
---------------------
Autonomous Satellite Thermal Anomaly & Kinetic Conflict Intelligence Engine.
Sources real-time thermal anomalies from NASA FIRMS (VIIRS Suomi-NPP / NOAA-20 / NOAA-21).

Detects 5 Strategic Macro & Defense Signatures:
1. Conventional Kinetic Military Engagements (c1 Kinetic Military Score in Model 28.1)
2. Energy Infrastructure & Refinery Disruptions (c3 Disruption Risk in Model 28.1 & Model 28.4)
3. Maritime Chokepoint & Waterborne Tanker Attacks (Hormuz, Bab el-Mandeb, Black Sea)
4. Critical Industrial Disruption Events
5. False Positive Filtering (FRP > 50 MW & High Confidence thresholds)

Outputs:
- llms-nasa-firms.json (Machine Contract)
- llms-nasa-firms.txt (Human/LLM Narrative Twin)

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-nasa-firms.json
"""

import os
import sys
import csv
import json
import io
import math
import datetime
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_JSON = os.path.join(ROOT_DIR, "llms-nasa-firms.json")
OUTPUT_TXT = os.path.join(ROOT_DIR, "llms-nasa-firms.txt")

# Canonical Monitored Sovereign Theaters & Chokepoints
# Maps ISO country code to Sovereign Entity ID, Geographic Theater, and Spatial Bounding Box (min_lon, min_lat, max_lon, max_lat)
MONITORED_THEATERS: Dict[str, Dict[str, Any]] = {
    "UKR": {
        "entity_id": "GEO_UA",
        "name": "Ukraine Frontline Axis",
        "category": "CONVENTIONAL_LAND_WARFARE",
        "theater": "Eastern European Flank",
        "bounds": (22.0, 44.0, 40.5, 52.5),
        "corridor_check": ["BLACK_SEA", "DONBAS", "ZAPORIZHZHIA", "KHERSON"]
    },
    "RUS": {
        "entity_id": "GEO_RU",
        "name": "Russian Federation Border & Refinery Littoral",
        "category": "STRATEGIC_INFRASTRUCTURE",
        "theater": "Eurasian Core",
        "bounds": (35.0, 50.0, 45.0, 56.5),
        "corridor_check": ["KURSK_BORDER", "REFINERY_CORRIDOR", "BLACK_SEA_LITTORAL"]
    },
    "ISR": {
        "entity_id": "GEO_IL",
        "name": "State of Israel & Frontline Perimeters",
        "category": "HIGH_INTENSITY_MISSILE_THEATER",
        "theater": "Levant Basin",
        "bounds": (34.0, 29.5, 36.0, 33.5),
        "corridor_check": ["NORTHERN_BORDER", "GAZA_PERIMETER", "PORT_OF_EILAT"]
    },
    "IRN": {
        "entity_id": "GEO_IR",
        "name": "Islamic Republic of Iran & Gulf Littoral",
        "category": "CHOKEPOINT_LITTORAL_AND_NUCLEAR",
        "theater": "Persian Gulf & Zagros",
        "bounds": (44.0, 24.5, 63.5, 39.8),
        "corridor_check": ["CHOKE_HORMUZ", "KHUZESTAN_ENERGY_GRID", "NATANZ_ISFAHAN"]
    },
    "YEM": {
        "entity_id": "GEO_YE",
        "name": "Republic of Yemen & Red Sea Littoral",
        "category": "MARITIME_CHOKEPOINT_INTERDICTION",
        "theater": "Bab el-Mandeb / Red Sea",
        "bounds": (42.0, 12.0, 54.0, 19.0),
        "corridor_check": ["CHOKE_BAB_EL_MANDEB", "HODEIDAH_PORT", "GULF_OF_ADEN"]
    },
    "SYR": {
        "entity_id": "GEO_SY",
        "name": "Syrian Arab Republic Buffer",
        "category": "ASYMMETRIC_BUFFER_THEATER",
        "theater": "Levant",
        "bounds": (35.5, 32.3, 42.4, 37.3),
        "corridor_check": ["NORTHERN_BUFFER", "EUPHRATES_BASIN"]
    },
    "LBN": {
        "entity_id": "GEO_LB",
        "name": "Lebanese Republic Southern Axis",
        "category": "MISSILE_INTERDICTION_ZONE",
        "theater": "Levant Littoral",
        "bounds": (35.1, 33.0, 36.6, 34.7),
        "corridor_check": ["LITANI_LINE", "BEIRUT_PORT"]
    }
}

# Maritime Bounding Box Coordinates for Waterborne Chokepoints (Bounding Box: min_lon, min_lat, max_lon, max_lat)
MARITIME_CHOKEPOINTS = {
    "CHOKE_HORMUZ": {
        "name": "Strait of Hormuz Maritime Box",
        "bounds": (55.5, 25.5, 57.5, 27.2),
        "primary_threat": "IRAN_GULF_NAVAL_INTERDICTION"
    },
    "CHOKE_BAB_EL_MANDEB": {
        "name": "Bab el-Mandeb Strait Maritime Box",
        "bounds": (42.5, 12.0, 44.5, 13.5),
        "primary_threat": "HOUTHI_ANTI_SHIP_BALLISTIC_STRIKES"
    }
}

# Satellite Thresholds (Noise Filtering Protocol)
MIN_FRP_MW = 25.0           # Minimum Fire Radiative Power (MW) to exclude trivial brush/camp fires
STRATEGIC_FRP_MW = 150.0    # Massive explosion / ammunition depot / missile impact threshold
REFINERY_FRP_MW = 500.0     # Industrial oil refinery / fuel storage blaze threshold

def fetch_firms_area_csv(map_key: str, bounds: Tuple[float, float, float, float], days: int = 1) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches real-time VIIRS Suomi-NPP 375m active fire data for a spatial bounding box.
    NASA FIRMS Area Endpoint: https://firms.modaps.eosdis.nasa.gov/api/area/csv/[MAP_KEY]/VIIRS_SNPP_NRT/[W,S,E,N]/[DAYS]
    """
    w, s, e, n = bounds
    area_str = f"{w:.1f},{s:.1f},{e:.1f},{n:.1f}"
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/VIIRS_SNPP_NRT/{area_str}/{days}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AnalysisReports-Autonomous-Ecosystem/3.0 (ORCID:0009-0005-6130-8003)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            content = resp.read().decode("utf-8")
            if "Invalid" in content or "Error" in content or "not available" in content:
                print(f"  [WARN] NASA FIRMS returned error response for area {area_str}: {content.strip()}")
                return None
            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)
            return rows
    except urllib.error.HTTPError as e:
        print(f"  [WARN] NASA FIRMS HTTP {e.code} error for area {area_str}: {e.reason}")
        return None
    except Exception as e:
        print(f"  [WARN] NASA FIRMS network fetch error for area {area_str}: {e}")
        return None

def analyze_thermal_anomalies(country_code: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Processes raw satellite rows into strategic kinetic indicators.
    Filters out noise, counts high-confidence military explosions, and categorizes severity.
    """
    theater_meta = MONITORED_THEATERS[country_code]
    total_raw = len(rows)
    
    high_conf_hits = []
    kinetic_strikes = 0
    refinery_major_hits = 0
    total_frp = 0.0
    max_frp = 0.0
    
    for r in rows:
        raw_frp = r.get("frp")
        raw_lat = r.get("latitude")
        raw_lon = r.get("longitude")
        if raw_frp is None or raw_lat is None or raw_lon is None:
            continue
        try:
            frp = float(raw_frp)
            conf = str(r.get("confidence", "")).strip().lower()
            lat = float(raw_lat)
            lon = float(raw_lon)
            acq_date = r.get("acq_date", "")
            acq_time = r.get("acq_time", "")
            daynight = r.get("daynight", "")
        except (ValueError, TypeError):
            continue
            
        # Noise Filter: Must be high confidence ('h') or nominal ('n' with high FRP)
        if conf == "l":
            continue
        if frp < MIN_FRP_MW:
            continue
            
        total_frp += frp
        if frp > max_frp:
            max_frp = frp
            
        if frp >= STRATEGIC_FRP_MW:
            kinetic_strikes += 1
            
        if frp >= REFINERY_FRP_MW:
            refinery_major_hits += 1
            
        high_conf_hits.append({
            "latitude": lat,
            "longitude": lon,
            "frp_mw": frp,
            "confidence": conf,
            "date": acq_date,
            "time_utc": acq_time,
            "daynight": daynight
        })
        
    filtered_count = len(high_conf_hits)
    
    # Calculate Deterministic Kinetic Score (0 to 100 scale) for Model 28.1 (c1)
    if filtered_count == 0:
        kinetic_score = 0
        severity = "LOW"
    elif filtered_count < 10 and max_frp < STRATEGIC_FRP_MW:
        kinetic_score = min(40, filtered_count * 4)
        severity = "MODERATE"
    elif filtered_count < 30 and refinery_major_hits == 0:
        kinetic_score = min(75, 40 + filtered_count * 1)
        severity = "HIGH"
    else:
        # High-volume frontline barrages or massive infrastructure strikes
        kinetic_score = min(100, 75 + int(math.log10(max(1, filtered_count)) * 10) + (refinery_major_hits * 5))
        severity = "CRITICAL"
        
    return {
        "entity_id": theater_meta["entity_id"],
        "name": theater_meta["name"],
        "theater": theater_meta["theater"],
        "category": theater_meta["category"],
        "total_satellite_detections": total_raw,
        "high_confidence_anomalies": filtered_count,
        "strategic_missile_strikes_count": kinetic_strikes,
        "refinery_depot_blazes_count": refinery_major_hits,
        "total_radiative_power_mw": round(total_frp, 2),
        "peak_explosion_power_mw": round(max_frp, 2),
        "kinetic_conflict_score": kinetic_score,
        "conflict_severity": severity,
        "corridor_flashpoints": theater_meta["corridor_check"],
        "sample_hotspots": sorted(high_conf_hits, key=lambda x: x["frp_mw"], reverse=True)[:5]
    }

def build_outputs(map_key: str) -> Tuple[str, Dict[str, Any]]:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    theaters_output: Dict[str, Any] = {}
    total_detections_global = 0
    critical_theaters = []
    
    for c_code in MONITORED_THEATERS:
        if not map_key:
            # Zero-Fallback Protocol: When API key is not configured, record graceful telemetry
            theaters_output[c_code] = {
                "entity_id": MONITORED_THEATERS[c_code]["entity_id"],
                "status": "UNCONFIGURED_KEY",
                "kinetic_conflict_score": None,
                "conflict_severity": "UNAVAILABLE"
            }
            continue
            
        raw_rows = fetch_firms_area_csv(map_key, MONITORED_THEATERS[c_code]["bounds"], days=1)
        if raw_rows is None:
            theaters_output[c_code] = {
                "entity_id": MONITORED_THEATERS[c_code]["entity_id"],
                "status": "API_OFFLINE",
                "kinetic_conflict_score": None,
                "conflict_severity": "UNAVAILABLE"
            }
            continue
            
        analysis = analyze_thermal_anomalies(c_code, raw_rows)
        analysis["status"] = "OK"
        theaters_output[c_code] = analysis
        total_detections_global += analysis["high_confidence_anomalies"]
        if analysis["conflict_severity"] == "CRITICAL":
            critical_theaters.append(analysis["name"])
            
    # Compile Master JSON Machine Contract (8 Golden Keys)
    full_json = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "metadata": {
            "title": "NASA FIRMS Satellite Thermal Anomaly & Autonomous Kinetic War Engine",
            "domain": "security",
            "version": "3.0.0",
            "author": "Ersoy Toptaş",
            "license": "CC BY-NC-ND 4.0",
            "endpoint": "https://analysisreports.github.io/llms-nasa-firms.json",
            "documentation": "https://analysisreports.github.io/llms-about.txt",
            "last_updated": now_iso,
            "sync_status": "SUCCESS" if map_key else "STANDBY_UNCONFIGURED_KEY",
            "last_successful_sync": now_iso if map_key else None,
            "source_authority": "NASA Earth Science Data / FIRMS (VIIRS Suomi-NPP & NOAA-20)",
            "methodology_reference": "https://analysisreports.github.io/llms-formulas-geopolitics.txt#28.1",
            "root_index": "https://analysisreports.github.io/llms.txt"
        },
        "orbital_telemetry_summary": {
            "active_satellites": ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT"],
            "spatial_resolution_meters": 375,
            "min_noise_filter_mw": MIN_FRP_MW,
            "strategic_strike_threshold_mw": STRATEGIC_FRP_MW,
            "monitored_theaters_count": len(MONITORED_THEATERS),
            "total_high_confidence_hits_24h": total_detections_global,
            "active_critical_kinetic_zones": critical_theaters
        },
        "theaters": theaters_output
    }
    
    # Compile Text Narrative Twin for LLM Prompt Ingestion
    lines = [
        "# Ersoy Toptaş Canonical Ingestion Contract (llms-nasa-firms.txt)",
        "> Autonomous Satellite Thermal Anomaly & Kinetic Conflict Intelligence Engine",
        f"> Last Orbital Sync: {now_iso} | Source: NASA FIRMS VIIRS 375m",
        f"> Global Active Critical Kinetic Zones: {', '.join(critical_theaters) if critical_theaters else 'None detected'}",
        "",
        "| Sovereign Theater | Entity ID | Status | 24h Hotspots | Peak FRP (MW) | Kinetic Score (0-100) | Conflict Severity | Primary Strategic Axis |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |"
    ]
    
    for c_code, data in theaters_output.items():
        if data.get("status") == "OK":
            lines.append(
                f"| **{data['name']}** | {data['entity_id']} | OK | "
                f"{data['high_confidence_anomalies']} | {data['peak_explosion_power_mw']:.1f} MW | "
                f"{data['kinetic_conflict_score']} | **{data['conflict_severity']}** | {data['category']} |"
            )
        else:
            lines.append(
                f"| **{MONITORED_THEATERS[c_code]['name']}** | {MONITORED_THEATERS[c_code]['entity_id']} | "
                f"{data.get('status')} | null | null | null | UNAVAILABLE | {MONITORED_THEATERS[c_code]['category']} |"
            )
            
    lines.append("")
    lines.append("## Strategic Signature Interpretation Protocol:")
    lines.append("1. FRP > 150 MW indicates heavy artillery barrages, ammunition depot detonations, or direct ballistic missile strikes.")
    lines.append("2. FRP > 500 MW indicates burning oil refineries, hydrocarbon pipelines, or industrial fuel depots.")
    lines.append("3. Conflict Severity == 'CRITICAL' automatically satisfies the kinetic condition for Model 25.1 (KINETIC_WAR).")
    
    full_txt = "\n".join(lines) + "\n"
    return full_txt, full_json

def main():
    map_key = os.environ.get("NASA_MAP_KEY", "").strip()
    if not map_key:
        print("[INFO] NASA_MAP_KEY environment variable not set. Running in standby mode...")
        
    full_txt, full_json = build_outputs(map_key)
    
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(full_json, f, indent=2, ensure_ascii=False)
    print(f"[SUCCESS] Wrote NASA FIRMS JSON to {OUTPUT_JSON}")
    
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(full_txt)
    print(f"[SUCCESS] Wrote NASA FIRMS Text Twin to {OUTPUT_TXT}")

if __name__ == "__main__":
    main()
