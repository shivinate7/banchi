"""`submissions` — the cards a live run has claimed and is about to pay to read.

THE ONE BINDING IN THIS PIPELINE THAT PROTECTS A DOLLAR, AND IT USED TO BE A BOX NUMBER.
`server/pipeline_routes.py:_busy_run` refuses a second `identify` press while a live run is
reading the same BOX, and that is the whole of it. The identification cache cannot stand in
for it: a cache entry is written AFTER collection, so two presses racing each other both see
an empty cache and both pay. The refusal has to happen before a byte is submitted, and it has
to happen against something a second press can see.

A BOX NUMBER IS THE WRONG THING TO SEE, IN BOTH DIRECTIONS.

  TOO WIDE.  Two live runs over DISJOINT selections in one drawer are refused, and
             `_busy_run`'s own docstring records that narrowing as accepted for want of a
             card-level vocabulary — D48's note. Nothing was ever going to be double-billed
             there: the two presses are buying different cards.
  TOO NARROW. `_run_box` answers `None` for a run whose captures span more than one box —
             `cli/cmd_identify.py:_scope_for` writes no scope block for such a run, and the
             capture directory's name does not parse as `boxN` — so a run over a multi-box
             pile is INVISIBLE to the guard in both directions. A box press and that run
             would not see each other, and the overlap would be billed twice.

SO THE CLAIM IS A SET OF POSITION KEYS, which is the vocabulary that has neither fault. A key
is `box/index` (`identify/sidecar.py:key`), the same string the cache, the queues and the join
are keyed by, so a claim over two drawers is one row and a claim over three cards is three
strings. A press is refused on INTERSECTION, and the refusal names the receipt holding the
cards and which cards they are.

WHAT IS CLAIMED IS THE SEND LIST, NEVER THE SELECTION. This is the property that keeps the
default press usable: on the operator's store 2,321 of 2,535 cards are cache hits, so a press
over everything claims ~214 keys and leaves the other 2,321 free for any other press. A table
that claimed the selection would lock the store on the first press, which is a guard nobody
would keep armed. A press whose send list is EMPTY writes no row at all — it is spending
nothing, so there is nothing to protect.

THE CHECK AND THE WRITE ARE ONE TRANSACTION, AND THAT IS NOT A DETAIL. The send list is
computed from digests and the cache before the claim — hashing thousands of photographs is not
something to do under the store lock — so two presses can both finish computing their misses
and both arrive here believing they are first. `claim_or_refuse` therefore RECOMPUTES the miss
set from the cache it is handed inside the transaction, intersects against the live claims read
in that same transaction, and writes the row before the lock is released. Its caller passes the
digests it already computed and the snapshot it is writing through; nothing here reads a file.

A ROW DOES NOT SELF-HEAL, AND IT IS NOT ALLOWED TO. `_busy_run` recovers on a server restart
because `_CHILDREN` empties and the marker file's pid stops resolving; a row in a table
survives every restart there is. That is the point rather than a defect: a run killed after it
submitted has a batch in flight at Anthropic that nobody collected, and a second press over
those cards submits them again and pays again. So a live row BLOCKS whatever its holder is
doing, and `holder_alive` below is REPORTED rather than acted on — the screen says "this
claim's holder is gone, release it" instead of a guard quietly deciding the money was never
spent. The way out is `release`, which is a press with a receipt on it.

FAILING TOWARD LIVE IS THE SAFETY DIRECTION, exactly as `scripts/janitor.py:_same_process`
argues for its own subject. A false "live" over-refuses a press and the operator releases the
claim; a false "dead" hands the operator a green button over a batch that is already paid for.
Everything unreadable here — a `ps` that will not parse, a missing `proc_start` — reads live.

THE PID-REUSE GUARD IS AN EXACT COMPARISON, AND JANITOR'S IS NOT. That function compares a
record's own `startedAt` (epoch milliseconds, UTC) against `ps -o lstart=` (local time) and
needs a 120-second tolerance to survive the mismatch — it says what that cost. This claim
records `proc_start` by calling the SAME `ps` at claim time, so the two strings come from one
source in one format and equality is the whole test. `ps` has one-second resolution, so a pid
reused inside the same second by a process that started in the same second reads as the
original holder; that is a false live, which is the direction above.
"""

from __future__ import annotations

import os
import secrets
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from store.rows import Rows, TableSpec

# A claim is one of two things and there is no third. `live` holds cards; `released` is the
# tombstone a release leaves — kept rather than deleted, because "who let this go, and when"
# is the only account of a claim that was given up while its holder may still have been
# spending, and a deleted row answers nothing.
STATE_LIVE = "live"
STATE_RELEASED = "released"
STATES = (STATE_LIVE, STATE_RELEASED)

# Who released a claim, for the row's own record. Two words, because they are different facts:
# the operator pressed the control, or the run that held it finished and gave it back.
BY_OPERATOR = "operator"
BY_RUN = "run"


class UnknownState(ValueError):
    """A state outside `STATES`. Raised rather than stored, the way `master.set_state` does."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_receipt() -> str:
    """A fresh claim's id: sortable, unique, and a legal URL path segment.

    IT IS NOT THE RUN NAME, AND THE RUN NAME WAS THE FIRST CHOICE. A run is created by
    `cli/runs.py:create` and a claim has to exist BEFORE that, or a press refused on
    intersection leaves an empty run directory on `#/runs` — a run with no phase, which the
    screen has no reading for. So the claim is written first under its own id, and the run
    name is attached to the row once there is one (`Submissions.attach_run`). A row whose
    `run` is still null is a claim made by a press that had not got as far as creating one.

    The random tail rather than a counter: two processes claiming in the same second must not
    collide on a key, and nothing may read the store to find out what the next id is —
    `next_box_number` allocates under the lock because a box number is a name a person types,
    and a receipt is not.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"sub-{stamp}-{secrets.token_hex(3)}"


# --------------------------------------------------------------- is the holder still there


def proc_start(pid: int) -> Optional[str]:
    """What `ps` says about when this pid started, verbatim, or None if it will not answer.

    THE STRING AND NOT A PARSED TIME, deliberately. It is recorded at claim time and compared
    at read time, both through this one function, so the only property needed of it is that
    the same process yields the same bytes and a different process almost certainly does not.
    Parsing it into an epoch would add a format assumption, a timezone and a rounding to a
    comparison that needs none of them — which is the exact shape of the bug
    `scripts/janitor.py:_same_process` records.
    """
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    try:
        got = subprocess.run(  # noqa: S603 — argv list, no shell, one integer argument
            ["ps", "-o", "lstart=", "-p", str(int(pid))],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = (got.stdout or "").strip()
    return out or None


def by_position(key: str) -> Tuple[int, int, int, str]:
    """Sort order for a HUMAN reading a list of position keys. DISPLAY ONLY.

    THE STORED ORDER IS AND STAYS LEXICOGRAPHIC, because `keys` is sorted on the way into the
    payload so `Rows.changes()` cannot see a reordering as an edit — that is a property of the
    stored bytes and it is not negotiable. What it is NOT is readable: string order puts
    `3/10` before `3/2`, so a sample drawn straight off it reads
    `3/1, 3/10, 3/11, 3/12, 3/13, 3/14, 3/2, 3/3` and looks to an operator like a bug in the
    thing that is meant to be protecting their money. Measured on the screen, which is the
    only place it shows.

    IT NEVER RAISES, which the obvious `int(k.split("/")[1])` does. `Capture.key` falls back to
    `file:<name>` for a photograph with no position (`identify/sidecar.py`), and such a key can
    reach a claim — it is a card that must still be identified. Those sort last, among
    themselves by name, rather than taking the sentence down.
    """
    box, slash, index = str(key).partition("/")
    if slash:
        try:
            return (0, int(box), int(index), "")
        except ValueError:
            pass
    return (1, 0, 0, str(key))


def holder_alive(submission: "Submission") -> bool:
    """Is the process that wrote this claim still running?

    REPORTED, NEVER ACTED ON. Nothing in this module lets a `False` here drop a claim: see the
    header on why a dead holder is exactly the case that must keep blocking. This answers the
    screen's question — wait, or release — and the selftest's.

    A NON-POSITIVE PID IS NOT A PID, `server/pipeline_routes.py:_live_pid`'s rule: `os.kill(0,
    0)` probes the caller's own process group and always succeeds, so a row holding `0` would
    read live forever.
    """
    pid = submission.pid
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    if not submission.proc_start:
        # No recorded start. Signal 0 is all there is, and it cannot tell this pid from a
        # reused one — so the answer is live, which is the direction the header argues for.
        return True
    actual = proc_start(pid)
    if actual is None:
        return True
    return actual == submission.proc_start


# ------------------------------------------------------------------------------ the record


@dataclass
class Submission:
    """One press's claim on the cards it is about to buy."""

    receipt: str
    pid: int
    started_at: str
    # THE SEND LIST, AS POSITION KEYS. A list rather than a set because `asdict` is the dump
    # and a set is not JSON — `store/master.py:Card.metadata_finish` carries the same note for
    # the same reason. Sorted on the way in so the payload is stable and `changes()` does not
    # see a reordering as an edit.
    keys: List[str] = field(default_factory=list)
    state: str = STATE_LIVE
    # `ps -o lstart=` for `pid` at the moment of the claim. See `proc_start`.
    proc_start: Optional[str] = None
    # The run this claim belongs to, attached once the press has created one. Null is a real
    # state and not a gap — see `new_receipt`.
    run: Optional[str] = None
    # What the press was pointed at, for the screen's sentence. Never read as a scope.
    capture_dir: Optional[str] = None
    released_at: Optional[str] = None
    released_by: Optional[str] = None

    @property
    def live(self) -> bool:
        return self.state == STATE_LIVE

    @property
    def key_set(self) -> set:
        return set(self.keys)


def _parse(key: str, record: dict) -> Optional["Submission"]:
    """One claim from its stored row, or None for a shape that will not construct.

    `Cache.parse`'s and `Queue.parse`'s rule, and it is a different trade here, so it is
    argued rather than copied. A cache row that will not parse costs a re-read; a CLAIM row
    that will not parse costs the protection it was written to provide. It is still skipped
    rather than raised on, because the alternative is a store that cannot be opened at all —
    and an unparseable row is reported: `Submissions.unreadable` counts what was skipped, the
    route puts the figure on the wire, and the screen says so.
    """
    if str(key).startswith("_"):
        return None
    known = {k: v for k, v in record.items() if k in Submission.__annotations__}
    known["receipt"] = str(key)
    keys = known.get("keys")
    known["keys"] = sorted({str(k) for k in keys}) if isinstance(keys, (list, tuple)) else []
    try:
        built = Submission(**known)
    except TypeError:
        return None
    if built.state not in STATES:
        return None
    if not isinstance(built.pid, int) or isinstance(built.pid, bool):
        return None
    return built


@dataclass
class Submissions:
    entries: "Rows" = field(default_factory=lambda: Rows(Submissions.ENTRIES))

    # The `submissions` table (D88's shape): the claim whole in the payload, and the four
    # facts a person with the `sqlite3` CLI would ask for beside it. `keys` is NOT a column —
    # it is a set, and a column holds one value.
    ENTRIES = TableSpec(
        "submissions",
        parse=_parse,
        dump=asdict,
        columns=lambda sub: {
            "pid": sub.pid,
            "state": sub.state,
            "started_at": sub.started_at,
            "run": sub.run,
        },
        column_names=("pid", "state", "started_at", "run"),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.entries, Rows):
            self.entries = Rows(Submissions.ENTRIES, objects=dict(self.entries))

    # -------------------------------------------------------------------------- reading

    def live(self) -> List["Submission"]:
        """Every claim still holding cards, oldest first.

        `where(state=...)` is one indexed query — `state` is a column — so this does not walk
        the table. It matters less here than anywhere else in the store (a healthy store holds
        no live claims at all, and a busy one holds a handful), and it is written this way so
        it cannot become the full-table pass that `cli/resolve.py:_copies_out` was measured as.
        """
        found = self.entries.where(state=STATE_LIVE)
        return sorted(found, key=lambda sub: (sub.started_at or "", sub.receipt))

    def overlap(self, keys: Iterable[str]) -> List[Tuple["Submission", List[str]]]:
        """Every live claim holding any of `keys`, with the cards it and this press share.

        THE CARDS ARE RETURNED AND NOT JUST THE COUNT, because the refusal names them. An
        operator told "box 3 is busy" has to go and look; one told "run X is already buying
        3/12 and 3/40" can see at a glance whether that is the press they just made twice or a
        different selection they had forgotten about.
        """
        wanted = {str(key) for key in keys}
        found: List[Tuple["Submission", List[str]]] = []
        for sub in self.live():
            shared = sorted(wanted & sub.key_set)
            if shared:
                found.append((sub, shared))
        return found

    def get(self, receipt: str) -> Optional["Submission"]:
        return self.entries.get(str(receipt))

    # -------------------------------------------------------------------------- writing

    def claim_or_refuse(
        self,
        candidates: Mapping[str, Optional[str]],
        cache,
        *,
        force: Iterable[str] = (),
        resuming: Optional[str] = None,
        pid: Optional[int] = None,
        capture_dir: Optional[str] = None,
        receipt: Optional[str] = None,
    ) -> Tuple[Optional["Submission"], List[Tuple["Submission", List[str]]]]:
        """RECOMPUTE the send list, check it against every live claim, and claim it. One act.

        `candidates` is `{position key: photograph digest}` for every card the press is
        considering — the whole selection, hits included — and `cache` is the `Cache` of the
        SAME snapshot this is being written through. That pairing is the entire point of this
        signature: the caller computed its misses minutes and thousands of file reads ago, and
        the only two things that can have moved since are the cache and the other claims. Both
        of them are read HERE, inside the transaction the row is written in, so there is no
        window between deciding and claiming for a second press to fit into.

        Returns `(claim, conflicts)`. Exactly one is meaningful:

          conflicts non-empty  -> nothing was written. The caller refuses and names them.
          claim is a row       -> the cards are held, and the caller may spend.
          claim is None        -> the recomputed send list is EMPTY and no row was written.
                                  Nothing is being bought, so nothing needs holding. This is
                                  the ordinary answer for a press over a drawer the store
                                  already owns every answer for, and it is not a refusal.

        THE DIGEST IS THE CALLER'S AND THE VERDICT IS NOT. `cache.reusable(key, digest)` is the
        same question `cli/cmd_identify.py` asked in its own consult pass, asked again against
        rows read under the lock. A key whose digest is None never became a send candidate
        there — the bytes would not hash — and is refused the same way here rather than
        claimed on an unknown.

        `force` IS THE DELIBERATE RE-READ, AND WITHOUT IT THIS WOULD HAVE SILENTLY BROKEN ONE.
        `--reidentify-stale` exists to pay again for an answer the cache already holds, so
        every one of its targets is a cache HIT by construction: recomputing from the cache
        alone would drop all of them from the claim, and the run would then submit cards
        nothing was holding. The caller names them, and they are claimed regardless of the
        cache — which is also the honest reading, since those are exactly the cards it is
        about to spend money on.

        `resuming` IS A RUN CONTINUING, NOT A SECOND PRESS. `--run-dir` re-enters a run that
        already claimed these cards and died, and its own stale claim is the first thing the
        resume would collide with — so a press that names the run it is resuming RELEASES that
        run's live claims here, in this transaction, before the intersection is computed. It
        releases nothing belonging to any other run, which is what keeps this from being a
        back door around the guard: the caller can only ever name the run it is re-entering.
        """
        if resuming:
            self.release_run(str(resuming), BY_RUN)
        forced = {str(key) for key in force}
        wanted = sorted(
            key
            for key, digest in candidates.items()
            if digest and (
                str(key) in forced or cache.reusable(str(key), str(digest)) is None
            )
        )
        conflicts = self.overlap(wanted)
        if conflicts:
            return None, conflicts
        if not wanted:
            return None, []
        token = str(receipt) if receipt else new_receipt()
        holder = int(pid if pid is not None else os.getpid())
        claim = Submission(
            receipt=token,
            pid=holder,
            started_at=now(),
            keys=wanted,
            state=STATE_LIVE,
            proc_start=proc_start(holder),
            capture_dir=capture_dir,
        )
        self.entries[token] = claim
        return claim, []

    def attach_run(self, receipt: str, run: str) -> Optional["Submission"]:
        """Name the run this claim belongs to, once the press has created one.

        A SECOND, TINY TRANSACTION, AND THE COST IS ARGUED. It could have been avoided by
        claiming after `runs.create`, which is what a refusal leaving an empty run directory
        on `#/runs` bought — see `new_receipt`. It could also have been avoided by leaving the
        row nameless and joining run to receipt by scanning every manifest, which makes the
        release preview a directory walk over a table read. So the row carries the name, and
        this write failing is harmless: the claim still stands, still blocks, and still
        releases, and the screen draws a claim with no run name rather than nothing.
        """
        claim = self.get(receipt)
        if claim is None:
            return None
        claim.run = str(run)
        # Reassigned rather than left as an in-place mutation (D-per-box-read): `Rows.where`/
        # `.select` trust the SOURCE's own index for every key this session has not itself
        # written through `__setitem__`, and a claim mutated only in place would keep
        # answering to its STALE `run`/`state` for the rest of this transaction.
        self.entries[claim.receipt] = claim
        return claim

    def release(self, receipt: str, by: str = BY_OPERATOR) -> Optional["Submission"]:
        """Give up a claim's hold on its cards. The row stays, as a tombstone.

        RELEASING TWICE IS NOT AN ERROR AND IS NOT A SECOND RELEASE. An already-released row is
        returned unchanged with its original `released_at` intact, so a replayed request and a
        stale screen both land on the answer the first press wrote. The route turns a receipt
        it cannot find into a 404 and this into an ordinary answer, which is the distinction
        `do_review_answer`'s undo already draws: nothing there, versus already done.
        """
        claim = self.get(receipt)
        if claim is None:
            return None
        if not claim.live:
            return claim
        claim.state = STATE_RELEASED
        claim.released_at = now()
        claim.released_by = str(by)
        # Reassigned rather than left as an in-place mutation (D-per-box-read) — see
        # `attach_run`'s comment: `release_run` calls `self.live()` again right after this,
        # in the SAME transaction, and it must see this claim as no longer live.
        self.entries[claim.receipt] = claim
        return claim

    def release_run(self, run: str, by: str = BY_RUN) -> List["Submission"]:
        """Release every live claim belonging to one run.

        THE RUN'S OWN WAY OUT, and `cli/cmd_identify.py` calls it inside the transaction that
        records the answers the claim paid for — so the cards are freed by the same commit that
        banks what they bought, or by neither. A run that dies before that keeps its claim,
        which is the whole of the header's argument about a batch in flight.
        """
        freed = []
        for sub in self.live():
            if sub.run == str(run):
                released = self.release(sub.receipt, by)
                if released is not None:
                    freed.append(released)
        return freed


def conflict_sentence(conflicts: Sequence[Tuple["Submission", List[str]]], shown: int = 6) -> str:
    """The refusal, in one sentence per claim, naming the receipt and the cards.

    HERE AND NOT IN EACH CALLER, because two of them refuse — `cli/cmd_identify.py` before it
    submits and `server/pipeline_routes.py` before it spawns — and a money refusal spelled two
    ways is two messages an operator has to learn to read as one thing. The cards are truncated
    and the count is not: a press that overlaps four hundred cards is a different mistake from
    one that overlaps two, and the number is what says which.
    """
    lines = []
    for sub, shared in conflicts:
        cards = ", ".join(sorted(shared, key=by_position)[:shown])
        more = f" and {len(shared) - shown} more" if len(shared) > shown else ""
        # THE RUN NAME IS WHAT THE OPERATOR CAN ACT ON — it is the row on `#/runs` they would
        # go and watch — so it leads, and the receipt follows it as the thing the release
        # control takes. A claim with no run yet has only the receipt, and saying it twice is
        # how a sentence stops being read.
        whose = f"Run {sub.run} (receipt {sub.receipt})" if sub.run else f"Receipt {sub.receipt}"
        gone = "" if holder_alive(sub) else " — its holder is gone; release it to press again"
        lines.append(
            f"{whose} already claimed {len(shared)} of these card(s) ({cards}{more}) "
            f"at {sub.started_at}{gone}"
        )
    return "; ".join(lines)


def counted(submissions: "Submissions") -> Dict[str, int]:
    """What the claims table is holding right now — rows, keys, and dead holders.

    THE WORK, NOT THE OUTCOME. A guard whose every outcome assertion passes can still be doing
    none of the work it claims: the addendum to PR A records deleting its gate and watching
    every answer stay right, because hash-first and decode-everything agree on every answer.
    So the figures a press is judged by are published rather than inferred — how many rows are
    live, how many CARDS are locked, and how many claims are held by a process that is gone.
    `server/pipeline_routes.py` puts these on the wire and the selftest asserts them.
    """
    live = submissions.live()
    return {
        "claims": len(live),
        "keys": sum(len(sub.keys) for sub in live),
        "stale": len([sub for sub in live if not holder_alive(sub)]),
    }

