import hashlib
import json
from pathlib import Path
import unittest

from gl_assets.registry import discover


class CommittedArtifactTests(unittest.TestCase):
    def test_committed_original_matches_config_and_manifest(self):
        root = Path(__file__).resolve().parents[1]/"generated/original"
        self.assertEqual(json.loads((root/"config.json").read_text()), discover()["original"].config)
        manifest = json.loads((root/"manifest.json").read_text())
        self.assertEqual(manifest["variant"], "original")
        for name, expected in manifest["sha256"].items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(), expected)
        topology = json.loads((root/"metadata.json").read_text())["asset"]["topology"]
        self.assertEqual(len(topology), 1)
        self.assertEqual(topology[0]["components"], 1)
        self.assertEqual(topology[0]["non_manifold_edges"], 0)
        self.assertGreater(topology[0]["volume"], 0)
