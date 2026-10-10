"""The logo, screens, storage keys and the render manifest."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from .core import (
    Finding,
    MECHANICAL,
    ROOT,
    Report,
    Row,
    _NUMBER_WORDS,
    _merge_rows,
    _strip_ts_comments,
    exists,
    markdown_files,
    read,
    rel,
)
from .records import decision_files

# ------------------------------------------------------------------ the mark (D102)

LOGO_SPEC = ROOT / "docs" / "specs" / "logo.md"
MARK_PALETTES = ROOT / "app" / "src" / "kit" / "markPalettes.ts"
LOCKUP_GEOMETRY = ROOT / "app" / "src" / "kit" / "lockupGeometry.ts"
LOCKUP_TSX = ROOT / "app" / "src" / "kit" / "Lockup.tsx"

# Section 9's rows, as they are written: | mark | prism | ground | bracket | card base |
# THE BRACKET LEGEND, WHICH SECTION 9 PUBLISHES AND THIS ROW READ FOR THE FIRST TIME ON
# 2026-09-05. The locked-set table names each mark's bracket as a WORD — `chrome`, `pale gold`,
# `rose` — and resolves it three lines below in a second table. Reading only the word meant the
# four hexes it stands for were compared against nothing: 24 of the 72 hexes in
# `markPalettes.ts` were unread, in the one file CLAUDE.md's color rule takes an exception for.
# Measured: changing bluesteel's `#B8C8D8` to `#B8C8D9` left `logo parity`, `raw color` AND
# `design tokens` all green, so a color nobody approved could reach the app past every reader
# the rule has. The docstring claimed the opposite in so many words.
_S9_BRACKET = re.compile(r"^\|\s*([a-z ]+?)\s*\|\s*`((?:#[0-9A-Fa-f]{6}\s*)+)`\s*\|", re.M)

_S9_ROW = re.compile(
    r"^\|\s*\*{0,2}([a-z ]+?)\*{0,2}(?:\s*—\s*DEFAULT)?\*{0,2}\s*\|"      # the mark's name
    r"\s*`([^`]+)`\s*\|"                                                       # prism stops
    r"\s*`([^`]+)`\s*→\s*`([^`]+)`\s*\|"                                     # ground, two stops
    r"\s*\*{0,2}([a-z ]+?)\*{0,2}\s*\|"                                      # bracket name
    r"\s*`([^`]+)`\s*\|",                                                      # card base
    re.M,
)


def _logo_parity() -> Row:
    """`app/src/kit/markPalettes.ts` and docs/specs/logo.md section 9 name the same colors.

    Folded into the `logo` row by `check_logo` (M3, L8, 2026-09-27) — this still does the
    same comparison and returns its own verdict rather than adding to the report directly.

    THIS ROW IS WHY THE MARK IS ALLOWED TO NAME COLORS AT ALL. CLAUDE.md's rule is that
    `app/src/tokens.css` is the only file in `app/` that may name one, and D102 takes a
    deliberate exception for the mark: those hexes are an illustration's, locked by another
    document, and must not be theme-overridable — which is exactly what moving them into
    `tokens.css` would invite.

    **`raw color` cannot see the file.** Its scope is `app/src/*.css`, non-recursive, and it
    never opens a `.ts` or `.tsx`, so all 72 hexes in `markPalettes.ts` pass it in silence. An
    exception with no reader is how a rule stops being one, so this row stands in its place.

    **AND IT ONLY BECAME TRUE OF ALL 72 ON 2026-09-05.** Section 9's locked-set table names each
    mark's bracket as a WORD and resolves it in a second table three lines below; this row read
    the word and never the table, so 24 of the 72 — every bracket ramp — were compared against
    nothing. Changing one of them left this row, `raw color` and `design tokens` all green, which
    is a color reaching the app past every reader CLAUDE.md's rule has. The sentence above about
    an exception with no reader was, for those 24, describing this row.

    Both directions, because the two failures are different: a palette here that section 9 does
    not publish is a color nobody approved, and a mark in section 9 that is missing here is a
    locked mark the product cannot draw. A bracket name section 9 uses and does not publish is a
    third, and it is reported rather than skipped.

    Provably wrong when it fires and no judgement to defer — both sides are literals.
    """
    if not exists(LOGO_SPEC) or not exists(MARK_PALETTES):
        # A ROW, NOT A RETURN — see `raw color`. A silent return deletes the row from
        # the render, and an absent row is the one state nothing in this file reads.
        return Row("logo parity", MECHANICAL, [],
                   "the spec or the generated palettes are not there", scanned=0)

    spec = read(LOGO_SPEC)
    # `chrome` -> ['#FFFFFF', '#B8C8D8', '#F2F8FF', '#8FA4B8'], off the legend table.
    ramps = {name.strip(): stops.split() for name, stops in _S9_BRACKET.findall(spec)}

    published: Dict[str, Dict[str, object]] = {}
    unresolved: List[str] = []
    for name, prism, hi, lo, bracket, base in _S9_ROW.findall(spec):
        ramp = ramps.get(bracket.strip())
        if ramp is None:
            unresolved.append(f"{name.strip()} -> {bracket.strip()}")
        published[name.strip()] = {
            "prism": prism.split(),
            "ground": [hi, lo],
            "bracket": ramp if ramp is not None else [],
            "base": base,
        }

    if not published:
        return Row("logo parity", MECHANICAL, [Finding(
            rel(LOGO_SPEC),
            "section 9's locked-set table did not parse, so this row is not comparing "
            "anything. Say so here rather than passing — a check that silently stops "
            "checking is worse than no check.",
        )], "")

    source = read(MARK_PALETTES)
    generated: Dict[str, Dict[str, object]] = {}
    for block in re.finditer(
        r"^  (\w+): \{\n"
        r"\s*label: '([^']+)',\n"
        r"\s*prism: \[([^\]]+)\],\n"
        r"\s*bracket: \[([^\]]+)\],\n"
        r"\s*ground: \['([^']+)', '([^']+)'\],\n"
        r"\s*base: '([^']+)',",
        source,
        re.M,
    ):
        _key, label, prism, bracket, hi, lo, base = block.groups()
        generated[label] = {
            "prism": re.findall(r"'(#[0-9A-Fa-f]{6})'", prism),
            "ground": [hi, lo],
            "bracket": re.findall(r"'(#[0-9A-Fa-f]{6})'", bracket),
            "base": base,
        }

    findings: List[Finding] = []
    for label in sorted(set(published) - set(generated)):
        findings.append(Finding(
            rel(MARK_PALETTES),
            f"section 9 locks `{label}` and no palette here draws it. The product cannot "
            f"render a mark the spec has locked. Re-run `node scripts/build-mark.mjs`.",
        ))
    for label in sorted(set(generated) - set(published)):
        findings.append(Finding(
            rel(MARK_PALETTES),
            f"`{label}` is a palette section 9 does not publish. Every color the mark names "
            f"is approved in docs/specs/logo.md section 9 (D102) — a hex that reaches the app "
            f"without going through that table is one nobody chose.",
        ))

    for pair in unresolved:
        findings.append(Finding(
            rel(LOGO_SPEC),
            f"section 9's locked-set table names the bracket `{pair.split(' -> ')[1]}` and the "
            f"gradient table below it does not publish that name, so the four hexes "
            f"`{pair.split(' -> ')[0]}` actually draws are approved by nothing. Add the ramp, "
            f"or rename the column to one that is published.",
        ))

    for label in sorted(set(published) & set(generated)):
        want, got = published[label], generated[label]
        for field in ("prism", "ground", "bracket", "base"):
            if want[field] != got[field]:
                findings.append(Finding(
                    f"{rel(MARK_PALETTES)} -> {label}",
                    f"{field} is {got[field]!r} here and {want[field]!r} in "
                    f"docs/specs/logo.md section 9. Section 9 is the store of record; "
                    f"re-run `node scripts/build-mark.mjs`, or move section 9 first.",
                ))

    return Row("logo parity", MECHANICAL, findings, scanned=len(published), summary=
               f"{len(published)} locked marks, every prism, ground, bracket and base "
               f"against section 9 ({sum(len(m['prism']) + len(m['ground']) + len(m['bracket']) + 1 for m in published.values())} hexes)"
               if not findings else f"{len(findings)} disagreements with section 9")


BUILD_MARK = ROOT / "scripts" / "build-mark.mjs"
APP_MANIFEST = ROOT / "app" / "public" / "manifest.webmanifest"

_S17_GRID = re.compile(r"\*\*(\d+)pt of artwork, cent(?:er|r)ed on a (\d+)pt canvas")
_MAC_GRID_CONST = re.compile(r"^const MAC_GRID = (\d+) / (\d+)\s*$", re.M)
_APP_SIZES = re.compile(r"^  const APP = \[([0-9, ]+)\]", re.M)


def _png_canvas(path: Path) -> "tuple[int, int] | None":
    """Width and height out of a PNG's IHDR. Stdlib only — this check is on the commit path.

    The pre-commit hook runs a bare `python3` with nothing installed (D18), so Pillow is not
    available here and never will be. The IHDR is the first chunk and its geometry is at a
    fixed offset, which is all this row needs: it reconciles DECLARATIONS, and the one fact it
    takes from the file itself is how big its canvas is.
    """
    try:
        head = path.read_bytes()[:24]
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def _mac_icon_grid() -> Row:
    """Apple's icon grid is one number in three places, and they must agree.

    docs/specs/logo.md section 17 publishes it, `scripts/build-mark.mjs` insets by it, and
    `app/public/manifest.webmanifest` lists the sizes it was applied to. The mark's own
    geometry is locked by section 3 and is NOT this row's business — what is, is that the
    generator and the spec do not drift apart, which is the failure `motion params` was added
    for one document over.

    **It cannot see the pixels, and says so rather than implying otherwise.** Whether a
    generated PNG's artwork really occupies 80.47% of its canvas needs an alpha bounding box,
    which needs Pillow, which is not on the commit path. So this reconciles the declarations
    and checks the one thing a PNG header can answer — that the file exists at the canvas size
    the manifest claims. A hand-edited PNG whose artwork was moved would pass; re-running the
    generator is what makes that unlikely, and the generator is what this row pins.
    """
    findings: list[Finding] = []
    spec = read(LOGO_SPEC)
    code = read(BUILD_MARK)

    published = _S17_GRID.search(spec)
    const = _MAC_GRID_CONST.search(code)
    if not published:
        findings.append(Finding(
            f"{rel(LOGO_SPEC)}",
            "section 17 no longer publishes the grid as `**<n>pt of artwork, centered on a "
            "<n>pt canvas`. That sentence is what `scripts/build-mark.mjs:MAC_GRID` is "
            "checked against; reword it back, or move this row to the new wording.",
        ))
    if not const:
        findings.append(Finding(
            f"{rel(BUILD_MARK)}",
            "`const MAC_GRID = <n> / <n>` is gone. docs/specs/logo.md section 17 publishes "
            "that ratio and nothing else reconciles the two.",
        ))
    if published and const and (
        (published.group(1), published.group(2)) != (const.group(1), const.group(2))
    ):
        findings.append(Finding(
            f"{rel(BUILD_MARK)} -> MAC_GRID",
            f"insets by {const.group(1)}/{const.group(2)} and docs/specs/logo.md "
            f"section 17 publishes {published.group(1)}/{published.group(2)}. Section 17 "
            f"is the store of record; re-run `node scripts/build-mark.mjs --icons`, or "
            f"move section 17 first.",
        ))

    # The manifest's set and the generator's set are the same set, and every file is there at
    # the canvas the manifest names. An icon listed but never generated is an install with a
    # missing size; one generated but not listed is dead weight Chrome will never read.
    sizes_m = _APP_SIZES.search(code)
    generated = ([int(n) for n in sizes_m.group(1).split(",") if n.strip()]
                 if sizes_m else [])
    try:
        listed = json.loads(read(APP_MANIFEST)).get("icons", [])
    except (ValueError, OSError):
        listed = []
    declared: list[int] = []
    for icon in listed:
        src, sizes = icon.get("src", ""), icon.get("sizes", "")
        if not src.endswith(".png"):
            findings.append(Finding(
                f"{rel(APP_MANIFEST)} -> {src}",
                "is in the manifest's icon list and is not one of the inset PNGs. Section 17 "
                "insets the WHOLE set on purpose: Chrome resizes these into the installed "
                "app's .icns, and one full-bleed entry pads the dock icon at one size and not "
                "the next. Keep it as a `<link rel=\"icon\">` instead.",
            ))
            continue
        try:
            declared.append(int(sizes.split("x")[0]))
        except ValueError:
            findings.append(Finding(f"{rel(APP_MANIFEST)} -> {src}",
                                    f"has an unreadable `sizes` of {sizes!r}."))
    if sizes_m and sorted(declared) != sorted(generated):
        findings.append(Finding(
            f"{rel(APP_MANIFEST)}",
            f"lists {sorted(declared)} and `scripts/build-mark.mjs:APP` generates "
            f"{sorted(generated)}. They are one set — a size listed but never written is a "
            f"404 at install time.",
        ))
    for size in declared:
        path = ROOT / "app" / "public" / f"icon-{size}.png"
        canvas = _png_canvas(path)
        if canvas is None:
            findings.append(Finding(f"{rel(APP_MANIFEST)}",
                                    f"names icon-{size}.png, which is missing or is not a PNG."))
        elif canvas != (size, size):
            findings.append(Finding(
                f"app/public/icon-{size}.png",
                f"is {canvas[0]}x{canvas[1]} and the manifest calls it {size}x{size}. "
                f"Re-run `node scripts/build-mark.mjs --icons`.",
            ))

    return Row("mac icon grid", MECHANICAL, findings, scanned=len(declared), summary=
               (f"{published.group(1)}/{published.group(2)} in section 17 and in build-mark.mjs, "
                f"over {len(declared)} inset icons"
                if published and const and not findings
                else f"{len(findings)} problem(s)"))


MARK_GEOMETRY = ROOT / "app" / "src" / "kit" / "markGeometry.ts"
LOCKUP_TSX_ = ROOT / "app" / "src" / "kit" / "Lockup.tsx"
FAVICON = ROOT / "app" / "public" / "favicon.svg"
MARK_PALETTES = ROOT / "app" / "src" / "kit" / "markPalettes.ts"

_LOCKUP_SPEC_ROW = re.compile(r"^\|\s*`(\w+)`\s*\|\s*([0-9.]+)\s*\|", re.M)


def _lockup_bracket() -> Row:
    """The lockup's dark bracket is a LOCKED palette, not a colour the sheet owns.

    §16 settles the dark theme's bracket as the chrome gradient `markPalettes.ts` already gives
    `bluesteel` — the default mark's own bracket — so the lockup and the mark are one object in
    one metal. That means four hexes are written in a sheet as well as in the generated file,
    which is the defect this work keeps finding, so this row checks that the component reads them.

    `raw color` cannot see it: its scope is `app/src/*.css`, and this is a `.tsx`.
    """
    if not exists(LOCKUP_TSX) or not exists(MARK_PALETTES):
        # A ROW, NOT A RETURN — see `raw color`. A silent return deletes the row from
        # the render, and an absent row is the one state nothing in this file reads.
        return Row("lockup bracket", MECHANICAL, [],
                   "the lockup component or the generated palettes are not there", scanned=0)
    gen = read(MARK_PALETTES)
    # the component reads the palette rather than naming hexes; if it ever stops, say so here
    if exists(LOCKUP_TSX):
        tsx = read(LOCKUP_TSX)
        if "MARKS.bluesteel.bracket" not in tsx and re.search(r"#[0-9A-Fa-f]{6}", tsx):
            return Row("lockup bracket", MECHANICAL, [Finding(
                rel(LOCKUP_TSX),
                "the lockup names a color of its own instead of reading "
                "`MARKS.bluesteel.bracket`. §16 settles the dark bracket as the MARK's metal so "
                "the two are one object; `markPalettes.ts` is the only file in app/ outside "
                "tokens.css allowed to name a hex, and `raw color` cannot see a .tsx.",
            )], "")
    m = re.search(r"bluesteel:\s*\{.*?bracket:\s*\[([^\]]+)\]", gen, re.S)
    if not m:
        return Row("lockup bracket", MECHANICAL, [Finding(
            rel(MARK_PALETTES),
            "`bluesteel`'s bracket is gone from the generated palettes. §16 draws the lockup's "
            "dark bracket from it; with it missing this row compares nothing.",
        )], "")
    want = re.findall(r"#[0-9A-Fa-f]{6}", m.group(1))
    return Row("lockup bracket", MECHANICAL, [],
               f"the lockup reads `bluesteel`'s locked bracket ({len(want)} stops)",
               scanned=len(want))


def _rail_mark() -> Row:
    """The sidebar mockup's rail bracket is the mark the app actually ships.

    IT WAS AN INVENTION, and drew four things wrong at once — stroke 11.0 against the mark's
    4.2, radius 14.6 against 8, an inset of 5.5 against 22.6, and a taper §11 had removed from
    the small cut on a measurement. It had been re-derived from the DISPLAY cut's unit rescaled
    into the wrong box, in the one sheet the sidebar's size is decided from.

    The shipped component and the generated files are what this row reads: the lockup imports
    `RAIL_ARM`, draws no path of its own, and the tab keeps its settled paint.
    """
    if not exists(MARK_GEOMETRY):
        # A ROW, NOT A RETURN — see `raw color`. A silent return deletes the row from
        # the render, and an absent row is the one state nothing in this file reads.
        return Row("rail mark", MECHANICAL, [],
                   "the generated mark is not there", scanned=0)
    gen = read(MARK_GEOMETRY)
    compared = 0
    want_path = re.search(r"SMALL_BRACKET = '([^']+)'", gen)
    want_stroke = re.search(r"SMALL_STROKE = ([\d.]+)", gen)
    if not (want_path and want_stroke):
        return Row("rail mark", MECHANICAL, [Finding(
            rel(MARK_GEOMETRY),
            "SMALL_BRACKET or SMALL_STROKE is gone from the generated mark. The lockup's rail "
            "end is built from them; with them missing this row compares nothing, which is worse than failing.",
        )], "")
    problems = []
    # THE SHIPPED COMPONENT IS CHECKED DIRECTLY.
    # `Lockup.tsx` does not COPY the rail's bracket — it imports `RAIL_ARM`, which
    # `build-lockup.mjs` generates by running the drawing's own `taperParts` at `tip = 1` and then
    # RENDERS against this file's stroked wire, refusing to write if they differ by more than 2%
    # of inked pixels at 10x. That is a stronger check than anything this row could perform, so
    # what is checked here is that it is still the check in force: a component that stops
    # importing the generated end, or grows a path literal, has quietly reintroduced the
    # invention this row was written for, one file further along.
    if exists(LOCKUP_TSX_):
        comp = read(LOCKUP_TSX_)
        if not re.search(r"import\s*\{[^}]*\bRAIL_ARM\b[^}]*\}\s*from\s*'\./lockupGeometry'", comp,
                         re.S):
            problems.append(Finding(
                rel(LOCKUP_TSX_),
                "the lockup no longer takes RAIL_ARM from the generated `lockupGeometry.ts`. That "
                "path is the collapse's rail end and the ONLY thing holding it to markGeometry.ts's "
                "own wire (D102, section 1) is the generator's pixel assertion against it; a "
                "component that draws its own is a second mark that agrees today.",
            ))
        if re.search(r"d=[\"']M[^\"']{40,}", comp):
            problems.append(Finding(
                rel(LOCKUP_TSX_),
                "a path literal is written into the lockup. Every drawing comes from the "
                "generator (D102); nothing about the mark is hand-drawn in app/.",
            ))
    if exists(LOCKUP_GEOMETRY):
        gen = read(LOCKUP_GEOMETRY)
        if "RAIL_ARM" not in gen:
            problems.append(Finding(
                rel(LOCKUP_GEOMETRY),
                "the generated geometry has no RAIL_ARM. The collapse morphs the bracket from the "
                "lockup's tapered frame to the mark's wire and needs both ends at one topology; "
                "without it the shell can only crossfade two drawings, which is what section 16 "
                "recorded as unavoidable and it was not.",
            ))
    # THE BROWSER TAB IS THE FOURTH SIDE, settled in section 18: the empty slot, the mark's own L,
    # no tile and no card. It is generated, so what can go wrong is a regeneration that quietly
    # reverts it to the whole mark — which would look entirely plausible and which no other row
    # here can see. A `<rect>` is the tell: the tile's sheen band and the card are both rects and
    # the bracket pair contains none.
    if exists(FAVICON):
        fav = read(FAVICON)
        compared += 3  # the rect, the settled paint, and the gradient
        if "<rect" in fav:
            problems.append(Finding(
                rel(FAVICON),
                "the browser tab is drawing a rect. Section 18 settles it as the EMPTY SLOT — the "
                "bracket pair alone, no tile, no card, no sheen — and every one of those three is "
                "a rect. The app icons keep the full mark; this file is the tab.",
            ))
        # THE PAINT IS SETTLED IN SECTION 18 AND READ FROM THERE, so the two cannot disagree —
        # `build-mark.mjs` greps that table rather than holding a hex. This row is what makes
        # that arrangement real: the spec is the state of record and the generated file has to
        # show it. The tab is the one Banchi surface NOT in a metal, and a regeneration that
        # quietly put the gradient back would look right on a dark bar and vanish on a light one,
        # which is the defect section 18 exists to record.
        want = re.search(r"\| paint \| \*\*flat `(#[0-9A-Fa-f]{6})`\*\*", read(LOGO_SPEC)) \
            if exists(LOGO_SPEC) else None
        if not want:
            problems.append(Finding(
                rel(LOGO_SPEC),
                "section 18 no longer settles the tab's paint as `| paint | **flat `#RRGGBB`** |`. "
                "`scripts/build-mark.mjs` reads that row and refuses to build without it.",
            ))
        elif want.group(1) not in fav:
            problems.append(Finding(
                rel(FAVICON),
                f"the browser tab is not painted {want.group(1)}, which is what section 18 settles. "
                "Gold is the only paint that reads on a dark browser bar and a light one, and the "
                "tab carries no ground of its own — silver vanishes on light, ink on dark.",
            ))
        if "Gradient" in fav:
            problems.append(Finding(
                rel(FAVICON),
                "the browser tab has a gradient. Section 18 settles it FLAT: at 16px the bracket "
                "pair is about twelve pixels of ink and a four-stop gradient across it resolves to "
                "noise. Every other surface keeps its metal; this one traded it for legibility.",
            ))
    return Row("rail mark", MECHANICAL, problems,
               "the rail bracket is the shipped mark — at both ends of the "
               "morph, and on the tab", scanned=compared)


def _lockup_params() -> Row:
    """docs/specs/logo.md's settled table and the generated lockup geometry agree.

    A settled parameter typed a second time is how these two drift. The spec is the store of
    record; `lockupGeometry.ts` is generated from it by `scripts/build-lockup.mjs`.

    Provably wrong when it fires — both sides are literals.
    """
    if not exists(LOGO_SPEC):
        # A ROW, NOT A RETURN — see `raw color`. A silent return deletes the row from
        # the render, and an absent row is the one state nothing in this file reads.
        return Row("lockup params", MECHANICAL, [],
                   "the spec is not there", scanned=0)

    spec_section = read(LOGO_SPEC)
    marker = "### The settled values, and the one place they live"
    if marker not in spec_section:
        return Row("lockup params", MECHANICAL, [Finding(
            rel(LOGO_SPEC),
            "the settled-values table is gone. This row compares it against the generated geometry; "
            "with it missing the row is not comparing anything, which is worse than failing.",
        )], "")
    tail = spec_section[spec_section.index(marker):]
    tail = tail[: tail.index("\n### ", 10)] if "\n### " in tail[10:] else tail
    published = {k: float(v) for k, v in _LOCKUP_SPEC_ROW.findall(tail)}

    if not published:
        return Row("lockup params", MECHANICAL, [Finding(
            rel(LOGO_SPEC),
            "no rows in the settled-values table. Say so here rather than passing.",
        )], "")

    findings: List[Finding] = []
    # THE GENERATED FILE IS THE COPY THE APP DRAWS FROM, reconciled both directions exactly as
    # `logo parity` does for `markPalettes.ts`. Without this row the app could draw a lockup the spec does not
    # describe and every other check would stay green — which is what `logo parity` exists for.
    if exists(LOCKUP_GEOMETRY):
        gen = read(LOCKUP_GEOMETRY)
        block = re.search(r"export const PARAMS = \{(.*?)\} as const", gen, re.S)
        if block is None:
            findings.append(Finding(
                rel(LOCKUP_GEOMETRY),
                "no `PARAMS` in the generated geometry. The app draws from this file; with the "
                "block missing nothing reconciles what it draws against the spec that settled it.",
            ))
        else:
            built = {k: float(v) for k, v in
                     re.findall(r"(\w+)\s*:\s*([0-9.]+)", block.group(1))}
            for key in sorted(set(published) & set(built)):
                if abs(built[key] - published[key]) > 1e-9:
                    findings.append(Finding(
                        f"{rel(LOCKUP_GEOMETRY)} -> {key}",
                        f"generated at {built[key]} and settled at {published[key]} in "
                        f"docs/specs/logo.md. Re-run `node scripts/build-lockup.mjs`, or move the "
                        f"spec first and say which round moved it.",
                    ))
            for key in sorted(set(published) - set(built)):
                findings.append(Finding(
                    rel(LOCKUP_GEOMETRY),
                    f"docs/specs/logo.md settles `{key}` and the generated geometry does not "
                    f"carry it. A settled value the app never receives is one the drawing can "
                    f"ignore.",
                ))

    return Row("lockup params", MECHANICAL, findings, scanned=len(published), summary=
               f"{len(published)} settled values against the generated geometry"
               if not findings else f"{len(findings)} disagreements")


def check_logo(report: Report) -> None:
    """The logo family, one row: parity, the mac icon grid, the lockup bracket, the rail
    mark and the lockup params — every reconciliation against docs/specs/logo.md.

    Merged from five rows by M3 (test-audit-2026-09-27, L8, Q8 yes). Each sub-check below
    is unchanged; only the last line of each moved from `report.add` to `return Row`, so
    every defect any of the five used to catch still fails this one.
    """
    merged = _merge_rows("logo", [
        _logo_parity(),
        _mac_icon_grid(),
        _lockup_params(),
        _rail_mark(),
        _lockup_bracket(),
    ])
    report.add("logo", merged.severity, merged.findings, merged.summary,
               scanned=merged.scanned)


# ------------------------------------------------------------------ views opsec (D24)

VIEWS_MANIFEST = ROOT / "scripts" / "views.txt"
APP_SRC = ROOT / "app" / "src"
APP_TSX = APP_SRC / "App.tsx"
APP_SERVER_TS = APP_SRC / "server.ts"
APP_TESTS = ROOT / "app" / "tests"

# The one origin `make dev` serves. strictPort in app/vite.config.ts exists so that a busy
# 5173 fails instead of quietly serving on 5174 — "where CLAUDE.md, this target and
# scripts/views.txt would all three be wrong" (Makefile). This set is the same fact.
APP_ORIGINS = {"localhost:5173", "127.0.0.1:5173"}

# A file whose CODE mentions the photo service. `photoUrl` is the single mint of
# `GET /photo/<box>/<index>` URLs (app/src/server.ts, D6); the literal path is the belt for
# a caller that builds the URL by hand. Run against comment-stripped text only — types.ts
# and Gallery.tsx both DISCUSS the route in prose and draw nothing from it.
_PHOTO_USE_RE = re.compile(r"\bphotoUrl\b|/photo/")


def _resolve_ts_module(from_file: Path, spec: str) -> Optional[Path]:
    base = from_file.parent / spec
    for candidate in (Path(str(base) + ".tsx"), Path(str(base) + ".ts")):
        if exists(candidate):
            return candidate
    return None


def _routes_table() -> Optional[Dict[str, Optional[Path]]]:
    """`app/src/App.tsx`'s ROUTES literal as route path -> component file, or None when the
    table cannot be read at all — which is a finding, not a shrug, because every verdict
    below hangs off it."""
    if not exists(APP_TSX):
        return None
    text = read(APP_TSX)
    table = re.search(r"const ROUTES[^=]*=\s*\[(.*?)\n\]", _strip_ts_comments(text), flags=re.S)
    if table is None:
        return None
    pairs = re.findall(r"path:\s*'([^']*)'[^{}]*?view:\s*([A-Za-z0-9_]+)", table.group(1))
    if not pairs:
        return None
    ident_to_spec: Dict[str, str] = {}
    for names, spec in re.findall(
        r"import\s+(?:type\s+)?([^;]*?)\s+from\s+['\"](\.[^'\"]+)['\"]", text
    ):
        for ident in re.findall(r"[A-Za-z0-9_]+", names):
            ident_to_spec[ident] = spec
    return {
        path: _resolve_ts_module(APP_TSX, ident_to_spec[view]) if view in ident_to_spec else None
        for path, view in pairs
    }


def _photo_reach(entry_file: Path) -> List[str]:
    """Every file in the component's import subtree whose code touches the photo service.

    Import-graph reach, not a judgment about what renders: a screen that imports a
    component that draws stored photos can draw them, and whether its runtime state ever
    does is exactly what this script cannot know. That asymmetry is why the row this feeds
    is advisory — see check_views_opsec.
    """
    seen: Set[Path] = set()
    stack = [entry_file]
    reached: List[str] = []
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            text = read(current)
        except Exception:
            continue
        if current != APP_SERVER_TS and _PHOTO_USE_RE.search(_strip_ts_comments(text)):
            reached.append(rel(current))
        for spec in re.findall(r"from\s+['\"](\.[^'\"]+)['\"]", text):
            if spec.endswith(".css"):
                continue
            resolved = _resolve_ts_module(current, spec)
            if resolved is not None:
                stack.append(resolved)
    return sorted(reached)


# A Playwright title, and ONLY off a bare `test(`. Every one of this repo's 370 tests is
# written that way, so nothing is lost by refusing `test.skip` and `test.only` — and a
# skipped proof must never go on holding a route out of the exposure list. Anything this
# cannot parse yields no title, which puts a route back IN the list rather than out of it.
_TEST_TITLE_RE = re.compile(
    r"^\s*test\(\s*(?P<q>['\"`])(?P<title>(?:\\.|(?!(?P=q))[^\\])*)(?P=q)",
    re.M,
)
_POOLED_SUBJECT_RE = re.compile(r"\bpooled\b", re.I)
_ABSOLUTE_NEGATIVE_RE = re.compile(r"\bnever\b", re.I)


def _pooled_absence_titles(spec_text: str) -> List[str]:
    """The test titles in a spec that CLAIM a pooled card is never drawn.

    The claim has to be in the TITLE, and that is the whole correction. A title is where
    this repo makes a spec answerable: it is the sentence the runner prints, the one a
    grep finds, and the one a person deletes when the behavior goes away. A spec's BODY
    carries the vocabulary whichever way its assertions run, so matching the body reads
    `pooled` out of a fixture field, a passing comment, or a proof of the OPPOSITE claim.

    MEASURED ON THE COMMITTED TREE, not predicted. The body match `pooled|located` held
    three routes out of the exposure list and not one of them asserted anything:

      - `app/tests/gallery.spec.ts` says `pooled` twelve times while proving the pooled
        row IS drawn — "the pooled row is a second no-bar shell, and it has not left".
        The spec whose subject is the pooled shape was the spec that suppressed the
        question about it.
      - `app/tests/inventory.spec.ts` matched on `located: true`, a fixture field.
      - `app/tests/pricing.spec.ts` contains no `pooled` at all. Its first match is the
        substring inside the word RELOCATED, in a comment about where a test was moved
        from. The pattern was not even word-bounded.

    A qualifying title names the pooled subject and makes an ABSOLUTE negative claim about
    it — `never`, not `not`. The row asks whether ANY render can contain a bearer
    instrument, so a title hedged to one case does not answer it, and `not` is how the two
    presence-asserting titles above happen to read ("has not left"). Two titles qualify
    today: the Fulfillment view's "a pooled card is never on his screen", which is the
    shape D24 asked for by name, and the review queue's "a pooled card never draws a
    photograph here", which cites this row in its own comment.

    What this still cannot do is read the assertions under the title, and a title using
    `never` to claim a pooled card is always drawn would pass it. That residual is a
    sentence a human deliberately wrote about a pooled card in the place this repo puts
    claims it stands behind, and the row is ADVISORY (D16). The defect being repaired is
    not a claim misjudged; it is that no claim was being read at all.
    """
    return [
        match.group("title")
        for match in _TEST_TITLE_RE.finditer(spec_text)
        if _POOLED_SUBJECT_RE.search(match.group("title"))
        and _ABSOLUTE_NEGATIVE_RE.search(match.group("title"))
    ]


def _pooled_exclusion_evidence(route_path: str) -> Optional[str]:
    """Committed proof that a route's screen never draws a pooled card's photo.

    The Fulfillment shape, exactly as D24 demanded it: `app/tests/fulfillment.spec.ts`
    asserts "a pooled card is never on his screen", in a spec `make design-check` runs.
    The tie is mechanical — the spec named after the route, carrying a TEST TITLE that
    makes that claim (`_pooled_absence_titles`, which argues the title/body line) — and
    self-cleaning: delete the assertion, or soften its title off the claim, and the route
    rejoins the exposure list. The root route has no segment to name a spec after, so it
    maps to `capture.spec.ts`: the capture screen is what `/` renders, and the manifest
    has always called it that.
    """
    name = route_path.strip("/") or "capture"
    if "/" in name:
        return None
    spec = APP_TESTS / f"{name}.spec.ts"
    if exists(spec) and _pooled_absence_titles(read(spec)):
        return rel(spec)
    return None


# ------------------------------------------------------- browser storage keys (D27, D94)

INDEX_HTML = ROOT / "app" / "index.html"

# A key literal, in either store. The two prefixes are the whole namespace: `banchi.` for
# anything written since the rebrand and `banchi.` for everything older, frozen at its
# spelling because renaming a live key silently discards what sits under the old one (D94).
_STORAGE_KEY_RE = re.compile(r"""['"]((?:banchi|banchi)\.[A-Za-z0-9._-]+)['"]""")

# The same key as a DOCUMENT writes it — bare, inside a fenced block, with no quotes to
# anchor on. D27's session roster is written that way, and reading it with the code regex
# above found nothing at all, which is a broken reader that reads like a broken entry.
_FENCED_STORAGE_KEY_RE = re.compile(r"\b((?:banchi|banchi)\.[A-Za-z0-9._-]+)")

# Which store a file touches. Member access only — `window.localStorage`, a bare
# `localStorage`, and the `window["localStorage"]` spelling the lint rule also has to cover.
_STORAGE_USE_RE = re.compile(r"""\b(local|session)Storage\b|['"](local|session)Storage['"]""")

# CLAUDE.md's published roster. Anchored on the sentence, not on a line number: the count is
# a WORD there because the sentence is prose, and a digit would read as a heading number.
_ROSTER_RE = re.compile(
    r"\*\*(\w+) keys are stored on the device.*?\*\*(.*?)(?=\n\n)", re.S
)
_ROSTER_FILE_RE = re.compile(r"`(app/src/[A-Za-z0-9_/]+\.tsx?)`")


def _storage_sites() -> Tuple[Dict[str, Dict[str, List[str]]], List[Finding]]:
    """Every browser-storage key the app writes, by store, with the files that hold it.

    KEYS ARE BOUND TO A STORE BY THEIR FILE, not by their call site, and that is the honest
    limit of this reader. `app/src/CaptureScreen.tsx` reaches its keys through one
    `readSession(key)` helper, so the literal and the `sessionStorage` call are in different
    functions and no regex walks from one to the other; `app/src/useCamera.ts` passes consts
    for the same reason `app/eslint.config.js` gives — a selector cannot read a key handed
    over as an identifier. What holds instead is that no file in this app touches both stores,
    which makes the file a sound binding — and a file that starts touching both is reported
    rather than guessed at, because that is the moment this reader would begin to lie.
    """
    findings: List[Finding] = []
    by_store: Dict[str, Dict[str, List[str]]] = {"local": {}, "session": {}}
    sources = sorted(APP_SRC.rglob("*.ts")) + sorted(APP_SRC.rglob("*.tsx"))
    for path in sources + [INDEX_HTML]:
        if not exists(path):
            continue
        text = read(path)
        body = _strip_ts_comments(text) if path.suffix != ".html" else re.sub(
            r"<!--.*?-->", "", text, flags=re.S
        )
        keys = sorted(set(_STORAGE_KEY_RE.findall(body)))
        if not keys:
            continue
        stores = {a or b for a, b in _STORAGE_USE_RE.findall(body)}
        if not stores:
            # A key spelling in a file that opens no store. Nothing does this today; it is
            # most likely a doc comment that survived the strip, so it is passed over rather
            # than reported — a false alarm on a comment is the one thing that would teach
            # somebody to route around this row.
            continue
        if len(stores) > 1:
            findings.append(
                Finding(
                    rel(path),
                    "touches both `localStorage` and `sessionStorage`, so this row cannot say "
                    "which store its keys belong to.\n"
                    f"  keys here: {', '.join('`' + k + '`' for k in keys)}\n"
                    "  Split the device-local keys into their own module the way "
                    "`app/src/deviceMemory.ts` already is, or bind each key to its store some "
                    "way a reader can follow. The binding is by FILE and there is no other.",
                )
            )
            continue
        store = stores.pop()
        for key in keys:
            by_store[store].setdefault(key, []).append(rel(path))
    return by_store, findings


def _decision_entry(number: int) -> Optional[Tuple[str, str]]:
    """(repo-relative path, text) of the entry whose heading is `## D<n> — …`, or None.

    FOUND BY HEADING AND NEVER BY FILENAME. A claim renames the file (D140), so a path
    typed here would go stale at the next merge while still pointing at a real document.
    """
    pattern = re.compile(rf"^##\s+D{number}\s+—", re.M)
    for path in decision_files():
        text = read(path)
        if pattern.search(text):
            return rel(path), text
    return None


def _session_fence_findings(session: Dict[str, List[str]]) -> List[Finding]:
    """D27's fenced session roster against what the app writes, in both directions.

    THE NARROWER PERMISSION HAD THE WEAKER READER. `localStorage` is reconciled against
    CLAUDE.md's count, roster and files in both directions; `sessionStorage` was held only
    to "named in some markdown", so D27's own fenced block could sit stale with the row
    green — and did. Measured 2026-09-12: the fence publishes EIGHT keys and the app writes
    TWO, because D142 moved six capture settings into `deviceMemory.ts`'s
    `banchi.capture.setup` on the operator's report that a shift ends when they stop
    feeding cards, which is neither a new tab nor a closed browser. The entry's next
    sentence still said `SESSION_KEYS` "declares the first seven"; it declares one.

    CLAUDE.md had already been corrected and dated for exactly this. The decision entry had
    not, and nothing could say so — which is the same defect this row was built for on the
    other store, where the sentence said FOUR and listed five for three days.

    **THE FENCE ONLY, NEVER THE SURROUNDING ARGUMENT.** D27 legitimately discusses the
    retired `banchi.*` spellings, the six keys that left, and what each one cost, all in
    prose. Reading the whole entry backwards would fail the commit over every abandoned key
    the entry exists to explain.
    """
    found = _decision_entry(27)
    if found is None:
        return [Finding(
            "docs/decisions/",
            "no entry headed `## D27 — …`, and it is what publishes the `sessionStorage` "
            "carve-out's roster. Renumbered, renamed past the heading grammar, or gone — "
            "either way this leg is reconciling nothing.",
        )]
    where, text = found
    fence = re.search(r"^```\n(.*?)^```", text, flags=re.M | re.S)
    if fence is None:
        return [Finding(
            where,
            "carries no fenced key block, and its roster is what this row reconciles "
            "against `app/src`.\n"
            "  Restore the fence, or say in the entry that the roster lives elsewhere — a "
            "leg with no subject prints green over whatever the app happens to write.",
        )]
    # BARE, not quoted. `_STORAGE_KEY_RE` reads a key literal out of CODE, where it wears
    # quotes; inside a fenced block a key is written as the app spells it and nothing else,
    # so the same regex found none and this leg printed a finding that read like a broken
    # entry rather than a broken reader.
    published = set(_FENCED_STORAGE_KEY_RE.findall(fence.group(1)))
    findings: List[Finding] = []
    if not published:
        return [Finding(
            where, "its fenced key block yields no key this row can read."
        )]
    for key in sorted(published - set(session)):
        findings.append(Finding(
            where,
            f"publishes `{key}` in its session roster and no file in `app/src` writes it to "
            "`sessionStorage`.\n"
            "  A key in the fence that the app does not write is a roster describing a "
            "product that has moved. Amend the entry with what happened to it — the fence "
            "is read, the argument around it is not.",
        ))
    for key in sorted(set(session) - published):
        findings.append(Finding(
            session[key][0],
            f"`{key}` is written to `sessionStorage` and D27's fenced roster does not name "
            "it.\n"
            "  That carve-out is the NARROWER permission: a key is in it because somebody "
            "argued the session scope is right for that value. Add it to the fence.",
        ))
    return findings


def check_storage_keys(report: Report) -> None:
    """Every browser-storage key the app writes, against what the docs publish.

    THIS ROW EXISTS BECAUSE THE PUBLISHED SENTENCE WAS WRONG AND NOTHING COULD SAY SO.
    CLAUDE.md read "**Four keys are stored on the device**" and then listed five, from
    2026-09-03 — the day `banchi.orders.last-check` landed — until 2026-09-06. In the same
    sentence the theme and the rail were attributed to `app/src/kit/index.tsx` and
    `App.tsx`, which is where they are USED; `app/src/deviceMemory.ts` is the module that
    holds them, and it exists precisely so that a reviewer has one file to read. Neither
    error was reachable from any check in this file.

    `app/eslint.config.js` is not that check and cannot become one. It bans the STORE by
    esquery selector and says so at length: a selector cannot read a key passed as a const,
    so the only exception it can express is a named FILE. It answers "may this file open
    `localStorage`" and never "which keys exist, what are they called, and does the
    documentation match" — which is the whole of what went wrong.

    TWO STORES, TWO DIFFERENT BARS, because the docs make two different promises.

     - `localStorage` is RECONCILED. CLAUDE.md publishes a count, a roster and the files, so
       all three are held against `app/src` in both directions. A key that survives closing
       the browser is the one a stale roster costs something for: D27 permits it only for
       facts about THIS MACHINE, and the way that permission erodes is one key at a time
       with nobody counting.
     - `sessionStorage` must only be NAMED IN MARKDOWN SOMEWHERE, the bar `check_env_names`
       sets for environment variables and for the reason given there — nothing mechanical
       can judge whether an explanation is any good, but it can hold that the key was
       written down once, on purpose, where a reader looking for it would find it. D27
       promised its keys were "named here" and named them only as English (*box number, set
       hint, finish claim…*) while the app spelled them with the old prefix. Measured
       2026-09-06: seven of the eight keys under that carve-out appeared in no markdown file
       in this repo, and two of them — `game` and `product` — had never been described in
       any form, having arrived after the entry was written.

    THE PREFIX IS HELD TOO, AS OF 2026-09-06, AND THIS ROW ARGUED THE OTHER WAY FIRST. The
    audit that built it proposed freezing `banchi.*` on the ten keys that carried it —
    D94 keeps every name beneath the product, a key's spelling is fixed on the day it is
    written, and renaming a live one discards whatever a browser holds under the old
    spelling. The owner overruled that after being shown the cost, declined a read-time
    fallback because a fallback can never safely be deleted afterwards, and took the loss:
    two presses on the rig, six on a capture tab left open across the deploy, and one key
    (`captureId`) that can burn a position if a capture was in flight at that moment. So
    there is no frozen set to remember, which is the only reason a prefix rule is checkable
    at all — `banchi.` on every key, with the whole argument in D27's second amendment.

    D94 IS NOT REOPENED BY THAT and this row is not evidence that it is. That entry governs
    the checkout, the CLI, the packages, the store on disk, every route on the wire and
    `BANCHI_HOME`; a storage key is a name this product writes and no other program reads,
    which is what separates it from every item on that list. Nothing here should be read as
    licence to rename anything else.
    """
    by_store, findings = _storage_sites()
    local, session = by_store["local"], by_store["session"]

    # THE PREFIX, over both stores at once. One line, because after the 2026-09-06 rename
    # there is no exception set to carry — the moment there is one, this becomes a list
    # somebody has to maintain and the rule stops being a rule.
    for key in sorted(set(local) | set(session)):
        if not key.startswith("banchi."):
            where = (local.get(key) or session.get(key) or ["app/src"])[0]
            findings.append(
                Finding(
                    where,
                    f"`{key}` does not carry the `banchi.` prefix every browser-storage key "
                    "has carried since 2026-09-06 (D27, second amendment).\n"
                    "  Ten keys were renamed off `banchi.` that day, with no migration and "
                    "the cost accepted in writing. A new key spelled the old way is not "
                    "continuity with them — they are gone — it is a second convention.",
                )
            )

    claude = ROOT / "CLAUDE.md"
    roster = _ROSTER_RE.search(read(claude)) if exists(claude) else None
    if roster is None:
        findings.append(
            Finding(
                "CLAUDE.md",
                "no `**N keys are stored on the device**` sentence found, so the roster this "
                "row reconciles is gone or reworded past the pattern watching it.\n"
                f"  the app writes {len(local)} `localStorage` key(s): "
                f"{', '.join('`' + k + '`' for k in sorted(local))}\n"
                "  Restore the sentence, or delete this row rather than leaving it passing "
                "vacuously — see docs/debts/ on a green row that cannot fail.",
            )
        )
    else:
        word, paragraph = roster.group(1), roster.group(0)
        published = set(_STORAGE_KEY_RE.findall(paragraph.replace("`", "'")))
        count = _NUMBER_WORDS.get(word.lower())
        if count is None:
            findings.append(
                Finding("CLAUDE.md", f"`{word} keys are stored on the device` — not a number word.")
            )
        elif count != len(local):
            findings.append(
                Finding(
                    "CLAUDE.md",
                    f"says `{word}` ({count}) keys are stored on the device; `app/src` writes "
                    f"{len(local)}.\n"
                    f"  in the app: {', '.join('`' + k + '`' for k in sorted(local))}\n"
                    "  This is the exact defect the row was built for: the sentence said four "
                    "and listed five for three days.",
                )
            )
        for key in sorted(published - set(local)):
            findings.append(
                Finding(
                    "CLAUDE.md",
                    f"`{key}` is published as a device-local key and no file in `app/src` "
                    "writes it to `localStorage`.",
                )
            )
        for key in sorted(set(local) - published):
            findings.append(
                Finding(
                    local[key][0],
                    f"`{key}` is written to `localStorage` and CLAUDE.md's roster does not "
                    "name it.\n"
                    "  D27 permits `localStorage` only for facts about THIS MACHINE. Add it "
                    "to that sentence with what it is a fact about, and correct the count.",
                )
            )
        named = set(_ROSTER_FILE_RE.findall(paragraph))
        holding = {f for files in local.values() for f in files if f.startswith("app/src/")}
        for path in sorted(named - holding):
            findings.append(
                Finding(
                    "CLAUDE.md",
                    f"the roster names `{path}` and that file writes no `localStorage` key.\n"
                    "  Name the module that HOLDS the key, not the screen that reads it back. "
                    "`App.tsx` and `kit/index.tsx` were named here and "
                    "`app/src/deviceMemory.ts`, which exists to hold them, was not.",
                )
            )
        for path in sorted(holding - named):
            findings.append(
                Finding(
                    path,
                    "writes a `localStorage` key and CLAUDE.md's roster does not name this "
                    f"file: {', '.join('`' + k + '`' for k in sorted(k for k in local if path in local[k]))}",
                )
            )

    documented = "\n".join(read(doc) for doc in markdown_files())
    for key in sorted(session):
        if key not in documented:
            findings.append(
                Finding(
                    session[key][0],
                    f"`{key}` is written to `sessionStorage` and named in no markdown file.\n"
                    "  D27 says the permitted keys are named there. Spell it — describing a "
                    "key in English is not naming it, and a key nothing spells is one no "
                    "search finds.",
                )
            )

    # ---- and D27's own fence, BOTH DIRECTIONS ------------------------------------------
    findings.extend(_session_fence_findings(session))

    report.add(
        "storage keys",
        MECHANICAL,
        findings,
        f"{len(local)} device-local keys against CLAUDE.md's roster, "
        f"{len(session)} session keys all named in markdown",
        scanned=len(local) + len(session),
    )


#: `# OFF_RENDER #/inventory — <reason>` in scripts/views.txt. A comment, so
#: `make screenshot` skips it and this row reads it — the same arrangement `OFF_NAV` has in
#: `App.tsx`, where the declaration lives beside the thing it is about rather than in a
#: checker. Either dash spelling, because a session writing this line will reach for both.
_OFF_RENDER_RE = re.compile(r"^#\s*OFF_RENDER\s+#?(\S+)\s*[—-]\s*(.+)$")


def _route_names() -> Dict[str, str]:
    """Every name a manifest line could legitimately use for a route -> that route's path.

    A route's SLUG (`/review` -> `review`) and its LABEL lowercased (`Home` -> `/`), both
    read out of the ROUTES table. The label is what makes `/` reachable by name at all: it
    has no slug, and `home` is what the render is called.
    """
    if not exists(APP_TSX):
        return {}
    names: Dict[str, str] = {}
    for path, label in re.findall(
        r"path:\s*'([^']*)'\s*,\s*label:\s*'([^']*)'", read(APP_TSX)
    ):
        slug = path.strip("/")
        if slug:
            names[slug] = path or "/"
        names[label.lower()] = path or "/"
    return names


def _render_manifest_findings(
    entries: List[Tuple[int, str, str]], off_render: Dict[str, str]
) -> Tuple[List[Finding], Set[str]]:
    """A render's filename names the screen it renders, and every absence says why.

    **A WRONG IMAGE WITH A RIGHT FILENAME IS WORSE THAN A MISSING ONE, because it is
    quotable as verification.** `capture http://localhost:5173/#/` sat in this manifest:
    a session rendering `captures/ui/capture.png` to check the capture screen was looking
    at the HOME page, and `make screenshot` exited 0. Home took the root hash when the
    shell was rebuilt and the line's NAME was never moved with its URL.

    **Clause one: a manifest name that names a route must point at that route.** Matched
    against the route's slug or its lowercased label, both read from ROUTES. A name that
    matches neither is left alone on purpose — `pull-confirm` is a kit specimen rendered
    off `#/gallery`, which is a deliberate arrangement and not a mislabelled screen.

    **Clause two: a route with no render says so, by name, with a reason.** It does NOT
    demand a line per route, which would re-arm an opsec leak the owner closed by ruling:
    `#/inventory` was removed from this manifest on 2026-09-05 because it draws a pooled
    card's photograph on purpose, and `#/codes` is the code-card screen. `OFF_RENDER` is
    where that argument lives, so a THIRTEENTH route cannot arrive unrendered and unargued
    — which is how `captures/ui/inventory.png` came to sit in the main checkout dated
    2026-08-29 while `app/src/Inventory.tsx` had moved on 2026-09-11, with no manifest line
    that would ever refresh it.
    """
    findings: List[Finding] = []
    names = _route_names()
    routes = _routes_table() or {}
    rendered: Set[str] = set()

    if not names or not routes:
        findings.append(Finding(
            rel(APP_TSX),
            "the ROUTES table yields no route name this row can read, so no render's "
            "filename is reconciled against the screen it draws and no absence is argued.",
        ))
        return findings, rendered

    for number, name, url in entries:
        route = (urlparse(url).fragment or "/").rstrip("/") or "/"
        rendered.add(route)
        wanted = names.get(name.lower())
        if wanted is None or wanted == route:
            continue
        findings.append(Finding(
            f"{rel(VIEWS_MANIFEST)}:{number}",
            f"is named `{name}`, which is the screen at `#{wanted}`, and renders "
            f"`#{route}`.\n"
            f"  The render lands at captures/ui/{name}.png, so a session opening it to "
            f"check `#{wanted}` is looking at a different screen and `make screenshot` "
            f"exits 0 — a wrong image with a right filename, quotable as verification.\n"
            f"  Point the URL at `#{wanted}`, or rename the line after the screen it "
            f"actually draws.",
        ))

    for route in sorted(routes):
        key = route.rstrip("/") or "/"
        if key in rendered or key in off_render:
            continue
        findings.append(Finding(
            rel(VIEWS_MANIFEST),
            f"`#{key}` is a registered route with no render and no reason given.\n"
            f"  Add a line for it, or declare the absence: "
            f"`# OFF_RENDER #{key} — <why>`. Four routes are deliberately unrendered and "
            f"each says why; a fifth arriving silently is a screen nothing has ever drawn, "
            f"which is how an image of one goes three weeks stale with nothing to refresh "
            f"it.",
        ))

    for route, reason in sorted(off_render.items()):
        if route in rendered:
            findings.append(Finding(
                rel(VIEWS_MANIFEST),
                f"declares `#{route}` OFF_RENDER ({reason}) and also renders it. One of the "
                f"two is stale, and a declaration that outlives its reason is how the list "
                f"stops being read.",
            ))
        elif route.rstrip("/") not in {r.rstrip("/") or "/" for r in routes}:
            findings.append(Finding(
                rel(VIEWS_MANIFEST),
                f"declares `#{route}` OFF_RENDER and no such route is registered. The "
                f"screen went; the declaration exempts nothing.",
            ))
    return findings, rendered
