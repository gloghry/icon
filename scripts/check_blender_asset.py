"""Run with Blender after opening generated/original/asset.blend."""
import json
import math
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


def close(actual, expected, label):
    if isinstance(expected, (list, tuple)):
        assert len(actual) == len(expected), label
        for a, b in zip(actual, expected):
            close(a, b, label)
    elif isinstance(expected, (float, int)) and not isinstance(expected, bool):
        assert math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-6), label
    else:
        assert actual == expected, label


graph = config["material"].get("shader")
if graph:
    tree = obj.data.materials[0].node_tree
    assert {n.name for n in tree.nodes} == {n["name"] for n in graph["nodes"]}
    for spec in graph["nodes"]:
        node = tree.nodes[spec["name"]]
        assert node.bl_idname == spec["type"]
        for name, value in spec.get("properties", {}).items():
            close(getattr(node, name), value, "Shader property: " + name)
        for name, value in spec.get("inputs", {}).items():
            socket = next(i for i in node.inputs if i.name == name)
            close(socket.default_value, value, "Shader input: " + name)
    links = [[l.from_node.name, l.from_socket.name, l.to_node.name, l.to_socket.name] for l in tree.links]
    assert sorted(links) == sorted(graph["links"]), "Saved shader wiring differs"
settings = config.get("lighting")
if settings:
    lights = {o.name: o for o in bpy.context.scene.objects if o.type == "LIGHT"}
    assert set(lights) == {s["name"] for s in settings["lights"]}
    for spec in settings["lights"]:
        light = lights[spec["name"]]
        for key in ("energy", "color", "shape", "size", "size_y", "spread", "normalize", "use_nodes"):
            if key in spec:
                close(getattr(light.data, key), spec[key], "Light property: " + key)
        for key, attribute in (("location", "location"), ("rotation", "rotation_euler"), ("scale", "scale")):
            close(getattr(light, attribute), spec[key], "Light transform: " + key)
    world = bpy.context.scene.world.node_tree.nodes["Background"]
    close(world.inputs["Color"].default_value, settings["world"]["color"], "World color")
    close(world.inputs["Strength"].default_value, settings["world"]["strength"], "World strength")
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
