"""Design tokens, raw color and breakpoints."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

from .core import ADVISORY, Finding, MECHANICAL, ROOT, Report, _sibling, exists, read, rel

# ------------------------------------------------ the palette the app actually renders from

DESIGN = ROOT / "docs" / "DESIGN.md"
TOKENS_CSS = ROOT / "app" / "src" / "tokens.css"

COLOR = "color"
TYPEFACE = "typeface"
LENGTH = "length"

# The two files name the same token differently in exactly two places, and both differences
# are cosmetic: the type rows are headed by the job a face does (`Utility`) where the
# property is abbreviated (`--util`), and the spacing scale is one row of numbers where the
# properties are `--s1`, `--s2` and so on. Renaming one side to match the other was the
# obvious alternative and is the wrong one — app/src/tokens.css says in its own header that
# its property names match the palette sheet that once sat beside it, and the doc's block is laid out to
# be read as a palette by a person. A three-line table is cheaper than either file getting
# worse to spare it.
# THE BLOCK NAMES TOKENS; IT NO LONGER SPELLS A PALETTE IN ROWS. What the old reader parsed —
# `Color #FCFCFD bg`, three typeface rows, one spacing row, one radius row — is a format that
# stopped existing when the `--bn-` system landed, and the reader read zero tokens from the new
# block and said so. These four read what the block actually writes.
_BN_NAME_RE = re.compile(r"--bn-[a-z0-9]+(?:-[a-z0-9]+)*")
# `--bn-fs-2xs … --bn-fs-5xl` and `--bn-1 … --bn-10`, in both the ellipsis and the three-dot
# spelling, because a document written by hand carries both.
_BN_RANGE_RE = re.compile(r"(--bn-[a-z0-9-]+)\s*(?:…|\.\.\.)\s*(--bn-[a-z0-9-]+)")
# A bare suffix continuing the name before it: `--bn-r-xs 4 · -sm 6`. Anchored on the separator
# so a hyphen inside a sentence — "9:16 frame" or "light-on-dark" — is not read as a token.
_BN_SUFFIX_RE = re.compile(r"[·/]\s*-([a-z0-9]+(?:-[a-z0-9]+)*)\b")
# `name #hex` pairs on a `·`-separated line, where the name may be a suffix of the one before.
_BN_PAIR_RE = re.compile(r"(--bn-[a-z0-9-]+|-[a-z0-9-]+)\s+(#[0-9A-Fa-f]{3,6})\b")
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,6}\b")

# The one definition, shared with strip_css_comments() in the `raw color` section below.
# It was declared twice, identically, once per section — harmless only for as long as the two
# stayed identical, and the second binding silently won for BOTH call sites, so an edit to
# this one would have been discarded without a diff to show for it. Two checks reading the
# same CSS must not be able to disagree about what a comment is.
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_CSS_PROPERTY_RE = re.compile(r"--([A-Za-z0-9_-]+)\s*:\s*([^;]+);")
_SHORTHAND_RE = re.compile(r"#[0-9a-f]{3}$")


class Token(NamedTuple):
    kind: str
    text: str  # as its own file writes it, so a finding can quote both spellings
    value: str  # normalised, and the only thing ever compared


def token_value(kind: str, text: str) -> str:
    """One normaliser, run over both sides.

    Deliberately not two. A doc-side and a css-side normaliser are two decisions about what
    counts as the same value, and the failure mode of their disagreeing is a permanent
    finding nobody can fix — or worse, a permanent pass. Every difference this collapses is
    a difference CSS itself does not see:

      color     `#FFF` and `#ffffff` are one color. A check that called them a
                 disagreement would be reporting a spelling, and would be worked around by
                 respelling the doc, which is D16's forbidden direction.
      typeface   the stylesheet names the locked face plus a generic fallback. The interview
                 chose a face; `sans-serif` behind it is a rendering nicety nobody locked.
                 Family names are ASCII case-insensitive to CSS, so case is folded too.
      length     whitespace only. `4px` and `4 px` are not the same value to CSS and are not
                 collapsed here.
    """
    if kind == COLOR:
        text = " ".join(text.split()).lower()
        return "#" + "".join(ch * 2 for ch in text[1:]) if _SHORTHAND_RE.match(text) else text
    if kind == TYPEFACE:
        return " ".join(text.split(",")[0].strip().strip("'\"").split()).lower()
    return " ".join(text.split()).lower()


def fenced_block(text: str, heading: str) -> Optional[str]:
    """The first fenced block under a `## ` HEADING (a regex, anchored after the hashes), or None.

    Split out of `design_token_block` when `breakpoints` needed the same reader for its own
    register. The scoping argument below is that row's and still holds for it; the mechanism is
    general, and a second caller is the reason a heading is a parameter rather than a literal.
    """
    collecting = False
    in_section = False
    block: List[str] = []
    for line in text.splitlines():
        if not collecting and line.startswith("## "):
            in_section = bool(re.match(r"^##\s+" + heading, line))
            continue
        if in_section and line.lstrip().startswith("```"):
            if collecting:
                return "\n".join(block)
            collecting = True
            continue
        if collecting:
            block.append(line)
    return None


def design_token_block(text: str) -> Optional[str]:
    """The fenced block under the `## Tokens` heading, or None.

    Scoped to that one section on purpose. docs/DESIGN.md carries a second fenced block —
    step 6's three button states — which restates some of these hexes; it is a doc arguing
    with itself rather than with the code, a different question with a different answer, and
    folding it in here would put two comparisons behind one row's name.

    An unterminated fence returns None, which the caller reports. Falling through to the
    next fence in the file would compare the button states against the stylesheet and find
    nothing wrong with either.
    """
    return fenced_block(text, r"Tokens\b")


class Claims(NamedTuple):
    """What the block locks, in the three shapes it writes them.

    `names` are stated outright. `alts` are the readings of a shorthand whose base is genuinely
    ambiguous — `-sm` after `--bn-r-xs` is `--bn-r-sm`, while `-lg` after `--bn-r` is
    `--bn-r-lg` — and a group is satisfied when ANY of its readings is declared. `prefixes`
    come from a range like `--bn-fs-2xs … --bn-fs-5xl`, which locks a family rather than a
    list, and covers every declared token beginning with it.
    """

    names: Set[str]
    alts: List[Set[str]]
    prefixes: Set[str]
    hexes: Dict[str, Tuple[Optional[str], Optional[str]]]

    def covers(self, name: str) -> bool:
        """Whether the block names this declared token, by any of the three routes."""
        if name in self.names or any(name in group for group in self.alts):
            return True
        return any(name.startswith(prefix + "-") or name == prefix for prefix in self.prefixes)


def design_token_claims(block: str) -> Claims:
    """What the block LOCKS: every token name it names, and the literal hexes it states.

    THE BLOCK IS PROSE LAID OUT AS A PALETTE, NOT A TABLE, and it is deliberately readable
    rather than parseable — `docs/DESIGN.md` says so where it describes the old reader, and
    respelling the palette to suit a script is D16's forbidden direction. So this reads what
    the block unambiguously states and nothing else:

      NAMES        every `--bn-…` identifier, plus two shorthands the block uses for families:
                   `--bn-r-xs 4 · -sm 6` continues the previous name, and `--bn-fs-2xs … --bn-fs-5xl`
                   names every token sharing that prefix.
      HEX VALUES   only where a name is followed by a hex literal. `ink 8%`, `accent 55%`,
                   `white .72` and `= ink in both themes` are alphas and aliases of another
                   token — the block says as much in the paragraphs under it — and there is no
                   second value to keep in step, so there is nothing here to compare.

    WHAT THAT MEANS THE ROW CAN AND CANNOT CATCH, stated rather than left to be discovered.
    It catches a token declared in the stylesheet that no interview ever chose, a token locked
    in the doc that nothing renders, and a hex that disagrees between the two files. It does
    NOT check a duration, a shadow, an easing curve, an alpha, or the value behind a
    `color-mix()` — those are named and checked for existence, and their values are not locked
    anywhere a script can read. `docs/debts/` carries that gap.
    """
    names: Set[str] = set()
    alts: List[Set[str]] = []
    prefixes: Set[str] = set()
    hexes: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    last_full: Optional[str] = None

    for line in block.splitlines():
        full = _BN_NAME_RE.findall(line)
        for name in full:
            names.add(name)

        # `--bn-fs-2xs … --bn-fs-5xl` names a family. The prefix is what the two ends share up
        # to the last hyphen, and every token under it is locked by the range.
        span = _BN_RANGE_RE.search(line)
        if span:
            names.update(_range_names(span.group(1), span.group(2)))
            if not _range_names(span.group(1), span.group(2)):
                prefixes.add(_family_prefix(span.group(1), span.group(2)))

        # `--bn-r-xs 4 · -sm 6 · --bn-r 8 · -lg 12` — a bare suffix continues the last full
        # name. WHICH name is genuinely ambiguous (`-sm` after `--bn-r-xs` means `--bn-r-sm`,
        # while `-lg` after `--bn-r` means `--bn-r-lg`), so both readings are recorded and the
        # comparison accepts either. Being generous here is the safe direction: it can only
        # fail to report a typo in the DOC, and never wave through a token in the stylesheet
        # that nobody chose, which is the finding that matters.
        for piece in _BN_SUFFIX_RE.findall(line):
            base = last_full if not full else full[-1]
            if base is None:
                continue
            reading = {base + "-" + piece}
            if "-" in base[len("--bn-"):]:
                reading.add(base.rsplit("-", 1)[0] + "-" + piece)
            alts.append(reading)
        if full:
            last_full = full[-1]

        # A hex claim, in the two shapes the block writes. `·` separates several name/value
        # pairs on one line (the stage palette); without it the leading name owns the row's
        # hexes, and a row naming two tokens with `/` gives them to the first — the second is
        # that color's tint, which the block's own paragraph says is an alpha.
        if "·" in line:
            for name, value in _BN_PAIR_RE.findall(line):
                if name.startswith("--bn-"):
                    hexes[name] = (value, None)
                elif last_full is not None:
                    hexes[last_full.rsplit("-", 1)[0] + name] = (value, None)
            continue
        found = _HEX_RE.findall(line)
        if full and found and line.lstrip().startswith("--bn-"):
            hexes[full[0]] = (found[0], found[1] if len(found) > 1 else None)

    return Claims(names, alts, prefixes, hexes)


def _range_names(low: str, high: str) -> Set[str]:
    """`--bn-1 … --bn-10` enumerated, or an empty set where the ends are not numbered.

    A NUMBERED RANGE IS A LIST AND A NAMED ONE IS A FAMILY, and treating the first as a prefix
    was wrong in the way that matters: the shared prefix of `--bn-1` and `--bn-10` is `--bn-1`,
    which covers `--bn-10` and nothing else, so the spacing scale locked one of its ten steps
    and the check passed on it. `--bn-fs-2xs … --bn-fs-5xl` genuinely is a family — the ends are
    words, the members are not enumerable from them — and stays a prefix.
    """
    ends = [re.match(r"^(--bn-[a-z0-9-]*?)(\d+)$", name) for name in (low, high)]
    if not all(ends) or ends[0].group(1) != ends[1].group(1):
        return set()
    stem = ends[0].group(1)
    first, last = int(ends[0].group(2)), int(ends[1].group(2))
    if last < first:
        return set()
    return {f"{stem}{n}" for n in range(first, last + 1)}


def _family_prefix(low: str, high: str) -> str:
    """The prefix two ends of a range share, as a name every member starts with."""
    shared = ""
    for a, b in zip(low, high):
        if a != b:
            break
        shared += a
    return shared.rstrip("-")


def css_token_scopes(text: str) -> Tuple[Dict[str, str], Dict[str, str], Set[str]]:
    """The light palette, the dark one, and every `--bn-` name declared anywhere.

    THE SCOPES ARE KEPT APART, AND THE OLD READER'S MERGING THEM WAS LOSSY RATHER THAN MERELY
    EMPTY. It folded every `:root` in the file into one dictionary, so `--bn-bg`'s dark value
    silently overwrote its light one and the check compared the doc's light column against a
    dark hex. Under a token system where every color has both, that is a check that cannot be
    right — the shape had to change before the parsing did.

    A `:root` inside an at-rule contributes NAMES ONLY. The phone/coarse-pointer query raises
    three control heights, which are a second value for a condition rather than a second theme;
    comparing them against the doc's light column would report a disagreement that is the
    stylesheet working. Comments are stripped first, for `css_root_tokens`' old reason: a token
    commented out during a refactor still reads as a declaration to a regex, and this check
    would then agree with the doc about a value the browser never paints.
    """
    body = _CSS_COMMENT_RE.sub(" ", text)

    conditional: List[Tuple[int, int]] = []
    for at in re.finditer(r"@[a-z-]+[^{;]*\{", body):
        conditional.append((at.start(), _block_end(body, at.end())))

    # SCOPED TO `--bn-`, AND THE EXCLUSION IS ARGUED IN `token_findings`. The legacy aliases at
    # the foot of the stylesheet are named in the prose under the block as a spent migration
    # seam that is to be deleted; a check that demanded they be locked would be fighting the
    # plan it is auditing.
    light: Dict[str, str] = {}
    dark: Dict[str, str] = {}
    every: Set[str] = set()
    for match in re.finditer(r":root\b[^{]*\{", body):
        end = _block_end(body, match.end())
        declared = [
            (name, value)
            for name, value in _CSS_PROPERTY_RE.findall(body[match.end():end])
            if name.startswith("bn-")
        ]
        for name, _value in declared:
            every.add("--" + name)
        if any(start <= match.start() < stop for start, stop in conditional):
            continue
        selector = body[match.start():match.end()]
        table = dark if "data-theme='dark'" in selector or 'data-theme="dark"' in selector else light
        for name, value in declared:
            table["--" + name] = value.strip()
    return light, dark, every


def _block_end(body: str, opened: int) -> int:
    """The index just past the `}` closing a block whose `{` has already been consumed."""
    depth = 1
    index = opened
    while index < len(body) and depth:
        if body[index] == "{":
            depth += 1
        elif body[index] == "}":
            depth -= 1
        index += 1
    return index


def token_findings(
    claims: Claims,
    light: Dict[str, str],
    dark: Dict[str, str],
    every: Set[str],
) -> List[Finding]:
    """Both directions, and every finding names both files and both values.

    Both directions because either half of a drift is the same defect seen from one side. A
    token in the doc and not the stylesheet is a decision the product never implemented; a
    token in the stylesheet and not the doc is a value the owner never chose, which is the more
    dangerous of the two — it renders perfectly and no interview ever saw it.

    SCOPED TO `--bn-` AND NOT TO EVERY CUSTOM PROPERTY. The legacy aliases at the foot of the
    stylesheet — `--ink`, `--s1`, `--radius` and the rest — are named in the prose under the
    block as a migration seam that is already spent and is to be deleted. Locking a name the
    document argues for deleting would make the check fight the plan it is auditing.
    """
    findings: List[Finding] = []

    for name in sorted(claims.names - every):
        findings.append(
            Finding(
                f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                f"{rel(DESIGN)} locks `{name}`, and {rel(TOKENS_CSS)} declares no such "
                f"property.\n"
                f"  Nothing renders it, so the locked value is a decision the product does "
                f"not carry.",
            )
        )

    for group in claims.alts:
        if group & every:
            continue
        findings.append(
            Finding(
                f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                f"{rel(DESIGN)} continues a name into {' or '.join(sorted(group))}, and "
                f"{rel(TOKENS_CSS)} declares neither.\n"
                f"  A shorthand that reads onto nothing is a token the block believes it "
                f"locked and does not.",
            )
        )

    for prefix in sorted(claims.prefixes):
        if any(name.startswith(prefix + "-") for name in every):
            continue
        findings.append(
            Finding(
                f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                f"{rel(DESIGN)} locks the family `{prefix}-…`, and {rel(TOKENS_CSS)} "
                f"declares nothing under it.\n"
                f"  A range that covers no token locks nothing at all.",
            )
        )

    for name in sorted(name for name in every if not claims.covers(name)):
        findings.append(
            Finding(
                f"{rel(TOKENS_CSS)} + {rel(DESIGN)}",
                f"`{name}: {light.get(name, dark.get(name, ''))}` is declared in "
                f"{rel(TOKENS_CSS)}, and the token block in {rel(DESIGN)} names no "
                f"`{name}`.\n"
                f"  Lock it there, or delete it here. A token the doc never chose is a value "
                f"with no argument behind it.",
            )
        )

    for name in sorted(claims.hexes):
        for rendered, locked, theme in (
            (light.get(name), claims.hexes[name][0], "light"),
            (dark.get(name), claims.hexes[name][1], "dark"),
        ):
            if locked is None or rendered is None or not rendered.startswith("#"):
                # A stylesheet value that is not a literal is an alpha or a mix of another
                # token, which the block states in words rather than as a second hex. There is
                # nothing to compare, and reporting it would be reporting the design.
                continue
            if token_value(COLOR, rendered) != token_value(COLOR, locked):
                findings.append(
                    Finding(
                        f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                        f"`{name}` disagrees in the {theme} theme.\n"
                        f"  {rel(DESIGN)}:      {locked}\n"
                        f"  {rel(TOKENS_CSS)}: {rendered}\n"
                        f"  The doc is the source — it records what the owner picked from "
                        f"rendered alternatives. Change the stylesheet, or take the value "
                        f"back through an interview and change both.",
                    )
                )
    return findings


def check_design_tokens(report: Report) -> None:
    """The locked palette in docs/DESIGN.md against the custom properties the app renders.

    docs/DESIGN.md's token block is the record of an interview: every value in it was chosen
    by the owner from rendered alternatives, and the paragraphs under it argue for the
    choices. app/src/tokens.css is what the browser actually paints. Nothing compared them
    until this row existed, and docs/debts/ recorded the gap with the reason it matters:
    a wrong hex renders perfectly, so the failure is silent by construction and the document
    is the one nobody re-reads.

    **Blocking, because a disagreement is provable.** Two files state the same value; either
    they match or they do not. There is no context this script is missing, which is D16's
    test for a mechanical finding rather than a printed question.

    **This is a check, not a generator, and the distinction is the whole of D18.** Nothing
    here writes. The temptation it is placed against is a build step that rewrites
    app/src/tokens.css from the block — which would run inside `make check`, make the two
    agree by construction, and turn every wrong hex into a confidently rendered one.
    Checking lets two things disagree in public.

    **What a green row means, exactly**: the values agree. It says nothing about whether the
    palette is any good — contrast is asserted in app/tests/fulfillment.spec.ts against
    rendered pixels, and taste is what the interview was for.
    """
    missing = [rel(path) for path in (DESIGN, TOKENS_CSS) if not exists(path)]
    if missing:
        report.add(
            "design tokens",
            MECHANICAL,
            [
                Finding(
                    " ".join(missing),
                    "does not exist, so nothing compares the locked palette against what "
                    "the app renders from.",
                )
            ],
        )
        return

    block = design_token_block(read(DESIGN))
    if block is None:
        report.add(
            "design tokens",
            MECHANICAL,
            [
                Finding(
                    rel(DESIGN),
                    "has no fenced block under its `## Tokens` heading, so there is no "
                    "locked palette to compare against.\n"
                    "  The block is the record of the interview that chose these values. "
                    "If it moved, this check has to move with it.",
                )
            ],
        )
        return

    claims = design_token_claims(block)
    light, dark, every = css_token_scopes(read(TOKENS_CSS))
    doc, css = claims.names, every
    if not doc or not css:
        # A side that parses to nothing must never report a clean row — same rule as a
        # malformed `source_suffixes` scanning nothing and saying so. This is the state
        # docs/debts/ calls this auditor's worst failure mode: a check gone quiet.
        report.add(
            "design tokens",
            MECHANICAL,
            [
                Finding(
                    f"{rel(DESIGN)} + {rel(TOKENS_CSS)}",
                    f"read {len(doc)} tokens from the block and {len(css)} from `:root`. "
                    f"A side that parses to nothing compares nothing.",
                )
            ],
        )
        return

    report.add(
        "design tokens",
        MECHANICAL,
        token_findings(claims, light, dark, every),
        f"{len(every)} declared tokens, every one named by the block; "
        f"{len(claims.hexes)} hexes compared across both themes",
        scanned=len(every),
    )


# ------------------------------------------------------------------ naming checks by name


# A check named by position. D17 already ruled against it for the repo-map check — "named
# rather than numbered, because a positional index re-drifts every time a check is added,
# and this one already had" — and the rest of the repo had not caught up: the section
# headers in this file ran 1 to 10 and then jumped, so two numbers in circulation pointed
# at nothing at all.
_POSITIONAL_RE = re.compile(r"\bchecks?\s+\d{1,2}\b", re.IGNORECASE)


APP_STYLES = ROOT / "app" / "src"

_RAW_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def strip_css_comments(text: str) -> str:
    """A comment replaced by as many newlines as it spanned, so line numbers survive.

    `_CSS_COMMENT_RE` is the one declared in the design-tokens section above and is
    deliberately not redeclared here — see the note on it. The newline-preserving
    substitution is this function's business; what counts as a comment is not.
    """
    return _CSS_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def check_raw_color(report: Report) -> None:
    """A color painted as a literal instead of read from a token.

    The house rule is stated everywhere and was enforced nowhere: stylesheets use
    `var(--token)` and never a raw hex, because the locked palette is only locked if the
    palette is the only place colors come from. `design tokens` above proves
    `app/src/tokens.css` agrees with `docs/DESIGN.md` — it cannot see a stylesheet that
    bypasses both.

    **Found by grep, not by argument.** `app/src/PullConfirm.css` painted `#ffffff` twice,
    in the component the token block is the reference for, and survived a design review, a
    six-lens adversarial review and two integration passes. It was reported three times as a
    style note and refuted twice on the reasonable grounds that there was no token to use
    instead — `--surface` means "raised panel", and saying that where you mean "text on the
    loud button" conflates two things the palette keeps apart. The refutations were right and
    the conclusion was still wrong: the answer was a missing token, not a permitted literal.
    `--on-accent` now exists and names a value `docs/DESIGN.md`'s step 6 block had specified
    from the beginning.

    **Blocking, because there is nothing to judge.** A hex outside `tokens.css` either is or
    is not there, which is D16's test. Comments are stripped first — a paragraph explaining
    why `#000000` is the wrong ground is prose about a color, not a color.

    **Scope is `app/src/*.css` only.** A static drawing sheet is full of hex on purpose:
    it is a drawing of the spec and imports nothing, so nothing audits the values inside it.
    """
    if not exists(APP_STYLES):
        # A ROW, NOT A RETURN. A silent return deletes the row from the render entirely,
        # and nothing in this file notices a row that is absent rather than green — the
        # same blind spot `check dispatch`'s own comment records about itself. With a
        # subject count of 0 the render says `none` and `subject counts` fails the commit.
        report.add("raw color", MECHANICAL, [],
                   f"{rel(APP_STYLES)} is not there, so no stylesheet was read", scanned=0)
        return

    findings: List[Finding] = []
    sheets = 0
    for path in sorted(APP_STYLES.glob("*.css")):
        if path == TOKENS_CSS:
            continue
        sheets += 1
        for number, line in enumerate(strip_css_comments(read(path)).splitlines(), start=1):
            for literal in _RAW_COLOR_RE.findall(line):
                findings.append(
                    Finding(
                        f"{rel(path)}:{number}",
                        f"paints `{literal}` directly. Read it from a token in "
                        f"app/src/tokens.css — and if no token means what you mean, the "
                        f"missing token is the finding.",
                    )
                )

    report.add("raw color", MECHANICAL, findings,
               f"{len(findings)} literals outside tokens.css" if findings
               else f"every color in {sheets} sheets comes from a token",
               scanned=sheets)


# ------------------------------------------------------------------------- raw motion
#
# MOTION IS TOKENS (CLAUDE.md), AND `docs/specs/motion.md` IS THE ROLE TABLE. A duration or an
# easing written as a literal in a stylesheet is a surface that no retune of `app/src/tokens.css`
# will ever reach, which is how 7 different stagger steps and 4 "live" loops grew. This row reads
# every `transition` and `animation` declaration (and their -duration, -delay and
# -timing-function longhands) outside tokens.css and refuses a time literal (`180ms`, `.4s`), a
# `cubic-bezier(`, `steps(` or an easing keyword (`ease`, `ease-in`, `ease-out`, `ease-in-out`,
# `linear`). WHAT IS NOT READ, ON PURPOSE: a `var(--x, <fallback>)` span, because the number
# there belongs to a custom property a script sets per use (a drain's length, a settle window);
# a zero time (`0s`, `0ms`), which is no duration at all; and a delay written as
# `calc(var(--bn-stagger) * n)`, which reads the token. A `var(--x, 300ms)` FALLBACK IS ALLOWED
# ON PURPOSE: the number belongs to a property a script sets, and the fallback is only its
# default. Units and keywords are read case-insensitively, and a `-webkit-` or `-moz-` prefix is
# read like the plain property. TSX is read for: the camelCase props (`transition`,
# `animation` and their Delay, Duration and TimingFunction forms) given a string or a bare number
# that carries a literal, `el.style.transition = '...'`, and `el.animate(...)` with a literal
# duration or delay. A justified exception lives in
# `scripts/motion-literal-allow.json`: each entry names a file and the literal, carries its
# reason, and is itself a finding once it matches nothing. The list only shrinks.

MOTION_ALLOW = ROOT / "scripts" / "motion-literal-allow.json"
_MOTION_DECL_RE = re.compile(r"(?:^|[{;\s])((?:-webkit-|-moz-)?(?:transition|animation)(?:-[a-z-]+)?)\s*:\s*([^;{}]+)", re.I)
_MOTION_SKIP_PROPS = {
    "transition-property", "transition-behavior", "animation-name", "animation-iteration-count",
    "animation-fill-mode", "animation-direction", "animation-play-state", "animation-timeline",
    "animation-range",
}
_MOTION_TIME_RE = re.compile(r"(?<![\w.-])(\d*\.?\d+)(ms|s)\b", re.I)
_MOTION_EASE_RE = re.compile(
    r"cubic-bezier\(|steps\(|(?<![\w-])(?:ease|ease-in|ease-out|ease-in-out|linear|step-start|step-end)(?![\w-])",
    re.I,
)
_STR = r"(`[^`]*`|'[^']*'|\"[^\"]*\")"
_MOTION_TSX_RES = (
    # a style prop given a string: `transition: 'opacity 200ms ease'`, `animationDelay: `${i * 30}ms``
    re.compile(r"\b(?:animation|transition)(?:Delay|Duration|TimingFunction)?\s*[:=]\s*" + _STR),
    # `el.style.transition = '...'`
    re.compile(r"\.style\.(?:animation|transition)(?:Delay|Duration|TimingFunction)?\s*=\s*" + _STR),
    # a bare number, which a style object reads as milliseconds
    re.compile(r"\b(?:animation|transition)(?:Delay|Duration)\s*[:=]\s*(\d[\d.]*)\b"),
    # `el.animate(frames, { duration: 300 })` and `el.animate(frames, 300)`
    re.compile(r"\.animate\([^;]{0,400}?\b(?:duration|delay)\s*:\s*(\d[\d.]*|`[^`]*\d[^`]*`)"),
    re.compile(r"\.animate\([^;{}]{0,400}?,\s*(\d[\d.]*)\s*\)"),
)


def _without_var(value: str) -> str:
    """`value` with every `var(...)` span, fallback included, removed."""
    out: List[str] = []
    depth = 0
    i = 0
    while i < len(value):
        if depth == 0 and value.startswith("var(", i):
            depth = 1
            i += 4
            continue
        if depth:
            depth += {"(": 1, ")": -1}.get(value[i], 0)
        else:
            out.append(value[i])
        i += 1
    return "".join(out)


def raw_motion_literals(text: str, tsx: bool = False) -> List[Tuple[int, str]]:
    """Every raw duration or easing in `text`, as (line, literal). One definition, read by the
    row and by its self-test."""
    found: List[Tuple[int, str]] = []
    if tsx:
        for pattern in _MOTION_TSX_RES:
            for m in pattern.finditer(text):
                body = re.sub(r"\$\{\s*[\w.]+\s*\}", "", m.group(1))
                body = _without_var(body)
                for lit in re.findall(r"\d+(?:\.\d+)?|cubic-bezier|steps|ease\w*|linear", body, re.I):
                    if lit != "0":
                        found.append((text[: m.start()].count("\n") + 1, m.group(1)))
                        break
        return found
    css = strip_css_comments(text)
    for m in _MOTION_DECL_RE.finditer(css):
        if m.group(1).lower().replace("-webkit-", "").replace("-moz-", "") in _MOTION_SKIP_PROPS:
            continue
        value = _without_var(m.group(2))
        hits = [t.group(0) for t in _MOTION_TIME_RE.finditer(value) if float(t.group(1)) != 0]
        hits += [e.group(0) for e in _MOTION_EASE_RE.finditer(value)]
        line = css[: m.start(1)].count("\n") + 1
        found.extend((line, hit) for hit in hits)
    return found


def check_raw_motion(report: Report) -> None:
    """A duration or an easing written as a literal where a token should be read."""
    import json

    if not exists(APP_STYLES):
        report.add("raw motion", MECHANICAL, [],
                   f"{rel(APP_STYLES)} is not there, so no stylesheet was read", scanned=0)
        return
    try:
        allow = json.loads(read(MOTION_ALLOW))["entries"] if exists(MOTION_ALLOW) else []
    except (ValueError, KeyError):
        allow = []
    used: Set[int] = set()
    findings: List[Finding] = []
    files = 0
    sources = [(p, False) for p in sorted(APP_STYLES.glob("*.css")) if p != TOKENS_CSS]
    sources += [(p, True) for p in sorted(APP_STYLES.rglob("*.ts*")) if "markPalettes" not in p.name]
    for path, tsx in sources:
        files += 1
        for line, literal in raw_motion_literals(read(path), tsx):
            index = next((i for i, e in enumerate(allow)
                          if e.get("file") == rel(path) and e.get("value") == literal), None)
            if index is not None:
                used.add(index)
                continue
            findings.append(Finding(
                f"{rel(path)}:{line}",
                f"writes `{literal}` as a raw duration or easing. Name a role token from "
                f"app/src/tokens.css (`--bn-t-*`, `--bn-ease-*`, `--bn-stagger`) — and if no token "
                f"means what you mean, the missing token is the finding (docs/specs/motion.md)."))
    for i, entry in enumerate(allow):
        if i not in used:
            findings.append(Finding(rel(MOTION_ALLOW), f"entry {entry!r} matches nothing, so it is stale. Delete it."))
    report.add("raw motion", MECHANICAL, findings,
               f"{len(findings)} raw durations or easings outside tokens.css" if findings
               else f"every duration and easing in {files} files comes from a token ({len(allow)} allow-listed)",
               scanned=files)


# --------------------------------------------------------------- the breakpoint vocabulary
#
# MEASURED BEFORE IT WAS WRITTEN, 2026-09-07: 124 `@media` and 16 `@container` blocks across
# 31 stylesheets under `app/src`, and nothing had ever read them together. What the reading
# found was NOT a rendering defect — the sheets that disagreed draw different screens, so no
# person ever saw two layouts at once. It was a vocabulary nobody could read:
#
#   FOUR EDGES WERE SPELLED TWICE. `max-width: 559px` and `max-width: 560px` are one intention
#   a pixel apart, and so were 639/640, 899/900 and 1099/1100. Nothing here reflows inside a
#   one-pixel band, so the sheet that lost the coin toss folded a pixel later than the one
#   beside it, forever.
#
#   THREE INTEGERS WERE USED ON BOTH SIDES — 560, 640 and 1100 were each a `min-width`
#   somewhere and a `max-width` elsewhere, so at exactly those widths two blocks written to
#   exclude each other both applied.
#
#   AND THE LADDER'S TOP RULE HAD NO ELEMENT. `@media (max-width: 1599px)` — the single widest
#   breakpoint in the product, and the only thing above 1500 — hid `.pricing-ready-fine`, a
#   class no component in `app/src` renders. It was deleted with the rest of that class.
#
# THE REGISTER IS `docs/DESIGN.md`, NOT THIS FILE, and that is the choice `design tokens`
# makes. A ladder step is a design decision with an argument under it; a constant here would be
# a design decision in a script, which is where they stop being argued.
#
# NO COUNTS ARE PUBLISHED IN THE REGISTER, deliberately. `docs/DESIGN.md` carried "54 media
# blocks ... and six" until this row landed, and the six was seven — `scripts/checks.py`'s own
# rule arriving on schedule. The counts are in this row's summary, taken at run time.

# The sheets that ARE the shell. A width in one of them is asking about the window because the
# window is its subject: `App.css` draws the sidebar, the rail, the phone bar and the tab bar;
# `base.css` and `kit.css` load on every route; `tokens.css` raises the control heights by the
# POINTER and by the width. Everything else under `app/src` is a screen.
SHELL_SHEETS = frozenset({"App.css", "base.css", "kit.css", "tokens.css"})

# At and above this the shell has a sidebar to subtract, and how much depends on `data-rail`.
# Below it `App.css` rails unconditionally between 768 and 1023, so a viewport question and a
# column question differ by a constant and either one is answerable.
COLUMN_FLOOR = 1024

_AT_RE = re.compile(r"@(media|container)([^{]*)\{")
_WIDTH_RE = re.compile(r"\((max|min)-width:\s*(\d+)px\)")
_CONTAINER_AT_RE = re.compile(r"@container\s+([A-Za-z][\w-]*)\s*\(")
_CONTAINER_NAME_RE = re.compile(r"container-name:\s*([A-Za-z][\w-]*)")


class Widths(NamedTuple):
    """Every width condition in one stylesheet, and the container names it uses or declares."""

    media: List[Tuple[str, int, int]]      # (side, value, line)
    container: List[Tuple[str, int, int]]
    blocks: int
    queried: Set[str]
    declared: Set[str]


def read_widths(text: str) -> Widths:
    """The widths and container names in one stylesheet's TEXT. Pure, so `--self-test` can drive
    it with no repository — the filesystem is not where this can be wrong.

    COMMENTS COME OFF FIRST, and here that matters more than anywhere else this file reads CSS:
    these stylesheets argue in prose ABOUT their breakpoints. `App.css` writes "768-1023px" in
    three comments that are not rules. `strip_css_comments` replaces a comment with as many
    newlines as it spanned, so a `file:line` in a finding still points at the rule.
    """
    body = strip_css_comments(text)
    media: List[Tuple[str, int, int]] = []
    container: List[Tuple[str, int, int]] = []
    blocks = 0
    for at in _AT_RE.finditer(body):
        blocks += 1
        line = body[: at.start()].count("\n") + 1
        into = media if at.group(1) == "media" else container
        for side, value in _WIDTH_RE.findall(at.group(2)):
            into.append((side, int(value), line))
    queried = set(_CONTAINER_AT_RE.findall(body))
    declared = set(_CONTAINER_NAME_RE.findall(body))
    return Widths(media, container, blocks, queried, declared)


class Ladder(NamedTuple):
    steps: Dict[int, str]
    refinements: Dict[int, str]
    container: Set[int]
    blind: Dict[str, str]


def read_ladder(block: str) -> Ladder:
    """The four sections of the register. Pure, for `read_widths`' reason.

    THE FENCE IS PROSE LAID OUT AS A TABLE, exactly as the token block is, and this reads what
    it unambiguously states and nothing else: an indented row whose first field is a bare
    integer (LADDER, REFINEMENTS) or a `*.css` filename (COLUMN-BLIND), and whose reason is two
    or more spaces away. A section heading starts at column zero, which is how the sections are
    told apart — so a section RENAMED in the document does not silently become a fifth one and
    take its rows out of the comparison.

    CONTAINER rows carry a container name before the width and only their VALUES are collected:
    a column's width is a measurement against one pane, not a step on a shared ladder, so it
    gets no step arithmetic. Naming it is the whole requirement.
    """
    steps: Dict[int, str] = {}
    refinements: Dict[int, str] = {}
    container: Set[int] = set()
    blind: Dict[str, str] = {}
    into: Optional[str] = None
    for line in block.splitlines():
        head = re.match(r"^([A-Z][A-Z -]+?)\s{2,}", line)
        if head is not None:
            into = head.group(1).strip()
            continue
        row = re.match(r"^\s+(?:\(?[a-z][\w-]*\)?\s+)?(\d{3,4})\s{2,}(\S.*)$", line)
        if row is not None and into in ("LADDER", "REFINEMENTS", "CONTAINER"):
            value, why = int(row.group(1)), row.group(2).strip()
            if into == "LADDER":
                steps[value] = why
            elif into == "REFINEMENTS":
                refinements[value] = why
            else:
                container.add(value)
            continue
        # a CONTAINER line may carry several widths on one row (`520, 640`)
        if into == "CONTAINER":
            many = re.match(r"^\s+\(?[a-z][\w-]*\)?\s+((?:\d{3,4},\s*)+\d{3,4})\s{2,}", line)
            if many is not None:
                container.update(int(v) for v in re.findall(r"\d{3,4}", many.group(1)))
                continue
        row = re.match(r"^\s+([\w.-]+\.css)\s{2,}(\S.*)$", line)
        if row is not None and into == "COLUMN-BLIND":
            blind[row.group(1)] = row.group(2).strip()
    return Ladder(steps, refinements, container, blind)


def breakpoint_subject() -> Tuple[Optional[Tuple[Ladder, Dict[Path, Widths]]], List[Finding]]:
    """The register and the stylesheets, or the findings saying which could not be read.

    RETURNS its findings rather than reporting them, because `defined_checks` marks any
    module-level function that calls `report.add` as a check — on purpose, so a check cannot
    hide behind a helper. This is a helper genuinely shared by two rows, so it hands the
    findings back and each row files them under its own name.

    An unreadable subject is a FINDING and never a skip — the state docs/debts/ calls this
    auditor's worst failure mode, a check gone quiet.
    """
    if not exists(APP_STYLES) or not exists(DESIGN):
        missing = [rel(p) for p in (APP_STYLES, DESIGN) if not exists(p)]
        return None, [Finding(" ".join(missing),
            "does not exist, so no stylesheet's widths are compared against the ladder that "
            "governs them.")]
    fence = fenced_block(read(DESIGN), r"Layout, density, and the widths")
    if fence is None:
        return None, [Finding(rel(DESIGN),
            "has no fenced block under the layout heading, so there is no register to compare "
            "against.\n"
            "  That block is where a width stops being a number somebody typed. If it moved, "
            "this row's reader has to move with it.")]
    ladder = read_ladder(fence)
    sheets = {p: read_widths(read(p)) for p in sorted(APP_STYLES.glob("*.css"))}
    if not (ladder.steps or ladder.refinements) or not sheets:
        return None, [Finding(f"{rel(DESIGN)} + {rel(APP_STYLES)}",
            f"read {len(ladder.steps)} ladder steps and {len(ladder.refinements)} refinements "
            f"from the register, and {len(sheets)} stylesheets. "
            f"A side that parses to nothing compares nothing.")]
    return (ladder, sheets), []


def check_breakpoints(report: Report) -> None:
    """Every `@media` width under `app/src`, against the ladder docs/DESIGN.md publishes.

    **Blocking, on `raw color`'s reasoning exactly.** A width is an integer in a stylesheet and
    the register is an integer in a document; either they agree or they do not, and there is no
    context this script is missing. That is D16's test for a mechanical finding rather than a
    printed question. The clause that WOULD have been a judgement — whether a rule is asking the
    viewport a question only the column can answer — is a separate ADVISORY row below, because
    answering it needs a reading of what the rule does.

    Four claims, and none of them is "this breakpoint is a good idea":

      1. ONE EDGE, ONE SPELLING. `max-width: N` and `max-width: N+1` may not both exist.
      2. ONE SIDE. No integer is both a `max-width` and a `min-width`.
      3. THE FORM. A `min-width` is a step the register names; a `max-width` is a step minus
         one. This is what makes 1 and 2 hold by construction rather than by luck.
      4. EVERY NAMED CONTAINER HAS A READER AND EVERY QUERY HAS A CONTAINER (D80, one register
         down): a `container-name` nothing queries is a declaration with no reader, and an
         `@container copies (...)` with no `copies` declared resolves against the nearest
         container instead — a rule that fires somewhere else and never says so.

    `@media` and `@container` are separate namespaces and 1-3 are asked of each on its own. A
    `pane` of 640px and a viewport of 640px are different quantities, so an integer used as a
    step in one and a measurement in the other is not a collision.

    **What a green row means, exactly**: the vocabulary agrees. It says nothing about whether a
    screen reflows WELL at any of these widths — `app/tests/wide.spec.ts` measures that above
    1280 and `app/tests/phone.spec.ts` below 768.
    """
    subject, unreadable = breakpoint_subject()
    if subject is None:
        report.add("breakpoints", MECHANICAL, unreadable)
        return
    ladder, sheets = subject
    named = dict(ladder.refinements)
    named.update(ladder.steps)
    findings: List[Finding] = []

    for kind in ("media", "container"):
        sides: Dict[Tuple[str, int], List[str]] = {}
        for path, found in sheets.items():
            for side, value, line in getattr(found, kind):
                sides.setdefault((side, value), []).append(f"{rel(path)}:{line}")

        for side, value in sorted(sides):
            if (side, value + 1) in sides:
                findings.append(Finding(", ".join(sides[(side, value)] + sides[(side, value + 1)]), (
                    f"spells one edge two ways in `@{kind}`: `{side}-width: {value}px` and "
                    f"`{side}-width: {value + 1}px`.\n"
                    f"  Nothing in this product reflows inside a one-pixel band, so these are one "
                    f"intention typed twice — and the sheet that loses folds a pixel later than "
                    f"the one beside it, forever, invisibly.\n"
                    f"  Move both onto whichever of the two the register names.")))

        for value in sorted({v for _, v in sides}):
            if ("min", value) in sides and ("max", value) in sides:
                findings.append(Finding(", ".join(sides[("min", value)] + sides[("max", value)][:3]), (
                    f"uses {value}px in `@{kind}` as BOTH a floor and a ceiling, so at exactly "
                    f"{value}px two blocks written to exclude each other both apply.\n"
                    f"  A `max-width` is the step MINUS ONE. Nothing else stops this recurring.")))

        if kind == "container":
            for (side, value), where in sorted(sides.items()):
                if value not in ladder.container:
                    findings.append(Finding(where[0], (
                        f"queries a container at `{side}-width: {value}px`, which the register's "
                        f"CONTAINER section does not name.\n"
                        f"  A column's width is a measurement against one pane, so it needs no "
                        f"step — but it does need naming, with its container and what it is for. "
                        f"A width nobody argued for is a width nobody can move.")))
            continue

        for (side, value), where in sorted(sides.items()):
            step = value if side == "min" else value + 1
            if step in named:
                continue
            findings.append(Finding(where[0], (
                f"opens a regime at `{side}-width: {value}px`, and the register names no "
                f"{step}px step."
                + (f"\n  It names {value}px. A `max-width` is the step MINUS ONE — this is the "
                   f"off-by-one claims 1 and 2 exist to stop, arriving one sheet at a time."
                   if side == "max" and value in named else
                   "\n  Add it under LADDER if any sheet may use it, or under REFINEMENTS with "
                   "the sheet that owns it and its reason."))))

    queried = {n for f in sheets.values() for n in f.queried}
    declared = {n for f in sheets.values() for n in f.declared}
    for name in sorted(queried - declared):
        where = next(rel(p) for p, f in sheets.items() if name in f.queried)
        findings.append(Finding(where, (
            f"queries `@container {name}` and no sheet under app/src declares "
            f"`container-name: {name}`. The query resolves against the nearest container "
            f"instead, or against none — and a rule that fires somewhere else never says so.")))
    for name in sorted(declared - queried):
        where = next(rel(p) for p, f in sheets.items() if name in f.declared)
        findings.append(Finding(where, (
            f"declares `container-name: {name}` and nothing queries it. Delete it or use it "
            f"(D80) — and note `container-type` also makes the element a containing block for "
            f"its `position: fixed` descendants, so an unused one is not free.")))

    blocks = sum(f.blocks for f in sheets.values())
    widths = {v for f in sheets.values() for _, v, _ in f.media}
    report.add("breakpoints", MECHANICAL, findings, (
        f"{blocks} blocks over {len(widths)} media widths in "
        f"{sum(1 for f in sheets.values() if f.blocks)} sheets, all on the ladder; "
        f"{len(declared)} named containers, each with a reader"), scanned=blocks)


def check_breakpoint_columns(report: Report) -> None:
    """A screen sheet asking the VIEWPORT a question only its COLUMN can answer.

    ADVISORY, and the severity is the finding's shape rather than its confidence. Whether a
    `min-width` is asking the wrong thing depends on what the rule DOES: a width that gates a
    `100dvh` stage, a `position: fixed` sheet or an input modality is a viewport question and is
    right as it stands. This row can see the width and not the intent, so it prints the question
    and lets the commit through — D16's line, and the same call `coupling` makes.

    THE MEASUREMENT UNDER IT. Every screen but the Fulfiller's draws inside `.bn-shell-main`,
    which is the viewport minus `--bn-sidebar-w` (236px) or minus `--bn-rail-w` (64px) when the
    rail is collapsed. Those differ by 172px — wider than the gap between two ladder steps — so
    a `min-width: 1024px` fires in a 788px column and in a 960px one and cannot tell them apart.
    Of the five blocks this row names today, `ReviewQueue.css` is the only place in the product
    that ever compensated, and it does it by writing every declaration twice.

    A sheet with a real reason is named under COLUMN-BLIND in the register and drops out here.
    """
    subject, unreadable = breakpoint_subject()
    if subject is None:
        report.add("breakpoint columns", ADVISORY, unreadable)
        return
    ladder, sheets = subject
    findings: List[Finding] = []
    for path, found in sheets.items():
        if path.name in SHELL_SHEETS or path.name in ladder.blind:
            continue
        for side, value, line in found.media:
            if side != "min" or value < COLUMN_FLOOR:
                continue
            findings.append(Finding(f"{rel(path)}:{line}", (
                f"opens a regime at `min-width: {value}px` on the VIEWPORT.\n"
                f"  This sheet draws inside `.bn-shell-main` — the viewport minus 236px, or "
                f"minus 64px when the rail is collapsed. So this fires in a {value - 236}px "
                f"column and in a {value - 64}px one and cannot tell them apart.\n"
                f"  Discharge: ask the column instead — a cap (`--bn-page-max`) or a "
                f"`container-type: inline-size` on an ancestor inside this screen, the way "
                f"`Pricing.css` and `BoxBrowse.css` already do — or, if the rule is genuinely "
                f"about the window (a `100dvh` stage, a fixed sheet, an input modality), name "
                f"this sheet under COLUMN-BLIND in docs/DESIGN.md with that reason.")))
    for name, why in sorted(ladder.blind.items()):
        path = APP_STYLES / name
        if not exists(path):
            findings.append(Finding(rel(DESIGN), (
                f"COLUMN-BLIND names `{name}`, which is not a stylesheet under app/src. "
                f"Remove the line — a stale exemption reads as coverage.")))
        elif not any(s == "min" and v >= COLUMN_FLOOR for s, v, _ in sheets[path].media):
            findings.append(Finding(rel(DESIGN), (
                f"COLUMN-BLIND excuses `{name}` from asking its column, and that sheet no "
                f"longer opens a regime at or above {COLUMN_FLOOR}px. Drop the line: the reason "
                f"it carries — {why} — is an argument nobody is making.")))
    report.add("breakpoint columns", ADVISORY, findings,
               f"{len(sheets)} sheets, {len(ladder.blind)} named column-blind",
               scanned=len(sheets))


JS_BREAKPOINTS_SCRIPT = ROOT / "scripts" / "js-breakpoints.py"
BROWSER_SCOPE_SCRIPT_FOR_PAIRING = ROOT / "scripts" / "browser-scope.py"


def check_js_breakpoints(report: Report) -> None:
    """A JS media query's viewport width, against what THE STYLESHEETS THAT FILE ITSELF
    IMPORTS declare (D123): a responsive breakpoint belongs in the stylesheet, and where a
    screen genuinely needs one in JavaScript its value must match one the stylesheets it is
    subject to already declare, so the two can never quietly disagree.

    PAIRED BY THE IMPORT GRAPH, NEVER GLOBALLY. A component declares which stylesheets it is
    subject to by importing them, and that is a primitive this repo already built for a
    different question — `scripts/browser-scope.py`'s `file_imports`, which D141's classifier
    needs to know whether one file reaches another. An earlier version of this row compared a
    JS breakpoint against every stylesheet under `app/src`, and it went GREEN on the exact
    defect it was written for: `app/src/Orders.tsx` carried `min-width: 1024px` with no
    stylesheet it imports declaring it, while `RunPanel.css` — a file `Orders.tsx` never
    imports — happened to declare 1024 for a reason of its own, and the global comparison
    could not tell the two apart. A guard that stays green on its own motivating defect is
    spent; this is the fix, not a second layer beside the old one.

    MECHANICAL: whether a JS breakpoint's value has a counterpart in the stylesheets ITS OWN
    FILE imports is not a matter of intent the way `breakpoint columns`' viewport-vs-column
    question is — it either does or it does not.

    THE EXTRACTION, THE PAIRING AND THE COMPARISON LIVE IN `scripts/js-breakpoints.py`,
    imported rather than reimplemented — the same reason its own `subject_css_widths` reuses
    `browser-scope.py`'s `file_imports` rather than writing a second import reader. This row
    does the filesystem half itself instead of calling the sibling's own `scan()`, because
    `read()` honors staged-commit mode for a stylesheet's CONTENT (the import graph itself,
    borrowed from `browser-scope.py`, still reads the worktree — the same limit `browser
    scope` and `spec map` above already accept).

    A FILE THAT IMPORTS NO STYLESHEET AT ALL, and still carries a JS viewport query, is
    UNPAIRED — its own finding, distinct from a mismatch, because there is no CSS to compare
    against and a silent pass would be exactly the failure this row exists to end.

    CONTAINER QUERIES CARRY NO JS SIDE and never enter the CSS a file is paired against; a
    `@container` width is `breakpoint columns`' and `breakpoints`' question, not this one's.

    FAILS OPEN: a missing sibling script (this row's own, or the `browser-scope.py` it
    borrows the import reader from), or a subject that reads zero JS breakpoints, is a
    finding and never a silent pass — the same posture `breakpoint_subject` above takes for
    its own two rows.
    """
    if not exists(APP_STYLES):
        report.add("js breakpoints", MECHANICAL, [Finding(
            rel(APP_STYLES),
            "does not exist, so no JS breakpoint can be compared against anything.")])
        return
    module = _sibling("js-breakpoints.py")
    if module is None:
        report.add("js breakpoints", MECHANICAL, [Finding(
            rel(JS_BREAKPOINTS_SCRIPT),
            "does not exist or does not import, so no JS breakpoint can be read at all.")])
        return
    scope_module = _sibling("browser-scope.py")
    if scope_module is None:
        report.add("js breakpoints", MECHANICAL, [Finding(
            rel(BROWSER_SCOPE_SCRIPT_FOR_PAIRING),
            "does not exist or does not import, and `js-breakpoints.py`'s pairing borrows "
            "its `file_imports` — with no import reader, no JS breakpoint can be paired to "
            "the stylesheets it is subject to.")])
        return

    js_by_file: Dict[str, List[Tuple[str, int, int]]] = {}
    for path in module.js_files(APP_STYLES):
        widths = module.read_js_widths(read(path))
        if widths:
            js_by_file[rel(path)] = widths

    if not js_by_file:
        report.add("js breakpoints", MECHANICAL, [Finding(
            rel(APP_STYLES),
            "read 0 JS breakpoints under app/src. A side that parses to nothing compares "
            "nothing.")])
        return

    subject_by_file: Dict[str, Optional[List[Tuple[str, int, int]]]] = {
        path: module.subject_css_widths(path, scope_module.file_imports, read_fn=read)
        for path in js_by_file
    }
    verdict = module.compare(js_by_file, subject_by_file)

    findings: List[Finding] = [
        Finding(f"{m.path}:{m.line}", (
            f"opens a whole layout regime in JavaScript at `{m.side}-width: {m.value}px`, "
            f"and no `@media` block in any stylesheet THIS FILE ITSELF IMPORTS declares that "
            f"breakpoint.\n"
            f"  D123: a responsive breakpoint belongs in the stylesheet. A component "
            f"declares which stylesheets it answers to by importing them — the way "
            f"`app/src/BoxBrowse.tsx:704` matches `app/src/BoxBrowse.css`'s own "
            f"`max-width: 767px`, which it imports directly — so the screen's script and "
            f"the CSS it actually loads can never quietly disagree. A DIFFERENT stylesheet "
            f"elsewhere declaring this value does not count; this file does not import it."))
        for m in verdict.mismatches
    ] + [
        Finding(f"{path}:{line}", (
            f"runs a JavaScript viewport query at `{side}-width: {value}px` and imports no "
            f"stylesheet at all — `.css` or otherwise — so nothing can vouch for the value.\n"
            f"  Import the stylesheet this breakpoint actually answers to, or argue in "
            f"`scripts/js-breakpoints.py`'s own module docstring why this file is exempt. A "
            f"file with no CSS to compare against is not a pass."))
        for path in verdict.unpaired
        for side, value, line in js_by_file[path]
    ]
    total_js = sum(len(v) for v in js_by_file.values())
    report.add("js breakpoints", MECHANICAL, findings,
               f"{total_js} JS breakpoints in {len(js_by_file)} files, each paired to its "
               f"own imports; {len(verdict.unpaired)} unpaired",
               scanned=total_js)
