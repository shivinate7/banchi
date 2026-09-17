#!/usr/bin/env python3
"""WHICH COMPONENT RENDERS THE THING, AND WHAT SELECTS IT.

A RENDERER. It writes nothing and gates nothing, so D18 does not reach it — the same
standing `scripts/map-view.py` has, and for the same reason: it may be as clever as it likes
because nothing downstream believes it.

WHAT IT IS FOR, and the defect that earned it. On 2026-09-17 a fix to `#/orders` was briefed
against `CopyMapView`. The screen the owner looks at renders `WalkGroups`. The three lines
that decide this are 1,000 apart in a 4,605-line file:

    Orders.tsx:3705   BuyerDetail passes  hidePicks={hasWalk}
    Orders.tsx:4018   {hidePicks || single || map.stops.length === 0 ? null : <CopyMapView …>}
    Orders.tsx:3716   <WalkGroups …> renders instead

The work was correct and invisible, and it cost a whole agent round. Nobody reads that
distance reliably, and a split would not fix it: an agent with `WalkGroups` in its own file
still would not know that `hidePicks` is what selects it. That is a RELATIONSHIP, not a
location, which is why this prints relationships.

IT IS DERIVED ON EVERY RUN AND NEVER STORED. A stored index is a second thing to keep true,
and the first time it drifted it would send an agent to the wrong component with more
confidence than no index at all.

WHAT IT CANNOT SEE, said out loud because a reader who trusts it further than this will be
wrong. There is no TypeScript parser in the standard library, so the spans come from
top-level declarations and the conditions from the text around a call site. A component
rendered through a variable, a map over a table of components, or a wrapper that takes one
as a prop is invisible to it. A condition spread over more lines than it reads is truncated.
Read it as the first place to look, never as proof that nothing else renders the thing.

    scripts/orient.py <file.tsx> [--name <Component>]
    scripts/orient.py --selftest
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional

ROOT = Path(__file__).resolve().parent.parent

#: A top-level declaration ends the one above it.
TOP = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:function|const|class|type|interface|enum)\s")
#: A component is a top-level function whose name is capitalised.
COMPONENT = re.compile(r"^(?:export\s+)?(?:default\s+)?function\s+([A-Z][A-Za-z0-9_]*)\s*[(<]")
#: How far back a condition may sit from the tag it guards.
LOOKBACK = 2


class Component(NamedTuple):
    name: str
    start: int
    end: int

    @property
    def lines(self) -> int:
        return self.end - self.start + 1


class Site(NamedTuple):
    line: int
    inside: Optional[str]
    condition: Optional[str]


def components(text: str) -> List[Component]:
    lines = text.splitlines()
    starts: List[tuple] = []
    for number, line in enumerate(lines, start=1):
        match = COMPONENT.match(line)
        if match:
            starts.append((number, match.group(1)))
    found: List[Component] = []
    for index, (number, name) in enumerate(starts):
        end = len(lines)
        for probe in range(number + 1, len(lines) + 1):
            if TOP.match(lines[probe - 1]):
                end = probe - 1
                break
        if index + 1 < len(starts):
            end = min(end, starts[index + 1][0] - 1)
        found.append(Component(name, number, end))
    return found


def owner_of(found: List[Component], line: int) -> Optional[str]:
    for component in found:
        if component.start <= line <= component.end:
            return component.name
    return None


def condition_for(lines: List[str], line: int, column: int) -> Optional[str]:
    """The text that decides whether this tag is drawn, if it sits near it.

    IT WALKS BACK BY BRACE DEPTH, not by proximity. The first version read the preceding
    lines as a flat window and handed `<Gamma />` the condition belonging to the CLOSED
    expression above it — a false relationship, which is the one output worse than none
    here. A tag is guarded only by an expression block still OPEN at the tag.
    """
    head = lines[line - 1][:column]
    window = "".join(lines[max(0, line - 1 - LOOKBACK):line - 1]) + head
    depth = 0
    opener = None
    for index in range(len(window) - 1, -1, -1):
        char = window[index]
        if char == "}":
            depth += 1
        elif char == "{":
            if depth == 0:
                opener = index
                break
            depth -= 1
    if opener is None:
        return None
    guard = re.sub(r"\s+", " ", window[opener + 1:]).strip()
    for marker, suffix in (("? null :", " ? … :"), ("?", " ? … :"), ("&&", " &&")):
        if marker in guard:
            before = guard.rsplit(marker, 1)[0].strip()
            if before and len(before) < 160:
                return before + suffix
    return None


def sites(text: str, found: List[Component], name: str) -> List[Site]:
    plain = text.splitlines()
    tag = re.compile(r"<" + re.escape(name) + r"[\s/>]")
    self_span = next((c for c in found if c.name == name), None)
    out: List[Site] = []
    for number, line in enumerate(plain, start=1):
        match = tag.search(line)
        if not match:
            continue
        if self_span and self_span.start <= number <= self_span.end:
            continue
        out.append(Site(number, owner_of(found, number),
                        condition_for(plain, number, match.start())))
    return out


def render(path: Path, only: Optional[str] = None) -> str:
    text = path.read_text()
    found = components(text)
    total = len(text.splitlines())
    rows = [c for c in found if only is None or c.name == only]
    if only is not None and not rows:
        names = ", ".join(c.name for c in found)
        return f"no component named `{only}` in {path}.\nThere are: {names}\n"

    width = max((len(c.name) for c in rows), default=4)
    out = [f"{path} — {total:,} lines, {len(found)} components", ""]
    for component in rows:
        out.append(f"  {component.name:<{width}}  {component.start}-{component.end}  "
                   f"({component.lines} lines)")
        for site in sites(text, found, component.name):
            where = f"{site.inside}:{site.line}" if site.inside else f":{site.line}"
            out.append(f"  {'':<{width}}    drawn by {where}")
            if site.condition:
                out.append(f"  {'':<{width}}      when  {site.condition}")
        if not sites(text, found, component.name):
            out.append(f"  {'':<{width}}    drawn by nothing in this file "
                       f"(exported, or reached through a variable)")
        out.append("")
    out.append("Derived on this run, never stored. It reads top-level declarations and the "
               "text around a call site,")
    out.append("so a component reached through a variable or a table is invisible to it. "
               "First place to look, not proof.")
    return "\n".join(out) + "\n"


def selftest() -> int:
    ok = True

    def check(label: str, got, want) -> None:
        nonlocal ok
        if got == want:
            print(f"  ok   {label}")
        else:
            ok = False
            print(f"  FAIL {label}\n       got  {got!r}\n       want {want!r}")

    sample = (
        "import x from 'y'\n"
        "function Alpha() {\n"
        "  return <div />\n"
        "}\n"
        "function Beta({ hide }: { hide: boolean }) {\n"
        "  return (\n"
        "    <div>\n"
        "      {hide || empty ? null : <Alpha />}\n"
        "      <Gamma />\n"
        "    </div>\n"
        "  )\n"
        "}\n"
        "function Gamma() {\n"
        "  return <span />\n"
        "}\n"
    )
    found = components(sample)
    check("it finds every component", [c.name for c in found], ["Alpha", "Beta", "Gamma"])
    check("a span ends at the next top-level declaration",
          [(c.start, c.end) for c in found], [(2, 4), (5, 12), (13, 15)])

    alpha = sites(sample, found, "Alpha")
    check("it names the component that draws it", [s.inside for s in alpha], ["Beta"])
    check("it reports the condition that suppresses it",
          [s.condition for s in alpha], ["hide || empty ? … :"])

    gamma = sites(sample, found, "Gamma")
    check("an unconditional draw reports no condition",
          [(s.inside, s.condition) for s in gamma], [("Beta", None)])
    check("a component does not count as drawing itself",
          sites(sample, found, "Beta"), [])

    # THE CASE THIS EXISTS FOR, against the real file.
    orders = ROOT / "app" / "src" / "Orders.tsx"
    if orders.exists():
        text = orders.read_text()
        real = components(text)
        names = {c.name for c in real}
        check("Orders.tsx: both of the confused components are found",
              {"CopyMapView", "WalkGroups"} <= names, True)
        copy_sites = sites(text, real, "CopyMapView")
        check("Orders.tsx: CopyMapView's draw is reported as conditional",
              any(s.condition and "hidePicks" in s.condition for s in copy_sites), True)
        walk_sites = sites(text, real, "WalkGroups")
        check("Orders.tsx: WalkGroups is drawn from more than one place",
              len(walk_sites) > 1, True)

    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", nargs="?", help="a .tsx file")
    parser.add_argument("--name", help="one component rather than all of them")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        return selftest()
    if not args.file:
        parser.print_help()
        return 2

    path = Path(args.file)
    if not path.exists():
        path = ROOT / args.file
    if not path.exists():
        print(f"no such file: {args.file}", file=sys.stderr)
        return 1
    sys.stdout.write(render(path, args.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
