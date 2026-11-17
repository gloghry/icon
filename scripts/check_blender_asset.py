"""Run with Blender after opening generated/original/asset.blend."""
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gl_assets.common.blender import topology
from gl_assets.common.camera import direction, framing

config = json.loads(Path(bpy.data.filepath).with_name("config.json").read_text())
d = config["dimensions"]
objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
assert len(objects) == 1, "Original sculpture must be one mesh object"
obj = objects[0]
evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
mesh = evaluated.to_mesh()
check = topology(mesh)
assert check["components"] == 1 and check["non_manifold_edges"] == 0 and check["volume"] > 0, check
assert len(obj.data.materials) == 1
assert bpy.context.scene.camera.data.type == "ORTHO"
camera = bpy.context.scene.camera
forward = camera.matrix_world.to_quaternion() @ Vector((0, 0, 1))
assert (forward - Vector(direction(config, "isometric"))).length < 1e-6, "Saved camera angle differs from config"
saved_framing = framing(config, "isometric")
if saved_framing:
    target, scale = saved_framing
    assert (camera.location - forward*30 - Vector(target)).length < 1e-5, "Saved camera target differs from config"
    assert abs(camera.data.ortho_scale - scale) < 1e-5, "Saved camera span differs from config"
s, w, e = d["stroke"], d["g_width"], d["g_elevation"]
def hit(x, z):
    return evaluated.ray_cast(Vector((x, -10, z)), Vector((0, 1, 0)))[0]
assert not hit(s/2, e/2), "Left back must not descend beneath G"
assert hit(w-s/2, e/2), "Only right upright must continue as L stem"
assert hit(s/2, e+s/2), "C back meets lower G bar"
return_top = e+(d["g_height"]+s)/2
inner_x = w-d["inner_bar_length"]+s/3
assert hit(inner_x, return_top-s/2), "Inner bar is present"
assert not hit(inner_x, (e+s+return_top-s)/2), "Gap below inner bar"
assert not hit(inner_x, (return_top+e+d["g_height"]-s)/2), "Gap above inner bar"
evaluated.to_mesh_clear()
print("Validated reopened editable .blend:", json.dumps(check, sort_keys=True))
