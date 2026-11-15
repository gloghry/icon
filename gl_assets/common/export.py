"""glTF 2.0 binary export. Authoring Z-up is rotated into glTF Y-up."""
import json
import struct


def strip_png_metadata(path):
    """Discard render timestamps/paths while preserving pixels and color data."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Expected a PNG render")
    result = bytearray(data[:8])
    offset = 8
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset+4:offset+8]
        if kind not in (b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME"):
            result.extend(data[offset:offset+length+12])
        offset += length + 12
    path.write_bytes(result)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_glb(path, asset):
    blob = bytearray()
    views, accessors, meshes, materials = [], [], [], []

    def accessor(data, fmt, component, kind, count, target, bounds=None):
        while len(blob) % 4:
            blob.append(0)
        offset = len(blob)
        blob.extend(struct.pack("<" + fmt * len(data), *data))
        views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(blob) - offset, "target": target})
        entry = {"bufferView": len(views) - 1, "componentType": component, "count": count, "type": kind}
        if bounds:
            entry.update(bounds)
        accessors.append(entry)
        return len(accessors) - 1

    for mesh in asset.meshes:
        # (x, y, z) -> (x, z, -y) is a rotation, preserving handedness.
        points = [(x, z, -y) for x, y, z in mesh.vertices]
        # Face-split vertices produce the original's crisp, flat surfaces.
        positions, normals, indices = [], [], []
        for tri in mesh.triangles:
            a, b, c = [points[i] for i in tri]
            u, v = [b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]
            n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            magnitude = sum(x*x for x in n)**0.5
            if not magnitude:
                raise ValueError("Cannot export degenerate triangle")
            normals.extend([x / magnitude for x in n] * 3)
            positions.extend((*a, *b, *c))
            indices.extend(range(len(indices), len(indices) + 3))
        bounds = {"min": [min(p[i] for p in points) for i in range(3)],
                  "max": [max(p[i] for p in points) for i in range(3)]}
        pos = accessor(positions, "f", 5126, "VEC3", len(positions)//3, 34962, bounds)
        norm = accessor(normals, "f", 5126, "VEC3", len(normals)//3, 34962)
        idx = accessor(indices, "I", 5125, "SCALAR", len(indices), 34963)
        m = mesh.material
        materials.append({"name": m.name, "pbrMetallicRoughness": {
            "baseColorFactor": m.color, "metallicFactor": m.metallic, "roughnessFactor": m.roughness},
            **({"alphaMode": "BLEND"} if m.color[3] < 1 else {})})
        meshes.append({"name": mesh.name, "primitives": [{"attributes": {"POSITION": pos, "NORMAL": norm},
                       "indices": idx, "material": len(materials)-1}]})
    while len(blob) % 4:
        blob.append(0)
    doc = {"asset": {"version": "2.0", "generator": "gl_assets"}, "scene": 0,
           "scenes": [{"nodes": list(range(len(meshes)))}],
           "nodes": [{"name": m.name, "mesh": i} for i, m in enumerate(asset.meshes)],
           "meshes": meshes, "materials": materials, "accessors": accessors, "bufferViews": views,
           "buffers": [{"byteLength": len(blob)}]}
    encoded = json.dumps(doc, separators=(",", ":"), allow_nan=False).encode()
    encoded += b" " * (-len(encoded) % 4)
    body = struct.pack("<I4s", len(encoded), b"JSON") + encoded + struct.pack("<I4s", len(blob), b"BIN\0") + blob
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12+len(body)) + body)
