#!/usr/bin/env python3
"""The held-out check on the free reader's accept rule. A GATE BEFORE ADOPTION, never part of `make check`.

The accept rule (`identify/match.py`: `MARGIN_MIN`, `FLOOR_MIN`, the look-alike guard) was fit on
the spike's 500 photographs. This runs it, unchanged, over photographs the spike never saw, scores
each answer against the owner's own confirmed identification, and says what happened. It reads
the store read-only and writes nothing to it. No image is copied or kept.

    BANCHI_HOME=<store> python3 scripts/match-heldout.py --from-store [--exclude FILE] [--limit N]
    python3 scripts/match-heldout.py --manifest FILE

`--from-store` takes every card the store holds with a confirmed SKU, a number and a photograph on
disk, minus the photographs in `--exclude` (a JSON list of photo paths or sha256 digests: the spike's
sample), in a fixed order so a rerun reads the same cards. `BANCHI_HOME` names the store, and it is
also where the hint vocabulary comes from (the exports under `inventory/.exports/`).
`--manifest` is a JSON list of `{photo, game, set, number, name, set_hint?}` for photographs that are
not in the store.

WHAT IT REPORTS, and what makes it fail:

  accepted, and wrong      an accepted card whose answer is not the card the owner confirmed.
                           THIS IS THE GATE: any one fails the check.
  absent-truth accepted    a card whose true printing has NO stock photo (the index lists it as
                           missing) that the reader accepted anyway. Every such card must be left
                           unread: it is the case the look-alike guard exists for, and any one
                           accepted fails the check.
  accepted share           how much of the set the rule reads, and the unread cards by reason.
  upper bound              the rule of three: with no wrong answer in N accepted, the true rate is
                           under 3/N at 95%. The check reports it and the owner judges it. THERE IS
                           NO PASS MARK ON THE SHARE OR THE BOUND: the owner's word was "measure first".

Exit 0 is a pass, 1 a failure, 2 a read that could not run (no model, no index, no photographs): never
reported as a pass or a failure.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_CODE_PREFIX = re.compile(r"^[^:]+:\s*")


def _same_set(truth: str, answered: str) -> bool:
    from pipeline import join

    strip = lambda name: join.normalize_set(_CODE_PREFIX.sub("", name or "", count=1))  # noqa: E731
    return join.normalize_set(truth or "") == join.normalize_set(answered or "") or strip(truth) == strip(answered)


def _store_cards(exclude):
    from store import files

    home = files.home()
    db = sqlite3.connect(f"file:{files.inventory_dir() / 'store.sqlite'}?mode=ro", uri=True)
    rows = db.execute(
        "select cards.key, cards.game, cards.set_name, cards.number, cards.name, cards.set_hint, i.photo_sha256 "
        "from cards join identifications i on i.key = cards.key "
        "where cards.sku is not null and cards.sku != '' and cards.number is not null and cards.number != '' "
        "and cards.game in ('pokemon', 'riftbound', 'one_piece') order by cards.key"
    ).fetchall()
    db.close()
    out = []
    for key, game, set_name, number, name, hint, sha in rows:
        photo = home / "photos" / sha[:2] / f"{sha}.jpg"
        if not photo.exists() or sha in exclude or str(photo) in exclude:
            continue
        out.append(dict(key=key, photo=str(photo), game=game, set=set_name, number=number, name=name, set_hint=hint))
    return out


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="the free reader's held-out check")
    parser.add_argument("--from-store", action="store_true")
    parser.add_argument("--manifest")
    parser.add_argument("--exclude", help="JSON list of photo paths or sha256 digests to leave out")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--model")
    parser.add_argument("--index")
    parser.add_argument("--json", help="also write the full result here")
    args = parser.parse_args(argv[1:])

    from identify import match
    from pipeline import join

    model = Path(args.model) if args.model else match.model_path()
    index_file = Path(args.index) if args.index else match.index_path()
    if not model.exists() or not index_file.exists():
        print(f"unknown: needs the model file ({model}) and the index ({index_file}). Prepare the free reader first.")
        return 2
    exclude = set(json.loads(Path(args.exclude).read_text())) if args.exclude else set()
    try:
        if args.manifest:
            cards = json.loads(Path(args.manifest).read_text())
        elif args.from_store:
            cards = _store_cards(exclude)
        else:
            print("unknown: name the photographs: --from-store or --manifest FILE")
            return 2
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        print(f"unknown: the photographs could not be listed ({exc})")
        return 2
    if args.limit:
        cards = cards[: args.limit]
    if not cards:
        print("unknown: no photographs to read")
        return 2

    strategies = {"pokemon": "pokemon_card_v1", "riftbound": "riftbound_card_v1", "one_piece": "one_piece_card_v1"}
    requests = [
        match.Request(
            key=str(i), photo=Path(c["photo"]), game=c["game"],
            strategy=strategies[c["game"]], set_hint=c.get("set_hint"),
        )
        for i, c in enumerate(cards)
    ]
    with match.Index(index_file) as index:
        if index.meta("model_sha256") != match.MODEL_SHA256 and model_path_is_pinned(model, match):
            print("unknown: the index was built by another model file")
            return 2
        results = match.read(requests, index, model)
        listed = {
            (g, s, join.number_index_key(n), match.card_name(name))
            for g, s, n, name in index.db.execute("select game, set_name, number, name from vec")
        }
        missing = {
            (g, s, join.number_index_key(n))
            for g, s, n in index.db.execute(
                "select game, set_name, number from vec where status in ('no_url','no_photo','unreadable')"
            )
        }
        twins = Counter(
            (g, match.card_name(name))
            for g, name in index.db.execute("select game, name from vec")
        )
        blocked_names = {
            match.card_name(name)
            for (name,) in index.db.execute("select name from vec where status in ('no_url','no_photo','unreadable')")
        }

    records = []
    wrong, absent_accepted, unread = [], [], Counter()
    bad_labels = []
    accepted = 0
    absent_cases = 0
    lookalike_cases = 0
    for card, result in zip(cards, results):
        number_key = join.number_index_key(card["number"])
        is_absent = any(
            g == card["game"] and n == number_key and _same_set(card["set"], s) for g, s, n in missing
        )
        absent_cases += 1 if is_absent else 0
        lookalike_cases += 1 if match.card_name(card.get("name") or "") in blocked_names else 0
        names = [match.card_name(c["name"]) for c in result.candidates]
        records.append(dict(
            photo=card["photo"], accepted=result.accepted, code=result.code, margin=result.margin,
            floor=result.floor, sibling=len(names) > 1 and names[0] == names[1],
            right=None, absent=is_absent,
        ))
        if not result.accepted:
            unread[str(result.code)] += 1
            continue
        accepted += 1
        payload = result.payload or {}
        answered_number = join.number_index_key(payload.get("number", ""))
        right = answered_number == number_key and _same_set(card["set"], payload.get("set", ""))
        stored_name = match.card_name(card.get("name") or "")
        if not right and not any(
            g == card["game"] and n == number_key and _same_set(card["set"], s) and name == stored_name
            for g, s, n, name in listed
        ):
            # THE STORED NAME AND NUMBER DO NOT AGREE WITH ANY PRINTING THE CATALOGUE LISTS (a typo in a
            # stored number, a total that does not exist, a number that belongs to another card). The
            # answer cannot be scored against it, so it is reported for the owner to look at and is NOT
            # counted as a wrong answer.
            bad_labels.append(
                dict(photo=card["photo"], stored=f"{card['set']} {card['number']} {card.get('name', '')}",
                     answered=f"{payload.get('set')} {payload.get('number')} {payload.get('name')}",
                     margin=result.margin, floor=result.floor)
            )
            records[-1]["right"] = None
            continue
        records[-1]["right"] = right
        # How many printings of the ANSWERED name the index holds in this game: the alternate arts,
        # overnumbered and promo twins the photograph has to be told apart from.
        records[-1]["twins"] = twins[(card["game"], match.card_name(payload.get("name", "")))]
        if is_absent:
            absent_accepted.append(card["key"] if "key" in card else card["photo"])
        if not right:
            wrong.append(
                dict(photo=card["photo"], truth=f"{card['set']} {card['number']} {card.get('name', '')}",
                     answered=f"{payload.get('set')} {payload.get('number')} {payload.get('name')}",
                     margin=result.margin, floor=result.floor)
            )

    total = len(cards)
    bound = 3 / accepted if accepted else None
    print(f"photographs read          {total}")
    print(f"accepted                  {accepted} ({accepted / total:.1%})")
    print(f"accepted, and wrong       {len(wrong)}")
    print(f"accepted, unscoreable     {len(bad_labels)} (the stored name and number are no printing the catalogue lists)")
    print(f"upper bound on wrong rate {'none (nothing accepted)' if bound is None else f'under {bound:.2%} at 95% (rule of three)'}")
    print(f"absent-truth cards        {absent_cases} (true printing has no stock photo); accepted anyway: {len(absent_accepted)}")
    print(f"look-alike name cards     {lookalike_cases} (a printing of the same name has no stock photo)")
    print("not accepted             " + (", ".join(f"{n} {code}" for code, n in sorted(unread.items())) or "none"))
    print(f"rule                      margin >= {match.MARGIN_MIN}, floor >= {match.FLOOR_MIN}, look-alike guard on")
    for item in bad_labels[:20]:
        print(f"CHECK THE STORED NUMBER {item['photo']}: stored {item['stored']} / answered {item['answered']}")
    for item in wrong[:20]:
        print(f"WRONG {item['photo']}: truth {item['truth']} / answered {item['answered']} (margin {item['margin']:.4f}, floor {item['floor']:.4f})")
    failed = bool(wrong or absent_accepted)
    print("held-out check:", "FAIL" if failed else "pass (no wrong answer accepted, no absent-truth card accepted)")
    if args.json:
        Path(args.json).write_text(json.dumps(dict(
            total=total, accepted=accepted, wrong=wrong, bad_labels=bad_labels, absent_cases=absent_cases,
            absent_accepted=absent_accepted, lookalike_cases=lookalike_cases, unread=dict(unread),
            upper_bound=bound, margin_min=match.MARGIN_MIN, floor_min=match.FLOOR_MIN, cards=records,
        ), indent=1))
    return 1 if failed else 0


def model_path_is_pinned(model: Path, match) -> bool:
    """A test model file with another hash may be used with an index built by that same file, so the
    pinned-index refusal applies only to the pinned file."""
    return model.resolve() == match.model_path().resolve()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
