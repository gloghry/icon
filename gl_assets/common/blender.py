"""Offline Blender adapter. Geometry builders have no dependency on bpy."""
import math

import bmesh
import bpy
from mathutils import Vector

from .camera import direction, framing
from .export import strip_png_metadata
from .model import Asset, Mesh


def topology(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    remaining = set(bm.verts)
    components = 0
    while remaining:
        components += 1
        pending = [remaining.pop()]
        while pending:
            vertex = pending.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in remaining:
                    remaining.remove(other)
                    pending.append(other)
    result = {"components": components, "non_manifold_edges": sum(not e.is_manifold for e in bm.edges),
              "vertices": len(bm.verts), "edges": len(bm.edges), "faces": len(bm.faces),
              "volume": bm.calc_volume(signed=True)}
    bm.free()
    return result


class BlenderBackend:
    def prepare(self, asset, config):
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        self.config, self.objects = config, []
        evaluated = []
        checks = []
        for mesh in asset.meshes:
            # The preview mesh deliberately splits vertices by face. Weld exact
            # authoring coordinates before modifiers see the surface topology.
            unique = list(dict.fromkeys(mesh.vertices))
            lookup = {v: i for i, v in enumerate(unique)}
            triangles = [tuple(lookup[mesh.vertices[i]] for i in t) for t in mesh.triangles]
            data = bpy.data.meshes.new(mesh.name)
            data.from_pydata(unique, [], triangles)
            bm = bmesh.new()
            bm.from_mesh(data)
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
            bmesh.ops.dissolve_limit(bm, angle_limit=1e-6, use_dissolve_boundaries=False,
                                     verts=list(bm.verts), edges=list(bm.edges), delimit=set())
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            bm.to_mesh(data)
            bm.free()
            obj = bpy.data.objects.new(mesh.name, data)
            bpy.context.collection.objects.link(obj)
            self.objects.append(obj)
            material = bpy.data.materials.new(mesh.material.name)
            material.use_nodes = True
            principled = material.node_tree.nodes.get("Principled BSDF")
            principled.inputs["Base Color"].default_value = mesh.material.color
            principled.inputs["Metallic"].default_value = mesh.material.metallic
            principled.inputs["Roughness"].default_value = mesh.material.roughness
            obj.data.materials.append(material)
            width = config.get("dimensions", {}).get("bevel_size", 0)
            if width:
                bevel = obj.modifiers.new("Tiny edge highlights", "BEVEL")
                bevel.width, bevel.segments = width, 3
                bevel.limit_method = "ANGLE"
                bevel.angle_limit = math.radians(30)
                bevel.harden_normals = True
                weighted = obj.modifiers.new("Keep planar faces flat", "WEIGHTED_NORMAL")
                weighted.keep_sharp = True
            depsgraph = bpy.context.evaluated_depsgraph_get()
            depsgraph.update()
            evaluated_obj = obj.evaluated_get(depsgraph)
            final = evaluated_obj.to_mesh()
            check = topology(final)
            if check["non_manifold_edges"] or check["volume"] <= 0:
                raise ValueError(f"Mesh is not a closed solid: {check}")
            if config["name"] == "original" and check["components"] != 1:
                raise ValueError("Original sculpture must be one continuous solid")
            checks.append(check)
            final.calc_loop_triangles()
            evaluated.append(Mesh(mesh.name, [tuple(v.co) for v in final.vertices],
                                  [tuple(t.vertices) for t in final.loop_triangles], mesh.material))
            evaluated_obj.to_mesh_clear()
        self.asset = Asset(evaluated, dict(asset.metadata), asset.gameplay)
        self.asset.metadata["topology"] = checks
        self.asset.metadata["toolchain"] = {"blender": bpy.app.version_string, "backend": "cycles-cpu"}
        self.setup_scene()
        return self.asset

    def setup_scene(self):
        scene = bpy.context.scene
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = self.config.get("render", {}).get("samples", 48)
        scene.cycles.seed = self.config["seed"] % (2**31)
        scene.cycles.use_animated_seed = False
        scene.cycles.use_adaptive_sampling = False
        scene.cycles.use_denoising = True
        scene.render.film_transparent = True
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.image_settings.color_depth = "8"
        scene.render.image_settings.compression = 90
        scene.render.resolution_percentage = 100
        scene.render.use_file_extension = True
        scene.render.threads_mode, scene.render.threads = "FIXED", 4
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
        scene.world.use_nodes = True
        scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.65, 0.72, 0.85, 1)
        scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.3
        bounds = self.asset.bounds
        self.center = Vector([(a+b)/2 for a,b in zip(bounds["min"], bounds["max"])])
        for name, position, energy, size in [
            ("Key softbox", (-4, -7, 12), 1300, 7),
            ("Right fill", (9, -2, 7), 450, 5),
            ("Rear edge", (-2, 7, 10), 900, 5),
        ]:
            light = bpy.data.lights.new(name, "AREA")
            light.energy, light.shape, light.size = energy, "DISK", size
            obj = bpy.data.objects.new(name, light)
            scene.collection.objects.link(obj)
            obj.location = position
            obj.rotation_euler = (self.center-obj.location).to_track_quat("-Z", "Y").to_euler()
        camera = bpy.data.cameras.new("Orthographic")
        camera.type = "ORTHO"
        self.camera = bpy.data.objects.new("Orthographic", camera)
        scene.collection.objects.link(self.camera)
        scene.camera = self.camera
        self.set_camera("isometric", self.config.get("render", {}).get("size", 640))

    def set_camera(self, preset, size):
        if isinstance(size, bool) or not isinstance(size, int) or not 16 <= size <= 4096:
            raise ValueError("Render size must be an integer from 16 to 4096")
        scene = bpy.context.scene
        forward = Vector(direction(self.config, preset)).normalized()
        right = Vector((0, 1, 0) if preset == "top" else (0, 0, 1)).cross(forward).normalized()
        up = forward.cross(right)
        points = [Vector(v) for mesh in self.asset.meshes for v in mesh.vertices]
        xs, ys = [p.dot(right) for p in points], [p.dot(up) for p in points]
        target = self.center + right*((max(xs)+min(xs))/2-self.center.dot(right))
        target += up*((max(ys)+min(ys))/2-self.center.dot(up))
        saved_framing = framing(self.config, preset)
        if saved_framing:
            target = Vector(saved_framing[0])
        self.camera.location = target + forward*30
        self.camera.rotation_euler = (-forward).to_track_quat("-Z", "Y").to_euler()
        padding = self.config.get("render", {}).get("padding", 0.08)
        if not isinstance(padding, (int, float)) or not 0 <= padding < 0.4:
            raise ValueError("render.padding must be between 0 and 0.4")
        self.camera.data.ortho_scale = max(max(xs)-min(xs), max(ys)-min(ys))/(1-2*padding)
        if saved_framing:
            self.camera.data.ortho_scale = saved_framing[1]
        scene.render.resolution_x = scene.render.resolution_y = size
        scene.camera.data.lens = 50

    def render(self, path, camera, size):
        self.set_camera(camera, size)
        bpy.context.scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        strip_png_metadata(path)

    def save(self, path):
        self.set_camera("isometric", self.config.get("render", {}).get("size", 640))
        bpy.context.scene.render.filepath = "//renders/isometric.png"
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False)
