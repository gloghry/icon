"""Build twice and compare deterministic deliverables with pinned Blender."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gl_assets.registry import discover


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("blender")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gl-smoke-") as temporary:
        root = Path(args.output_dir or temporary)
        root.mkdir(parents=True, exist_ok=True)
        config = copy.deepcopy(discover()["original"].config)
        config["render"].update(size=96, samples=8)
        config_path = root / "config.json"
        config_path.write_text(json.dumps(config))
        for name in ("first", "second"):
            subprocess.run([sys.executable, "-m", "gl_assets", "generate", "original",
                "--blender", args.blender, "--config", str(config_path), "--output-dir", str(root/name)],
                cwd=ROOT, check=True)
        first, second = root/"first/original", root/"second/original"
        for name in ("asset.glb", "metadata.json", "config.json", "renders/front.png",
                     "renders/side.png", "renders/isometric.png"):
            a, b = (first/name).read_bytes(), (second/name).read_bytes()
            assert a == b, f"Non-reproducible deliverable: {name}"
            print(name, hashlib.sha256(a).hexdigest())
        subprocess.run([args.blender, "--background", str(first/"asset.blend"),
            "--python-exit-code", "1", "--python", str(ROOT/"scripts/check_blender_asset.py")], check=True)
    print("Two seeded builds match; saved Blender solid validated.")


if __name__ == "__main__":
    main()
