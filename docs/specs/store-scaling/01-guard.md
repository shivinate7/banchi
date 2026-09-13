# Item 1 — the `unscoped walk` row

This is one of the eight item files under `docs/specs/store-scaling/`, described by
`00-phases.md`. Read that file's "Phase 0" section first if you have it; this file is
self-contained regardless. Your only write for this item is `scripts/docs-audit.py`
(one new function, one new call in `audit()`, one new self-test block) — do not touch
`docs/specs/store-scaling.md`, `CLAUDE.md`, `scripts/checks.py`, or any file under `app/`,
`server/`, `store/`, `cli/` for this item. This item is a guard, not a fix.

## Goal and done-when

**Goal:** stop a future PR from adding a new full-table read of `inventory.cards` — or
quietly removing one from the allowlist without saying so — by making `make docs-audit`
fail the commit when it happens.

**Done when:** `python3 scripts/docs-audit.py --json` contains a row named
`"unscoped walk"` with `"scanned": 12`, zero findings on a clean tree; `--self-test`
passes two new cases (a synthetic new site fails the row, a synthetic stale-allowlist
entry fails the row); and `check_dispatch` (already in the file) confirms the new function
is called from `audit()` — you don't have to prove this by hand, it fails on its own if
you forget the call.

## Depends on / conflicts with

- **Depends on nothing.** This is Phase 0 in `00-phases.md` and runs alone, first, before
  any other item opens a PR.
- **Every later item (2, 4, 7, 8) edits this file's allowlist constant** in the same PR
  that removes a full-table read — they lower `UNSCOPED_WALK_ALLOWED` (the name you give
  the allowlist constant; see Steps) and delete the matching entries. This item's job is
  only to make that constant exist and be enforced; do not pre-populate future removals.
- **No conflict with PR #333** (the `readings` table) — different files.

## Read first

- `docs/specs/store-scaling.md` §3 item 1 and §4 (the allowlist table) — the source of
  the twelve sites and the one exception this file adds.
- `docs/specs/store-scaling/00-phases.md`, "Where each item's decisions came from" —
  states the owner's ruling that `GET /inventory` stays on the allowlist permanently even
  though `docs/specs/store-scaling.md` §4's own table says "Removed by: item 2". **That
  table is stale on this one point and you do not edit it** — your file (this one) is the
  authority for what the guard actually enforces; `00-phases.md`'s own table already
  reflects the correction (its Phase-0 row says "`do_inventory` and `to_payload` stay by
  the owner's word").
- `scripts/docs-audit.py:13538` `check_rule_enforcement` — the "pinned number, moves only
  down, mutation-proofed" pattern this row's allowlist count copies.
- `scripts/docs-audit.py:9836` `check_storage_keys` — the "reconcile code against a
  roster, in both directions, with `scanned=`" pattern this row's allowlist copies from
  the other side (roster → code instead of code → roster is symmetric here since there is
  no markdown roster, only the constant in this same file).
- `scripts/docs-audit.py:2671` `_history_readers` — the exact `ast.walk` shape to copy for
  finding calls inside functions and naming which function owns each call.
- `scripts/docs-audit.py:15548` `audit()` — where every check is dispatched; `check_dispatch`
  fails the commit if you define a function here and never call it.
- `scripts/docs-audit.py:12737` `check_subject_counts` — why every `report.add(...)` call
  needs `scanned=<n>` and what happens if you omit it (a distinct "no count declared"
  finding, always failing, never silently green).
- `store/rows.py:213-266` — `Rows.where(**equals)`, `Rows.select(columns, **equals)`,
  `Rows.distinct(column)`. `Rows` is a `MutableMapping`, so `.values()`/`.items()` take no
  arguments ever (they are the ABC's own methods) and always materialise every row.
  `distinct()` takes no filter parameter at all — every call is a full-column scan by
  construction. `select()` takes `**equals`; a call with keywords is scoped, a call with
  none is not. `where()` is never flagged (see "Do not touch" below) because the plan's
  own text names only `.values()`, `.items()`, `to_payload()`, and unfiltered
  `select`/`distinct` — not `where`.

## Steps

### 1. Add the pinned constant and the allowlist, near the other pinned constants

Put this near `HARD_RULE_FLOOR`/`PROSE_ONLY_EXPECTED` (around line 13432) or in a new
section just above your new function — either is fine, but keep the constant and the
function that reads it in the same file section so the next reader sees both together.

```python
# THE ALLOWLIST IS KEYED BY (path, function, shape) AND NEVER BY LINE NUMBER, because a
# line number moves the day somebody edits an unrelated docstring above it and the guard
# would then fail on a site that did not change. `shape` disambiguates a function that
# makes more than one kind of unscoped call (store/master.py's `to_payload` calls
# `.items()` on `self.cards`, `self.boxes` AND `self.listings` — only the `cards` one is
# on this list, matched by `shape="items"` restricted to the `.cards` chain in the
# matcher itself, never by which `.items()` call comes first in the function body).
#
# TAKEN 2026-09-12, docs/specs/store-scaling.md §4, PLUS ONE. `do_inventory`'s
# `to_payload()` call is kept here PERMANENTLY, on the owner's word recorded in
# docs/specs/store-scaling/00-phases.md ("do_inventory is kept, unused, on the
# allowlist") — §4's own table says "Removed by: item 2" for that row and that line is
# stale; the correction lives here and in 00-phases.md, not in store-scaling.md itself.
#
# THIS COUNT MAY ONLY GO DOWN, same rule as `PROSE_ONLY_EXPECTED` above: an item that
# removes a full-table read deletes its tuple from UNSCOPED_WALK_ALLOWED and lowers
# UNSCOPED_WALK_EXPECTED in the SAME commit, or the row reports a stale allowlist entry
# (site not found) rather than silently shrinking. An item that cannot yet remove its
# site for some reason must not touch the count.
UNSCOPED_WALK_ALLOWED: FrozenSet[Tuple[str, str, str]] = frozenset({
    # (path relative to ROOT, enclosing function name, shape)
    ("server/capture_server.py", "do_inventory", "to_payload"),   # kept permanently — owner's word
    ("server/capture_server.py", "_release_plan", "items"),
    ("server/capture_server.py", "do_search", "values"),
    ("server/capture_server.py", "_boxes_named", "distinct"),
    ("server/capture_server.py", "do_boxes", "distinct"),
    ("server/pipeline_routes.py", "_box_names", "select"),
    ("server/pipeline_routes.py", "_unsent_ledger", "distinct"),
    ("server/pipeline_routes.py", "_on_hand_by_run", "select"),
    ("server/pipeline_routes.py", "do_pipeline_value", "values"),
    ("store/master.py", "to_payload", "items"),
    ("store/master.py", "counts", "select"),
    ("cli/resolve.py", "box_views", "values"),
})
UNSCOPED_WALK_EXPECTED = 12
```

`FrozenSet` needs `FrozenSet` imported from `typing` — check the existing `from typing
import ...` line near the top of the file (around line 74) and add `FrozenSet` to it if
it is not already there.

### 2. Write the pure scanner, modelled on `_history_readers` (line 2671)

Add this function anywhere above `check_dispatch` (line 12620) — a reasonable spot is
right after `_history_readers`/`check_sole_reader`, since both are "walk `.py` files
looking for a call shape on the store" functions, or immediately before your new
`check_unscoped_walk` function. Keep it a **pure** function (no `Report` argument) so
`--self-test` can drive it directly against a synthetic fixture, matching the convention
in `mechanism_refs`, `_payload_keys`, `_history_readers` etc.

```python
# The three roots the plan names, in the order they are read. server/ is a FLAT
# directory (no subpackages as of 2026-09-12 — capture_server.py, pipeline_routes.py,
# codes_routes.py, order_transport.py, ports.py, shipping_routes.py, tcg_export.py,
# tcg_import.py), so `_walk(ROOT / "server", (".py",))` is exactly "server/*.py" and
# never needs to recurse into a package that does not exist yet. `store/master.py` and
# `cli/resolve.py` are named as single files because the plan is explicit that only
# `master.py` (the Inventory/Card schema) is in scope inside `store/` — `store/rows.py`,
# `store/db.py` and `store/queues.py` all touch rows too, but not `inventory.cards`
# directly, and widening the walk to all of `store/` would flag `Rows` itself defining
# `.values()`/`.items()` as their OWN implementation, which is not a call site at all.
_UNSCOPED_WALK_ROOTS: Tuple[Path, ...] = (
    ROOT / "server",
)
_UNSCOPED_WALK_SINGLE_FILES: Tuple[Path, ...] = (
    ROOT / "store" / "master.py",
    ROOT / "cli" / "resolve.py",
)

# The three method names that always materialise every row when called on something
# ending in `.cards` (`Rows` is a `MutableMapping`; these three take no filter argument
# under any Rows signature — see store/rows.py:213-266), plus `select`, which only
# materialises everything when called with NO keyword arguments (a keyword is a filter:
# `equals` in `Rows.select`).
_UNSCOPED_METHODS = frozenset({"values", "items", "distinct"})


def _enclosing_functions(tree: ast.AST) -> Dict[int, str]:
    """line number -> the name of the FunctionDef/AsyncFunctionDef that contains it.

    Copied from `_history_readers`'s own inline dict-building loop (line ~2689) rather
    than imported, because that loop is not split into its own function there — if a
    future session factors it out, prefer that shared helper over keeping two copies.
    """
    owner: Dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                line = getattr(inner, "lineno", None)
                if line is not None:
                    owner.setdefault(line, node.name)
    return owner


def _cards_chain(node: ast.AST) -> bool:
    """Does this call's receiver end in `.cards`? `inventory.cards`, `self.cards`,
    `store.read().inventory.cards` — any depth, only the last hop matters."""
    return isinstance(node, ast.Attribute) and node.attr == "cards"


def _inventory_like(node: ast.AST) -> bool:
    """Does this call's receiver look like an `Inventory` instance? Heuristic, and named
    as one: matches a bare `inventory` name or a `.inventory` attribute, which is the
    variable name this repo uses everywhere an `Inventory` is bound (`Store().read().inventory`,
    `self.inventory`). This is what keeps `to_payload()` from also matching
    `book.to_payload()` / `entry.to_payload()` elsewhere in the same files, which are a
    different class's method of the same name."""
    if isinstance(node, ast.Name):
        return node.id == "inventory"
    if isinstance(node, ast.Attribute):
        return node.attr == "inventory"
    return False


def unscoped_walk_sites(paths: Sequence[Path]) -> List[Tuple[str, int, str, str]]:
    """Every call in `paths` that materialises the whole `inventory.cards` collection.

    Returns (path relative to ROOT, line number, enclosing function name, shape) tuples,
    where shape is one of "values", "items", "distinct", "select", "to_payload". Pure —
    no Report, no filesystem side effects beyond reading `paths` — so `--self-test` can
    hand it a synthetic fixture file and assert on the return value directly, the same
    shape `_payload_keys` and `mechanism_refs` are tested in already.

    WHAT THIS CANNOT SEE, and it says so rather than pretending completeness:
    `store/rows.py:177`'s degradation — a `where()`/`select()` call that LOOKS scoped but
    answers from a Python-side list because an earlier call in the same request already
    materialised everything — is invisible here. This function reads one file at a time
    with no notion of a request's call order, so it cannot tell a `where()` that hits the
    index from one that is quietly a full scan because of what ran before it in the same
    handler. Item 2 removes the degradation itself; this row is a static shape reader and
    will keep reporting a `where()`-only handler as clean before and after that fix,
    correctly, because the shape on the page never changes — only what it costs at
    runtime does.
    """
    sites: List[Tuple[str, int, str, str]] = []
    for path in paths:
        if not exists(path):
            continue
        try:
            tree = ast.parse(read(path))
        except SyntaxError:
            continue
        owner = _enclosing_functions(tree)
        where = rel(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            fname = owner.get(node.lineno, "<module>")
            if func.attr in _UNSCOPED_METHODS and _cards_chain(func.value):
                sites.append((where, node.lineno, fname, func.attr))
            elif func.attr == "select" and _cards_chain(func.value) and not node.keywords:
                sites.append((where, node.lineno, fname, "select"))
            elif func.attr == "to_payload" and _inventory_like(func.value):
                sites.append((where, node.lineno, fname, "to_payload"))
    return sites
```

**Why `select` is `elif` and not folded into the `_UNSCOPED_METHODS` set:** the other
three methods (`values`/`items`/`distinct`) are unconditionally full scans, but `select`
needs the extra `not node.keywords` test — `inventory.cards.select(("box",), box=None)`
inside `_boxes_named` (server/capture_server.py, around line 8348) is a real, scoped call
right next to the unscoped `distinct("box")` call one line above it, and it must NOT be
flagged. If you fold `select` into the set and add the keyword check as a second `if`
inside the loop, you get the same result — either shape is fine, but do not drop the
keyword check, since that is the one line standing between this row and a false positive
on a real, already-scoped call in a function you are not supposed to touch.

### 3. Write the check function

Modelled directly on `check_storage_keys` (line 9836) for the "reconcile code against a
constant, three kinds of disagreement, one `report.add`" shape, and on
`check_rule_enforcement` (line 13538) for "a pinned count that may only move down, and a
non-vacuity floor is not needed here because the list can never legitimately go to zero
— `do_inventory` never leaves it".

```python
def check_unscoped_walk(report: Report) -> None:
    """Every full-table read of `inventory.cards`, against an allowlist that starts at
    the 2026-09-12 census and may only shrink.

    docs/specs/store-scaling.md §0: almost every non-capture handler in `server/`
    materialises the whole `cards` table and then does per-card work over it, and at
    50,000 cards several of those routes cost seconds rather than milliseconds. §3 item 1
    is this row: land the guard BEFORE any of the six PRs that remove a full-table read,
    so each of them is checked against something rather than landing with no reader — the
    exact shape `docs/GATES.md` step 7's own finding names, one register down.

    THREE KINDS OF DISAGREEMENT, exactly `check_storage_keys`'s shape:
      - a site this file scans and finds, not on the allowlist: a NEW full-table read.
      - an allowlist entry naming a (path, function, shape) this scan does not find: a
        REMOVED site whose allowlist entry was not deleted in the same commit — this is
        the failure mode item 1's own spec text calls out by name ("a removed site is
        removed from the list in the same PR or the row reports a stale allowlist entry").
      - the allowlist's length disagreeing with `UNSCOPED_WALK_EXPECTED`: the same pinned-
        number discipline `check_rule_enforcement` uses, so a mutation cannot silently
        drop an entry and leave the printed count claiming coverage it no longer has.

    `do_inventory`'s `to_payload()` call is the one entry that can never be removed: the
    owner ruled (docs/specs/store-scaling/00-phases.md) that `GET /inventory` stays on the
    wire, unused, rather than being deleted once item 2 lands a scoped `GET
    /inventory/<box>`. Nothing in this function treats it specially — it is simply an
    entry nothing will ever delete, which is why `UNSCOPED_WALK_EXPECTED`'s floor never
    reaches zero.

    WHAT IT CANNOT SEE: `store/rows.py:177`'s runtime degradation (a call that reads
    scoped in the source and answers unscoped at runtime because an earlier call in the
    same request already loaded everything) — see `unscoped_walk_sites`'s own docstring,
    which item 2 is what actually removes. This row reads Python source shapes, never
    request traces.
    """
    found = set(unscoped_walk_sites(list(_UNSCOPED_WALK_ROOTS[0].glob("*.py") if False else
                                          _walk(_UNSCOPED_WALK_ROOTS[0], (".py",)))
                                     + list(_UNSCOPED_WALK_SINGLE_FILES)))
    allowed = UNSCOPED_WALK_ALLOWED
    findings: List[Finding] = []

    for path, line, fname, shape in sorted(found):
        if (path, fname, shape) not in allowed:
            findings.append(Finding(
                f"{path}:{line}",
                f"`{fname}` calls `.{shape}(...)` on a collection that ends in "
                f"`.cards` (or `to_payload()` on an `Inventory`), materialising every "
                f"row in the store.\n"
                f"  If this is a genuine new full-table read, either scope it — a "
                f"`where(...)`/`select(..., **filter)` with an index, or a per-box read "
                f"through `records_in` — or add `(\"{path}\", \"{fname}\", \"{shape}\") "
                f"to `UNSCOPED_WALK_ALLOWED` and raise `UNSCOPED_WALK_EXPECTED` by one, "
                f"with the reason in the commit message. docs/specs/store-scaling.md §0 "
                f"is why this matters: every one of these costs proportionally more as "
                f"the store grows, and none of it shows up until it does.",
            ))

    scanned_keys = {(path, fname, shape) for path, _, fname, shape in found}
    for path, fname, shape in sorted(allowed):
        if (path, fname, shape) not in scanned_keys:
            findings.append(Finding(
                path,
                f"the allowlist names `{fname}` (`.{shape}(...)`) and this scan finds no "
                f"such call there any more.\n"
                f"  Either the function moved to a shape this reader does not recognise, "
                f"or a full-table read was genuinely removed and the allowlist entry was "
                f"not deleted with it. Delete the entry and lower "
                f"`UNSCOPED_WALK_EXPECTED` in the same commit, or say why the shape "
                f"changed and update the tuple.",
            ))

    if len(allowed) != UNSCOPED_WALK_EXPECTED:
        findings.append(Finding(
            "scripts/docs-audit.py -> UNSCOPED_WALK_ALLOWED",
            f"has {len(allowed)} entries where {UNSCOPED_WALK_EXPECTED} are pinned. The "
            f"count is the plan's progress meter (docs/specs/store-scaling.md §3): raise "
            f"`UNSCOPED_WALK_EXPECTED` only alongside a NEW site you are deliberately "
            f"keeping (say why), and lower it in the same commit that deletes a site the "
            f"tree no longer has.",
        ))

    report.add(
        "unscoped walk",
        MECHANICAL,
        findings,
        f"{len(found)} full-table reads of inventory.cards found, "
        f"{len(allowed)} allowed (pinned at {UNSCOPED_WALK_EXPECTED})",
        scanned=len(found),
    )
```

**Fix the sloppy one-liner in step 3 above before you commit it** — it was written that
way here only to show the two roots being combined; write it plainly:

```python
    server_files = _walk(_UNSCOPED_WALK_ROOTS[0], (".py",))
    found = set(unscoped_walk_sites(server_files + list(_UNSCOPED_WALK_SINGLE_FILES)))
```

Confirm `_walk` is visible at this point in the file (it is defined at line 340, well
before both `check_storage_keys` at 9836 and `check_rule_enforcement` at 13538 — anywhere
after line 340 can call it) and that it already resolves through `--staged` mode's index
correctly (see `_walk`'s own docstring at line 340) — you do not need to pass
`staged_only` into this check; every other pure code-scanning row in this file (e.g.
`check_server_concurrency`, `check_claim_decode`) reads the same way and stays correct
under `--staged` for free because `read()`/`exists()`/`_walk()` all consult the staged
index when `enter_staged_mode()` has run.

### 4. Register it in `audit()`

At `scripts/docs-audit.py:15548`, add one line. Place it near the other single-purpose
code-scanning rows — right after `check_shell_substitution(report)` and before
`check_rule_enforcement(report)` is fine, or anywhere before the two lines at the very end
(`check_dispatch(report)` and, if staged, `check_coupling`; `check_subject_counts` must
stay last). Concretely:

```python
    check_identifier_spelling(report)
    check_shell_substitution(report)
    check_unscoped_walk(report)          # <-- new
    check_rule_enforcement(report)
    check_dispatch(report)
```

Do not put it after `check_dispatch(report)` — `check_dispatch` reconciles every function
defined against every function called, reading the file's OWN source, so it will
correctly catch a forgotten call regardless of where you place it, but `check_dispatch`
and `check_subject_counts` must remain the last two calls (the second reads the whole
`report.checks` list built so far, per their own comments in `audit()`).

### 5. Add the two self-test mutation arms

Find `self_test()` (line 13749). Add a new block anywhere after the existing checks — a
natural spot is right after the block that tests `check_rule_enforcement`'s helpers
(search for `PROSE_ONLY_EXPECTED` inside `self_test()`, or just append before the
function's final `return`/print-summary lines). Model the `tempfile.TemporaryDirectory()`
+ single fixture file + assert-on-return-value shape used at line 14046
(`module = Path(tmp) / "sample.py"`) — do not spin up a fake `server/` tree; call
`unscoped_walk_sites` directly against one synthetic file.

```python
    print("\nunscoped walk: the matcher, against synthetic fixtures")
    with tempfile.TemporaryDirectory() as tmp:
        # Arm (a): a NEW unscoped call must be found and reported as not-on-the-allowlist.
        fixture = Path(tmp) / "fixture_new_site.py"
        fixture.write_text(
            "def do_something_new():\n"
            "    inventory = Store().read().inventory\n"
            "    for card in inventory.cards.values():\n"
            "        touch(card)\n",
            encoding="utf-8",
        )
        sites = unscoped_walk_sites([fixture])
        ok(
            any(fname == "do_something_new" and shape == "values"
                for _, _, fname, shape in sites),
            "a new `.values()` call on `inventory.cards` is found by the scanner",
            str(sites),
        )

        # Arm (b): a call the scanner does NOT recognise as unscoped — a filtered
        # `select(...)` with a keyword — must not appear, proving the keyword check
        # actually narrows `select` and does not just always fire.
        fixture2 = Path(tmp) / "fixture_scoped_select.py"
        fixture2.write_text(
            "def do_scoped():\n"
            "    for key, row in inventory.cards.select((\"box\",), box=3):\n"
            "        touch(row)\n",
            encoding="utf-8",
        )
        sites2 = unscoped_walk_sites([fixture2])
        ok(
            not sites2,
            "a `select(...)` called WITH a filter keyword is never flagged",
            str(sites2),
        )

        # Arm (c): `to_payload()` is only flagged on something that looks like an
        # Inventory — a differently-typed object's `to_payload()` must not match, proving
        # the guard does not simply grep the method name across the whole file.
        fixture3 = Path(tmp) / "fixture_other_to_payload.py"
        fixture3.write_text(
            "def do_other():\n"
            "    book = load_corpus()\n"
            "    return book.to_payload()\n",
            encoding="utf-8",
        )
        sites3 = unscoped_walk_sites([fixture3])
        ok(
            not sites3,
            "`book.to_payload()` (not an Inventory) is never flagged",
            str(sites3),
        )
```

```python
    print("\nunscoped walk: the row itself, against the two failure shapes item 1's spec names")

    # Arm (d): a site not on the allowlist fails the row (report-level, not just the
    # matcher). Reuses fixture from arm (a) above if still in scope, or rewrite it here
    # standalone so this block does not depend on the tempdir from the previous `with`.
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture_new_site.py"
        fixture.write_text(
            "def do_something_new():\n"
            "    for card in inventory.cards.values():\n"
            "        touch(card)\n",
            encoding="utf-8",
        )
        report = Report()
        # Directly exercise the matcher + the allowlist comparison the check function
        # does, without needing a Report-shaped end-to-end call — the check function
        # itself hard-codes the real repo's paths, so drive the comparison logic instead:
        found = unscoped_walk_sites([fixture])
        new_site_flagged = any(
            (rel(fixture), fname, shape) not in UNSCOPED_WALK_ALLOWED
            for _, _, fname, shape in found
        )
        ok(new_site_flagged, "a site absent from UNSCOPED_WALK_ALLOWED is reportable as new")

    # Arm (e): an allowlist entry naming a site the tree no longer has is reportable as
    # stale — the "removed site not removed from the list" failure item 1's spec text
    # calls out by name. Synthesize a fixture with NONE of the allowlisted shapes and
    # confirm every real allowlist entry is absent from what it finds.
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture_empty.py"
        fixture.write_text("def do_boxes():\n    return []\n", encoding="utf-8")
        found = unscoped_walk_sites([fixture])
        stale = [
            (path, fname, shape) for path, fname, shape in UNSCOPED_WALK_ALLOWED
            if (path, fname, shape) not in {(rel(fixture), f, s) for _, _, f, s in found}
        ]
        ok(
            len(stale) == len(UNSCOPED_WALK_ALLOWED),
            "every allowlist entry is reportable as stale when the scan does not find it "
            "(proves the 'removed but not deleted from the list' comparison actually runs)",
            str(stale[:3]),
        )
```

Arms (d) and (e) are deliberately written against the pure comparison logic rather than
by calling `check_unscoped_walk(Report())` end-to-end and asserting on `report.checks` —
every other row's self-test in this file does the same (drives the pure helper, not the
`Report`-taking wrapper), because the wrapper always scans the REAL repository's
`server/`, `store/master.py`, `cli/resolve.py`, and a self-test fixture cannot substitute
for that without monkeypatching `_UNSCOPED_WALK_ROOTS`, which none of this file's other
self-tests do. If you want an end-to-end proof as well, add one more `ok(...)` that runs
`check_unscoped_walk(Report())` against the real tree and asserts zero findings — that is
your Measure step below, not a self-test arm, since it depends on the real repo being
clean at the moment you run it.

## Call sites (complete list — the 12 the guard starts from)

| # | File:function | Shape | Verified at |
|---|---|---|---|
| 1 | `server/capture_server.py` `do_inventory` | `to_payload()` on `inventory` | def line 3056, call at 3094 |
| 2 | `server/capture_server.py` `_release_plan` | `.items()` on `inventory.cards` | call at 4549 |
| 3 | `server/capture_server.py` `do_search` | `.values()` on `inventory.cards` | call at 7970 |
| 4 | `server/capture_server.py` `_boxes_named` | `.distinct("box")` on `inventory.cards` | call at 8349 (a second call in the same function, `select(("box",), box=None)`, is scoped and NOT on the list — it carries a keyword) |
| 5 | `server/capture_server.py` `do_boxes` | `.distinct("box")` on `inventory.cards` | call at 8388 |
| 6 | `server/pipeline_routes.py` `_box_names` | `.select(("box","run"))` on `inventory.cards`, no keywords | def line 797, call at 838 |
| 7 | `server/pipeline_routes.py` `_unsent_ledger` | `.distinct("sku")` on `inventory.cards` | def line 2283, call at 2370 |
| 8 | `server/pipeline_routes.py` `_on_hand_by_run` | `.select(("run","state"))` on `inventory.cards`, no keywords | def line 2429, call at 2444 |
| 9 | `server/pipeline_routes.py` `do_pipeline_value` | `.values()` on `inventory.cards` | def line 3117, call at 3202 |
| 10 | `store/master.py` `to_payload` (method of `Inventory`) | `.items()` on `self.cards` (NOT the `.items()` calls on `self.boxes`/`self.listings` two lines below — the matcher's `_cards_chain` check is what tells them apart) | def line 1447, call at 1458 |
| 11 | `store/master.py` `counts` (method of `Inventory`) | `.select(("state",))` on `self.cards`, no keywords | def line 2374, call at 2378 |
| 12 | `cli/resolve.py` `box_views` | `.values()` on `inventory.cards` | def line 372, call at 395 |

**Line numbers above are for your verification while writing the matcher, never for the
allowlist itself** — the allowlist is keyed by `(path, function, shape)` precisely so
these numbers moving does not break anything. If any of these have moved by the time you
implement this, re-find the function by name (`grep -n "^def <name>"`) and confirm the
shape is unchanged before treating a mismatch as a defect in this file rather than in the
matcher.

## Tests

This item has no harness (`T*`) test — it is a `docs-audit` row, and `make docs-audit`
rows are proved by `scripts/docs-audit.py --self-test` (`make audit-self-test`), never by
`harness/tests/`. There is no per-check pytest-style test name in this file; every row's
proof lives inline in `self_test()` as `ok(condition, label, detail)` calls, which is what
you are adding in Step 5.

- `scripts/docs-audit.py --self-test` (`make audit-self-test`) — must print `ok` for all
  five new lines: the three matcher arms in the first block (new site found; scoped
  `select` not found; unrelated `to_payload()` not found) and the two row-level arms in
  the second block (new site reportable; every allowlist entry reportable as stale
  against an empty fixture).
- `python3 scripts/docs-audit.py --json | python3 -c "import json,sys; \
  rows={r['label']: r for r in json.load(sys.stdin)['rows']}; \
  print(rows['unscoped walk'])"` — on the clean tree this must show
  `"scanned": 12, "findings": []`.
- `make docs-audit` (full render) — the `unscoped walk` line should print
  `ok   unscoped walk           12 full-table reads of inventory.cards found, 12 allowed
  (pinned at 12)` or equivalent wording from your `summary=` string.
- `make check` — must stay green; this only adds a new row inside the `docs-audit` target
  that `check` already runs, so no new Makefile target and no `scripts/checks.py` entry.

## Allowlist (the literal list this row starts from)

```python
UNSCOPED_WALK_ALLOWED: FrozenSet[Tuple[str, str, str]] = frozenset({
    ("server/capture_server.py", "do_inventory", "to_payload"),   # permanent, owner's word
    ("server/capture_server.py", "_release_plan", "items"),
    ("server/capture_server.py", "do_search", "values"),
    ("server/capture_server.py", "_boxes_named", "distinct"),
    ("server/capture_server.py", "do_boxes", "distinct"),
    ("server/pipeline_routes.py", "_box_names", "select"),
    ("server/pipeline_routes.py", "_unsent_ledger", "distinct"),
    ("server/pipeline_routes.py", "_on_hand_by_run", "select"),
    ("server/pipeline_routes.py", "do_pipeline_value", "values"),
    ("store/master.py", "to_payload", "items"),
    ("store/master.py", "counts", "select"),
    ("cli/resolve.py", "box_views", "values"),
})
UNSCOPED_WALK_EXPECTED = 12
```

Per `docs/specs/store-scaling/00-phases.md`'s phase table, later items lower this as
follows (recorded here for your own sanity-check only — do not implement any of these
removals as part of this item, and do not treat a disagreement between this note and a
later item's own file as your problem to resolve; the later item's file wins):

- Phase 1 (items 2, 4) → expected to fall to 10 (removes `_boxes_named`, `_unsent_ledger`).
- Phase 2 (items 6, 7, 8) → expected to fall to 4 (removes `do_pipeline_value`,
  `box_views`, `_release_plan`, `_box_names`, `_on_hand_by_run`, `do_search` — six more
  sites off the 10 Phase 1 leaves). Trust each item's own file's count over this summary
  line, which exists only to state the direction — down, never up — not to re-derive the
  arithmetic; `00-phases.md`'s own phase table is the authority if the two disagree.
- Final resting state: 4 — `do_inventory` (permanent), `store/master.py:to_payload`
  (permanent — nothing removes the legacy JSON-shape method itself, only its two current
  *callers*; if a later item proves `to_payload()`'s own `.items()` call becomes
  unreachable in production code, that is a bonus finding for that item to make, not
  something to assume here), `do_boxes` (permanent — one indexed column, cheap, the guard
  names it and moves on), `counts` (permanent — same reason).

## Do not touch

- **`Rows.where(**equals)`** — never flagged, in this item or any later one. The plan's
  own text (docs/specs/store-scaling.md §3 item 1) names exactly four shapes:
  `.values()`, `.items()`, `to_payload()`, and unfiltered `select`/`distinct`. `where()`
  always takes keyword filters in every call site in this repo; it is not part of this
  guard's scope, and adding it would very likely produce false positives on legitimately
  scoped code this session has not audited.
- **`store/rows.py`, `store/db.py`, `store/queues.py`** — not in the three roots. Do not
  widen `_UNSCOPED_WALK_ROOTS`/`_UNSCOPED_WALK_SINGLE_FILES` to "all of `store/`"; `Rows`
  itself defines `values`/`items`/`select`/`distinct` inside `store/rows.py`, and a wider
  walk would flag the method DEFINITIONS as if they were unscoped call sites.
- **`docs/specs/store-scaling.md`** — this item does not edit the plan document, even
  though this file corrects one of its table entries (`do_inventory`'s "Removed by: item
  2"). The correction already lives in `docs/specs/store-scaling/00-phases.md`; adding a
  third place that states it is how the "three ways to spell a doc citation" defect
  (D149, `docs/specs/store-scaling.md` is governed by the same discipline) gets started.
- **`CLAUDE.md`** — no hard rule references this row, so `check_rule_enforcement` has
  nothing to reconcile here and none is needed. Do not add a CLAUDE.md sentence claiming
  a count for this row; nothing in the repo's existing mechanism (`check_check_registry`,
  `check_check_census`) governs *docs-audit row* rosters the way it governs `make check`
  *target* rosters — those two rows are about the Makefile's `check:` recipe, not about
  which functions `scripts/docs-audit.py` defines. `check_dispatch` is the only mechanism
  that needs this row registered, and it is registered in `audit()` (Step 4).
- **`scripts/checks.py`** — this is not a new `make` target, it is a new row inside the
  existing `docs-audit` target. `check_check_registry` reconciles `scripts/checks.py`
  against the `check:` *recipe* (a list of `make` target names); it has no concept of a
  row inside one target and does not need one added.

## Measure

Before writing anything, confirm the twelve sites are still where this file says:

```bash
grep -n "\.values()\|\.items()\|\.distinct(\|\.select(\|to_payload()" \
  server/capture_server.py server/pipeline_routes.py store/master.py cli/resolve.py
```

Cross-check each hit against the table in "Call sites" above and re-derive any that moved.

After implementing, in order:

```bash
python3 -c "import ast; ast.parse(open('scripts/docs-audit.py').read())"   # parses clean
python3 scripts/docs-audit.py --self-test 2>&1 | tail -40                  # your 5 new "ok" lines, 0 FAIL
make audit-self-test                                                        # same, via make
python3 scripts/docs-audit.py --json | python3 -m json.tool | grep -A6 '"unscoped walk"'
# expect: "scanned": 12, "findings": []
make docs-audit                                                             # full render, "unscoped walk" line reads ok
make check                                                                  # still green end to end
```

Expected `--json` fragment on a clean tree:

```json
{
  "label": "unscoped walk",
  "severity": "mechanical",
  "summary": "12 full-table reads of inventory.cards found, 12 allowed (pinned at 12)",
  "scanned": 12,
  "vacuous": false,
  "findings": []
}
```

## Risks the implementer should know

- **The keyword check on `select` is the one line most likely to be "fixed" into a false
  positive.** If a future edit changes `not node.keywords` to something that also treats
  `select(("box",), box=None)` as unscoped, `_boxes_named` gains a spurious finding on a
  call that is genuinely filtered (it just happens to filter for `box IS NULL`, a small
  result set). Keep the self-test arm (b) passing as the regression guard for this.
- **`_inventory_like` is a name heuristic, not a type check.** Python source has no static
  types here, so a future site named e.g. `store_inventory.to_payload()` would be missed
  (the heuristic checks for the literal name `inventory`, not a suffix or substring — by
  design, since a substring match would also catch unrelated variables like
  `inventory_snapshot_for_debug`). If a later item renames the variable that holds an
  `Inventory` instance anywhere in these three roots, re-check this heuristic still
  matches; it is a plausible future false-negative and worth a one-line comment reminder
  at the call site if you notice it happening.
- **Do not be tempted to make this row ADVISORY instead of MECHANICAL "until the six PRs
  land."** The plan is explicit that this guard goes first specifically so later PRs are
  checked against it — a soft version now and a hard flip later would mean none of the six
  PRs was ever actually gated by anything, which is the exact "route exists, nothing
  reaches it" failure CLAUDE.md's hard rules section names by name for a different case.
- **The final resting allowlist is 4, not 0.** Do not treat a later item's inability to
  reach zero as a sign this guard is broken — `do_inventory`, `store/master.py:to_payload`,
  `do_boxes`, and `counts` are permanent by design (one is an owner ruling to keep an
  unused route rather than delete it; the other three are one indexed column each, judged
  cheap enough in the plan's own §4 table — "stays — one column, cheap; the guard names
  it").
