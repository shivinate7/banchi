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

D48 IS NARROWED, NOT REPEALED. That entry's subject is a RUN: one reading, one `--bypass`
ruling, one queue, one join. All of that stays per run and is untouched. What leaves the run
directory is the pricing ANSWER. The policy fields go too, on the owner's instruction, with a
per-run override kept for the lot that genuinely differs — see `for_run`.

THE FILE IS THE AUTHORITY AND THE RUN IS THE RECORD, which is D49 Part One unchanged and
pointed one level up: `join` still writes what it ran with into the manifest, and a record of
what happened is not an answer to what should happen.

NOTHING HERE READS THE STORE OR THE CATALOG. It holds answers, produces a
`pipeline/decisions.py:Decisions` for a run, and is otherwise inert — which is what lets
`join`, `emit` and every test written before it stay exactly as they are.
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
    sub_threshold: object = None
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
        return cls(
            rule=str(policy.get("rule", "match")),
            basis=str(policy.get("basis", "market")),
            sub_threshold=policy.get("sub_threshold"),
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
        ANSWERED. That is `Decisions.add_unpriced`'s job in the per-run world and it has to
        keep happening: a `no_market_data` key with a `null` value is precisely what makes
        `blocking` say the run owes an answer, and D9 forbids inventing one — *a missing price
        is an unknown price, never the floor by default*.
        """
        keys = set(wanted)
        over = self.overrides.get(run_name or "") or {}
        prices: dict = {}
        unknown: dict = {}
        for sku, answer in self.answers.items():
            if sku not in keys:
                continue
            (unknown if answer.channel == "unknown" else prices)[sku] = answer.value
        for sku in unpriced:
            if sku not in prices and sku not in unknown:
                unknown[sku] = None
        payload: dict = {
            "rule": over.get("rule", self.rule),
            "basis": over.get("basis", self.basis),
            "sub_threshold": over.get("sub_threshold", self.sub_threshold),
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
        return {
            "rule": over.get("rule", self.rule),
            "basis": over.get("basis", self.basis),
            "sub_threshold": over.get("sub_threshold", self.sub_threshold),
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


# ------------------------------------------------------------------ folding the run files in


@dataclass
class Change:
    """One SKU the migration had to choose an answer for, and what it chose."""

    sku: str
    kept: str
    dropped: List[Tuple[str, str]]
    hold_lost: bool


def adopt(run_answers: List[Tuple[str, dict]], corpus: Optional[Corpus] = None):
    """Fold per-run `decisions.json` documents into one corpus. Newest wins, changes reported.

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
    seen: Dict[str, List[Tuple[str, object]]] = {}
    for name, payload in run_answers:
        if not isinstance(payload, dict):
            continue
        for key in ("rule", "basis", "sub_threshold"):
            if payload.get(key) is not None:
                setattr(out, key, payload[key])
        for table in ("overrides", "no_market_data"):
            for sku, value in (payload.get(table) or {}).items():
                if value is None:
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
    return out, changes


def _is_hold(value: object) -> bool:
    if isinstance(value, dict):
        return decisions_mod.WITHHELD_KEY in value
    return str(value).strip().lower() == decisions_mod.pricing.UNLISTED


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
        return f"${Decimal(text).normalize()}"
    except (ArithmeticError, InvalidOperation, ValueError):
        # A value `Decisions.parse` will refuse later. Reported as typed rather than guessed.
        return text
