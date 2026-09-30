"""Reason codes, motion, presets, transport, hints and the export request."""

from __future__ import annotations

import ast
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
    _walk,
    exists,
    literals_from_module,
    read,
    rel,
)
from .games import (
    EXPORT_MODULE,
    EXPORT_STANDING,
    HINT_REASON_NON_TRANSPORT,
    HINT_REASON_ROOT,
    HINT_REASON_SCREEN,
    LIVE_QUERY_EXPECTED,
    TRANSPORT_OPENER,
    TRANSPORT_PROMISE_MODULE,
    _HINT_REASON_CODE_RE,
    _HINT_REASON_FN_RE,
    _TRANSPORT_HEADLINE_RE,
    _TRANSPORT_NUMBERS,
    _TRANSPORT_ROUTE_RE,
)

# ------------------------------------------------------------------- the reason codes

# The labels moved out of ReviewQueue.tsx on 2026-08-25, when #/inventory's card panel began
# saying whether the selected card has an open question. Extracted rather than copied — the
# vocabulary's own docstring is the argument, and this check is half of what makes it work.
REVIEW_QUEUE_TSX = ROOT / "app" / "src" / "reasons.ts"
REASON_MODULES = ("pipeline/variant.py", "pipeline/routing.py")

_REASON_LABELS_RE = re.compile(r"const\s+REASON_LABELS\b[^{]*\{(.*?)\n\}", re.DOTALL)
_LABEL_KEY_RE = re.compile(r"^\s{2,}([a-z][a-z0-9_]*)\s*:", re.MULTILINE)
_BACKTICKED_RE = re.compile(r"`([a-z][a-z0-9_]*)`")


def self_named_strings(path: Path) -> Set[str]:
    """Module-level `NAME = "name"` constants — the shape every reason string is written in.

    A superset on purpose. `NORMAL = "normal"` and `LISTED = "listed"` match it too, and
    neither is a reason; this function is the ORACLE the published vocabularies are checked
    against, never the roster itself. Asking it "is `low_confidence` defined in
    pipeline/routing.py" is a question it answers exactly; asking it "which of these are
    reasons" is a question it cannot answer, and inventing a heuristic for that would put a
    guess on a blocking row.
    """
    if not exists(path):
        return set()
    try:
        tree = ast.parse(read(path))
    except SyntaxError:
        return set()
    found: Set[str] = set()
    for node in tree.body:
        targets: List[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == node.value.value.upper():
                found.add(node.value.value)
    return found


def design_reason_lists() -> Tuple[Dict[str, str], Optional[str]]:
    """docs/DESIGN.md's enumerated reason codes -> the module it attributes each to.

    The doc enumerates them as two parenthesised lists, each introduced by the module it
    credits. Parsed that way rather than by scraping every backticked snake_case token in
    the file, because the attribution is half of what this row reconciles: a reason moved
    between the ladder and routing without the doc following is exactly the drift D16 is
    for, and a flat set of strings could not see it.
    """
    design = ROOT / "docs" / "DESIGN.md"
    if not exists(design):
        return {}, "docs/DESIGN.md does not exist"
    flat = re.sub(r"\s+", " ", read(design))
    out: Dict[str, str] = {}
    for module in REASON_MODULES:
        pattern = re.escape(f"`{module}`") + r"\s*\(([^)]*)\)"
        lists = [
            match.group(1)
            for match in re.finditer(pattern, flat)
            if len(_BACKTICKED_RE.findall(match.group(1))) >= 2
        ]
        if len(lists) != 1:
            return {}, (
                f"docs/DESIGN.md should introduce exactly one parenthesised list of reason "
                f"codes with `{module}`; found {len(lists)}. This row reads that paragraph "
                f"— if it was rewritten, teach `design_reason_lists` the new shape rather "
                f"than reshaping the prose to suit the parser."
            )
        for name in _BACKTICKED_RE.findall(lists[0]):
            out[name] = module
    return out, None


# The scorer's constants, by the DEFAULT_PARAMS key each one mirrors. Written out rather
# than derived by case conversion, because a rule that turns `dSeed` into `D_SEED` also
# turns a typo into a name that simply is not found — and "not found" is how a mirror stops
# being checked without anyone deciding to stop checking it.
MOTION_MIRROR = {
    "stillK": "STILL_K",
    "moveK": "MOVE_K",
    "dSeed": "D_SEED",
    "dFloor": "D_FLOOR",
    "noiseWindowMs": "NOISE_WINDOW_MS",
    "stillFractionMin": "STILL_FRACTION_MIN",
    "restQuantile": "REST_QUANTILE",
    "stillFrames": "STILL_FRAMES",
    "stillWindow": "STILL_WINDOW",
    "refractoryMs": "REFRACTORY_MS",
    "tNovel": "T_NOVEL",
    "presenceK": "PRESENCE_K",
    "presenceMin": "PRESENCE_MIN",
    "rescueK": "RESCUE_K",
    "rescueAfter": "RESCUE_AFTER",
    "maxMoveMs": "MAX_MOVE_MS",
    "uniformMinShare": "UNIFORM_MIN_SHARE",
    "uniformToe": "UNIFORM_TOE",
    "uniformShoulder": "UNIFORM_SHOULDER",
}

# Parameters the offline scorer deliberately does not carry, each with the reason. The list
# is checked in BOTH directions below: an entry naming a parameter that no longer exists is
# as much a finding as a parameter in neither map, because a stale excuse is how a real gap
# hides.
# EMPTY SINCE 2026-09-12. `tNovel` sat here for as long as the scorer replayed only the
# stillness and presence halves; `score-trace.py gain` now reads the scaled novelty between
# consecutive fires against it, so it is mirrored like the rest. The map stays, checked in
# both directions, so the next parameter the scorer does not need has somewhere to say why.
MOTION_UNMIRRORED: Dict[str, str] = {}

_NUMERIC = re.compile(r"^[\d.\s()*/+-]+$")


def _motion_number(text: str) -> Optional[float]:
    """A parameter's value as a number, or None if it is not plain arithmetic.

    `moveK` is written `(2.0 * 16) / 9` in both files — the same expression, deliberately,
    so the 16:9 argument survives — so this cannot be a literal parse. It refuses anything
    that is not digits and operators rather than widening: an unreadable value is REPORTED
    below, never skipped, because a silently skipped parameter is an unchecked mirror.
    """
    body = text.strip().rstrip(",")
    if not _NUMERIC.match(body):
        return None
    try:
        return float(eval(body, {"__builtins__": {}}, {}))  # noqa: S307 - guarded above
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError):
        return None


def check_motion_params(report: Report) -> None:
    """`app/src/motion.ts`'s DEFAULT_PARAMS and `scripts/score-trace.py`'s mirror agree.

    THE SCORER IS A SECOND IMPLEMENTATION OF THE MACHINE, and it exists because the first
    one runs in a browser at a rig. Every threshold in this subsystem was chosen by replaying
    saved traces through `scripts/score-trace.py`, and T9 asserts its counts — so a constant
    moved in `motion.ts` and not in the scorer does not fail anything. It makes the harness
    grade a machine nobody is running, and grade it GREEN, which is worse than no grade.

    THIS ROW WAS CLAIMED BEFORE IT EXISTED. `score-trace.py` has said since D81 that "`make
    docs-audit`'s `motion params` row is what keeps the two honest"; there was no such row.
    Two constants drifted apart for the length of that claim without consequence, and D84
    widened the mirror by two more. A comment naming a check that does not exist is worse
    than no comment: it is the reason the next session does not write one.

    Provably wrong when it fires, and no judgement to defer — both numbers are literals in
    the tree, and they either match or they do not.
    """
    findings: List[Finding] = []
    ts_path = ROOT / "app/src/motion.ts"
    py_path = ROOT / "scripts/score-trace.py"
    for path in (ts_path, py_path):
        if not exists(path):
            report.add("motion params", MECHANICAL,
                       [Finding(rel(path), f"{rel(path)} is missing.")], "")
            return

    block = re.search(
        r"export const DEFAULT_PARAMS: MotionParams = \{(.*?)\n\}", read(ts_path), re.S
    )
    if block is None:
        report.add("motion params", MECHANICAL, [Finding(
            rel(ts_path),
            "no `export const DEFAULT_PARAMS: MotionParams = {...}` to read. The mirror "
            "check cannot run, which means it is not running — say so here rather than "
            "passing.",
        )], "")
        return

    declared: Dict[str, str] = {}
    for line in block.group(1).splitlines():
        entry = re.match(r"\s*([A-Za-z][A-Za-z0-9_]*)\s*:\s*(.+?),?\s*$", line)
        if entry and not line.lstrip().startswith(("*", "/")):
            declared[entry.group(1)] = entry.group(2)

    scorer: Dict[str, str] = {}
    for line in read(py_path).splitlines():
        entry = re.match(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.+?)\s*$", line)
        if entry:
            scorer[entry.group(1)] = entry.group(2)

    for name in sorted(set(declared) - set(MOTION_MIRROR) - set(MOTION_UNMIRRORED)):
        findings.append(Finding(rel(ts_path), (
            f"DEFAULT_PARAMS carries `{name}`, which is in neither MOTION_MIRROR nor "
            f"MOTION_UNMIRRORED in this file. Mirror it into scripts/score-trace.py, or "
            f"say in MOTION_UNMIRRORED why the offline scorer does not need it."
        )))
    for name in sorted((set(MOTION_MIRROR) | set(MOTION_UNMIRRORED)) - set(declared)):
        findings.append(Finding(rel(ts_path), (
            f"this file's mirror map names `{name}`, which DEFAULT_PARAMS no longer "
            f"declares. Remove the entry — a stale excuse reads as coverage."
        )))

    for name, constant in sorted(MOTION_MIRROR.items()):
        if name not in declared:
            continue
        if constant not in scorer:
            findings.append(Finding(rel(py_path), (
                f"`{constant}` is gone, but motion.ts still declares `{name}`. The offline "
                f"scorer is what chose every threshold in this subsystem and what T9 grades; "
                f"an absent constant makes it grade a different machine."
            )))
            continue
        here, there = _motion_number(declared[name]), _motion_number(scorer[constant])
        if here is None or there is None:
            findings.append(Finding(
                rel(ts_path if here is None else py_path),
                f"`{name}`/`{constant}` is not plain arithmetic, so the two cannot be "
                f"compared: {declared[name]!r} vs {scorer[constant]!r}. Keep both a number "
                f"or an expression over numbers.",
            ))
        elif here != there:
            findings.append(Finding(rel(py_path), (
                f"`{name}` is {declared[name].strip()} in app/src/motion.ts and "
                f"`{constant}` is {scorer[constant].strip()} here. The rig runs the first "
                f"and every saved trace is scored against the second."
            )))

    report.add(
        "motion params",
        MECHANICAL,
        findings,
        f"{len(MOTION_MIRROR)} mirrored constants agree, {len(MOTION_UNMIRRORED)} accounted for",
        scanned=len(MOTION_MIRROR),
    )


def check_supervisor_self_watch(report: Report) -> None:
    """Every project module the supervisor imports is in its own `SELF_FILES`.

    `scripts/serve.py` restarts ITSELF when a file it is made of changes — `os.execv`, same
    pid, children rebuilt. That list is hand-written, and a hand-written list of a file's own
    imports is exactly the thing that goes stale the next time somebody adds one.

    THE FAILURE IT PREVENTS IS SILENT, WHICH IS WHY IT BLOCKS. An import that is watched but
    absent from `SELF_FILES` still restarts the capture CHILD — visibly, in the log, looking
    like the change landing — while the supervisor goes on running the module it imported at
    boot, because Python caches it. Something restarts, so nothing looks wrong. That is how
    `server/ports.py` behaved before D138's amendment.

    Provably wrong when it fires, and no judgement to defer: the import is right there in the
    same file as the list that fails to mention it.
    """
    findings: List[Finding] = []
    path = ROOT / "scripts" / "serve.py"
    if not exists(path):
        report.add("supervisor self-watch", MECHANICAL,
                   [Finding(rel(path), "scripts/serve.py is missing.")], "")
        return

    tree = ast.parse(read(path))

    declared: Set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SELF_FILES":
                    try:
                        declared = set(ast.literal_eval(node.value))
                    except (ValueError, SyntaxError):
                        declared = set()

    # Module-level imports only: something imported inside a handler is not held across the
    # life of the process in the way that makes staleness possible.
    imported: Set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.replace(".", "/") + ".py")
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                imported.add(f"{node.module.replace('.', '/')}/{alias.name}.py")

    # Project-local means "resolves to a file in this repo". Stdlib and third-party do not,
    # and neither can go stale under us anyway — they are not what a `git pull` rewrites.
    local = {name for name in imported if (ROOT / name).is_file()}

    for name in sorted(local - declared):
        findings.append(
            Finding(
                rel(path),
                f"imports `{name}` at module scope but SELF_FILES does not list it. Python "
                f"caches that module, so a change to it leaves this supervisor running the "
                f"old code while its CHILD restarts and looks like the fix landed. Add it to "
                f"SELF_FILES.",
            )
        )

    report.add(
        "supervisor self-watch",
        MECHANICAL,
        findings,
        f"{len(declared)} self-files, every module-scope import accounted for",
        scanned=len(declared),
    )


def _withhold_reasons() -> Row:
    """The three withhold reasons, reconciled across the two languages that declare them.

    D86 gives `overrides` a second kind of answer — a SKU the operator is deliberately not
    listing, carrying a reason — and the reason vocabulary is authored in `pipeline/
    decisions.py` and offered by `app/src/holds.ts`. That is two independent declarations of
    one closed set, which is exactly the shape `check_reason_codes` above exists for and
    exactly the drift D16 exists to catch.

    IT MATTERS MORE HERE THAN FOR THE REVIEW REASONS, and the reason is worth stating: `PUT
    /pipeline/runs/<name>/decisions` writes that document with NO VALIDATION AT ALL and says
    so in its own comment. The screen's defence against writing an unparseable file is that it
    builds the document from typed state and cannot construct a shape its own code does not
    know — and that defence is worth exactly as much as the two declarations agreeing.
    A reason the screen offers and the parser refuses is a run the operator cannot join.

    BLOCKING, because a mismatch is provably wrong rather than a question of judgement.

    THE HUMAN LABELS ARE NOT CHECKED and that is deliberate: `WITHHOLD_LABELS` is prose for a
    person, `docs/DESIGN.md` does not enumerate it, and a rule about wording would be this
    audit taking a view on English. What is checked is the machine string, which is the thing
    that has to match a parser.
    """
    findings: List[Finding] = []
    python_path = ROOT / "pipeline" / "decisions.py"
    ts_path = ROOT / "app" / "src" / "holds.ts"

    authored: Set[str] = set()
    for node in ast.walk(ast.parse(read(python_path))):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "WITHHOLD_REASONS" not in names:
            continue
        try:
            authored = set(ast.literal_eval(node.value))
        except (ValueError, SyntaxError):
            findings.append(
                Finding(
                    "pipeline/decisions.py",
                    "WITHHOLD_REASONS is not a literal this audit can read. It is a "
                    "hand-authored vocabulary in D22's sense and has to stay one.",
                )
            )

    ts_text = read(ts_path)
    match = re.search(r"WITHHOLD_REASONS\s*=\s*\[(.*?)\]", ts_text, re.S)
    offered: Set[str] = set(re.findall(r"'([^']+)'", match.group(1))) if match else set()

    if not authored:
        findings.append(
            Finding("pipeline/decisions.py", "WITHHOLD_REASONS is missing or empty.")
        )
    if match is None:
        findings.append(
            Finding(
                "app/src/holds.ts",
                "no WITHHOLD_REASONS array — the screen has to declare the vocabulary it "
                "offers, in one place, or nothing can reconcile it with the parser.",
            )
        )

    for reason in sorted(offered - authored):
        findings.append(
            Finding(
                "app/src/holds.ts",
                f"{reason!r} is offered by the screen and is not in "
                f"pipeline/decisions.py:WITHHOLD_REASONS — `_withheld` refuses it, so "
                f"choosing it writes an inventory/prices.json the next join cannot read.",
            )
        )
    for reason in sorted(authored - offered):
        findings.append(
            Finding(
                "app/src/holds.ts",
                f"{reason!r} is authored in pipeline/decisions.py and the screen does not "
                f"offer it — legal in the file, unreachable from the product.",
            )
        )

    return Row(
        "withhold reasons",
        MECHANICAL,
        findings,
        f"{len(authored)} authored, offered by the screen, none unreachable",
        scanned=len(authored),
    )


def _order_reasons() -> Row:
    """The six order-line reasons, reconciled across the two languages that declare them.

    D69's order screen looks a reason UP rather than re-deriving it from whatever the line
    carries beside it, so `app/src/orderReasons.ts:ORDER_REASONS` is a second independent
    declaration of `pipeline/orders.py:LINE_REASONS`. That is the shape `check_reason_codes`
    and `check_withhold_reasons` above both exist for, and exactly the drift D16 exists to
    catch. `orderReasons.ts`'s own header asserts in writing that this check exists; without
    it that paragraph would name a control that is not there, which is the failure
    `app/eslint.config.js`'s header calls worse than admitting there is none.

    THE COMPILER ALREADY DOES THE OTHER HALF AND CANNOT DO THIS ONE. Within the app,
    `ORDER_REASONS` carries `satisfies readonly OrderLineReason[]` and the two lookup tables
    are `Record<OrderLineReason, string>`, so the array cannot say a word the union does not
    and the tables cannot miss one. What no TypeScript can do is import a Python tuple: a
    reason `pipeline/orders.py` gains and this file does not is invisible until something
    compares the two files as text, and this is that something.

    BLOCKING, because a mismatch is provably wrong rather than a question of judgement. A
    reason the resolver emits and the screen has no entry for renders as its own machine
    string — `orderReasonLabel`'s `?? reason` fallback is deliberate and is not a repair —
    but the row then reads as a raw code to the one person who has to act on it, and the
    remedy beside it is blank.

    THE TUPLE IS READ THROUGH ITS OWN CONSTANTS, which is where this parts company with
    `check_withhold_reasons` one function up. `LINE_REASONS` is a tuple of NAMES
    (`RESOLVED`, `SHORT`, …) rather than of string literals, so `ast.literal_eval` cannot
    read it at all. The module's own `NAME = "literal"` assignments are collected first and
    the tuple's elements are resolved through them; a member that is neither a literal nor a
    name this file assigns a string to is REPORTED rather than skipped, because a silently
    dropped member would make this check quietly smaller than it looks.

    THE HUMAN LABELS AND REMEDIES ARE NOT CHECKED, for `check_withhold_reasons`' reason:
    they are prose for a person, and a rule about wording would be this audit taking a view
    on English. What is checked is the machine string, which is what has to match a resolver.
    """
    findings: List[Finding] = []
    python_path = ROOT / "pipeline" / "orders.py"
    ts_path = ROOT / "app" / "src" / "orderReasons.ts"

    tree = ast.parse(read(python_path))

    # Module-level `NAME = "literal"`, which is how this module spells its vocabulary.
    literals: Dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                literals[target.id] = node.value.value

    authored: Set[str] = set()
    seen_tuple = False
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "LINE_REASONS" for t in node.targets):
            continue
        seen_tuple = True
        if not isinstance(node.value, (ast.Tuple, ast.List)):
            findings.append(
                Finding(
                    "pipeline/orders.py",
                    "LINE_REASONS is not a tuple or list this audit can read. It is a "
                    "hand-authored vocabulary in D22's sense and has to stay one.",
                )
            )
            continue
        for element in node.value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                authored.add(element.value)
            elif isinstance(element, ast.Name) and element.id in literals:
                authored.add(literals[element.id])
            else:
                findings.append(
                    Finding(
                        "pipeline/orders.py",
                        "LINE_REASONS carries a member that is neither a string literal nor "
                        "a name this module assigns a string to, so this check cannot say "
                        "what the vocabulary is. Spell every member as a module-level "
                        "constant or as a literal.",
                    )
                )

    ts_text = read(ts_path)
    match = re.search(r"ORDER_REASONS\s*=\s*\[(.*?)\]", ts_text, re.S)
    offered: Set[str] = set(re.findall(r"'([^']+)'", match.group(1))) if match else set()

    if not seen_tuple or not authored:
        findings.append(
            Finding("pipeline/orders.py", "LINE_REASONS is missing or empty.")
        )
    if match is None:
        findings.append(
            Finding(
                "app/src/orderReasons.ts",
                "no ORDER_REASONS array — the screen has to declare the vocabulary it "
                "offers, in one place, or nothing can reconcile it with the resolver. A "
                "`Record`'s keys are a type and are erased; a text check needs a list.",
            )
        )

    for reason in sorted(offered - authored):
        findings.append(
            Finding(
                "app/src/orderReasons.ts",
                f"{reason!r} is offered by the screen and is not in "
                f"pipeline/orders.py:LINE_REASONS — no resolved line can ever carry it, so "
                f"it is a label, a remedy and a filter position for a state that cannot "
                f"happen.",
            )
        )
    for reason in sorted(authored - offered):
        findings.append(
            Finding(
                "app/src/orderReasons.ts",
                f"{reason!r} is authored in pipeline/orders.py and the screen does not "
                f"offer it — the resolver emits it and the row draws the raw machine string "
                f"with a blank remedy beside it.",
            )
        )

    return Row(
        "order reasons",
        MECHANICAL,
        findings,
        f"{len(authored)} authored, offered by the screen, none unreachable",
        scanned=len(authored),
    )


def _terminal_statuses() -> Row:
    """The terminal-status vocabulary, reconciled between the code and its own published claim.

    D63 amended 2026-09-13 on the owner's two rulings — a Canceled order is never open, and
    an order the feed reports Shipped or Delivered closes on that word — and
    `store/orders.py:is_terminal_status` is where the vocabulary that answers both lives,
    exactly once, in `TERMINAL_STATUSES`. That set is hand-authored in D22's sense: it is not
    derivable from anything else in the tree, so a typo or a dropped entry is invisible to
    every other check here.

    THIS ROW ANSWERS FROM THE TREE ALONE, DELIBERATELY, WHICH IS `make lan-check`'s ARGUMENT
    APPLIED HERE. The honest reconciliation for a vocabulary like this is against the
    DISTINCT statuses a real feed has actually sent — `make docs-audit` cannot do that
    because it never opens `inventory/store.sqlite` and never will (that is what would make
    it `make lan-check`'s problem instead: a live-store dependency this audit's other ninety
    rows deliberately do not carry). So the second declaration this row reconciles against is
    not a store, it is the fenced `terminal-statuses` block inside
    `docs/decisions/D063-…md` itself — the decision entry's own published claim of what the
    set contains, written in a shape this function can parse directly. That fenced block is not decoration: a session amending `TERMINAL_STATUSES` in
    code without moving the block, or the reverse, fails this row rather than silently
    drifting apart, which is the whole of what D16 asks a hand-authored vocabulary to do.

    BLOCKING, for `check_withhold_reasons`' reason and it applies verbatim: whether the
    mechanism is any GOOD (whether the strings are the right ones to treat as terminal) is a
    judgement call the owner already made; whether the code and its own decision entry still
    agree about what was decided is arithmetic.

    THE COMPARISON IS EXACT-STRING, NEVER CASE-FOLDED, on purpose — this row is checking that
    two DECLARATIONS spell the same set the same way, which is a stricter question than
    whether two ORDER STATUSES refer to the same fact (that folding lives in
    `is_terminal_status` itself, at RUN time, and is unrelated to this comparison).
    """
    findings: List[Finding] = []
    python_path = ROOT / "store" / "orders.py"
    # the entry is found by its number, so a retitle never breaks this row
    doc_path = next(iter(sorted((ROOT / "docs" / "decisions").glob("D063-*.md"))),
                    ROOT / "docs" / "decisions" / "D063-missing.md")

    tree = ast.parse(read(python_path))
    authored: Optional[Set[str]] = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "TERMINAL_STATUSES" for t in node.targets):
            continue
        value = node.value
        # `frozenset({...})` — the call's first argument is the literal set this audit reads.
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "frozenset"
            and value.args
        ):
            value = value.args[0]
        try:
            authored = set(ast.literal_eval(value))
        except (ValueError, SyntaxError):
            findings.append(
                Finding(
                    "store/orders.py",
                    "TERMINAL_STATUSES is not a literal this audit can read. It is a "
                    "hand-authored vocabulary in D22's sense and has to stay one.",
                )
            )

    if authored is None:
        findings.append(
            Finding("store/orders.py", "TERMINAL_STATUSES is missing.")
        )
        authored = set()
    elif not authored:
        findings.append(
            Finding("store/orders.py", "TERMINAL_STATUSES is empty.")
        )

    if not exists(doc_path):
        findings.append(
            Finding(str(doc_path.relative_to(ROOT)), "does not exist — D63's amendment "
                    "cannot be checked against code that has moved past it.")
        )
        published: Set[str] = set()
    else:
        match = re.search(r"```terminal-statuses\n(.*?)```", read(doc_path), re.S)
        if match is None:
            findings.append(
                Finding(
                    str(doc_path.relative_to(ROOT)),
                    "carries no fenced `terminal-statuses` block — the decision entry has "
                    "to publish the set it settled on in a shape this script can parse, or "
                    "there is nothing here to reconcile the code against.",
                )
            )
            published = set()
        else:
            published = {line.strip() for line in match.group(1).splitlines() if line.strip()}

    for status in sorted(authored - published):
        findings.append(
            Finding(
                "store/orders.py",
                f"{status!r} is in TERMINAL_STATUSES and not in D63's published "
                f"`terminal-statuses` block — the code recognises a status the decision "
                f"entry never says it does.",
            )
        )
    for status in sorted(published - authored):
        findings.append(
            Finding(
                str(doc_path.relative_to(ROOT)),
                f"{status!r} is published in the `terminal-statuses` block and is not in "
                f"store/orders.py:TERMINAL_STATUSES — the decision entry claims a status "
                f"closes an order and the code does not recognise it.",
            )
        )

    return Row(
        "terminal statuses",
        MECHANICAL,
        findings,
        f"{len(authored)} authored, published in D63, none unreachable",
        scanned=len(authored),
    )


def _pricing_presets() -> Row:
    """The three pricing presets, reconciled between the tuple that prices them and the
    table that writes them.

    `pipeline/pricing.py:PRESETS` is `(key, rule, basis)` and prices every SKU under every preset
    so the client performs no arithmetic on money. `app/src/Pricing.tsx:PRESETS` is what a
    press on the pricing screen writes into `inventory/prices.json` — and it has to write the RULE,
    because D86 refuses to write the suggestions themselves: an override is layer 1 of
    `prices_for` and would beat the rule at layer 4, producing a run where changing the preset
    silently changed nothing.

    THE DEFECT THAT PUT THIS ROW HERE IS THAT SAME FAILURE BY THE OTHER ROAD. The press wrote
    `preset: <key>`, a field `pipeline/decisions.py:parse` does not know and `to_payload` does
    not emit — so the next join dropped it and `rule`/`basis` never moved. Measured on the
    owner's riftbound run: `preset: market_undercut_5` beside `rule: match`, 2 overrides across
    50 SKUs, and 48 cards about to list at a price nobody had chosen. Nothing could see it: no
    check compared the two tables, and the screen never drew which rule was live.

    BLOCKING, for the reason `check_withhold_reasons` above gives and which applies here
    nearly verbatim: `PUT /pricing` refuses a rule `pricing.Rule.parse` cannot read, but a
    refused save is an answer that never landed, so two declarations agreeing is still the
    whole defence. A rule the screen writes and the parser refuses is a run `emit` cannot price.

    THE LABELS AND THE BLURBS ARE NOT CHECKED, the same carve-out and the same reason: they are
    prose for a person, and a rule about wording would be this audit taking a view on English.
    What is checked is the triple a parser has to accept.
    """
    findings: List[Finding] = []
    # THE TABLE MOVED TO `pipeline/pricing.py` ON 2026-09-07 AND THIS ROW FOLLOWED IT. Two
    # callers price presets now — a run's `pricing.json` and a markdown's `survey.json` — and
    # the second was shipping `presets: {}`, so every preset button on the lens filled nothing
    # while still writing the store's standing rule. `cli/cmd_join.py` re-exports the name its
    # own callers already spell, and a re-export is not a table this audit can read, which is
    # exactly what it said when the move happened.
    python_path = ROOT / "pipeline" / "pricing.py"
    ts_path = ROOT / "app" / "src" / "Pricing.tsx"

    # `PRESETS` NAMES `pricing.RULE_MATCH` RATHER THAN `"match"`, WHICH IS RIGHT AND IS WHY
    # THIS IS NOT A `literal_eval`. Referring to the constant is what keeps `cmd_join.py` from
    # being a fourth place a rule name is spelled; the cost is that reading it means resolving
    # `pricing.<NAME>` first. Resolved by `ast` out of `pipeline/pricing.py`, never by
    # importing — same rule D22 sets for the game registry and this script keeps for itself.
    constants: Dict[str, object] = {}
    for node in ast.walk(ast.parse(read(ROOT / "pipeline" / "pricing.py"))):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                constants[target.id] = node.value.value

    def resolved(node):
        """One PRESETS cell as its string, or None where this audit cannot say."""
        if isinstance(node, ast.Constant):
            return node.value
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "pricing"
        ):
            return constants.get(node.attr)
        # AND A BARE NAME, BECAUSE THE TABLE NOW LIVES IN THE MODULE THAT DEFINES THOSE
        # CONSTANTS. `cli/cmd_join.py` spelled them `pricing.RULE_MATCH`; inside
        # `pipeline/pricing.py` the same constant is `RULE_MATCH`, and a `pricing.` prefix
        # there would be a module referring to itself. Resolved against the SAME dict, so
        # there is still exactly one place a rule name is spelled and this row still
        # reconciles rather than going quietly green.
        if isinstance(node, ast.Name):
            return constants.get(node.id)
        return None

    authored: Set[tuple] = set()
    for node in ast.walk(ast.parse(read(python_path))):
        if not isinstance(node, ast.Assign):
            continue
        if "PRESETS" not in [t.id for t in node.targets if isinstance(t, ast.Name)]:
            continue
        if not isinstance(node.value, (ast.Tuple, ast.List)):
            findings.append(
                Finding(
                    "cli/cmd_join.py",
                    "PRESETS is not a table this audit can read. It is a hand-authored "
                    "table in D22's sense and has to stay one.",
                )
            )
            continue
        for row in node.value.elts:
            if not isinstance(row, (ast.Tuple, ast.List)) or len(row.elts) != 3:
                continue
            cells = [resolved(cell) for cell in row.elts]
            if all(isinstance(cell, str) for cell in cells):
                authored.add(tuple(cells))
            else:
                findings.append(
                    Finding(
                        "cli/cmd_join.py",
                        "a PRESETS row names something this audit cannot resolve to a "
                        "string. Spell it as a literal or as a `pricing.` constant, or this "
                        "row stops reconciling anything and goes quietly green.",
                    )
                )

    ts_text = read(ts_path)
    block = re.search(r"const PRESETS[^=]*=\s*\[(.*?)\n\]", ts_text, re.S)
    offered: Set[tuple] = set()
    if block is None:
        findings.append(
            Finding(
                "app/src/Pricing.tsx",
                "no PRESETS array — the screen has to declare the rule each preset writes, "
                "in one place, or nothing can reconcile it with the tuple that prices them.",
            )
        )
    else:
        for entry in re.findall(r"\{(.*?)\}", block.group(1), re.S):
            fields = dict(re.findall(r"(key|rule|basis):\s*'([^']*)'", entry))
            if {"key", "rule", "basis"} <= set(fields):
                offered.add((fields["key"], fields["rule"], fields["basis"]))
            elif "key" in fields:
                findings.append(
                    Finding(
                        "app/src/Pricing.tsx",
                        f"preset {fields['key']!r} declares no rule/basis pair. A press has "
                        f"to write one: writing anything else leaves the run at whatever rule "
                        f"it already had, which is the defect this row exists for.",
                    )
                )

    if not authored:
        findings.append(Finding("cli/cmd_join.py", "PRESETS is missing or empty."))

    for entry in sorted(offered - authored):
        findings.append(
            Finding(
                "app/src/Pricing.tsx",
                f"the screen writes {entry!r} and cli/cmd_join.py:PRESETS does not price it — "
                f"so the suggested numbers on screen are not what this rule emits.",
            )
        )
    for entry in sorted(authored - offered):
        findings.append(
            Finding(
                "app/src/Pricing.tsx",
                f"cli/cmd_join.py prices {entry!r} and the screen does not write it — priced "
                f"into every row of the pricing table, reachable from nothing.",
            )
        )

    return Row(
        "pricing presets",
        MECHANICAL,
        findings,
        f"{len(authored)} priced, written by the screen, key rule and basis agree",
        scanned=len(authored),
    )


def _transport_url_constants(tree: ast.AST) -> Dict[str, str]:
    """Module-level `NAME = "https://..."` assignments. The routes, as the code holds them."""
    out: Dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            continue
        if not value.value.startswith(("http://", "https://")):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                out[target.id] = value.value
    return out


def _carries_a_url(value: ast.AST, accessors: Dict[str, str]) -> bool:
    """Whether an assignment's right-hand side is a URL being BUILT rather than one being USED.

    THE DISTINCTION IS THE WHOLE ACCURACY OF THE ROW, and getting it wrong was measured on the
    first run: `following = _check_status(status, headers, url)` MENTIONS the download's URL,
    so a reader that propagated through any expression containing it decided the redirect hop
    was a fourth route — `GET /admin/pricing/downloadexportcsv`, a request this file cannot
    make. A promise checked against a route that does not exist fails a commit for nothing,
    which is how a row gets switched off.

    So a string expression carries the URL forward — a name, an f-string, a concatenation, a
    literal, a call to one of the endpoint accessors — and a call to anything else does not.
    An accessor is a function that returns one of the constants; nothing here reads a name.
    """
    if isinstance(value, ast.Call):
        return isinstance(value.func, ast.Name) and value.func.id in accessors
    return isinstance(value, (ast.Name, ast.JoinedStr, ast.BinOp, ast.Constant))


def _transport_requests(tree: ast.AST, urls: Dict[str, str]) -> Set[Tuple[str, str]]:
    """(constant name, METHOD) for every request the module can issue against its own routes.

    THE METHOD IS THE KEYWORD, WHICH IS WHY THIS IS A FACT AND NOT A READING. `_open` builds
    `method="POST" if data else "GET"` and there is no other opener in the file, so a call site
    that passes `data=` is a POST and one that does not is a GET. Nothing is inferred from a
    function's name.

    ATTRIBUTION IS BY THE URL A CALL WAS HANDED, walked back through the accessors — `endpoint`,
    `live_endpoint`, `_filters_endpoint` are just functions that return one of the constants, so
    a local assigned from one of them carries that constant, and so does a local assigned from
    such a local (`url = f"{url}?..."` keeps what `url` already meant).

    A REDIRECT HOP IS DELIBERATELY NOT A ROUTE. The second `_open` in each fetch is handed
    `following`, a Location the portal chose, and this module never names it — one hop is
    followed and the cookie does not cross a host change, which is the bullet's own sentence.
    Counting it would make the promise answer for somebody else's server.
    """
    accessors: Dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Return)
                and isinstance(sub.value, ast.Name)
                and sub.value.id in urls
            ):
                accessors[node.name] = sub.value.id

    pairs: Set[Tuple[str, str]] = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        carries: Dict[str, str] = {}
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assign) and _carries_a_url(sub.value, accessors):
                reached = set()
                for inner in ast.walk(sub.value):
                    if isinstance(inner, ast.Name):
                        if inner.id in urls:
                            reached.add(inner.id)
                        elif inner.id in carries:
                            reached.add(carries[inner.id])
                    elif (
                        isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Name)
                        and inner.func.id in accessors
                    ):
                        reached.add(accessors[inner.func.id])
                if len(reached) == 1:
                    for target in sub.targets:
                        if isinstance(target, ast.Name):
                            carries[target.id] = next(iter(reached))
            if not (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Name)
                and sub.func.id == TRANSPORT_OPENER
            ):
                continue
            first = sub.args[0] if sub.args else None
            named = None
            if isinstance(first, ast.Name):
                named = carries.get(first.id) or (first.id if first.id in urls else None)
            elif isinstance(first, ast.Call) and isinstance(first.func, ast.Name):
                named = accessors.get(first.func.id)
            if named is None:
                continue
            body = next((kw for kw in sub.keywords if kw.arg == "data"), None)
            empty = body is not None and isinstance(body.value, ast.Constant) and body.value.value is None
            pairs.add((named, "GET" if body is None or empty else "POST"))
    return pairs


def _refusals_reachable(tree: ast.AST, root: str) -> Optional[Set[str]]:
    """Every `FetchRefusal` code raisable from `root`, following calls within the module.

    A CLOSURE OVER THE CALL GRAPH, not a grep of the file and not a read of one function.
    `filters` raises two of the nine itself; the other seven come out of `_cookie`, `_open`,
    `_check_status` and the endpoint accessors. A reader that stopped at the function the route
    names would have reported two — which is exactly the number the screen already labeled,
    so it would have blessed the defect it was written to find. Measured by removing the
    recursion: seven codes flip to unreachable.

    Returns None when `root` is not defined, which is a finding rather than an empty answer: an
    empty set reads as "nothing can go wrong", and the difference between that and "this reader
    has lost its subject" is the whole value of the row.
    """
    bodies = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    if root not in bodies:
        return None
    seen: Set[str] = set()
    codes: Set[str] = set()
    pending = [root]
    while pending:
        name = pending.pop()
        if name in seen or name not in bodies:
            continue
        seen.add(name)
        for node in ast.walk(bodies[name]):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "FetchRefusal":
                first = node.args[0] if node.args else None
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    codes.add(first.value)
            elif node.func.id in bodies:
                pending.append(node.func.id)
    return codes


def check_hint_reasons(report: Report) -> None:
    """The capture screen's refusal labels, against the refusals its route can send.

    **THE ONE PLACE A TRANSPORT REFUSAL BECOMES A SENTENCE ON A SCREEN.** Three of the four
    call sites into `server/tcg_export.py` answer 502 carrying the module's own remedial
    sentence. The fourth — `GET /pipeline/games/<game>/sets` — answers 200 and hands the CODE
    to `CaptureScreen.tsx` to re-word, because the operator is mid-capture and a failed
    autocomplete is not a failed capture. That is argued and it is right. What it means is that
    `hintReason` is the copy for nine refusals, and nothing read it.

    **IT NAMED TWO OF THE NINE.** Measured 2026-09-06. The other seven fell to the map's
    unknown-code tail and printed as `Set list unavailable (tcg_blocked)`. The tail is argued
    and correct — `docs/DESIGN.md` shows reason codes beside names, so what the operator saw
    stays greppable — and a session widening the map wrote over that argument before putting
    it back. THE DEFECT IS THE SEVEN, NOT THE TAIL: a floor is not where nine tenths of a map
    should land. Nothing could say so — the route was green, the screen typechecked, and the
    only way to see it was to make TCGplayer refuse a real client.

    **MECHANICAL, and the reachability is the part that makes it so.** The codes are string
    literals in `FetchRefusal(...)` calls and the map is a run of `code === '...'` comparisons;
    both are read with a parser, and the reachable set is closed over the module's own call
    graph rather than taken from the one function the route names — see `_refusals_reachable`
    for what that difference measured.

    **BOTH DIRECTIONS.** A reachable code the map does not name is an operator reading a
    fallback. A code the map names that nothing can raise is a dead branch, and dead branches
    are how a map stops being readable as the answer to "what can happen here"; those are
    permitted only through `HINT_REASON_NON_TRANSPORT`, which carries the reason for each.

    **THE ROUTE CARRIES `message` NOW, AND THIS ROW IS WHY THAT IS NOT THE FIX.** A fallback
    that is routinely what the operator reads is a fallback nobody ever widens the map for —
    which is how two-of-nine survived. The transport's sentence sits between the map and the
    bare code, and it names `.env`, which this screen deliberately does not; the map is what
    the screen owes.
    """
    findings: List[Finding] = []
    module = rel(TRANSPORT_PROMISE_MODULE)
    screen = rel(HINT_REASON_SCREEN)

    for path in (TRANSPORT_PROMISE_MODULE, HINT_REASON_SCREEN):
        if not exists(path):
            report.add("hint reasons", MECHANICAL, [Finding(rel(path), "does not exist")])
            return

    try:
        tree = ast.parse(read(TRANSPORT_PROMISE_MODULE))
    except SyntaxError as exc:
        report.add("hint reasons", MECHANICAL, [Finding(module, f"cannot be parsed.\n{exc}")])
        return

    reachable = _refusals_reachable(tree, HINT_REASON_ROOT)
    if reachable is None:
        report.add("hint reasons", MECHANICAL, [Finding(module, (
            f"defines no `{HINT_REASON_ROOT}`, which is the call the set-list route makes and "
            f"the root this row walks from.\n  Re-point `HINT_REASON_ROOT`, or drop the row — "
            f"a reader with no subject reports nothing and\n  blesses whatever the screen "
            f"happens to say."
        ))], "")
        return

    block = _HINT_REASON_FN_RE.search(read(HINT_REASON_SCREEN))
    if block is None:
        report.add("hint reasons", MECHANICAL, [Finding(screen, (
            "defines no `hintReason` this row can read. It is the copy for every refusal the "
            "set-list route can send;\n  either it was renamed, or it was restructured past "
            "the pattern watching it. A check that quietly\n  stops covering a screen's copy "
            "is worse than no check."
        ))], "")
        return

    named = set(_HINT_REASON_CODE_RE.findall(block.group(1)))

    for code in sorted(reachable - named):
        findings.append(Finding(screen, (
            f"does not name `{code}`, which `{module}:{HINT_REASON_ROOT}` can raise and the "
            f"set-list route sends\n  straight to this screen. Unnamed, the operator reads the "
            f"transport's own sentence — written for the\n  pipeline's reader, not for "
            f"somebody holding a card over a stand. Give it a clause in the rig's register."
        )))

    for code in sorted(named - reachable - set(HINT_REASON_NON_TRANSPORT)):
        findings.append(Finding(screen, (
            f"names `{code}` and nothing reachable from `{module}:{HINT_REASON_ROOT}` raises "
            f"it, so that branch is dead.\n  Strike it, or record it in "
            f"`HINT_REASON_NON_TRANSPORT` with where it does come from — a map that may name\n"
            f"  anything cannot be read as the answer to what can happen here."
        )))

    for code, why in sorted(HINT_REASON_NON_TRANSPORT.items()):
        if code not in named:
            findings.append(Finding(screen, (
                f"no longer names `{code}`, which is declared as a code this map covers: {why}\n"
                f"  Either the screen stopped labelling it — and it now falls through — or the "
                f"declaration is stale."
            )))

    report.add(
        "hint reasons",
        MECHANICAL,
        findings,
        f"{len(reachable)} refusals reachable from {HINT_REASON_ROOT}(), "
        f"{len(named)} labeled by the screen",
        scanned=len(reachable),
    )


def check_transport_promise(report: Report) -> None:
    """`server/tcg_export.py`'s first bullet, against the constants and calls beneath it.

    **THE FILE THIS ROW WATCHES IS THE ONE THAT READS THE BEARER CREDENTIAL**, and its opening
    four bullets are not description — the module says so itself. `server/capture_server.py`
    promised for months that this process "holds no API key and makes no outbound call"; this
    file broke the second half literally, and rather than narrow the promise to a technicality
    it deleted it and wrote four replacement bullets. A replacement nobody maintains is the
    narrowing arriving late, which is D16's whole subject.

    **AND THE FIRST BULLET HAD ALREADY DONE IT.** `One host, one method, one route` was written
    on 2026-08-30 over a single GET and was true that morning. D65 landed the same day: the
    download became a POST against `/admin/pricing/downloadexportcsv`, and the filter list went
    from a line in the auth measurement table to a call the module makes. D104 added the live
    download on 2026-09-06. Three routes, two methods, and the sentence above them never moved
    — nor did `server/pipeline_routes.py`'s copy of it, which is the shape a claim takes once
    it has a second home and no reader.

    **MECHANICAL, because none of it is a judgement.** The host of a `https://` constant, the
    path of one, and whether an `_open` call carries a body are three facts in one file, and
    `_open` builds `method="POST" if data else "GET"` so the keyword is the method. A finding is
    a (method, route) pair the code can issue and the bullet does not tabulate, or one the
    bullet tabulates and the code cannot issue. Both directions: an unlisted route is the drift
    that happened, and a listed-but-unreachable one is the promise describing a file that has
    moved on.

    **IT REFUSES TO GO QUIET**, which `check census` paid for and this row inherits. A headline
    reworded past the pattern, a table that yields no routes, or a module with no attributable
    request is REPORTED rather than passed — a promise this row stops reading is a promise back
    in exactly the state it spent a week in, and green.

    **WHAT IT DOES NOT CHECK.** The other three bullets. "It cannot cause a charge", "the secret
    never leaves this module" and "every anticipated failure has its own code" are arguments
    about what the code does NOT do, and a check that claimed to settle those would be asserting
    the absence of something rather than the presence of it — the vacuous green docs/debts/
    opens by warning about. They are verified by reading, and the reading is recorded in the
    bullets themselves.
    """
    findings: List[Finding] = []
    where = rel(TRANSPORT_PROMISE_MODULE)
    if not exists(TRANSPORT_PROMISE_MODULE):
        report.add("transport promise", MECHANICAL, [Finding(where, "does not exist")])
        return

    try:
        tree = ast.parse(read(TRANSPORT_PROMISE_MODULE))
    except SyntaxError as exc:
        report.add(
            "transport promise",
            MECHANICAL,
            [Finding(where, f"cannot be parsed, so neither its promise nor its calls can be "
                            f"read.\n{exc}")],
        )
        return

    promise = ast.get_docstring(tree) or ""
    headline = _TRANSPORT_HEADLINE_RE.search(promise)
    if headline is None:
        report.add(
            "transport promise",
            MECHANICAL,
            [Finding(where, (
                "its module docstring no longer opens with a `**N hosts, N methods, N routes**"
                "` headline, so the promise over the credential this file reads is watched by\n"
                "  nothing. Either the bullet was deleted, or it was reworded past the pattern.\n"
                "  Re-point `_TRANSPORT_HEADLINE_RE`, or take the row out deliberately — a check\n"
                "  whose subject has left is worse than no check."
            ))],
            "",
        )
        return

    tail = promise[headline.end():]
    cut = tail.find("\n  - **")
    bullet = tail if cut < 0 else tail[:cut]

    urls = _transport_url_constants(tree)
    issued = _transport_requests(tree, urls)
    reachable = {(method, urlparse(urls[name]).path) for name, method in issued}
    hosts = {urlparse(value).netloc for value in urls.values()}
    tabulated = {(method.upper(), route) for method, route in _TRANSPORT_ROUTE_RE.findall(bullet)}

    if not urls:
        findings.append(Finding(where, (
            "declares no module-level `https://` URL constant. The bullet promises the routes "
            "are constants rather than\n  anything a request can name; there is nothing here "
            "for that to be true of."
        )))
    if not issued:
        findings.append(Finding(where, (
            f"no `{TRANSPORT_OPENER}` call could be attributed to one of its URL constants, so "
            f"this row cannot say what the\n  module reaches. Either every request moved out of "
            f"`{TRANSPORT_OPENER}`, or the accessors stopped returning\n  the constants — and "
            f"either way the promise above them is unread."
        )))
    if not tabulated:
        findings.append(Finding(where, (
            "its first bullet tabulates no `METHOD /path` lines. The headline counts routes and "
            "nothing names them,\n  which is the state that let `one method, one route` stand "
            "over three of each for a week."
        )))

    for method, route in sorted(reachable - tabulated):
        findings.append(Finding(where, (
            f"reaches `{method} {route}` and the promise does not name it. This is the module "
            f"that carries the operator's\n  session cookie; a route it can open and its own "
            f"header does not list is the narrowing D16 exists to catch."
        )))
    for method, route in sorted(tabulated - reachable):
        findings.append(Finding(where, (
            f"promises `{method} {route}` and no call in this file can issue it. A promise that "
            f"describes a file which has\n  moved on is read as current by the next session; "
            f"strike it, or restore the call."
        )))

    if len(hosts) > 1:
        findings.append(Finding(where, (
            "names more than one host — " + ", ".join(sorted("`%s`" % h for h in hosts)) + ". "
            "The bullet says one, and `server/order_transport.py`\n  exists precisely because "
            "the second host got its own module rather than a second URL in this one."
        )))
    for host in sorted(hosts):
        if host and host not in bullet:
            findings.append(Finding(where, (
                f"opens sockets to `{host}` and its first bullet does not say so. The host is "
                f"the one thing a reader\n  checks before trusting where the cookie goes."
            )))

    claimed = [_TRANSPORT_NUMBERS.get(word.lower()) for word in headline.groups()]
    actual = [len(hosts), len({method for method, _ in reachable}), len(reachable)]
    for word, count, real, noun in zip(headline.groups(), claimed, actual, ("host", "method", "route")):
        if count is None:
            findings.append(Finding(where, (
                f"counts `{word}` {noun}s in its headline and this row cannot read that as a "
                f"number. Write it as a word\n  up to ten, or widen `_TRANSPORT_NUMBERS` — an "
                f"unreadable count is an unchecked one."
            )))
        elif count != real:
            findings.append(Finding(where, (
                f"says `{word}` {noun}{'' if count == 1 else 's'} and the code reaches {real}. "
                f"Recount from the constants and the\n  `{TRANSPORT_OPENER}` calls; never "
                f"adjust the word to end a build."
            )))

    for name in sorted(urls):
        if name not in bullet:
            findings.append(Finding(where, (
                f"binds `{name}` to a URL and its first bullet does not name the constant. The "
                f"bullet lists them so a\n  fourth cannot arrive as an ordinary assignment."
            )))

    report.add(
        "transport promise",
        MECHANICAL,
        findings,
        f"{len(hosts)} host, {len({m for m, _ in reachable})} methods, {len(reachable)} routes, "
        f"as promised and as called",
        scanned=len(reachable),
    )


def check_export_request(report: Report) -> None:
    """The three fields of the export request that are DECISIONS, pinned to their values.

    **THE OTHER ELEVEN FIELDS ARE TRANSCRIPTION AND THIS ROW IGNORES THEM.**
    `server/tcg_export.py:Scope.model` is a body captured off the portal's own form submit,
    so most of it is a shape somebody copied and nothing here should have an opinion about
    it. Three of the fourteen are the operator's standing instruction, they are hoisted into
    `STANDING_FILTERS` for that reason, and this row is what makes the hoisting mean
    something.

    **WHY A BLOCKING ROW AND NOT A COMMENT, WHICH IS WHAT IT ALREADY HAD.** All three are
    invisible downstream. `ExcludeListos` is the worst of them: D65 measured `Photo URL`
    empty in all eleven exports, filtered AND unfiltered, so the axis leaves no trace in the
    file it narrows. A wrong value produces a clean join, a clean reconcile, a green
    `make check` and a mispriced listing, indefinitely — there is no run, no report and no
    later check that could ever disagree with it.

    **And the failure mode is specific rather than hypothetical.** `ExcludeListos` shipped
    `False` in D65 because the capture took whatever the checkbox happened to be set to that
    day, and the next re-capture of that body would paste over all fourteen fields the same
    way. This row is what turns that paste into a stopped commit.

    The finding names the INSTRUCTION rather than the literal, because somebody who has just
    changed the value already knows what the literal is.
    """
    findings: List[Finding] = []
    where = rel(EXPORT_MODULE)
    if not exists(EXPORT_MODULE):
        report.add("export request", MECHANICAL, [Finding(where, "does not exist")])
        return

    held = literals_from_module(EXPORT_MODULE).get("STANDING_FILTERS")
    if not isinstance(held, dict):
        findings.append(
            Finding(
                where,
                "no `STANDING_FILTERS` literal could be read. It is hoisted out of "
                "`Scope.model` precisely so this row can read it with `ast`; folding it back "
                "into the method body puts three standing instructions somewhere nothing "
                "checks.",
            )
        )
    else:
        for field, expected, why in EXPORT_STANDING:
            actual = held.get(field)
            if field not in held:
                findings.append(
                    Finding(where, f"`STANDING_FILTERS` no longer names {field}. {why}")
                )
            elif actual != expected:
                findings.append(
                    Finding(
                        where,
                        f"{field} is {actual!r} and must be {expected!r}. {why}",
                    )
                )

    live = literals_from_module(EXPORT_MODULE).get("LIVE_QUERY")
    if not isinstance(live, dict):
        findings.append(
            Finding(
                where,
                "no `LIVE_QUERY` literal could be read. The live-inventory download's two query "
                "parameters are hoisted for this row's sake (D104), exactly as the catalogue "
                "request's three fields are.",
            )
        )
    else:
        for field, expected, why in LIVE_QUERY_EXPECTED:
            if field not in live:
                findings.append(
                    Finding(where, f"`LIVE_QUERY` no longer names {field}. {why}")
                )
            elif live.get(field) != expected:
                findings.append(
                    Finding(
                        where,
                        f"`LIVE_QUERY`'s {field} is {live.get(field)!r} and must be "
                        f"{expected!r}. {why}",
                    )
                )

    # THE TWO REQUESTS MUST STAY TWO REQUESTS. They are different endpoints, different methods
    # and different documents — a POST of a filtered model against `downloadexportcsv`, and a
    # GET of everything against `DownloadMyExportCSV`. The likeliest future edit is somebody
    # noticing they both "fetch an export" and routing one through the other, which would make
    # the live path scoped again and silently empty (D104's measurement).
    source = read(EXPORT_MODULE)
    if "def fetch_live()" not in source:
        findings.append(
            Finding(
                where,
                "`fetch_live` no longer takes no arguments. It has no scope BECAUSE the live "
                "download has none — a parameter here is a scope creeping back onto a request "
                "the portal answers emptily when it is scoped wrong.",
            )
        )
    if "tcg_export_empty" not in source:
        findings.append(
            Finding(
                where,
                "`fetch_live` no longer refuses an empty export. That refusal is the only thing "
                "between a wrong request and a store-wide `live: 0`: this endpoint answers a "
                "request it cannot satisfy with a valid header and zero rows, measured.",
            )
        )

    report.add(
        "export request",
        MECHANICAL,
        findings,
        f"{len(EXPORT_STANDING)} catalogue filters and {len(LIVE_QUERY_EXPECTED)} live query "
        f"parameters, each at its measured value",
        scanned=len(EXPORT_STANDING) + len(LIVE_QUERY_EXPECTED),
    )


def _reason_labels() -> Optional[Set[str]]:
    """The screen's `REASON_LABELS` keys, or None if the block cannot be read."""
    if not exists(REVIEW_QUEUE_TSX):
        return None
    block = _REASON_LABELS_RE.search(read(REVIEW_QUEUE_TSX))
    if block is None:
        return None
    return set(re.findall(r"^\s*([a-z_][a-z0-9_]*)\s*:", block.group(1), re.M))


def _constant_for(module: str, value: str) -> Optional[str]:
    """The constant NAME a module binds to this reason string."""
    path = ROOT / module
    if not exists(path):
        return None
    try:
        tree = ast.parse(read(path))
    except SyntaxError:
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (isinstance(target, ast.Name)
                and isinstance(node.value, ast.Constant)
                and node.value.value == value):
            return target.id
    return None


def _emitted_names() -> Set[str]:
    """Every identifier LOADED anywhere in the production tree.

    A load and not a definition: `NO_POSITION = "no_position"` binds the name, and what says
    a reason can reach a card is somebody reading it back out. Attribute access counts, since
    the usual site is `routing.SET_AMBIGUOUS` from another module.

    **THE ROSTER TUPLES THEMSELVES ARE EXCLUDED, and leaving them in made this row vacuous.**
    `ROUTING_REASONS = (LOW_CONFIDENCE, ..., CARD_NOT_DETECTED, ...)` loads every reason name
    by construction, so the declaration alone satisfied the emission test for all thirteen —
    the row went green the moment the rosters landed, including for the one reason measured to
    have no producer at all. A check that is satisfied by the act of declaring the thing it
    checks is the vacuous green this file opens by warning about, and it was reachable here in
    the same commit that added the rosters.
    """
    declarations = {name for _, name in REASON_ROSTERS}
    names: Set[str] = set()
    for root in EMISSION_ROOTS:
        base = ROOT / root
        if not exists(base):
            continue
        for path in _walk(base, (".py",)):
            try:
                tree = ast.parse(read(path))
            except SyntaxError:
                continue
            skip: Set[int] = set()
            for node in tree.body:
                if (isinstance(node, ast.Assign) and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name)
                        and node.targets[0].id in declarations):
                    for element in ast.walk(node.value):
                        if isinstance(element, ast.Name):
                            skip.add(id(element))
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    if id(node) not in skip:
                        names.add(node.id)
                elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                    names.add(node.attr)
    return names


# The two tuples that publish the review vocabulary, and where each is declared.
REASON_ROSTERS = (
    ("pipeline/variant.py", "LADDER_REASONS"),
    ("pipeline/routing.py", "ROUTING_REASONS"),
)

# Where a reason may be handed to a card. The harness is excluded deliberately: a test that
# constructs a reason proves the string exists, never that the pipeline can produce it, and
# counting those would make every reason permanently "emitted".
EMISSION_ROOTS = ("pipeline", "server", "cli", "identify", "store", "codes")

# Reasons that are declared and deliberately have no producer: name -> the argument.
#
# THE SAME SHAPE AS `UNDISPATCHED` ABOVE, AND FOR THE SAME REASON. Without it the only ways
# to quiet this row are to delete a reason or to emit one artificially, and both land in a
# diff looking like tidying. An entry here is an argument a reviewer can disagree with.
#
# Self-cleaning: an entry naming a reason that IS emitted is stale and reported, and one
# naming nothing in the rosters is dangling and reported. A list that only grows stops
# being read.
UNEMITTED_REASONS: Dict[str, str] = {
    "card_not_detected": (
        "reachable in principle and has no producer in the repo today — recorded in "
        "docs/specs/capture-app.md, which argues it is not a defect in the screen and costs "
        "no more than a line in a lookup table. The screen must still label it, because a "
        "reason with no label draws the bare machine string on the day something first "
        "emits one."
    ),
}


def _roster(module: str, name: str) -> Optional[List[str]]:
    """One published reason tuple, resolved through the constants beside it.

    `literals_from_module` cannot read these: the tuple's members are NAMES, not string
    literals, which is the whole point of declaring it next to the constants rather than
    repeating their values. So the module's own `NAME = "value"` assignments are collected
    first and the tuple is resolved against them.
    """
    path = ROOT / module
    if not exists(path):
        return None
    try:
        tree = ast.parse(read(path))
    except SyntaxError:
        return None
    constants: Dict[str, str] = {}
    roster: Optional[List[str]] = None
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            constants[target.id] = node.value.value
        elif target.id == name and isinstance(node.value, ast.Tuple):
            roster = [
                constants[element.id]
                for element in node.value.elts
                if isinstance(element, ast.Name) and element.id in constants
            ]
    return roster


def _reason_emissions() -> Row:
    """Every published reason is in a roster, and every roster reason has a producer.

    `check_reason_codes` reconciles this vocabulary across the screen, docs/DESIGN.md and the
    constants — but only ever in one direction. It starts from a reason somebody published and
    asks whether the code defines it. Its own docstring records what that cannot see: a reason
    constant no doc and no screen mentions, invisible because the modules never said which of
    their constants are reasons.

    **The fix was in the code, not in a cleverer checker.** `pipeline/variant.py` declares
    fourteen module-level constants and six are reasons; the rest are finishes and ladder
    stages, spelled identically. Any rule for telling them apart is a guess, and the cheapest
    one is wrong about eight of fourteen in that file alone. So the modules publish
    `LADDER_REASONS` and `ROUTING_REASONS`, and this row is a set comparison rather than a
    heuristic — which is the bar this repo now holds a new row to (D16, amended 2026-09-05).

    Two things it asks that nothing asked before:

      the rosters ARE the vocabulary   a reason the screen labels and no roster names, or a
                                       roster entry no screen labels. Either way the code and
                                       the product disagree about what can happen to a card.
      a reason has a producer          a constant nothing assigns is dead vocabulary: it
                                       occupies a label, a doc line and a reader's attention,
                                       and no card can ever carry it.

    The harness is not a producer. A test constructing a reason proves the string exists, not
    that the pipeline can reach it, and counting tests would make every reason permanently
    emitted — the vacuous green this file exists to refuse.
    """
    findings: List[Finding] = []
    published: Set[str] = set()
    missing_roster = False
    for module, name in REASON_ROSTERS:
        roster = _roster(module, name)
        if roster is None:
            missing_roster = True
            findings.append(
                Finding(
                    module,
                    f"declares no `{name}` tuple this row can read. It is what lets the "
                    f"vocabulary be checked from the code outwards; without it only the "
                    f"doc-to-code direction is provable.",
                )
            )
            continue
        published.update(roster)

    labeled = _reason_labels()
    if labeled is None:
        findings.append(
            Finding(rel(REVIEW_QUEUE_TSX), "no `REASON_LABELS` block to read.")
        )
    elif not missing_roster:
        for reason in sorted(labeled - published):
            findings.append(
                Finding(
                    rel(REVIEW_QUEUE_TSX),
                    f"`{reason}` is labeled on the screen and named by no roster.\n"
                    f"  Add it to `LADDER_REASONS` or `ROUTING_REASONS` — whichever module "
                    f"produces it — so the code publishes the vocabulary it can emit.",
                )
            )
        for reason in sorted(published - labeled):
            findings.append(
                Finding(
                    rel(REVIEW_QUEUE_TSX),
                    f"`{reason}` is in a roster and the screen has no label for it.\n"
                    f"  The queue would draw the bare machine string the day something emits "
                    f"one, which is the outcome the label table exists to prevent.",
                )
            )

    emitted = _emitted_names()
    for module, name in REASON_ROSTERS:
        roster = _roster(module, name) or []
        for reason in roster:
            constant = _constant_for(module, reason)
            if constant is None or constant in emitted:
                if reason in UNEMITTED_REASONS and constant in emitted:
                    findings.append(
                        Finding(
                            "scripts/docs-audit.py",
                            f"`UNEMITTED_REASONS` still excuses `{reason}`, which now has a "
                            f"producer. Delete the entry — the argument it carries is spent.",
                        )
                    )
                continue
            if reason in UNEMITTED_REASONS:
                continue
            findings.append(
                Finding(
                    module,
                    f"`{reason}` is declared, labeled and documented, and nothing in "
                    f"{', '.join(EMISSION_ROOTS)} ever assigns it.\n"
                    f"  No card can carry it, so its label and its doc line describe a state "
                    f"the product cannot reach. Emit it, retire it, or argue it into "
                    f"`UNEMITTED_REASONS` with the reason.",
                )
            )
    for reason in sorted(UNEMITTED_REASONS):
        if reason not in published and not missing_roster:
            findings.append(
                Finding(
                    "scripts/docs-audit.py",
                    f"`UNEMITTED_REASONS` names `{reason}`, which is in no roster. A dangling "
                    f"exemption is one nobody can evaluate.",
                )
            )

    return Row(
        "reason emissions",
        MECHANICAL,
        findings,
        f"{len(published)} published reasons, {len(published) - len(UNEMITTED_REASONS)} with "
        f"a producer and {len(UNEMITTED_REASONS)} argued",
        scanned=len(published),
    )


def _reason_codes() -> Row:
    """The twelve review reasons, reconciled across the three places they are published.

    They are written down in three independent places and nothing compared them: the
    constants in `pipeline/variant.py` and `pipeline/routing.py`, the keys of
    `REASON_LABELS` in `app/src/ReviewQueue.tsx`, and the enumerated list in
    `docs/DESIGN.md`. That file names the failure itself — showing only a friendly label
    "creates a second vocabulary that nothing audits" — and until this row existed, the
    audit it was appealing to did not check the vocabulary either.

    Four reconciliations, each provable:

      a label with no constant   the screen renders a friendly label for a string the
                                 pipeline cannot emit. Dead code that reads as coverage.
      a documented reason with   the queue would draw the bare machine string the day
      no label                   routing first emits it, which is the outcome the two-size
                                 label rule exists to prevent.
      a label the doc omits      a vocabulary the screen has and the spec does not, which
                                 is the drift in the direction nobody notices.
      a wrong attribution        docs/DESIGN.md credits each reason to the ladder or to
                                 routing; a reason that moved between them without the doc
                                 following is a doc that is confidently wrong.

    **What this could not see, `reason emissions` below now does (2026-09-05).** The gap was a
    reason constant that no doc and no screen mentions: `self_named_strings` answers "is this
    string defined here" and not "which strings here are reasons", and every rule for telling
    them apart was a guess — `pipeline/variant.py` spells finishes, ladder stages and reasons
    identically, and eight of its fourteen constants are not reasons.

    **The fix was in the pipeline, not in a cleverer reader here.** `LADDER_REASONS` and
    `ROUTING_REASONS` publish the set, so the missing direction is a set comparison. This row
    is unchanged and still runs from the published vocabulary inwards; the two are
    complementary, and neither subsumes the other.
    """
    findings: List[Finding] = []
    documented, problem = design_reason_lists()
    if problem:
        findings.append(Finding("docs/DESIGN.md", problem))

    labels: Set[str] = set()
    if not exists(REVIEW_QUEUE_TSX):
        findings.append(Finding(rel(REVIEW_QUEUE_TSX), "does not exist"))
    else:
        block = _REASON_LABELS_RE.search(read(REVIEW_QUEUE_TSX))
        if block is None:
            findings.append(
                Finding(
                    rel(REVIEW_QUEUE_TSX),
                    "no `const REASON_LABELS = { ... }` block could be read. The screen's "
                    "half of this reconciliation is that map; if it was restructured, this "
                    "row has to learn the new shape.",
                )
            )
        else:
            labels = set(_LABEL_KEY_RE.findall(block.group(1)))

    defined = {module: self_named_strings(ROOT / module) for module in REASON_MODULES}
    everywhere = set().union(*defined.values()) if defined else set()

    for reason in sorted(labels):
        if reason not in everywhere:
            findings.append(
                Finding(
                    rel(REVIEW_QUEUE_TSX),
                    f"REASON_LABELS carries {reason!r}, which is not defined as a constant "
                    f"in {' or '.join(REASON_MODULES)}. Nothing can put it on screen.",
                )
            )
        if documented and reason not in documented:
            findings.append(
                Finding(
                    rel(REVIEW_QUEUE_TSX),
                    f"REASON_LABELS carries {reason!r}, which docs/DESIGN.md's enumerated "
                    f"list does not name.",
                )
            )

    for reason, module in sorted(documented.items()):
        if labels and reason not in labels:
            findings.append(
                Finding(
                    "docs/DESIGN.md",
                    f"{reason!r} is enumerated but has no entry in REASON_LABELS, so the "
                    f"review queue would render the raw string.",
                )
            )
        if reason not in everywhere:
            findings.append(
                Finding(
                    "docs/DESIGN.md",
                    f"{reason!r} is enumerated but is defined as a constant in neither "
                    f"{' nor '.join(REASON_MODULES)}.",
                )
            )
        elif reason not in defined.get(module, set()):
            actual = sorted(name for name, strings in defined.items() if reason in strings)
            findings.append(
                Finding(
                    "docs/DESIGN.md",
                    f"{reason!r} is attributed to {module} and is actually defined in "
                    f"{', '.join(actual)}.",
                )
            )

    return Row(
        "reason codes",
        MECHANICAL,
        findings,
        f"{len(documented)} enumerated, {len(labels)} labeled, all defined",
        scanned=len(documented),
    )
