"""sRGB <-> OKLCH, for the ground derivation in docs/specs/logo.md.

The ground is the prism's own hue driven to near-black, so the sweep has to be
done in a perceptual space: equal chroma steps in OKLCH are equal steps to the
eye, and equal steps in sRGB are not.
"""
import math


def _to_linear(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_srgb(c):
    c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return max(0, min(255, round(c * 255)))


def hex2ok(h):
    """#RRGGBB -> (L, C, H degrees)."""
    h = h.lstrip("#")
    r, g, b = (_to_linear(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    lc = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    mc = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    sc = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    lc, mc, sc = lc ** (1 / 3), mc ** (1 / 3), sc ** (1 / 3)
    lightness = 0.2104542553 * lc + 0.7936177850 * mc - 0.0040720468 * sc
    a = 1.9779984951 * lc - 2.4285922050 * mc + 0.4505937099 * sc
    b2 = 0.0259040371 * lc + 0.7827717662 * mc - 0.8086757660 * sc
    return lightness, math.hypot(a, b2), math.degrees(math.atan2(b2, a)) % 360


def ok2hex(lightness, chroma, hue):
    """(L, C, H degrees) -> #RRGGBB, clipped into sRGB."""
    a = chroma * math.cos(math.radians(hue))
    b2 = chroma * math.sin(math.radians(hue))
    lc = (lightness + 0.3963377774 * a + 0.2158037573 * b2) ** 3
    mc = (lightness - 0.1055613458 * a - 0.0638541728 * b2) ** 3
    sc = (lightness - 0.0894841775 * a - 1.2914855480 * b2) ** 3
    r = 4.0767416621 * lc - 3.3077115913 * mc + 0.2309699292 * sc
    g = -1.2684380046 * lc + 2.6097574011 * mc - 0.3413193965 * sc
    b = -0.0041960863 * lc - 0.7034186147 * mc + 1.7076147010 * sc
    return "#%02X%02X%02X" % (_to_srgb(r), _to_srgb(g), _to_srgb(b))
