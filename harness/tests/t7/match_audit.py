"""T7 group: `pkmnscan match audit [--write]` re-runs the free reader over filed cards.

Part of `harness/tests/t7_store_and_seams.py`. Incident: a paid read misfiled a card and it sold.
Owner's ruling: a card still in stock whose confident free pick disagrees with its filed card goes
back to Review with its photo, reason `free_reader_disagrees`; a sold one is only listed; a card
the reader cannot accept is "not checked", never a disagreement. The audit never spends.

OUTPUT CONTRACT (what these checks read): one line per card with a photo and a SKU, holding the
position key and the filed SKU; a line for a disagreement also holds the word "disagree"; one
summary line holds "<n> not checked". The fake reader is the one the T7 sweep tests use.
"""

from __future__ import annotations

import hashlib
import re
from unittest import mock

from harness.tests import Checks
from harness.tests.t7 import free_adopt as fa
from harness.tests.t7.common import ARTICUNO_SKU, isolated_home, quiet
from identify import match, sweep
from store.queues import QueueEntry
from store import files, master
from store.session import Store

REASON = "free_reader_disagrees"
DEATH = {"name": "Death from Below", "number": "186", "printed_total": "219", "finish": "unknown", "confidence": "high"}


def _audit(argv, pick, *, ready=True):
    """Run the verb under the fake reader. `pick` maps key -> payload; others are passed on.
    Returns (exit code or 'usage', output lines, paid-call count)."""
    from cli import __main__ as cli_entry
    from cli import cmd_identify, cmd_match

    lines, paid = [], []
    try:
        args = cli_entry.build_parser().parse_args(["match", "audit", *argv])
    except SystemExit:
        return "usage", lines, paid
    with fa._fake_matcher(pick if callable(pick) else fa._results(None, pick)), \
            mock.patch.object(match, "status", lambda *_a, **_k: {"ready": ready}), \
            mock.patch.object(cmd_identify.batch, "run_batch", lambda *a, **k: paid.append(1)), \
            quiet():
        code = cmd_match.run(args, lines.append)
    return code, lines, paid


def _bytes():
    return hashlib.sha256((files.inventory_dir() / "store.sqlite").read_bytes()).hexdigest()


def _rows():
    """Every row of every table, hashed, columns unnamed, so a write to any table moves it. Unlike
    `_bytes` it ignores a WAL checkpoint a connection left open by an earlier check may run: a
    checkpoint moves bytes, not rows. A table that cannot be read raises, naming it.
    The one skip beyond `sqlite_*` is the FTS5 table `cards_fts`: it is external-content over
    `cards` and lists a column (`note`) that `cards` lacks, so `select *` on it always raises. Its
    shadow tables (`cards_fts_data`, `_idx`, `_docsize`, `_config`) are ordinary tables and are hashed."""
    import sqlite3

    conn = sqlite3.connect(f"file:{files.inventory_dir() / 'store.sqlite'}?mode=ro", uri=True)
    try:
        tables = [r[0] for r in conn.execute("select name from sqlite_master where type = 'table' and name not like 'sqlite_%' and sql not like 'CREATE VIRTUAL%' order by name")]
        dump = []
        for t in tables:
            try:
                dump.append(sorted(repr(r) for r in conn.execute(f'select * from "{t}"')))
            except sqlite3.OperationalError as exc:
                sql = [r[0] for r in conn.execute("select sql from sqlite_master where name = ? or tbl_name = ?", (t, t))]
                raise AssertionError(f"table {t!r} cannot be read: {exc}; schema {sql}") from exc
        return hashlib.sha256(repr((tables, dump)).encode()).hexdigest()
    finally:
        conn.close()


def _cards(keys):
    return {k: repr(Store().read().inventory.cards[k]) for k in keys}


def _line(lines, key):
    return " ".join(line for line in lines if key in line)


def check_match_audit(checks: Checks) -> None:
    checks.note("")
    checks.note("MATCH AUDIT: free reader over filed cards; in stock goes to Review, sold is listed")
    from server import capture_server

    with isolated_home():
        keys = [fa._shoot(fa.ARTICUNO) for _ in range(6)]
        stock, sold, agree, unread, agree2, nosku = keys
        fa._seed_export()
        fa._sweep(fa._results(keys, {k: fa.ARTICUNO for k in keys}))
        sku = ARTICUNO_SKU  # `emit` stamps `card.sku`; the audit reads the filed SKU from the card
        with Store().write() as snap:
            for k in keys[:5]:  # `nosku` is identified but never emitted
                snap.inventory.cards[k].sku = sku
        capture_server.do_mark_sold(*map(int, sold.split("/")), {})
        states = {Store().read().inventory.cards[k].state for k in keys}
        checks.ok(bool(sku) and states == {master.IDENTIFIED, master.SOLD} and Store().read().inventory.cards[nosku].sku is None, "(precondition) five cards are filed with a SKU (one sold), one has none")
        pick = {stock: DEATH, nosku: DEATH, sold: DEATH, agree: fa.ARTICUNO, agree2: fa.ARTICUNO}  # `unread` is passed on
        review0 = fa._review(keys)

        # 1. preview: nothing changes, and it says what it found
        before_bytes, before_cards = _bytes(), _cards(keys)
        code, lines, paid = _audit([], pick)
        checks.equal(code, 0, "1. `match audit` runs and exits 0")
        checks.equal((_bytes(), _cards(keys)), (before_bytes, before_cards), "1. without --write the store bytes and every card row are unchanged")
        checks.ok(sku in _line(lines, stock) and "disagree" in _line(lines, stock), "1. an in-stock disagreement is listed with its filed SKU and the word disagree")
        checks.ok("disagree" in _line(lines, nosku), "1. an identified card with no SKU is listed, and disagrees")
        checks.ok("disagree" in _line(lines, sold), "1. a sold disagreement is listed too")
        checks.ok(sku in _line(lines, agree) and "disagree" not in _line(lines, agree), "1. a card that agrees is listed as agreeing")
        checks.ok("1 not checked" in " ".join(lines) and "disagree" not in _line(lines, unread), "1. the card the reader cannot accept is counted not checked, never a disagreement")
        checks.equal(fa._review(keys), review0, "1. and the review queue is unchanged")

        # 2. --write
        code, lines, paid = _audit(["--write"], pick)
        entries = Store().read().review.entries
        checks.equal(code, 0, "2. `match audit --write` exits 0")
        checks.equal(sorted(k for k in keys if k in entries), sorted([stock, nosku]), "2. only the in-stock disagreements are queued, with or without a SKU")
        checks.equal(entries[stock].reason if stock in entries else None, REASON, f"2. with the reason `{REASON}`")
        checks.ok(all(k in entries and entries[k].reason == REASON and bool(entries[k].photo) for k in (stock, nosku)), "2. each with the reason and its photo")
        checks.ok(Store().read().inventory.cards[sold].state == master.SOLD and sold not in entries, "2. a sold card is only listed, never queued or changed")
        rest = (sold, agree, unread, agree2)
        checks.equal({k: v for k, v in _cards(keys).items() if k in rest}, {k: v for k, v in before_cards.items() if k in rest},
                     "2. cards that agree, were not checked or sold are untouched")
        after = repr(entries[stock]) if stock in entries else ""
        _audit(["--write"], pick)
        entries = Store().read().review.entries
        checks.ok(sorted(k for k in keys if k in entries) == sorted([stock, nosku]) and repr(entries[stock]) == after, "2. a second --write queues nothing new")

        # 3. never spends, refuses when not ready
        checks.equal(paid, [], "3. no paid call is made")
        snap = _bytes()
        code, lines, paid = _audit(["--write"], pick, ready=False)
        checks.ok(code not in (0, "usage") and "not ready" in " ".join(lines).lower(), "3. with no ready model or index it refuses and says not ready")
        checks.equal(_bytes(), snap, "3. and changes nothing")


def _reader(accepted, unread):
    """The fake reader: `accepted` key -> payload; `unread` key -> the code it was passed on with."""
    def read(requests, _index=None, *_a, **_k):
        return [
            match.Result(r.key, True, dict(accepted[r.key], engine=fa.MATCHER), margin=0.2, floor=0.95)
            if r.key in accepted
            else match.Result(r.key, False, None, unread[r.key], margin=0.03, floor=0.9)
            for r in requests
        ]
    return read


def _counted(lines, code, n):
    return bool(re.search(rf"{code}\D{{0,6}}{n}\b|\b{n}\D{{0,6}}{code}", " ".join(lines)))


def check_match_audit_edges(checks: Checks) -> None:
    checks.note("")
    checks.note("MATCH AUDIT EDGES: already in review, candidate, lock, reasons, retired and moved")
    with isolated_home():
        keys = [fa._shoot(fa.ARTICUNO) for _ in range(6)]
        inrev, fresh, retired, moved, nohint, weak = keys
        fa._seed_export()
        fa._sweep(fa._results(keys, {k: fa.ARTICUNO for k in keys}))
        with Store().write() as snap:
            card = snap.inventory.cards[inrev]
            snap.review.upsert(QueueEntry(
                position=inrev, box=card.box, index=card.index, label="seeded", photo=str(card.photo or "p.jpg"),
                read={"name": "Seeded", "number": "1"}, confidence="low", reason="name_disputed", market="12.34",
                candidates=[{"name": "Seeded candidate", "number": "7"}],
            ))
            snap.inventory.retire(retired, "lost")
            snap.inventory.cards[moved].state = master.MOVED
        pick = _reader({inrev: DEATH, fresh: DEATH, retired: DEATH, moved: DEATH},
                       {nohint: match.UNREAD_NO_HINT, weak: match.UNREAD_MARGIN})
        seeded = repr(Store().read().review.entries[inrev])

        # 3. the background reader holds its lock: refuse, plainly, write nothing
        held, snap_rows = sweep.acquire_lock(), _rows()
        try:
            code, lines, _paid = _audit(["--write"], pick)
        finally:
            held.close()
        checks.ok(code not in (0, "usage") and "background reader" in " ".join(lines).lower(), "3. with the background reader running the audit refuses, naming it, and exits non-zero")
        checks.equal(_rows(), snap_rows, "3. and writes nothing (every row of every table unchanged)")

        code, lines, _paid = _audit(["--write"], pick)
        entries = Store().read().review.entries
        text = " ".join(lines)
        # 1. already in review
        checks.equal(repr(entries.get(inrev)), seeded, "1. a card already in review for another reason is left exactly as it was (reason, market, candidates)")
        checks.ok("already in review" in text and re.search(r"\b1\b\D{0,12}already in review|already in review\D{0,6}\b1\b", text) is not None, "1. and the summary counts it as skipped, already in review")
        # 2. candidate
        got = str(entries[fresh].candidates) if fresh in entries else ""
        checks.ok("Death from Below" in got and "186" in got, "2. a newly queued disagreement carries the free reader's pick as a candidate")
        # 4. reasons
        checks.ok(_counted(lines, match.UNREAD_NO_HINT, 1) and _counted(lines, match.UNREAD_MARGIN, 1),
                  f"4. not checked is broken down by reason with counts ({match.UNREAD_NO_HINT}, {match.UNREAD_MARGIN})")
        # 5. retired and moved
        checks.ok("retired" in _line(lines, retired) and "moved" in _line(lines, moved), "5. retired and moved cards are tagged in the listing")
        checks.ok(retired not in entries and moved not in entries, "5. and never queued")


CHECKS = (check_match_audit, check_match_audit_edges)
