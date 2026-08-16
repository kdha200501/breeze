---
name: svg-fit-viewport
description: >-
  Resize an SVG graphic so its overall height exactly fills the viewport while
  preserving aspect ratios and radial angles to the center. Use this skill when
  the user says the SVG graphic is too small, doesn't fill the viewport height,
  is cropped, or asks to fit/scale the graphic to the viewport.
---

# SVG Fit-to-Viewport Height

## Prerequisites — files in context

Before doing anything else, check whether the target SVG file(s) are available
in context (attached, pasted, or already read).

**If no SVG file is in context**, use `ask_user` to request it:

```
ask_user: "Please share the SVG file(s) you want to fit to the viewport."
```

Do not proceed until at least one SVG file is available to read.

---

## Goal

Make the visible content of an SVG fill the viewport height exactly, without
moving or distorting any paths, and without clipping the stroke or shadow.

**Key insight:** Do **not** scale or transform the paths. Instead, shrink the
`viewBox` attribute so it tightly frames the full visual extent of the content
(including stroke half-width and filter output regions). The SVG renderer then
scales the viewBox to fit the `width`/`height` attributes automatically.

---

## Step 1 — Establish the geometric bounding box

Collect the min/max coordinates of every drawn element (paths, polygons, rects)
**before** any stroke or filter:

```
x_min, x_max, y_min, y_max  →  gw = x_max - x_min,  gh = y_max - y_min
cx = (x_min + x_max) / 2
cy = (y_min + y_max) / 2
```

---

## Step 2 — Expand for stroke width

If any element has `stroke-width: W`, extend the bbox by `W/2` on every side:

```
half = W / 2
sx_min = x_min - half
sx_max = x_max + half
sy_min = y_min - half
sy_max = y_max + half
```

---

## Step 3 — Expand for SVG filter output regions

SVG `<filter>` elements carry `x`, `y`, `width`, `height` attributes that
define the filter output region. These are **fractions of the element's
geometric bounding box** (not the stroke-expanded box) when
`filterUnits="objectBoundingBox"` (the default).

Convert them to absolute SVG coordinates:

```
fx_min = gx_min + filter_x * gw
fy_min = gy_min + filter_y * gh
fx_max = fx_min + filter_w * gw
fy_max = fy_min + filter_h * gh
```

The true visual extent is the **union** of the stroke-expanded box and every
filter output box.

### ⚠️ Degenerate bounding box (zero width or height)

When an element is a **purely horizontal or purely vertical line**, its
geometric bounding box has `gh = 0` (or `gw = 0`). With
`filterUnits="objectBoundingBox"`, the filter region collapses to zero area —
standards-compliant renderers (Chrome, WebStorm) render **nothing**, even
though the stroke itself is non-zero.

**Detection**: if `gw == 0` or `gh == 0` for any filtered element, the filter
is broken.

**Fix**: switch that filter to `filterUnits="userSpaceOnUse"` and specify
absolute SVG-coordinate bounds that cover the stroke (path coords ± stroke
half-width ± filter blur/offset):

```xml
<filter filterUnits="userSpaceOnUse"
        x="{sx_min - blur - |dx|}"
        y="{sy_min - blur - |dy|}"
        width="{sx_width + 2*blur + |dx|}"
        height="{sy_height + 2*blur + |dy|}">
```

where `blur` = `stdDeviation` and `dx`/`dy` = `feOffset` values. Only the
filter definition changes; the path `d` attribute is untouched.

---

## Step 4 — Build a square viewBox (for a square viewport)

When the SVG `width` == `height` (square viewport), use a square viewBox so
that `preserveAspectRatio="xMidYMid meet"` (the default) applies a uniform
scale with no letterboxing artefacts.

```
visual_h = vy_max - vy_min   # height of union bbox
visual_w = vx_max - vx_min   # width  of union bbox
side     = max(visual_h, visual_w)   # use height if it is the limiting dimension

vb_x = cx - side / 2
vb_y = cy - side / 2
```

Set `viewBox="{vb_x} {vb_y} {side} {side}"`.

The graphic now fills the viewport height: `side * (px_h / side) = px_h`.

---

## Step 5 — Verify symmetry

The viewBox center must equal the content center so that radial angles from
the center are preserved:

```
assert abs((vb_x + side/2) - cx) < 0.01
assert abs((vb_y + side/2) - cy) < 0.01
```

---

## Worked example (6079.svg)

| Parameter | Value |
|---|---|
| Geometric bbox | x: 132.5–227.5 (w=95), y: 47.5–222.5 (h=175) |
| Content center | (180, 135) |
| Stroke-width | 30 → half = 15 |
| filter5 attrs | x=−0.309, y=−0.168, w=1.619, h=1.336 |
| Filter output y | 47.5 + (−0.168×175) = 18.1 → 18.1 + (1.336×175) = 251.9 |
| Filter output x | 132.5 + (−0.309×95) = 103.1 → 103.1 + (1.619×95) = 257.0 |
| Visual height | 251.9 − 18.1 = **233.8** (limiting dimension) |
| Final viewBox | `63.1475 18.1 233.8 233.8` |

The only change made to the SVG file was replacing the `viewBox` attribute.
No paths, transforms, or coordinates were modified.

---

## Common mistakes

| Mistake | Why it's wrong |
|---|---|
| Wrapping elements in `<g transform="scale(…)">` | Scales stroke widths and filter blur radii too, producing a graphic that appears larger than the viewport |
| Using only geometric bbox for viewBox | Clips the stroke overhang and drop shadow |
| Using a non-square viewBox on a square viewport | Letterboxing — the graphic won't fill height or width uniformly |
| Scaling around the SVG origin (0,0) instead of content center | Distorts radial angles; content shifts off-center |
| Using `filterUnits="objectBoundingBox"` (default) on a horizontal or vertical line | The bounding box has zero height/width, so the filter region collapses — the element becomes invisible in Chrome/WebStorm. Fix: switch to `filterUnits="userSpaceOnUse"` with absolute pixel bounds. |
