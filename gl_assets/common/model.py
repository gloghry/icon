from dataclasses import dataclass, field
import math

AXES = {"up": "+Z", "g_plane": "XZ", "l_plane": "YZ", "units": "meters"}


@dataclass(frozen=True)
class Material:
    name: str
    color: tuple[float, float, float, float]
    metallic: float = 0.0
    roughness: float = 0.65
    shader: dict | None = None


@dataclass
class Mesh:
    name: str
    vertices: list[tuple[float, float, float]]
    triangles: list[tuple[int, int, int]]
    material: Material


@dataclass
class Asset:
    meshes: list[Mesh]
    metadata: dict = field(default_factory=dict)
    gameplay: dict | None = None

    @property
    def bounds(self):
        points = [v for mesh in self.meshes for v in mesh.vertices]
        return {"min": [min(p[i] for p in points) for i in range(3)],
                "max": [max(p[i] for p in points) for i in range(3)]}

    def validate(self):
        if not self.meshes:
            raise ValueError("Asset must contain at least one mesh")
        for mesh in self.meshes:
            if not mesh.vertices or not mesh.triangles:
                raise ValueError(f"Empty mesh: {mesh.name}")
            if any(len(v) != 3 or not all(math.isfinite(x) for x in v) for v in mesh.vertices):
                raise ValueError(f"Invalid vertices: {mesh.name}")
            if any(len(t) != 3 or any(not isinstance(i, int) or i < 0 or i >= len(mesh.vertices)
                                     for i in t) for t in mesh.triangles):
                raise ValueError(f"Invalid triangles: {mesh.name}")
            m = mesh.material
            if len(m.color) != 4 or not all(math.isfinite(x) and 0 <= x <= 1
                                          for x in (*m.color, m.metallic, m.roughness)):
                raise ValueError(f"Invalid material: {m.name}")


def positive(config, key):
    value = config[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{key} must be a positive finite number")
    return value
