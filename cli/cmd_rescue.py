"""`pkmnscan rescue <run>` — the cards of a stranded run, re-addressed to where they are now.

THE ONE-TIME REPAIR FOR A RUN D36 REFUSES, AND IT IS `realign`'s MECHANISM WITH ONE
RESTRICTION LIFTED. `cli/resolve.py:realign` re-binds a run's records to the slots their
photographs occupy now, box by box, and it looks only in the boxes THE RUN NAMES — which is
right inside a join, because a join must never follow a card into a drawer nobody asked it
about. That restriction is also exactly why it cannot see the case here: the cards left the
box the run names.

Measured on the owner's store, 2026-09-12. `2026-08-29-box1-01` read 133 cards out of box 1.
On 2026-09-11 the operator MOVED 99 of them to box 3 (D83) — `1/1 -> 3/724`, `1/2 -> 3/725`,
and so on to `3/822` — and then deleted box 1, which buried the 133 source records (D134).
Box 1's number was reused the same evening for a new drawer. So the run describes box 1, the
box 1 that exists today is somebody else's drawer, and `refuse_reallocated` refuses the join
— correctly, and forever, because the refusal is about the LABEL and cannot be talked out of
it. The 99 cards are on a shelf, identified, each carrying a SKU, and no press in the product
could reach them.

WHAT THIS WRITES IS A NEW RUN, BECAUSE A RUN IS AN IMMUTABLE INPUT. `cli/runs.py` says so in
its first sentence and the whole pipeline rests on it: a run directory is a record of what was
read, and editing one would make every report about it a claim nobody can check. The rescue
derives a SECOND run — the same readings, re-addressed to the positions the photographs are at
now, scoped to the drawer they are actually in and carrying that drawer's `bid` (D145) — and
leaves the first exactly as it is. The new run joins and emits by the ordinary path with no
special case anywhere, which is the property that made this shape worth the extra directory.

THE PHOTOGRAPH IS THE TRUTH, WHICH IS D36's OWN SENTENCE. Nothing here trusts a slot number,
a run name, a box number or the `run` column on a card. Every binding is a sha256 of the
photograph on disk matched against the sha256 the run recorded when it read that card, and a
digest that matches two records, or two photographs, is a question rather than a slot — so it
refuses the whole run rather than guessing an identity, exactly as `realign` does.

IT REFUSES A RUN THAT IS NOT STRANDED, and that is a safety property rather than tidiness. A
healthy run is joinable already; rescuing one would put a second run over the same positions
in `runs/`, and D86 measured what several runs over one shelf cost a capped send. The only
runs this will touch are the ones `cli/resolve.py:refuse_reallocated` refuses.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

from cli import resolve, runs
from store import files
from store import master
from store import photos
from store.session import Store

# The manifest key naming the run this one was derived from. Read by `rescue` itself to spot
# a repeat, and it is the only thing that makes a rescue run tellable from an ordinary one.
RESCUED_FROM = "rescued_from"


def _digests_in(payload: dict) -> Tuple[Dict[str, str], List[str], List[str]]:
    """(position key -> digest, records with no digest, digests carried by two records).

    A RECORD WITH NO DIGEST CANNOT BE RESCUED AND IS NOT A FAILURE. It is a run written
    before the field existed, or one whose photograph could not be prepared; it is named in
    the report and left alone, which is `CLAUDE.md`'s rule — dropping a card is forbidden,
    naming one is not.
    """
    by_key: Dict[str, str] = {}
    blind: List[str] = []
    seen: Dict[str, int] = {}
    for key, record in sorted((payload.get("cards") or {}).items()):
        digest = record.get("photo_sha256") if isinstance(record, dict) else None
        if not isinstance(digest, str) or not digest:
            blind.append(key)
            continue
        by_key[key] = digest
        seen[digest] = seen.get(digest, 0) + 1
    return by_key, blind, sorted(d for d, n in seen.items() if n > 1)


def _stranded_because(payload: dict, inventory: master.Inventory, run: runs.Run) -> List[str]:
    """Every sentence the store has for refusing this run's boxes, or an empty list.

    THE SAME CALL THE JOIN MAKES, on the same rule, through the same method — `refuse_reallocated`
    raises on the first one and this collects them all, because the operator is being shown why
    a rescue is being offered rather than being stopped.
    """
    scope = run.manifest.get("scope")
    bid = scope.get("bid") if isinstance(scope, dict) else None
    if not isinstance(bid, int) or isinstance(bid, bool):
        bid = None
    boxes = sorted(
        {
            int(record["box"])
            for record in (payload.get("cards") or {}).values()
            if isinstance(record, dict) and record.get("box") is not None
        }
    )
    out: List[str] = []
    for box in boxes:
        sentence = inventory.box_disowns_run(box, run.name, run.created_at, bid=bid)
        if sentence is not None:
            out.append(sentence)
    return out


def _existing_rescues(source: str, root: Path) -> List[runs.Run]:
    """Every run already derived from this one, oldest first."""
    found: List[runs.Run] = []
    if not root.is_dir():
        return found
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or not (entry / runs.MANIFEST).is_file():
            continue
        try:
            other = runs.open_run(entry)
        except runs.RunError:
            continue
        if other.manifest.get(RESCUED_FROM) == source:
            found.append(other)
    return found


def _photo_for(key: str, box: int, index: int, inventory: master.Inventory) -> str:
    """The path that NAMES the photograph now at `key`, rather than the slot it sits in.

    THE WHOLE POINT OF THE RESCUE IS THAT THE PHOTOGRAPH IS THE TRUTH, AND THIS FIELD USED TO
    CONTRADICT IT. It composed `captures/cards/box<B>/<idx>.jpg` by hand — the slot, which is
    exactly the thing the rescue has just finished proving unreliable. Since
    `D183` the bytes are filed under the card's own name,
    so this asks `store/photos.py` for the file and writes down what it answers.

    THREE ANSWERS, IN ORDER, AND EACH ONE MEANS SOMETHING DIFFERENT:

      the file that exists   `photos.find` — the card's name first, then the legacy address
                             while `meta.photos_relocated` is unset. This is the one every
                             rescued card takes, because the rescue only matched it against a
                             photograph in the first place.
      the name it would have a card whose photograph has gone since the match: the canonical
                             path is still the honest thing to write, because it is where the
                             bytes are if they come back (a D26 re-shoot writes there) and it
                             is what an audit compares against.
      the old address        a card with no cid naming a photograph at all — a `moved:`
                             tombstone or a `nophoto:` record. There is no name to compose, so
                             the field keeps the only shape it ever had, and the review screen
                             renders exactly what it rendered before.
    """
    card = inventory.cards.get(key)
    cid = getattr(card, "cid", None)
    found = photos.find(
        cid,
        box,
        index,
        relocated=bool(inventory.photos_relocated),
        home=files.home(),
    )
    if found is not None:
        return str(found)
    if photos.is_photo_cid(cid):
        return str(photos.path(cid))
    return str(photos.legacy_path(box, index))


def _rebound(payload: dict, moved: Dict[str, str], inventory: master.Inventory) -> dict:
    """The source payload with every rescued record re-keyed and re-addressed.

    THREE FIELDS MOVE AND NOTHING ELSE DOES. `box` and `index` are the address, `photo` is
    the file that address names now; the identification, the digest, the game, the claims and
    the strategy are what the run READ, and a rescue re-addresses a reading rather than
    revising one. `photo_sha256` is deliberately kept: it is the same bytes, which is the
    whole basis on which this record was matched, and it is what lets `realign` go on
    checking the rescue run at every later join.

    `inventory` IS THE SNAPSHOT `run` ALREADY HELD, and it is here for one field: `photo` is
    now asked of `store/photos.py` against the card at the new key rather than composed from
    the slot — see `_photo_for`. Nothing else reads it, and nothing here writes the store.
    """
    cards = payload.get("cards") or {}
    rebuilt: Dict[str, dict] = {}
    for old_key, new_key in sorted(moved.items(), key=lambda pair: _sort_key(pair[1])):
        record = dict(cards[old_key])
        box, _, index = new_key.partition("/")
        record["box"] = int(box)
        record["index"] = int(index)
        photo = record.get("photo")
        if isinstance(photo, str) and photo:
            record["photo"] = _photo_for(new_key, int(box), int(index), inventory)
        record["rescued_from_position"] = old_key
        rebuilt[new_key] = record
    out = {key: value for key, value in payload.items() if key != "cards"}
    out["cards"] = rebuilt
    # WHERE EACH CARD CAME FROM, AS ONE MAP. Every record already carries its own
    # `rescued_from_position`; this is the same fact collected so a reader can check the whole
    # re-addressing against the source run without walking 99 records.
    out["rescued_from_positions"] = {new: old for old, new in sorted(moved.items())}
    return out


def _sort_key(position: str) -> Tuple[int, int]:
    box, _, index = position.partition("/")
    try:
        return int(box), int(index)
    except ValueError:  # pragma: no cover — keys are built from ints above
        return 0, 0


def run(args, say) -> int:
    source = runs.open_run(args.run_dir)
    payload = source.read_identifications()
    snapshot = Store().read()
    inventory = snapshot.inventory

    say(f"rescue          {source.name}")
    say("")

    # ------------------------------------------------------------------ is it even stranded
    why = _stranded_because(payload, inventory, source)
    if not why:
        raise runs.RunError(
            f"REFUSING: {source.name} is not stranded — the store still reads its drawer as "
            f"its own, so `pkmnscan join {source.directory}` works and this command has "
            f"nothing to repair.\n"
            f"Rescuing a healthy run would put a second run over the same positions in "
            f"runs/, which is the shape D86 measured a capped send over.\n"
            f"Nothing was read past the store, and nothing was written."
        )
    for sentence in why:
        say(f"  stranded      {sentence}")
    say("")

    # ------------------------------------------------------------------ what the run recorded
    by_key, blind, twice_in_run = _digests_in(payload)
    say(f"  records       {len(payload.get('cards') or {})}")
    if twice_in_run:
        raise runs.RunError(
            f"REFUSING: {len(twice_in_run)} photograph digest(s) in this run are carried by "
            f"more than one record, so a digest does not name a card here. That is a "
            f"question, not a slot, and `CLAUDE.md` forbids guessing an identity.\n"
            f"Nothing was written."
        )
    if blind:
        say(f"  no digest     {len(blind)} record(s) cannot be checked: {_few(blind)}")

    # ------------------------------------------------------------------ where they are now
    boxes = sorted(int(entry.box) for entry in inventory.boxes.values())
    say(f"  searching     box {', '.join(str(b) for b in boxes) or 'none'} (every live drawer)")
    # THE SNAPSHOT IS HANDED IN, AND THE SOURCE IS PRINTED. The map comes off `cards.cid`
    # now rather than out of 997 MB of photographs, so passing the snapshot this command
    # already holds is one store read instead of a second one — and `source` says which
    # mechanism answered, because a rescue that searched the wrong thing would otherwise
    # report "none of this run's records match" in the same words either way.
    at, twice_on_disk, digest_source = resolve._photo_digests(boxes, inventory)
    say(f"  slots read    from the {digest_source}")

    moved: Dict[str, str] = {}
    missing: List[str] = []
    ambiguous: List[str] = []
    for key, digest in sorted(by_key.items()):
        if digest in twice_on_disk:
            ambiguous.append(key)
        elif digest in at:
            moved[key] = at[digest]
        else:
            missing.append(key)

    if ambiguous:
        raise runs.RunError(
            f"REFUSING: {len(ambiguous)} record(s) match a digest that is on two photographs "
            f"on disk: {_few(ambiguous)}. A digest that names two slots is a question, not a "
            f"slot, and `CLAUDE.md` forbids guessing an identity.\n"
            f"Nothing was written."
        )

    if not moved:
        raise runs.RunError(
            f"REFUSING: none of this run's {len(by_key)} checkable record(s) matches a "
            f"photograph in any live drawer, so there is nothing on a shelf to re-address. "
            f"The cards this run read have left the store — sold, retired, or deleted with "
            f"their box.\n"
            f"Nothing was written."
        )

    landed = sorted({_sort_key(new)[0] for new in moved.values()})
    if len(landed) > 1:
        raise runs.RunError(
            f"REFUSING: this run's cards are spread across boxes "
            f"{', '.join(str(b) for b in landed)}. D48 keeps a run to one box, and a rescue "
            f"that wrote one run over several would be a cart nobody has argued for.\n"
            f"Nothing was written."
        )

    box = landed[0]
    entry = inventory.box(box)
    bid = None if entry is None else master.int_or_none(entry.bid)
    label = f"box {box}" + (f" ({entry.name})" if entry is not None and entry.name else "")
    say(f"  found         {len(moved)} card(s), all in {label}")
    say(f"  bid           {bid if bid is not None else 'none — this drawer has no true index'}")
    if missing:
        say(f"  not on shelf  {len(missing)} record(s), left alone: {_few(missing)}")
    say("")
    for old_key in sorted(moved, key=_sort_key)[:5]:
        say(f"    {old_key} -> {moved[old_key]}")
    if len(moved) > 5:
        say(f"    ... and {len(moved) - 5} more")
    say("")

    # ------------------------------------------------------------------ already done?
    rebuilt = _rebound(payload, moved, inventory)
    # COMPARED AS DATA AND NOT AS BYTES. Two `json.dumps` call sites agreeing on `indent`,
    # `sort_keys` and `default` is a coupling nothing checks; what "already rescued" means is
    # that the same records landed at the same positions.
    for other in _existing_rescues(source.name, files.runs_dir()):
        try:
            already = json.loads(other.path(runs.IDENTIFICATIONS).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if already == json.loads(json.dumps(rebuilt, default=str)):
            say(f"already rescued: {other.name} holds exactly these {len(moved)} card(s).")
            say("Nothing written — this command is re-runnable and had nothing to add.")
            say(f"Next:  ./pkmnscan join {other.directory}")
            return 0

    if not args.write:
        say(f"--write would create a run over box {box} holding {len(moved)} card(s),")
        say(f"leaving {source.name} exactly as it is. Nothing was written.")
        return 0

    # ------------------------------------------------------------------ write the rescue run
    rescued = runs.create(f"box{box}-rescue")
    rescued.write_identifications(rebuilt)
    # WHAT IS CARRIED IS THE READING; WHAT IS DROPPED IS THE SOURCE RUN'S OWN ACTS. The model,
    # the prompt fingerprints, the flags and the pricing rule describe HOW these cards were
    # read and are as true of the rescue as of the source. `joined`, `emitted`, `counts`,
    # `usage`, `batch_ids` and `collected` are a record of what the SOURCE did; copied here
    # they would claim this run had submitted a batch, spent money and sent a file, none of
    # which it has.
    #
    # A RESCUE OF A RESCUE IS REACHABLE AND THIS SHAPE IS WHY IT IS SAFE. A rescue run carries
    # a `bid`, so a deleted-and-reused drawer strands it exactly as one stranded the run it
    # came from. Built as one dict and set once, this command's own three keys are simply
    # overwritten below — last write wins, and the derived run's figures are its own. Spelled
    # as `set(**carried, rescued_cards=...)` it was a `TypeError` on that second rescue, which
    # is the one shape of this that cannot be written down safely.
    written = {
        key: value
        for key, value in source.manifest.items()
        if key
        not in {
            "created_at",
            "updated_at",
            "scope",
            "joined",
            "emitted",
            "counts",
            "usage",
            "batch_ids",
            "collected",
            "capture_dir",
            "exports",
            "export",
            RESCUED_FROM,
        }
    }
    exports = _carry_exports(source, rescued)
    written[RESCUED_FROM] = source.name
    # THE BOX'S CAPTURE DIRECTORY, ASKED OF `store/photos.py` RATHER THAN SPELLED HERE.
    # It is still the LEGACY address, and that is the honest answer rather than an oversight:
    # a `capture_dir` is a directory `identify.sidecar.scan` could be pointed at, and the
    # content store is flat and shared — a run cannot be a directory of it.
    # `D183` §0.4 answers that with a built `.scopes/`
    # view of symlinks named `<idx:04d>.jpg`, and this line becomes that view's path when it
    # is. Until then the string is the one it always was, composed in the one module allowed
    # to compose it, so the change lands in one place.
    written["capture_dir"] = str(photos.legacy_box_dir(box))
    # THE SCOPE THE WHOLE REPAIR TURNS ON (D145). `bid` is what stops this run ever becoming
    # the thing it was derived from: box 3 may be deleted and its number reused tomorrow, and
    # this run will still say which drawer it was over.
    written["scope"] = {"box": box, "whole_box": False, "cards": len(moved), "bid": bid}
    written["rescued_cards"] = len(moved)
    written["rescued_left_behind"] = len(missing) + len(blind)
    if exports:
        written["exports"] = exports
    rescued.set(**written)
    say(f"wrote           {rescued.directory}")
    say(f"                {len(moved)} card(s) over box {box}, bid {bid}")
    if exports:
        say(f"                carried this run's export for {', '.join(sorted(exports))}")
    say(f"                {source.name} is unchanged")
    say("")
    say(f"Next:  ./pkmnscan join {rescued.directory}")
    say(f"       ./pkmnscan emit {rescued.directory}")
    return 0


def _carry_exports(source: runs.Run, rescued: runs.Run) -> Dict[str, dict]:
    """Copy the source's export files into the rescue and re-point the manifest at them.

    THE CATALOGUE IS THE SAME CATALOGUE, and carrying it is what makes the rescue joinable
    with no further input — the point of the exercise. It cannot be silently the wrong file:
    `cli/resolve.py:exports_for` re-reads every path and re-derives the game mapping off the
    rows' own `Product Line` cells rather than trusting what the manifest said (D25).

    THE PRICES IN IT ARE THE SOURCE RUN'S AND MAY BE OLD, and nothing here pretends
    otherwise — `join --export <fresh.csv>` re-prices, and `_readings` arbitrates newest-wins
    across every run table and live export on a clock (D86), so an old reading on this run's
    table does not reach a screen that has a newer one.
    """
    out: Dict[str, dict] = {}
    recorded = source.manifest.get("exports")
    if not isinstance(recorded, dict):
        return out
    for game, entry in recorded.items():
        if not isinstance(entry, dict) or not entry.get("path"):
            continue
        origin = Path(entry["path"])
        if not origin.is_file():
            continue
        target = rescued.path(origin.name)
        shutil.copy2(origin, target)
        carried = dict(entry)
        carried["path"] = str(target)
        carried["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        out[game] = carried
    return out


def _few(keys: List[str], limit: int = 4) -> str:
    shown = ", ".join(sorted(keys, key=_sort_key)[:limit])
    return shown if len(keys) <= limit else f"{shown}, +{len(keys) - limit} more"


__all__ = ["run", "RESCUED_FROM"]
