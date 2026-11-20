#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_graph.py
--------------
Master Knowledge Graph Compiler & Synchronizer.

Reads the modular graph layers:
1. llms-graph-actors.json (Sovereign actors, alliances, non-state actors)
2. llms-graph-models.json (Macroeconomic models, FRED/BEA indicators, ingestion edges)
3. llms-graph-chokepoints.json (Maritime chokepoints, strategic basins, commodities)

And dynamically compiles/updates `llms-graph.json` (Master Router & Guide Manifest)
with exact node and edge counts, ensuring zero manual counting and 100% automated precision.

Author: Ersoy Toptaş
License: CC BY-NC-ND 4.0
Endpoint: https://analysisreports.github.io/llms-graph.json
"""

import os
import json

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_GRAPH = os.path.join(ROOT_DIR, "llms-graph.json")
GRAPH_SCHEMA_URL = "https://analysisreports.github.io/schemas/graph.schema.json"

ACTORS_JSON = os.path.join(ROOT_DIR, "llms-graph-actors.json")
MODELS_JSON = os.path.join(ROOT_DIR, "llms-graph-models.json")
CHOKEPOINTS_JSON = os.path.join(ROOT_DIR, "llms-graph-chokepoints.json")

def compile_master_graph():
    # 1. Read existing subgraphs
    with open(ACTORS_JSON, "r", encoding="utf-8") as f:
        actors = json.load(f)
    with open(MODELS_JSON, "r", encoding="utf-8") as f:
        models = json.load(f)
    with open(CHOKEPOINTS_JSON, "r", encoding="utf-8") as f:
        choke = json.load(f)
    with open(SRC_GRAPH, "r", encoding="utf-8") as f:
        master = json.load(f)

    actor_nodes = len(actors.get("nodes", []))
    actor_edges = len(actors.get("edges", []))

    model_nodes = len(models.get("nodes", []))
    model_edges = len(models.get("edges", []))

    choke_nodes = len(choke.get("nodes", []))
    choke_edges = len(choke.get("edges", []))

    backbone_nodes = len(master.get("nodes", []))
    backbone_edges = len(master.get("edges", []))

    mod_nodes = actor_nodes + model_nodes + choke_nodes
    mod_edges = actor_edges + model_edges + choke_edges

    total_nodes = mod_nodes + backbone_nodes
    total_edges = mod_edges + backbone_edges

    # Update master router accounting & subgraphs dynamically
    master["$schema"] = GRAPH_SCHEMA_URL
    master["author"] = "Ersoy Toptaş"
    master["graph_accounting"] = {
        "modular_subgraphs_nodes": mod_nodes,
        "modular_subgraphs_edges": mod_edges,
        "core_backbone_nodes": backbone_nodes,
        "core_backbone_edges": backbone_edges,
        "total_federated_nodes": total_nodes,
        "total_federated_edges": total_edges
    }

    if "subgraphs" not in master:
        master["subgraphs"] = {}

    if "chokepoints" in master["subgraphs"]:
        master["subgraphs"]["chokepoints"]["nodes_count"] = choke_nodes
        master["subgraphs"]["chokepoints"]["edges_count"] = choke_edges
    if "models" in master["subgraphs"]:
        master["subgraphs"]["models"]["nodes_count"] = model_nodes
        master["subgraphs"]["models"]["edges_count"] = model_edges
    if "actors" in master["subgraphs"]:
        master["subgraphs"]["actors"]["nodes_count"] = actor_nodes
        master["subgraphs"]["actors"]["edges_count"] = actor_edges
    if "core_backbone" in master["subgraphs"]:
        master["subgraphs"]["core_backbone"]["nodes_count"] = backbone_nodes
        master["subgraphs"]["core_backbone"]["edges_count"] = backbone_edges

    with open(SRC_GRAPH, "w", encoding="utf-8") as f:
        json.dump(master, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"[OK] Compiled {os.path.basename(SRC_GRAPH)} with dynamic accounting:")
    print(f"     Actors: {actor_nodes} nodes, {actor_edges} edges")
    print(f"     Models: {model_nodes} nodes, {model_edges} edges")
    print(f"     Chokepoints: {choke_nodes} nodes, {choke_edges} edges")
    print(f"     Core Backbone: {backbone_nodes} nodes, {backbone_edges} edges")
    print(f"     Total Federated: {total_nodes} nodes, {total_edges} edges")

if __name__ == "__main__":
    compile_master_graph()
