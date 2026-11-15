import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

try:
    from PIL import Image
except ImportError:
    Image = None


@unittest.skipIf(Image is None, "Install requirements-web.txt to check offline web exports")
class WebExportTests(unittest.TestCase):
    def setUp(self):
        from scripts.export_web import export
        self.export = export
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)/"original"
        source = Path(__file__).resolve().parents[1]/"generated/original"
        self.directory.mkdir()
        shutil.copyfile(source/"config.json", self.directory/"config.json")
        shutil.copyfile(source/"manifest.json", self.directory/"manifest.json")
        shutil.copytree(source/"renders", self.directory/"renders")

    def test_transparency_dimensions_optimization_and_repeatability(self):
        web = self.export(self.directory)
        before = {p.name: p.read_bytes() for p in web.iterdir()}
        with Image.open(web/"gl-mark.png") as png, Image.open(web/"gl-mark.webp") as webp:
            self.assertEqual(png.size, (128, 208))
            self.assertEqual(png.size, webp.size)
            self.assertEqual(png.mode, "RGBA")
            self.assertEqual(png.getchannel("A").getextrema(), (0, 255))
            self.assertEqual(png.getchannel("A").tobytes(), webp.getchannel("A").tobytes())
        self.assertLess((web/"gl-mark.webp").stat().st_size, (web/"gl-mark.png").stat().st_size)
        self.export(self.directory)
        self.assertEqual(before, {p.name: p.read_bytes() for p in web.iterdir()})
        manifest = json.loads((self.directory/"manifest.json").read_text())
        for path in web.iterdir():
            self.assertEqual(manifest["sha256"]["web/"+path.name], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_tampered_render_rejected_before_export(self):
        path = self.directory/"renders/isometric.png"
        path.write_bytes(path.read_bytes()+b"changed")
        with self.assertRaisesRegex(ValueError, "manifest"):
            self.export(self.directory)
