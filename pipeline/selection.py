"""WHICH CARDS A PRESS IS OVER — one object, and the drawer is one of its terms.

THE BOX STOPPED BEING THE UNIT OF WORK HERE. `server/pipeline_routes.py:_resolve_scope`
refused any request that did not name a positive integer `box` — *"A run is always scoped to
one box"* — and `pkmnscan identify` took exactly one directory. So "identify everything that
still needs it" was not a thing an operator could ask for, and a pile spanning two drawers was
two presses whatever the cards were.

THE TERMS ARE NAMES THE STORE ALREADY HAS FOR A GROUP OF CARDS, and that is the whole of the
design rule. Nothing here invents a grouping: `box` and `index` are `store/master.py:Card`'s
own two coordinates, `bid` is D145's true index, a section is the dividers somebody put in the
drawer (D10), `game` is D21's per-card claim, `state` is `master.STATES` verbatim, a key is
`identify/sidecar.py:Capture.key` — the same string the cache, the queues, the join and D174's
claim table are all keyed by — and `run` is a run directory's own card list. A term that
needed a new vocabulary would be a second answer to a question the store already answers.

EVERY TERM NARROWS AND NONE WIDENS, so the order they are applied in cannot change the answer
and there is no precedence to remember. The roots say which photographs are in view; each term
removes some of them. That is also what makes the empty answer safe to refuse rather than
having to be interpreted: nothing matched means these terms name no card, not that one term
overrode another.

THE ROOTS ARE PATHS AND THE TERMS ARE FACTS ABOUT CARDS, which is the one asymmetry worth
knowing. `captures/cards/box3` is a CONVENTION — `identify/sidecar.py`'s own header says the
box marker in a path is a recovery route and the sidecar is the claim — and this store has two
runs that prove it: `2026-08-29-box1-01`'s 99 cards and `2026-09-02-box6-01`'s 65 are all in
box 3 today, while the path says 1 and 6. So `--box 3` filters on what each capture RECORDED
and never on where the file sits, and pointing at a path is how you say "these photographs",
not "this drawer".

NOTHING HERE READS THE STORE OR THE DISK. `needs_store` and `needs_run` say what a caller has
to fetch, and `narrow` takes it as an argument — so the CLI pays for one snapshot it was going
to take anyway, a selection naming only sidecar-backed terms pays for none, and the harness can
drive every branch without a store at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from pipeline import games
from store import master
from store import photos

# HOW MANY KEYS ONE SELECTION MAY NAME. The bound is `ARG_MAX` and not a judgement about how
# many cards an operator may tick: `Selection.flags` puts the list in a child's argv, and Darwin
# caps argv-plus-environment at 1,048,576 bytes (`getconf ARG_MAX`, measured). A comma-joined
# list of 20,000 `box/index` keys is about 180 KB of that. The store holds 2,535 photographs and
# its largest drawer 887, so this is an order of magnitude above anything physical and an order
# of magnitude below the ceiling that would turn a big tick list into `E2BIG` — which is the
# failure mode worth bounding, because it arrives as an `OSError` from `Popen` rather than as a
# refusal anybody can read.
MAX_KEYS = 20_000

# A position key, `box/index`, exactly as `identify/sidecar.py:Capture.key` composes it. Both
# halves are positive integers with no padding: `store/master.py:position_key` is the other end
# of this string and `3/017` is not a key it would ever write.
KEY = re.compile(r"^([1-9][0-9]*)/([1-9][0-9]*)$")

# The capture root every box's directory sits under. Named here rather than imported from
# `server/pipeline_routes.py:box_capture_dir` for `cli/cmd_identify.py:_scope_for`'s reason —
# the pipeline does not depend on the server — and it is the same expression in both places.
CAPTURES = ("captures", "cards")


def _drawers(one: str, many: str, values: Sequence[int]) -> str:
    """`box 3`, `boxes 3 and 5`, `boxes 3, 4 and 5`. Sentences on screen, not machine strings.

    `docs/DESIGN.md`'s register rule reaches a refusal as much as a heading — this string is
    what the preflight's own report, the selection sentence and every refusal in
    `server/pipeline_routes.py` all print, so `boxes [3, 4, 5]` would be a Python repr leaking
    into the one line an operator reads before spending money.
    """
    names = [str(v) for v in values]
    if len(names) == 1:
        return f"{one} {names[0]}"
    if len(names) == 2:
        return f"{many} {names[0]} and {names[1]}"
    return f"{many} {', '.join(names[:-1])} and {names[-1]}"


class SelectionError(Exception):
    """A selection that cannot be read, or that names no card.

    TWO KINDS AND THE CALLER NEEDS TO TELL THEM APART, which is what `empty` is for. A term
    this cannot parse is the request's fault and is a 400; a well-formed selection that matched
    nothing is a 404, and `server/pipeline_routes.py` maps it to one. The CLI prints either and
    exits 1, because a terminal has no status codes to disagree about.
    """

    def __init__(self, code: str, message: str, *, empty: bool = False):
        super().__init__(message)
        self.code = code
        self.empty = empty


def _positives(raw: Any, term: str) -> Tuple[int, ...]:
    """`3` or `[3, 4, 5]` -> a tuple of drawer numbers, deduplicated and in order.

    A BARE INTEGER READS AS A LIST OF ONE, which is D48's own read-side widening applied to the
    thing that replaced it — every request ever written against `_resolve_scope` sent
    `{"box": 3}` and still means box 3, with no migration and no second spelling.

    THE LIST IS WHY THE ONE MULTI-DRAWER PRESS THIS STORE HAS MADE IS NOT A REGRESSION.
    Measured: on 2026-09-01T21:50:52 the operator sent boxes 3, 4 and 5 in one press — three
    run directories created in the same second, all `started_by: app` — so a selection that
    could name only one drawer would have taken a capability away. A filter naming three values
    is still one filter, one selection, one reading and ONE run, which is strictly less work
    downstream than the three runs that press actually produced.
    """
    values = raw if isinstance(raw, (list, tuple)) else [raw]
    if not values:
        raise SelectionError(
            "selection_invalid",
            f"`{term}` must be a positive integer or a non-empty array of them.",
        )
    out: List[int] = []
    for value in values:
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise SelectionError(
                "selection_invalid",
                f"`{term}` holds {value!r}, which is not a positive integer.",
            )
        if value not in out:
            out.append(value)
    return tuple(sorted(out))


@dataclass(frozen=True)
class Selection:
    """The cards a press is over, as it was asked for.

    FROZEN AND DERIVED-ONLY, so the thing that was quoted and the thing that is spent are the
    same object. D33's two-step gate is a preflight and a confirm over one selection, and the
    one way that gate fails in substance is the confirm describing a different send from the
    quote. `Selection` is built once per request from the payload, hashes and compares by
    value, and `flags` is a pure function of it — so the argv the preflight child gets and the
    argv the paid child gets are equal strings whenever the selections are equal.
    """

    # The directories whose photographs are in view. Empty means every capture in the store,
    # which is the one selection a terminal will not perform without `--all` being typed.
    paths: Tuple[str, ...] = ()
    state: Optional[str] = None
    # THE DRAWERS, AND IT IS A TUPLE BECAUSE ONE PRESS HAS NAMED THREE. `box` is the number on
    # the shelf and `bid` is D145's true index; both are filters over what each capture
    # recorded, and both accept one value or several. `section` below needs exactly one, because
    # a divider is a boundary inside one drawer.
    box: Optional[Tuple[int, ...]] = None
    bid: Optional[Tuple[int, ...]] = None
    section: Optional[int] = None
    game: Optional[str] = None
    since: Optional[str] = None
    keys: Optional[Tuple[str, ...]] = None
    run: Optional[str] = None

    # --------------------------------------------------------------- what it asks of a caller

    @property
    def named(self) -> bool:
        """Does this selection narrow anything at all?

        THE ONE PROPERTY THE TWO SURFACES DISAGREE ABOUT, and the disagreement is deliberate
        rather than a default that drifted. A selection that names nothing is every photograph
        in the store, and the two callers are not in the same position to be handed that: the
        screen has the free preflight and a confirm in front of it, and a terminal has a
        newline. So `cli/cmd_identify.py` refuses `not named` unless `--all` is typed, the
        route does not refuse it, and `flags` emits `--all` so the child the route spawns does
        not refuse itself. Both gates are written where they apply; neither is a default.
        """
        return bool(
            self.paths
            or self.state
            or self.box
            or self.bid
            or self.section
            or self.game
            or self.since
            or self.keys
            or self.run
        )

    @property
    def needs_store(self) -> bool:
        """Do any of these terms have to be looked up in the store?

        `box`, `game` and `keys` are answered by the sidecars alone — `Capture` carries all
        three — so the ordinary drawer press reads no store at all to decide what it is over.
        The four here cannot be: an id and a section are the registry's, and a state and a
        capture time are the card record's.
        """
        return bool(self.bid or self.section or self.state or self.since)

    @property
    def needs_run(self) -> bool:
        return bool(self.run)

    def roots(self, home: Path) -> List[Path]:
        """The directories to scan. The whole capture root where nothing was named.

        ONE ROOT RATHER THAN ONE PER BOX, AND THAT IS WHAT MAKES `--box` A FILTER. Scanning
        `captures/cards` finds the same 2,535 photographs in 0.386 s (measured) that five
        per-box scans would, and `identify/sidecar.py:position_from_path` still recovers a box
        from the `box3` directory above a photograph because it walks up as far as the root it
        was given. What it adds is that a card whose sidecar says box 3 is found by `--box 3`
        wherever the file happens to sit — which is the fault the two mis-filed runs above have
        and no narrower root can see.

        AND THE CONTENT-ADDRESSED STORE IS A SECOND DEFAULT ROOT, SINCE D172 (written in
        parallel with this module, neither seeing the other). `store/photos.write` is what
        `do_capture` has filed every photograph under from the moment D172 landed — the card's
        own name, under `<home>/photos/`, a sibling of `captures/cards/` and a directory this
        method never named until now. Left alone, a card captured after both changes merge
        scans as zero photographs FOREVER, on the one caller of this method that spends money
        (`server/pipeline_routes.py:do_pipeline_identify`, through the CLI child it spawns).
        `identify/sidecar.py`'s own header already carries the fourth filename convention for
        this exact layout — no index in a content-addressed name, position read off the
        SIDECAR instead, which `do_capture` writes with `box`/`index` on it — so the reader was
        ready; only the root list here was not.

        GUARDED BY AN EXISTENCE CHECK, so a store with nothing captured since D172 landed scans
        exactly as it always did — this can never raise `FileNotFoundError` for a directory
        that is not there, which matters because `cli/cmd_identify.py` treats that as a hard
        refusal for ANY root it is handed. And an explicit `paths` selection (a caller naming
        its own directories) is never widened behind its back.
        """
        if not self.paths:
            roots = [home.joinpath(*CAPTURES)]
            content_root = photos.root(home)
            if content_root.is_dir():
                roots.append(content_root)
            return roots
        return [Path(p) for p in self.paths]

    # -------------------------------------------------------------------------- the spellings

    def flags(self) -> List[str]:
        """This selection as the argv a child gets. The CLI's spelling of the same object.

        THE ROUTE SPAWNS `pkmnscan identify` AND NO LONGER BUILDS IT A DIRECTORY, which is the
        deletion this module exists for. `_scope_dir` symlinked the chosen photographs into
        `.scopes/box3-<n>-<stamp>` so that a subset could be expressed as the one thing
        `identify` accepted — a path. Measured on the owner's checkout: 264 such directories,
        every single one named `-1-`, so every one was built by the crop PREVIEW stepping one
        card at a time and not one of them was ever a submission. A flag says the same thing
        with nothing on disk to sweep.
        """
        out: List[str] = list(self.paths)
        if self.state:
            out += ["--state", self.state]
        if self.box:
            out += ["--box", ",".join(str(n) for n in self.box)]
        if self.bid:
            out += ["--bid", ",".join(str(n) for n in self.bid)]
        if self.section:
            out += ["--section", str(self.section)]
        if self.game:
            out += ["--game", self.game]
        if self.since:
            out += ["--since", self.since]
        if self.run:
            out += ["--run", self.run]
        if self.keys:
            out += ["--keys", ",".join(self.keys)]
        if not self.named:
            out.append("--all")
        return out

    def describe(self) -> Dict[str, Any]:
        """The selection on the wire and in the run's manifest: the terms that were SET.

        ABSENT RATHER THAN NULL, so a reader can tell a term nobody used from a term set to
        nothing. `_summary` and `runScope.ts` read the manifest's `scope` block for the drawer
        and D145's id; this block sits beside it and records what was ASKED FOR, which is the
        one fact those two cannot reconstruct — a run over box 3 and a run over the store that
        happened to find only box 3 are the same cards and different presses.
        """
        out: Dict[str, Any] = {}
        if self.paths:
            out["paths"] = list(self.paths)
        for term in ("state", "section", "game", "since", "run"):
            value = getattr(self, term)
            if value:
                out[term] = value
        # ALWAYS A LIST HERE, EVEN FOR ONE DRAWER, and that is the opposite of the input rule
        # one function up on purpose: `parse` widens so that no request has to be rewritten,
        # and this narrows so that no READER has to ask which shape it got before it can ask
        # anything else. D48 made exactly that argument about its response shape and it is the
        # half of that entry worth keeping.
        for term in ("box", "bid"):
            value = getattr(self, term)
            if value:
                out[term] = list(value)
        if self.keys:
            out["keys"] = list(self.keys)
        if not self.named:
            out["all"] = True
        return out

    def sentence(self) -> str:
        """What this press is over, in words, for a refusal and a report to agree on.

        COMPOSED ONCE FOR EVERY SITE, which is `store/submissions.py:conflict_sentence`'s rule
        one register over: a selection spelled one way by the command's report and another by
        the route's refusal is two things an operator has to learn to read as one.
        """
        parts: List[str] = []
        if self.paths:
            parts.append("under " + ", ".join(self.paths))
        if self.box:
            parts.append(_drawers("box", "boxes", self.box))
        if self.bid:
            parts.append(_drawers("drawer id", "drawer ids", self.bid))
        if self.section:
            parts.append(f"section {self.section}")
        if self.game:
            parts.append(str(games.get(self.game).get("label") or self.game))
        if self.state:
            parts.append(self.state)
        if self.since:
            parts.append(f"captured since {self.since}")
        if self.run:
            parts.append(f"the cards of run {self.run}")
        if self.keys:
            parts.append(f"{len(self.keys)} named card{'' if len(self.keys) == 1 else 's'}")
        return ", ".join(parts) if parts else "every photograph in the store"


# ------------------------------------------------------------------------------- reading one


def _keys_of(raw: Any) -> Tuple[str, ...]:
    """`["3/17", "4/210"]` -> the same, validated and deduplicated in position order.

    ONE BAD MEMBER REFUSES THE WHOLE LIST rather than being dropped from it, which is the rule
    the finish claim already follows and the rule the old `indices` followed. A selection that
    silently shed the key it could not read would be a press over fewer cards than the operator
    ticked, and `CLAUDE.md`'s standing rule is that a card is never silently dropped.
    """
    if not isinstance(raw, list) or not raw:
        raise SelectionError(
            "selection_invalid",
            "`keys` must be a non-empty array of `box/index` position keys. An empty array is "
            "refused rather than read as every card.",
        )
    if len(raw) > MAX_KEYS:
        raise SelectionError(
            "selection_invalid",
            f"{len(raw)} keys in one selection, and the limit is {MAX_KEYS}. The list reaches "
            f"a child's argv, which Darwin caps at 1 MB.",
        )
    out: List[str] = []
    for value in raw:
        if not isinstance(value, str) or not KEY.match(value):
            raise SelectionError(
                "selection_invalid",
                f"`keys` holds {value!r}, which is not a `box/index` position key.",
            )
        if value not in out:
            out.append(value)
    return tuple(sorted(out, key=lambda k: tuple(int(p) for p in k.split("/"))))


def _state_of(raw: Any) -> str:
    """One of `store/master.py:STATES`, which is the whole vocabulary and is not copied here.

    `master.check_state` IS THE READER, so this list cannot drift from the store's. A sixth
    state added there is selectable the same day with no edit in this file.

    `unjoined` WAS ASKED FOR AND IS NOT HERE, named rather than quietly dropped. It is a
    property of a RUN — whether that run has been joined against an export — and not of a card,
    so it would be a sixth value beside five real ones with a different kind of answer behind
    it. Nothing would identify an unjoined card either: the join is the next step over an answer
    already bought, not a re-read of the photograph. `--state identified` plus
    `--reidentify-stale` is the re-read, and `--run <name>` is how a run's own cards are named.
    """
    if not isinstance(raw, str):
        raise SelectionError("selection_invalid", f"`state` is {raw!r}, which is not a state.")
    try:
        return master.check_state(raw)
    except Exception:
        raise SelectionError(
            "selection_invalid",
            f"`state` is {raw!r}. The states a card can be in are "
            f"{', '.join(master.STATES)}.",
        ) from None


def _game_of(raw: Any) -> str:
    """A game the registry knows, refused by name where it does not.

    `games.get` IS THE READER for the same reason `check_state` is above, and the refusal is
    worth making here rather than letting the filter quietly match nothing: a mistyped game
    would otherwise be an empty selection reported as "these terms name no card", which blames
    the store for a typo.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise SelectionError("selection_invalid", f"`game` is {raw!r}, which is not a game.")
    key = raw.strip()
    try:
        games.get(key)
    except Exception:
        raise SelectionError(
            "selection_invalid",
            f"`game` is {key!r}, which is not a game this pipeline knows. D22 makes the "
            f"taxonomies hand-authored per game, so an unregistered one has no prompt and no "
            f"export scope.",
        ) from None
    return key


def _since_of(raw: Any) -> str:
    """An ISO-8601 instant, compared as a STRING and that is on purpose.

    `store/master.py` writes `captured_at` through one `now()`, so every stamp in the store is
    the same shape and lexicographic order IS chronological order over them. Parsing to
    `datetime` here would buy nothing and would introduce a timezone question the store does
    not have — and it would make a stamp the store wrote unreadable to the filter if either end
    ever normalised differently.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise SelectionError(
            "selection_invalid", f"`since` is {raw!r}, which is not an ISO-8601 instant."
        )
    value = raw.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?", value):
        raise SelectionError(
            "selection_invalid",
            f"`since` is {value!r}. It is an ISO-8601 instant — `2026-09-12` or "
            f"`2026-09-12T14:30:00` — compared against each card's `captured_at`.",
        )
    return value


def _run_of(raw: Any) -> str:
    """A run NAME, validated as a name and never joined onto a path blind.

    `server/pipeline_routes.py:_open_run`'s posture, applied here because this value reaches a
    directory read on both surfaces: `runs.create` builds `<date>-<slug>-<nn>` and nothing else
    ever should, so anything carrying a separator or a dot-dot is not a run name.
    """
    if not isinstance(raw, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", raw or ""):
        raise SelectionError("selection_invalid", f"`run` is {raw!r}, which is not a run name.")
    return raw


def parse(payload: Dict[str, Any]) -> Selection:
    """The wire's spelling: one JSON object, every term optional.

    `{"box": 3}` STILL MEANS BOX 3 AND THERE IS NO MIGRATION. Every request written against
    `_resolve_scope` named a positive integer `box` and nothing else was legal, so every one of
    them is a well-formed selection here and resolves to the same cards — the drawer press is
    one click and one field, exactly as it was.

    `indices` IS GONE AND IS NOT ACCEPTED. `{"box": 3, "indices": [17]}` and
    `{"keys": ["3/17"]}` are one idea spelled twice, and the second is the spelling the cache,
    the queues, the join and D174's claim table already use. `app/src/server.ts` composes the
    key from the handoff's box and indices, so the tick list is unchanged on the screen and
    there is exactly one shape on the wire. A payload still carrying `indices` is refused BY
    NAME rather than ignored: a filter that silently did nothing would be a press over the
    whole drawer reported as a press over one card.
    """
    if not isinstance(payload, dict):
        raise SelectionError("selection_invalid", "A selection is a JSON object.")
    if "indices" in payload:
        raise SelectionError(
            "selection_invalid",
            "`indices` is not a selection term. Name the cards as `keys`, a list of "
            "`box/index` position keys — the same spelling the cache, the queues and the join "
            "use. `{\"box\": 3, \"indices\": [17]}` is `{\"keys\": [\"3/17\"]}`.",
        )
    if "scopes" in payload:
        raise SelectionError(
            "selection_invalid",
            "`scopes` is not a selection term. A send is one selection over cards, not a cart "
            "of boxes — name the drawers' cards with `keys`, or the whole lot with `state`.",
        )

    raw_paths = payload.get("paths")
    paths: Tuple[str, ...] = ()
    if raw_paths is not None:
        if not isinstance(raw_paths, list) or not raw_paths:
            raise SelectionError(
                "selection_invalid",
                "`paths` must be a non-empty array of capture directories, or absent.",
            )
        for value in raw_paths:
            if not isinstance(value, str) or not value.strip():
                raise SelectionError(
                    "selection_invalid", f"`paths` holds {value!r}, which is not a path."
                )
        paths = tuple(value.strip() for value in raw_paths)

    selection = Selection(
        paths=paths,
        state=_state_of(payload["state"]) if payload.get("state") is not None else None,
        box=_positives(payload["box"], "box") if payload.get("box") is not None else None,
        bid=_positives(payload["bid"], "bid") if payload.get("bid") is not None else None,
        section=(
            _positives(payload["section"], "section")[0]
            if payload.get("section") is not None
            else None
        ),
        game=_game_of(payload["game"]) if payload.get("game") is not None else None,
        since=_since_of(payload["since"]) if payload.get("since") is not None else None,
        keys=_keys_of(payload["keys"]) if payload.get("keys") is not None else None,
        run=_run_of(payload["run"]) if payload.get("run") is not None else None,
    )
    return check(selection)


def check(selection: Selection) -> Selection:
    """The rules that are about two terms together rather than about either one.

    ONE READER FOR BOTH SURFACES. `parse` validates the wire and `cli/cmd_identify.py` builds
    the same object out of argparse, so a cross-term rule written in only one of them would
    hold on one surface and not the other — which is the shape D43's port bug had.
    """
    if selection.section is not None and len(selection.box or selection.bid or ()) != 1:
        raise SelectionError(
            "selection_invalid",
            "`section` names a divider inside ONE drawer, so it needs exactly one `box` or "
            "`bid` beside it. Section 2 is a different set of cards in every box, and a "
            "section number over three drawers would name three unrelated runs of cards.",
        )
    if selection.box is not None and selection.bid is not None:
        raise SelectionError(
            "selection_invalid",
            "`box` and `bid` both name a drawer — the number on the shelf and its true index "
            "(D145) — so naming both is two answers to one question. Send whichever you have.",
        )
    return selection


# ------------------------------------------------------------------------------- the filter


def narrow(
    selection: Selection,
    captures: Sequence[Any],
    *,
    inventory: Optional[master.Inventory] = None,
    run_keys: Optional[Callable[[str], Sequence[str]]] = None,
) -> List[Any]:
    """The captures this selection is over, in the order they were scanned.

    ORDER IS PRESERVED BECAUSE IT IS THE PRESS'S ORDER. `sidecar.scan` returns filename order
    and `cli/cmd_identify.py` walks that list to hash, prepare and submit, so re-sorting here
    would quietly reorder a batch's requests against the run report that describes it.

    A CAPTURE WITH NO POSITION SURVIVES EVERY POSITION TERM IT IS NOT ASKED ABOUT and is
    dropped by the ones it is. `identify/sidecar.py`'s first promise is that a card is never
    skipped — a photograph whose position could not be recovered is identified anyway and
    routed to the review queue flagged `no_position` — so an unpositioned capture under a path
    the operator named is still that press's business. What it cannot be is the answer to
    `--box 3`, because nothing knows whether it is in box 3. Measured on the owner's store:
    0 of 2,535 captures lack a position, so this arm is a rule rather than a workload.
    """
    out = list(captures)

    boxes: Optional[Tuple[int, ...]] = selection.box
    if selection.bid is not None:
        if inventory is None:  # pragma: no cover — a caller that ignored `needs_store`
            raise SelectionError("selection_invalid", "`bid` needs the store to resolve.")
        found: List[int] = []
        for bid in selection.bid:
            entry = inventory.box_by_id(bid)
            if entry is None:
                raise SelectionError(
                    "selection_invalid",
                    f"No drawer has true index {bid}. An id is fixed when the drawer is "
                    f"created and is never handed back out, so an unknown one is a typo "
                    f"rather than a deleted box.",
                )
            found.append(int(entry.box))
        boxes = tuple(sorted(set(found)))

    if boxes is not None:
        wanted_boxes = set(boxes)
        out = [c for c in out if c.box is not None and int(c.box) in wanted_boxes]

    if selection.section is not None:
        if inventory is None:  # pragma: no cover — a caller that ignored `needs_store`
            raise SelectionError("selection_invalid", "`section` needs the store to resolve.")
        # THE DIVIDERS SOMEBODY PUT IN THE BOX, AND NOTHING ELSE (D10 amended). An undeclared
        # box is ONE section — `Position.layout` falls back to `(1,)`, the divider at the front
        # of every drawer — so `--section 1` over an undeclared box is the whole drawer and
        # `--section 2` is refused rather than inventing a boundary at 25 cards.
        box = (boxes or (0,))[0]
        dividers = inventory.sections_for(box) or (1,)
        if not (1 <= selection.section <= len(dividers)):
            raise SelectionError(
                "selection_invalid",
                f"Box {box} has {len(dividers)} section"
                f"{'' if len(dividers) == 1 else 's'}, so there is no section "
                f"{selection.section}. A box's sections are the dividers somebody put in it.",
            )
        start = dividers[selection.section - 1]
        end = (
            dividers[selection.section]
            if selection.section < len(dividers)
            else None
        )
        # INDEX SPACE AND NOT SLOT SPACE, which is the side of D58 a photograph lives on. A
        # capture carries an `index` — the `/inventory/<box>/<index>` path its photograph is
        # named after and the key every write aims by — and `Place.slot` is the number a person
        # counts to, which differs by the cards that have departed in front of this one. The
        # dividers editor speaks slots and `join.divider_index` maps it back; a selection over
        # PHOTOGRAPHS has no slot to speak, because a departed card still has a photograph.
        out = [
            c
            for c in out
            if c.index is not None and c.index >= start and (end is None or c.index < end)
        ]

    if selection.game is not None:
        out = [c for c in out if c.game_or_default == selection.game]

    if selection.keys is not None:
        wanted = set(selection.keys)
        out = [c for c in out if c.has_position and c.key in wanted]

    if selection.run is not None:
        if run_keys is None:  # pragma: no cover — a caller that ignored `needs_run`
            raise SelectionError("selection_invalid", "`run` needs the run directory to read.")
        wanted = set(run_keys(selection.run))
        out = [c for c in out if c.has_position and c.key in wanted]

    if selection.state is not None or selection.since is not None:
        if inventory is None:  # pragma: no cover — a caller that ignored `needs_store`
            raise SelectionError("selection_invalid", "`state` needs the store to resolve.")
        # ONE PASS OVER THE CARD ROWS FOR BOTH TERMS. `Inventory.in_state` is a full-table
        # `Rows.where` — about a second on this store — so asking it once and reading
        # `captured_at` off the same objects is the difference between one pass and two.
        records = (
            inventory.in_state(selection.state)
            if selection.state is not None
            else list(inventory.cards.values())
        )
        if selection.since is not None:
            records = [
                card
                for card in records
                if isinstance(card.captured_at, str) and card.captured_at >= selection.since
            ]
        wanted = {f"{card.box}/{card.index}" for card in records}
        # A PHOTOGRAPH THE STORE HAS NO RECORD OF IS DROPPED BY THESE TWO TERMS AND NOTHING
        # ELSE. Both ask a question only a card record can answer, so a capture with no record
        # has no answer — and the honest reading of "the cards in state `captured`" is the ones
        # the store says are, not those plus the ones it has never heard of.
        out = [c for c in out if c.has_position and c.key in wanted]

    return out


def scope_block(
    captures: Sequence[Any],
    *,
    home: Path,
    inventory: Optional[master.Inventory] = None,
) -> Optional[Dict[str, Any]]:
    """WHICH DRAWER THIS RUN TURNED OUT TO BE OVER — the manifest's `scope`, from the cards.

    ONE IMPLEMENTATION, AND THERE WERE TWO. `cli/cmd_identify.py:_scope_for` built this block
    for a terminal run and `server/pipeline_routes.py:_resolve_scope` built it for a pressed
    one, and the only thing holding them together was a comment in each pointing at the other
    — T7's own assertion message says *"the shape `_resolve_scope` writes on the route"* about
    a call into the CLI's copy. Two functions asserted to agree by prose is the shape
    `make port-agreement` and `logo parity` exist to stop, and this one is small enough to
    simply not have twice.

    IT IS DERIVED FROM WHAT WAS READ AND NEVER FROM WHAT WAS ASKED FOR, which is why it is
    separate from `Selection.describe`. `scope` answers "which drawer is this run's cards in",
    which `_run_box`, `_run_box_id`, `refuse_reallocated` (D36) and `_summary`'s `box_name`
    (D56) all read; `describe` answers "what did the operator name", which none of them can
    reconstruct. A run over the whole store that happened to find only box 3 gets the same
    `scope` as a run over box 3 and a different `selection`.

    `None` FOR TWO DRAWERS, exactly as before (D48's rule, and the one part of it this entry
    keeps). A scope block naming one of two boxes would be a claim about cards it is wrong
    about, and the two runs on this store whose path says one drawer while their cards are in
    another are what that costs. What CHANGED is that being wrong is now the only thing a
    reader loses: `_run_box`'s path arm is gone, so a run with no scope block reads as "this
    run does not say", never as a confident number off a directory name.

    `whole_box` IS COUNTED RATHER THAN INFERRED FROM THE PATH. It used to be
    `capture_dir == captures/cards/boxN`, which cannot survive `--box 3` becoming a filter
    over a scan of the whole capture root — the path is the root now, not the drawer. So it
    asks the question the field has always MEANT: did this run read every photograph the
    drawer holds? One `glob`, and it is right for a press over the store that swept up all of
    box 3 as well as for a press aimed at it.
    """
    boxes = {int(c.box) for c in captures if c.box is not None}
    if len(boxes) != 1:
        return None
    box = boxes.pop()
    mine = [c for c in captures if c.box is not None and int(c.box) == box]
    own = home.joinpath(*CAPTURES) / f"box{box}"
    try:
        held = sum(
            1
            for path in own.iterdir()
            if path.is_file() and path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        )
    except OSError:
        # THE DRAWER'S OWN DIRECTORY IS NOT THERE OR WILL NOT OPEN, which is a real state on
        # this store: two runs point at capture directories that have since been deleted. Not
        # the whole box, because nothing can say it was — and `cards` then carries the count,
        # which is strictly more than the `null` a `whole_box` guess would have left.
        held = 0
    whole_box = held > 0 and len(mine) == held
    entry = inventory.box(box) if inventory is not None else None
    return {
        "box": box,
        "whole_box": whole_box,
        "cards": None if whole_box else len(mine),
        # ABSENT-AS-None RATHER THAN WRONG where the registry has no entry for the box
        # (D145/D165): a run with no id is read by the older rule, which is the arm that has
        # always worked.
        "bid": None if entry is None else master.int_or_none(entry.bid),
    }


def refuse_empty(selection: Selection, scanned: int) -> None:
    """The one refusal a well-formed selection can earn: it names no card.

    IT NAMES THE TERMS AND THE COUNT IT STARTED FROM, because those separate the three things
    an empty answer can mean — a mistyped box, a drawer whose cards are all identified already,
    and a capture root that is not there. `box_has_no_captures` could only ever say the first.
    """
    raise SelectionError(
        "selection_is_empty",
        f"Nothing to identify: {selection.sentence()} names no photograph, out of "
        f"{scanned} scanned.",
        empty=True,
    )
