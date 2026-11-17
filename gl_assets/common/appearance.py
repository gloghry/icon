"""Build editable material nodes and explicit lighting in offline Blender."""
import math


def finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + " must be finite")
    return value


def vector(value, count, label):
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(label + " has an invalid dimension")
    return [finite(v, label) for v in value]


def material_nodes(material, graph):
    """Only known shader nodes; no script, file, texture or external inputs."""
    supported = {"ShaderNodeBsdfMetallic", "ShaderNodeBsdfPrincipled",
                 "ShaderNodeBevel", "ShaderNodeOutputMaterial"}
    nodes = {}
    material.node_tree.nodes.clear()
    for spec in graph["nodes"]:
        if spec["type"] not in supported or spec["name"] in nodes:
            raise ValueError("Unsupported or duplicate material node")
        node = material.node_tree.nodes.new(spec["type"])
        node.name = spec["name"]
        if "location" in spec:
            node.location = vector(spec["location"], 2, "Node location")
        for key, value in spec.get("properties", {}).items():
            if key not in {"distribution", "fresnel_type", "samples"}:
                raise ValueError("Unsupported material node property")
            setattr(node, key, value)
        for key, value in spec.get("inputs", {}).items():
            if isinstance(value, (list, tuple)):
                value = vector(value, len(value), "Shader input")
            else:
                finite(value, "Shader input")
            # Some Metallic sockets are disabled by the Fresnel mode but remain
            # part of the editable graph; Blender's name lookup skips them.
            socket = next((i for i in node.inputs if i.name == key), None)
            if socket is None:
                raise ValueError("Unsupported shader input: " + key)
            socket.default_value = value
        nodes[node.name] = node
    for source, output, target, socket in graph["links"]:
        material.node_tree.links.new(nodes[source].outputs[output], nodes[target].inputs[socket])


def lighting(scene, settings, center):
    import bpy
    from mathutils import Vector
    world = settings.get("world", {})
    background = scene.world.node_tree.nodes["Background"]
    background.inputs["Color"].default_value = vector(world.get("color", [0.65, 0.72, 0.85, 1]), 4, "World color")
    strength = finite(world.get("strength", 0.3), "World strength")
    if strength < 0:
        raise ValueError("World strength must be nonnegative")
    background.inputs["Strength"].default_value = strength
    defaults = [{"name": name, "location": position, "energy": energy, "size": size, "shape": "DISK"}
                for name, position, energy, size in [
                    ("Key softbox", [-4, -7, 12], 1300, 7),
                    ("Right fill", [9, -2, 7], 450, 5),
                    ("Rear edge", [-2, 7, 10], 900, 5)]]
    names = set()
    for spec in settings.get("lights", defaults):
        if spec["name"] in names or spec.get("type", "AREA") != "AREA":
            raise ValueError("Area lights need unique names")
        names.add(spec["name"])
        light = bpy.data.lights.new(spec["name"], "AREA")
        light.energy = finite(spec["energy"], "Light energy")
        light.size = finite(spec["size"], "Light size")
        if spec["energy"] < 0 or spec["size"] <= 0:
            raise ValueError("Light energy/size out of range")
        light.shape = spec.get("shape", "DISK")
        light.color = vector(spec.get("color", [1, 1, 1]), 3, "Light color")
        if "size_y" in spec:
            if finite(spec["size_y"], "Light height") <= 0:
                raise ValueError("Light height must be positive")
            light.size_y = spec["size_y"]
        if "spread" in spec:
            if not 0 <= finite(spec["spread"], "Light spread") <= math.pi + 1e-6:
                raise ValueError("Light spread out of range")
            light.spread = spec["spread"]
        light.normalize = spec.get("normalize", True)
        light.use_nodes = spec.get("use_nodes", False)
        obj = bpy.data.objects.new(spec["name"], light)
        scene.collection.objects.link(obj)
        obj.location = vector(spec["location"], 3, "Light location")
        if "rotation" in spec:
            obj.rotation_euler = vector(spec["rotation"], 3, "Light rotation")
        else:
            obj.rotation_euler = (center-obj.location).to_track_quat("-Z", "Y").to_euler()
        obj.scale = vector(spec.get("scale", [1, 1, 1]), 3, "Light scale")
