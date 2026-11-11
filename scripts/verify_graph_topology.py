#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_graph_topology.py
-------------------------
Knowledge Graph Topological Health, Orphan Node, Edge Polarity & Encoding Auditor.

Audits 'llms-graph.json':
1. Character Encoding & Mojibake Guard: Zero UTF-8 decoding anomalies (e.g. ÅŸ, Ã¼, Ä±).
2. Node Uniqueness: Zero duplicate node IDs.
3. Edge Target Integrity: Zero broken edges (source & target must exist in node registry).
4. Master SSOT Polarity Invariance: Cross-checks edge 'p_baseline' against 'llms-country-relationships.txt'.
5. Orphan Node Auditing: Identifies isolated nodes (degree == 0).

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-graph.json
"""

import os
import re
import sys
import json
from typing import Dict, List, Set, Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GRAPH_PATH = os.path.join(ROOT_DIR, "llms-graph.json")
COUNTRY_TXT = os.path.join(ROOT_DIR, "llms-country-relationships.txt")

MOJIBAKE_PATTERNS = ["ÅŸ", "Ã¼", "BoÄŸaz", "Ã§", "Ä±", "Ã¶", "Ã", "â€", "Åž", "Ä°", "Ã‡", "Ã–", "Ãœ"]

def audit_encoding(content: str) -> List[str]:
    errors = []
    found = [p for p in MOJIBAKE_PATTERNS if p in content]
    if found:
        errors.append(f"CHARACTER ENCODING CORRUPTION (Mojibake) detected: {found}")
    return errors

def audit_polarity_synchronization(graph_edges: List[Dict[str, Any]]) -> Tuple[List[str], int]:
    errors = []
    synced_matches = 0

    if not os.path.exists(COUNTRY_TXT):
        return ["Master country relationships file not found for polarity sync check."], 0

    with open(COUNTRY_TXT, "r", encoding="utf-8") as f:
        c_txt = f.read()

    # Extract master polarities from SSOT
    country_polarities = {}
    dyad_matches = re.findall(
        r"Dyad ID:\s*REL_GEO_([A-Z0-9_]+)_GEO_([A-Z0-9_]+).*?Bilateral Stance:\s*([+\-0-9\.]+)",
        c_txt,
        re.S
    )
    for a1, a2, score in dyad_matches:
        val = float(score)
        country_polarities[(f"ACTOR_{a1}", f"ACTOR_{a2}")] = val
        country_polarities[(f"ACTOR_{a2}", f"ACTOR_{a1}")] = val
        country_polarities[(f"GEO_{a1}", f"GEO_{a2}")] = val
        country_polarities[(f"GEO_{a2}", f"GEO_{a1}")] = val

    for idx, edge in enumerate(graph_edges):
        s = edge.get("source")
        t = edge.get("target")
        p_base = edge.get("p_baseline")

        if p_base is not None and (s, t) in country_polarities:
            expected = country_polarities[(s, t)]
            if abs(p_base - expected) > 0.001:
                errors.append(
                    f"GRAPH POLARITY DESYNC (Edge #{idx} {s} -> {t}): "
                    f"Graph has {p_base:+.2f} but Master SSOT has {expected:+.2f}."
                )
            else:
                synced_matches += 1

    return errors, synced_matches

def main():
    print("=" * 70)
    print("KNOWLEDGE GRAPH TOPOLOGY, POLARITY INVARIANCE & ENCODING AUDITOR")
    print("Sources: llms-graph.json & llms-country-relationships.txt")
    print("=" * 70)

    if not os.path.exists(GRAPH_PATH):
        print(f"[FAIL] Graph file not found at {GRAPH_PATH}")
        sys.exit(1)

    with open(GRAPH_PATH, "r", encoding="utf-8") as f:
        raw_content = f.read()

    # 1. Encoding Guard
    enc_errors = audit_encoding(raw_content)

    data = json.loads(raw_content)
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    print(f"[*] Total Nodes Registered : {len(nodes)}")
    print(f"[*] Total Edges Registered : {len(edges)}")

    errors = enc_errors
    warnings = []

    # 2. Node Uniqueness
    node_registry: Dict[str, Dict[str, Any]] = {}
    duplicate_nodes = []
    for n in nodes:
        nid = n.get("id")
        if not nid:
            errors.append(f"Node missing 'id': {n}")
            continue
        if nid in node_registry:
            duplicate_nodes.append(nid)
        node_registry[nid] = n

    if duplicate_nodes:
        errors.append(f"DUPLICATE NODE IDs detected: {duplicate_nodes}")

    # 3. Edge Integrity (Zero Broken Edges & Self-Loops)
    broken_edges = []
    self_loops = []
    node_degree: Dict[str, int] = {nid: 0 for nid in node_registry}

    for idx, e in enumerate(edges):
        src = e.get("source")
        tgt = e.get("target")
        etype = e.get("type", "UNKNOWN")

        if src not in node_registry:
            broken_edges.append(f"Edge #{idx} ({etype}): Source '{src}' does not exist in nodes.")
        else:
            node_degree[src] += 1

        if tgt not in node_registry:
            broken_edges.append(f"Edge #{idx} ({etype}): Target '{tgt}' does not exist in nodes.")
        else:
            node_degree[tgt] += 1

        if src == tgt:
            self_loops.append(f"Edge #{idx}: Self-loop detected on '{src}'.")

    if broken_edges:
        errors.extend(broken_edges)

    if self_loops:
        warnings.extend(self_loops)

    # 4. Master SSOT Polarity Invariance
    pol_errors, synced_count = audit_polarity_synchronization(edges)
    errors.extend(pol_errors)

    # 5. Orphan Node Detection (Degree 0)
    orphans = [nid for nid, deg in node_degree.items() if deg == 0]
    connected_count = len(node_registry) - len(orphans)

    n_count = len(node_registry)
    max_edges = n_count * (n_count - 1) if n_count > 1 else 1
    density = len(edges) / max_edges if max_edges > 0 else 0

    print(f"[*] Connected Nodes        : {connected_count} / {n_count} ({connected_count/n_count*100:.1f}%)")
    print(f"[*] Edge Polarities Synced : {synced_count} edges verified against Master SSOT")
    print(f"[*] Graph Edge Density     : {density:.4f}")

    print("\n" + "=" * 70)
    if errors:
        print(f"[FAIL] DETECTED {len(errors)} GRAPH ISSUES:")
        for err in errors:
            print(f"  [!] {err}")
        print("=" * 70)
        sys.exit(1)
    else:
        print("[SUCCESS] GRAPH 100% SOUND & SYNCHRONIZED:")
        print("  - Zero encoding corruption / Zero mojibake")
        print("  - Zero broken edges (All sources and targets resolve)")
        print(f"  - 100% Edge polarities match Master Country SSOT ({synced_count} checked)")
        print("  - Zero duplicate node IDs")
        print("=" * 70)
        sys.exit(0)

if __name__ == "__main__":
    main()
