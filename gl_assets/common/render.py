"""Deterministic orthographic software renderer, with a depth buffer."""
import math
import struct
import zlib
from .camera import CAMERAS

# Direction from the asset toward the camera in authoring coordinates.
LIGHT = (-0.4, -0.6, 1.0)
BACKGROUND = (242, 245, 250)


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def normalized(v):
    length = math.sqrt(dot(v, v))
    return tuple(x / length for x in v)


def write_png(path, asset, camera="isometric", size=512, direction=None):
    if camera not in CAMERAS:
        raise ValueError(f"Unknown camera: {camera}")
    if isinstance(size, bool) or not isinstance(size, int) or not 16 <= size <= 4096:
        raise ValueError("Render size must be an integer from 16 to 4096")
    forward = normalized(direction or CAMERAS[camera])
    right = normalized(cross((0, 1, 0) if camera == "top" else (0, 0, 1), forward))
    up = cross(forward, right)
    points = [v for mesh in asset.meshes for v in mesh.vertices]
    xs, ys = [dot(p, right) for p in points], [dot(p, up) for p in points]
    scale = 0.8 * size / max(max(xs)-min(xs), max(ys)-min(ys), 1e-9)
    cx, cy = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2

    def project(p):
        return (size/2 + (dot(p, right)-cx)*scale,
                size/2 - (dot(p, up)-cy)*scale, dot(p, forward))

    pixels = bytearray(BACKGROUND * (size*size))
    depth = [-math.inf] * (size*size)
    light = normalized(LIGHT)
    for mesh in asset.meshes:
        for tri in mesh.triangles:
            world = [mesh.vertices[i] for i in tri]
            n = cross(tuple(world[1][i]-world[0][i] for i in range(3)),
                      tuple(world[2][i]-world[0][i] for i in range(3)))
            if dot(n, forward) <= 0:
                continue
            intensity = 0.35 + 0.65 * max(0, dot(normalized(n), light))
            color = [round(255 * c * intensity) for c in mesh.material.color[:3]]
            a, b, c = [project(p) for p in world]
            denom = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
            if abs(denom) < 1e-10:
                continue
            for y in range(max(0, math.floor(min(a[1], b[1], c[1]))), min(size, math.ceil(max(a[1], b[1], c[1])))):
                for x in range(max(0, math.floor(min(a[0], b[0], c[0]))), min(size, math.ceil(max(a[0], b[0], c[0])))):
                    px, py = x+0.5, y+0.5
                    u = ((b[1]-c[1])*(px-c[0]) + (c[0]-b[0])*(py-c[1])) / denom
                    v = ((c[1]-a[1])*(px-c[0]) + (a[0]-c[0])*(py-c[1])) / denom
                    w = 1-u-v
                    if min(u, v, w) < -1e-8:
                        continue
                    z, index = u*a[2]+v*b[2]+w*c[2], y*size+x
                    if z > depth[index]:
                        depth[index] = z
                        pixels[index*3:index*3+3] = bytes(color)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind+data))

    raw = b"".join(b"\0" + pixels[y*size*3:(y+1)*size*3] for y in range(size))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
