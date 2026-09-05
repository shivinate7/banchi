"""Derive the ground gradients from the prisms, and print them as a JS literal.

THE GROUND IS NOT A FREE CHOICE BESIDE THE PRISM (docs/specs/logo.md section 3). It is the
prism's own hue, driven away from the card, carrying a fraction of the prism's peak chroma.
This script is the ONE implementation of that rule; the sheets carry its output as literals
rather than repeating the arithmetic, because a second implementation of a rule is a second
thing to drift — `make docs-audit`'s `motion params` row exists for the case where exactly
that already happened.

Two facts about the method are reproduced here rather than asserted, and both check out
against section 3's published table:

  * the hue is the CHROMA-WEIGHTED hue of the five prism stops, not the hue of the
    highest-chroma stop. The two disagree by up to 5 degrees, and only the weighted one
    reproduces section 3's 249.1 / 291.1 / 174.1 / 76.0.
  * the chroma is a RATIO of the prism's peak, not an absolute. Section 3 corrected itself
    on this on 2026-09-05 and this script is what that correction now runs on.
  * THE CHROMA FALLS TO 0.60 OF THAT RATIO AT THE BOTTOM OF THE GRADIENT. Section 3 states
    the rule with ONE fraction and its own published grounds carry two. Held constant down
    the gradient the rule misses every bottom stop in the file; tapered to 0.60 it
    reproduces all twelve — three prisms, both chroma families, top and bottom — byte for
    byte. See `check()`. That is a parameter nobody wrote down, recovered from the values it
    had already produced.

    python3 docs/specs/logo/sheets/grounds.py         # the table, and the section 3 check
    python3 docs/specs/logo/sheets/grounds.py --js    # the literal the sheets carry
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oklch import hex2ok, ok2hex  # noqa: E402

PRISMS = {
    "bluesteel":  ["#E4EEF8", "#B0C8E0", "#7F9FC0", "#F2F8FF", "#6086AC"],
    "lilacish":   ["#EFEAFA", "#BCB4E0", "#8E86C0", "#F6F2FF", "#6E68A8"],
    "mint":       ["#E6F6F0", "#A8D4C4", "#78AC9C", "#F2FCF8", "#589084"],
    "rich":       ["#FFD97A", "#F0A82E", "#C9821E", "#FFEFC0", "#B36F18"],
    "wg_warm":    ["#FFFBF2", "#EFE6D2", "#DCD0B8", "#FFFFFF", "#C9BCA2"],
    "rg_classic": ["#FFD9C8", "#F0B49A", "#DE9070", "#FFE9DF", "#C87A5C"],
}

# Section 3, locked. `deeper drop` (0.288 -> 0.115) was the only candidate that moved this
# pair and it is the only one that lost.
DARK_L = (0.255, 0.148)

# The light pairs this sweep offers, bracketed so both ends are meant to be wrong (section 7
# rule 2): 0.99 should be indistinguishable from the page it sits on, 0.86 should have
# stopped being a light tile and become a grey one.
LIGHT_L = [(0.99, 0.95), (0.97, 0.91), (0.94, 0.87), (0.90, 0.82), (0.86, 0.76)]

RATIOS = [0.23, 0.31, 0.39, 0.48, 0.70]

# The ground fades toward neutral as it darkens. Recovered from section 3's own numbers, not
# chosen: see the module docstring and `check()`.
TAPER = 0.60

# Every ground section 3 and section 9 publish, as the fixture `check()` runs against.
PUBLISHED = {
    0.39: {"bluesteel": ("#182430", "#060B12"), "lilacish": ("#231F34", "#0B0914"),
           "mint": ("#162722", "#050D0A")},
    0.23: {"bluesteel": ("#1D242B", "#080B0F"), "lilacish": ("#23212D", "#0B0A10"),
           "mint": ("#1C2522", "#070C0A")},
}


def in_gamut(lightness, chroma, hue):
    """False where sRGB cannot hold this colour, so the hex is a CLIP and not the hue asked
    for. It bites on the light side and never on the dark: near white, sRGB runs out of blue
    long before the eye runs out of tolerance."""
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    lc = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    mc = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    sc = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return all(-1e-9 <= v <= 1 + 1e-9 for v in (
        4.0767416621 * lc - 3.3077115913 * mc + 0.2309699292 * sc,
        -1.2684380046 * lc + 2.6097574011 * mc - 0.3413193965 * sc,
        -0.0041960863 * lc - 0.7034186147 * mc + 1.7076147010 * sc))


def peak(stops):
    """(chroma-weighted hue in degrees, peak chroma) for a five-stop prism."""
    x = y = top = 0.0
    for s in stops:
        _, chroma, hue = hex2ok(s)
        x += chroma * math.cos(math.radians(hue))
        y += chroma * math.sin(math.radians(hue))
        top = max(top, chroma)
    return math.degrees(math.atan2(y, x)) % 360, top


def ground(stops, pair, ratio):
    hue, top = peak(stops)
    hi, lo = top * ratio, top * ratio * TAPER
    return ok2hex(pair[0], hi, hue), ok2hex(pair[1], lo, hue)


def clips(stops, pair, ratio):
    """True where either stop of this ground had to be clipped into sRGB."""
    hue, top = peak(stops)
    return not (in_gamut(pair[0], top * ratio, hue)
                and in_gamut(pair[1], top * ratio * TAPER, hue))


def check():
    """Every published ground, re-derived. Prints a line per stop and returns the tally."""
    good = total = 0
    for ratio, wanted in sorted(PUBLISHED.items()):
        for name, (hi, lo) in wanted.items():
            got = ground(PRISMS[name], DARK_L, ratio)
            for g, w in zip(got, (hi, lo)):
                total += 1
                good += g == w
                print(f"  {name:<10} ratio {ratio}: {g} {'==' if g == w else '!='} {w}")
    print(f"  {good}/{total} published stops reproduced exactly")
    return good, total


def table():
    print(f"{'prism':<12}{'hue':>8}{'peak C':>9}")
    for name, stops in PRISMS.items():
        hue, top = peak(stops)
        print(f"{name:<12}{hue:8.1f}{top:9.4f}")
    print("\nevery published ground, re-derived — the check that this is the same rule:")
    check()
    print("\nlight candidates, bluesteel, by L pair at ratio 0.31:")
    for pair in LIGHT_L:
        a, b = ground(PRISMS["bluesteel"], pair, 0.31)
        flag = "   CLIPPED — not on the prism's hue" if clips(PRISMS["bluesteel"], pair, 0.31) else ""
        print(f"  L {pair[0]:.2f} -> {pair[1]:.2f}: {a} -> {b}{flag}")
    print("\nlight candidates, bluesteel, by ratio at L 0.94 -> 0.87:")
    for ratio in RATIOS:
        a, b = ground(PRISMS["bluesteel"], (0.94, 0.87), ratio)
        flag = "   CLIPPED" if clips(PRISMS["bluesteel"], (0.94, 0.87), ratio) else ""
        print(f"  ratio {ratio}: {a} -> {b}{flag}")


def js():
    print("/* GENERATED by `python3 grounds.py --js`. Do not hand-edit; re-run the script. */")
    print("const GROUND = {")
    print("  darkLocked: {")
    for name, stops in PRISMS.items():
        a, b = ground(stops, DARK_L, 0.39)
        print(f"    {name}: ['{a}','{b}'],")
    print("  },")
    print("  byPair: {")
    for pair in LIGHT_L:
        a, b = ground(PRISMS["bluesteel"], pair, 0.31)
        print(f"    '{pair[0]:.2f}': ['{a}','{b}'],")
    print("  },")
    print("  byRatio: {")
    for ratio in RATIOS:
        a, b = ground(PRISMS["bluesteel"], (0.94, 0.87), ratio)
        print(f"    '{ratio}': ['{a}','{b}'],")
    print("  },")
    for pair, key in (((0.97, 0.91), "p97"), ((0.94, 0.87), "p94"), ((0.90, 0.82), "p90")):
        print(f"  {key}: {{")
        for name, stops in PRISMS.items():
            a, b = ground(stops, pair, 0.31)
            print(f"    {name}: ['{a}','{b}'],")
        print("  },")
    print("}")


if __name__ == "__main__":
    js() if "--js" in sys.argv else table()
