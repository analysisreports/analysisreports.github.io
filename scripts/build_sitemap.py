#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_sitemap.py
----------------
Deterministic Sitemap Engine for AI Crawlers & Web Search Bots.

Aggregates all canonical .txt, .json, and schema endpoints on analysisreports.github.io.
Extracts real git/file timestamps for <lastmod> and assigns calibrated priority tiers:
  - 1.0 : Root home / index node
  - 0.9 : High-frequency living telemetry (SITREP, News, Root llms.txt, Master Models)
  - 0.8 : Master Formulas, Shelves, Knowledge Graphs, About/Credentials, Catalogs
  - 0.7 : Indicator dictionaries, Relationships, Tools, Data series (FRED, EIA, ECB)
  - 0.6 : Domain JSON payloads & Schemas
  - 0.5 : Architectural specs & Documentation (WORKFLOW.md, .well-known)

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/sitemap.xml
"""

import os
import glob
import datetime
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = "https://analysisreports.github.io"
SITEMAP_PATH = os.path.join(BASE_DIR, "sitemap.xml")

def get_file_lastmod_iso(file_path):
    """Retrieves file modification date in ISO 8601 (YYYY-MM-DD) format from git or filesystem."""
    rel_path = os.path.relpath(file_path, BASE_DIR).replace("\\", "/")
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", rel_path],
            cwd=BASE_DIR,
            capture_output=True,
            text=True
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    
    # Fallback to file mtime
    try:
        mtime = os.path.getmtime(file_path)
        return datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

def determine_tier_and_freq(rel_url):
    """Assigns priority and change frequency based on canonical artifact role."""
    if rel_url == "" or rel_url == "/":
        return 1.0, "daily"
    
    # Tier 1: Real-time intelligence & root manifests (0.9, hourly/daily)
    if rel_url in [
        "llms-sitrep.txt", "llms-sitrep.json",
        "llms-news.txt", "llms-news.json",
        "llms.txt", "llms-full.txt",
        "llms-models.txt", "llms-models.json"
    ]:
        return 0.9, "hourly" if "sitrep" in rel_url or "news" in rel_url else "daily"
        
    # Tier 2: Analytical Shelves, Knowledge Graphs, Formulas, Identity (0.8)
    if any(k in rel_url for k in [
        "formulas", "graph", "llms-about", "ai-catalog", "llms-models-bridge"
    ]):
        return 0.8, "daily"
        
    # Tier 3: Relationship matrix, Tools, Provider series, Portwatch, Indicators (0.7)
    if any(k in rel_url for k in [
        "relationships", "tools", "series", "indicators", "portwatch", "nasa-firms", "entities"
    ]):
        return 0.7, "daily"
        
    # Tier 4: Schemas & Domain JSON payloads (0.6)
    if "schema" in rel_url or rel_url.endswith(".schema.json") or rel_url in [
        "economy.json", "country.json", "political.json", "concept.json", "glossary.json", "editorial.json", "strategic-macro.json"
    ]:
        return 0.6, "weekly"
        
    # Tier 5: Static docs & well-known (0.5)
    return 0.5, "weekly"

def collect_endpoints():
    endpoints = []
    today_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    
    # 1. Root / Home Node
    endpoints.append(("", today_iso, 1.0, "daily"))
    
    # 2. llms*.txt and llms*.json
    for path in glob.glob(os.path.join(BASE_DIR, "llms*.*")):
        fname = os.path.basename(path)
        if fname.endswith((".txt", ".json")):
            lastmod = get_file_lastmod_iso(path)
            priority, freq = determine_tier_and_freq(fname)
            endpoints.append((fname, lastmod, priority, freq))
            
    # 3. Root JSON payloads & discovery
    for extra in ["ai-catalog.json", "economy.json", "country.json", "political.json", "strategic-macro.json"]:
        path = os.path.join(BASE_DIR, extra)
        if os.path.exists(path):
            lastmod = get_file_lastmod_iso(path)
            priority, freq = determine_tier_and_freq(extra)
            endpoints.append((extra, lastmod, priority, freq))
            
    # 4. Schemas
    for path in glob.glob(os.path.join(BASE_DIR, "schemas", "*.schema.json")):
        rel = os.path.relpath(path, BASE_DIR).replace("\\", "/")
        lastmod = get_file_lastmod_iso(path)
        priority, freq = determine_tier_and_freq(rel)
        endpoints.append((rel, lastmod, priority, freq))
        
    # 5. Well-known
    for path in glob.glob(os.path.join(BASE_DIR, ".well-known", "*")):
        rel = os.path.relpath(path, BASE_DIR).replace("\\", "/")
        lastmod = get_file_lastmod_iso(path)
        priority, freq = determine_tier_and_freq(rel)
        endpoints.append((rel, lastmod, priority, freq))
        
    # 6. WORKFLOW.md & README.md
    for doc in ["WORKFLOW.md", "README.md"]:
        path = os.path.join(BASE_DIR, doc)
        if os.path.exists(path):
            lastmod = get_file_lastmod_iso(path)
            priority, freq = determine_tier_and_freq(doc)
            endpoints.append((doc, lastmod, priority, freq))

    # Deduplicate while preserving order
    seen = set()
    unique_endpoints = []
    for rel_url, lastmod, priority, freq in endpoints:
        clean_url = rel_url.lstrip("/")
        if clean_url not in seen:
            seen.add(clean_url)
            unique_endpoints.append((clean_url, lastmod, priority, freq))
            
    return unique_endpoints

def build_sitemap():
    endpoints = collect_endpoints()
    
    # Sort endpoints: by priority descending, then by URL
    endpoints.sort(key=lambda x: (-x[2], x[0]))
    
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        '  <!-- Ersoy Toptaş Quantitative Macro Research & Machine-Readable AI Knowledge Base -->',
        f'  <!-- Total Canonical Endpoints: {len(endpoints)} | Generated: {datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} -->'
    ]
    
    for rel_url, lastmod, priority, freq in endpoints:
        full_url = f"{BASE_URL}/{rel_url}" if rel_url else f"{BASE_URL}/"
        lines.append("  <url>")
        lines.append(f"    <loc>{full_url}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <changefreq>{freq}</changefreq>")
        lines.append(f"    <priority>{priority:.1f}</priority>")
        lines.append("  </url>")
        
    lines.append("</urlset>\n")
    
    content = "\n".join(lines)
    with open(SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"[SUCCESS] Compiled {SITEMAP_PATH} with {len(endpoints)} canonical endpoints.")

if __name__ == "__main__":
    build_sitemap()
