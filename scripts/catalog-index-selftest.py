#!/usr/bin/env python3
"""Prove `scripts/catalog-index.py` and `pipeline/catalog.py` against a throwaway fixture
(D15, build-order step 9, piece 2's guard).

RED FIRST: every case here failed before `scripts/catalog-index.py` and `pipeline/catalog.py`
existed — there was no index to build and no reader to open one. Run against a small,
synthetic two-set vendor tree under a temp directory, never against the real 26 MB snapshot,
so this is fast enough to run on every `make check` — build-order-step-9's own guard rather
than a re-assertion that the owner's real catalog looks a particular way.

Cases:
  - a clean build joins cards to sets BY FILENAME and composes the same join_key
    `pipeline.join.number_index_key` would
  - a card file naming a set absent from sets/en.json is REFUSED, not silently skipped
  - `pipeline.catalog.CatalogIndex.open` refuses with `CatalogNotBuilt` before a build,
    and answers real lookups after one
  - the composed join_key matches `number_index_key` applied by hand, so the two paths this
    entry's decision argues can never drift are asserted to agree rather than assumed to

Never in the git hook (D18 — it writes a temp tree). In `make check` via `catalog-index-selftest`.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("catalog_index_cli", ROOT / "scripts" / "catalog-index.py")
catalog_index_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(catalog_index_cli)  # type: ignore[union-attr]

from pipeline.catalog import CatalogIndex, CatalogNotBuilt  # noqa: E402
from pipeline.join import number_index_key  # noqa: E402

FAILURES = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"ok   {label}")
    else:
        print(f"FAIL {label}  {detail}")
        FAILURES.append(label)


def make_fixture(root: Path) -> None:
    cards_dir = root / "cards" / "en"
    cards_dir.mkdir(parents=True)
    sets_dir = root / "sets"
    sets_dir.mkdir(parents=True)

    (sets_dir / "en.json").write_text(json.dumps([
        {"id": "fx1", "name": "Fixture One", "series": "Fixture", "printedTotal": 100,
         "total": 102, "ptcgoCode": "FX1", "releaseDate": "2020/01/01", "updatedAt": "2020/01/01 00:00:00"},
        {"id": "fx2", "name": "Fixture Two", "series": "Fixture", "printedTotal": 50,
         "total": 50, "ptcgoCode": "FX2", "releaseDate": "2021/01/01", "updatedAt": "2021/01/01 00:00:00"},
    ]), encoding="utf-8")

    (cards_dir / "fx1.json").write_text(json.dumps([
        {"id": "fx1-1", "name": "Alpha", "number": "007", "rarity": "Common", "supertype": "Pokémon",
         "images": {"small": "https://images.pokemontcg.io/fx1/7.png", "large": "https://images.pokemontcg.io/fx1/7_hires.png"}},
        {"id": "fx1-2", "name": "Beta", "number": "42", "rarity": "Rare", "supertype": "Pokémon",
         "images": {}},
    ]), encoding="utf-8")
    (cards_dir / "fx2.json").write_text(json.dumps([
        {"id": "fx2-1", "name": "Gamma", "number": "1", "rarity": "Common", "supertype": "Pokémon",
         "images": {}},
    ]), encoding="utf-8")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="catalog-index-selftest-"))
    try:
        vendor_dir = tmp / "vendor"
        make_fixture(vendor_dir)
        out_path = vendor_dir / "catalog.sqlite"

        # A reader over an unbuilt index refuses rather than building or crashing obscurely.
        try:
            CatalogIndex.open(out_path)
            check("open before build refuses", False, "did not raise CatalogNotBuilt")
        except CatalogNotBuilt:
            check("open before build refuses", True)

        stats = catalog_index_cli.build(vendor_dir, out_path)
        check("build reports both tables", stats == {"sets": 2, "cards": 3, "out": str(out_path)}, str(stats))

        with CatalogIndex.open(out_path) as idx:
            check("counts match the fixture", idx.counts() == {"sets": 2, "cards": 3}, str(idx.counts()))

            card = idx.card_by_id("fx1-1")
            expected_key = number_index_key("007/100")
            check(
                "join_key matches number_index_key composed by hand",
                card is not None and card.join_key == expected_key,
                f"got {card.join_key if card else None!r}, want {expected_key!r}",
            )

            by_key = idx.cards_by_join_key("7/100")  # unpadded lookup — the fold must still hit
            check(
                "cards_by_join_key finds the unpadded lookup",
                len(by_key) == 1 and by_key[0].id == "fx1-1",
                str(by_key),
            )

            s = idx.set_by_id("fx2")
            check("set_by_id reads printed_total", s is not None and s.printed_total == 50, str(s))

            by_name = idx.cards_by_name("Gamma")
            check("cards_by_name finds the fixture card", len(by_name) == 1 and by_name[0].set_id == "fx2", str(by_name))

        # A card file naming a set absent from sets/en.json is refused, not silently skipped.
        orphan_dir = tmp / "vendor-orphan"
        make_fixture(orphan_dir)
        (orphan_dir / "cards" / "en" / "ghost.json").write_text(json.dumps([
            {"id": "ghost-1", "name": "Nobody", "number": "1", "images": {}}
        ]), encoding="utf-8")
        try:
            catalog_index_cli.build(orphan_dir, orphan_dir / "catalog.sqlite")
            check("a card file with no matching set is refused", False, "build did not raise")
        except catalog_index_cli.CatalogBuildError as exc:
            check("a card file with no matching set is refused", "ghost" in str(exc), str(exc))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAILURES:
        print(f"\n{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        return 1
    print("\nall catalog-index-selftest cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
