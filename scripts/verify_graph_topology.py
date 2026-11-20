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

    # Extract master polarities from SSOT (Shelves or Master TXT)
    country_polarities = {}
    shelf_files = [
        os.path.join(ROOT_DIR, f"llms-country-relationships-{slug}.txt")
        for slug in ("us", "ru", "cn", "ir")
    ]
    all_shelves_exist = all(os.path.exists(sf) for sf in shelf_files)

    dyad_matches = []
    if all_shelves_exist:
        for sf in shelf_files:
            with open(sf, "r", encoding="utf-8") as f:
                content = f.read()
            found = re.findall(
                r"Dyad ID:\s*REL_GEO_([A-Z0-9_]+)_GEO_([A-Z0-9_]+).*?Bilateral Stance:\s*([+\-0-9\.]+)",
                content,
                re.S
            )
            dyad_matches.extend(found)
    else:
        dyad_matches = re.findall(
            r"Dyad ID:\s*REL_GEO_([A-Z0-9_]+)_GEO_([A-Z0-9_]+).*?Bilateral Stance:\s*([+\-0-9\.]+)",
            c_txt,
            re.S
        )
        if not dyad_matches:
            dyad_matches = re.findall(
                r"ID:\s*REL_GEO_([A-Z0-9_]+)_GEO_([A-Z0-9_]+)[^\n]*\n\s*Ref:[^\n]*\n\s*P_baseline:\s*([+\-0-9\.]+)",
                c_txt
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
    errors = list(enc_errors)
    warnings = []

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

    mod_nodes_count = 0
    mod_edges_count = 0

    for sg_path in subgraph_files:
        if os.path.exists(sg_path):
            with open(sg_path, "r", encoding="utf-8") as sg_f:
                sg_data = json.load(sg_f)
                sg_nodes = sg_data.get("nodes", [])
                sg_edges = sg_data.get("edges", [])
                nodes.extend(sg_nodes)
                edges.extend(sg_edges)
                mod_nodes_count += len(sg_nodes)
                mod_edges_count += len(sg_edges)
        else:
            errors.append(f"MISSING SUBGRAPH FILE: {sg_path}")

    bb_nodes_count = len(data.get("nodes", []))
    bb_edges_count = len(data.get("edges", []))

    print(f"[*] Federated Nodes Audited : {len(nodes)} ({bb_nodes_count} Master Backbone + {mod_nodes_count} Modular Subgraphs)")
    print(f"[*] Federated Edges Audited : {len(edges)} ({bb_edges_count} Master Backbone + {mod_edges_count} Modular Subgraphs)")

    # 1.2 Graph Accounting & Subgraph Counts Strict Synchronicity Guard
    accounting = data.get("graph_accounting", {})
    subgraphs = data.get("subgraphs", {})

    m_path = os.path.join(ROOT_DIR, "llms-graph-models.json")
    a_path = os.path.join(ROOT_DIR, "llms-graph-actors.json")
    c_path = os.path.join(ROOT_DIR, "llms-graph-chokepoints.json")

    actual_m_nodes = len(json.load(open(m_path, encoding="utf-8")).get("nodes", [])) if os.path.exists(m_path) else 0
    actual_m_edges = len(json.load(open(m_path, encoding="utf-8")).get("edges", [])) if os.path.exists(m_path) else 0
    actual_a_nodes = len(json.load(open(a_path, encoding="utf-8")).get("nodes", [])) if os.path.exists(a_path) else 0
    actual_a_edges = len(json.load(open(a_path, encoding="utf-8")).get("edges", [])) if os.path.exists(a_path) else 0
    actual_c_nodes = len(json.load(open(c_path, encoding="utf-8")).get("nodes", [])) if os.path.exists(c_path) else 0
    actual_c_edges = len(json.load(open(c_path, encoding="utf-8")).get("edges", [])) if os.path.exists(c_path) else 0

    actual_bb_nodes = len(data.get("nodes", []))
    actual_bb_edges = len(data.get("edges", []))

    actual_mod_nodes = actual_m_nodes + actual_a_nodes + actual_c_nodes
    actual_mod_edges = actual_m_edges + actual_a_edges + actual_c_edges
    actual_tot_nodes = actual_mod_nodes + actual_bb_nodes
    actual_tot_edges = actual_mod_edges + actual_bb_edges

    # Check graph_accounting exact matches
    if accounting.get("modular_subgraphs_nodes") != actual_mod_nodes:
        errors.append(f"graph_accounting.modular_subgraphs_nodes ({accounting.get('modular_subgraphs_nodes')}) != actual ({actual_mod_nodes})")
    if accounting.get("modular_subgraphs_edges") != actual_mod_edges:
        errors.append(f"graph_accounting.modular_subgraphs_edges ({accounting.get('modular_subgraphs_edges')}) != actual ({actual_mod_edges})")
    if accounting.get("core_backbone_nodes") != actual_bb_nodes:
        errors.append(f"graph_accounting.core_backbone_nodes ({accounting.get('core_backbone_nodes')}) != actual ({actual_bb_nodes})")
    if accounting.get("core_backbone_edges") != actual_bb_edges:
        errors.append(f"graph_accounting.core_backbone_edges ({accounting.get('core_backbone_edges')}) != actual ({actual_bb_edges})")
    if accounting.get("total_federated_nodes") != actual_tot_nodes:
        errors.append(f"graph_accounting.total_federated_nodes ({accounting.get('total_federated_nodes')}) != actual ({actual_tot_nodes})")
    if accounting.get("total_federated_edges") != actual_tot_edges:
        errors.append(f"graph_accounting.total_federated_edges ({accounting.get('total_federated_edges')}) != actual ({actual_tot_edges})")

    # Check individual subgraphs exact matches
    if subgraphs.get("models", {}).get("nodes_count") != actual_m_nodes:
        errors.append(f"subgraphs.models.nodes_count ({subgraphs.get('models', {}).get('nodes_count')}) != actual ({actual_m_nodes})")
    if subgraphs.get("models", {}).get("edges_count") != actual_m_edges:
        errors.append(f"subgraphs.models.edges_count ({subgraphs.get('models', {}).get('edges_count')}) != actual ({actual_m_edges})")
    if subgraphs.get("actors", {}).get("nodes_count") != actual_a_nodes:
        errors.append(f"subgraphs.actors.nodes_count ({subgraphs.get('actors', {}).get('nodes_count')}) != actual ({actual_a_nodes})")
    if subgraphs.get("actors", {}).get("edges_count") != actual_a_edges:
        errors.append(f"subgraphs.actors.edges_count ({subgraphs.get('actors', {}).get('edges_count')}) != actual ({actual_a_edges})")
    if subgraphs.get("chokepoints", {}).get("nodes_count") != actual_c_nodes:
        errors.append(f"subgraphs.chokepoints.nodes_count ({subgraphs.get('chokepoints', {}).get('nodes_count')}) != actual ({actual_c_nodes})")
    if subgraphs.get("chokepoints", {}).get("edges_count") != actual_c_edges:
        errors.append(f"subgraphs.chokepoints.edges_count ({subgraphs.get('chokepoints', {}).get('edges_count')}) != actual ({actual_c_edges})")

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

    # 5. Orphan Node Detection (Degree 0) - Zero Orphan Tolerance
    orphans = [nid for nid, deg in node_degree.items() if deg == 0]
    if orphans:
        errors.append(f"ORPHAN NODES DETECTED: Found {len(orphans)} isolated nodes with 0 connections in Knowledge Graph: {sorted(orphans)}")

    # 6. Cross-Manifest Parity (Formulas <-> Graph <-> Models Manifest)
    # Extracts all active models from formula files and ensures they are registered in the graph
    import glob
    formula_files = glob.glob(os.path.join(ROOT_DIR, "llms-formulas*.txt"))
    all_formula_models = set()
    for ff in formula_files:
        with open(ff, "r", encoding="utf-8") as f_f:
            f_content = f_f.read()
        for match in re.finditer(r'^###\s+([0-9]+(?:\.[0-9]+)?)\.\s+', f_content, re.M):
            num = match.group(1)
            # Skip architectural directives, data engines or reserved placeholders
            if num in ("0.1", "0.2", "0.3", "0.4", "0.5", "0.5.1", "0.6", "0.7", "25.4"):
                continue
            all_formula_models.add(f"MODEL_{num}")

    graph_model_nodes = {nid for nid in node_registry if nid.startswith("MODEL_")}
    missing_models_in_graph = all_formula_models - graph_model_nodes
    if missing_models_in_graph:
        errors.append(
            f"FORMULA TO GRAPH DESYNCHRONIZATION: The following models are documented in formula manifests but MISSING from Knowledge Graph: {sorted(missing_models_in_graph)}"
        )

    # 7. Model Ingestion Integrity Guard
    # Every MODEL_ node must ingest at least one series or connect to another model via BRIDGES_TO_MODEL/EXECUTES_MODEL
    for mid in graph_model_nodes:
        has_ingress_or_bridge = any(
            (e.get("target") == mid and e.get("type") in ("INGESTS_SERIES", "EXECUTES_MODEL", "BRIDGES_TO_MODEL")) or
            (e.get("source") == mid and e.get("type") in ("BRIDGES_TO_MODEL", "EXECUTES_MODEL"))
            for e in edges if isinstance(e, dict)
        )
        if not has_ingress_or_bridge:
            errors.append(f"UNLINKED MODEL NODE: '{mid}' has no INGESTS_SERIES or bridge connection in graph!")

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
