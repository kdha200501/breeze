---
name: breeze-cursor-build
description: >-
    Knowledge of the Breeze cursor theme build pipeline: rendering PNGs with Inkscape,
    generating XCursor binaries and scalable SVG cursors with generate_cursors (Python 3 + PySide6),
    hotspot extraction, animated cursor grouping, alias symlinks, output layout, and the
    jacks-customizations override pattern. Use when the user asks about building, modifying,
    or understanding the Breeze cursor build process.
user-invocable: false
---

# Breeze Cursor Theme — Build Pipeline

> **Manual step**: Building is NOT run by CMake. You run the shared `build.sh` directly.
> Prerequisites: **Inkscape** (for PNG rasterisation) and **xcursorgen** (for XCursor binary compilation).
>
> **Each theme variant is a self-contained directory** (e.g. `Breeze/`, `Breeze_Light/`),
> each holding its own `src/svg`, `src/index.theme`, and `src/alias.list`.
>
> **Before building**, ask the user which variant/theme to build (e.g. `Breeze` or `Breeze Light`).
>
> **To build a variant**: `cd` into the variant directory and run `../src/build.sh`.
> `build.sh` resolves `src/svg`, `src/index.theme`, `src/alias.list` relative to the **CWD** (the
> variant dir), while its own tooling (`generate_cursors`) is located via its own path.
>
> The theme output directory name comes from the `Name=` value in the variant's `src/index.theme`,
> with spaces replaced by underscores (e.g. `Name=Breeze Light` → `Breeze_Light`).

## Directory layout (source)

```
cursors/
  src/                      ← SHARED build tooling (not per-variant)
    build.sh                ← top-level build driver
    generate_cursors        ← Python 3 + PySide6 per-cursor compiler
    kcursorgen, clean_svg, diff_pixmaps, etc.

  Breeze/                   ← upstream variant (source SVGs only; no CMakeLists.txt)
    src/
      svg/                  ← one SVG per cursor shape; animated frames as wait-01.svg…wait-23.svg
      index.theme           ← Name=Breeze
      alias.list            ← whitespace-separated pairs: <alias> <target>
    Breeze/                 ← build OUTPUT (theme dir, named from Name=)

  Breeze_Light/             ← another upstream variant
    src/
      svg/
      index.theme           ← Name=Breeze Light
      alias.list
    Breeze_Light/           ← build OUTPUT

  jacks-customizations/     ← OVERRIDE variant; installs in place of Breeze
    CMakeLists.txt          ← install(DIRECTORY Breeze/ DESTINATION …/breeze_cursors)
    Breeze/                 ← pre-built theme output (checked in; not generated at CMake time)
      index.theme
      cursors/              ← XCursor binaries
      cursors_scalable/     ← SVG cursors + metadata.json
    src/                    ← source material (SVGs, alias list, index.theme)
```

Key: the **shared** `build.sh` and `generate_cursors` live in `cursors/src/`; each **variant** carries
its own `src/svg`, `src/index.theme`, and `src/alias.list`.

### jacks-customizations override pattern

`jacks-customizations` replaces the upstream `Breeze` cursor theme at install time.
`cursors/CMakeLists.txt` must reference it **instead of** `Breeze`:

```cmake
add_subdirectory(jacks-customizations)   # replaces add_subdirectory(Breeze)
add_subdirectory(Breeze_Light)
```

The pre-built output in `jacks-customizations/Breeze/` is built the same way as any variant
(run `../src/build.sh` from `jacks-customizations/`), then committed.

### SVG authoring requirements for jacks-customizations

When editing SVGs in `jacks-customizations/src/svg/` with Inkscape, always **export as Plain SVG**
(File → Save a Copy → Plain SVG) before running the build. Inkscape's native `.svg` format embeds
Live Path Effects (`inkscape:path-effect`), `sodipodi:` extensions, and large `<defs>` blocks that
are not understood by `QSvgRenderer` / librsvg — the renderer used during `generate_cursors` and
by KWin at runtime. Saving as Plain SVG flattens all LPEs into standard `d=` path data.

## Step 1 — Render PNGs (`build.sh:44–64`)

`build.sh` (run from the variant dir) drives Inkscape in `--shell` mode to rasterise every SVG for
every scale. For each `src/svg/*.svg` it emits one PNG per scale:

- **Scales** (`SCALES`, `build.sh:13`): `50 75 100 125 150 175 200 225 250 275 300`
- **REAL_SIZE**: `32` px (the base pixel size used for rasterisation)
- PNG pixel size per scale: `REAL_SIZE * scale / 100` (e.g. scale 200 → 64 px)
- Output path (relative to the variant dir): `build/x{scale}/{name}.png`
- Renders are cached: a PNG whose mtime is older than its SVG is skipped, so re-running
  `build.sh` is incremental.

## Step 2 — Generate the theme (`build.sh:66–73`)

1. Reads the variant's `src/index.theme`, extracting the first `Name=` value (e.g. `Breeze Light`).
2. Replaces spaces with underscores → theme output directory name (e.g. `Breeze_Light`).
   Since the variant dir and the theme dir can share a name, this is why the output often nests as
   `Breeze_Light/Breeze_Light/`.
3. Removes any existing output dir (`rm -rf "$OUTPUT"`), recreates it, and invokes the shared
   `generate_cursors`:

    ```
    <svg cursor dir> <pixmap dir> <xcursor output dir> <svg cursor output dir> <base size> <animation frame time> <scales>
    ```

    `build.sh:72` calls it as `$BIN_DIR/generate_cursors`, where `BIN_DIR` is the directory holding
    `build.sh` — i.e. from the variant dir this resolves to `../src/generate_cursors`. The concrete
    arguments are `src/svg  build  <ThemeName>/cursors  <ThemeName>/cursors_scalable  24  30  50 75 … 300`.

## Step 3 — Per-cursor compile (`generate_cursors:35–96`)

For each cursor name:

1. **Groups** a base SVG with any numbered frame files (e.g. `wait-01.svg`…`wait-23.svg`) into a
   single animated cursor entry; the first sorted file (e.g. `wait-01.svg`) seeds the group and the
   remaining frames are collected via the `<basename>-[0-9]*.svg` glob.
2. **Hotspot extraction**: resolves the element with `id="hotspot"` (an invisible rectangle per the
   README; any hotspot element works) via `transformForElement("hotspot").map(boundsOnElement(...))`.
   The raw result is in SVG user-coordinate space; `generate_cursors` normalises it to rendered
   pixel space using the SVG's `viewBoxF()` and `defaultSize()`:
   `hotspot_px = (hotspot_svg - vb.topLeft()) / vb.size() * defaultSize()`.
   This is a no-op for standard Breeze SVGs (`viewBox="0 0 32 32"`) but required for SVGs with a
   different viewBox (e.g. a larger Inkscape canvas).
   `HOTSPOT_DISPLACE = 1` nudges the hotspot +1/100 px before flooring to avoid off-by-one errors
   when the cursor is scaled.
3. **Config file**: writes `build/config/{name}.config` — one line per scale per frame:
   ```
   <size> <hotspot_x> <hotspot_y> x{scale}/{frame}.png [delay_ms]
   ```
   Here `<size> = floor(nominal_size * scale / 100)` with **`nominal_size = 24`** (a different
   base size than the `REAL_SIZE = 32` used for the PNGs). Animation frame delay is **30 ms**.
4. **XCursor binary**: runs
   `xcursorgen -p build build/config/{name}.config <ThemeName>/cursors/{name}`
   → `Xcursor data version 1.0` binary.
5. **Scalable SVG cursor**: copies each source SVG → `cursors_scalable/{name}/{frame}.svg` and writes
   `metadata.json` with `filename`, `hotspot_x`, `hotspot_y`, **`nominal_size`**, and (for animated
   cursors) `delay`. **`nominal_size` is required in every frame** — for both static and animated
   cursors. If it is missing, KWin cannot scale the cursor and falls back to the system default.

   > **Note**: the current `generate_cursors` script omits `nominal_size` from animated cursor
   > frames (a known bug). When building `jacks-customizations`, verify that every frame in every
   > animated cursor's `metadata.json` includes `"nominal_size": 24` before committing the output.
   > Animated cursors affected: `wait`, `progress` (and all their alias symlinks).

   Correct animated `metadata.json` format:
   ```json
   [
       {
           "filename": "wait-01.svg",
           "hotspot_x": 15.99,
           "hotspot_y": 16.0,
           "delay": 30,
           "nominal_size": 24
       },
       ...
   ]
   ```

## Step 4 — Aliases + index (`build.sh:75–103`)

- Reads the variant's `src/alias.list` (pairs: `<alias> <target>`), e.g.:
  ```
  arrow default
  pointer default
  00000000000000020006000e7e9ffc3f progress
  ```
- Creates symlinks in both `<ThemeName>/cursors/` and `<ThemeName>/cursors_scalable/` for any alias
  not already present.
  Hex-named entries in the output are alias symlinks for legacy cursor-name compatibility.
- Copies the variant's `src/index.theme` → `<ThemeName>/index.theme`.

## Step 5 — Cleanup (after the build is verified)

`build.sh` leaves the temporary `build/` artefact **in the variant directory** you ran it from
(the CWD): `x{scale}/*.png` + `config/*.config`. **Do not leave it behind** — once the build
completes successfully (you see `COMPLETE!`), remove it immediately:

```sh
# from the variant dir that CONTAINS src/, build/ and the theme output:
rm -rf build                            # e.g. cursors/Breeze/ or cursors/foo/
```

Because `build.sh` resolves `src/` relative to the CWD, `build/` is created in the variant directory,
so run the cleanup **there** (not from `cursors/`).

If a rebuild is needed, the PNG renders are regenerated (the cache lives in `build/`, so a clean
rebuild re-renders all SVGs). Keep `<ThemeName>/` (the finished theme output, e.g. `Breeze/`)
around for inspection; a rebuild already recreates it (see `build.sh:69 rm -rf "$OUTPUT"`).

**Failed builds**: if `build.sh` exits before `COMPLETE!`, keep `build/` as-is — it preserves the
last good PNG cache for the next incremental rebuild; investigate the failure before deleting it.

## Output layout

```
Breeze_Light/                  ← theme output (named from Name=), created inside the variant dir
  index.theme
  cursors/
    default                    ← XCursor binary
    arrow -> default           ← symlink alias
    00000000…3f -> progress    ← hex alias symlink
    …
  cursors_scalable/
    default/
      default.svg
      metadata.json
    …
```

## Key constants (build.sh)

| Constant      | Value                          | Meaning                          |
|---------------|--------------------------------|----------------------------------|
| `REAL_SIZE`   | `32`                           | Base pixel size for PNG render   |
| `NOMINAL_SIZE`| `24`                           | Base size reported in XCursor config + `nominal_size` in metadata |
| `SCALES`      | `50 75 100 125 150 175 200 225 250 275 300` | % scales to render |
| Frame delay   | `30` ms                        | Passed to `generate_cursors`     |
| `HOTSPOT_DISPLACE` | `1`                     | +1/100 px hotspot nudge before floor |

`HOTSPOT_DISPLACE` lives in `generate_cursors:16`, not `build.sh`.
