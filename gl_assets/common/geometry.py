"""Block union builder; other structures should use their own builders."""
from .model import Mesh


def block_union(name, boxes, material):
    """Extract the exterior of an axis-aligned box union, without internal faces.

    Boxes are (xmin, ymin, zmin, xmax, ymax, zmax). Coordinate compression
    supports independent proportions without imposing a fixed voxel size.
    """
    axes = [sorted({b[i] for b in boxes} | {b[i + 3] for b in boxes}) for i in range(3)]
    occupied = set()
    for x in range(len(axes[0]) - 1):
        for y in range(len(axes[1]) - 1):
            for z in range(len(axes[2]) - 1):
                p = [(axes[i][j] + axes[i][j + 1]) / 2 for i, j in enumerate((x, y, z))]
                if any(all(b[i] <= p[i] <= b[i + 3] for i in range(3)) for b in boxes):
                    occupied.add((x, y, z))
    vertices, triangles = [], []
    # Each face is wound counterclockwise as seen from outside.
    faces = [((-1, 0, 0), (0, 4, 6, 2)), ((1, 0, 0), (1, 3, 7, 5)),
             ((0, -1, 0), (0, 1, 5, 4)), ((0, 1, 0), (2, 6, 7, 3)),
             ((0, 0, -1), (0, 2, 3, 1)), ((0, 0, 1), (4, 5, 7, 6))]
    for cell in sorted(occupied):
        corners = [tuple(axes[i][cell[i] + ((k >> i) & 1)] for i in range(3)) for k in range(8)]
        for delta, indices in faces:
            if tuple(cell[i] + delta[i] for i in range(3)) in occupied:
                continue
            start = len(vertices)
            vertices.extend(corners[i] for i in indices)
            triangles.extend([(start, start + 1, start + 2), (start, start + 2, start + 3)])
    return Mesh(name, vertices, triangles, material)
