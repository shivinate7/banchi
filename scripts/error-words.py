#!/usr/bin/env python3
"""The error-state check `machine-words.spec.ts` cannot be: it reads loaded screens, so it never
sees a refusal. This reads the refusal templates themselves, at the source, and needs no browser.

WHAT IT READS. Every message a refusal carries to the screen word for word, in two places:
  - `server/*.py`: the message argument of `BadRequest`, `PipelineRefusal`, `ShippingRefusal`,
    `CodesRefusal`, `_refuse`, `_fail`, `FetchRefusal` and `PushFailed`.
  - `store/*.py` and `pipeline/*.py`: the message of every `raise <Class>(...)` where the class is
    an exception this repo defines. The dispatcher relays these with `str(exc)`.
  - `app/src/*.ts(x)`: the message argument of `new ServerError(...)`.
WHY THIS ONE (D196, D284). A mocked failing server over every route would prove the renderer
and miss most refusals, because most refusals need a specific press to fire. The template is the
one place every refusal is a literal.

WHAT IT REFUSES (per message): a backtick, a decision id, a repository path or file extension,
a word from `scripts/machine-words.json`, a snake_case token, an HTTP status or `JSON`,
exception text interpolated raw, a typed middle dot or bullet, and a first letter that is not a
capital. ONE SHRINKING LIST, `scripts/error-words-allow.json`: file -> message start -> reason.
A finding not listed is red. A listed entry that no longer matches is stale, and red.

    python3 scripts/error-words.py            # exit 1 on a finding or a stale entry
    python3 scripts/error-words.py --list     # print every finding, allow-listed or not
    python3 scripts/error-words.py --self-test
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOW_PATH = ROOT / "scripts" / "error-words-allow.json"
WORDS = json.loads((ROOT / "scripts" / "machine-words.json").read_text())

# name -> index of the message argument
PY_CTORS = {
    "BadRequest": 2, "PipelineRefusal": 2, "ShippingRefusal": 2, "CodesRefusal": 2,
    "_refuse": 2, "_fail": 2, "FetchRefusal": 1, "PushFailed": 1,
}
EXC_NAMES = {"exc", "err", "e", "error", "detail", "why", "refused"}

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


def flatten(node: ast.AST) -> str:
    """The literal text of a message expression. `{x}` becomes `\\x00`, a raw exception `\\x01`."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(str(v.value))
            elif isinstance(v, ast.FormattedValue):
                inner = v.value
                parts.append("\x01" if isinstance(inner, ast.Name) and inner.id in EXC_NAMES else "\x00")
        return "".join(parts)
    if isinstance(node, ast.BinOp):
        return flatten(node.left) + flatten(node.right)
    if isinstance(node, ast.IfExp):
        return flatten(node.body) + " " + flatten(node.orelse)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return flatten(node.func.value)
    return "\x00"


def python_findings(source: str) -> list[tuple[str, int, str]]:
    found = []
    for node in ast.walk(ast.parse(source)):
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
        text = flatten(arg)
        found += [(text, node.lineno, p) for p in problems(text)]
    return found


TS_CALL = re.compile(r"new ServerError\(\s*'[a-z_]+'\s*,\s*((?:'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`|\s|\+)+)")
TS_LIT = re.compile(r"'((?:[^'\\]|\\.)*)'|`((?:[^`\\]|\\.)*)`")


def ts_findings(source: str) -> list[tuple[str, int, str]]:
    found = []
    for m in TS_CALL.finditer(source):
        text = ""
        for lit in TS_LIT.finditer(m.group(1)):
            s = lit.group(1) if lit.group(1) is not None else re.sub(r"\$\{[^}]*\}", "\x00", lit.group(2))
            text += s.replace("\\u2019", "’")
        line = source.count("\n", 0, m.start()) + 1
        found += [(text, line, p) for p in problems(text)]
    return found


def exception_classes() -> set[str]:
    """Names of the exception classes store/ and pipeline/ define, subclasses included."""
    trees = [ast.parse(p.read_text()) for d in ("store", "pipeline") for p in sorted((ROOT / d).glob("*.py"))]
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
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
            continue
        f = node.exc.func
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
        idx = 1 if name == "SelectionError" else 0
        if name in classes and len(node.exc.args) > idx:
            text = flatten(node.exc.args[idx])
            found += [(text, node.lineno, p) for p in problems(text)]
    return found


def scan() -> list[tuple[str, int, str, str]]:
    out = []
    for path in sorted((ROOT / "server").glob("*.py")):
        rel = str(path.relative_to(ROOT))
        out += [(rel, line, text, p) for text, line, p in python_findings(path.read_text())]
    classes = exception_classes()
    for d in ("store", "pipeline"):
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
    return text.replace("\x00", "{}").replace("\x01", "{exc}")[:50]


def main() -> int:
    if "--self-test" in sys.argv:
        assert problems("Send a JSON body.") and problems("Box `x` is gone.") and problems("see decisions D42")
        assert problems("bad thing") == ["no capital"] and not problems("That box is full. Pick another.")
        assert python_findings("raise BadRequest(s, 'c', 'store_busy now')")
        assert ts_findings("throw new ServerError('c', 'Start it with `make server`.', 0)")
        print("error-words: self-test ok")
        return 0
    allow = json.loads(ALLOW_PATH.read_text()) if ALLOW_PATH.exists() else {}
    allow.pop("_about", None)
    found = scan()
    if "--list" in sys.argv:
        for f, line, text, p in found:
            print(f"{f}:{line}: [{p}] {key(text)!r}")
        return 0
    used, bad = set(), []
    for f, line, text, p in found:
        k = key(text)
        if k in allow.get(f, {}):
            used.add((f, k))
        else:
            bad.append(f"{f}:{line}: [{p}] {k!r}. Reword it, or list it in scripts/error-words-allow.json with the lane that owes it.")
    for f, msgs in allow.items():
        for k in msgs:
            if (f, k) not in used:
                bad.append(f"{f}: allow entry {k!r} matches nothing. Delete it.")
    print("\n".join(bad) if bad else "error-words: ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
