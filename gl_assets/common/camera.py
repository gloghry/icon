"""Authoring-space camera presets shared by Blender and quick previews."""
import math

CAMERAS = {"isometric": (6, -12, 8), "front": (0, -1, 0),
           "side": (1, 0, 0), "top": (0, 0, 1)}


def direction(config, preset):
    if preset not in CAMERAS:
        raise ValueError(f"Unknown camera: {preset}")
    if preset != "isometric":
        return CAMERAS[preset]
    camera = config.get("render", {}).get("camera")
    if camera is None:
        return CAMERAS[preset]
    az, el = camera["azimuth_degrees"], camera["elevation_degrees"]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (az, el)):
        raise ValueError("Camera angles must be finite numbers")
    if not 0 < az < 80 or not 0 < el < 80:
        raise ValueError("Three-quarter camera angles must lie between 0 and 80 degrees")
    az, el = math.radians(az), math.radians(el)
    return (math.sin(az)*math.cos(el), -math.cos(az)*math.cos(el), math.sin(el))
