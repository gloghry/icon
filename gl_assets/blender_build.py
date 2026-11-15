"""Blender entry point, launched by python -m gl_assets generate."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gl_assets.__main__ import main

raise SystemExit(main(sys.argv[sys.argv.index("--") + 1:]))
