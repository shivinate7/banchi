#!/usr/bin/env python3
"""ADD THE DECISION IDS A FILE CITES TO `governed_by` IN docs/map.py.

THIS IS A GENERATOR AND IT GATES NOTHING (D18). It is run by hand, or by an agent whose
commit `make docs-audit`'s `repo map` row has just refused. The row keeps its job unchanged:
it reads, it blocks, it never writes. This writes and never blocks. D18's seam list names
`docs/map.py -> governed_by` as the one permitted location, and the argument for it is in
that entry.

THE TWO SIDES READ ONE FUNCTION, WHICH IS THE WHOLE POINT. The row computes
`cited_decisions(module_path) - declared - component_governed_by` and this imports
`cited_decisions` from the row's own module rather than reimplementing it. A second
implementation would drift, and the first time it drifted the generator would write
something the gate then refused, which is worse than no generator: the remedy would be
telling the operator to do something that does not work.

STDLIB ONLY, AND IT SPLICES WITH `ast` (D18). The freshness side of this runs in the
pre-commit hook on a bare `python3`, so nothing here may need `make venv`. `ast` gives the
exact source span of each `governed_by` list, which is how the surrounding hand-written
prose in docs/map.py survives a rewrite untouched.

IT ONLY EVER ADDS. An id in `governed_by` that the file does not cite is not a defect this
can see — a person may have put it there deliberately, and the row does not complain about
it either, because the check is one-directional. Removing one is a judgement, so it stays a
person's.

    scripts/map-fix.py            what it would add, and to which entries. Writes nothing.
    scripts/map-fix.py --write    add them.
    scripts/map-fix.py --selftest its own cases, over a throwaway map.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "docs" / "map.py"

#: docs/map.py's own wrapping. Its `governed_by` lists are wrapped near this column.
WIDTH = 100


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _cited_decisions():
    """The audit row's own reader, imported rather than reimplemented."""
    audit = _load("_docs_audit_for_map_fix", ROOT / "scripts" / "docs-audit.py")
    return audit.cited_decisions


def _key(entry: int) -> int:
    return entry


def _sort_ids(ids) -> List[str]:
    return sorted(ids, key=lambda value: int(value[1:]))


def _render(ids: List[str], column: int) -> str:
    """One list literal, wrapped the way docs/map.py wraps them."""
    parts = [f'"{value}"' for value in ids]
    lines: List[str] = []
    current = "["
    for index, part in enumerate(parts):
        piece = part + ("," if index < len(parts) - 1 else "")
        candidate = current + piece if current == "[" else current + " " + piece
        if len(candidate) + column > WIDTH and current != "[":
            lines.append(current)
            current = " " * 1 + piece
        else:
            current = candidate
    lines.append(current + "]")
    if len(lines) == 1:
        return lines[0]
    pad = " " * (column + 1)
    return ("\n" + pad).join(line.lstrip() if index else line for index, line in enumerate(lines))


def _spans(source: str) -> Dict[Tuple[str, str], ast.AST]:
    """(component path, module name) -> the `governed_by` List node for that module."""
    tree = ast.parse(source)
    found: Dict[Tuple[str, str], ast.AST] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "COMPONENTS" not in targets or not isinstance(node.value, ast.List):
            continue
        for component in node.value.elts:
            if not isinstance(component, ast.Dict):
                continue
            path = _string_for(component, "path")
            modules = _value_for(component, "modules")
            if path is None or not isinstance(modules, ast.Dict):
                continue
            for key, entry in zip(modules.keys, modules.values):
                if not isinstance(key, ast.Constant) or not isinstance(entry, ast.Dict):
                    continue
                governed = _value_for(entry, "governed_by")
                if isinstance(governed, ast.List):
                    found[(path, str(key.value))] = governed
    return found


def _value_for(node: ast.Dict, name: str):
    for key, value in zip(node.keys, node.values):
        if isinstance(key, ast.Constant) and key.value == name:
            return value
    return None


def _string_for(node: ast.Dict, name: str):
    value = _value_for(node, name)
    return value.value if isinstance(value, ast.Constant) else None


def _offsets(source: str) -> List[int]:
    """Byte offset of the start of each 1-indexed line."""
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def plan(map_path: Path = MAP, root: Path = ROOT):
    """Every module entry that cites an id its `governed_by` does not carry."""
    cited_decisions = _cited_decisions()
    mapping = _load("_map_for_map_fix", map_path)
    work = []
    for component in mapping.COMPONENTS:
        path = component.get("path")
        owner = set(component.get("governed_by") or [])
        for name, entry in (component.get("modules") or {}).items():
            module_path = root / path / name
            if not module_path.exists():
                continue
            declared = set(entry.get("governed_by") or [])
            missing = cited_decisions(module_path) - declared - owner
            if missing:
                work.append((path, name, _sort_ids(declared | missing), _sort_ids(missing)))
    return work


def apply(work, map_path: Path = MAP) -> str:
    source = map_path.read_text()
    spans = _spans(source)
    offsets = _offsets(source)
    edits = []
    for path, name, full, _missing in work:
        node = spans.get((path, name))
        if node is None:
            raise SystemExit(f"no `governed_by` list found for {path}{name}")
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[node.end_lineno - 1] + node.end_col_offset
        edits.append((start, end, _render(full, node.col_offset)))
    for start, end, text in sorted(edits, reverse=True):
        source = source[:start] + text + source[end:]
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="apply the additions")
    parser.add_argument("--selftest", action="store_true", help="prove it on a throwaway map")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    work = plan()
    if not work:
        print("every module's `governed_by` already carries every id its file cites.")
        return 0

    for path, name, _full, missing in work:
        print(f"  {path}{name}  + {', '.join(missing)}")
    print(f"\n{len(work)} entr{'y' if len(work) == 1 else 'ies'}, "
          f"{sum(len(m) for _, _, _, m in work)} id(s).")

    if not args.write:
        print("\nPreview. `scripts/map-fix.py --write` adds them.")
        return 0

    MAP.write_text(apply(work))
    print("\nwritten. `make docs-audit` is what says it is right — this never gates (D18).")
    return 0


def selftest() -> int:
    """The rendering and the splice, over a map this test writes and throws away."""
    import tempfile

    ok = True

    # THE IDS HERE ARE COMPOSED, NEVER TYPED. `cited_decisions` reads every mapped file for
    # `D<n>`, and a fixture holding the literal string is a citation as far as it can tell —
    # this file's own `repo map` entry demanded six decisions it has nothing to do with the
    # first time this test was written. The same failure the binary-suffix list covers, one
    # register up: a citation is a thing a person wrote about a decision, not three bytes.
    def d(number: int) -> str:
        return "D" + str(number)

    def check(label: str, got, want) -> None:
        nonlocal ok
        if got == want:
            print(f"  ok   {label}")
        else:
            ok = False
            print(f"  FAIL {label}\n       got  {got!r}\n       want {want!r}")

    check("a short list stays on one line",
          _render([d(1), d(2)], 30), f'["{d(1)}", "{d(2)}"]')
    long = _render([d(n) for n in range(1, 30)], 40)
    check("a long list wraps", "\n" in long, True)
    check("every id survives the wrap",
          sorted(int(part.strip(' []"D,')) for part in long.replace("\n", " ").split(",")),
          list(range(1, 30)))
    check("ids sort numerically, not lexically",
          _sort_ids({d(9), d(100), d(21)}), [d(9), d(21), d(100)])

    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp)
        (tree / "pkg").mkdir()
        (tree / "pkg" / "one.py").write_text(f"# governed by {d(7)} and {d(42)}\n")
        fake = tree / "map.py"
        fake.write_text(
            "COMPONENTS = [\n"
            "    {\n"
            '        "path": "pkg/",\n'
            f'        "governed_by": ["{d(1)}"],\n'
            '        "modules": {\n'
            f'            "one.py": {{"does": "a thing", "governed_by": ["{d(7)}"]}},\n'
            "        },\n"
            "    },\n"
            "]\n"
        )
        work = plan(map_path=fake, root=tree)
        check("it finds exactly the cited id the map lacks",
              [(path, name, missing) for path, name, _full, missing in work],
              [("pkg/", "one.py", [d(42)])])
        written = apply(work, map_path=fake)
        check("the splice adds it",
              f'"governed_by": ["{d(7)}", "{d(42)}"]' in written, True)
        check("the splice leaves the prose alone", '"does": "a thing"' in written, True)
        check("the component's own id is not copied down",
              f'"{d(1)}"' in written.split("modules")[1], False)

        # A citation the OWNER entry already carries is not the module's to declare.
        (tree / "pkg" / "one.py").write_text(f"# governed by {d(1)} alone\n")
        check("an id the component already governs is not added",
              plan(map_path=fake, root=tree), [])

    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
