import argparse
import json
from pathlib import Path
import sys
import shutil
import subprocess

from .pipeline import generate
from .registry import discover


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate named GL assets")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List registered variants and supported outputs")
    build = commands.add_parser("generate", help="Generate one named variant or all")
    build.add_argument("variant", help="Variant name, or all")
    build.add_argument("--seed", type=int, help="Override each selected variant's seed")
    build.add_argument("--output-dir", default="generated", help="Parent directory for variant outputs")
    build.add_argument("--config", help="Full replacement JSON config for a single variant")
    build.add_argument("--backend", choices=["blender", "preview"], default="blender")
    build.add_argument("--blender", default="blender", help="Blender executable (4.5 LTS recommended)")
    args = parser.parse_args(argv)
    try:
        variants = discover()
        if args.command == "list":
            for name, variant in variants.items():
                print(f"{name}: {', '.join(variant.config['outputs'])}")
            return 0
        if args.variant != "all" and args.variant not in variants:
            raise ValueError(f"Unknown variant {args.variant!r}; available: {', '.join(variants)}")
        if args.config and args.variant == "all":
            raise ValueError("--config requires a single named variant")
        config = json.loads(Path(args.config).read_text()) if args.config else None
        backend = None
        if args.backend == "blender":
            try:
                import bpy
            except ImportError:
                binary = shutil.which(args.blender)
                if binary is None:
                    raise ValueError("Blender not found; install Blender 4.5 LTS or pass --blender /path/to/blender")
                script = Path(__file__).with_name("blender_build.py").resolve()
                return subprocess.run([binary, "--background", "--factory-startup", "--threads", "4",
                    "--python-exit-code", "1", "--python", str(script), "--"] +
                    list(sys.argv[1:] if argv is None else argv), check=False).returncode
            from .common.blender import BlenderBackend
            backend = BlenderBackend()
        selected = variants.values() if args.variant == "all" else [variants[args.variant]]
        for variant in selected:
            effective = config
            if args.backend == "preview":
                # Quick previews remain available without Blender. They never
                # claim to contain bevels or an editable Blender source.
                effective = dict(variant.config if config is None else config)
                effective["outputs"] = [o for o in effective["outputs"] if o != "blend"]
            print(generate(variant, args.output_dir, args.seed, effective, backend))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
