"""Authoring-space camera presets shared by Blender and quick previews."""
import math

CAMERAS = {"isometric": (6, -12, 8), "front": (0, -1, 0),
           "side": (1, 0, 0), "top": (0, 0, 1)}


def framing(config, preset):
    """Optional saved orthographic framing; straight views remain auto-fitted."""
    camera = config.get("render", {}).get("camera") or {}
    if preset != "isometric" or not ({"target", "ortho_scale"} & camera.keys()):
        return None
    target, scale = camera.get("target"), camera.get("ortho_scale")
    if (not isinstance(target, (list, tuple)) or len(target) != 3
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) for v in target)):
        raise ValueError("Camera target must contain three finite coordinates")
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("Camera ortho_scale must be finite and positive")
    return tuple(target), scale


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
