#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_graph.py
--------------
Master Knowledge Graph Compiler & Sharding Engine.

Compiles modular graph layers:
1. llms-graph-actors.json (Sovereign actors, alliances, non-state actors)
2. llms-graph-models.json (Macroeconomic models, FRED/BEA indicators, ingestion edges)
3. llms-graph-chokepoints.json (Maritime chokepoints, strategic basins, commodities)
4. llms-graph.json (Master Router & Guide Manifest - Pure Router, no monolithic nodes/edges dump)

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-graph.json
"""

import os
import json

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_GRAPH = os.path.join(ROOT_DIR, "llms-graph.json")

ACTORS_JSON = os.path.join(ROOT_DIR, "llms-graph-actors.json")
MODELS_JSON = os.path.join(ROOT_DIR, "llms-graph-models.json")
CHOKEPOINTS_JSON = os.path.join(ROOT_DIR, "llms-graph-chokepoints.json")

CHOKE_CATEGORIES = {"CHOKEPOINT", "COMMODITY_STRATEGIC", "CRITICAL_MINERAL", "ENERGY_BENCHMARK"}
MODEL_CATEGORIES = {"MODEL", "INDICATOR"}
ACTOR_CATEGORIES = {"ACTOR"}
ENDPOINT_CATEGORIES = {"ENDPOINT_SCHEMA"}

def line_per_object_json(data_dict: dict) -> str:
    lines = ["{"]
    keys = list(data_dict.keys())
    for idx, (k, v) in enumerate(data_dict.items()):
        comma_outer = "," if idx < len(keys) - 1 else ""
        if k in ("nodes", "edges"):
            lines.append(f'  "{k}": [')
            for i, item in enumerate(v):
                comma = "," if i < len(v) - 1 else ""
                lines.append("    " + json.dumps(item, ensure_ascii=False) + comma)
            lines.append(f"  ]{comma_outer}")
        else:
            lines.append(f'  "{k}": ' + json.dumps(v, ensure_ascii=False) + comma_outer)
    lines.append("}")
    return "\n".join(lines)

def build_modular_graphs():
    # Load from existing modular files or raw data
    with open(SRC_GRAPH, "r", encoding="utf-8") as f:
        master = json.load(f)

    nodes = master.get("nodes", [])
    edges = master.get("edges", [])
    node_cats = {n["id"]: n.get("category") for n in nodes}

    # Clean descriptions to remove verbosity
    cleaned_nodes = []
    for n in nodes:
        item = dict(n)
        if "description" in item:
            del item["description"]
        cleaned_nodes.append(item)

    choke_nodes = [n for n in cleaned_nodes if n.get("category") in CHOKE_CATEGORIES]
    model_nodes = [n for n in cleaned_nodes if n.get("category") in MODEL_CATEGORIES]
    actor_nodes = [n for n in cleaned_nodes if n.get("category") in ACTOR_CATEGORIES]
    endpoint_nodes = [n for n in cleaned_nodes if n.get("category") in ENDPOINT_CATEGORIES]

    choke_edges = [
        e for e in edges
        if node_cats.get(e["source"]) in CHOKE_CATEGORIES or node_cats.get(e["target"]) in CHOKE_CATEGORIES
    ]
    rem_edges = [e for e in edges if e not in choke_edges]

    model_edges = [
        e for e in rem_edges
        if node_cats.get(e["source"]) in MODEL_CATEGORIES or node_cats.get(e["target"]) in MODEL_CATEGORIES
    ]
    rem_edges2 = [e for e in rem_edges if e not in model_edges]

    actor_edges = [
        e for e in rem_edges2
        if node_cats.get(e["source"]) in ACTOR_CATEGORIES and node_cats.get(e["target"]) in ACTOR_CATEGORIES
    ]
    rem_edges3 = [e for e in rem_edges2 if e not in actor_edges]
    backbone_edges = rem_edges3

    base_meta = {
        "$schema": master.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
        "author": master.get("author", "Ersoy Toptas"),
        "license": master.get("license", "CC BY-NC-ND 4.0"),
        "repository": master.get("repository", "https://analysisreports.github.io/")
    }

    # 1. Chokepoints layer
    choke_data = dict(base_meta)
    choke_data.update({
        "name": "Maritime Chokepoints, Strategic Basins & Commodity Corridors Subgraph",
        "version": "3.0.0",
        "subgraph_domain": "CHOKEPOINTS_AND_COMMODITIES",
        "nodes": choke_nodes,
        "edges": choke_edges
    })
    with open(CHOKEPOINTS_JSON, "w", encoding="utf-8") as f:
        f.write(line_per_object_json(choke_data))
    print(f"[OK] Generated {os.path.basename(CHOKEPOINTS_JSON)}: {len(choke_nodes)} nodes, {len(choke_edges)} edges")

    # 2. Models layer
    model_data = dict(base_meta)
    model_data.update({
        "name": "Quantitative Macroeconomic Models & Indicator Data Bindings Subgraph",
        "version": "3.0.0",
        "subgraph_domain": "MACRO_MODELS_AND_INDICATORS",
        "nodes": model_nodes,
        "edges": model_edges
    })
    with open(MODELS_JSON, "w", encoding="utf-8") as f:
        f.write(line_per_object_json(model_data))
    print(f"[OK] Generated {os.path.basename(MODELS_JSON)}: {len(model_nodes)} nodes, {len(model_edges)} edges")

    # 3. Actors layer
    actor_data = dict(base_meta)
    actor_data.update({
        "name": "Sovereign States, Alliances & Strategic Actors Subgraph",
        "version": "3.0.0",
        "subgraph_domain": "SOVEREIGN_ACTORS_AND_BLOCS",
        "nodes": actor_nodes,
        "edges": actor_edges
    })
    with open(ACTORS_JSON, "w", encoding="utf-8") as f:
        f.write(line_per_object_json(actor_data))
    print(f"[OK] Generated {os.path.basename(ACTORS_JSON)}: {len(actor_nodes)} nodes, {len(actor_edges)} edges")

    # 4. Pure Master Router & Guide Manifest (llms-graph.json)
    # Only holds the 8 core backbone nodes & 7 indexing edges, plus federated subgraph pointers.
    # Total size: ~3 KB instead of 88 KB!
    master_router = {
        "$schema": master.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
        "name": "Ersoy Toptas Macroeconomic & Geopolitical Knowledge Graph (Master Router & Guide)",
        "version": "3.0.0",
        "author": master.get("author", "Ersoy Toptas"),
        "license": master.get("license", "CC BY-NC-ND 4.0"),
        "repository": master.get("repository", "https://analysisreports.github.io/"),
        "architecture_type": "FEDERATED_MODULAR_GRAPH",
        "routing_policy": {
            "routing_instruction": "HIGH-PRIORITY DIRECTIVE: Fetch domain-specific subgraphs first based on query intent. Do not traverse monolithic graphs.",
            "chokepoints_subgraph": "https://analysisreports.github.io/llms-graph-chokepoints.json",
            "models_subgraph": "https://analysisreports.github.io/llms-graph-models.json",
            "actors_subgraph": "https://analysisreports.github.io/llms-graph-actors.json"
        },
        "graph_accounting": {
            "modular_subgraphs_nodes": len(choke_nodes) + len(model_nodes) + len(actor_nodes),
            "modular_subgraphs_edges": len(choke_edges) + len(model_edges) + len(actor_edges),
            "core_backbone_nodes": len(endpoint_nodes),
            "core_backbone_edges": len(backbone_edges),
            "total_federated_nodes": len(cleaned_nodes),
            "total_federated_edges": len(edges)
        },
        "subgraphs": {
            "chokepoints": {
                "endpoint": "https://analysisreports.github.io/llms-graph-chokepoints.json",
                "nodes_count": len(choke_nodes),
                "edges_count": len(choke_edges),
                "token_size": "~2,000",
                "scope": "Maritime chokepoints, naval bottlenecks, strategic basins, and commodities"
            },
            "models": {
                "endpoint": "https://analysisreports.github.io/llms-graph-models.json",
                "nodes_count": len(model_nodes),
                "edges_count": len(model_edges),
                "token_size": "~9,500",
                "scope": "Quantitative macro models, FRED/BEA indicators, and data ingestion bindings"
            },
            "actors": {
                "endpoint": "https://analysisreports.github.io/llms-graph-actors.json",
                "nodes_count": len(actor_nodes),
                "edges_count": len(actor_edges),
                "token_size": "~8,800",
                "scope": "Sovereign states, bilateral polarities, multilateral defense alliances, and strategic defense actors"
            },
            "core_backbone": {
                "scope": "Master repository endpoint schemas and cross-manifest indexing links",
                "nodes_count": len(endpoint_nodes),
                "edges_count": len(backbone_edges)
            }
        },
        "graph_metadata": master.get("graph_metadata", {}),
        "nodes": endpoint_nodes,
        "edges": backbone_edges
    }
    with open(SRC_GRAPH, "w", encoding="utf-8") as f:
        f.write(json.dumps(master_router, indent=2, ensure_ascii=False))
    print(f"[OK] Master Router {os.path.basename(SRC_GRAPH)} created: 8 backbone nodes, 7 edges (Pure Guide Format: ~3 KB)")

if __name__ == "__main__":
    build_modular_graphs()
