#!/usr/bin/env python3
"""`make submission-selftest` — the claim table, proved by violating it.

WHY THIS EXISTS. `store/submissions.py` is the only binding in this pipeline that protects a
dollar: it refuses a second `identify` press over cards a live run has already claimed. That
claim is worth exactly what its REFUSALS are worth, and a refusal cannot be exercised against
the real thing — the press it exists to stop costs money at Anthropic, and "run two presses
over the operator's store and read the invoice" is the incident, not the test. So every case
here runs against a throwaway store under a temp directory, and the concurrent ones are real
separate processes racing a real flock.

WHAT IS ACTUALLY RACED, SAID PLAINLY SO NOBODY READS MORE INTO IT THAN IS THERE. Two OS
processes, each opening the throwaway store and calling `Submissions.claim_or_refuse` inside
`Store.write()` — the same call, in the same transaction, that `cli/cmd_identify.py` makes
before it submits a byte. It is NOT `pkmnscan identify` end to end: that needs photographs,
sidecars and the Batch API, and a test that mocked the API would be racing the mock. The claim
is the mechanism, and the claim is what is raced.

THE RACE CASE REPRODUCES THE BUG RATHER THAN ASSERTING ABOUT IT, which is
`scripts/reap-selftest.sh`'s rule — that file reproduces `pkill -f` with real processes instead
of asserting that it would have been wrong. So `case_the_naive_order_loses_the_race` runs the
children in TWO modes. `naive` reads the live claims BEFORE taking the store lock and then
writes, which is the order a reasonable person writes first, and both presses claim the same
card: the double invoice, on screen, in this suite. `atomic` calls `claim_or_refuse` inside
`Store.write()`, and exactly one wins. Without the first half, the second half proves only that
something happened.

AND THE BARRIER IS A BARRIER, NOT A SLEEP (D136). The naive children synchronise twice — once
to start, once after each has read and before either writes — so the window is held open by
construction rather than by hoping a `sleep` is long enough. A sleep there would make the
reproduction probabilistic, and a probabilistic reproduction of a money bug is a flake.

WHY IT IS NOT IN THE GIT HOOK. D18: it writes a temp tree and it signals processes. It IS in
`make check`, which is `reap-selftest`'s and `janitor-selftest`'s standing.

IT NEVER TOUCHES THE OPERATOR'S STORE. `PKMNSCAN_HOME` is set to a fresh temp directory for
every case and the real one is never opened, for reading or for writing. The one case needing a
killed holder kills a process this script started, in its own session.

THE WORK IS ASSERTED, NOT JUST THE OUTCOME. The addendum to the hash-first PR records deleting
its gate and watching every outcome assertion stay green, because hash-first and
decode-everything agree on every ANSWER. A guard has the same failure available to it: a claim
table that claimed nothing would let every press through, and every "the press succeeded"
assertion here would still pass. So the cases assert FIGURES — rows live, CARDS locked, presses
refused — and `case_claims_the_send_list_only` exists for no other reason.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

PASS = 0
FAIL = 0
MADE: list = []
KIDS: list = []

# How long the parent waits for a child's verdict file. Generous — a cold sqlite open under a
# loaded `make check` is not fast — and it is a TIMEOUT rather than a wait: reaching it is a
# failure with a message, never a silent pass.
CHILD_TIMEOUT_S = 60.0


def ok(what: str) -> None:
    global PASS
    PASS += 1
    print(f"  ok     {what}")


def bad(what: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  FAIL   {what}")


def check(condition: bool, what: str) -> bool:
    (ok if condition else bad)(what)
    return bool(condition)


def fresh_store() -> Path:
    """A throwaway store directory, with `PKMNSCAN_HOME` pointed at it.

    A DIRECTORY PER CASE, never one reused with its rows deleted. A claim table's whole meaning
    is what is live in it, so a leftover row from the previous case is exactly the thing that
    would make the next one unreadable — and the failure would read as the guard misbehaving.
    """
    where = Path(tempfile.mkdtemp(prefix="pkmnscan-claim."))
    MADE.append(where)
    os.environ["PKMNSCAN_HOME"] = str(where)
    return where


def cleanup() -> None:
    for pid in KIDS:
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL)
    for where in MADE:
        shutil.rmtree(where, ignore_errors=True)


# ----------------------------------------------------------------- the arithmetic, in process


def claim(keys, *, digests=None, **kw):
    """Claim these position keys in the current store. Returns `(claim, conflicts)` as plain
    dicts — read out INSIDE the session, because the objects belong to a `Rows` bound to a
    connection that closes with the block."""
    from store.session import Store

    with Store().write() as session:
        candidates = {key: (digests or {}).get(key, f"digest-of-{key}") for key in keys}
        got, conflicts = session.submissions.claim_or_refuse(
            candidates, session.cache, **kw
        )
        return (
            None if got is None else {"receipt": got.receipt, "keys": list(got.keys)},
            [
                {"receipt": sub.receipt, "shared": list(shared), "run": sub.run}
                for sub, shared in conflicts
            ],
        )


def live_figures():
    """`(rows, cards locked, dead holders)` — `submissions.counted`, through a fresh read."""
    from store import submissions as subs
    from store.session import Store

    counts = subs.counted(Store().read().submissions)
    return counts["claims"], counts["keys"], counts["stale"]


def answer_in_store(digests: dict) -> None:
    """Put a paid-for answer in the cache for each key, so it is a HIT for the next press."""
    from store.session import Store

    with Store().write() as session:
        for key, digest in digests.items():
            session.cache.put(key, {"name": "Paid for already"}, digest, "fp-1")


def case_disjoint_in_one_drawer() -> None:
    """TWO DISJOINT SELECTIONS IN ONE DRAWER MUST BOTH BE ALLOWED.

    This is the over-refusal `_busy_run` accepts by construction — it compares BOX numbers, so
    two presses over different cards in box 3 are one refusal — and D48 records that narrowing
    as accepted for want of a card-level vocabulary. This is the vocabulary.
    """
    fresh_store()
    first, conflicts = claim(["3/1", "3/2"])
    check(first is not None and not conflicts, "a selection in box 3 is claimed")
    second, conflicts = claim(["3/10", "3/11"])
    check(
        second is not None and not conflicts,
        "a DISJOINT selection in the SAME drawer is allowed (the box form refuses this)",
    )
    rows, cards, _ = live_figures()
    check(rows == 2, f"two live claims stand, not one ({rows})")
    check(cards == 4, f"four cards are locked, two per claim ({cards})")


def case_overlap_in_one_drawer() -> None:
    """ONE SHARED CARD IS A REFUSAL, and the refusal names the receipt and that card."""
    fresh_store()
    first, _ = claim(["3/1", "3/2", "3/3"])
    second, conflicts = claim(["3/3", "3/4"])
    check(second is None, "an overlapping selection is refused")
    check(
        bool(conflicts) and conflicts[0]["receipt"] == first["receipt"],
        "the refusal names the receipt holding the cards",
    )
    check(
        bool(conflicts) and conflicts[0]["shared"] == ["3/3"],
        f"it names the overlapping card and only that card "
        f"({conflicts[0]['shared'] if conflicts else None})",
    )
    rows, cards, _ = live_figures()
    check(
        rows == 1 and cards == 3,
        f"the refused press wrote nothing ({rows} rows, {cards} cards)",
    )


def case_store_wide_against_a_box() -> None:
    """A PRESS SPANNING DRAWERS MUST SEE A LIVE BOX PRESS, AND BE SEEN BY ONE.

    THE CASE THE BOX FORM STRUCTURALLY CANNOT ANSWER. `_run_box` answers None for a run whose
    captures span more than one box — `cli/cmd_identify.py:_scope_for` writes no scope block
    for one, and the capture directory's name does not parse as `boxN` — so `_busy_run` is
    blind to such a run in BOTH directions and the overlap would be billed twice. Both
    directions are asserted, in both orders, because a guard that only works when the wide
    press happens to be second is a guard that works by luck.
    """
    fresh_store()
    box_press, _ = claim(["1/1", "1/2", "1/3"])
    check(box_press is not None, "a box press claims its three cards")
    wide, conflicts = claim(["1/2", "2/7", "9/4"])
    check(wide is None, "a press spanning drawers is REFUSED by the live box press")
    check(
        bool(conflicts) and conflicts[0]["shared"] == ["1/2"],
        "and the refusal names the one card they share across the drawers",
    )

    fresh_store()
    wide, _ = claim(["1/2", "2/7", "9/4"])
    check(wide is not None, "a press spanning drawers claims all three drawers' cards")
    box_press, conflicts = claim(["2/7", "2/8"])
    check(box_press is None, "a box press is REFUSED by the live press spanning drawers")
    check(
        bool(conflicts) and conflicts[0]["shared"] == ["2/7"],
        "and that refusal names the shared card too",
    )

    # THE OVERLAP IN A DRAWER THAT IS NOT THE FIRST ONE NAMED, and this case is here because a
    # mutation arm survived without it. Every direction above happens to share its card with
    # the LOWEST-numbered box in the pressing selection, so a guard that intersected only the
    # first drawer it saw passed all four of them — the arm that narrowed `overlap` to one box
    # was killed by nothing. The shared card is in box 9 here, two drawers past the first.
    fresh_store()
    held, _ = claim(["9/4"])
    check(held is not None, "a claim is held in box 9 and nowhere else")
    wide, conflicts = claim(["1/9", "2/7", "9/4"])
    check(
        wide is None,
        "a press spanning drawers is refused on a card in its LAST drawer, not just its first",
    )
    check(
        bool(conflicts) and conflicts[0]["shared"] == ["9/4"],
        f"and the refusal names that card "
        f"({conflicts[0]['shared'] if conflicts else None})",
    )


def case_claims_the_send_list_only() -> None:
    """THE CLAIM IS THE MISSES, NEVER THE SELECTION — asserted as a FIGURE, not an outcome.

    THE WORK-COUNTING CASE, AND THE REASON IT IS NOT AN OUTCOME ASSERTION. A table that claimed
    the whole selection would pass every other case in this file: the first press would still
    succeed, the overlapping one would still be refused, the disjoint one would still be
    allowed. What it would break is the property that keeps the guard armable at all — on the
    operator's store 2,321 of 2,535 cards are cache hits, so a press over everything must lock
    ~214 cards and not 2,535. Only a count can see that.

    The shape is the operator's, scaled down: ten cards in the drawer, eight already answered.
    """
    fresh_store()
    selection = [f"5/{n}" for n in range(1, 11)]
    digests = {key: f"digest-of-{key}" for key in selection}
    hits = selection[:8]
    answer_in_store({key: digests[key] for key in hits})

    got, conflicts = claim(selection, digests=digests)
    check(not conflicts, "a press over a mostly-answered drawer is not refused")
    check(
        got is not None and len(got["keys"]) == 2,
        f"it claims the 2 MISSES and not the 10-card selection "
        f"({None if got is None else len(got['keys'])})",
    )
    check(
        got is not None and sorted(got["keys"]) == ["5/10", "5/9"],
        "and they are exactly the two cards with no answer in the store",
    )
    _, cards, _ = live_figures()
    check(cards == 2, f"2 cards are locked, not 10 ({cards})")

    # AND THE EIGHT ANSWERED CARDS ARE STILL FREE, which is the point of the figure above:
    # another press may take them, because nobody is paying for them.
    free, conflicts = claim(hits, digests=digests)
    check(
        free is None and not conflicts,
        "a second press over the 8 answered cards is neither refused nor claimed — "
        "it is buying nothing",
    )
    rows, cards, _ = live_figures()
    check(rows == 1 and cards == 2, f"and it wrote no row ({rows} rows, {cards} cards)")


def case_empty_send_list_writes_no_row() -> None:
    """A PRESS THAT BUYS NOTHING HOLDS NOTHING. The limit case of the figure above."""
    fresh_store()
    digests = {"7/1": "d1", "7/2": "d2"}
    answer_in_store(digests)
    got, conflicts = claim(list(digests), digests=digests)
    check(got is None and not conflicts, "an all-cache-hit press is allowed and claims nothing")
    rows, cards, _ = live_figures()
    check(rows == 0 and cards == 0, f"the table is empty ({rows} rows, {cards} cards)")


def case_reidentify_stale_is_still_claimed() -> None:
    """A DELIBERATE RE-READ IS A CACHE HIT AND MUST STILL BE CLAIMED.

    `--reidentify-stale` pays again for an answer the store already holds, so every one of its
    targets is a hit by construction. Recomputing from the cache alone would drop all of them
    from the claim and the run would submit cards nothing was holding — the one way the
    recompute that makes this table safe could have made it useless.
    """
    fresh_store()
    digests = {"8/1": "d1", "8/2": "d2"}
    answer_in_store(digests)
    got, _ = claim(list(digests), digests=digests, force=["8/1"])
    check(
        got is not None and got["keys"] == ["8/1"],
        f"the forced re-read is claimed though the cache answers it "
        f"({None if got is None else got['keys']})",
    )
    _, cards, _ = live_figures()
    check(cards == 1, f"one card locked — the re-read, not its answered neighbour ({cards})")


def case_release_frees_the_cards() -> None:
    """RELEASE IS THE WAY OUT, AND RELEASING TWICE IS NOT A SECOND RELEASE."""
    fresh_store()
    from store import submissions as subs
    from store.session import Store

    first, _ = claim(["4/1", "4/2"])
    blocked, conflicts = claim(["4/2"])
    check(blocked is None and bool(conflicts), "the card is held")

    with Store().write() as session:
        released = session.submissions.release(first["receipt"], subs.BY_OPERATOR)
        check(released is not None and not released.live, "the claim is released")
        stamp = released.released_at
    rows, cards, _ = live_figures()
    check(rows == 0 and cards == 0, f"no cards are locked any more ({rows} rows, {cards} cards)")

    after, conflicts = claim(["4/2"])
    check(after is not None and not conflicts, "and the press that was refused now goes through")

    with Store().write() as session:
        again = session.submissions.release(first["receipt"], subs.BY_OPERATOR)
        check(
            again is not None and again.released_at == stamp,
            "a second release keeps the first one's stamp rather than writing a new one",
        )


def case_resume_releases_only_its_own() -> None:
    """A RESUME RELEASES THE RUN IT IS RE-ENTERING AND NOTHING ELSE.

    `--run-dir` re-enters a run that already claimed these cards and died, so its own stale
    claim is the first thing the resume collides with. The door is narrow on purpose: naming a
    run releases THAT run's claims, so it can never be a way around another press's.
    """
    fresh_store()
    from store.session import Store

    mine, _ = claim(["6/1", "6/2"])
    theirs, _ = claim(["6/9"])
    with Store().write() as session:
        session.submissions.attach_run(mine["receipt"], "2026-09-12-box6-01")
        session.submissions.attach_run(theirs["receipt"], "2026-09-12-box6-02")

    again, conflicts = claim(["6/1", "6/2"], resuming="2026-09-12-box6-01")
    check(again is not None and not conflicts, "the resume re-claims its own cards")

    poach, conflicts = claim(["6/9"], resuming="2026-09-12-box6-01")
    check(
        poach is None and bool(conflicts),
        "and naming its own run does NOT release another run's claim",
    )


def case_a_dead_holder_still_blocks() -> None:
    """A HOLDER KILLED WITH -9 LEAVES A CLAIM THAT STILL BLOCKS AND IS RELEASABLE.

    THE CASE THAT LOOKS LIKE A BUG AND IS THE DESIGN. `_busy_run` self-heals because
    `_CHILDREN` empties on a restart; a row does not, and it must not. A run killed AFTER it
    submitted has a batch in flight at Anthropic that nobody collected and that keeps for 29
    days, so a guard that quietly dropped the row on finding the pid gone would hand the
    operator a green button over an invoice already rung up. What the operator gets instead is
    the truth — the holder is gone — and a release control.

    THE PID IS A REAL ONE THE OS HAS REAPED, not an integer this test invented: `-9` is the
    signal `flock` survives and a pidfile does not, which is `reap-selftest`'s argument for
    doing it for real.
    """
    fresh_store()
    from store import submissions as subs
    from store.session import Store

    script = Path(MADE[-1]) / "sleeper.py"
    script.write_text("import time\ntime.sleep(300)\n")
    child = subprocess.Popen(  # noqa: S603
        [sys.executable, str(script)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    KIDS.append(child.pid)
    held, _ = claim(["2/1", "2/2"], pid=child.pid)
    check(held is not None, "a claim is written naming a live holder")

    snap = Store().read().submissions
    check(
        subs.holder_alive(snap.get(held["receipt"])),
        "its holder reads as alive while the process is up",
    )

    os.kill(child.pid, signal.SIGKILL)
    child.wait(timeout=10)

    snap = Store().read().submissions
    check(
        not subs.holder_alive(snap.get(held["receipt"])),
        "after -9 the holder reads as GONE",
    )
    rows, cards, stale = live_figures()
    check(
        rows == 1 and cards == 2 and stale == 1,
        f"and the claim still stands, still holding its cards ({rows} rows, {cards} cards, "
        f"{stale} dead holder)",
    )
    blocked, conflicts = claim(["2/2"])
    check(
        blocked is None and bool(conflicts),
        "a press over its cards is STILL REFUSED — a dead holder does not self-heal",
    )
    check(
        "holder is gone" in subs.conflict_sentence(
            [(snap.get(held["receipt"]), ["2/2"])]
        ),
        "and the refusal says the holder is gone, so the operator knows which case this is",
    )

    with Store().write() as session:
        session.submissions.release(held["receipt"], subs.BY_OPERATOR)
    freed, conflicts = claim(["2/2"])
    check(
        freed is not None and not conflicts,
        "it is RELEASABLE, and the press goes through once it is released",
    )


def case_pid_reuse_cannot_inherit_a_claim() -> None:
    """A PID THE OS HANDED TO SOMETHING ELSE DOES NOT INHERIT A DEAD CLAIM'S HOLDER.

    The pid alone cannot answer this — `os.kill(pid, 0)` succeeds for whatever holds the pid
    now — so the row records what `ps` said about its holder's start at claim time and the
    comparison is exact. This process's own pid with somebody else's start time is that case
    without waiting for the kernel to wrap its pid space.
    """
    fresh_store()
    from store import submissions as subs
    from store.session import Store

    held, _ = claim(["9/1"], pid=os.getpid())
    check(held is not None, "a claim naming this process is written")
    snap = Store().read().submissions
    check(subs.holder_alive(snap.get(held["receipt"])), "and reads as alive")

    with Store().write() as session:
        row = session.submissions.get(held["receipt"])
        row.proc_start = "Mon Jan  1 00:00:00 2001"
    snap = Store().read().submissions
    check(
        not subs.holder_alive(snap.get(held["receipt"])),
        "the same live pid with a DIFFERENT recorded start reads as gone (pid reuse)",
    )


# ------------------------------------------------------------------------------- the race

CHILD = '''
import json, os, sys, time
sys.path.insert(0, {repo!r})
mode, home, go, out, key, mark, peers = sys.argv[1:8]
os.environ["PKMNSCAN_HOME"] = home

from store.session import Store
from store import submissions as subs

candidates = {{key: "digest-of-" + key}}

# THE EXPENSIVE PRE-PASS, WHICH IS WHAT OPENS THE WINDOW. `cli/cmd_identify.py` hashes every
# photograph and consults the cache before it claims — a minute of work on 678 cards — so by
# the time it claims, its idea of what it is buying is old. This is that, in one line.
pre = Store().read()
misses = sorted(k for k, d in candidates.items() if pre.cache.reusable(k, d) is None)

def wait_for(paths):
    while not all(os.path.exists(p) for p in paths):
        pass

wait_for([go])
verdict = {{"mode": mode, "pid": os.getpid(), "claimed": None, "refused": None}}

if mode == "naive":
    # THE BUG, RECONSTRUCTED: the intersection is read BEFORE the store lock is taken, and the
    # row is written after. Anyone would write this first.
    seen = Store().read().submissions.overlap(misses)
    # Both children have now read. The second barrier holds the window open by construction,
    # so the reproduction is deterministic rather than dependent on a sleep being long enough.
    open(mark, "w").close()
    wait_for(peers.split(","))
    if seen:
        verdict["refused"] = [s.receipt for s, _ in seen]
    else:
        with Store().write() as s:
            row = subs.Submission(
                receipt=subs.new_receipt(), pid=os.getpid(),
                started_at=subs.now(), keys=list(misses),
            )
            s.submissions.entries[row.receipt] = row
            verdict["claimed"] = row.receipt
else:
    # THE SHIPPED ORDER: one transaction, the miss set recomputed inside it, the row written
    # before the lock goes.
    open(mark, "w").close()
    with Store().write() as s:
        got, conflicts = s.submissions.claim_or_refuse(candidates, s.cache)
        if conflicts:
            verdict["refused"] = [x.receipt for x, _ in conflicts]
        elif got is not None:
            verdict["claimed"] = got.receipt

with open(out, "w") as fh:
    json.dump(verdict, fh)
'''


def race(mode: str, key: str, home: Path, rounds: int = 1):
    """Two processes, one card, started together. Returns each child's verdict."""
    work = Path(tempfile.mkdtemp(prefix="pkmnscan-race."))
    MADE.append(work)
    script = work / "press.py"
    script.write_text(CHILD.format(repo=str(REPO)))

    go = work / "go"
    outs = [work / f"verdict-{n}.json" for n in (0, 1)]
    marks = [work / f"read-{n}" for n in (0, 1)]
    peers = ",".join(str(m) for m in marks)

    kids = []
    for n in (0, 1):
        kids.append(
            subprocess.Popen(  # noqa: S603
                [
                    sys.executable, str(script), mode, str(home), str(go),
                    str(outs[n]), key, str(marks[n]), peers,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        )
        KIDS.append(kids[-1].pid)

    # Both are up and spinning on the barrier. Release them together.
    go.touch()
    verdicts = []
    for n, kid in enumerate(kids):
        try:
            chatter = kid.communicate(timeout=CHILD_TIMEOUT_S)[0]
        except subprocess.TimeoutExpired:
            kid.kill()
            bad(f"[{mode}] press {n} never finished — its output: {kid.stdout}")
            return None
        if not outs[n].is_file():
            bad(
                f"[{mode}] press {n} left no verdict (exit {kid.returncode}): "
                f"{(chatter or b'').decode('utf-8', 'replace')[-800:]}"
            )
            return None
        verdicts.append(json.loads(outs[n].read_text()))
    return verdicts


def case_the_naive_order_loses_the_race() -> None:
    """THE DOUBLE INVOICE, REPRODUCED: check-then-claim lets both presses buy the same card.

    This asserts the BUG, not the fix. Without it, the case below proves only that two
    processes ran and one of them was refused — which a guard that refused at random would also
    satisfy. `reap-selftest.sh` reproduces `pkill -f` for exactly this reason.
    """
    home = fresh_store()
    # The store has to exist before the children open it, or two processes race the schema
    # creation instead of the claim — a different race, and not this one's subject.
    live_figures()
    verdicts = race("naive", "1/1", home)
    if verdicts is None:
        return
    claimed = [v for v in verdicts if v["claimed"]]
    check(
        len(claimed) == 2,
        f"check-then-claim lets BOTH presses claim card 1/1 — the double invoice "
        f"({len(claimed)} of 2 claimed)",
    )
    rows, cards, _ = live_figures()
    check(
        rows == 2 and cards == 2,
        f"and the table holds two claims on one card ({rows} rows over {cards} card-claims)",
    )


def case_one_transaction_wins_the_race() -> None:
    """TWO CONCURRENT PRESSES OVER ONE CARD: exactly one claims, exactly one is refused.

    THE CASE THE WHOLE TABLE EXISTS FOR. Run over several rounds on a fresh card each time,
    because a guard that wins once may be winning by scheduling luck.
    """
    home = fresh_store()
    live_figures()
    wins = refusals = 0
    rounds = 6
    for n in range(rounds):
        verdicts = race("atomic", f"1/{n + 1}", home)
        if verdicts is None:
            return
        claimed = [v for v in verdicts if v["claimed"]]
        refused = [v for v in verdicts if v["refused"]]
        if len(claimed) == 1 and len(refused) == 1:
            wins += 1
            refusals += 1
        else:
            bad(
                f"round {n + 1}: {len(claimed)} claimed and {len(refused)} refused "
                f"over one card — exactly one of each is the contract"
            )
    check(
        wins == rounds and refusals == rounds,
        f"over {rounds} rounds of two concurrent presses on one card: {wins} claims and "
        f"{refusals} refusals — one of each, every round",
    )
    rows, cards, _ = live_figures()
    check(
        rows == rounds and cards == rounds,
        f"and the table holds exactly one claim per card ({rows} rows, {cards} cards)",
    )


CASES = (
    case_disjoint_in_one_drawer,
    case_overlap_in_one_drawer,
    case_store_wide_against_a_box,
    case_claims_the_send_list_only,
    case_empty_send_list_writes_no_row,
    case_reidentify_stale_is_still_claimed,
    case_release_frees_the_cards,
    case_resume_releases_only_its_own,
    case_a_dead_holder_still_blocks,
    case_pid_reuse_cannot_inherit_a_claim,
    case_the_naive_order_loses_the_race,
    case_one_transaction_wins_the_race,
)


def main() -> int:
    print("submission-selftest — the claim table, proved by violating it")
    try:
        for case in CASES:
            print(f"\n{case.__name__}")
            try:
                case()
            except Exception as exc:  # noqa: BLE001 — every case must run and be scored
                bad(f"{case.__name__} raised {type(exc).__name__}: {exc}")
    finally:
        cleanup()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
