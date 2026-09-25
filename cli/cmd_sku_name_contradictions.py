"""`pkmnscan cards sku-names` — RETIRED into `pkmnscan cards identity`
(`docs/specs/identity-follows-sku.md` §5.5, lane 2).

D242's sibling compared a card's own stored `name` against its SKU's product name in the
newest cached export. After lane 2's `bind_sku` becomes the one writer of a card's identity
(`store/master.py`, lane 1), a bound card's `name` IS its SKU's product name by
construction, so this class also reads zero forever — the exact argument §5.5 makes for its
own twin. The merged report reads the SKU table directly instead: `pipeline/
identity_binding.py`'s name half, run by `./pkmnscan cards identity`.

`run` below is now a one-line pointer, on the owner's own ruling ("Merge them", §12 ruling
6). `pipeline/sku_name_contradictions.py`'s own resolver (`find_contradictions`) is still
proved directly by `scripts/sku-name-contradictions-selftest.py` against fixtures, even
though nothing on the ordinary command path calls it any more — the module is not lost, only
this command's own use of it (§9: "Given up... `cards sku-names`... The one writer, the one
table and the one report subsume each, and none is lost").
"""

from __future__ import annotations


def run(args, say) -> int:
    """RETIRED (§5.5, ruling 6: "Merge them"). `./pkmnscan cards identity` carries this
    check's replacement — the name half of its name/number contradiction report, read off
    the SKU table rather than off a re-fetched export. Exits 0: an operator who typed the
    old command is told where to go, not refused."""
    say("`cards sku-names` is retired — run `./pkmnscan cards identity` instead. "
        "docs/specs/identity-follows-sku.md §5.5: the same question, answered off the SKU "
        "table, merged with `cards contradictions` into one report.")
    return 0
