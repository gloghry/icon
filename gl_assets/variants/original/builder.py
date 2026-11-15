"""Original block logo; no animation or runtime dependencies."""
from gl_assets.common.geometry import block_union
from gl_assets.common.model import AXES, Asset, Material, positive
import math


def build(config, rng):
    # rng is local to this build; reserved for reproducible decorations.
    d = config["dimensions"]
    s, depth, w, h, elevation, length = [positive(d, k) for k in
        ("stroke", "depth", "g_width", "g_height", "g_elevation", "l_length")]
    if w <= 3 * s or h <= 3 * s or length <= depth:
        raise ValueError("G width/height must exceed 3 strokes; L length must exceed depth")
    if not math.isclose(depth, s, rel_tol=1e-9):
        raise ValueError("depth must equal stroke for the square X–Y shared stem")
    inner_length = positive(d, "inner_bar_length")
    if not s < inner_length < w - s:
        raise ValueError("inner_bar_length must exceed stroke and stop short of the left back")
    bevel = d["bevel_size"]
    if isinstance(bevel, bool) or not isinstance(bevel, (int, float)) or not math.isfinite(bevel) or not 0 <= bevel <= s * 0.1:
        raise ValueError("bevel_size must be between zero and 10% of stroke")
    if elevation <= s:
        raise ValueError("g_elevation (stem extension) must exceed stroke")
    top = elevation + h
    # Center the inner bar within the opening, leaving equal clear space
    # above and below. The right return continues down as the L's stem.
    return_top = elevation + (h + s) / 2
    boxes = [
        (0, 0, elevation, s, depth, top),                # C back ends at G base
        (0, 0, top - s, w, depth, top),                  # G cap
        (0, 0, elevation, w, depth, elevation + s),       # G base
        (w - s, 0, 0, w, depth, return_top),             # right return / shared stem
        (w - inner_length, 0, return_top - s, w, depth, return_top),
        (w - s, 0, 0, w, length, s),                     # short L foot toward +Y
    ]
    m = config["material"]
    material = Material(m["name"], tuple(m["color"]), m["metallic"], m["roughness"])
    # Future decorations can be separate meshes in Asset.meshes. Fundamentally
    # different variants should implement their own geometry builder.
    return Asset([block_union("GL", boxes, material)], {
        "identity": {**AXES, "g_elevation": elevation,
                     "shared_stem": {"min": [w-s, 0, 0], "max": [w, depth, return_top]},
                     "l_foot_direction": "+Y"},
        "dimensions": d,
    })
