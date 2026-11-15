import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from gl_assets.pipeline import generate
from gl_assets.__main__ import main
from gl_assets.registry import discover
from gl_assets.common.geometry import block_union
from gl_assets.common.model import Material


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = discover()["original"]

    def config(self):
        config = copy.deepcopy(self.original.config)
        config["outputs"] = [o for o in config["outputs"] if o != "blend"]
        config["render"]["size"] = 48
        return config

    def snapshot(self, directory):
        return {p.relative_to(directory).as_posix(): p.read_bytes()
                for p in directory.rglob("*") if p.is_file()}

    def test_reproducible_exports_and_glb_structure(self):
        output = generate(self.original, self.root, config=self.config())
        before = self.snapshot(output)
        generate(self.original, self.root, config=self.config())
        self.assertEqual(before, self.snapshot(output))
        glb = before["asset.glb"]
        magic, version, length = struct.unpack_from("<4sII", glb)
        self.assertEqual((magic, version, length), (b"glTF", 2, len(glb)))
        json_length, kind = struct.unpack_from("<I4s", glb, 12)
        self.assertEqual(kind, b"JSON")
        doc = json.loads(glb[20:20+json_length])
        binary_length, kind = struct.unpack_from("<I4s", glb, 20+json_length)
        self.assertEqual(kind, b"BIN\0")
        self.assertEqual(binary_length, doc["buffers"][0]["byteLength"])
        for view in doc["bufferViews"]:
            self.assertEqual(view["byteOffset"] % 4, 0)
            self.assertLessEqual(view["byteOffset"] + view["byteLength"], binary_length)
        self.assertEqual(doc["accessors"][0]["min"], [0, 0, -3.6])
        self.assertEqual(doc["accessors"][0]["max"], [4.5, 8, 0])
        png = before["renders/isometric.png"]
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack_from(">II", png, 16), (48, 48))
        metadata = json.loads(before["metadata.json"])
        self.assertEqual(metadata["asset"]["identity"]["g_elevation"], 3)
        self.assertIsNone(metadata["gameplay"])

    def test_discovery_seed_and_variant_isolation(self):
        sources = self.root / "variants"
        for name in ("first", "second"):
            directory = sources / name
            directory.mkdir(parents=True)
            (directory / "builder.py").write_text(
                'from gl_assets.common.model import Asset, Mesh, Material\n'
                'def build(config, rng):\n'
                '    return Asset([Mesh("triangle", [(0,0,0), (1,0,0), (0,1,0)], '
                '[(0,1,2)], Material("plain", (1,1,1,1)))], gameplay={"random": rng.random()})\n')
            (directory / "config.json").write_text(json.dumps({
                "name": name, "seed": 123, "outputs": ["metadata", "glb"]}))
        variants = discover(sources)
        self.assertEqual(list(variants), ["first", "second"])
        output = self.root / "outputs"
        with patch("gl_assets.__main__.discover", return_value=variants), redirect_stdout(io.StringIO()):
            self.assertEqual(main(["generate", "all", "--backend", "preview", "--output-dir", str(output)]), 0)
        second = self.snapshot(output / "second")
        first = self.snapshot(output / "first")
        generate(variants["first"], output)
        self.assertEqual(first, self.snapshot(output / "first"))
        generate(variants["first"], output, seed=321)
        self.assertNotEqual(first["metadata.json"], (output / "first/metadata.json").read_bytes())
        self.assertEqual(second, self.snapshot(output / "second"))

    def test_output_selection_removes_obsolete_exports(self):
        config = self.config()
        output = generate(self.original, self.root, config=config)
        config["outputs"] = ["metadata"]
        generate(self.original, self.root, config=config)
        self.assertEqual(set(self.snapshot(output)), {"config.json", "metadata.json", "manifest.json"})

    def test_proportions_are_variant_configuration(self):
        config = self.config()
        config["dimensions"].update(g_width=5, g_height=6, g_elevation=3, l_length=7)
        output = generate(self.original, self.root, config=config)
        metadata = json.loads((output / "metadata.json").read_text())
        self.assertEqual(metadata["bounds"], {"min": [0, 0, 0], "max": [5, 7, 9]})
        config["dimensions"]["stroke"] = 2
        with self.assertRaisesRegex(ValueError, "G width/height"):
            generate(self.original, self.root, config=config)

    def test_failed_render_preserves_previous_output(self):
        config = self.config()
        output = generate(self.original, self.root, config=config)
        before = self.snapshot(output)
        config["render"]["cameras"] = ["../../escape"]
        with self.assertRaisesRegex(ValueError, "Unknown camera"):
            generate(self.original, self.root, config=config)
        self.assertEqual(before, self.snapshot(output))
        self.assertEqual([p.name for p in self.root.iterdir()], ["original"])

    def test_source_cannot_be_output_destination(self):
        with self.assertRaisesRegex(ValueError, "separate"):
            generate(self.original, self.original.directory.parent, config=self.config())

    def test_union_removes_internal_faces_and_has_outward_normals(self):
        mesh = block_union("adjacent", [(0,0,0,1,1,1), (1,0,0,2,1,1)],
                           Material("plain", (1,1,1,1)))
        self.assertEqual(len(mesh.triangles), 20)
        volume = 0
        for tri in mesh.triangles:
            a, b, c = [mesh.vertices[i] for i in tri]
            volume += (a[0]*(b[1]*c[2]-b[2]*c[1]) + a[1]*(b[2]*c[0]-b[0]*c[2])
                       + a[2]*(b[0]*c[1]-b[1]*c[0])) / 6
        self.assertAlmostEqual(volume, 2)

    def test_failed_publish_restores_previous_output(self):
        output = generate(self.original, self.root, config=self.config())
        before = self.snapshot(output)
        rename = Path.rename

        def fail_stage(path, target):
            if path.name.startswith(".original-"):
                raise OSError("simulated publish failure")
            return rename(path, target)

        with patch.object(Path, "rename", fail_stage), self.assertRaises(OSError):
            generate(self.original, self.root, config=self.config())
        self.assertEqual(before, self.snapshot(output))


if __name__ == "__main__":
    unittest.main()
