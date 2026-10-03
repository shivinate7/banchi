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
from types import SimpleNamespace

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


def _read_one(sims, names, blocked=()):
    """One Riftbound card read against a pool whose cosines are `sims`, best first."""
    import numpy as np

    real_crop, real_embed = match._crop, match.embed
    match._crop = lambda _photo, _aspect: object()
    match.embed = lambda cards, _path=None: np.array([[1.0, 0.0, 0.0, 0.0]] * len(cards))
    try:
        request = match.Request("1/1", Path("unused.jpg"), "riftbound", "riftbound_card_v1")
        return match.read([request], _FakeIndex(sims, names, blocked))[0]
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
    weak = _read_one([0.7, 0.5, 0.4], names)
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
                real = match.read([request], index)[0]
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

    Three Pokemon photographs: `4/1` the free reader accepts, `4/2` and `4/3` it does not. Only
    the last two may reach the paid batch, the preflight says whether its count is estimated or
    measured, a press with no index is refused, and the run record keeps what the free reader
    thought of each card it passed on."""
    from cli import __main__ as cli_entry
    from cli import cmd_identify

    checks.note("")
    checks.note("IDENTIFY, FREE FIRST — fake matcher, fake batch (nothing paid, nothing downloaded)")

    def spoken(lines, prefix):
        return next((line for line in lines if line.startswith(prefix)), "")

    with isolated_home() as home:
        caps = Path(home) / "free-caps"
        caps.mkdir()
        for index in (1, 2, 3):
            identify_images.Image.new("RGB", (64, 89), (40 * index, 90 + 30 * index, 200 - 50 * index)).save(
                caps / f"4-00{index}.jpg", "JPEG"
            )
            (caps / f"4-00{index}.json").write_text(
                json.dumps({"box": 4, "position": index, "game": "pokemon", "set_hint": "SV09"}), "utf-8"
            )

        sent: list = []
        asked: list = []

        def fake_run_batch(requests, log=None, on_submit=None):
            outcomes = {}
            for request in requests:
                sent.append(request.custom_id)
                outcomes[request.custom_id] = batch.Outcome(
                    request.custom_id, batch.SUCCEEDED,
                    identification=prompt.parse(
                        {"name": "Raichu", "number": "026", "printed_total": "102",
                         "finish": "normal", "confidence": "high"},
                        request.strategy,
                    ),
                )
            return batch.BatchRun(outcomes=outcomes)

        def fake_read(requests, index, model=None, aspect=0.716, log=lambda _m: None):
            asked.append([r.key for r in requests])
            return [_accepted(r.key) if r.key == "4/1" else _unaccepted(r.key) for r in requests]

        real = (cmd_identify.batch.run_batch, match.read, match.status)
        cmd_identify.batch.run_batch = fake_run_batch
        match.read = fake_read
        argv = ["identify", str(caps), "--engine", "marqo-b"]

        def press(*extra):
            lines: list = []
            with quiet():
                code = cmd_identify.run(cli_entry.build_parser().parse_args(argv + list(extra)), lines.append)
            return code, lines

        try:
            # ------------------------------------------------ no index: estimated, and refused
            match.status = lambda *_a, **_k: {"ready": False}
            code, lines = press("--dry-run")
            checks.equal(code, 0, "a free dry run with no index exits 0")
            checks.equal(
                spoken(lines, "second look"),
                "second look     1 of 3 estimated",
                "with no index the second-look count is ESTIMATED from the held-out share (0.37 of 3)",
            )
            checks.equal(asked, [], "and the estimate read no photograph")
            code, lines = press()
            checks.equal(code, 1, "the press with no index is refused")
            checks.ok(
                any("not prepared" in line for line in lines),
                "and the refusal says the free reader is not prepared",
                "\n".join(lines[-4:]),
            )
            checks.equal(sent, [], "and nothing reached the paid batch")
            checks.equal(
                list((Path(home)).glob("**/identifications.json")), [], "and no run record was written"
            )

            # ------------------------------------------------ an index: measured, only 4/2 and 4/3 paid
            match.status = lambda *_a, **_k: {"ready": True}
            code, lines = press("--dry-run")
            checks.equal(code, 0, "a free dry run with an index exits 0")
            checks.equal(
                spoken(lines, "second look"),
                "second look     2 of 3 measured",
                "with an index the count is MEASURED by a free pass over the selection",
            )
            checks.equal(
                spoken(lines, "free read"), "free read       1 of 3 measured", "and so is the free read"
            )
            checks.equal(sent, [], "a dry run sends nothing")

            code, lines = press()
            checks.equal(code, 0, "the free press with an index exits 0")
            checks.equal(
                sorted(sent),
                ["4-2f-2", "4-2f-3"],
                "ONLY THE CARDS THE FREE READER DID NOT ACCEPT reach the Haiku batch (`4/2`, `4/3`)",
            )
            run_dirs = sorted(d for d in (Path(home) / "runs").iterdir() if d.is_dir()) if (Path(home) / "runs").is_dir() else []
            records = [p for d in run_dirs for p in [d / "identifications.json"] if p.exists()]
            cards = json.loads(records[-1].read_text("utf-8"))["cards"] if records else {}
            checks.equal(sorted(cards), ["4/1", "4/2", "4/3"], "the record holds all three cards")
            checks.equal(cards.get("4/1", {}).get("second_look"), None, "the accepted card carries no second_look")
            checks.equal(cards.get("4/1", {}).get("engine"), cache_mod.ENGINE_MATCHER, "and names the free reader as its engine")
            look = cards.get("4/2", {}).get("second_look") or {}
            checks.equal(
                (look.get("code"), look.get("name"), look.get("number"), look.get("set"), look.get("floor"), look.get("margin")),
                (match.UNREAD_MARGIN, "Raichu", "026", "Base Set", 0.91, 0.031),
                "a passed-on card carries second_look: why, the top pick, and the figures",
            )
            checks.equal(cards.get("4/2", {}).get("engine"), cache_mod.ENGINE_HAIKU, "and its answer names the paid read")
        finally:
            cmd_identify.batch.run_batch, match.read, match.status = real


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
        [routing.LOW_CONFIDENCE],
        "it routes to review, as low_confidence",
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

    old = cache_mod.Cache.parse(
        {"3/1": {"identification": said("Old"), "photo_sha256": "s", "prompt_fingerprint": "f", "at": "t"}}
    )
    checks.equal(old.get("3/1").engine, haiku, "an entry stored with no engine reads as haiku")
    checks.equal(
        (old.stale_prompt({"3/1": "other"}), held(matcher, "Free").stale_prompt({"3/1": "other"})),
        (["3/1"], []),
        "and is judged against the prompt, where a matcher entry never is",
    )


CHECKS = (
    check_matcher_accept_rule,
    check_model_download,
    check_identify_free_first,
    check_second_look_routing,
    check_cache_engines,
)
