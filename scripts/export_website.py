"""Stage only reviewed static web assets and public provenance, without Blender."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gl_assets.common.camera import direction, framing
ASSETS = ("gl-mark.png", "gl-mark.webp", "favicon.svg")
FILES = tuple("assets/images/gl/" + name for name in ASSETS) + (
    "docs/gl-mark-provenance.json", "docs/gl-mark.md")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def regular_file(root, name):
    path = root / name
    if root.is_symlink() or any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError("Missing or symlinked export input")
    return path.read_bytes()


def validate_images(files):
    png = files["assets/images/gl/gl-mark.png"]
    if (len(png) < 33 or png[:8] != b"\x89PNG\r\n\x1a\n"
            or struct.unpack_from(">II", png, 16) != (128, 208) or png[24:26] != bytes((8, 6))):
        raise ValueError("Expected 128x208 RGBA PNG")
    webp = files["assets/images/gl/gl-mark.webp"]
    if len(webp) < 12 or webp[:4] != b"RIFF" or webp[8:12] != b"WEBP":
        raise ValueError("Invalid WebP")
    svg = files["assets/images/gl/favicon.svg"].decode()
    # This favicon is code owned by the variant, not an uploaded document.
    # Reject active or remotely loaded content before it crosses repositories.
    if not svg.lstrip().startswith("<svg") or re.search(
            r"<\s*(?:script|foreignObject|animate|set)\b|\bon\w+\s*=|(?:href|src)\s*=|<!|url\s*\(|@import", svg, re.I):
        raise ValueError("Unsupported favicon content")


def stage(source, destination, variant_config):
    """Export a fresh exact allowlist; source SHA stays inside the source workflow."""
    if destination.exists() or destination.is_symlink():
        raise ValueError("Destination must not exist")
    manifest = json.loads(regular_file(source, "manifest.json"))
    config = json.loads(regular_file(source, "config.json"))
    if config != variant_config or config["name"] != "original" or manifest["variant"] != "original":
        raise ValueError("Regenerate original: effective config differs from variant source")
    for name in ("config.json", "renders/isometric.png", *("web/" + n for n in ASSETS), "web/export.json"):
        if digest(regular_file(source, name)) != manifest["sha256"].get(name):
            raise ValueError("Generated input does not match manifest")
    report = json.loads(regular_file(source, "web/export.json"))
    if (report["source_render_sha256"] != manifest["sha256"]["renders/isometric.png"]
            or report["variant"] != "original" or (report["width"], report["height"]) != (128, 208)
            or set(report["files"]) != set(ASSETS)):
        raise ValueError("Invalid web export report")
    files = {"assets/images/gl/" + n: regular_file(source, "web/" + n) for n in ASSETS}
    for name in ASSETS:
        data = files["assets/images/gl/" + name]
        if report["files"][name] != {"bytes": len(data), "sha256": digest(data)}:
            raise ValueError("Web export hash mismatch")
    validate_images(files)
    direction(config, "isometric")
    framing(config, "isometric")
    camera = {key: config["render"]["camera"][key]
              for key in ("azimuth_degrees", "elevation_degrees", "target", "ortho_scale")
              if key in config["render"]["camera"]}
    if not re.fullmatch(r"Pillow [0-9]+(?:\.[0-9]+)+", report["encoder"]):
        raise ValueError("Unexpected web encoder")
    provenance = {"variant": "original", "width": 128, "height": 208,
                  "files": report["files"], "encoder": report["encoder"],
                  "source_render_sha256": report["source_render_sha256"],
                  "camera": camera,
                  "source": "Offline GL asset pipeline; public content hashes identify this export"}
    files["docs/gl-mark-provenance.json"] = encoded(provenance)
    files["docs/gl-mark.md"] = b"""# GL header mark

Garett Loghry supplied the sculpture design and selected its camera view.
The original variant is built offline with Blender; Jekyll serves prebuilt files.
Codex implemented the procedural model, static exports and automated handoff.

## Current export

[gl-mark-provenance.json](gl-mark-provenance.json) records the public asset
hashes, image dimensions and camera settings. Source repository revisions and
workflow links are intentionally omitted so the source can remain private.
Only the three static files in `assets/images/gl/` are served: the transparent
128x208 PNG fallback, optimized WebP and simplified SVG favicon. The elevated G
has a descending right-hand stem shared with the perpendicular L and its +Y foot.

The header displays the mark at 32x52 CSS pixels, or 28x45.5 on narrow phones.
The existing home link, visible name, font, themes and layout remain unchanged.
The favicon is a separate optical simplification for small browser icons.

## Updates and review

Approved source changes merge before the source publisher proposes a website
PR. It copies only these assets and the two provenance documents, and never
merges or deploys. No source token, Blender, Python or WebGL is required by the
website to obtain or display the mark. Use the source repository README for
offline regeneration and publisher setup; do not edit generated images here.

Before merging a proposal, inspect its exact files and existing website CI.
Review desktop/mobile header screenshots in both themes, including the root
URL and a nonempty base path as described in [accessibility.md](accessibility.md).
The existing [gl-mark-review/](gl-mark-review/) bundle is historical evidence;
it is not regenerated by the publisher and may show an older mark. Use the
current PR's browser artifacts/preview for the new export.
"""
    destination.mkdir(parents=True)
    for name, data in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (destination / "manifest.json").write_bytes(encoded({"files": {n: digest(v) for n, v in files.items()}}))
    return files


def load_export(folder):
    manifest = json.loads(regular_file(folder, "manifest.json"))
    if set(manifest) != {"files"} or set(manifest["files"]) != set(FILES):
        raise ValueError("Invalid website export allowlist")
    if any(p.is_symlink() for p in folder.rglob("*")):
        raise ValueError("Export contains symlink")
    if {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()} != set(FILES) | {"manifest.json"}:
        raise ValueError("Export contains missing or unexpected files")
    files = {n: regular_file(folder, n) for n in FILES}
    if any(digest(v) != manifest["files"][n] for n, v in files.items()):
        raise ValueError("Export hash mismatch")
    validate_images(files)
    return files, digest(encoded(manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((ROOT / "gl_assets/variants/original/config.json").read_text())
    stage(ROOT / "generated/original", args.destination, config)
    print("Validated five-file static website export.")
