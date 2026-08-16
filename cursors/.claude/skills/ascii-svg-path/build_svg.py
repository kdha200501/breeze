#!/usr/bin/env python3
"""Build an SVG from an ASCII shape of '#' markings.

Usage:
    python3 build_svg.py shape.txt > out.svg
    cat shape.txt | python3 build_svg.py - > out.svg

Rules:
  - every '#' cell becomes exactly one node at (col*CELL, row*CELL)
  - nodes are stored in a MAP keyed by their (x, y) coordinate, so a node
    at an already-claimed (x, y) is never created a second time
  - two nodes are adjacent when they are 8-neighbours in the grid
  - a stroke is drawn between EVERY pair of adjacent nodes exactly once
  - the output is one <path> element whose d attribute is a sequence of
    node-simple trails separated by M (move-to) commands; within each
    trail no node is repeated, and every adjacency edge is covered by
    exactly one trail

Algorithm:
  1. read '#' cells -> node map keyed by (x, y)
  2. build the edge set from 8-neighbour adjacency
  3. decompose the edge set into node-simple trails using a DFS that
     backtracks through the remaining edge multigraph:
       - greedily extend the current trail depth-first
       - when no unused edge can be taken from the current node without
         revisiting a node already in the current trail, close the trail
         and start a new one (M teleport) from an arbitrary node that
         still has unused edges
  4. emit the trails as one <path d="M... L... L... M... L..."/>
"""
import sys
from collections import defaultdict

CELL = 30
STROKE = CELL // 5
PAD = CELL


def parse_nodes(lines):
    """Return a map keyed by (x, y).  Duplicate (x, y) are never created."""
    nodes = {}
    for row, line in enumerate(lines):
        for col, ch in enumerate(line.rstrip("\n")):
            if ch == "#":
                x, y = col * CELL, row * CELL
                if (x, y) not in nodes:
                    nodes[(x, y)] = (col, row)
    if not nodes:
        raise SystemExit("no '#' nodes found in the input")
    return nodes


def build_adjacency(nodes):
    adj = {p: set() for p in nodes}
    for x, y in nodes:
        for dx in (0, -CELL, CELL):
            for dy in (0, -CELL, CELL):
                if (dx, dy) == (0, 0):
                    continue
                q = (x + dx, y + dy)
                if q in nodes:
                    adj[(x, y)].add(q)
    return adj


def edge_set(adj):
    edges = set()
    for p, neighbours in adj.items():
        for q in neighbours:
            edges.add(frozenset((p, q)))
    return edges


def decompose_trails(nodes, adj):
    """Decompose all edges into node-simple trails.

    Returns a list of trails, where each trail is a list of (x,y) nodes.
    Within each trail no node is repeated.  Together the trails cover
    every adjacency edge exactly once.
    """
    # Build a mutable remaining-edges structure
    remaining = defaultdict(list)
    for p, neighbours in adj.items():
        for q in sorted(neighbours):  # sorted for determinism
            if p < q:  # add each undirected edge once
                remaining[p].append(q)
                remaining[q].append(p)

    def has_remaining(v):
        return bool(remaining[v])

    def any_node_with_edges():
        for v in sorted(nodes):
            if remaining[v]:
                return v
        return None

    trails = []
    start = min(nodes)

    while True:
        if not has_remaining(start):
            start = any_node_with_edges()
            if start is None:
                break

        trail = [start]
        trail_set = {start}
        current = start

        while True:
            # Pick a neighbour reachable via an unused edge that is not
            # already in the current trail
            moved = False
            for i, nxt in enumerate(remaining[current]):
                if nxt not in trail_set:
                    remaining[current].pop(i)
                    remaining[nxt].remove(current)
                    trail.append(nxt)
                    trail_set.add(nxt)
                    current = nxt
                    moved = True
                    break
            if not moved:
                break

        trails.append(trail)
        # next trail starts from a node that still has unused edges
        start = any_node_with_edges() or min(nodes)

    return trails


def verify(trails, nodes, adj):
    all_edges = edge_set(adj)
    drawn = set()
    for trail in trails:
        seen_in_trail = set()
        for i, p in enumerate(trail):
            if p in seen_in_trail:
                raise SystemExit("internal error: node %s repeated in trail %d" % (p, trails.index(trail)))
            seen_in_trail.add(p)
            if i > 0:
                a, b = trail[i - 1], p
                if max(abs(a[0] - b[0]), abs(a[1] - b[1])) != CELL:
                    raise SystemExit("internal error: non-adjacent jump %s -> %s" % (a, b))
                e = frozenset((a, b))
                if e in drawn:
                    raise SystemExit("internal error: edge %s drawn twice" % str(e))
                drawn.add(e)
    missing = all_edges - drawn
    if missing:
        raise SystemExit("internal error: %d edge(s) not drawn: %s" % (len(missing), missing))


def to_svg(trails, nodes):
    all_pts = [p for trail in trails for p in trail]
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    view = (
        min(xs) - PAD,
        min(ys) - PAD,
        max(xs) - min(xs) + 2 * PAD,
        max(ys) - min(ys) + 2 * PAD,
    )
    parts = []
    for trail in trails:
        seg = "M%d %d" % trail[0]
        for p in trail[1:]:
            seg += " L%d %d" % p
        parts.append(seg)
    d = " ".join(parts)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="%d %d %d %d" width="%d" height="%d">\n'
        '  <path d="%s" fill="none" stroke="#000" '
        'stroke-width="%d" stroke-linecap="round" '
        'stroke-linejoin="round"/>\n'
        "</svg>\n"
        % (view[0], view[1], view[2], view[3], view[2] * 2, view[3] * 2, d, STROKE)
    )


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "-"
    stream = sys.stdin if path == "-" else open(path)
    with stream:
        lines = stream.read().splitlines()

    nodes = parse_nodes(lines)
    adj = build_adjacency(nodes)
    edges = edge_set(adj)
    trails = decompose_trails(nodes, adj)
    verify(trails, nodes, adj)
    sys.stdout.write(to_svg(trails, nodes))

    total_segments = sum(len(t) - 1 for t in trails)
    sys.stderr.write("nodes: %d\n" % len(nodes))
    for (x, y) in sorted(nodes):
        sys.stderr.write("  node (%d, %d)\n" % (x, y))
    sys.stderr.write(
        "edges: %d  trails: %d  segments: %d  -> %d M command(s)\n"
        % (len(edges), len(trails), total_segments, len(trails))
    )


if __name__ == "__main__":
    main()
