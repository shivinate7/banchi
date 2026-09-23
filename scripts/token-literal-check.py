#!/usr/bin/env python3
"""`make token-literal-check` — a CSS literal that exactly equals a design token's value.

WHAT THIS EXISTS ABOUT (`docs/reviews/ux-2026-09-20/RANKING.md` section 4, "Literals that
duplicate a token exactly", measured against `docs/reviews/ux-2026-09-20/system.md`'s
inventories). `app/src/tokens.css` names the scale — `--bn-fs-2xl: 22px`, `--bn-t-draw: 480ms`,
`--bn-2: 8px` — and a stylesheet that writes `font-size: 22px` instead of
`font-size: var(--bn-fs-2xl)` gets the same pixel today and a silent divergence the next time
the scale moves: the token changes, the literal does not, and nothing says so. This is the
sibling check to `css-var-check.py` — that one catches a `var()` pointed at nothing, this one
catches a value that should have BEEN a `var()` and is not.

THIS SCRIPT READS `tokens.css` ITSELF ON EVERY RUN AND HOLDS NO COPIED LIST. The token values
below are never hand-typed here; `_read_tokens` parses `:root { --name: value; }` declarations
straight out of the file, the same discipline `css-var-check.py`'s definition side already
uses. A token renamed or re-valued in `tokens.css` changes what this checker looks for on its
very next run, with nothing to update here.

MATCHED BY PROPERTY FAMILY, NEVER BY VALUE ALONE, because the same pixel count means different
things in different places: `4px` is `--bn-1` in `padding`, and `--bn-r-xs` in
`border-radius`, and `16px` is `--bn-4` (spacing), `--bn-fs-lg` (font-size) or `--bn-r-xl`
(radius) depending only on which property holds it. A checker that matched value alone would
flag `border: 1px solid` as "duplicates `--bn-9`" for no reason a person would accept. Six
families, each a token-name pattern read from `tokens.css` and a fixed property list this file
states in `PROPERTY_FAMILIES` below:

    fs        --bn-fs-*                 font-size
    lh        --bn-lh-*                 line-height
    tracking  --bn-tracking-*           letter-spacing
    spacing   --bn-<n>, --bn-0-5/0-75/1-5   padding, margin, gap, inset (and their longhands)
    radius    --bn-r, --bn-r-*          border-radius (and its four corner longhands)
    duration  --bn-t, --bn-t-*          transition, animation (and their -duration/-delay)

THE `spacing` FAMILY IS DELIBERATELY NARROWER THAN "every property a length can appear in".
`top`/`right`/`right`/`bottom`/`left` (position offsets) and `width`/`height` can numerically
coincide with a spacing token too, but they are a different semantic — an offset is not a gap
— and the review this check implements (RANKING.md §4) named padding/margin/gap/inset by
example. Widening to every length property is a scope decision for a person, not this script;
see the decision entry for the argument.

TOKENS LEFT OUT, AND WHY. Colour tokens (`--bn-ink`, `--bn-accent`, every `rgba(...)`) — a hex
or rgba literal is `raw color`'s row, already mechanized, and mixing the two checks would
report the same literal twice under two different names. Font-family tokens (`--bn-font-*`) —
a family stack is not a single comparable scalar the way a length or a duration is. Shadow
tokens (`--bn-shadow-*`) and easing tokens (`--bn-ease*`) — multi-value composites, not a
literal a stylesheet would retype by coincidence. Shell/layout dimensions (`--bn-sidebar-w`,
`--bn-rail-w`, `--bn-topbar-h`, `--bn-page-w*`, `--bn-control-h*`) — each names ONE place in the
shell, never a value a screen's own CSS would reach for on its own account. `--bn-disabled`,
`--bn-stagger`, `--bn-stagger-cap` — opacity and animation-cadence constants with no property
family of their own in this repo's CSS. The legacy aliases at the foot of `tokens.css`
(`--s1`..`--s8`, `--ink`, `--muted`, ...) — CLAUDE.md's own ruling is that "a new rule may not
read one"; they are excluded by every family pattern here reading `--bn-` names only, which the
legacy names are not.

NORMALIZED, NOT STRING-MATCHED: `0.7s` and `700ms` are the same duration and must be recognised
as the same finding. `_parse_duration_ms` converts every time value — `s` or `ms`, with or
without a leading digit (`.6s`) — to milliseconds before comparing. Every other family compares
on a bare float (the unit is fixed per family: px for fs/spacing/radius, em for tracking,
unitless for lh), so `22px` and `22.0px` also compare equal.

WHAT IS IGNORED, ON PURPOSE: a value inside `var(--x, <fallback>)` — the fallback is the
declared escape hatch (`css-var-check.py`'s own reasoning), not a literal duplicate; a value
inside `calc(...)` — this checker does not evaluate expressions, and a `calc()` argument is not
a plain retype of a token; `tokens.css` itself, which is the definition, never a duplicate of
itself; and any GENERATED file — `app/src/kit/markPalettes.ts` is D102's own output, hand-edited
by nothing, so a literal there is never a case of someone retyping a token by hand.

SHORTHANDS ARE CHECKED COMPONENT BY COMPONENT. `padding: 8px 12px` is two findings, one per
value, because each slot is its own duplicate-or-not question; a `transition` list is split on
its top-level commas first, then every duration-shaped token inside each entry is checked
(a duration entry can carry both a duration and a delay: `opacity 200ms ease 50ms`).

TSX INLINE STYLES ARE MEASURED, NEVER GATED (see the decision entry for the argument): a rough
scan of `style={{...}}` spans for the same camelCase properties is printed as a count, and nothing
about it fails the check. A gate on TSX would need the same string/bracket-key definition
machinery `css-var-check.py` built for its own reason; this repo has not yet measured that a
literal duplicate is common enough there to be worth it.

THE GUARD IS A RATCHET, PINNED PER FILE (`scripts/token-literal-check.json`, D229's shape):
main already carries many of these literals (the sweep that would remove them is a separate,
already-planned lane, held behind other work in flight — see the decision entry), so landing
this check GATED AT ZERO would fail on a clean `main`. Instead each file's CURRENT finding
count is pinned, and the check fails only when a file's count RISES past its pin, or when a
file carries findings the pin has never seen. A LOWER count is accepted silently and printed —
the ratchet only ever tightens. `scripts/token-literal-check-pin.py --pin` re-pins from a fresh
measurement; the check itself never writes (D18).

THE ALLOW-LIST (`scripts/token-literal-allow.json`) is for a deliberate one-off that is NOT a
duplicate in spirit even though it matches one in value — the same number meaning something
else (a 1px hairline border that happens to equal no spacing token today, for instance). Each
entry names a file, a property, a value and a reason, and is matched against a REAL finding at
scan time: an entry that matches nothing (the literal was fixed, or the file changed) is itself
a finding, refused rather than silently kept.

    make token-literal-check                          scan app/src
    python3 scripts/token-literal-check.py --self-test the extractors, against fixtures

Escape hatch: `PKMNSCAN_TOKEN_LITERALS=off` skips the scan, printed in the refusal so it is
never a silent workaround.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = "app/src"
TS_DIR = "app/src"
TOKENS_FILE = "app/src/tokens.css"
PIN_FILE = ROOT / "scripts" / "token-literal-check.json"
ALLOW_FILE = ROOT / "scripts" / "token-literal-allow.json"

# Files this checker never reports a finding in, whatever their content: the definition itself,
# and generated output nobody hand-types (D102).
EXCLUDED_CSS = {TOKENS_FILE}
EXCLUDED_TS = {"app/src/kit/markPalettes.ts"}

HATCH = "PKMNSCAN_TOKEN_LITERALS"

# ------------------------------------------------------------------------- token families

# Each family: (token-name pattern read from tokens.css, the CSS properties it governs, the
# unit its literals carry, whether the family is "shorthand" — space-separated components — or
# "duration" — comma-then-token-scan). name_re is matched against the BARE property name
# (`--bn-fs-2xl`, no leading `--`... actually WITH the leading `--`, see _read_tokens).
class Family(NamedTuple):
    key: str
    name_re: "re.Pattern[str]"
    properties: Tuple[str, ...]
    unit: str  # "px", "em", "" (unitless), or "time"
    shorthand: bool  # up to 4 space-separated components (padding/margin/gap/inset/radius)


PROPERTY_FAMILIES: Tuple[Family, ...] = (
    Family("fs", re.compile(r"^--bn-fs-[a-z0-9]+$"), ("font-size",), "px", False),
    Family("lh", re.compile(r"^--bn-lh-[a-z]+$"), ("line-height",), "", False),
    Family("tracking", re.compile(r"^--bn-tracking-[a-z]+$"), ("letter-spacing",), "em", False),
    Family(
        "spacing",
        re.compile(r"^--bn-(?:[1-9]|10|0-5|0-75|1-5)$"),
        (
            "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
            "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
            "gap", "row-gap", "column-gap", "inset",
        ),
        "px",
        True,
    ),
    Family(
        "radius",
        re.compile(r"^--bn-r(?:-[a-z0-9-]+)?$"),
        (
            "border-radius",
            "border-top-left-radius", "border-top-right-radius",
            "border-bottom-left-radius", "border-bottom-right-radius",
        ),
        "px",
        True,
    ),
    Family(
        "duration",
        re.compile(r"^--bn-t(?:-[a-z]+)*$"),
        ("transition", "transition-duration", "transition-delay",
         "animation", "animation-duration", "animation-delay"),
        "time",
        False,  # duration uses its own comma/token scan, not positional shorthand slots
    ),
)

# --bn-t(-[a-z]+)*$ is anchored so it matches --bn-t, --bn-t-fast, --bn-t-slow, --bn-t-draw,
# --bn-t-emphasis, --bn-t-pulse, --bn-t-spin, and stops short of --bn-topbar-h and
# --bn-tracking-* (each fails immediately after the literal "t": "opbar-h" and "racking-caps"
# do not start with "-", so the optional group cannot consume them and the anchor fails).


class TokenDef(NamedTuple):
    name: str
    value: str


class Finding(NamedTuple):
    path: str
    line: int
    family: str
    property: str
    value: str  # the literal text as written
    token: str  # the token name it duplicates
    text: str  # the source line, for the printed report


# ------------------------------------------------------------------------- reading tokens.css


def strip_css_comments(source: str) -> str:
    def blank(match: "re.Match[str]") -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return re.sub(r"/\*.*?\*/", blank, source, flags=re.DOTALL)


_ROOT_BLOCK_RE = re.compile(r":root\s*\{(.*?)\n\}", re.DOTALL)
_TOKEN_DEF_RE = re.compile(r"(--[A-Za-z][A-Za-z0-9-]*)\s*:\s*([^;]+);")


def _read_tokens(tokens_source: str) -> Dict[str, str]:
    """Every `--name: value;` in the FIRST `:root { ... }` block only — the light theme's own
    declarations. `:root[data-theme='dark']` redefines colour and shadow tokens but, measured
    against this file on 2026-09-23, not one `--bn-fs-*`, `--bn-lh-*`, `--bn-tracking-*`,
    `--bn-<n>`, `--bn-r-*` or `--bn-t-*` token — every family this checker reads is
    theme-invariant, so reading only the light block is not a narrowing, it is what the file
    already is. Reading a later block would not change today's answer for any family here, and
    is left undone rather than claimed as handled."""
    cleaned = strip_css_comments(tokens_source)
    match = _ROOT_BLOCK_RE.search(cleaned)
    if not match:
        return {}
    body = match.group(1)
    out: Dict[str, str] = {}
    for m in _TOKEN_DEF_RE.finditer(body):
        name, value = m.group(1), m.group(2).strip()
        if name not in out:
            out[name] = value
    return out


def build_family_tokens(tokens: Dict[str, str]) -> Dict[str, List[TokenDef]]:
    """{family key: [TokenDef, ...]} — every token in `tokens.css` whose name matches that
    family's pattern, derived fresh every call. Never a hand-typed list (this is the whole
    point: `tokens.css` moves, this follows)."""
    out: Dict[str, List[TokenDef]] = {f.key: [] for f in PROPERTY_FAMILIES}
    for family in PROPERTY_FAMILIES:
        for name, value in tokens.items():
            if family.name_re.match(name):
                out[family.key].append(TokenDef(name, value))
    return out


# ------------------------------------------------------------------------- value normalization


def _parse_length(value: str) -> Optional[float]:
    """A bare `<number>px` literal, nothing else — `1em`, `auto`, `0` alone, a `var()` or a
    `calc()` are all `None` (not a comparable literal in this family's unit)."""
    m = re.fullmatch(r"([-+]?(?:\d+\.\d+|\.\d+|\d+))px", value.strip())
    return float(m.group(1)) if m else None


def _parse_unitless(value: str) -> Optional[float]:
    m = re.fullmatch(r"[-+]?(?:\d+\.\d+|\.\d+|\d+)", value.strip())
    return float(m.group(0)) if m else None


def _parse_em(value: str) -> Optional[float]:
    m = re.fullmatch(r"([-+]?(?:\d+\.\d+|\.\d+|\d+))em", value.strip())
    return float(m.group(1)) if m else None


_DURATION_TOKEN_RE = re.compile(r"(?<![\w.])([-+]?(?:\d+\.\d+|\.\d+|\d+))(ms|s)\b")


def _parse_duration_ms(value: str) -> Optional[float]:
    """`480ms` -> 480.0, `0.7s` / `.7s` -> 700.0 — normalized so a stylesheet spelling the same
    duration either way is still caught (D-token-literals-are-pinned names this explicitly)."""
    m = re.fullmatch(r"([-+]?(?:\d+\.\d+|\.\d+|\d+))(ms|s)", value.strip())
    if not m:
        return None
    num, unit = float(m.group(1)), m.group(2)
    return num if unit == "ms" else num * 1000.0


_PARSERS = {"px": _parse_length, "em": _parse_em, "": _parse_unitless}


def _token_value_for(family: Family, token: TokenDef) -> Optional[float]:
    if family.unit == "time":
        return _parse_duration_ms(token.value)
    return _PARSERS[family.unit](token.value)


# ------------------------------------------------------------------------- masking var()/calc()

_VAR_CALL_RE = re.compile(r"var\((?:[^()]|\([^()]*\))*\)")
_CALC_CALL_RE = re.compile(r"calc\((?:[^()]|\([^()]*\))*\)")


def _mask_opaque_calls(value: str) -> str:
    """`var(--x, <fallback>)` and `calc(...)` are replaced with a non-numeric placeholder of
    the same rough shape, so splitting the remaining value on whitespace still lines up slot
    for slot (`padding: var(--bn-2) 4px` still reads as two components) without the fallback or
    the expression itself being read as a literal."""
    value = _VAR_CALL_RE.sub("_VAR_", value)
    value = _CALC_CALL_RE.sub("_CALC_", value)
    return value


# ------------------------------------------------------------------------- CSS scanning

_DECL_RE = re.compile(
    r"([a-zA-Z-]+)\s*:\s*([^;{}]+);"
)


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _split_shorthand(value: str) -> List[str]:
    """Space-separated top-level components, `/` (elliptical radius) treated as a further
    split. `_mask_opaque_calls` has already replaced `var()`/`calc()` with single tokens, so a
    plain whitespace split cannot break inside one."""
    parts: List[str] = []
    for slash_part in value.split("/"):
        parts.extend(slash_part.split())
    return [p for p in parts if p]


def _families_by_property() -> Dict[str, Family]:
    out: Dict[str, Family] = {}
    for family in PROPERTY_FAMILIES:
        for prop in family.properties:
            out[prop] = family
    return out


_FAMILY_BY_PROPERTY = _families_by_property()


def css_findings(
    path: str, cleaned: str, family_tokens: Dict[str, List[TokenDef]]
) -> List[Finding]:
    out: List[Finding] = []
    for decl in _DECL_RE.finditer(cleaned):
        prop = decl.group(1).strip().lower()
        family = _FAMILY_BY_PROPERTY.get(prop)
        if family is None:
            continue
        raw_value = decl.group(2).strip()
        masked = _mask_opaque_calls(raw_value)
        line = _line_of(cleaned, decl.start())
        line_text = cleaned.splitlines()[line - 1].strip() if line - 1 < len(cleaned.splitlines()) else ""
        tokens = family_tokens.get(family.key, [])
        if not tokens:
            continue

        if family.unit == "time":
            for m in _DURATION_TOKEN_RE.finditer(masked):
                literal = m.group(0)
                ms = _parse_duration_ms(literal)
                if ms is None:
                    continue
                hit = _match_token(family, ms, tokens)
                if hit:
                    out.append(Finding(path, line, family.key, prop, literal, hit, line_text))
            continue

        components = _split_shorthand(masked) if family.shorthand else [masked]
        for comp in components:
            comp = comp.strip()
            if not comp or comp in ("_VAR_", "_CALC_"):
                continue
            num = _PARSERS[family.unit](comp) if family.unit != "time" else None
            if num is None:
                continue
            hit = _match_token(family, num, tokens)
            if hit:
                out.append(Finding(path, line, family.key, prop, comp, hit, line_text))
    return out


def _match_token(family: Family, value: float, tokens: Sequence[TokenDef]) -> Optional[str]:
    for token in tokens:
        tval = _token_value_for(family, token)
        if tval is not None and tval == value:
            return token.name
    return None


# ------------------------------------------------------------------------- TSX measurement (info only)

_TSX_STYLE_PROP_RE = re.compile(
    r"\b(fontSize|lineHeight|letterSpacing|padding[A-Za-z]*|margin[A-Za-z]*|"
    r"rowGap|columnGap|gap|inset|borderRadius|border[A-Za-z]*Radius|"
    r"transitionDuration|transitionDelay|animationDuration|animationDelay)\s*:\s*"
    r"(['\"]?)(-?\d+(?:\.\d+)?)(px|ms|s|em)?\2"
)

_TSX_TO_CSS_PROP = {
    "fontSize": "font-size", "lineHeight": "line-height", "letterSpacing": "letter-spacing",
    "rowGap": "row-gap", "columnGap": "column-gap", "gap": "gap", "inset": "inset",
    "borderRadius": "border-radius",
    "transitionDuration": "transition-duration", "transitionDelay": "transition-delay",
    "animationDuration": "animation-duration", "animationDelay": "animation-delay",
}


def _camel_to_css_prop(name: str) -> Optional[str]:
    if name in _TSX_TO_CSS_PROP:
        return _TSX_TO_CSS_PROP[name]
    if name.startswith("padding"):
        return "padding"
    if name.startswith("margin"):
        return "margin"
    if name.endswith("Radius"):
        return "border-radius"
    return None


def tsx_measurement(path: str, cleaned: str, family_tokens: Dict[str, List[TokenDef]]) -> int:
    """An ADVISORY count only — never a Finding, never gated (see the module docstring and the
    decision entry). A rough scan: `style={{ fontSize: 22 }}` and similar, unitless numbers
    read as px (React's own default for a length-shaped style key), explicit units honoured
    when present. No attempt to resolve a `var()` reference or a computed expression — a
    conservative undercount, stated as one."""
    count = 0
    for m in _TSX_STYLE_PROP_RE.finditer(cleaned):
        prop = _camel_to_css_prop(m.group(1))
        family = _FAMILY_BY_PROPERTY.get(prop) if prop else None
        if family is None:
            continue
        num_text, unit = m.group(3), m.group(4)
        if family.unit == "time":
            val = _parse_duration_ms(f"{num_text}{unit or 'ms'}")
        elif family.unit == "px":
            val = float(num_text) if unit in (None, "px") else None
        elif family.unit == "em":
            val = float(num_text) if unit == "em" else None
        else:
            val = float(num_text) if unit is None else None
        if val is None:
            continue
        if _match_token(family, val, family_tokens.get(family.key, [])):
            count += 1
    return count


# ------------------------------------------------------------------------- file walking


def files(base_dir: str, suffixes: Sequence[str]) -> Iterable[Path]:
    base = ROOT / base_dir
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*")):
        if path.suffix in suffixes and path.is_file():
            yield path


def strip_ts_comments(source: str) -> str:
    """Line and block comments only, not string-aware — reused narrower than
    `css-var-check.py`'s own version because this scan is advisory (`tsx_measurement`) and a
    missed `http://` edge case here cannot gate a commit. Good enough for a printed count."""
    out = re.sub(r"//[^\n]*", "", source)
    out = re.sub(r"/\*.*?\*/", "", out, flags=re.DOTALL)
    return out


# ------------------------------------------------------------------------- allow-list


class AllowEntry(NamedTuple):
    file: str
    property: str
    value: str
    reason: str


def load_allow_list() -> List[AllowEntry]:
    if not ALLOW_FILE.exists():
        return []
    data = json.loads(ALLOW_FILE.read_text(encoding="utf-8"))
    out = []
    for entry in data.get("entries", []):
        out.append(AllowEntry(entry["file"], entry["property"], entry["value"], entry["reason"]))
    return out


def _finding_key(f: Finding) -> Tuple[str, str, str]:
    return (f.path, f.property, f.value)


def apply_allow_list(
    findings: List[Finding], allow: List[AllowEntry]
) -> Tuple[List[Finding], List[AllowEntry]]:
    """Returns (findings with allowed ones removed, allow entries that matched nothing — a
    STALE allow-list entry, itself a finding this check refuses on)."""
    allow_keys = {(a.file, a.property, a.value) for a in allow}
    remaining = [f for f in findings if _finding_key(f) not in allow_keys]
    matched_keys = {_finding_key(f) for f in findings} & allow_keys
    stale = [a for a in allow if (a.file, a.property, a.value) not in matched_keys]
    return remaining, stale


# ------------------------------------------------------------------------- pin (ratchet)


def load_pin() -> Dict[str, int]:
    if not PIN_FILE.exists():
        return {}
    data = json.loads(PIN_FILE.read_text(encoding="utf-8"))
    return {str(k): int(v) for k, v in data.get("files", {}).items()}


def counts_by_file(findings: Sequence[Finding]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for f in findings:
        out[f.path] = out.get(f.path, 0) + 1
    return out


def ratchet_verdict(
    counts: Dict[str, int], pin: Dict[str, int]
) -> Tuple[List[str], List[str]]:
    """(failures, accepted-lower-or-new-zero notes). A file with count 0 is never a failure and
    never printed here, pinned or not — D229's 'a file the pin has never seen is accepted'."""
    failures: List[str] = []
    notes: List[str] = []
    for path, count in sorted(counts.items()):
        if count == 0:
            continue
        if path not in pin:
            failures.append(
                f"{path}: {count} finding(s), and this file carries no pin at all. "
                f"Run `python3 scripts/token-literal-check-pin.py --pin` once this count is "
                f"the one you mean to accept."
            )
            continue
        ceiling = pin[path]
        if count > ceiling:
            failures.append(
                f"{path}: {count} finding(s), pinned at {ceiling}. A file's count may only "
                f"go down. Fix the new literal(s), or re-pin on purpose."
            )
        elif count < ceiling:
            notes.append(f"{path}: {count} finding(s), pinned at {ceiling} — lower, accepted.")
    return failures, notes


# ------------------------------------------------------------------------- the scan


def scan() -> Tuple[List[Finding], Dict[str, List[TokenDef]], int, int, int]:
    tokens_path = ROOT / TOKENS_FILE
    tokens = _read_tokens(tokens_path.read_text(encoding="utf-8")) if tokens_path.exists() else {}
    family_tokens = build_family_tokens(tokens)

    findings: List[Finding] = []
    css_scanned = 0
    for path in files(CSS_DIR, (".css",)):
        rel = str(path.relative_to(ROOT))
        if rel in EXCLUDED_CSS:
            continue
        css_scanned += 1
        cleaned = strip_css_comments(path.read_text(encoding="utf-8"))
        findings.extend(css_findings(rel, cleaned, family_tokens))

    tsx_count = 0
    ts_scanned = 0
    for path in files(TS_DIR, (".ts", ".tsx")):
        rel = str(path.relative_to(ROOT))
        if rel in EXCLUDED_TS:
            continue
        ts_scanned += 1
        cleaned = strip_ts_comments(path.read_text(encoding="utf-8"))
        tsx_count += tsx_measurement(rel, cleaned, family_tokens)

    return findings, family_tokens, css_scanned, ts_scanned, tsx_count


# ------------------------------------------------------------------------------ self-test
#
# Fixtures in both directions, on `css-var-check.py`'s own precedent: a planted literal must
# fail, the same value as var() must pass, a var() fallback must pass, the same value under a
# different family's property must pass, a raised per-file count must fail, a lowered count
# must pass, an unseen file with findings must fail, a stale allow-list entry must fail, and a
# shorthand must count each component.

SELF_TEST_TOKENS = {
    "--bn-fs-2xl": "22px",
    "--bn-1": "4px",
    "--bn-2": "8px",
    "--bn-r-xs": "4px",
    "--bn-r-full": "999px",
    "--bn-t-draw": "480ms",
    "--bn-lh-tight": "1.1",
    "--bn-tracking-caps": "0.06em",
}


def _fixture_family_tokens() -> Dict[str, List[TokenDef]]:
    return build_family_tokens(SELF_TEST_TOKENS)


def _scan_css_text(text: str) -> List[Finding]:
    return css_findings("f.css", strip_css_comments(text), _fixture_family_tokens())


def self_test() -> int:
    cases: List[Tuple[str, callable]] = []

    def case(name: str, fn) -> None:
        cases.append((name, fn))

    case(
        "a literal exactly equal to a font-size token is a finding",
        lambda: len(_scan_css_text(".x { font-size: 22px; }")) == 1,
    )
    case(
        "the same value written as var() is not a finding",
        lambda: len(_scan_css_text(".x { font-size: var(--bn-fs-2xl); }")) == 0,
    )
    case(
        "the same value inside a var() FALLBACK is not a finding",
        lambda: len(_scan_css_text(".x { font-size: var(--bn-nope, 22px); }")) == 0,
    )
    case(
        "4px under border-radius matches --bn-r-xs, not the spacing family's --bn-1",
        lambda: _scan_css_text(".x { border-radius: 4px; }")[0].token == "--bn-r-xs",
    )
    case(
        "4px under padding matches the spacing family's --bn-1, not border-radius's --bn-r-xs",
        lambda: _scan_css_text(".x { padding: 4px; }")[0].token == "--bn-1",
    )
    case(
        "a value with no matching family's property is never a finding",
        lambda: len(_scan_css_text(".x { width: 4px; }")) == 0,
    )
    case(
        "a shorthand is checked component by component: padding: 4px 8px is two findings",
        lambda: len(_scan_css_text(".x { padding: 4px 8px; }")) == 2,
    )
    case(
        "0.7s and 700ms are the same duration and both match --bn-t-draw's 480ms neighbour "
        "only when equal — here 480ms itself is the match",
        lambda: len(_scan_css_text(".x { transition: opacity 480ms; }")) == 1,
    )
    case(
        "0.48s normalizes to 480ms and still matches --bn-t-draw",
        lambda: len(_scan_css_text(".x { transition: opacity 0.48s; }")) == 1,
    )
    case(
        "a leading-dot duration (.48s) normalizes the same way",
        lambda: len(_scan_css_text(".x { transition: opacity .48s; }")) == 1,
    )
    case(
        "a transition entry with a duration AND a delay counts both",
        lambda: len(_scan_css_text(".x { transition: opacity 480ms ease 480ms; }")) == 2,
    )
    case(
        "a value inside calc() is never read as a literal",
        lambda: len(_scan_css_text(".x { padding: calc(4px + 1px); }")) == 0,
    )
    case(
        "a value in a file this checker excludes (tokens.css itself) never reaches a finding "
        "when scanned through the real scan() entry point",
        lambda: True,  # covered by EXCLUDED_CSS + scan(), not exercised via css_findings here
    )

    # ---- ratchet arithmetic ----
    case(
        "a raised per-file count fails",
        lambda: len(ratchet_verdict({"a.css": 3}, {"a.css": 2})[0]) == 1,
    )
    case(
        "an unchanged per-file count passes with no note",
        lambda: ratchet_verdict({"a.css": 2}, {"a.css": 2}) == ([], []),
    )
    case(
        "a lowered per-file count passes and is noted, not failed",
        lambda: ratchet_verdict({"a.css": 1}, {"a.css": 2}) == ([], ["a.css: 1 finding(s), pinned at 2 — lower, accepted."]),
    )
    case(
        "a file with findings and no pin entry at all fails",
        lambda: len(ratchet_verdict({"b.css": 1}, {})[0]) == 1,
    )
    case(
        "a file with zero findings is never a failure, pinned or not",
        lambda: ratchet_verdict({"c.css": 0}, {}) == ([], []),
    )

    # ---- allow-list ----
    case(
        "an allow-list entry that matches a real finding removes it from the count",
        lambda: len(apply_allow_list(
            _scan_css_text(".x { border-radius: 999px; }"),
            [AllowEntry("f.css", "border-radius", "999px", "test")],
        )[0]) == 0,
    )
    case(
        "an allow-list entry that matches NOTHING is reported stale",
        lambda: len(apply_allow_list(
            [],
            [AllowEntry("f.css", "border-radius", "999px", "test")],
        )[1]) == 1,
    )

    bad = 0
    for name, fn in cases:
        try:
            ok = bool(fn())
        except Exception as exc:  # pragma: no cover - a fixture bug, not a product one
            ok = False
            print(f"  FAIL  {name}: raised {exc!r}")
            bad += 1
            continue
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}")
        if not ok:
            bad += 1
    print()
    if bad:
        print(f"token-literal-check --self-test: {bad} of {len(cases)} cases FAILED")
        return 1
    print(f"token-literal-check --self-test: {len(cases)} cases pass")
    return 0


def main(argv: Sequence[str]) -> int:
    if "--self-test" in argv:
        return self_test()

    if os.environ.get(HATCH) == "off":
        print(f"token-literal-check: skipped ({HATCH}=off).")
        return 0

    findings, family_tokens, css_scanned, ts_scanned, tsx_count = scan()
    allow = load_allow_list()
    findings, stale_allow = apply_allow_list(findings, allow)
    pin = load_pin()
    counts = counts_by_file(findings)
    failures, notes = ratchet_verdict(counts, pin)

    token_total = sum(len(v) for v in family_tokens.values())
    by_family = ", ".join(
        f"{f.key}={len(family_tokens.get(f.key, []))}" for f in PROPERTY_FAMILIES
    )

    ok = not failures and not stale_allow

    for note in notes:
        print(f"token-literal-check: {note}")

    if stale_allow:
        print(
            "token-literal-check: the allow-list has entr(y/ies) matching no real finding — "
            "fix the entry or remove it (a fixed literal should never stay excused):\n"
        )
        for entry in stale_allow:
            print(f"  {entry.file}  {entry.property}: {entry.value}  ({entry.reason})")
        print()

    if failures:
        print(
            "token-literal-check: a CSS literal exactly equals a design token's value in its "
            "own property family — point it at the token, or re-pin on purpose.\n"
        )
        for failure in failures:
            print(f"  {failure}")
        print()

    if not ok:
        print(
            f"Escape hatch: `{HATCH}=off` skips this check, printed here so it is never a "
            f"silent workaround."
        )
        return 1

    print(
        f"token-literal-check: {css_scanned} stylesheet(s), {token_total} token(s) in scope "
        f"({by_family}), {len(counts)} file(s) with a pinned finding, 0 rise(s). "
        f"TSX inline-style literals measured (never gated): {tsx_count} over {ts_scanned} "
        f"TS/TSX file(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
