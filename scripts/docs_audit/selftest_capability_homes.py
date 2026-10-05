"""Self-test cases, the capability homes row. Called by `selftest.self_test`.

Contract the row must meet (module `capability_homes`):
    home_findings(files, registry, allow) -> list of findings, each with `.message`
      files     {repo path: source text}, the fixture tree
      registry  [{"capability", "home": "identify/images.py:card_box_for",
                  "primitives": ("detect_card", "locate_card"),
                  "allowed_dirs": ("geometry/",)}]
      allow     [{"file", "primitive", "reason"}], a list that only shrinks
A finding for a stray call names the home function to call instead. A stale allow entry says "stale".
"""

from __future__ import annotations

try:
    from .capability_homes import home_findings
except ImportError:  # the row is not built yet: every arm goes red as "row missing"
    home_findings = None

_REG = [{
    "capability": "card box",
    "home": "identify/images.py:card_box_for",
    "primitives": ("detect_card", "locate_card"),
    "allowed_dirs": ("geometry/",),
}]
_HOME = (
    "import geometry\n\n"
    "def card_box_for(path, aspect=None):\n"
    "    return geometry.locate_card(path, aspect=aspect) or geometry.detect_card(path, aspect=aspect)\n"
)


def _msgs(found):
    return " | ".join(f.message for f in found)


def run(ok) -> None:
    print("\nthe capability homes row goes red on a stray call to a private primitive and stays green on the home")

    def arm(label, files, allow=(), want_fail=False, want_text=""):
        if home_findings is None:
            ok(False, label, "row missing: scripts/docs_audit/capability_homes.py has no home_findings")
            return
        found = home_findings(files, _REG, list(allow))
        if want_fail:
            ok(bool(found) and want_text in _msgs(found), label, _msgs(found) or "not flagged")
        else:
            ok(not found, label, _msgs(found))

    arm("a direct `detect_card` outside geometry/ is flagged and names `card_box_for`",
        {"identify/images.py": _HOME, "cli/x.py": "import geometry\nbox = geometry.detect_card(p)\n"},
        want_fail=True, want_text="card_box_for")
    arm("a direct `locate_card` outside geometry/ is flagged and names `card_box_for`",
        {"identify/images.py": _HOME, "cli/x.py": "from geometry import locate_card\nbox = locate_card(p)\n"},
        want_fail=True, want_text="card_box_for")
    arm("the same call inside geometry/ passes",
        {"identify/images.py": _HOME, "geometry/card_box.py": "def f(s):\n    return detect_card(s)\n"})
    arm("a call through `card_box_for` passes",
        {"identify/images.py": _HOME, "cli/x.py": "from identify import images\nbox = images.card_box_for(p)\n"})
    arm("a primitive called inside the home module but outside `card_box_for` is flagged",
        {"identify/images.py": _HOME + "\ndef other(p):\n    return geometry.locate_card(p)\n"},
        want_fail=True, want_text="card_box_for")
    arm("an allow entry for a call that no longer exists is stale",
        {"identify/images.py": _HOME, "cli/x.py": "x = 1\n"},
        allow=[{"file": "cli/x.py", "primitive": "detect_card", "reason": "old"}],
        want_fail=True, want_text="stale")
    arm("an allow entry for a call that still exists passes",
        {"identify/images.py": _HOME, "cli/x.py": "box = detect_card(p)\n"},
        allow=[{"file": "cli/x.py", "primitive": "detect_card", "reason": "slow path"}])
    arm("a comment, a docstring and a string naming `detect_card` pass",
        {"identify/images.py": _HOME,
         "cli/x.py": '"""Why `detect_card` is slow."""\n# detect_card(p) refuses\nmsg = "call detect_card(p)"\n'})
