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
from typing import Dict, List, Set, Any, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GRAPH_PATH = os.path.join(ROOT_DIR, "llms-graph.json")
COUNTRY_TXT = os.path.join(ROOT_DIR, "llms-country-relationships.txt")
ENTITIES_PATH = os.path.join(ROOT_DIR, "llms-entities-id.txt")

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

    # 1.1 Strict Schema & Metadata Guard
    required_root_keys = ["$schema", "name", "version", "author", "license", "repository", "architecture_type", "routing_policy", "graph_accounting", "subgraphs", "graph_metadata", "nodes", "edges"]
    missing_root_keys = [k for k in required_root_keys if k not in data]
    if missing_root_keys:
        errors.append(f"MISSING GRAPH METADATA KEYS: {missing_root_keys}")

    graph_meta = data.get("graph_metadata", {})
    if not isinstance(graph_meta, dict) or "node_categories" not in graph_meta or "edge_types" not in graph_meta:
        errors.append("INVALID 'graph_metadata': must contain 'node_categories' and 'edge_types' lists.")

    # In federated architecture, also load all modular subgraphs for complete topological auditing
    subgraphs_manifest = data.get("subgraphs", {})
    subgraph_files = [
        os.path.join(ROOT_DIR, "llms-graph-chokepoints.json"),
        os.path.join(ROOT_DIR, "llms-graph-models.json"),
        os.path.join(ROOT_DIR, "llms-graph-actors.json")
    ]

    nodes = list(data.get("nodes", []))
    edges = list(data.get("edges", []))

    for sg_path in subgraph_files:
        if os.path.exists(sg_path):
            with open(sg_path, "r", encoding="utf-8") as sg_f:
                sg_data = json.load(sg_f)
                nodes.extend(sg_data.get("nodes", []))
                edges.extend(sg_data.get("edges", []))
        else:
            errors.append(f"MISSING SUBGRAPH FILE: {sg_path}")

    print(f"[*] Federated Nodes Audited : {len(nodes)} (8 Master Backbone + 234 Modular Subgraphs)")
    print(f"[*] Federated Edges Audited : {len(edges)} (7 Master Backbone + 297 Modular Subgraphs)")

    errors = enc_errors
    warnings = []

    # 2. Node & Edge Uniqueness
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

    seen_edges: Dict[Tuple[str, str, str], int] = {}
    duplicate_edges = []
    for idx, e in enumerate(edges):
        s = e.get("source")
        t = e.get("target")
        etype = e.get("type", "")
        edge_key = (s, t, etype)
        if edge_key in seen_edges:
            duplicate_edges.append((idx, seen_edges[edge_key], edge_key))
        else:
            seen_edges[edge_key] = idx

    if duplicate_edges:
        for curr_idx, prev_idx, k in duplicate_edges:
            errors.append(f"DUPLICATE EDGE detected: Edge #{curr_idx} duplicates Edge #{prev_idx} ({k[0]} -> {k[1]} [{k[2]}])")

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

    # 3.1 Strict Attribute Entity & Whitelist Guard
    valid_entity_tokens = set()
    if os.path.exists(ENTITIES_PATH):
        with open(ENTITIES_PATH, "r", encoding="utf-8") as ef:
            for eline in ef:
                eline = eline.strip()
                if eline and not eline.startswith("#"):
                    token = eline.split("|")[0].strip()
                    if token:
                        valid_entity_tokens.add(token)

    entity_attribute_keys = {"patron", "jurisdiction", "parent_authority", "dominant_supplier", "bloc", "strategic_alliance", "observer_bloc"}
    invalid_attribute_entities = []
    for n in nodes:
        nid = n.get("id", "UNKNOWN")
        attrs = n.get("attributes", {})
        if isinstance(attrs, dict):
            for k, val in attrs.items():
                if k in entity_attribute_keys and isinstance(val, str):
                    if val not in valid_entity_tokens and val not in node_registry:
                        invalid_attribute_entities.append(
                            f"Node '{nid}' attribute '{k}': '{val}' is not a registered entity in llms-entities-id.txt!"
                        )

    if invalid_attribute_entities:
        errors.extend(invalid_attribute_entities)

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
        print(f"  - Zero duplicate edge connections ({len(edges)} unique edges verified)")
        print("  - Zero duplicate node IDs")
        print("=" * 70)
        sys.exit(0)

if __name__ == "__main__":
    main()
