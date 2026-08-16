---
name: ascii-svg-path
description: >-
  Convert an ASCII art shape of '#' markings into an SVG shape drawn as a
  single unbroken stroke. Use this skill when the user provides a grid of '#'
  characters (optionally decorated with other letters/dots) and asks to turn it
  into an SVG, or mentions "create an svg shape from the # markings".
---

# ASCII '#' Shape to Single Path SVG

## Overview

Turn a shape drawn out of `#` characters into an SVG whose contents are **one
`<path>` element**: a sequence of node-simple trails joined by `M` (move-to)
commands. Within each trail no node is repeated. Together the trails cover
**every adjacency edge exactly once** — no edge is skipped, no edge is
retraced.

The conversion is bundled as `build_svg.py` in this skill's directory and is
run as a one-off command.

---

## Rules that define the result

1. **Nodes** — every `#` becomes exactly one node at an (x, y) coordinate.
   Nodes are stored in a **map keyed by (x, y)**, so a node at an
   already-claimed coordinate is never created a second time (guaranteed
   uniqueness). A simple array/list would not give that guarantee.

2. **Adjacency** — a node has at most eight neighbours in the grid (the 8
  -neighbourhood around a cell). Two nodes are *adjacent* when one falls into
   the other node's eight neighbouring positions. A stroke is required between
   **every** pair of adjacent nodes.

3. **Node-simple trail decomposition** — the `d` attribute is produced as a
   sequence of `M … L … L …` subpaths:
   - Each subpath (trail) extends greedily via DFS, picking an unused edge to a
     neighbour **not yet in the current trail**.
   - When no such move is possible (dead-end or all neighbours already visited
     in this trail), the trail ends and an `M` teleport begins a new trail at
     any node that still has unused edges.
   - Within each trail no node appears more than once.
   - A node may appear as an `M` start for more than one trail (once per trail
     that begins there) — this is the expected cost of trail decomposition on
     branching graphs.
   - Every adjacency edge is drawn exactly once across all trails.

4. **Coordinates** — the cell size is 30 px: a `#` at column `c` (0-based) and
   row `r` (0-based) maps to `(x, y) = (c * 30, r * 30)`.

5. **Stroke** — black, `stroke-width="6"`, round caps and joins.

---

## How to run

Locate `build_svg.py` in this skill's directory:

- **Claude Code**: the path is `${CLAUDE_SKILL_DIR}/build_svg.py`
- **Other tools**: find `build_svg.py` alongside this `SKILL.md`
  (e.g. `~/.claude/skills/ascii-svg-path/build_svg.py`)

Take the shape from the user's message (copy it into a file), then:

```bash
python3 <path_to_build_svg.py> <shape_file> > out.svg
```

The script prints the SVG to stdout and a diagnostic report to stderr
(number of nodes, list of node coordinates, edge count, trail count, and
total segment count).

---

## Working example

Given the shape:

```
................
#..............#
#..............#
.#.....#......#.
..############..
.#.....#......#.
#..............#
#..............#
................
```

26 `#` nodes are found. There are 29 adjacency edges. The trail decomposition
produces 6 node-simple trails covering all 29 edges exactly once, using 6 `M`
commands within a single `<path>` element. Within each trail, no node is
repeated.

---

## Troubleshooting

- **`no '#' nodes found`** — the input has no `#` characters. Confirm the
  shape was copied verbatim.
- **`shape is not connected`** — two (or more) clusters of `#`s are not
  8-neighbour-adjacent. Either connect them or run the skill on each cluster
  separately and merge the SVG outputs.
- **Many trails / M commands** — shapes with many branching nodes (degree ≥ 3)
  require more trails. This is expected: a degree-4 branching node must appear
  in at least 2 trails; a degree-3 node in at least 2 trails. The algorithm
  minimises this greedily but may not always find the globally optimal split.
