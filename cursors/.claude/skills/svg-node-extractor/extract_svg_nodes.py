#!/usr/bin/env python3
"""
Extract the outer contour nodes from SVG files by computing the polygon union
of all path shapes, then saving the resulting boundary coordinates to a
separate text file per SVG.

Usage:
    python3 extract_svg_nodes.py <glob_pattern_or_files...>

Example:
    python3 extract_svg_nodes.py 607*.svg
    python3 extract_svg_nodes.py /path/to/files/*.svg

Requires: shapely  (pip install shapely)
"""

import re
import sys
import glob
import os

try:
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from shapely.validation import make_valid
except ImportError:
    sys.exit("Missing dependency: pip install shapely")


def split_subpaths(d: str) -> list[str]:
    """Split a path d string into individual subpaths at each M/m command."""
    parts = re.split(r'(?<![a-zA-Z])(?=[Mm])', d.strip())
    return [p.strip() for p in parts if p.strip()]


CURVE_SAMPLES = 12  # intermediate points sampled per curve segment


def _sample_cubic(p0, p1, p2, p3, n=CURVE_SAMPLES):
    """Return n points along a cubic bezier (excluding p0, including p3)."""
    pts = []
    for k in range(1, n + 1):
        t = k / n
        u = 1 - t
        x = u**3*p0[0] + 3*u**2*t*p1[0] + 3*u*t**2*p2[0] + t**3*p3[0]
        y = u**3*p0[1] + 3*u**2*t*p1[1] + 3*u*t**2*p2[1] + t**3*p3[1]
        pts.append((x, y))
    return pts


def _sample_quadratic(p0, p1, p2, n=CURVE_SAMPLES):
    """Return n points along a quadratic bezier (excluding p0, including p2)."""
    pts = []
    for k in range(1, n + 1):
        t = k / n
        u = 1 - t
        x = u**2*p0[0] + 2*u*t*p1[0] + t**2*p2[0]
        y = u**2*p0[1] + 2*u*t*p1[1] + t**2*p2[1]
        pts.append((x, y))
    return pts


def _sample_arc(x1, y1, rx, ry, x_rot_deg, large_arc, sweep, x2, y2, n=CURVE_SAMPLES):
    """Sample n points along an SVG arc using the endpoint parameterisation."""
    import math
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    phi = math.radians(x_rot_deg)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p =  cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy
    rx, ry = abs(rx), abs(ry)
    lam = (x1p / rx)**2 + (y1p / ry)**2
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = max(0.0, (rx*ry)**2 - (rx*y1p)**2 - (ry*x1p)**2)
    den = (rx*y1p)**2 + (ry*x1p)**2
    sq = math.sqrt(num / den) if den else 0
    if large_arc == sweep:
        sq = -sq
    cxp =  sq * rx * y1p / ry
    cyp = -sq * ry * x1p / rx
    acx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2
    acy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2

    def angle(ux, uy, vx, vy):
        c = max(-1.0, min(1.0, (ux*vx + uy*vy) / (math.sqrt(ux**2+uy**2) * math.sqrt(vx**2+vy**2))))
        a = math.acos(c)
        return -a if ux*vy - uy*vx < 0 else a

    theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    elif sweep and dtheta < 0:
        dtheta += 2 * math.pi

    pts = []
    for k in range(1, n + 1):
        t = theta1 + dtheta * k / n
        xp = cos_phi * rx * math.cos(t) - sin_phi * ry * math.sin(t) + acx
        yp = sin_phi * rx * math.cos(t) + cos_phi * ry * math.sin(t) + acy
        pts.append((xp, yp))
    return pts


def parse_path_nodes(d: str) -> list[tuple[float, float]]:
    """
    Parse an SVG path `d` string and return a list of absolute (x, y) node
    positions. Curves (C/c, S/s, Q/q, T/t, A/a) are tessellated into
    CURVE_SAMPLES intermediate points so curved strokes are faithfully
    represented in the output polygon.

    Handles: M m L l H h V v C c S s Q q T t A a Z z
    """
    tokens = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', d)

    nodes: list[tuple[float, float]] = []
    cx, cy = 0.0, 0.0
    sx, sy = 0.0, 0.0
    last_cp = (0.0, 0.0)
    last_cmd = ''
    cmd = ''
    nums: list[float] = []

    def consume():
        nonlocal cx, cy, sx, sy, last_cp, last_cmd
        if not cmd or not nums:
            return
        i = 0
        while True:
            if cmd == 'M':
                cx, cy = nums[i], nums[i+1]; i += 2
                nodes.append((cx, cy)); sx, sy = cx, cy
            elif cmd == 'm':
                cx, cy = cx+nums[i], cy+nums[i+1]; i += 2
                nodes.append((cx, cy)); sx, sy = cx, cy
            elif cmd == 'L':
                cx, cy = nums[i], nums[i+1]; i += 2; nodes.append((cx, cy))
            elif cmd == 'l':
                cx, cy = cx+nums[i], cy+nums[i+1]; i += 2; nodes.append((cx, cy))
            elif cmd == 'H':
                cx = nums[i]; i += 1; nodes.append((cx, cy))
            elif cmd == 'h':
                cx += nums[i]; i += 1; nodes.append((cx, cy))
            elif cmd == 'V':
                cy = nums[i]; i += 1; nodes.append((cx, cy))
            elif cmd == 'v':
                cy += nums[i]; i += 1; nodes.append((cx, cy))
            elif cmd in ('C', 'c'):
                p0 = (cx, cy)
                if cmd == 'C':
                    p1 = (nums[i], nums[i+1])
                    p2 = (nums[i+2], nums[i+3])
                    p3 = (nums[i+4], nums[i+5])
                else:
                    p1 = (cx+nums[i], cy+nums[i+1])
                    p2 = (cx+nums[i+2], cy+nums[i+3])
                    p3 = (cx+nums[i+4], cy+nums[i+5])
                nodes.extend(_sample_cubic(p0, p1, p2, p3))
                cx, cy = p3; last_cp = p2; i += 6
            elif cmd in ('S', 's'):
                p0 = (cx, cy)
                p1 = (2*cx - last_cp[0], 2*cy - last_cp[1]) if last_cmd in ('C','c','S','s') else p0
                if cmd == 'S':
                    p2 = (nums[i], nums[i+1])
                    p3 = (nums[i+2], nums[i+3])
                else:
                    p2 = (cx+nums[i], cy+nums[i+1])
                    p3 = (cx+nums[i+2], cy+nums[i+3])
                nodes.extend(_sample_cubic(p0, p1, p2, p3))
                cx, cy = p3; last_cp = p2; i += 4
            elif cmd in ('Q', 'q'):
                p0 = (cx, cy)
                if cmd == 'Q':
                    p1 = (nums[i], nums[i+1])
                    p2 = (nums[i+2], nums[i+3])
                else:
                    p1 = (cx+nums[i], cy+nums[i+1])
                    p2 = (cx+nums[i+2], cy+nums[i+3])
                nodes.extend(_sample_quadratic(p0, p1, p2))
                cx, cy = p2; last_cp = p1; i += 4
            elif cmd in ('T', 't'):
                p0 = (cx, cy)
                p1 = (2*cx - last_cp[0], 2*cy - last_cp[1]) if last_cmd in ('Q','q','T','t') else p0
                if cmd == 'T':
                    p2 = (nums[i], nums[i+1])
                else:
                    p2 = (cx+nums[i], cy+nums[i+1])
                nodes.extend(_sample_quadratic(p0, p1, p2))
                cx, cy = p2; last_cp = p1; i += 2
            elif cmd in ('A', 'a'):
                rx, ry = nums[i], nums[i+1]
                x_rot = nums[i+2]
                large_arc = int(nums[i+3])
                sweep = int(nums[i+4])
                if cmd == 'A':
                    ex, ey = nums[i+5], nums[i+6]
                else:
                    ex, ey = cx+nums[i+5], cy+nums[i+6]
                nodes.extend(_sample_arc(cx, cy, rx, ry, x_rot, large_arc, sweep, ex, ey))
                cx, cy = ex, ey; i += 7
            elif cmd in ('Z', 'z'):
                cx, cy = sx, sy; break
            else:
                break
            last_cmd = cmd
            if i >= len(nums):
                break

    for tok in tokens:
        if tok in 'MmLlHhVvCcSsQqTtAaZz':
            consume(); last_cmd = cmd; cmd = tok; nums = []
        else:
            nums.append(float(tok))
    consume()
    return nodes


def outer_contour_nodes(filepath: str) -> list[tuple[float, float]]:
    """
    Parse all paths in the SVG, build Shapely polygons from every subpath,
    compute their union, and return the outer contour coordinates.
    """
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    polygons = []
    path_blocks = re.findall(r'<path\b(.*?)/?>', content, re.DOTALL)

    for block in path_blocks:
        d_m = re.search(r'\bd="([^"]*)"', block)
        if not d_m:
            continue
        d = d_m.group(1).strip()
        for subpath in split_subpaths(d):
            nodes = parse_path_nodes(subpath)
            if len(nodes) >= 3:
                try:
                    poly = Polygon(nodes)
                    if not poly.is_valid:
                        poly = make_valid(poly)
                    if not poly.is_empty:
                        polygons.append(poly)
                except Exception:
                    pass

    if not polygons:
        return []

    union = unary_union(polygons)

    # Extract exterior ring coordinates
    from shapely import get_parts
    polys = [g for g in get_parts(union) if g.geom_type == 'Polygon']
    if not polys:
        coords = []
    else:
        # Take the largest polygon as the outer contour
        largest = max(polys, key=lambda p: p.area)
        coords = list(largest.exterior.coords)

    return [(round(x, 5), round(y, 5)) for x, y in coords]


def write_output(filepath: str, nodes: list[tuple[float, float]]) -> str:
    """Write outer contour nodes to a _nodes.txt file. Returns output path."""
    base = os.path.splitext(filepath)[0]
    out_path = base + "_nodes.txt"
    fname = os.path.basename(filepath)

    lines = [f"SVG file: {fname}", "=" * (len(fname) + 10), "",
             f"Outer contour ({len(nodes)} nodes):"]
    for x, y in nodes:
        lines.append(f"  ({x}, {y})")
    lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return out_path


def main():
    if len(sys.argv) < 2:
        print("Usage: extract_svg_nodes.py <file_or_glob> [...]", file=sys.stderr)
        sys.exit(1)

    files = []
    for arg in sys.argv[1:]:
        expanded = glob.glob(arg)
        files.extend(expanded if expanded else [arg])

    if not files:
        print("No files matched.", file=sys.stderr)
        sys.exit(1)

    for filepath in sorted(files):
        if not os.path.isfile(filepath):
            print(f"Skipping (not a file): {filepath}", file=sys.stderr)
            continue
        nodes = outer_contour_nodes(filepath)
        out = write_output(filepath, nodes)
        print(f"  {os.path.basename(filepath)} -> {out}  ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()
