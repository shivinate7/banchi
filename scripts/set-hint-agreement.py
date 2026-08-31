#!/usr/bin/env python3
"""Prove `server/tcg_export.py:match_sets` and `app/src/setHint.ts` still answer the same.

WHY THIS EXISTS. D65 puts one matching rule in two languages because neither side can import
the other: Python RESOLVES the hint when the export is fetched, and TypeScript tells the
operator, at the rig, whether the hint they are typing is going to resolve. If the two ever
disagree the screen says MATCHED over a hint the fetch will miss — which is worse than the
silence it replaced, because silence is not trusted and a verdict is.

This repo has been bitten by an unasserted cross-language seam twice. `docs/GATES.md` carries
the first: two new game prompts named their identifier field differently from what
`cli/resolve.py` read, which would have parsed cleanly and handed the join a card with
`number=None`. `scripts/port-agreement.py` carries the second and is this script's model.

WHAT IT COMPARES. Not the shape of the verdicts — the two sides deliberately answer different
questions. Python returns the set IDS it resolved and the hints that missed; TypeScript
returns a verdict a sentence can be written from, which splits Python's single "missed" into
`ambiguous` (several sets answer, so none does) and `unmatched` (none answers). What has to
agree is the ONE fact both are staking a claim on: DID THIS HINT RESOLVE, AND TO WHICH SET.
So every case is run through both and reduced to that pair.

THE CASES ARE THE REAL VOCABULARY, not invented strings. Two of the three set lists below are
verbatim from D65's own measurements — the Riftbound and Pokemon names it resolved `UNL`,
`ME01`, `SV05`, `SV09`, `OGN`, `MEG`, `TEF` and `JTG` against — because the rules that are
easy to get wrong are the ones about real shapes: a colon-code, a prefix that is unique, and
a prefix that is not — `Origin` answers to both `Origins` and `Origins: Proving Grounds` and
therefore to neither, while `Origins` resolves outright because equality is tried first.

Stdlib only, and it writes nothing anywhere.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import tcg_export  # noqa: E402

# TCGplayer's own set names, with the ids the portal serves them under. `0` is the "All Set
# Names" row and never appears here: `server/pipeline_routes.py:do_tcg_sets` drops it before
# the screen sees it, and `match_sets` drops it again on its own side.
RIFTBOUND = [
    {"Text": "Origins", "Value": "24000"},
    {"Text": "Origins: Proving Grounds", "Value": "24001"},
    {"Text": "Unleashed", "Value": "24010"},
    {"Text": "Spiritforged", "Value": "24020"},
    {"Text": "Vendetta", "Value": "24030"},
    {"Text": "Secret Garden", "Value": "24040"},
]
POKEMON = [
    {"Text": "SV05: Temporal Forces", "Value": "23000"},
    {"Text": "SV09: Journey Together", "Value": "23100"},
    {"Text": "ME01: Mega Evolution", "Value": "23200"},
    {"Text": "SV: Prismatic Evolutions", "Value": "23300"},
    {"Text": "SV: Paldean Fates", "Value": "23400"},
]
ONE_PIECE = [{"Text": "OP-15 A Fist of Divine Speed", "Value": "22000"}]

POKEMON_ALIASES = {"MEG": "ME01", "TEF": "SV05", "JTG": "SV09"}
RIFTBOUND_ALIASES = {"OGN": "Origins"}

# (label, hint, sets, aliases). The label is what a failure prints, so it says what the case
# is FOR rather than repeating the hint.
CASES: List[Tuple[str, str, list, dict]] = [
    ("the set's own name", "Spiritforged", RIFTBOUND, RIFTBOUND_ALIASES),
    ("its own name, folded", "spiritforged", RIFTBOUND, RIFTBOUND_ALIASES),
    ("its own name, padded", "  Spiritforged  ", RIFTBOUND, RIFTBOUND_ALIASES),
    ("a unique prefix", "Spirit", RIFTBOUND, RIFTBOUND_ALIASES),
    ("D65's measured prefix", "UNL", RIFTBOUND, RIFTBOUND_ALIASES),
    # A base set that is ALSO a prefix of its own sub-set. Rule one runs before rule two, so
    # this resolves to the base set — which is why the rules are ordered rather than merged,
    # and why substring is not among them: as a substring it would answer to both and to
    # neither. The case one letter shorter is the one that genuinely cannot choose.
    ("a base set that is its sub-set's prefix", "Origins", RIFTBOUND, RIFTBOUND_ALIASES),
    ("a prefix answering to two sets", "Origin", RIFTBOUND, RIFTBOUND_ALIASES),
    ("an alias onto a base set", "OGN", RIFTBOUND, RIFTBOUND_ALIASES),
    # A DROPPED MIDDLE LETTER, not a truncation: `Spiritforge` is a unique prefix and
    # resolves. This is the typo shape the screen's verdict exists for.
    ("nothing like any of them", "Spiritfoged", RIFTBOUND, RIFTBOUND_ALIASES),
    ("a truncation, which is a prefix", "Spiritforge", RIFTBOUND, RIFTBOUND_ALIASES),
    ("a hint for the wrong game", "SV09", RIFTBOUND, RIFTBOUND_ALIASES),
    ("D65's measured colon-code", "ME01", POKEMON, POKEMON_ALIASES),
    ("a colon-code, folded", "me01", POKEMON, POKEMON_ALIASES),
    ("D65's measured alias", "MEG", POKEMON, POKEMON_ALIASES),
    ("an alias, folded", "meg", POKEMON, POKEMON_ALIASES),
    ("the full colon name", "SV09: Journey Together", POKEMON, POKEMON_ALIASES),
    ("a community code with no alias", "PAL", POKEMON, POKEMON_ALIASES),
    ("the digits alone", "09", POKEMON, POKEMON_ALIASES),
    ("a hyphenated identifier", "OP-15 A Fist of Divine Speed", ONE_PIECE, {}),
    ("blank", "", POKEMON, POKEMON_ALIASES),
    ("whitespace only", "   ", POKEMON, POKEMON_ALIASES),
    ("no vocabulary at all", "SV09", [], {}),
    # THE ABBREVIATION RULE, which is the last one tried and the only one that can invent an
    # answer. Every case here was measured against the real committed export before it was
    # written down — see the module docstring of `pipeline/setnames.py`.
    ("a real code no alias covers", "SFD", RIFTBOUND, RIFTBOUND_ALIASES),
    ("that code, folded", "sfd", RIFTBOUND, RIFTBOUND_ALIASES),
    ("a real code that resolves as a prefix, not an abbreviation", "VEN", RIFTBOUND, RIFTBOUND_ALIASES),
    ("three letters spanning a two-word name", "SEC", RIFTBOUND, RIFTBOUND_ALIASES),
    ("a real code built off the colon's right side", "JTG", POKEMON, {}),
    ("longer than a code can be", "SPIRI", RIFTBOUND, RIFTBOUND_ALIASES),
    # ZERO PADDING. `sv9` and `SV09` are one set in two vocabularies — pokemontcg.io writes
    # the unpadded form and TCGplayer the padded one. The fetch could not match it at all
    # until the two matchers were merged; the join always could.
    ("an unpadded block number", "sv9", POKEMON, {}),
    ("a padded block number", "SV09", POKEMON, {}),
    # THE PREFIX GUARD. `sv1` is a prefix of `sv19` as a string and is a DIFFERENT SET as a
    # number. `harness/tests/t3_join_coverage.py` has asserted this since before either
    # matcher existed, and the fetch's own prefix rule got it wrong.
    ("a prefix that splits a number", "sv1", POKEMON, {}),
    # A colon prefix shared by two sets. Four real SV sets share `SV:`; two here is enough to
    # tie, and a tie widens rather than picking.
    ("a colon side two sets share", "SV", POKEMON, {}),
]


def python_answer(hint: str, sets: list, aliases: dict) -> Optional[str]:
    """The set NAME `match_sets` resolved this hint to, or None for a miss.

    `match_sets` answers in ids because that is what the portal's request takes; the name is
    recovered here so the two sides compare like with like.
    """
    matched, _missed = tcg_export.match_sets([hint], sets, aliases)
    if len(matched) != 1:
        return None
    wanted = str(matched[0])
    for row in sets:
        if str(row.get("Value")) == wanted:
            return str(row.get("Text"))
    raise SystemExit(f"match_sets returned id {wanted}, which is in no set list it was given")


def node_answers(cases: List[Tuple[str, str, list, dict]]) -> List[Optional[str]]:
    """Run the real `app/src/setHint.ts` — never a copy of it — and read back its verdicts."""
    payload = [
        {
            "hint": hint,
            "sets": [{"name": str(row["Text"])} for row in sets],
            "aliases": aliases,
        }
        for _label, hint, sets, aliases in cases
    ]
    script = (
        "const m = await import(%s);\n"
        "const cases = JSON.parse(process.argv[1]);\n"
        "console.log(JSON.stringify(cases.map((c) => {\n"
        "  const v = m.resolveSetHint(c.hint, c.sets, c.aliases);\n"
        "  return v.state === 'matched' ? v.set : null;\n"
        "})));\n" % json.dumps((ROOT / "app" / "src" / "setHint.ts").as_uri())
    )
    done = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script,
         json.dumps(payload)],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    if done.returncode != 0:
        raise SystemExit(
            "node could not evaluate app/src/setHint.ts — the agreement is unproven, which\n"
            "is not the same as agreed:\n" + (done.stderr.strip() or "(no stderr)")
        )
    return json.loads(done.stdout.strip().splitlines()[-1])


def main() -> int:
    theirs = node_answers(CASES)
    failures = []
    resolved = 0
    for (label, hint, sets, aliases), got in zip(CASES, theirs):
        want = python_answer(hint, sets, aliases)
        if want is not None:
            resolved += 1
        if want != got:
            failures.append(
                f"{label} — hint {hint!r}: python {want or 'no match'}, node {got or 'no match'}"
            )

    if failures:
        print("set hint agreement: FAILED")
        for line in failures:
            print(f"  {line}")
        print()
        print("  The capture screen would tell the operator one thing and the export fetch")
        print("  would do another. Fix app/src/setHint.ts against server/tcg_export.py:")
        print("  match_sets, which is the side that decides what is actually fetched.")
        return 1

    print(
        f"set hint agreement: {len(CASES)} hints, identical verdicts "
        f"({resolved} resolve, {len(CASES) - resolved} do not)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
