import copy
import hashlib
from pathlib import Path
import random
import shutil
import tempfile

from .common.export import write_glb, write_json
from .common.model import AXES
from .common.camera import direction
from .common.render import CAMERAS, write_png
from .registry import validate_config


def generate(variant, output_root="generated", seed=None, config=None, backend=None):
    effective = copy.deepcopy(variant.config if config is None else config)
    if seed is not None:
        effective["seed"] = seed
    validate_config(effective, variant.name)
    asset = variant.builder()(effective, random.Random(effective["seed"]))
    asset.validate()
    if "blend" in effective["outputs"] and backend is None:
        raise ValueError("blend output requires the Blender backend")
    if backend is not None:
        asset = backend.prepare(asset, effective)
        asset.validate()
    root = Path(output_root).resolve()
    destination = root / variant.name
    source = Path(__file__).parent.resolve()
    if destination.is_symlink() or source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Output destination must be separate from asset source")
    variant_source = variant.directory.resolve()
    if variant_source == destination or variant_source in destination.parents or destination in variant_source.parents:
        raise ValueError("Output destination must be separate from variant source")
    if destination.exists() and not destination.is_dir():
        raise ValueError("Output destination must be a directory")
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{variant.name}-", dir=root))
    try:
        outputs = effective["outputs"]
        if "glb" in outputs:
            write_glb(stage / "asset.glb", asset)
        if "png" in outputs:
            render = effective.get("render", {})
            cameras = render.get("cameras", ["isometric"])
            if not isinstance(cameras, list) or not cameras or any(not isinstance(c, str) for c in cameras):
                raise ValueError("render.cameras must be a nonempty list of camera names")
            (stage / "renders").mkdir()
            for camera in cameras:
                # Camera validation happens before constructing an output path.
                if camera not in CAMERAS:
                    raise ValueError(f"Unknown camera: {camera}")
                path = stage / "renders" / f"{camera}.png"
                if backend is None:
                    write_png(path, asset, camera, render.get("size", 512), direction(effective, camera))
                else:
                    backend.render(path, camera, render.get("size", 512))
        if "blend" in outputs:
            backend.save(stage / "asset.blend")
        if "metadata" in outputs:
            write_json(stage / "metadata.json", {"variant": variant.name, "seed": effective["seed"],
                       "axes": AXES, "bounds": asset.bounds, "asset": asset.metadata, "gameplay": asset.gameplay})
        # Preserve the complete effective configuration alongside its results.
        write_json(stage / "config.json", effective)
        hashes = {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(stage.rglob("*")) if p.is_file()}
        write_json(stage / "manifest.json", {"schema_version": 1, "variant": variant.name,
                   "seed": effective["seed"], "outputs": outputs, "sha256": hashes,
                   "glb_axes": {"up": "+Y", "authoring_to_gltf": "(x, y, z) -> (x, z, -y)"}})
        # Finish every export before replacing this variant's previous output.
        backup = stage / "previous"
        if destination.exists():
            destination.rename(backup)
        try:
            # Backup must live outside stage when stage becomes destination.
            stage.rename(destination)
        except OSError:
            if backup.exists():
                backup.rename(destination)
            raise
        previous = destination / "previous"
        if previous.exists():
            shutil.rmtree(previous)
        return destination
    finally:
        if stage.exists():
            shutil.rmtree(stage)
