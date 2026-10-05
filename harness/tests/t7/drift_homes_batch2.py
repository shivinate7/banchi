"""T7 group: one home per capability, the server, pipeline and identify copies that still agree (DEBT86).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). Each check is RED while its second copy
exists and goes green when the second copy calls the home. Source scans read the AST of the product
packages, never a comment or a docstring. Two copies are measured to disagree today, and a case
shows it: the box parsers' refusal codes, and the number key for a number that already carries its total.

No model, no network, no store.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Callable, Iterator, List, Tuple

from harness.tests import Checks

ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ("server", "pipeline", "store", "identify", "geometry", "cli", "codes")


def _trees() -> Iterator[Tuple[str, ast.AST]]:
    for package in PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            yield path.relative_to(ROOT).as_posix(), ast.parse(path.read_text(encoding="utf-8"))


def _tree(rel: str) -> ast.AST:
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"))


def _top_names(rel: str) -> set:
    """Module-level `def`, `class` and assigned names of one file."""
    names = set()
    for node in _tree(rel).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _hits(match: Callable[[str, ast.AST], bool]) -> List[str]:
    return [f"{rel}:{getattr(node, 'lineno', 0)}" for rel, tree in _trees() for node in ast.walk(tree) if match(rel, node)]


def _show(hits: List[str]) -> str:
    return "; ".join(hits[:14])


def check_transport_one_home(checks: Checks) -> None:
    """`tcg_export` and `order_transport` each define the same five transport helpers."""
    both = _top_names("server/tcg_export.py") & _top_names("server/order_transport.py")
    twice = sorted(both & {"_cookie", "_agent", "_open", "_check_status", "_NoRedirect"})
    checks.equal(twice, [], "transport helpers are defined in one module only")
    checks.ok("__getattr__" not in _top_names("server/order_transport.py"),
              "order_transport keeps no alias for its old `_open` name")


def check_box_parse_one_home(checks: Checks) -> None:
    """The codes route refuses a bad box under the code `refusal.require_box` names."""
    from server import codes_routes
    from server.refusal import require_box

    def code_of(fn, payload):
        try:
            fn(payload)
        except Exception as caught:  # noqa: BLE001 - the refusal's code is the datum
            return getattr(caught, "code", type(caught).__name__)
        return "accepted"

    def scan(payload):
        return codes_routes.do_codes_scan(payload, "/nonexistent-captures-root")

    for label, payload, want in (("box 0", {"box": 0}, "box_invalid"), ("box -1", {"box": -1}, "box_invalid"),
                                 ("box 'x'", {"box": "x"}, "box_invalid"), ("no box", {}, "box_required")):
        checks.equal(code_of(require_box, payload), want, f"{label}: the home refuses as {want}")
        checks.equal(code_of(scan, payload), want, f"{label}: the codes route refuses as the home does")
    checks.equal(code_of(require_box, {"box": 3}), "accepted", "box 3 is accepted")
    both = {"_require_box", "_require_to_box"} & _top_names("server/capture_server.py")
    checks.ok(len(both) < 2, "`_require_box` and `_require_to_box` are one parser with a field name",
              "both are defined in server/capture_server.py")
    checks.ok("_box_of" not in ast.unparse(_tree("server/codes_routes.py")),
              "codes_routes has no box parser of its own, not even an alias")


def check_clock_one_home(checks: Checks) -> None:
    """`send_routes._now/_iso/_parse` beside `pipeline_routes._now_iso`: one stamp, one home."""
    from datetime import datetime, timezone
    from store import clock

    stamp = clock.iso(datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
    checks.equal(stamp, "2026-01-02T03:04:05+00:00", "fixture: the two clocks write one stamp shape")
    names = {n.id for n in ast.walk(_tree("server/send_routes.py")) if isinstance(n, ast.Name)}
    twin = {"_now", "_iso", "_parse"} & (_top_names("server/send_routes.py") | names)
    checks.ok(not twin,
              "UTC-second stamp has one home: send_routes keeps no `_now/_iso/_parse`, not even an alias of `store/clock.py`",
              f"send_routes defines {sorted(twin)}")


def check_sku_cell_one_home(checks: Checks) -> None:
    """`str(row.get(SKU_COLUMN) or "").strip()` is written more than once."""
    pattern = re.compile(r"str\(\w+\.get\((?:tcgcsv\.)?SKU_COLUMN\) or ''\)\.strip\(\)")
    counts = [(rel, len(pattern.findall(ast.unparse(tree)))) for rel, tree in _trees()]
    found = [f"{rel} x{n}" for rel, n in counts if n]
    total = sum(n for _, n in counts)
    checks.ok(total <= 1, "the SKU cell read is written once", f"{total} copies: {_show(found)}")


def check_number_key_one_home(checks: Checks) -> None:
    """`capture_server._number_compare_key` and `identity_binding._read_number_key` fold a read pair
    two ways when the number already carries its own total; a hand `zfill(3)` sits beside `join_key`."""
    from pipeline import identity_binding
    from store import numbers

    strategy = numbers.NUMBER_AND_PRINTED_TOTAL
    for number, total, want in (("54", "132", "54/132"), ("054", "132", "54/132"), ("54/132", "132", "54/132"),
                                ("161", "159", "161/159"), ("", "132", None), ("54", "", None)):
        checks.equal(identity_binding._read_number_key(strategy, number, total), want,
                     f"Pokemon pair {number!r}/{total!r}: the home folds it to {want!r}")
    for number in ("54", "SV-054"):
        checks.equal(identity_binding._read_number_key("other", number, None), "54",
                     f"other-game {number!r}: the home folds it to its digits")
    checks.ok("_number_compare_key" not in ast.unparse(_tree("server/capture_server.py")),
              "capture_server keeps no number key of its own, not even an alias")
    zfills = _hits(lambda rel, n: isinstance(n, ast.Attribute) and n.attr == "zfill" and rel != "store/numbers.py")
    checks.equal(zfills, [], "no hand `zfill` outside `store/numbers.py`")


def check_on_hand_one_home(checks: Checks) -> None:
    """Inline `state not in TERMINAL_STATES` walks beside `master.Inventory.copies_on_hand`."""
    def inline(rel: str, node: ast.AST) -> bool:
        if rel == "store/master.py" or not isinstance(node, ast.Compare):
            return False
        right = node.comparators[0]
        name = getattr(right, "attr", getattr(right, "id", ""))
        return isinstance(node.ops[0], ast.NotIn) and name == "TERMINAL_STATES" and "state" in ast.unparse(node.left)

    checks.equal(_hits(inline), [], "no on-hand test written inline outside store/master.py")


def check_canceled_status_one_home(checks: Checks) -> None:
    """`pricearchive.CANCELED_STATUS` repeats the word `store/orders.py` declares; and
    `sku_name_contradictions` tests the literal 'sold' where `master.SOLD` exists."""
    word = _hits(lambda rel, n: isinstance(n, ast.Constant) and n.value == "canceled"
                 and rel in ("pipeline/pricearchive.py", "server/capture_server.py", "pipeline/orders.py"))
    checks.equal(word, [], "pricearchive does not restate the 'canceled' word `store/orders.py` declares")
    sold = _hits(lambda rel, n: isinstance(n, ast.Constant) and n.value == "sold"
                 and rel == "pipeline/sku_name_contradictions.py")
    checks.equal(sold, [], "sku_name_contradictions reads `master.SOLD`, never the literal")


def check_identify_constants_one_home(checks: Checks) -> None:
    """One edge cap and one sidecar suffix."""
    edge = _hits(lambda rel, n: isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and n.value.value == 1568
                 and rel.startswith(("geometry/", "identify/")) and isinstance(n.targets[0], ast.Name))
    checks.ok(len(edge) <= 1, "the 1568 edge cap is defined once (geometry.crop vs identify.images)", _show(edge))
    suffix = _hits(lambda rel, n: isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                   and n.targets[0].id == "SIDECAR_SUFFIX")
    checks.ok(len(suffix) <= 1, "SIDECAR_SUFFIX is defined once", _show(suffix))


def check_position_label_one_home(checks: Checks) -> None:
    """`pipeline_routes._position_label` re-derives `_Places.of`'s pooled-first label rule."""
    for node in ast.walk(_tree("server/pipeline_routes.py")):
        if isinstance(node, ast.FunctionDef) and node.name == "_position_label":
            calls = {getattr(c.func, "attr", getattr(c.func, "id", "")) for c in ast.walk(node) if isinstance(c, ast.Call)}
            checks.ok(not {"is_located", "place_text"} <= calls,
                      "`_position_label` is not a second renderer of the pooled-first rule",
                      "it calls is_located and place_text itself")
            return
    checks.ok(True, "`_position_label` is gone")


CHECKS = (check_transport_one_home, check_box_parse_one_home, check_clock_one_home, check_sku_cell_one_home,
          check_number_key_one_home, check_on_hand_one_home, check_canceled_status_one_home,
          check_identify_constants_one_home, check_position_label_one_home)
