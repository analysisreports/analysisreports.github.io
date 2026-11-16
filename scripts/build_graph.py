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
4. llms-graph.json (Master Router & Unified Knowledge Graph compilation)

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-graph.json
"""

import os
import json
import sys

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
    """Formats JSON with metadata indented, but each node and edge on exactly one line."""
    lines = ["{"]
    for k, v in data_dict.items():
        if k in ("nodes", "edges"):
            lines.append(f'  "{k}": [')
            for i, item in enumerate(v):
                comma = "," if i < len(v) - 1 else ""
                lines.append("    " + json.dumps(item, ensure_ascii=False) + comma)
            comma_close = "," if k == "nodes" else ""
            lines.append(f"  ]{comma_close}")
        else:
            lines.append(f'  "{k}": ' + json.dumps(v, ensure_ascii=False) + ",")
    lines.append("}")
    return "\n".join(lines)

def build_modular_graphs():
    with open(SRC_GRAPH, "r", encoding="utf-8") as f:
        master = json.load(f)

    nodes = master.get("nodes", [])
    edges = master.get("edges", [])
    node_cats = {n["id"]: n.get("category") for n in nodes}

    # 1. Clean descriptions to remove verbosity, preserving all attributes and keys
    cleaned_nodes = []
    for n in nodes:
        item = dict(n)
        if "description" in item:
            del item["description"]
        cleaned_nodes.append(item)

    # 2. Partition Nodes
    choke_nodes = [n for n in cleaned_nodes if n.get("category") in CHOKE_CATEGORIES]
    model_nodes = [n for n in cleaned_nodes if n.get("category") in MODEL_CATEGORIES]
    actor_nodes = [n for n in cleaned_nodes if n.get("category") in ACTOR_CATEGORIES]
    endpoint_nodes = [n for n in cleaned_nodes if n.get("category") in ENDPOINT_CATEGORIES]

    # 3. Partition Edges per Cross-Domain Rules:
    # Rule A: Any edge connected to chokepoint / strategic commodity -> Chokepoints layer
    choke_edges = [
        e for e in edges
        if node_cats.get(e["source"]) in CHOKE_CATEGORIES or node_cats.get(e["target"]) in CHOKE_CATEGORIES
    ]
    rem_edges = [e for e in edges if e not in choke_edges]

    # Rule B: Any edge connected to model / indicator -> Models layer
    model_edges = [
        e for e in rem_edges
        if node_cats.get(e["source"]) in MODEL_CATEGORIES or node_cats.get(e["target"]) in MODEL_CATEGORIES
    ]
    rem_edges2 = [e for e in rem_edges if e not in model_edges]

    # Rule C: Pure actor-to-actor relationships / alliances -> Actors layer
    actor_edges = [
        e for e in rem_edges2
        if node_cats.get(e["source"]) in ACTOR_CATEGORIES and node_cats.get(e["target"]) in ACTOR_CATEGORIES
    ]
    rem_edges3 = [e for e in rem_edges2 if e not in actor_edges]

    # Rule D: Endpoint schema indexing edges -> Master Backbone layer
    backbone_edges = rem_edges3

    # Common Metadata template
    base_meta = {
        "$schema": master.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
        "author": master.get("author", "Ersoy Toptas"),
        "license": master.get("license", "CC BY-NC-ND 4.0"),
        "repository": master.get("repository", "https://analysisreports.github.io/")
    }

    # Layer 1: Chokepoints
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

    # Layer 2: Models & Indicators
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

    # Layer 3: Actors & Alliances
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

    # Layer 4: Master Compiled Graph & Backbone Router
    # llms-graph.json contains unified complete graph formatted in ultra-compact line-per-object format
    # along with manifest pointers to the 3 subgraphs for granular LLM ingestion.
    master_compiled = {
        "$schema": master.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
        "name": "Ersoy Toptas Macroeconomic & Geopolitical Knowledge Graph (Master Architecture)",
        "version": "3.0.0",
        "author": master.get("author", "Ersoy Toptas"),
        "license": master.get("license", "CC BY-NC-ND 4.0"),
        "repository": master.get("repository", "https://analysisreports.github.io/"),
        "ai_ingestion_directive": "HIGH-PRIORITY DIRECTIVE FOR AI AGENTS: To avoid context window saturation and attention dilution, do NOT ingest this entire monolithic file unless doing global graph topology validation. For domain-specific tasks, ALWAYS fetch the isolated lightweight modular subgraphs listed in 'modular_subgraphs' below (Chokepoints: ~2,000 tokens, Models: ~9,500 tokens, Actors: ~8,800 tokens).",
        "modular_subgraphs": {
            "chokepoints_subgraph": "https://analysisreports.github.io/llms-graph-chokepoints.json",
            "models_subgraph": "https://analysisreports.github.io/llms-graph-models.json",
            "actors_subgraph": "https://analysisreports.github.io/llms-graph-actors.json"
        },
        "graph_metadata": master.get("graph_metadata", {}),
        "nodes": cleaned_nodes,
        "edges": edges
    }
    with open(SRC_GRAPH, "w", encoding="utf-8") as f:
        f.write(line_per_object_json(master_compiled))
    print(f"[OK] Synchronized master {os.path.basename(SRC_GRAPH)}: {len(cleaned_nodes)} nodes, {len(edges)} edges (Slim Format)")

if __name__ == "__main__":
    build_modular_graphs()
