# GL sculpture assets

The `original` variant follows Garett's supplied and approved
[sculpture reference](gl_assets/variants/original/reference/approved-sculpture.png).
Its elevated squared-C G lies in X–Z (Z up). The left back ends at the lower
bar; only the right return descends as the L's square stem. A compact foot
extends along +Y. The inner bar stops before the left back and has clear space
above and below it.

Blender runs **offline**. Websites consume prebuilt assets; no Blender, Python,
WebGL, or animation code is needed in a Jekyll build or the visitor's browser.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the issue/PR workflow.

## Regenerate

Use Python 3.10+ and Blender **4.5.3 LTS** for the reviewed rendering baseline:

```sh
python3 -m gl_assets list
python3 -m gl_assets generate original --blender /path/to/blender
python3 -m gl_assets generate all --blender /path/to/blender
python3 -m unittest discover -s tests -v
```

If Blender is on PATH, omit `--blender`. Blender starts with factory settings,
uses CPU Cycles with four threads, and needs no add-ons or network. The entry
point can also run directly:

```sh
blender --background --factory-startup --threads 4 --python-exit-code 1 \
  --python gl_assets/blender_build.py -- generate original
blender --background generated/original/asset.blend --python-exit-code 1 \
  --python scripts/check_blender_asset.py
```

Each build writes only `generated/<variant>/`, with a .blend source, a static
GLB of the evaluated beveled mesh, transparent PNG front/side/three-quarter
(`isometric`) renders from that same mesh, JSON metadata and effective config,
and a SHA-256 manifest. Renders are orthographic. In the three-quarter view,
the G is upper-left and the +Y foot projects up-right. Export failures preserve
the previous build; completed builds replace that variant's output directory.
Do not build the same variant concurrently into the same output root.

The editable .blend retains the base solid, non-destructive bevel/normal
modifiers, one material, lighting, and the three-quarter camera. The build
checks a single connected manifold solid with positive volume. GLB rotates
authoring `(x, y, z)` to glTF Y-up `(x, z, -y)`; metadata remains Z-up, in meters.

## Parameters and reproducibility

Each variant owns its [configuration](gl_assets/variants/original/config.json).
Copy it to experiment:

```sh
python3 -m gl_assets generate original --config /tmp/original.json \
  --seed 42 --output-dir /tmp/gl-assets --blender /path/to/blender
```

`--config` is a full replacement for one named variant. `--seed` overrides its
seed. The original exposes:

| Parameter | Meaning |
| --- | --- |
| `stroke`, `depth` | Bar width and G depth; equal for a square X–Y stem |
| `g_width`, `g_height` | Overall G dimensions |
| `g_elevation` | Stem extension from floor to underside of the G |
| `inner_bar_length` | Total inward bar length including the right return |
| `l_length` | Overall +Y foot length including the stem depth |
| `bevel_size` | Small edge radius; 0–10% of stroke, default 0.025 |
| `render.camera` | Three-quarter azimuth from -Y toward +X, and elevation, in degrees |
| `render.size`, `samples`, `padding` | Square preview resolution, Cycles samples, margin fraction |

The inner bar is centered vertically in the G opening. G width/height must
exceed three strokes and the inner tip must leave a gap before the left back.
Every procedural random choice must use the per-build `random.Random(seed)`;
adding a variant cannot change another's random stream. Geometry and renders
are reproducible with the pinned Blender version, source, config and seed on
the same platform. Blender .blend containers can contain session-specific
state, and rendered pixels may vary between Blender versions/platforms; do not
promise cross-platform byte identity. The manifest records actual file hashes.

A fast dependency-free draft renderer remains available:

```sh
python3 -m gl_assets generate original --backend preview --output-dir /tmp/gl-draft
```

Drafts omit the .blend and bevels; final assets use Blender.

## Add a variant

Create `gl_assets/variants/<unique-kebab-case-name>/config.json` and `builder.py`.
Discovery is automatic; `all` is reserved. The config's `name` must match its
directory and specify an integer `seed` and supported outputs (`png`, `glb`,
`metadata`, `blend`). Expose `build(config, rng) -> Asset` using the shared
`Mesh`/`Material` types. Supply geometry, materials, optional decoration meshes,
JSON metadata, and optional `gameplay` metadata. No existing variant needs editing.

Use separate geometry builders for fundamentally different structures. The
original uses an exterior block union, with no internal faces, followed by
Blender welding and tiny bevels. Other builders can return entirely different
meshes and materials. Axes/dimensions, camera presets, lighting, rendering,
GLB export, and output isolation are shared in `gl_assets/common/` and
`pipeline.py`. Keep variant-specific resources beside its builder, and all
generated files beneath that variant's output directory. Source directories
cannot be output destinations. Animation and interaction belong in
`behaviors/` or a consuming app, separately from the asset.

Hollow-tube ball puzzle (#6) and moss/roots/trees (#7) remain open design tasks;
neither is registered or implemented. Proportions and structures can differ
while retaining the elevated G, perpendicular lower L, and shared stem identity.
