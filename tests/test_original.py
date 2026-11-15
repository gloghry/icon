import copy
from collections import Counter
import random
import unittest

from gl_assets.common.camera import direction
from gl_assets.registry import discover


def front_contains(mesh, x, z):
    """Sample the actual mesh's front silhouette, independent of builder boxes."""
    for tri in mesh.triangles:
        a, b, c = [mesh.vertices[i] for i in tri]
        if any(p[1] != 0 for p in (a, b, c)):
            continue
        denominator = (b[2]-c[2])*(a[0]-c[0]) + (c[0]-b[0])*(a[2]-c[2])
        if not denominator:
            continue
        u = ((b[2]-c[2])*(x-c[0]) + (c[0]-b[0])*(z-c[2]))/denominator
        v = ((c[2]-a[2])*(x-c[0]) + (a[0]-c[0])*(z-c[2]))/denominator
        if min(u, v, 1-u-v) >= -1e-9:
            return True
    return False


class OriginalSculptureTests(unittest.TestCase):
    def setUp(self):
        self.variant = discover()['original']
        self.config = copy.deepcopy(self.variant.config)

    def mesh(self):
        return self.variant.builder()(self.config, random.Random(42)).meshes[0]

    def test_only_right_upright_descends_below_g(self):
        mesh = self.mesh()
        self.assertFalse(front_contains(mesh, 0.5, 2))
        self.assertFalse(front_contains(mesh, 2, 2))
        self.assertTrue(front_contains(mesh, 4, 2))
        self.assertTrue(front_contains(mesh, 0.5, 3.5))

    def test_g_bars_and_three_opening_gaps(self):
        mesh = self.mesh()
        for x, z in [(2, 7.5), (0.5, 6.5), (2, 3.5), (2.7, 5.5)]:
            self.assertTrue(front_contains(mesh, x, z), (x, z))
        for x, z in [(2.7, 6.5), (2.7, 4.5), (1.5, 5.5)]:
            self.assertFalse(front_contains(mesh, x, z), (x, z))

    def test_closed_surface_and_foot_direction(self):
        mesh = self.mesh()
        edges = Counter(tuple(sorted((mesh.vertices[t[i]], mesh.vertices[t[(i+1)%3]])))
                        for t in mesh.triangles for i in range(3))
        self.assertEqual(set(edges.values()), {2})
        foot_points = [p for p in mesh.vertices if p[1] > 1]
        self.assertTrue(foot_points)
        self.assertTrue(all(p[2] <= 1 and p[0] >= 3.5 for p in foot_points))
        self.assertEqual(min(p[1] for p in mesh.vertices), 0)

    def test_independent_inner_bar_parameter_and_square_stem(self):
        self.config['dimensions']['inner_bar_length'] = 1.5
        self.assertFalse(front_contains(self.mesh(), 2.7, 5.5))
        self.assertTrue(front_contains(self.mesh(), 3.2, 5.5))
        self.config['dimensions']['depth'] = 0.5
        with self.assertRaisesRegex(ValueError, 'square'):
            self.mesh()

    def test_invalid_tip_or_bevel_rejected(self):
        for name, value in [('inner_bar_length', 3.5), ('bevel_size', 0.5)]:
            with self.subTest(name=name):
                self.config = copy.deepcopy(self.variant.config)
                self.config['dimensions'][name] = value
                with self.assertRaises(ValueError):
                    self.mesh()

    def test_camera_projects_plus_y_up_and_right(self):
        from gl_assets.common.render import cross, normalized
        forward = normalized(direction(self.config, 'isometric'))
        right = normalized(cross((0, 0, 1), forward))
        up = cross(forward, right)
        self.assertGreater(right[1], 0)
        self.assertGreater(up[1], 0)
        self.assertGreater(right[0], 0)  # G's X direction remains readable.
