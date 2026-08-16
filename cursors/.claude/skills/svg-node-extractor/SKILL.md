---
name: svg-node-extractor
description: >-
  Extract outer node coordinates from SVG files and save them to separate text
  files. Use this skill when the user asks to extract, save, or list node
  coordinates from one or more SVG files, or mentions "outer nodes" from SVGs.
---

# SVG Node Coordinate Extractor

## Overview

For each `.svg` file provided, extract all path node coordinates (from `M`/`L`/`m`/`l`
commands in `d=` attributes) and save the results to a separate `<basename>_nodes.txt`
file next to the source SVG.

The extraction script is bundled as `extract_svg_nodes.py` in this skill's directory.

---

## How to run

```bash
python3 ~/.claude/skills/svg-node-extractor/extract_svg_nodes.py <file_or_glob> [...]
```

### Examples

```bash
# All SVGs matching a pattern in the current directory
python3 ~/.claude/skills/svg-node-extractor/extract_svg_nodes.py 607*.svg

# A specific file
python3 ~/.claude/skills/svg-node-extractor/extract_svg_nodes.py /path/to/file.svg

# All SVGs in a directory
python3 ~/.claude/skills/svg-node-extractor/extract_svg_nodes.py /path/to/dir/*.svg
```

---

## Output format

Each SVG produces a `<basename>_nodes.txt` file in the same directory as the SVG:

```
SVG file: 6072.svg
====================

path id=rect1-2-7  label=lower-strap
  (157.39042, 182.49918)

path id=path2
  (135.0, 110.0)
  (20.0, 20.0)
  ...
```

Each path element is listed with its `id`, optional `inkscape:label`, and all
`(x, y)` coordinate pairs extracted from `M`/`L`/`m`/`l` commands.

---

## Notes

- Coordinates reflect the raw path `d=` values — absolute for `M`/`L`, relative for `m`/`l`.
- Paths with no `M`/`L`/`m`/`l` nodes (e.g., pure arc paths) are omitted.
- The script handles glob expansion itself, so quoting patterns is safe.
