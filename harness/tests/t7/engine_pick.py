"""T7 group: the free card reader, phase 1 (`docs/specs/identify-engine-pick.md`).

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them. Nothing here loads the model or touches the network: the
matcher's embedder and crop are replaced, and the model download runs against a local HTTP
server on 127.0.0.1.
"""

from __future__ import annotations

import hashlib
import http.server
import json
import math
import threading
import urllib.request
from pathlib import Path

from harness.tests import Checks
from harness.tests.t7.common import REPO_ROOT, isolated_home, quiet
from identify import batch, images as identify_images, match, prompt
from pipeline import join, routing, tcgcsv
from store import cache as cache_mod


# ------------------------------------------------------------------------ the accept rule


class _FakeIndex:
    """The three calls `match.read` makes of an index, over vectors the case chose."""

    def __init__(self, sims, names, blocked=()):
        self.sims, self.names, self.blocked = sims, names, set(blocked)

    def meta(self, key, value=None):
        return match.MODEL_SHA256

    def set_names(self, game):
        return ["Set A"]

    def pool(self, game, set_names):
        import numpy as np

        # Row i has cosine `sims[i]` to the query e0 EXACTLY: [s, sqrt(1 - s*s), 0, 0] . e0 = s.
        rows = [[s, math.sqrt(1.0 - s * s), 0.0, 0.0] for s in self.sims]
        return match.Pool(
            vectors=np.array(rows, dtype=np.float64),
            rows=[(game, "Set A", f"p{i}", f"{i + 1:03d}") for i in range(len(rows))],
            names=list(self.names),
            printed=["100"] * len(rows),
            blocked=self.blocked,
            sets=("Set A",),
        )


def _read_one(sims, names, blocked=(), *, hint=None, promo_games=frozenset()):
    """One Riftbound card read against a pool whose cosines are `sims`, best first.

    `promo_games` is passed explicitly, so no case reads the store's own promo census."""
    import numpy as np

    real_crop, real_embed = match._crop, match.embed
    match._crop = lambda _photo, _aspect: object()
    match.embed = lambda cards, _path=None: np.array([[1.0, 0.0, 0.0, 0.0]] * len(cards))
    try:
        request = match.Request("1/1", Path("unused.jpg"), "riftbound", "riftbound_card_v1", hint)
        return match.read([request], _FakeIndex(sims, names, blocked), promo_games=set(promo_games))[0]
    finally:
        match._crop, match.embed = real_crop, real_embed


def check_matcher_accept_rule(checks: Checks) -> None:
    """The accept rule: margin 0.05 and floor 0.755, one home (`match.MARGIN_MIN`).

    TWO DOUBLES ABOVE 0.5 DIFFER BY A MULTIPLE OF 2**-53, and 0.05 is not one, so "exactly 0.05"
    cannot be built from two cosines. The cases below use the pair whose difference is the
    nearest the arithmetic gives (0.9 - 0.85, 0.05000000000000004) and a pair 0.049 apart, so a
    margin moved either way across 0.05 changes an answer."""
    checks.note("")
    checks.note("MATCHER ACCEPT RULE — margin 0.05 at the floor, top candidates kept, look-alike guard")
    names = ["Vex, Gloomist", "Vex, Gloomist (Alternate Art)", "Other Card"]

    at_margin = _read_one([0.9, 0.85, 0.5], names)
    checks.ok(
        0.05 <= at_margin.margin < 0.0500001,
        "the 0.9 and 0.85 pair is a margin of 0.05 as the arithmetic gives it",
        f"margin {at_margin.margin!r}",
    )
    checks.ok(at_margin.accepted, "a margin of 0.05, at a floor of 0.9, is accepted", at_margin.detail)
    checks.equal(
        at_margin.payload["engine"] if at_margin.payload else None,
        cache_mod.ENGINE_MATCHER,
        "and the accepted answer names the free reader as its engine",
    )

    under = _read_one([0.9, 0.851, 0.5], names)
    checks.ok(0.0489 < under.margin < 0.0491, "the 0.9 and 0.851 pair is a margin of 0.049", f"{under.margin!r}")
    checks.ok(not under.accepted, "a margin of 0.049 is not accepted")
    checks.equal(under.code, match.UNREAD_MARGIN, "and it is left unread for the margin, by its code")

    # A NON-ACCEPTED RESULT KEEPS WHAT THE READER THOUGHT: the second look and the review screen
    # show the top pick beside the paid answer, so every unread code keeps the top candidates.
    weak = _read_one([0.69, 0.5, 0.4], names)
    for label, result, code in (
        ("margin", under, match.UNREAD_MARGIN),
        ("floor", weak, match.UNREAD_FLOOR),
    ):
        checks.equal(result.code, code, f"the {label} case is unread for its own code")
        checks.equal(
            [c["name"] for c in result.candidates],
            names,
            f"a card unread for the {label} keeps its top {match.TOP_N} candidates, best first",
        )
        checks.ok(
            result.floor is not None and result.margin is not None,
            f"and keeps the floor and the margin it was judged on ({label})",
        )

    # THE LOOK-ALIKE GUARD. The best answer shares its name with a printing that has no stock
    # photo, so the stock photo shown may be the wrong printing: never accepted, whatever the
    # margin. The control is the same read with nothing blocked.
    blocked = {match.card_name("Vex, Gloomist (Alternate Art)")}
    guarded = _read_one([0.95, 0.4, 0.3], names, blocked)
    control = _read_one([0.95, 0.4, 0.3], names)
    checks.ok(control.accepted, "control: a 0.55 margin at a 0.95 floor is accepted with nothing blocked")
    checks.ok(not guarded.accepted, "the same answer is unaccepted when a no-image printing shares its name")
    checks.equal(guarded.code, match.UNREAD_LOOKALIKE, "and the code is the look-alike guard's")
    checks.equal(
        [c["name"] for c in guarded.candidates][0],
        "Vex, Gloomist",
        "and it still keeps the top candidate for the review screen",
    )

    # THE PROMO GUARD (spec section 2). A store that holds a promo card of a game has an incomplete
    # pool for it: an unhinted card of that game is held back, a hinted one is read as before.
    unhinted = _read_one([0.95, 0.4, 0.3], names, promo_games={"riftbound"})
    checks.equal(
        (unhinted.accepted, unhinted.code),
        (False, match.UNREAD_PROMO_HELD),
        "an unhinted card of a game the store holds a promo of is not accepted, and is held for the promo guard",
    )
    checks.equal(
        [c["name"] for c in unhinted.candidates] if unhinted.candidates else [],
        [],
        "and the promo hold is a pool rule, so it carries no candidates",
    )
    hinted = _read_one([0.95, 0.4, 0.3], names, hint="Set A", promo_games={"riftbound"})
    checks.ok(hinted.accepted, "a hinted card of that game is left alone by the guard", hinted.detail)
    other = _read_one([0.95, 0.4, 0.3], names, promo_games={"pokemon"})
    checks.ok(other.accepted, "and a promo held in another game does not touch this one")
    checks.equal(
        _read_one([0.95, 0.4, 0.3], names, promo_games={match.ALL_GAMES}).code,
        match.UNREAD_PROMO_HELD,
        "a store that could not be read holds a promo in every game",
    )

    # THE SAME GUARD THROUGH THE REAL INDEX: a `no_url` row blocks its name, an `ok` row reads.
    import tempfile

    import numpy as np

    with tempfile.TemporaryDirectory() as tmp:
        with match.Index(Path(tmp) / "fingerprints.sqlite") as index:
            index.meta("model_sha256", match.MODEL_SHA256)
            index.db.execute(
                "insert into sets values(?,?,?,?,?,?,?)",
                ("riftbound", "Set A", "tcgcsv", "", 2, 0, "t"),
            )
            vec = np.array([1.0, 0.0] + [0.0] * (match.DIM - 2), np.float32)
            far = np.array([0.0, 1.0] + [0.0] * (match.DIM - 2), np.float32)
            for pid, name, status_, blob in (
                ("1", "Vex, Gloomist", match.S_OK, vec.tobytes()),
                ("2", "Other Card", match.S_OK, far.tobytes()),
                ("3", "Vex, Gloomist (Alternate Art)", match.S_NO_URL, None),
            ):
                index.db.execute(
                    "insert into vec values(?,?,?,?,?,?,?,?,?,?)",
                    ("riftbound", "Set A", pid, pid.zfill(3), name, "", status_, None, blob, "t"),
                )
            index.db.commit()
            real_crop, real_embed = match._crop, match.embed
            match._crop = lambda _photo, _aspect: object()
            match.embed = lambda cards, _path=None: np.stack([vec] * len(cards))
            try:
                request = match.Request("1/1", Path("unused.jpg"), "riftbound", "riftbound_card_v1")
                real = match.read([request], index, promo_games=set())[0]
            finally:
                match._crop, match.embed = real_crop, real_embed
        checks.equal(
            (real.accepted, real.code),
            (False, match.UNREAD_LOOKALIKE),
            "through a real index, a card whose name a no-image printing shares is left unread by the guard",
        )


# ------------------------------------------------------------------------ the download


class _ModelServer(http.server.BaseHTTPRequestHandler):
    body = b"GOOD" * 1000
    wrong_sum = b"EVIL" * 1000  # the pinned size, another content

    def do_GET(self):  # noqa: N802 (http.server's name)
        routes = {"/good": self.body, "/short": self.body[:-1], "/sum": self.wrong_sum}
        if self.path not in routes:
            self.send_error(404)
            return
        data = routes[self.path]
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        pass


def check_model_download(checks: Checks) -> None:
    """`match.download_model` against a local server: a wrong file is thrown away, a right one kept.

    The pin is swapped for a 4,000-byte file's size and hash for the length of the check: the real
    model is 371 MB and nothing here may download it."""
    checks.note("")
    checks.note("MODEL DOWNLOAD — wrong size, wrong checksum, 404, right file (127.0.0.1 only)")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _ModelServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    # No proxy: a `http_proxy` in the environment must not carry a loopback request elsewhere.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
    saved = match.MODEL_BYTES, match.MODEL_SHA256
    match.MODEL_BYTES = len(_ModelServer.body)
    match.MODEL_SHA256 = hashlib.sha256(_ModelServer.body).hexdigest()
    try:
        with isolated_home() as home:
            for path, fragment, label in (
                ("/short", "wrong size or checksum", "a file of the wrong size"),
                ("/sum", "wrong size or checksum", "a file of the right size and the wrong sha256"),
                ("/missing", "answered 404", "a 404"),
            ):
                dest = Path(home) / label.replace(" ", "-") / "model.onnx"
                caught = checks.raises(
                    match.ModelDownloadError,
                    lambda dest=dest, path=path: match.download_model(dest, base + path, opener=opener),
                    f"{label} is refused with a named error",
                )
                checks.ok(
                    caught is not None and fragment in str(caught),
                    f"and the message says so plainly ({fragment!r})",
                    f"message: {caught}",
                )
                checks.ok(
                    not dest.exists() and not dest.with_name(dest.name + ".part").exists(),
                    f"{label} leaves neither a model file nor a part file",
                )
            dest = Path(home) / "right" / "model.onnx"
            got = match.download_model(dest, base + "/good", opener=opener)
            checks.equal(got, dest, "the right file is accepted and returned at its path")
            checks.equal(dest.read_bytes(), _ModelServer.body, "with its bytes intact")
            checks.ok(
                not dest.with_name(dest.name + ".part").exists() and match.model_ready(dest),
                "and no part file is left, and `model_ready` agrees",
            )
    finally:
        match.MODEL_BYTES, match.MODEL_SHA256 = saved
        server.shutdown()
        server.server_close()


# ------------------------------------------------------------------------ cmd_identify


def _unaccepted(key, code=match.UNREAD_MARGIN):
    return match.Result(
        key, False, code=code, detail="the free reader is not sure", margin=0.031, floor=0.91,
        candidates=[{"product_id": "9", "set": "Base Set", "number": "026", "name": "Raichu", "cosine": 0.91}],
    )


def _accepted(key):
    payload = {
        "name": "Pikachu", "number": "025", "printed_total": "102", "finish": "normal",
        "confidence": "high", "engine": cache_mod.ENGINE_MATCHER,
    }
    return match.Result(key, True, payload=payload, margin=0.2, floor=0.95)


def check_identify_free_first(checks: Checks) -> None:
    """`identify --engine marqo-b` with a fake matcher and a fake batch transport.

    Four Pokemon photographs: `4/1` the free reader accepts, `4/2` to `4/4` it does not. Only the
    last three may reach the paid batch; the preflight says whether its count is estimated or
    measured; a press with no index is refused; the run record keeps what the free reader thought
    of each card it passed on, on a cached press and on a resumed one too."""
    from cli import __main__ as cli_entry
    from cli import cmd_identify, resolve
    from store.session import Store

    checks.note("")
    checks.note("IDENTIFY, FREE FIRST — fake matcher, fake batch (nothing paid, nothing downloaded)")

    def spoken(lines, prefix):
        return next((line for line in lines if line.startswith(prefix)), "")

    def photos(directory, box, count):
        directory.mkdir()
        for index in range(1, count + 1):
            identify_images.Image.new("RGB", (64, 89), (40 * index, (90 + 30 * index + 70 * box) % 256, 200 - 50 * index)).save(
                directory / f"{box}-00{index}.jpg", "JPEG"
            )
            (directory / f"{box}-00{index}.json").write_text(
                json.dumps({"box": box, "position": index, "game": "pokemon", "set_hint": "SV09"}), "utf-8"
            )

    def newest_cards(home):
        runs = sorted(d for d in (Path(home) / "runs").iterdir() if d.is_dir())
        return json.loads((runs[-1] / "identifications.json").read_text("utf-8"))["cards"]

    with isolated_home() as home:
        caps = Path(home) / "free-caps"
        photos(caps, 4, 4)
        sent: list = []
        asked: list = []
        accepted = {"4/1"}

        def answer(custom_id, strategy):
            return batch.Outcome(
                custom_id, batch.SUCCEEDED,
                identification=prompt.parse(
                    {"name": "Raichu", "number": "026", "printed_total": "102", "finish": "normal", "confidence": "high"},
                    strategy,
                ),
            )

        def fake_run_batch(requests, log=None, on_submit=None):
            sent.extend(r.custom_id for r in requests)
            return batch.BatchRun(outcomes={r.custom_id: answer(r.custom_id, r.strategy) for r in requests})

        def fake_read(requests, index, model=None, aspect=0.716, log=lambda _m: None, promo_games=None):
            asked.append([r.key for r in requests])
            return [_accepted(r.key) if r.key in accepted else _unaccepted(r.key) for r in requests]

        real = (cmd_identify.batch.run_batch, match.read, match.status, match.preflight, match.MEASURE_MAX)
        cmd_identify.batch.run_batch = fake_run_batch
        match.read = fake_read

        def press(directory, *extra):
            lines: list = []
            argv = ["identify", str(directory), "--engine", "marqo-b", *extra]
            with quiet():
                code = cmd_identify.run(cli_entry.build_parser().parse_args(argv), lines.append)
            return code, lines

        try:
            # ------------------------------------------------ no index: estimated, and refused
            match.status = lambda *_a, **_k: {"ready": False}
            code, lines = press(caps, "--dry-run")
            checks.equal(code, 0, "a free dry run with no index exits 0")
            checks.equal(
                spoken(lines, "second look"),
                "second look     4 of 4 estimated",
                "with no index every card is a certain second look: the pool rules cannot read any",
            )
            checks.equal(asked, [], "and the estimate read no photograph")
            code, lines = press(caps)
            checks.equal(code, 1, "the press with no index is refused")
            checks.ok(
                any("not prepared" in line for line in lines),
                "and the refusal says the free reader is not prepared",
                "\n".join(lines[-4:]),
            )
            checks.equal(sent, [], "and nothing reached the paid batch")
            checks.equal(list(Path(home).glob("**/identifications.json")), [], "and no run record was written")

            # ------------------------------------------------ a long selection: estimated, never run
            # N = max(round(0.40 x M), the cards the pool rules cannot read). M is 4 here, so 0.40 gives 2.
            match.status = lambda *_a, **_k: {"ready": True}
            match.MEASURE_MAX = 3
            for can_read, expected in ((4, 2), (1, 3), (0, 4)):
                match.preflight = lambda requests, *_a, can_read=can_read, **_k: {
                    "cards": len(requests), "can_read": can_read, "unread": {}, "state": {"ready": True},
                }
                code, lines = press(caps, "--dry-run")
                checks.equal(
                    spoken(lines, "second look"),
                    f"second look     {expected} of 4 estimated",
                    f"a dry run over 4 > MEASURE_MAX cards with {can_read} readable by the pool rules estimates "
                    f"max(round(0.40 x 4), {4 - can_read}) = {expected}",
                )
            checks.equal(asked, [], "and a dry run past MEASURE_MAX never runs the matcher")
            match.MEASURE_MAX, match.preflight = real[4], real[3]

            # ------------------------------------------------ an index: measured, only 4/2 to 4/4 paid
            code, lines = press(caps, "--dry-run")
            checks.equal(code, 0, "a free dry run with an index exits 0")
            checks.equal(
                spoken(lines, "second look"),
                "second look     3 of 4 measured",
                "within MEASURE_MAX the count is MEASURED by a free pass over the selection",
            )
            checks.equal(spoken(lines, "free read"), "free read       1 of 4 measured", "and so is the free read")
            checks.equal(sent, [], "a dry run sends nothing")

            code, lines = press(caps)
            checks.equal(code, 0, "the free press with an index exits 0")
            checks.equal(
                sorted(sent),
                ["4-2f-2", "4-2f-3", "4-2f-4"],
                "ONLY THE CARDS THE FREE READER DID NOT ACCEPT reach the Haiku batch (`4/2` to `4/4`)",
            )
            cards = newest_cards(home)
            checks.equal(sorted(cards), ["4/1", "4/2", "4/3", "4/4"], "the record holds all four cards")
            checks.equal(cards["4/1"].get("second_look"), None, "the accepted card carries no second_look")
            checks.equal(cards["4/1"].get("engine"), cache_mod.ENGINE_MATCHER, "and names the free reader as its engine")
            look = cards["4/2"].get("second_look") or {}
            checks.equal(
                (look.get("code"), look.get("name"), look.get("number"), look.get("set"), look.get("floor"), look.get("margin")),
                (match.UNREAD_MARGIN, "Raichu", "026", "Base Set", 0.91, 0.031),
                "a passed-on card carries second_look: why, the top pick, and the figures",
            )
            checks.equal(cards["4/2"].get("engine"), cache_mod.ENGINE_HAIKU, "and its answer names the paid read")

            # ------------------------------------------------ the cache keeps the hold
            held = Store().read().cache.get("4/2")
            checks.equal(held.second_look, look if look else None, "the cache entry of a second-look answer carries the hold")
            sent_before = len(sent)
            code, _lines = press(caps)
            checks.equal(code, 0, "a second press over the same cards exits 0")
            checks.equal(len(sent), sent_before, "and buys nothing: every answer is cached")
            again = newest_cards(home)
            checks.equal(again["4/2"].get("cached"), True, "the second-look card was adopted from the cache")
            checks.equal(
                again["4/2"].get("second_look"),
                look,
                "AND ITS RECORD STILL CARRIES second_look: a cached hold is never lost to a later press",
            )
            checks.equal(again["4/1"].get("second_look"), None, "while the accepted card still carries none")

            pick = resolve._second_look(again["4/2"].get("second_look"))
            card = join.IdentifiedCard(
                position=join.Position(box=3, index=1), name="Dunsparce", number="120", printed_total="159",
                metadata_finish="normal", photo="captures/box3/0001.jpg", confidence="high", second_look=pick,
            )
            catalog = join.Catalog(tcgcsv.read_export(REPO_ROOT / "fixtures/sv09_export_untouched.csv"))
            joined = join.join_batch([card], catalog, router=join.default_router(review_below=routing.CONFIDENCE_NONE))
            checks.equal(
                ([q.destination.reason for q in joined.queued], list(joined.matches)),
                ([routing.READERS_DISAGREE], []),
                "and the join routes that cached card to review under review_below=none",
            )

            # ------------------------------------------------ a resume keeps the hold from the manifest
            resumed = Path(home) / "resume-caps"
            photos(resumed, 5, 2)
            accepted.clear()
            accepted.add("5/1")

            def dying_batch(requests, log=None, on_submit=None):
                if on_submit is not None:
                    on_submit("msgbatch_x")
                raise batch.BatchError("the line dropped")

            cmd_identify.batch.run_batch = dying_batch
            code, _lines = press(resumed)
            checks.equal(code, 1, "a free press whose batch dies exits 1")
            run_dir = sorted(d for d in (Path(home) / "runs").iterdir() if d.is_dir())[-1]
            manifest_file = run_dir / "manifest.json"
            manifest = json.loads(manifest_file.read_text("utf-8")) if manifest_file.exists() else {}
            rows = manifest.get("second_look") or []
            checks.equal(
                [(row.get("key"), row.get("code")) for row in rows],
                [("5/2", match.UNREAD_MARGIN)],
                "the manifest lists each second-look card as a dict with its key and its code, before the batch",
            )
            # The resumed press's matcher now accepts both cards, so only the manifest can say 5/2 was held.
            accepted.add("5/2")

            def fake_collect(ids, **_kwargs):
                return batch.BatchRun(
                    outcomes={custom: answer(custom, "pokemon_card_v1") for custom in ("5-2f-1", "5-2f-2")}
                )

            real_collect = cmd_identify.batch.collect_batches
            cmd_identify.batch.collect_batches = fake_collect
            try:
                code, _lines = press(resumed, "--run-dir", str(run_dir))
            finally:
                cmd_identify.batch.collect_batches = real_collect
            checks.equal(code, 0, "a resume into that run reattaches and exits 0")
            records = json.loads((run_dir / "identifications.json").read_text("utf-8"))["cards"]
            checks.equal(
                (records["5/2"].get("second_look") or {}).get("code"),
                match.UNREAD_MARGIN,
                "THE RESUMED RECORD KEEPS second_look: the hold came from the manifest, this process never ran the matcher",
            )
            checks.equal((records["5/2"].get("second_look") or {}).get("name"), "Raichu", "with the matcher's pick")
            checks.ok("key" not in (records["5/2"].get("second_look") or {}), "and without the manifest's own key field")
        finally:
            cmd_identify.batch.run_batch, match.read, match.status, match.preflight, match.MEASURE_MAX = real


# ------------------------------------------------------------------------ the join


def check_second_look_routing(checks: Checks) -> None:
    """A second-look card is reviewed whatever the gate says, and only it carries `matcher_pick`."""
    from cli import resolve

    checks.note("")
    checks.note("SECOND LOOK ROUTING — review under review_below=none, matcher_pick on the entry")
    catalog = join.Catalog(tcgcsv.read_export(REPO_ROOT / "fixtures/sv09_export_untouched.csv"))
    pick = join.MatcherPick(code=match.UNREAD_MARGIN, name="Raichu", number="026", set="Base Set", floor=0.91, margin=0.03)

    def card(index, second_look=None, confidence="high"):
        return join.IdentifiedCard(
            position=join.Position(box=3, index=index), name="Dunsparce", number="120",
            printed_total="159", metadata_finish="normal", photo=f"captures/box3/{index:04d}.jpg",
            confidence=confidence, second_look=second_look,
        )

    router = join.default_router(review_below=routing.CONFIDENCE_NONE)
    plain = join.join_batch([card(1)], catalog, router=router)
    checks.ok(len(plain.matches) == 1 and not plain.queued, "control: a high-confidence card lists under review_below=none")

    looked = join.join_batch([card(2, pick)], catalog, router=router)
    checks.equal(list(looked.matches), [], "a card with second_look lists nothing even under review_below=none")
    checks.equal(
        [q.destination.reason for q in looked.queued],
        [routing.READERS_DISAGREE],
        "it routes to review, as readers_disagree",
    )
    if looked.queued:
        read = resolve.queue_entry(looked.queued[0]).read
        checks.equal(
            read.get("matcher_pick"),
            {"name": "Raichu", "number": "026", "set": "Base Set", "reason": match.UNREAD_MARGIN},
            "its queue entry carries matcher_pick: the top pick and why it was not accepted",
        )

    other = join.join_batch([card(3, None, confidence="low")], catalog, router=join.default_router())
    checks.ok(bool(other.queued), "control: a low-confidence card with no second_look is queued too")
    if other.queued:
        checks.ok(
            "matcher_pick" not in resolve.queue_entry(other.queued[0]).read,
            "and its queue entry has no matcher_pick key at all",
        )

    checks.equal(resolve._second_look({"code": "x", "name": "N"}), join.MatcherPick(code="x", name="N"), "a record's second_look block parses to the carrier")
    checks.equal(
        [resolve._second_look(raw) for raw in (None, {}, {"name": "N"}, "text")],
        [None] * 4,
        "an absent, empty, codeless or malformed block parses to None, never a guess",
    )


SV09_SET = "SV09: Journey Together"  # the set cell of the fixture export's Dunsparce 120/159 row
DUNSPARCE_SKU = "8608459"


def check_second_look_agreement(checks: Checks) -> None:
    """The owner's ruling: the free reader refused but named a pick, and a HIGH paid read names
    the SAME printing (set and number through `identity_binding.number_agrees`; name alone
    never counts), so the card is not held. Disagreement, or a paid read below high, still is,
    and the reason says which, never `low_confidence` over a high read."""
    import re

    from cli import requeue
    from harness.tests.t7.common import capture_payload, entry, write_export
    from server import capture_server
    from store import master
    from store.session import Store

    checks.note("")
    checks.note("SECOND LOOK AGREEMENT — agree + high resolves; every other pairing is held, for its own reason")
    catalog = join.Catalog(tcgcsv.read_export(REPO_ROOT / "fixtures/sv09_export_untouched.csv"))
    router = join.default_router()

    def pick(name="Dunsparce", number="120", set=SV09_SET):
        return join.MatcherPick(code=match.UNREAD_MARGIN, name=name, number=number, set=set, floor=0.91, margin=0.03)

    def card(index, second_look, confidence):
        return join.IdentifiedCard(
            position=join.Position(box=3, index=index), name="Dunsparce", number="120",
            printed_total="159", metadata_finish="normal", photo=f"captures/box3/{index:04d}.jpg",
            confidence=confidence, second_look=second_look,
        )

    agreed = join.join_batch([card(1, pick(), "high")], catalog, router=router)
    checks.equal(list(agreed.matches), [DUNSPARCE_SKU], "agree + high: the card lists as the card both readers named")
    checks.equal([q.destination.reason for q in agreed.queued], [], "agree + high: nothing is queued")

    unsure = join.join_batch([card(2, pick(), "medium")], catalog, router=router)
    checks.equal(len(unsure.queued), 1, "agree + medium: held for review")
    why = [q.destination.reason for q in unsure.queued]
    checks.ok(
        bool(why) and why[0] != routing.LOW_CONFIDENCE and re.search(r"disagree|unsure", why[0]) is not None,
        f"agree + medium: the reason says the paid read was unsure, got {why}",
    )

    disagreed = join.join_batch([card(3, pick("Raichu", "026", "Base Set"), "high")], catalog, router=router)
    checks.equal(len(disagreed.queued), 1, "disagree + high: held for review")
    why = [q.destination.reason for q in disagreed.queued]
    checks.ok(
        bool(why) and why[0] != routing.LOW_CONFIDENCE and "disagree" in why[0],
        f"disagree + high: the reason says the readers disagreed, never low_confidence, got {why}",
    )

    # Same name, other printing: a name never counts as agreement.
    other = join.join_batch([card(4, pick("Dunsparce", "199", SV09_SET), "high")], catalog, router=router)
    checks.equal(len(other.queued), 1, "same name, other number + high: held, name alone never agrees")

    # An OPEN entry that already meets the rule leaves on the next re-resolve, unanswered.
    with isolated_home() as home:
        for _ in range(2):
            capture_server.do_capture(capture_payload(1))
        export = write_export(home / "agree-export.csv")
        catalogs, _, _ = requeue.catalogs_from([export])
        with Store().write() as snapshot:
            for index in (1, 2):
                snapshot.inventory.record_identification(
                    master.position_key(1, index), name="Dunsparce", number="120", printed_total="159", confidence="high",
                )
                # The capture's finish claim settles the two Dunsparce condition rows, as `card()` above does.
                snapshot.inventory.cards[master.position_key(1, index)].metadata_finish = ["normal"]
            for index, said in ((1, pick()), (2, pick("Raichu", "026", "Base Set"))):
                snapshot.review.upsert(entry(
                    1, index, reason=routing.LOW_CONFIDENCE, confidence="high",
                    read={"name": "Dunsparce", "number": "120", "matcher_pick": {
                        "name": said.name, "number": said.number, "set": said.set, "reason": said.code}},
                ))
        snap = Store().read()
        plan = requeue.plan(snap.inventory, snap.review, snap.parked, catalogs)
        checks.equal([c.position for c in plan.resolved], ["1/1"], "re-resolve: the open agree + high entry leaves the queue with no answer")
        held = [c for c in plan.refreshed if c.position == "1/2"]
        checks.ok(
            len(held) == 1 and held[0].after is not None
            and held[0].after.reason != routing.LOW_CONFIDENCE and "disagree" in held[0].after.reason,
            "re-resolve: the open disagree + high entry stays, with the readers-disagreed reason",
        )


def check_disagree_candidates_hold_both(checks: Checks) -> None:
    """A `readers_disagree` entry offers BOTH printings, so one numbered press answers it: the
    free pick resolves to its catalog row(s) through the same lookup the candidates use."""
    from cli import resolve

    checks.note("")
    checks.note("READERS DISAGREE — the entry's candidates hold the paid card and the free pick")
    catalog = join.Catalog(tcgcsv.read_export(REPO_ROOT / "fixtures/sv09_export_untouched.csv"))
    router = join.default_router()

    def queued(number):
        pick = join.MatcherPick(code=match.UNREAD_MARGIN, name="Dudunsparce ex", number=number, set=SV09_SET)
        card = join.IdentifiedCard(
            position=join.Position(box=3, index=1), name="Dunsparce", number="120",
            printed_total="159", metadata_finish="normal", photo="captures/box3/0001.jpg",
            confidence="high", second_look=pick,
        )
        report = join.join_batch([card], catalog, router=router)
        return resolve.queue_entry(report.queued[0]) if report.queued else None

    found = queued("121")
    skus = [c["sku"] for c in found.candidates] if found else []
    checks.ok(DUNSPARCE_SKU in skus, f"the paid read's own row is a candidate, got {skus}")
    checks.ok("8608469" in skus, f"the free pick's row (Dudunsparce ex 121/159) is a candidate too, got {skus}")

    gone = queued("999")
    checks.ok(gone is not None and gone.reason == routing.READERS_DISAGREE, "a pick with no catalog row still holds the card as readers_disagree")
    checks.ok(
        gone is not None and [c["sku"] for c in gone.candidates].count("8608469") == 0 and gone.read.get("matcher_pick", {}).get("number") == "999",
        "and offers no invented row: the pick stays on the entry, the candidates stay the paid read's alone",
    )


# ------------------------------------------------------------------------ the cache


def check_cache_engines(checks: Checks) -> None:
    """Which engine's answer may replace which (`store/cache.py`'s header, section 7 of the spec)."""
    checks.note("")
    checks.note("CACHE ENGINES — matcher never replaces, Haiku replaces a matcher entry")
    haiku, matcher = cache_mod.ENGINE_HAIKU, cache_mod.ENGINE_MATCHER
    said = lambda name: {"name": name, "number": "1", "printed_total": "9", "confidence": "high"}  # noqa: E731

    def held(engine, name, cleared=False):
        cache = cache_mod.Cache.parse({})
        cache.put("3/1", said(name), "sha-old", "fp", engine=engine)
        if cleared:
            cache.entries["3/1"].cleared_by_human = True
        return cache

    for label, cache in (
        ("a paid answer", held(haiku, "Paid")),
        ("a matcher answer", held(matcher, "Free")),
        ("a human-cleared answer", held(haiku, "Human", cleared=True)),
    ):
        before = cache.get("3/1").identification["name"]
        returned = cache.put("3/1", said("Matcher"), "sha-new", "", engine=matcher)
        entry = cache.get("3/1")
        checks.ok(
            returned is None and entry.identification["name"] == before and entry.photo_sha256 == "sha-old",
            f"a matcher put never replaces {label}",
        )
    empty = cache_mod.Cache.parse({})
    empty.put("3/1", said("Free"), "sha", "", engine=matcher)
    checks.equal(empty.get("3/1").engine, matcher, "a matcher put on an empty slot writes it, as a matcher entry")

    over = held(matcher, "Free")
    over.put("3/1", said("Paid"), "sha-new", "fp2", engine=haiku)
    entry = over.get("3/1")
    checks.equal(
        (entry.identification["name"], entry.engine, entry.photo_sha256),
        ("Paid", haiku, "sha-new"),
        "a Haiku put replaces a matcher entry, and the entry now reads as paid",
    )
    cleared = held(haiku, "Human", cleared=True)
    cleared.put("3/1", said("Paid"), "sha-new", "fp2", engine=haiku)
    checks.equal(cleared.get("3/1").identification["name"], "Human", "a Haiku put still never replaces a cleared entry")

    free_entry = held(matcher, "Free")
    checks.equal(free_entry.reusable("3/1", "sha-old"), free_entry.get("3/1"), "a matcher entry is reusable by an ordinary paid press")
    checks.equal(free_entry.reusable("3/1", "sha-old", reread_matcher=True), None, "reread_matcher returns None for an uncleared matcher entry")
    checks.equal(free_entry.reusable("3/1", "sha-old", reread_matcher=False), free_entry.get("3/1"), "and reread_matcher off returns the entry")
    cleared_free = held(matcher, "Free", cleared=True)
    checks.equal(cleared_free.reusable("3/1", "sha-other", reread_matcher=True), cleared_free.get("3/1"), "a cleared matcher entry is returned by reread_matcher, whatever the photo says")
    paid = held(haiku, "Paid")
    checks.equal(paid.reusable("3/1", "sha-old", reread_matcher=True), paid.get("3/1"), "reread_matcher leaves a paid entry reusable")

    # THE REVIEW HOLD RIDES THE ENTRY: a second-look answer put with its pick comes back with it.
    pick = {"code": match.UNREAD_MARGIN, "name": "Raichu", "number": "026", "set": "Base Set", "floor": 0.91, "margin": 0.03}
    holder = cache_mod.Cache.parse({})
    holder.put("3/1", said("Paid"), "sha", "fp", engine=haiku, second_look=pick)
    checks.equal(holder.reusable("3/1", "sha").second_look, pick, "an entry put with second_look is reusable with it, unchanged")
    checks.equal(held(haiku, "Paid").get("3/1").second_look, None, "and an entry put without one has none")
    checks.equal(
        cache_mod.Cache.parse(holder.to_payload()).get("3/1").second_look, pick, "and the hold survives a round trip through the store payload"
    )

    old = cache_mod.Cache.parse(
        {"3/1": {"identification": said("Old"), "photo_sha256": "s", "prompt_fingerprint": "f", "at": "t"}}
    )
    checks.equal(old.get("3/1").engine, haiku, "an entry stored with no engine reads as haiku")
    checks.equal(
        (old.stale_prompt({"3/1": "other"}), held(matcher, "Free").stale_prompt({"3/1": "other"})),
        (["3/1"], []),
        "and is judged against the prompt, where a matcher entry never is",
    )


# ------------------------------------------------------------------------ the model verdict, the promo census, Prepare


def check_model_ready_hashes_once(checks: Checks) -> None:
    """`match.model_ready` hashes the 372 MB file once per (path, size, mtime), and again on a change.

    `GET /pipeline/match` is polled every few seconds. The pin is swapped for a small file's, and
    the hash function is replaced by a counter that calls the real one."""
    import os
    import tempfile

    checks.note("")
    checks.note("MODEL READY — one hash per stat, a new one after a change")
    body = b"MODEL" * 100
    saved = match.MODEL_BYTES, match.MODEL_SHA256, match.sha256_of_file
    calls: list = []

    def counting(path):
        calls.append(str(path))
        return saved[2](path)

    match.MODEL_BYTES, match.MODEL_SHA256, match.sha256_of_file = len(body), hashlib.sha256(body).hexdigest(), counting
    match._verdicts.clear()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "m.onnx"
            target.write_bytes(body)
            checks.ok(match.model_ready(target) and match.model_ready(target), "a right file is ready, twice")
            checks.equal(len(calls), 1, "and two calls with the same stat hash once")
            stat = target.stat()
            os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
            checks.ok(match.model_ready(target), "a changed mtime on the same bytes is still ready")
            checks.equal(len(calls), 2, "and a changed mtime hashes again")
            target.write_bytes(b"EVIL!" * 100)  # the pinned size, other content, a new mtime
            os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 9_000_000_000))
            checks.ok(not match.model_ready(target), "a file replaced in place with other bytes of the same size is not ready")
            checks.equal(len(calls), 3, "because the replacement was hashed, not trusted from the old verdict")
            target.write_bytes(body + b"x")
            checks.ok(not match.model_ready(target), "a file of another size is not ready")
            checks.equal(len(calls), 3, "and a size change is refused without a hash")
            target.write_bytes(body)
            os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 11_000_000_000))
            checks.ok(match.model_ready(target), "restored bytes are ready again")
            checks.equal(len(calls), 4, "after a fresh hash")
    finally:
        match.MODEL_BYTES, match.MODEL_SHA256, match.sha256_of_file = saved
        match._verdicts.clear()


def check_promo_census(checks: Checks) -> None:
    """`match.held_promo_games` names the games the store holds a promo card of, and ignores a sold one."""
    import sqlite3

    from server import capture_server
    from harness.tests.t7.common import capture_payload
    from store import db, files

    checks.note("")
    checks.note("PROMO CENSUS — the games a held promo card makes unsafe to read unhinted")
    with isolated_home():
        checks.equal(match.held_promo_games(), set(), "a store that does not exist holds no promo")
        for _ in range(3):
            capture_server.do_capture(capture_payload(1))
        conn = sqlite3.connect(db.path(files.inventory_dir()))

        def mark(index, set_name, game, state="captured"):
            conn.execute(
                "update cards set set_name=?, game=?, state=? where box=1 and idx=?",
                (set_name, game, state, index),
            )
            conn.commit()

        checks.equal(match.held_promo_games(), set(), "a store of cards with no set holds none")
        mark(1, "Origins Promos", "riftbound")
        checks.equal(match.held_promo_games(), {"riftbound"}, "a held promo card names its game")
        mark(2, "SV Black Star Promo", None, state="sold")
        checks.equal(match.held_promo_games(), {"riftbound"}, "a SOLD promo card is ignored")
        mark(3, "SV Black Star Promo", None)
        checks.equal(match.held_promo_games(), {"riftbound", "pokemon"}, "a held promo card with no game is a Pokemon one")
        conn.close()
    with isolated_home():
        capture_server.do_capture(capture_payload(1))
        db.path(files.inventory_dir()).write_bytes(b"this is not a database")
        checks.equal(match.held_promo_games(), {match.ALL_GAMES}, "a store that cannot be read holds a promo in every game, never none")


def check_prepare_clears_stale_part(checks: Checks) -> None:
    """Prepare removes a half file from a dead download even when the model itself is ready."""
    from cli import cmd_match

    checks.note("")
    checks.note("PREPARE — a stale .part goes, whether or not the model is ready")
    with isolated_home():
        part = match.model_path().with_name(match.MODEL_FILENAME + ".part")
        part.parent.mkdir(parents=True, exist_ok=True)
        part.write_bytes(b"half a model")
        real_ready = match.model_ready
        match.model_ready = lambda *_a, **_k: True
        try:
            said: list = []
            code = cmd_match.prepare(said.append, model_only=True)
        finally:
            match.model_ready = real_ready
        checks.equal(code, 0, "a model-only Prepare over a ready model exits 0")
        checks.ok(not part.exists(), "and the stale part file is gone")
        checks.ok(any("already here" in line for line in said), "and the model was not downloaded again")


def check_prepare_dead_child(checks: Checks) -> None:
    """A Prepare child that exited is not running, even while it is still a zombie of the server."""
    import subprocess
    import sys
    import time

    from server import pipeline_routes

    checks.note("")
    checks.note("PREPARE DEAD CHILD — an exited child (zombie or reaped) is not running, and the screen says so")
    for reaped in (False, True):
        with isolated_home():
            child = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(2)"], stdout=subprocess.PIPE)
            try:
                # EOF on the pipe means the child is exiting. It is not reaped until `child.wait()`,
                # so it ends as a zombie. A bounded look at its state, not an open-ended wait.
                child.stdout.read()
                for _ in range(100):
                    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(child.pid)], capture_output=True, text=True)
                    if stat.stdout.strip().startswith("Z"):
                        break
                    time.sleep(0.02)
                checks.ok(stat.stdout.strip().startswith("Z"), f"setup: the child is a zombie (ps says {stat.stdout.strip()!r})")
                if reaped:
                    child.wait()
                match.progress_path().parent.mkdir(parents=True, exist_ok=True)
                match.progress_path().write_text(json.dumps({
                    "state": "running", "phase": "fingerprints", "done": 15, "total": 1773,
                    "message": "Reading stock photos", "pid": child.pid, "started": 1.0, "at": 2.0,
                }))
                answer = pipeline_routes.do_pipeline_match()
            finally:
                child.wait()
            kind = "reaped" if reaped else "zombie"
            checks.equal(answer["running"], False, f"a {kind} child: GET /pipeline/match says running false")
            progress = answer["progress"] or {}
            checks.equal(progress.get("state"), "failed", f"a {kind} child: the progress state is failed")
            checks.ok(
                "Press Prepare to carry on" in progress.get("message", ""),
                f"a {kind} child: the message tells the owner to press Prepare again",
            )


def check_prepare_runtime_missing(checks: Checks) -> None:
    """With the model runtime not importable, Prepare refuses before it spawns, and GET says why."""
    import sys
    from http import HTTPStatus
    from unittest import mock

    from server import pipeline_routes

    checks.note("")
    checks.note("PREPARE RUNTIME MISSING — refused before any spawn, in plain words; GET carries `runtime_missing`")
    spawned: list = []
    with isolated_home(), mock.patch.dict(sys.modules, {"onnxruntime": None}), mock.patch.object(
        pipeline_routes.subprocess, "Popen", lambda *a, **k: spawned.append(a) or mock.Mock(pid=1)
    ):
        refused = None
        try:
            pipeline_routes.do_pipeline_match_prepare({"confirm": True})
        except pipeline_routes.PipelineRefusal as caught:
            refused = caught
        checks.ok(refused is not None, "Prepare is refused")
        checks.equal(getattr(refused, "code", None), "runtime_missing", "with the code runtime_missing")
        checks.equal(getattr(refused, "status", None), HTTPStatus.CONFLICT, "and status 409")
        checks.equal(spawned, [], "and nothing is spawned")
        words = str(refused or "").lower()
        checks.ok(
            bool(words) and not any(w in words for w in ("onnx", "module", "package", "python", "pip", "venv", "import")),
            "the sentence names no module, package or tool",
        )
        checks.equal(pipeline_routes.do_pipeline_match().get("runtime_missing"), True, "GET /pipeline/match: runtime_missing is true")
    with isolated_home():
        checks.equal(
            pipeline_routes.do_pipeline_match().get("runtime_missing"), False,
            "control: with the runtime importable, runtime_missing is false",
        )


def check_match_route_lane(checks: Checks) -> None:
    """`GET /pipeline/match` is a photo-lane route (a stat, one cached verdict, a count), and its siblings are not."""
    from server import capture_server

    checks.note("")
    checks.note("LANE — the free reader's state is polled, so it rides the photo lane")
    lane = capture_server.photo_lane_path
    checks.ok(lane("/pipeline/match"), "`/pipeline/match` is served by the photo lane")
    checks.ok(lane("/pipeline/match?x=1") and lane("/pipeline/match/"), "with a query or a trailing slash too")
    checks.ok(not lane("/pipeline/match/prepare"), "`/pipeline/match/prepare` is not: it spawns a download")
    checks.ok(not lane("/pipeline/preflight") and not lane("/pipeline/runs"), "and no other pipeline route is")


CHECKS = (
    check_matcher_accept_rule,
    check_model_download,
    check_identify_free_first,
    check_second_look_routing,
    check_second_look_agreement,
    check_disagree_candidates_hold_both,
    check_cache_engines,
    check_model_ready_hashes_once,
    check_promo_census,
    check_prepare_clears_stale_part,
    check_prepare_dead_child,
    check_prepare_runtime_missing,
    check_match_route_lane,
)
