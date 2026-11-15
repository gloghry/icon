"""Derive compact website assets from the reviewed Blender render, offline."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

from PIL import Image, ImageDraw, ImageOps, __version__ as pillow_version

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gl_assets.common.export import write_json


def review_sheets(directory, mark):
    review = directory / "review"
    review.mkdir(exist_ok=True)
    canvas = Image.new("RGB", (1080, 430), "#EDF1F3")
    draw = ImageDraw.Draw(canvas)
    for i, name in enumerate(("front", "side", "isometric")):
        with Image.open(directory/"renders"/f"{name}.png") as render:
            render.thumbnail((340, 360))
            canvas.paste(render, (i*360+(360-render.width)//2, 40), render)
        draw.text((i*360+20, 15), "Three-quarter" if name == "isometric" else name.title(), fill="#202A30")
    canvas.save(review/"previews.png", optimize=True)
    canvas = Image.new("RGB", (720, 260), "#EDF1F3")
    draw = ImageDraw.Draw(canvas)
    for i, height in enumerate((16, 24, 32, 52)):
        small = ImageOps.contain(mark, (height, height), Image.Resampling.LANCZOS)
        x = 20+i*175
        canvas.paste(small, (x, 40), small)
        enlarged = small.resize((small.width*4, small.height*4), Image.Resampling.NEAREST)
        canvas.paste(enlarged, (x, 105), enlarged)
        draw.text((x, 15), f"{height}px; 4x below", fill="#202A30")
    canvas.save(review/"small-sizes.png", optimize=True)


def export(directory):
    directory = Path(directory).resolve()
    config = json.loads((directory / "config.json").read_text())
    manifest = json.loads((directory / "manifest.json").read_text())
    name = config["name"]
    if directory.name != name or manifest["variant"] != name:
        raise ValueError("Input must be the named variant's generated directory")
    source = directory / "renders/isometric.png"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_hash != manifest["sha256"].get("renders/isometric.png"):
        raise ValueError("Render does not match its build manifest")
    with Image.open(source) as original:
        if original.mode != "RGBA":
            raise ValueError("Final web assets require a transparent Blender RGBA render")
        # Ignore negligible alpha noise but retain a two-pixel anti-alias margin.
        bbox = original.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        if bbox is None:
            raise ValueError("Empty sculpture render")
        x0, y0, x1, y1 = bbox
        bbox = (max(0,x0-2), max(0,y0-2), min(original.width,x1+2), min(original.height,y1+2))
        fitted = ImageOps.contain(original.crop(bbox), (120, 200), Image.Resampling.LANCZOS)
        image = Image.new("RGBA", (128, 208))
        image.paste(fitted, ((128-fitted.width)//2, (208-fitted.height)//2))
    web = directory / "web"
    web.mkdir(exist_ok=True)
    image.save(web/"gl-mark.png", optimize=True)
    image.save(web/"gl-mark.webp", quality=88, method=6, alpha_quality=100, exact=True)
    favicon = ROOT / "gl_assets/variants" / name / "favicon.svg"
    if favicon.is_file():
        shutil.copyfile(favicon, web/"favicon.svg")
    if all((directory/"renders"/f"{c}.png").is_file() for c in ("front", "side", "isometric")):
        review_sheets(directory, image)
    report = {"variant": name, "source_render_sha256": source_hash, "crop": bbox,
              "width": 128, "height": 208, "display_width": 32, "display_height": 52,
              "encoder": f"Pillow {pillow_version}", "webp_quality": 88,
              "files": {p.name: {"bytes": p.stat().st_size,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                        for p in sorted(web.iterdir()) if p.name != "export.json"}}
    write_json(web/"export.json", report)
    derived = list(web.iterdir()) + list((directory/"review").glob("*.png"))
    for path in sorted(derived):
        manifest["sha256"][path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(directory/"manifest.json", manifest)
    print(json.dumps(report, indent=2))
    return web


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    export(args.directory)
