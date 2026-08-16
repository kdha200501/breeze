---
name: png-ascii-preview
description: >-
  Render a PNG image as an ASCII picture on the terminal, using '#' and 'o' for
  pixels and '.' for transparent areas. Use this skill when the user wants to
  preview, inspect, or ASCII-render a PNG file (e.g. an icon or cursor), or
  mentions "show me the PNG as ASCII" or "preview the png".
---

# PNG ASCII Preview

## Overview

This skill renders a PNG image as plain ASCII art so it can be inspected directly
in the terminal. It uses `preview_png.py` — bundled in this skill's directory
alongside this `SKILL.md` — which requires Python 3 and Pillow (`PIL`).

Legend:

- `#` — opaque dark pixel (r+g+b < 300)
- `o` — opaque light pixel
- `.` — transparent pixel (alpha < 128)

---

## Step 1 — Determine the target file

If the user named a PNG file in the conversation, use that file.

Otherwise, look for PNG files in the current working directory:

```bash
ls -1 *.png 2>/dev/null
```

- If exactly one PNG is found, ask the user to confirm it.
- If multiple PNGs are found, list them and ask the user which one to preview.
- If no PNGs are found, ask the user for the path to the file they want to
  preview and wait for their answer.

## Step 2 — Render the image

```bash
python3 ~/.claude/skills/png-ascii-preview/preview_png.py PATH/TO/FILE.png
```

The script prints the image dimensions (`W H`) on the first line, followed by
one row of ASCII per image row.

If the file is large, the ASCII output can be very wide and tall; consider
telling the user the dimensions first. To inspect just a portion, the user can
ask for a crop, and `preview_png.py` can be adapted on the fly (e.g. passing a
crop region) if they do.

## Notes

- Pillow is required: install with `pip install Pillow` if the import fails.
- The skill directory is `~/.claude/skills/png-ascii-preview/`.
