"""Load and query the SBDD knowledge graph (see build_graph.py for schema)."""

import json
from pathlib import Path

import networkx as nx

GRAPH_PATH = Path(__file__).parent / "graph.json"


def load():
    data = json.loads(GRAPH_PATH.read_text())
    return nx.node_link_graph(data, edges="edges")


def describe(G, node_id):
    n = G.nodes[node_id]
    print(f"[{n['type']}] {n['label']}  ({node_id})")
    print(f"  {n['summary']}")
    if n["type"] == "Paper":
        print(f"  {n['url']} ({n['year']})")


def neighbors_by_relation(G, node_id, relation, direction="out"):
    """Nodes connected to node_id via a given relation, either direction."""
    edges = G.out_edges(node_id, data=True) if direction == "out" \
        else G.in_edges(node_id, data=True)
    result = []
    for u, v, d in edges:
        if d["relation"] == relation:
            result.append(v if direction == "out" else u)
    return result


def papers_for_concept(G, concept_id):
    """Papers that introduce/extend/discuss/explain a concept."""
    return [u for u, v, d in G.in_edges(concept_id, data=True)
            if G.nodes[u]["type"] == "Paper"]


def concepts_for_paper(G, paper_id):
    return [v for u, v, d in G.out_edges(paper_id, data=True)
            if G.nodes[v]["type"] in ("Concept", "Method")]


if __name__ == "__main__":
    G = load()
    print(f"loaded {G.number_of_nodes()} nodes, {G.number_of_edges()} edges\n")

    print("== Papers behind 'hot_spot' ==")
    for p in papers_for_concept(G, "hot_spot"):
        describe(G, p)
    print()

    print("== What 'rigid_receptor_docking' fails under ==")
    for c in neighbors_by_relation(G, "rigid_receptor_docking", "fails_under"):
        describe(G, c)
    print()

    print("== Everything 'docking' is connected to ==")
    for _, v, d in G.out_edges("docking", data=True):
        print(f"  docking --{d['relation']}--> {v}")
    for u, _, d in G.in_edges("docking", data=True):
        print(f"  {u} --{d['relation']}--> docking")
