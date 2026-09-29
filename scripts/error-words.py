#!/usr/bin/env python3
"""The error-state check `machine-words.spec.ts` cannot be: it reads loaded screens, so it never
sees a refusal. This reads the refusal templates themselves, at the source, and needs no browser.

WHAT IT READS. Every message a refusal carries to the screen word for word, in three places:
  - `server/*.py`: the message argument of `BadRequest`, `PipelineRefusal`, `ShippingRefusal`,
    `CodesRefusal`, `_refuse`, `_fail`, `FetchRefusal` and `PushFailed`.
  - `store/*.py`, `pipeline/*.py` and `codes/*.py`: the message of every `raise <Class>(...)` where the class is
    an exception this repo defines. The dispatcher relays these with `str(exc)`.
  - `app/src/*.ts(x)`: the message of `new ServerError(...)` (any quote style) and of a
    `{ code: ..., message: ... }` object a screen builds by hand.
WHY THIS ONE (D196, D284). A mocked failing server over every route would prove the renderer
and miss most refusals, because most refusals need a specific press to fire. The template is the
one place every refusal is a literal.

WHAT IT REFUSES (per message): a backtick, a decision id, a repository path or file extension,
a word from `scripts/machine-words.json`, a snake_case token, an HTTP status or `JSON`, a typed
middle dot or bullet, a first letter that is not a capital, and EXCEPTION TEXT: `{exc}`,
`str(exc)`, `{e.args[0]}` or `type(...).__name__` inside a message. One relay is allowed: an
exception this repo defines, whose own raise sites this script reads, caught by name in an
`except` clause that lists only such classes. Name the variable `said` there, never `exc`.

ONE SHRINKING LIST, `scripts/error-words-allow.json`: file -> full message template -> reason.
A finding not listed is red. A listed entry that no longer matches is stale, and red. The list
only shrinks: `scripts/only_shrinks.py`, the one helper every offender list reads, refuses an
entry that the list at the merge-base with origin/main did not hold.

    python3 scripts/error-words.py            # exit 1 on a finding, a stale entry or growth
    python3 scripts/error-words.py --list     # print every finding, allow-listed or not
    python3 scripts/error-words.py --self-test
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOW_REL = "scripts/error-words-allow.json"
ALLOW_PATH = ROOT / ALLOW_REL
WORDS = json.loads((ROOT / "scripts" / "machine-words.json").read_text())

# name -> index of the message argument
PY_CTORS = {
    "BadRequest": 2, "PipelineRefusal": 2, "ShippingRefusal": 2, "CodesRefusal": 2,
    "_refuse": 2, "_fail": 2, "FetchRefusal": 1, "PushFailed": 1,
}
# Refusal classes defined under server/: relayed by name like the store/ and pipeline/ ones.
DIRS = ("store", "pipeline", "codes")  # the packages whose raise sites are read
SERVER_CLASSES = {"BadRequest", "PipelineRefusal", "ShippingRefusal", "CodesRefusal", "FetchRefusal", "PushFailed"}
EXC_NAMES = {"exc", "err", "e", "error", "refused"}

_DIRS = "|".join(re.escape(d) for d in WORDS["repoTopDirs"])
CHECKS = [
    ("backtick", re.compile(r"`")),
    ("decision id", re.compile(r"\b(?:D|DEBT)\d+\b")),
    ("repo path", re.compile(rf"\b(?:{_DIRS})/|\.(?:py|json|sqlite|md|jsonl)\b")),
    ("snake_case", re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")),
    ("http detail", re.compile(r"\bHTTP\b|\bJSON\b|\b[45]\d\d\b|Content-Length|traceId|\bmake (?:up|server|venv|dev|check|demo)\b")),
    ("typed dot", re.compile("[·•]")),
]
_WORD_RES = [
    (w, re.compile(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])" if re.fullmatch(r"[\w-]+", w) else re.escape(w), re.I))
    for w in WORDS["words"]
]


def problems(message: str) -> list[str]:
    out = [name for name, rx in CHECKS if rx.search(message)]
    out += [f"word '{w}'" for w, rx in _WORD_RES if rx.search(message)]
    if "\x01" in message:
        out.append("exception text")
    if message[:1].islower():
        out.append("no capital")
    return out


def is_exc_expr(node: ast.AST) -> bool:
    """`exc`, `str(exc)`, `repr(exc)`, `exc.args[0]`, `exc.message`, `type(x).__name__`."""
    if isinstance(node, ast.Name):
        return node.id in EXC_NAMES
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name) and f.id in ("str", "repr") and node.args:
            return is_exc_expr(node.args[0])
        return isinstance(f, ast.Name) and f.id == "type"
    if isinstance(node, ast.Subscript):
        return is_exc_expr(node.value)
    if isinstance(node, ast.Attribute):
        return node.attr in ("args", "message", "__name__") and (
            is_exc_expr(node.value) or isinstance(node.value, ast.Call)
        ) or is_exc_expr(node.value)
    return False


def flatten(node: ast.AST) -> str:
    """The literal text of a message expression. `{x}` becomes `\\x00`, exception text `\\x01`."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(str(v.value))
            elif isinstance(v, ast.FormattedValue):
                parts.append("\x01" if is_exc_expr(v.value) else "\x00")
        return "".join(parts)
    if isinstance(node, ast.BinOp):
        return flatten(node.left) + flatten(node.right)
    if isinstance(node, ast.IfExp):
        return flatten(node.body) + " " + flatten(node.orelse)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return flatten(node.func.value)
    return "\x01" if is_exc_expr(node) else "\x00"


def _handler_names(handler: ast.ExceptHandler) -> list[str]:
    t = handler.type
    elts = t.elts if isinstance(t, ast.Tuple) else [t] if t is not None else []
    return [e.id if isinstance(e, ast.Name) else e.attr if isinstance(e, ast.Attribute) else "?" for e in elts]


def _relay_ok(node: ast.AST, parents: dict, first_party: set[str]) -> bool:
    """True inside an `except` clause that catches only exceptions whose raise sites are read."""
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, ast.ExceptHandler):
            names = _handler_names(cur)
            return bool(names) and all(n in first_party for n in names)
        cur = parents.get(cur)
    return False


def _parents(tree: ast.AST) -> dict:
    return {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}


def _clean(text: str, relay_ok: bool) -> str:
    return text.replace("\x01", "\x00") if relay_ok else text


def python_findings(source: str, first_party: set[str] | None = None) -> list[tuple[str, int, str]]:
    first_party = (first_party if first_party is not None else set()) | SERVER_CLASSES
    tree = ast.parse(source)
    parents = _parents(tree)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        if name not in PY_CTORS:
            continue
        idx = 3 if name == "_fail" and isinstance(f, ast.Name) else PY_CTORS[name]  # send_routes._fail(dir, record, code, message, status)
        arg = node.args[idx] if len(node.args) > idx else next((k.value for k in node.keywords if k.arg == "message"), None)
        if arg is None:
            continue
        text = _clean(flatten(arg), _relay_ok(node, parents, first_party))
        found += [(text, node.lineno, p) for p in problems(text)]
    return found


# `new ServerError(<code>, <message>...)`, any quote style for the code, and `{ code: ..., message: ... }`.
_LIT = r"""'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|`(?:[^`\\]|\\.)*`"""
_MSG = rf"((?:{_LIT}|\s|\+)+)"
TS_CALL = re.compile(rf"new ServerError\(\s*(?:{_LIT}|[\w.]+)\s*,\s*{_MSG}")
TS_OBJ = re.compile(rf"\bcode:\s*(?:{_LIT}|[\w.]+)\s*,\s*message:\s*{_MSG}")
TS_LIT = re.compile(r"""'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\]|\\.)*)`""")


def ts_findings(source: str) -> list[tuple[str, int, str]]:
    found = []
    for rx in (TS_CALL, TS_OBJ):
        for m in rx.finditer(source):
            text = ""
            for lit in TS_LIT.finditer(m.group(1)):
                if lit.group(1) is not None:
                    s = lit.group(1)
                elif lit.group(2) is not None:
                    s = lit.group(2)
                else:
                    s = re.sub(r"\$\{[^}]*\}", "\x00", lit.group(3))
                text += s.replace("\\u2019", "’")
            line = source.count("\n", 0, m.start()) + 1
            found += [(text, line, p) for p in problems(text)]
    return found


def exception_classes() -> set[str]:
    """Names of the exception classes store/ and pipeline/ define, subclasses included."""
    trees = [ast.parse(p.read_text()) for d in DIRS for p in sorted((ROOT / d).glob("*.py"))]
    known: set[str] = set()
    for _ in range(4):
        for tree in trees:
            for n in ast.walk(tree):
                if isinstance(n, ast.ClassDef):
                    for b in n.bases:
                        base = b.id if isinstance(b, ast.Name) else b.attr if isinstance(b, ast.Attribute) else ""
                        if base.endswith(("Error", "Exception")) or base in known or base in (
                            "ValueError", "KeyError", "LookupError", "RuntimeError",
                        ):
                            known.add(n.name)
    return known


def raised_findings(source: str, classes: set[str]) -> list[tuple[str, int, str]]:
    tree = ast.parse(source)
    parents = _parents(tree)
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
            continue
        f = node.exc.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        idx = 1 if name == "SelectionError" else 0
        if name in classes and len(node.exc.args) > idx:
            text = _clean(flatten(node.exc.args[idx]), _relay_ok(node, parents, classes | SERVER_CLASSES))
            found += [(text, node.lineno, p) for p in problems(text)]
    return found


def scan() -> list[tuple[str, int, str, str]]:
    out = []
    classes = exception_classes()
    for path in sorted((ROOT / "server").glob("*.py")):
        rel = str(path.relative_to(ROOT))
        out += [(rel, line, text, p) for text, line, p in python_findings(path.read_text(), classes)]
    for d in DIRS:
        for path in sorted((ROOT / d).glob("*.py")):
            rel = str(path.relative_to(ROOT))
            out += [(rel, line, text, p) for text, line, p in raised_findings(path.read_text(), classes)]
    src = ROOT / "app" / "src"
    for path in sorted([*src.glob("*.ts"), *src.glob("*.tsx")]):
        if path.name == "demoServer.ts":
            continue
        rel = str(path.relative_to(ROOT))
        out += [(rel, line, text, p) for text, line, p in ts_findings(path.read_text())]
    return out


def key(text: str) -> str:
    """The whole message template. A prefix would let a later edit hide under an old entry."""
    return text.replace("\x00", "{}").replace("\x01", "{exc}")


def _only_shrinks():
    spec = importlib.util.spec_from_file_location("only_shrinks", ROOT / "scripts" / "only_shrinks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RULE = "error words"


def growth(head: dict) -> list[str]:
    """Entries HEAD holds that the list at the merge-base did not. The rules are
    `only_shrinks.growth`'s: a list born on this branch may hold its first entries."""
    helper = _only_shrinks()
    document, where, _, _ = helper.list_at_merge_base(ALLOW_REL, ROOT)
    base = {k: v for k, v in (document or {}).items() if k != "_about"} if isinstance(document, dict) else {}
    pairs = lambda d: [(RULE, f"{f}\x00{k}") for f, ks in d.items() for k in ks]  # noqa: E731
    rules = {RULE} if isinstance(document, dict) else None
    refused, _allowed = helper.growth(pairs(base), pairs(head), rules if rules else {RULE}, {RULE})
    if not isinstance(document, dict):
        return []  # no list at the merge-base: this branch gives it its birth, and `where` says so
    return [f"{g.identity.split(chr(0))[0]}: allow entry {g.identity.split(chr(0))[1][:60]!r} is not in the list at the merge-base ({where}). The list only shrinks." for g in refused]


def self_test() -> None:
    assert problems("Send a JSON body.") and problems("Box `x` is gone.") and problems("see decisions D42")
    assert problems("bad thing") == ["no capital"] and not problems("That box is full. Pick another.")
    assert python_findings("raise BadRequest(s, 'c', 'store_busy now')")
    assert ts_findings("throw new ServerError('c', 'Start it with `make server`.', 0)")
    # every gap the review named, planted red
    assert ts_findings('throw new ServerError("c", "Try `make up` now", 0)'), "double-quoted ServerError"
    assert ts_findings("throw new ServerError(`c`, `Try `+'the store_busy'+` now`, 0)"), "template code"
    assert ts_findings("const f = { code: 'x', message: 'It hit store_busy.' }"), "snake_case in a {code, message} object"
    assert ts_findings('const f = { code: "x", message: "See D42." }'), "double-quoted object message"
    planted = {
        "str(exc)": "try:\n    x()\nexcept OSError as exc:\n    raise BadRequest(s, 'c', str(exc))\n",
        "{exc}": "try:\n    x()\nexcept ValueError as exc:\n    raise BadRequest(s, 'c', f'Bad: {exc}')\n",
        "{e.args[0]}": "try:\n    x()\nexcept KeyError as e:\n    raise BadRequest(s, 'c', f'Missing {e.args[0]}')\n",
        "type(...).__name__": "try:\n    x()\nexcept Exception as exc:\n    raise BadRequest(s, 'c', f'Broke: {type(exc).__name__}')\n",
    }
    for what, code in planted.items():
        assert any(p == "exception text" for _t, _l, p in python_findings(code)), f"{what} not caught"
    relay = "try:\n    x()\nexcept master.BadSections as said:\n    raise BadRequest(s, 'c', f'{said}. Try again.')\n"
    assert not python_findings(relay, {"BadSections"}), "a first-party relay must stay green"
    bare = "try:\n    x()\nexcept master.BadSections as exc:\n    raise BadRequest(s, 'c', str(exc))\n"
    assert not python_findings(bare, {"BadSections"}), "str(exc) of a first-party class stays green"
    assert python_findings(bare, set()), "the same str(exc) is red when the class is not one this repo defines"
    print("error-words: self-test ok")


def main() -> int:
    if "--self-test" in sys.argv:
        self_test()
        return 0
    allow = json.loads(ALLOW_PATH.read_text()) if ALLOW_PATH.exists() else {}
    allow.pop("_about", None)
    found = scan()
    if "--list" in sys.argv:
        for f, line, text, p in found:
            print(f"{f}:{line}: [{p}] {key(text)[:90]!r}")
        return 0
    used, bad = set(), []
    for f, line, text, p in found:
        k = key(text)
        if k in allow.get(f, {}):
            used.add((f, k))
        else:
            bad.append(f"{f}:{line}: [{p}] {k[:90]!r}. Reword it, or list it in {ALLOW_REL} with the lane that owes it.")
    for f, msgs in allow.items():
        for k in msgs:
            if (f, k) not in used:
                bad.append(f"{f}: allow entry {k[:60]!r} matches nothing. Delete it.")
    bad += growth(allow)
    print("\n".join(bad) if bad else "error-words: ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
