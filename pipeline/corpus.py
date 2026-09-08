"""The pricing corpus — one listing answer per card, for the whole store (D86, amended).

WHY THIS FILE EXISTS, IN THE OWNER'S WORDS: *"why can't it be my front end is largely a
pricing corpus/dashboard of everything, with boxes feeding it? why is it we've made a
federalist state system when this is best done as a centralized system?"*

They are right, and the repo had already written down the evidence twice without acting on
it. D49 named the gap — *"no durable home for a hold outside the run directory; no cross-run
view of what is being held"* — and D62 repeated *"No cross-run view."*

THE ARGUMENT, WHICH IS ABOUT SCOPE AND NOT ABOUT TIDINESS. `runs/<n>/decisions.json` held two
different kinds of fact in one file:

    rule / basis / sub_threshold     arguably a property of the lot     (D48's argument)
    overrides / no_market_data       a property of the CARD             (D7's argument)

The second half is what a price actually is. TCGplayer prices per SKU globally, D7 states
*"price is per-SKU and shared across copies"*, and `pipeline/join.py` spends the live cap
against every box at once. Storing that answer inside a run directory means one card carries
one answer per drawer it has ever been photographed in — measured on this machine, 75 stored
rows for 66 distinct SKUs, **8 of them answered in more than one file**, and **3 of those a
`withheld` hold answered with a price in a later sitting**.

WHAT THAT COST, AND WHY IT IS NOT AN ABSTRACTION ARGUMENT. SKU 9191210 was held `bullish`
above $5 out of box 3 and listed at $3.45 out of box 4 the next day. Nothing could have said
so. The first build of D86 answered it with machinery — a fan-out write into N files,
conflict detection on the row, and an agreement refusal before a merged file could be written
— all of which exists only to reconcile a duplication that a single store does not have. The
conflict class stops existing here rather than being reported.

D48 IS NARROWED, NOT REPEALED. That entry's subject is a RUN: one reading, one queue, one
join. All of that stays per run and is untouched. What leaves the run
directory is the pricing ANSWER. The policy fields go too, on the owner's instruction, with a
per-run override kept for the lot that genuinely differs — see `for_run`.

THE FILE IS THE AUTHORITY AND THE RUN IS THE RECORD, which is D49 Part One unchanged and
pointed one level up: `join` still writes what it ran with into the manifest, and a record of
what happened is not an answer to what should happen.

NOTHING HERE READS THE STORE OR THE CATALOG. It holds answers, produces a
`pipeline/decisions.py:Decisions` for a run, and is otherwise inert — which is what lets
`join`, `emit` and every test written before it stay exactly as they are.

THE POLICY HAS ONE DEFAULT AND TWO KEYS READ IT. A `sub_threshold` the file leaves absent or
null reads as `DEFAULT_SUB_THRESHOLD` (D9, amended 2026-09-02), so a fresh store's first emit
is not refused for want of an answer the owner has already given once; a `threshold` the file
leaves out reads the SAME figure, because they are one variable (D99) and a store that has
chosen neither must not partition at one price and sell at another.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional, Tuple

from pipeline import decisions as decisions_mod, pricing

FILENAME = "prices.json"

#: The document version. Bumped only when a reader would get an OLD file wrong — a new
#: optional key is not a version change, because `parse` round-trips what it does not know.
VERSION = 1

#: THE STORE'S STANDING CUT-OFF WHEN THE POLICY IS SILENT — ONE FIGURE FOR BOTH KEYS (D99,
#: on the owner's ruling of 2026-09-03: *"threshold and cheap card are the same variable and
#: should be the same"*).
#:
#: THIS CONSTANT EXISTS BECAUSE THE MERGE PUT THE INVERSION BACK AT THE DEFAULT. D9's amendment
#: of 2026-09-02 gave `sub_threshold` a default of flat $0.49 so a fresh store's first emit is
#: not refused for want of an answer the owner has already given once; `threshold` separately
#: read `pricing.THRESHOLD`, $0.40. Both are reasonable alone and together they are the defect
#: D99 was written to end: a store that has set neither partitions at $0.40 and prices the half
#: below it at $0.49, so a card worth $0.38 lists ABOVE one worth $0.42 — the card that failed
#: the bar going out dearer than the one that cleared it, which is the whole of the argument.
#:
#: SO THE DEFAULT IS ONE VALUE READ BY BOTH KEYS, and the two cannot disagree unless somebody
#: writes them apart deliberately. D9's $0.40 derivation is not repealed — it is a labor bar
#: and it is still the argument for having a cut-off at all — but the figure a store that has
#: chosen nothing reads is the owner's, and they set it at $0.49 twice.
DEFAULT_CUTOFF: str = "0.49"

#: The same figure in the sub-threshold key's own `{"flat": "<price>"}` shape. Applied where
#: that key is ABSENT OR NULL and nowhere else — a file that says `"floor"` says floor. Applied
#: on READ, never written on read: `Corpus.read` serves GET routes, and the default reaches the
#: file on the next ordinary write (every join's `book.write()`, every `#/pricing` save).
DEFAULT_SUB_THRESHOLD: dict = {decisions_mod.FLAT_KEY: DEFAULT_CUTOFF}


@dataclass
class Answer:
    """One card's answer, and the provenance of it.

    THE SHAPES ARE D49's, UNCHANGED. A price is a string; a hold is `withheld` plus an optional
    `watch_above` and `note`. They are round-tripped rather than re-modelled so that
    `Decisions.parse` — the one parser for what an answer MEANS — stays the only one.

    `at` AND `from_run` ARE PROVENANCE AND NEVER INPUT. They say when this answer was written
    and, for a row the migration folded in, which run it came out of. Nothing prices from them;
    they exist so a corpus that absorbed eight run files can still be audited against them.
    """

    value: object
    at: Optional[str] = None
    from_run: Optional[str] = None
    #: Which of `decisions.json`'s two tables this answer belongs in — `"price"` for
    #: `overrides`, `"unknown"` for `no_market_data`.
    #:
    #: THE CHANNEL IS NOT COSMETIC AND DROPPING IT BROKE A GATE. `pipeline/decisions.py:
    #: blocking` reads `no_market_data` ALONE to decide whether `emit` must refuse, and
    #: `app/src/readiness.ts` mirrors it. Route a hand-entered answer for a card the catalog
    #: has no price for through `overrides` instead and `prices_for` still prices it correctly
    #: — layer 1 beats layer 2 — while `blocking` stops being able to see the channel at all.
    #: The screen would then report nothing owed for a run `emit` refuses.
    channel: str = "price"

    @property
    def is_hold(self) -> bool:
        if isinstance(self.value, dict):
            return decisions_mod.WITHHELD_KEY in self.value
        return str(self.value).strip().lower() == decisions_mod.pricing.UNLISTED


@dataclass
class Corpus:
    """Every answer, plus the standing policy.

    `unknown` IS THE ROUND-TRIP AND IT IS LOAD-BEARING. `PUT /pricing` replaces this document
    wholesale, so a key a later version adds — or `_note`, which a person writes by hand —
    must survive a screen that has never heard of it. D49 gave `decisions.json` the same
    property for the same reason and it is the reason `to_payload` is not a field list.
    """

    rule: str = "match"
    basis: str = "market"
    sub_threshold: object = field(default_factory=lambda: dict(DEFAULT_SUB_THRESHOLD))
    #: The D9 cut-off, as the string it was typed as. `DEFAULT_CUTOFF` is the default, and it
    #: is the SAME figure `sub_threshold` falls back to — see that constant for why they may
    #: not differ.
    #:
    #: IT IS POLICY AND NOT AN ANSWER, which is why it sits here beside `rule` and `basis`
    #: rather than in `skus`. D9 calls the threshold *"configurable"* and derives $0.40 from a
    #: labor bar; a labor bar is a fact about the operator's hour, not about any one card, and
    #: a per-SKU cut-off is just a per-SKU price with extra steps. Stored as a STRING for the
    #: reason every price in this file is: `Decimal` is not JSON, and the figure the operator
    #: typed is the figure that comes back.
    #:
    #: IT SHARES `sub_threshold`'s DEFAULT AND THE SYMMETRY IS THE POINT. The two were
    #: asymmetric for a day — a defaulted cheap price beside a constant threshold — and the
    #: pair inverted. One figure, one fallback.
    threshold: object = DEFAULT_CUTOFF
    #: How many copies of one SKU may be live at TCGplayer at once, or `None` for NO CAP —
    #: which is the ordinary value since D7 was rewritten (2026-09-07). Store-wide, and
    #: overridable per run through `policy.per_run` like the four keys above it — the run-level
    #: override D86 named as its own reopening condition, and this is its FIRST WRITER. A lot
    #: that genuinely wants a different exposure is exactly the case D7's "configurable" was
    #: about, and the store-wide figure is the one that answers for everything else.
    #:
    #: THE DEFAULT WAS STILL `LIVE_QUANTITY_CAP` UNTIL 2026-09-08, WHICH LEFT D7's REWRITE
    #: UNFINISHED. `Corpus.parse` reads an absent key as `None` correctly, so a store with a
    #: file was answered right — but a DEFAULT-CONSTRUCTED corpus carried four, and
    #: `to_payload` writes this key unconditionally, so the first save of a fresh store wrote
    #: the retired bound into `policy` where every later read would find it. The one caller
    #: that matters is `server/pipeline_routes.py`'s fallback for a corpus it could not read:
    #: it invented a cap nobody had set, which is exactly what `live_cap_for`'s own except
    #: arm was changed to stop doing.
    live_cap: object = None
    answers: Dict[str, Answer] = field(default_factory=dict)
    #: run name -> the policy keys that run overrides. Empty for every run that takes the
    #: standing policy, which is expected to be almost all of them.
    overrides: Dict[str, dict] = field(default_factory=dict)
    unknown: dict = field(default_factory=dict)

    # ------------------------------------------------------------------------ reading

    @classmethod
    def parse(cls, payload: Optional[dict]) -> "Corpus":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise decisions_mod.MalformedDecisions(
                f"{FILENAME}: expected an object, got {type(payload).__name__}"
            )
        policy = payload.get("policy") or {}
        answers: Dict[str, Answer] = {}
        for sku, row in (payload.get("skus") or {}).items():
            if row is None:
                # `null` DROPS AN ANSWER AND NEVER ROUND-TRIPS — D49's rule for clearing a key,
                # kept identical here so a screen clears an answer the way it always has.
                continue
            if isinstance(row, dict) and "value" in row:
                answers[str(sku)] = Answer(
                    value=row["value"],
                    at=row.get("at"),
                    from_run=row.get("from_run"),
                    channel=str(row.get("channel") or "price"),
                )
            else:
                # A BARE VALUE IS AN ANSWER WITH NO PROVENANCE, which is what a person editing
                # this file by hand will write. Accepted for the reason D49 accepts a bare
                # `"unlisted"`: the spelling a terminal user reaches for has to work.
                answers[str(sku)] = Answer(value=row)
        keep = {k: v for k, v in payload.items() if k not in ("policy", "skus", "version")}
        # VALIDATED AT READ TIME, SO THE REFUSAL LANDS WHERE A COMMAND IS ALREADY CATCHING IT.
        # `rule` and `basis` are round-tripped as STRINGS here — the corpus stores what was
        # written — so nothing in this class would have raised on `undercut:not-a-number`, and
        # the `UnknownRule` surfaced later at `pricing.Rule.parse` in the middle of `emit`,
        # outside every `except` that exists to turn it into a sentence. D49 recorded this
        # exact shape once already: these are `ValueError`s, not `MalformedDecisions`, and
        # nothing above `cli/__main__.py` catches them. The results are discarded; only the
        # raising matters.
        pricing.Rule.parse(policy.get("rule", "match"))
        pricing.check_basis(policy.get("basis", "market"))
        # VALIDATED HERE FOR THE SAME REASON AND WITH ONE DIFFERENCE: the parsed value is
        # discarded like the two above, but a MISSING key is the store that has never set one
        # and reads `DEFAULT_CUTOFF`, where a present-and-unusable one is refused by name.
        pricing.check_threshold(policy.get("threshold"))
        # VALIDATED AT READ TIME LIKE THE OTHERS, and by the same parser `Decisions.parse`
        # uses, so a store whose policy holds `live_cap: 0` refuses when the file is opened
        # rather than emitting nothing for every SKU and looking like a broken pipeline.
        decisions_mod.parse_live_cap(policy.get("live_cap"))
        # THE ONE KEY WITH A DEFAULT VALUE, AND ONLY WHERE THE FILE IS SILENT. Absent or `null`
        # reads as `DEFAULT_SUB_THRESHOLD`; `"floor"` and a written flat price are what they
        # say. Validated ONCE here, by the parser `Decisions.parse` uses, for the argument the
        # comment above makes for `rule`: a malformed policy refuses at read time, where
        # `cli/cmd_join.py` and `cli/cmd_emit.py` already catch `MalformedDecisions`.
        sub_threshold = policy.get("sub_threshold")
        if sub_threshold is None:
            sub_threshold = dict(DEFAULT_SUB_THRESHOLD)
        decisions_mod.parse_sub_threshold(sub_threshold)
        return cls(
            rule=str(policy.get("rule", "match")),
            basis=str(policy.get("basis", "market")),
            sub_threshold=sub_threshold,
            threshold=(
                DEFAULT_CUTOFF
                if policy.get("threshold") is None
                else str(policy["threshold"]).strip()
            ),
            live_cap=decisions_mod.parse_live_cap(policy.get("live_cap")),
            answers=answers,
            overrides={
                str(name): dict(over)
                for name, over in (policy.get("per_run") or {}).items()
                if isinstance(over, dict)
            },
            unknown=keep,
        )

    @classmethod
    def read(cls, path: Optional[Path] = None) -> "Corpus":
        """The corpus, or an empty one. A missing file is not an error.

        A STORE THAT HAS NEVER PRICED ANYTHING IS NOT A BROKEN STORE, which is the same
        posture `cli/runs.py` takes to a runs directory that does not exist yet. The first
        answer creates the file.
        """
        from store import files  # local: `pipeline/` must not import `store/` at module scope

        target = Path(path) if path is not None else files.prices_path()
        if not target.is_file():
            return cls()
        try:
            return cls.parse(json.loads(target.read_text("utf-8")))
        except json.JSONDecodeError as exc:
            raise decisions_mod.MalformedDecisions(f"{target}: {exc}") from exc

    # ------------------------------------------------------------------------ writing

    def to_payload(self) -> dict:
        out = dict(self.unknown)
        policy: dict = {
            "rule": self.rule,
            "basis": self.basis,
            "sub_threshold": self.sub_threshold,
            # WRITTEN EVEN WHEN IT IS THE DEFAULT, unlike `per_run` below. `#/pricing` reads
            # `policy.threshold` to draw the control, and a key that appears only once
            # somebody has changed it is a control that cannot draw its own current value.
            "threshold": self.threshold,
            # WRITTEN ALWAYS, FOR `threshold`'S REASON. A screen that lets the operator set
            # the cap has to be able to draw the figure standing now, and a key that appears
            # only after somebody changes it cannot show its own current value.
            "live_cap": self.live_cap,
        }
        if self.overrides:
            policy["per_run"] = self.overrides
        out["version"] = VERSION
        out["policy"] = policy
        out["skus"] = {
            sku: {
                "value": answer.value,
                **({"at": answer.at} if answer.at else {}),
                **({"from_run": answer.from_run} if answer.from_run else {}),
                **({"channel": answer.channel} if answer.channel != "price" else {}),
            }
            for sku, answer in sorted(self.answers.items())
        }
        return out

    def write(self, path: Optional[Path] = None) -> Path:
        from store import files

        target = Path(path) if path is not None else files.prices_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        files.write_json(target, self.to_payload())
        return target

    # ------------------------------------------------------------------------ using

    def for_run(self, run_name: str) -> decisions_mod.Decisions:
        """This corpus as the `Decisions` one run is priced with.

        THE WHOLE POINT OF THIS METHOD IS THAT NOTHING DOWNSTREAM CHANGED. `join`, `emit`,
        `prices_for` and every harness case already take a `Decisions`; handing them one built
        from the corpus means the pipeline never learns that answers moved, which is the same
        property D48 spent its length protecting when the CART changed and the run did not.

        THE PER-RUN OVERRIDE IS POLICY ONLY, AND DELIBERATELY NOT PER-SKU. A lot of commons
        can want a different `sub_threshold` from a lot of hits — that is D48's argument and it
        survives. A per-SKU override would re-create the duplication this file exists to end,
        so there is no shape here that can express one.

        EVERY ANSWER GOES TO EVERY RUN, and the filtering happens in `prices_for`, which walks
        the report's own matches. A corpus answer for a card this run does not hold is simply
        never reached — except by `sku_dispositions`' unknown-key check, which is why the
        payload below routes answers through `overrides`/`no_market_data` exactly as a run file
        did and lets `Decisions.parse` decide which is which.
        """
        return self._decisions(run_name, self.answers.keys(), ())

    def _decisions(
        self, run_name: Optional[str], wanted: Iterable[str], unpriced: Iterable[str]
    ) -> decisions_mod.Decisions:
        """One `Decisions`, built from the corpus, for the SKUs named.

        THE TWO TABLES ARE KEPT APART BY `Answer.channel` — see that field for the gate that
        breaks when they are not.

        `unpriced` SEEDS A NULL FOR EVERY CARD THIS RUN COULD NOT PRICE AND THE CORPUS HAS NOT
        ANSWERED. That was `Decisions.add_unpriced`'s job in the per-run world (gone with D86's
        amendment) and it has to keep happening: a `no_market_data` key with a `null` value is
        precisely what makes `blocking` say the run owes an answer, and D9 forbids inventing one
        — *a missing price is an unknown price, never the floor by default*.
        """
        keys = set(wanted)
        prices: dict = {}
        unknown: dict = {}
        for sku, answer in self.answers.items():
            if sku not in keys:
                continue
            # AN ALLOW-LIST, AND IT WAS A DENY-LIST UNTIL 2026-09-06. It read
            # `unknown if channel == "unknown" else prices`, so EVERY value but one landed in
            # `overrides` — the table `pipeline/join.py:prices_for` consults FIRST, which
            # beats the rule, the market and the sub-threshold policy, for every future copy
            # out of every future box. A channel nobody had thought of yet would therefore
            # have priced cards, silently, in the money direction.
            #
            # `docs/specs/tcgplayer-portal-api.md` §4 rule 4 states this repo's position on
            # the shape — "Never a deny-list. A guard that blocks named-dangerous calls fails
            # open on the one nobody named" — and it was written after a dry-run interceptor
            # built from the wrong names let 100 real rows reach TCGplayer. The same shape was
            # sitting on the file that decides what every card lists at. An unrecognised
            # channel now falls to `no_market_data`, which `pipeline/decisions.py:blocking`
            # reads as "this card is not answered" and refuses the emit over: the safe
            # direction is the one that stops rather than the one that prices.
            (prices if answer.channel == "price" else unknown)[sku] = answer.value
        for sku in unpriced:
            if sku not in prices and sku not in unknown:
                unknown[sku] = None
        payload: dict = {
            **self.policy_for(run_name),
            "overrides": prices,
            "no_market_data": unknown,
        }
        return decisions_mod.Decisions.parse(payload)

    def policy_for(self, run_name: Optional[str] = None) -> Dict[str, object]:
        """The standing policy, with this run's override folded over it.

        SEPARATE FROM `scoped_to` BECAUSE THE TWO ARE NEEDED AT DIFFERENT MOMENTS.
        `cli/resolve.py:load` prices every match and so needs `rule` and `basis` BEFORE the
        matches exist; the per-SKU answers cannot be scoped until they do. One document, two
        reads, rather than a document read twice.
        """
        over = self.overrides.get(run_name or "") or {}
        # AN EXPLICIT `null` IN AN OVERRIDE MEANS "TAKE THE STANDING POLICY", not "unset": the
        # standing key can no longer be null after `parse`, and an override that could put a
        # null back would reopen the refusal the default exists to end.
        # `threshold` RIDES THE SAME RULE AS THE OTHER THREE. NOTHING HERE IS PARSED:
        # `check_basis` and `check_threshold` are called by the CALLER for the same reason —
        # this method answers what the policy SAYS, and the commands that price from it
        # already catch the refusal a bad value raises.
        standing = {
            "rule": self.rule,
            "basis": self.basis,
            "sub_threshold": self.sub_threshold,
            "threshold": self.threshold,
            "live_cap": self.live_cap,
        }
        return {
            key: (over[key] if over.get(key) is not None else value)
            for key, value in standing.items()
        }

    def scoped_to(
        self,
        skus: Iterable[str],
        *,
        run_name: Optional[str] = None,
        unpriced: Iterable[str] = (),
    ) -> decisions_mod.Decisions:
        """`for_run`'s answers narrowed to the SKUs a batch actually holds.

        `cli/cmd_emit.py` REFUSES WHEN A DISPOSITION NAMES A SKU THE BATCH DOES NOT HOLD, and
        that check is right for a run file — a name in it that matches nothing is a typo. It is
        WRONG for a corpus, which holds every card this operator has ever priced and is
        expected to name thousands the run in front of it does not. The narrowing happens here
        rather than by weakening the check, because the check is what catches a real typo.
        """
        return self._decisions(run_name, skus, unpriced)


# ------------------------------------------------------------------ provenance and the digest


def revision(path: Optional[Path] = None) -> str:
    """A short digest of the corpus as it stands on disk, or `""` if there is no file.

    ONE IMPLEMENTATION, FOR BOTH WRITERS, AND THAT IS THE WHOLE REASON IT IS HERE. This was
    `server/pipeline_routes.py:_corpus_revision` and served the route alone, so `PUT /pricing`
    was guarded against a stale write while `pkmnscan reprice apply` and `prices adopt` — which
    read-modify-write the same file from a subprocess — were not. `cli/` may not import
    `server/`, so the guard could not be shared until it moved down here.

    IT ALSO CLOSES A HAZARD THE ROUTE'S OWN TEST NAMES. `check_corpus_revision`'s header warns
    that a digest CACHE in the route would leave a route-only test green while the real refusal
    silently stopped firing. One reader of the file, for every writer, is what makes that
    unrepresentable rather than merely untested.

    OUT OF BAND, IN THE ENVELOPE, AND NEVER INSIDE THE DOCUMENT. `#/pricing` decides "unsaved"
    by comparing the corpus object it holds against the one it last sent, BY IDENTITY. A
    revision inside the document would mean rebuilding that object every time a write lands,
    which is the endless unsaved -> saving -> unsaved oscillation that screen was built to
    avoid.
    """
    import hashlib

    from store import files  # local: `pipeline/` must not import `store/` at module scope

    target = Path(path) if path is not None else files.prices_path()
    if not target.is_file():
        return ""
    return hashlib.sha256(target.read_bytes()).hexdigest()[:16]


def stamp_answers(before: "Corpus", after: "Corpus", at: str) -> List[str]:
    """Stamp `at` on every PRICE answer in `after` that `before` did not already hold, in place.

    Returns the SKUs stamped, so a caller can say how many answers it just dated.

    PURE, AND THE CLOCK COMES FROM THE CALLER — `pipeline/reprice.py:plan` takes its `now` the
    same way and for the same reason: a module that reads a clock cannot be driven by a test
    that wants to be at a particular moment.

    WHY IT EXISTS. `Answer.at` was written in exactly ONE place in this repo,
    `cli/cmd_reprice.py`'s apply, and read in exactly one, that command's own ratchet. So
    `priced_recently` meant "this store MARKED THIS DOWN recently" while D100 claimed it meant
    *"a card the operator hand-priced on `#/pricing` yesterday is not stale"*. It did not: the
    screen has never stamped anything. Hand-price fifty live listings and every one of them
    still read as stale the next morning.

    THREE RULES, AND EACH ONE IS LOAD-BEARING.

    1. DIFF-BASED, NEVER BLANKET. `#/pricing` PUTs the WHOLE document on every debounced save.
       Stamping unconditionally moves every answer's `at` to now on every keystroke, and the
       entire corpus reads `priced_recently` forever — the ratchet inverted into a permanent
       refusal. An answer whose value and channel are unchanged keeps the `at` it has.

    2. `channel == "price"` ONLY. `cli/cmd_join.py` seeds `Answer(value=None,
       channel="unknown")` for every card the catalog could not price, and `join` writes the
       book. Those are not answers; they are the ABSENCE of one, and `pipeline/decisions.py:
       blocking` reads that table to refuse an `emit`. Stamping them would make an UNPRICED
       card read as priced, which is the opposite of the truth in the one direction that costs
       money.

    3. A HOLD IS NOT A PRICE. `Answer.is_hold` covers both spellings — the `withheld` dict and
       a bare `unlisted` — and the ratchet already excludes holds on the read side. Stamping
       one would date a decision NOT to list as though it were a listing.

    NOT CALLED BY `prices adopt`. A folded run answer's real time is unknown, and `from_run` is
    the provenance that migration owes; inventing an `at` for it would date every adopted answer
    to the migration and refuse the whole corpus as `priced_recently` on the next survey.
    """
    stamped: List[str] = []
    for sku, answer in after.answers.items():
        if answer.channel != "price" or answer.is_hold:
            continue
        # THE COMPARISON IS ON THE ANSWER, NOT ON THE STAMP. `_token` folds `0.50` and `0.5`
        # into one answer for D86's reason, and the same fold has to apply here or a screen
        # that round-trips a price through a text field re-dates it on every save.
        previous = before.answers.get(sku)
        if (
            previous is not None
            and not previous.is_hold
            and previous.channel == answer.channel
            and _token(previous.value) == _token(answer.value)
        ):
            answer.at = previous.at
            continue
        answer.at = at
        stamped.append(sku)
    return stamped


# ------------------------------------------------------------------ folding the run files in


@dataclass
class Change:
    """One SKU the migration had to choose an answer for, and what it chose."""

    sku: str
    kept: str
    dropped: List[Tuple[str, str]]
    hold_lost: bool


@dataclass
class Kept:
    """One SKU a run file answers that the corpus already answers, left as the corpus has it.

    THE CORPUS'S ANSWER IS THE NEWER FACT. After the first adoption every answer is written on
    `#/pricing` into the corpus, and a run file that still names the SKU is the older sitting
    by construction — so a re-adopt keeps the corpus and REPORTS the file, and only `--force`
    reverses that. `in_file` and `in_corpus` are `_token`s, so the line can say whether the
    two actually differ.
    """

    sku: str
    run: str
    in_file: str
    in_corpus: str


def adopt(
    run_answers: List[Tuple[str, dict]],
    corpus: Optional[Corpus] = None,
    *,
    replace: bool = True,
) -> Tuple[Corpus, List[Change], List[Kept]]:
    """Fold per-run `decisions.json` documents into one corpus. Newest wins, changes reported.

    `replace=True` IS THE FIRST ADOPTION: every answer in a file lands over the base, newest
    file last, and the policy is the newest run's that stated one. `replace=False` IS EVERY
    ADOPTION AFTER IT: a SKU the corpus already answers is left alone and returned as a
    `Kept`, a SKU it does not is added, and the three policy keys are never touched. Both
    fold into the corpus handed in — never into a fresh one, which would drop every answer
    written on `#/pricing` since the last fold.

    `run_answers` is `(run name, parsed document)` OLDEST FIRST — run names are date-prefixed,
    so that is the directory order. The last writer wins, which is the owner's ruling on this
    migration: *"Newest run wins, flag what changed."*

    IT REPORTS EVERY OVERWRITE AND MARKS THE ONES THAT COST SOMETHING. Three of the eight
    contested SKUs on this machine are a `withheld` hold answered by a later price — the
    direction that lost money, because a hold is a deliberate "not this one" and the price that
    replaced it was typed by somebody who could not see it. Newest-wins resolves those to the
    price. `hold_lost` is how the report says so, and it is the reason this returns a list of
    `Change` rather than just writing.

    THE POLICY COMES FROM THE NEWEST RUN THAT STATED ONE, for the same reason and with the same
    caveat: measured, the three answers to `sub_threshold` on this machine are `.49`, `floor`
    and `.5`, given in three sittings within eleven minutes of each other. That reads as drift
    rather than as three deliberate lot decisions, which is the owner's reason for making
    policy global at all.
    """
    out = corpus or Corpus()
    # SNAPSHOTTED BEFORE THE WALK, so two files naming one SKU the corpus does not hold still
    # resolve newest-wins between themselves rather than the second reading as "already held".
    already = set(out.answers) if not replace else set()
    # AND IN REPLACE MODE THE CORPUS'S OWN ANSWER IS THE OLDEST ENTRY IN THE HISTORY, so a
    # `--force` that folds a run's price over a hold set on `#/pricing` reports it as the
    # hold-lost change it is, rather than as a SKU nobody disagreed about.
    prior = {sku: answer for sku, answer in out.answers.items()} if replace else {}
    seen: Dict[str, List[Tuple[str, object]]] = {}
    kept: List[Kept] = []
    for name, payload in run_answers:
        if not isinstance(payload, dict):
            continue
        if replace:
            for key in ("rule", "basis", "sub_threshold"):
                if payload.get(key) is not None:
                    setattr(out, key, payload[key])
        for table in ("overrides", "no_market_data"):
            for sku, value in (payload.get(table) or {}).items():
                if value is None:
                    continue
                if str(sku) in prior and str(sku) not in seen:
                    held = prior[str(sku)]
                    seen[str(sku)] = [(held.from_run or "corpus", held.value)]
                if str(sku) in already:
                    kept.append(
                        Kept(
                            sku=str(sku),
                            run=name,
                            in_file=_token(value),
                            in_corpus=_token(out.answers[str(sku)].value),
                        )
                    )
                    continue
                seen.setdefault(str(sku), []).append((name, value))
                out.answers[str(sku)] = Answer(
                    value=value,
                    from_run=name,
                    channel="unknown" if table == "no_market_data" else "price",
                )

    changes: List[Change] = []
    for sku, history in seen.items():
        if len(history) < 2:
            continue
        tokens = {_token(value) for _, value in history}
        if len(tokens) < 2:
            # SAME ANSWER IN TWO FILES IS NOT A CHANGE. Four of the eight contested SKUs are
            # `0.5` against `.5` — one figure typed twice — and reporting those would bury the
            # three that matter under noise nobody needs to read.
            continue
        kept_run, kept_value = history[-1]
        changes.append(
            Change(
                sku=sku,
                kept=f"{_token(kept_value)} ({kept_run})",
                dropped=[
                    (name, _token(value))
                    for name, value in history[:-1]
                    if _token(value) != _token(kept_value)
                ],
                hold_lost=(
                    any(_is_hold(value) for _, value in history[:-1])
                    and not _is_hold(kept_value)
                ),
            )
        )
    return out, changes, kept


def retirable(run_answers: List[Tuple[str, dict]], corpus: Corpus) -> List[str]:
    """The run names whose every answered SKU the corpus now answers — the files `adopt` may retire.

    A FILE IS RETIRED ONLY WHEN NOTHING IN IT IS LOST, and "lost" is measured against the
    corpus rather than against what this fold added: a re-adopt that kept the corpus's answer
    for a SKU still leaves that SKU answered, so the file naming it has nothing left to say.
    A file the fold could not read is never in `run_answers` and so is never here.
    """
    out: List[str] = []
    for name, payload in run_answers:
        if not isinstance(payload, dict):
            continue
        answered = {
            str(sku)
            for table in ("overrides", "no_market_data")
            for sku, value in (payload.get(table) or {}).items()
            if value is not None
        }
        if answered <= set(corpus.answers):
            out.append(name)
    return out


def _is_hold(value: object) -> bool:
    if isinstance(value, dict):
        return decisions_mod.WITHHELD_KEY in value
    return str(value).strip().lower() == decisions_mod.pricing.UNLISTED


def live_cap_for(run_name: Optional[str] = None) -> Optional[int]:
    """The live cap standing right now, store-wide or for one run. Never raises.

    FOR THE READ PATHS, which are the servers. `#/pricing`, `#/runs` and the copy map all draw
    the cap, and a screen that cannot draw it because the corpus is momentarily unreadable is
    worse than one drawing D7's default — the figure is advisory on those surfaces, and the
    write paths (`join`, `emit`) parse the policy properly and refuse a bad one. So a malformed
    or missing file falls back here rather than taking a read route down.
    """
    try:
        return decisions_mod.parse_live_cap(
            Corpus.read().policy_for(run_name).get("live_cap")
        )
    except Exception:  # noqa: BLE001 - a read surface never fails over an advisory figure
        # `None` — NO CAP — is the fallback since D7 was rewritten, and it matches what an unreadable
        # policy most likely says: nothing. Falling back to a NUMBER here would invent a bound
        # the operator did not set, on a screen, from a file this could not read.
        return None


def _token(value: object) -> str:
    """An answer as a comparable string. `0.50` and `0.5` are ONE answer, for D86's reason."""
    if isinstance(value, dict):
        reason = value.get(decisions_mod.WITHHELD_KEY, "")
        watch = value.get(decisions_mod.WATCH_KEY)
        return f"held: {reason}" + (f" above ${watch}" if watch else "")
    text = str(value).strip()
    if text.lower() == decisions_mod.pricing.UNLISTED:
        return "unlisted"
    try:
        # `normalize()` IS THE COMPARISON AND `_plain` IS THE RENDERING, and they were one
        # call until 2026-09-06. Normalising folds `0.50` and `0.5` into one answer, which is
        # the whole point — and it also folds `7000.00` into `7E+3`, because that is what
        # `Decimal.normalize` does to a round number of at least 100. Every string here is
        # printed to the operator by `cli/cmd_prices.py`, so the two highest-value figures
        # this repo has ever handled — a $7,000 listing and a $750 test publish — both
        # rendered as exponents in the report that names what a price was changed to.
        return f"${_plain(Decimal(text).normalize())}"
    except (ArithmeticError, InvalidOperation, ValueError):
        # A value `Decisions.parse` will refuse later. Reported as typed rather than guessed.
        return text


def _plain(number: Decimal) -> str:
    """A normalised `Decimal` as digits, never scientific notation.

    `Decimal("7000.00").normalize()` is `Decimal("7E+3")` and `str()` of it says so. The fix
    is `quantize` back to a whole exponent, which is exact for a value that only LOST
    trailing zeros — the case `normalize` produces — and cannot lose a significant digit.
    Small values are unaffected: `0.49` normalizes to itself.
    """
    if number == number.to_integral_value() and number.as_tuple().exponent > 0:
        return str(number.quantize(Decimal(1)))
    return str(number)
