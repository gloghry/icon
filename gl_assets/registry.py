"""Variants register themselves by providing config.json and builder.py."""
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import re

VARIANTS = Path(__file__).parent / "variants"
NAME = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
OUTPUTS = {"png", "glb", "metadata", "blend"}


@dataclass(frozen=True)
class Variant:
    name: str
    directory: Path
    config: dict

    def builder(self):
        spec = importlib.util.spec_from_file_location(f"gl_asset_variant_{self.name.replace('-', '_')}",
                                                      self.directory / "builder.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.build


def validate_config(config, expected_name):
    if config.get("name") != expected_name:
        raise ValueError(f"Configuration name must match variant directory: {expected_name}")
    if isinstance(config.get("seed"), bool) or not isinstance(config.get("seed"), int):
        raise ValueError("seed must be an integer")
    outputs = config.get("outputs")
    if not isinstance(outputs, list) or not outputs or any(not isinstance(o, str) or o not in OUTPUTS for o in outputs):
        raise ValueError(f"outputs must be a nonempty list from {sorted(OUTPUTS)}")
    if len(set(outputs)) != len(outputs):
        raise ValueError("outputs must not contain duplicates")


def discover(root=VARIANTS):
    variants = {}
    for directory in sorted(Path(root).iterdir()):
        if not directory.is_dir() or directory.name.startswith((".", "_")):
            continue
        if not NAME.fullmatch(directory.name) or directory.name == "all":
            raise ValueError(f"Invalid or reserved variant name: {directory.name}")
        if not (directory / "builder.py").is_file():
            raise ValueError(f"Missing builder.py in {directory}")
        config = json.loads((directory / "config.json").read_text())
        validate_config(config, directory.name)
        variants[directory.name] = Variant(directory.name, directory, config)
    return variants
