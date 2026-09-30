"""T7 group: crop preview, export fetch, key rotation.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import json
import http.server
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import envfile

from pathlib import Path
from typing import Optional
from harness.tests import Checks
from cli import resolve, runs
from identify import batch
from pipeline import games, tcgcsv
from server import capture_server, pipeline_routes, tcg_export
from store import files
from store.session import Store
from scripts import serve
from harness.tests.t7.common import (
    _SERVE_ROOT,
    ARTICUNO_SKU,
    DUNSPARCE_SKU,
    FIXTURE_EXPORT,
    QuietHandler,
    SEAM_SKUS,
    _spawn_server,
    error_code,
    identifications_for,
    isolated_home,
    request,
    seam_run,
    write_export,
)

def check_crop_preview(checks: Checks) -> None:
    """D32 — `POST /pipeline/crop-preview`: what a reading sends, before it is paid for.

    ITS OWN ISOLATED HOME, this file's own lesson yet again: the block writes photographs
    into a box, and the blocks above count records over boxes they build card by card.

    WHAT IT IS FOR. D32's amendment gave the crop three named pairs and a sentence each,
    because the owner could not read the control: *"walk me through how im supposed to
    understand crop with just this dialog box"*. The sentences are prose about pixels. This
    route answers the same question as a picture — the cut, and the collector-number strip at
    the resolution the reading delivers — and it has to be free, because it is pressed while
    the reading is being CHOSEN, before the preflight and long before the confirm.

    THE PROPERTY WORTH ASSERTING MOST IS A NEGATIVE ONE: it writes nothing. It sits in the one
    module of this server that can spend money, one route above the one that does, so
    "creates no run directory, no scope directory, no store write" is not a detail — it is
    what makes it safe to fire on every chip press.
    """
    try:
        from PIL import Image, ImageDraw  # noqa: F401
    except ImportError:
        checks.note("crop preview: Pillow absent, the route's own refusal path is all that runs")

    from server import pipeline_routes

    def photograph(path, *, card=True):
        """A bright card on a dark ground — the one premise `geometry.detect_card` needs."""
        from PIL import Image, ImageDraw

        # BIG ENOUGH THAT THE MAX EDGE BINDS, which the first draft was not: a 900x1600 frame
        # holding a 420x586 card crops to ~470x655, and `downscale` never upscales — so 1200
        # and 900 both sent it untouched and the band came back the same size at both. The
        # test was right and the fixture was wrong. A cropped long edge of ~1500 means both
        # readings actually resize, which is the condition the rig's 2160x3840 frames meet.
        frame = Image.new("RGB", (1500, 2600), (26, 28, 32))
        if card:
            draw = ImageDraw.Draw(frame)
            # 1000x1396 is CARD_ASPECT — 63:88, 0.716. An earlier draft drew 420x786 and the
            # detector correctly refused every frame: the shape gates are what stop it
            # cropping a guess, so a fixture that is not card-shaped tests the refusal path.
            draw.rectangle((300, 500, 1300, 1896), fill=(238, 232, 214))
            # A dark strip where a collector number prints, so the band is not blank paper.
            draw.rectangle((350, 1780, 700, 1840), fill=(40, 40, 40))
        frame.save(path, format="JPEG", quality=92)

    with isolated_home() as home:
        box = home / "captures" / "cards" / "box3"
        box.mkdir(parents=True)
        for index in (1, 2, 3, 4, 5, 6):
            photograph(box / f"{index:04d}.jpg")
            (box / f"{index:04d}.json").write_text(
                json.dumps({"box": 3, "index": index, "game": "pokemon"}), "utf-8"
            )

        runs_before = sorted(p.name for p in files.runs_dir().iterdir()) if files.runs_dir().is_dir() else []
        home_before = sorted(entry.name for entry in home.iterdir())

        # --- the refusals, each in its own code ------------------------------------------
        # A BARE `{}` IS NO LONGER A REFUSAL, AND THAT IS THE THESIS. `box_required` used to
        # fire here — *"A run is always scoped to one box"* — so the preview could not be asked
        # about a selection that was not a drawer. An empty payload is now every photograph in
        # the store, which for this fixture is box 3's six, and the first of them is previewed.
        for payload, code, why in (
            ({"box": 0}, "selection_invalid", "a box that is not a positive integer"),
            ({"box": 99}, "selection_is_empty", "a box nothing has been photographed into"),
            ({"box": 3, "keys": []}, "selection_invalid", "an empty selection"),
            (
                {"box": 3, "indices": [1]},
                "selection_invalid",
                "`indices`, which is one idea spelled twice — refused BY NAME rather than "
                "ignored, because a filter that silently did nothing would be a press over the "
                "whole drawer reported as a press over one card",
            ),
            ({"section": 2}, "selection_invalid", "a section with no drawer to be inside"),
            ({"box": 3, "bid": 3}, "selection_invalid", "a drawer named twice, two ways"),
            ({"box": 3, "max_edge": 40}, "max_edge_invalid", "a max edge below the floor"),
            ({"box": 3, "max_edge": "1200"}, "max_edge_invalid", "a max edge that is a string"),
            ({"box": 3, "offset": -1}, "offset_invalid", "a negative offset"),
        ):
            try:
                pipeline_routes.do_pipeline_crop_preview(payload)
                checks.ok(False, f"crop preview refuses {why}", "it answered instead")
            except pipeline_routes.PipelineRefusal as refusal:
                checks.equal(refusal.code, code, f"crop preview refuses {why} as `{code}`")

        # `max_edge` is validated by the SAME function the preflight uses, so a reading the
        # preview accepts is a reading `identify` will accept. A second range check beside the
        # second caller is a refusal that can disagree with the one the run actually gets.
        try:
            pipeline_routes._identify_flags({"max_edge": 40})
            checks.ok(False, "and the preflight refuses the same value", "it accepted it")
        except pipeline_routes.PipelineRefusal as refusal:
            checks.equal(
                refusal.code,
                "max_edge_invalid",
                "and the preflight refuses the same value through the same validator",
            )

        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            return

        # --- the cut, and the seam it shares with the run --------------------------------
        #
        # `geometry` IS DELIBERATELY NOT IMPORTED HERE, and the reason is a check in
        # `scripts/docs-audit.py`'s own self-test rather than taste: it proves the `tested_by
        # reach` row does not follow imports transitively by asserting that T7 reaches `store`
        # directly and does NOT reach `geometry` through `cli`. A direct import here would make
        # that fixture unable to tell a transitive follow from a real one, and it went red the
        # first time this block was written.
        #
        # Nothing is lost. The identity — that the rectangle the screen draws is the one
        # `card_crop` cuts — is T6's, asserted there against the detector and observed failing
        # against a `card_crop` that had stopped using `crop_rect`. What belongs HERE is the
        # route's own contract: that it reports a rectangle at all, that the rectangle is a
        # card, and that it lands inside the photograph the screen will draw it over.
        cropped = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 1200}
        )
        checks.equal(cropped["total"], 6, "the preview counts the photographs in scope")
        checks.equal(
            cropped["sample"]["index"], 1, "and shows ONE card, the one the offset names"
        )
        first = cropped["sample"]
        checks.ok(first["rect"] is not None, "a cropping reading reports where the cut falls")
        if first["rect"] is not None:
            left, top, right, bottom = first["rect"]
            width, height = first["frame"]
            checks.ok(
                0 <= left < right <= width and 0 <= top < bottom <= height,
                "and it lands inside the photograph the screen draws it over — the overlay is "
                "positioned as a percentage of the frame, so a cut that ran off the picture "
                "would be drawn outside it",
                f"{first['rect']} against {first['frame']}",
            )
            aspect = (right - left) / (bottom - top)
            checks.ok(
                abs(aspect - 0.716) < 0.05,
                "and it is CARD-SHAPED, which is the aspect correction reaching the screen: a "
                "flat pad over a box short for its width is what cut 38 collector numbers off "
                "box 2, and the preview would have drawn that crop as though it were fine",
                f"aspect {aspect:.3f}",
            )

        # --- the walk: one card, `offset`, and it WRAPS ----------------------------------
        #
        # Three evenly spaced cards for a few hours, on the argument that cards move on the
        # tray so the front of a box does not stand for it. The owner overruled it on the only
        # ground that decides whether a picture works: three abreast are three small pictures.
        # The spread is reached by walking now, which is also the only version of it that lets
        # you look at a card you actually suspect.
        walked = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 1200, "offset": 2}
        )
        checks.equal(walked["sample"]["index"], 3, "the offset walks the box one card at a time")
        wrapped = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 1200, "offset": 6}
        )
        checks.equal(
            wrapped["sample"]["index"],
            1,
            "and it WRAPS rather than clamping — a stepper that stops at the end of a 543-card "
            "box leaves the operator pressing a key that does nothing",
        )
        checks.equal(wrapped["offset"], 0, "and the answer reports the offset it actually used")

        # --- the whole-frame reading, and the two ways `rect` can be null ----------------
        whole = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": False, "max_edge": 1568}
        )
        checks.ok(
            whole["sample"]["rect"] is None,
            "the whole-frame reading reports no cut, because there is none",
        )
        checks.ok(
            whole["sample"]["method"] is not None,
            "but it still reports the detector's answer — `rect: null` because the crop is "
            "OFF and `rect: null` because detection REFUSED are opposite facts to an "
            "operator, and `method` is the only thing that tells them apart",
        )
        checks.ok(
            whole["sample"]["sent"] != cropped["sample"]["sent"],
            "and the two readings send different bytes, which is the whole subject",
        )

        # --- the band: the half that moves when the max edge moves -----------------------
        cheap = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 900}
        )
        checks.equal(
            cheap["sample"]["rect"],
            cropped["sample"]["rect"],
            "THE RECTANGLE IS IDENTICAL AT 1200 AND AT 900 — the crop decides framing and the "
            "max edge decides resolution, which is why the band exists at all",
        )
        checks.ok(
            cheap["sample"]["band_px"][0] < cropped["sample"]["band_px"][0],
            "and the collector number occupies FEWER PIXELS at 900 — the only half of the "
            "preview that can tell the two cropping readings apart",
            f"{cheap['sample']['band_px']} against {cropped['sample']['band_px']}",
        )

        # --- THE PICTURE IS THE PAYLOAD, WHICH IS WHAT MAKES ANY OF IT VISIBLE -----------
        #
        # The owner: "the crop preview should also show the depixelation reflected as you
        # change the options". The frame drew `GET /photo` — the same bytes at every reading —
        # so the one thing being changed was the one thing the picture could not show.
        checks.ok(
            str(cropped["sample"]["sent_image"]).startswith("data:image/jpeg;base64,"),
            "the sample carries the BYTES THAT WILL BE SENT, not the file on disk",
        )
        checks.ok(
            cropped["sample"]["sent_image"] != cheap["sample"]["sent_image"],
            "and they are different bytes at 1200 and at 900 — which is the whole of what the "
            "operator was asking to see",
        )
        checks.ok(
            cropped["sample"]["band_rect"] is not None
            and cropped["sample"]["band_rect"][2] <= cropped["sample"]["sent"][0]
            and cropped["sample"]["band_rect"][3] <= cropped["sample"]["sent"][1],
            "the band is a RECTANGLE INTO those bytes rather than a second image, so the 1:1 "
            "view and the frame cannot disagree about what is being sent — there is no second "
            "file to disagree with",
            f"{cropped['sample']['band_rect']} in {cropped['sample']['sent']}",
        )

        # --- THE BAND IS THE REGISTRY'S TO GRANT, PER CARD -------------------------------
        #
        # THE DEFECT THIS ROUTE SHIPPED WITH, found by the owner on box 1. It cut
        # `geometry/crop.py`'s number band over every game, and `pipeline/games.py` refuses
        # that in writing: "the bands are fractions measured on a Pokemon card. Nothing has
        # measured where a Riftbound card puts its title or its number, and a band claimed
        # without that measurement is cut over the wrong pixels." Box 1 is Riftbound, and the
        # strip drew its RULES TEXT as though it were a collector number.
        (box / "0001.json").write_text(
            json.dumps({"box": 3, "index": 1, "game": "riftbound"}), "utf-8"
        )
        rift = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 1200}
        )
        checks.equal(rift["sample"]["game"], "riftbound", "the sample carries the card's game")
        checks.equal(
            rift["sample"]["band_rect"],
            None,
            "a game whose `crop_bands` claims no number band gets NO RESTING AIM — the same "
            "refusal `crop_regions` makes, reached through the same registry field",
        )
        checks.ok(
            rift["sample"]["band_absent"] is not None
            and "riftbound" in rift["sample"]["band_absent"],
            "and the screen is told WHY, in the registry's own terms — and the 1:1 view still "
            "works, because the operator can point at the identifier themselves",
        )
        checks.ok(
            rift["sample"]["rect"] is not None,
            "while the CUT is unaffected — a card is 63x88mm whatever is printed on it, so "
            "the crop is right for every game even where no band has been measured",
        )
        (box / "0001.json").write_text(
            json.dumps({"box": 3, "index": 1, "game": "pokemon"}), "utf-8"
        )

        # --- a photograph with no card in it ---------------------------------------------
        photograph(box / "0001.jpg", card=False)
        refused = pipeline_routes.do_pipeline_crop_preview(
            {"box": 3, "crop": True, "max_edge": 1200}
        )
        checks.equal(
            refused["sample"]["method"],
            None,
            "a frame the detector cannot find a card in reports no method, so the screen can "
            "say the card is going at whole-frame cost rather than leaving it inferred from a "
            "missing rectangle",
        )

        # --- and it wrote nothing ---------------------------------------------------------
        runs_after = sorted(p.name for p in files.runs_dir().iterdir()) if files.runs_dir().is_dir() else []
        checks.equal(
            runs_after,
            runs_before,
            "TEN PREVIEWS CREATED NO RUN DIRECTORY. It lives in the module that can spend, "
            "one route above the one that does, and it is fired on every chip press and every "
            "press of an arrow key",
        )
        # AND IT WROTE NOTHING ANYWHERE, WHICH IS NEW AND IS COUNTED (D180).
        #
        # THIS ROUTE BUILT EVERY SCOPE DIRECTORY ON THE OPERATOR'S CHECKOUT. Measured
        # 2026-09-12: 264 of them under `.scopes/`, and 264 of 264 are named `box<n>-1-<stamp>`
        # — a selection of exactly ONE card, which is what stepping this preview does. Not one
        # was ever a submission. A free read that had to write symlinks and then be swept was
        # the clearest evidence the directory was standing in for a vocabulary that did not
        # exist, and the count is the assertion because the OUTCOME never changed: the preview
        # answered correctly the whole time.
        #
        # THE WHOLE HOME IS COMPARED AND NOT JUST `.scopes`, deliberately. An assertion naming
        # the directory that was deleted can only ever pass once the deletion has happened; one
        # over the home's own top level sees the NEXT temporary directory somebody adds here
        # too, and this is the route that is fired on every chip press and every arrow key.
        checks.equal(
            sorted(entry.name for entry in home.iterdir()),
            home_before,
            "TEN PREVIEWS ADDED NOTHING TO THE HOME AT ALL — no scope directory, no run, "
            "nothing to sweep. The 264 symlink directories this route left on the operator's "
            "checkout were the old shape's only trace, and a ticked selection is a list of "
            "position keys on the wire now",
        )

def check_export_fetch(checks: Checks) -> None:
    """D65: the Filtered Export fetched instead of downloaded, and every refusal in the way.

    ITS OWN `isolated_home`, this file's own repeated lesson — and its own ENVIRONMENT too,
    which is new. This is the first section that reads `.env`, and one that left
    `TCGPLAYER_STORE_COOKIE` or `PKMNSCAN_TCG_EXPORT_URL` set behind it would point every
    later fetch in this process somewhere unexpected.

    THE FETCH IS AIMED AT A LOCAL SOCKET AND NEVER AT TCGPLAYER. `server/tcg_export.py` takes
    its URL from an override that refuses to carry the cookie over plain http anywhere but
    loopback, and that guard is what makes this testable at all: a real fetch would need the
    owner's live session, would run at the end of every turn, and would be measuring their
    portal filter rather than this code.

    WHAT IS PROVABLE HERE AND WHAT IS NOT, said plainly so a green run is not misread.
    Provable: that a session redirected to a login page never becomes a parsed CSV, that a WAF
    403 has its own name, that a re-fetch of identical bytes lands on the file the run already
    holds, that a refusal
    keeps nothing, that the cookie reaches the socket and reaches no file, and that a fetched
    file is the one `join` then actually joins against. NOT provable: whether TCGplayer's WAF
    accepts this client when the request carries a real session. That is one live fetch by the
    owner, and D65 names it as owed rather than implying it has happened.
    """
    keys = (
        "PKMNSCAN_TCG_EXPORT_URL",
        "TCGPLAYER_STORE_COOKIE",
        "PKMNSCAN_TCG_USER_AGENT",
        # THE CLAIM HAS A SECOND HOME SINCE 2026-09-11 and clearing the set no longer clears
        # it: `envfile.FROM_FILE_ENV` carries the lifted names across a spawn, so it lives in
        # `os.environ` and outlives a `_from_file.clear()`. Saved here and popped below with
        # the rest of the ritual. Measured when it was not: the PRECEDENCE case at the end of
        # this block read `two` instead of `from-env`, because the marker published at harness
        # import still said the cookie came from a file and re-reading the file was the right
        # answer to that.
        envfile.FROM_FILE_ENV,
    )
    previous = {name: os.environ.get(name) for name in keys}

    # THE FAKE PORTAL. It serves whatever `stub["mode"]` currently says, which is how one
    # socket covers a good download, an expired session in BOTH of its shapes, a WAF block and
    # an export that has quietly narrowed. Real fixture rows throughout — `write_export`
    # builds them out of the committed SV09 file — because the receipt counts rows and SKUs,
    # and invented rows would be testing the fixture.
    stub = {
        "mode": "csv",
        "body": b"",
        "seen": [],
        "posted": [],
        "got": [],
        # One set, so a hint can resolve to exactly it and the positive check has something
        # to be positive about. `0` is the portal's own "all" row and is never a set.
        "filters": {
            "Sets": [
                {"Text": "All Set Names", "Value": "0"},
                {"Text": "SV09: Journey Together", "Value": "4242"},
            ],
            "Rarities": [{"Text": "All Rarities", "Value": "0"}],
            "Conditions": [{"Text": "All Conditions", "Value": "0"}],
            "Printings": [{"Text": "All Printings", "Value": "0"}],
        },
    }

    class Portal(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # noqa: A003
            pass

        def _serve(self):
            stub["seen"].append(self.headers.get("Cookie"))
            mode = stub["mode"]
            if mode == "logon":
                self.send_response(302)
                self.send_header("Location", "/admin/account/logon?ReturnUrl=%2fAdmin")
                self.end_headers()
                return
            if mode == "html200":
                body = b"<html><body>Please sign in</body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif mode == "waf":
                body = b""
                self.send_response(403)
            elif mode == "boom":
                body = b""
                self.send_response(503)
            else:
                body = stub["body"]
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

    # THE MODULE MAKES TWO CALLS AND THE STUB ANSWERS BOTH (D65). `getjsonfilters` is a GET
    # returning the category's vocabulary; the export is a POST whose body carries the scope.
    # The POST body is RECORDED, because the assertion worth making is not that a request
    # happened but that the scope the run implies is the scope that went out.
    def _do_GET(self):  # noqa: N802
        # THE LIVE DOWNLOAD IS A GET AND ITS QUERY STRING IS THE WHOLE REQUEST (D104). Recorded
        # for the same reason the POST body is: the assertion worth making is not that a fetch
        # happened but that what went out was what the portal answers with rows.
        if "DownloadMyExportCSV" in self.path:
            stub["got"].append(self.path)
            body = stub.get("live_body", stub["body"]) or b""
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)
            return
        if "getjsonfilters" in self.path:
            stub["seen"].append(self.headers.get("Cookie"))
            body = json.dumps(stub["filters"]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._serve()

    def _do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        stub["posted"].append(self.rfile.read(length).decode("utf-8", "replace"))
        self._serve()

    Portal.do_GET = _do_GET
    Portal.do_POST = _do_POST

    portal = http.server.HTTPServer(("127.0.0.1", 0), Portal)
    portal_thread = _spawn_server(portal)

    cookie = "TCGAuthTicket_Production=t7-not-a-real-session"
    os.environ["PKMNSCAN_TCG_EXPORT_URL"] = (
        f"http://127.0.0.1:{portal.server_address[1]}/admin/pricing/downloadexportcsv"
    )
    os.environ["TCGPLAYER_STORE_COOKIE"] = cookie
    os.environ.pop("PKMNSCAN_TCG_USER_AGENT", None)

    # HERMETIC AGAINST THE DEVELOPER'S OWN `.env`, WHICH THIS BLOCK WAS NOT — and the way it
    # was not is a secret leaving the place it belongs, not merely a test going red.
    #
    # `envfile._from_file` IS A PROCESS GLOBAL AND IT IS PART OF THE PRECEDENCE RULE.
    # `get_live` returns an environment variable only when the name is in `os.environ` AND
    # NOT in that set — that pair is how "a real environment variable wins" is told apart
    # from a name this module itself lifted out of the file, which after `load` look
    # identical in `os.environ`. The rule is right and `envfile.py` is not what is wrong
    # here. What is wrong is that ANY earlier `load()` in this process — the harness imports
    # six other tests and the server package — records `TCGPLAYER_STORE_COOKIE` in that set
    # on a machine whose `.env` carries one. The line above then sets the variable, `get_live`
    # sees a name it believes it owns, and reads THE FILE instead.
    #
    # SO THE STUB WAS SENT THE OPERATOR'S REAL SESSION. Measured on this Mac: the fetch went
    # out carrying the live 2,784-byte cookie rather than the 44-byte fixture above, and
    # `stub["seen"]` held it for the rest of the block — 127.0.0.1, in memory, never written,
    # but a bearer instrument (D65) somewhere it was never meant to be, and one `checks.equal`
    # failure message away from being printed. That is why this is fixed here rather than
    # filed: two red checks are the SYMPTOM.
    #
    # AND IT IS INVISIBLE ON A CLEAN CHECKOUT, which is why it stood. With no `.env` the set
    # is empty, both checks pass, and the block is only ever wrong on the one machine that
    # has the secret it is about.
    #
    # WHICH HALF IS THE FIX, MEASURED RATHER THAN ASSUMED — three mutations, each run with a
    # `load()` in front of it because that is the only condition either defect appears under:
    #
    #   neither half          all three checks red, this block's guard first
    #   redirect only         the PRECEDENCE check still red, at the end of the rotation cases
    #   cache reset only      green
    #
    # So **the cache reset is the fix** and the redirect is a second wall. The middle row is
    # the interesting one and is why both are kept: the rotation cases below point `ENV_FILE`
    # at their own file, so a redirect here does not reach them — only an unpolluted
    # `_from_file` makes `get_live` honour the variable they set. The redirect earns its place
    # separately, by making the block hermetic no matter what any future edit does before it:
    # `_parse` answers `{}` for a missing path, so the real `.env` cannot be read here at all.
    #
    # The rotation cases move `ENV_FILE` again on top of this and restore what they found,
    # which is now the sentinel rather than the operator's own file.
    env_before = (envfile.ENV_FILE, set(envfile._from_file), envfile._loaded)
    envfile.ENV_FILE = Path(tempfile.gettempdir()) / "t7-export-fetch-no-such.env"
    envfile._from_file.clear()
    os.environ.pop(envfile.FROM_FILE_ENV, None)  # the third location; see `keys` above
    envfile._loaded = False

    try:
        with isolated_home() as home:
            httpd = capture_server.CaptureServer(("127.0.0.1", 0), QuietHandler)
            port = httpd.server_address[1]
            thread = _spawn_server(httpd)
            try:
                # THE FIXTURE COOKIE IS WHAT THIS BLOCK READS, ASSERTED BEFORE ANYTHING
                # FETCHES. Everything below sends a Cookie header to a stub and then reads
                # `stub["seen"]` back, so if the reader is answering out of the developer's
                # real `.env` the whole block is exercising the wrong secret — silently, and
                # only on the machine that has one. The setup above has the mechanism; this
                # is the one line that keeps the fix from quietly coming undone, and it is
                # first so a failure names the CAUSE instead of surfacing as two puzzling
                # cookie mismatches four hundred lines apart.
                checks.equal(
                    envfile.get_live("TCGPLAYER_STORE_COOKIE"),
                    cookie,
                    "the reader answers this block's own fixture cookie — `envfile._from_file`"
                    " is a process global, and any earlier `load()` over a real `.env` makes "
                    "`get_live` believe it owns the name and read the FILE past the variable "
                    "set here (D65: that value is a bearer instrument, and it was reaching "
                    "the stub)",
                )

                cards = [
                    (3, 1, "Dunsparce", "120/159", "normal"),
                    (3, 2, "Articuno ex", "161/159", None),
                ]
                run, _ = seam_run(checks, cards)
                directory = run.directory

                # ------------------------------------- THE BASELINE IS A HINTED POKEMON RUN
                #
                # AND IT HAS TO BE, BECAUSE `pokemon` CARRIES `export_needs_hint`. Every
                # fetch below this line is a fetch this block wants to SUCCEED — it is
                # testing the transport, the reuse, the receipt and the join seam, using
                # Pokemon as the stand-in for "a catalogued game". An unhinted Pokemon run
                # is refused before a socket opens now, so leaving the cards bare would
                # fail forty assertions about the transport with a message about set hints.
                #
                # THIS IS ALSO THE REALISTIC STATE: the owner's store holds 543 Pokemon
                # cards and 543 of them carry `ME01`. Unanimous is what a Pokemon run
                # looks like; the bare one is the defect, and it is asserted where the
                # refusal is built rather than assumed for a thousand lines here.
                def hint_run(run_dir, hinted):
                    """Give the first `hinted` of a run's cards a set hint, clear the rest."""
                    path = run_dir / pipeline_routes.run_files.IDENTIFICATIONS
                    payload = json.loads(path.read_text())
                    for at, key in enumerate(sorted(payload["cards"])):
                        payload["cards"][key].pop("set_hint", None)
                        if at < hinted:
                            payload["cards"][key]["set_hint"] = "SV09"
                    path.write_text(json.dumps(payload))

                def hint_cards(hinted):
                    """`hint_run` over THIS block's first run, which most checks here use."""
                    hint_run(directory, hinted)

                hint_cards(len(cards))
                whole = write_export(home / "whole.csv")
                stub["body"] = whole.read_bytes()

                # WHERE A FETCHED EXPORT LIVES SINCE D166: the GAME's own
                # directory under `inventory/.exports/`, store-wide, not the run's. Every
                # assertion below that used to read the run directory reads this instead,
                # which is the move — and `run_local()` is kept beside it so the two
                # locations can be told apart rather than conflated.
                exports_root = home / "inventory" / files.EXPORTS_DIRNAME

                def kept(game="pokemon"):
                    holder = exports_root / game
                    if not holder.is_dir():
                        return []
                    # THE SUFFIX IS PART OF THE FILTER, because the export's own scope note
                    # sits beside it carrying the same prefix. Matching on the prefix alone
                    # counts a file per export twice and reads as a dedupe that did not fire.
                    return sorted(
                        entry.name
                        for entry in holder.iterdir()
                        if entry.name.startswith(pipeline_routes.FETCHED_PREFIX)
                        and entry.name.endswith(".csv")
                    )

                def fetched_files(game="pokemon"):
                    return kept(game)

                def run_local():
                    return sorted(
                        entry.name
                        for entry in directory.iterdir()
                        if entry.name.startswith(pipeline_routes.FETCHED_PREFIX)
                    )

                def fetch(payload=None):
                    return request(
                        port,
                        "POST",
                        f"/pipeline/runs/{directory.name}/export",
                        payload=payload or {},
                    )

                # ------------------------------------------------ the transport refusals
                for mode, expected, label in (
                    (
                        "logon",
                        "tcg_session_expired",
                        "a session redirected to the login page refuses BY NAME rather than "
                        "following the redirect — an HTML login page parsed as a CSV is the "
                        "failure this exists to prevent, and it would have arrived as an "
                        "empty catalog blaming the export",
                    ),
                    (
                        "html200",
                        "tcg_session_expired",
                        "and a login page served as a 200 refuses the same way: the portal "
                        "does not have to redirect for the session to be the thing that is "
                        "wrong, so the body is read as well as the status",
                    ),
                    (
                        "waf",
                        "tcg_blocked",
                        "a 403 gets its own code, because the WAF declining this client and "
                        "the session expiring have different remedies — and one of them is "
                        "an environment variable this refusal names",
                    ),
                    (
                        "boom",
                        "tcg_unavailable",
                        "and a 5xx says it is TCGplayer's end rather than this one",
                    ),
                ):
                    stub["mode"] = mode
                    status, raw, _ = fetch()
                    checks.equal((status, error_code(raw)), (502, expected), label)
                checks.equal(
                    (fetched_files(), run_local()),
                    ([], []),
                    "and NOT ONE of those refusals left a file — in the game's directory or "
                    "in the run's. A directory accumulating a dead export per failed press "
                    "stops explaining itself, and the shared one has more readers to "
                    "confuse than the run directory ever had",
                )

                # ------------------------------------------------------- the good download
                stub["mode"] = "csv"
                status, raw, _ = fetch()
                body = json.loads(raw or b"{}")
                checks.equal(
                    (status, body.get("ok"), body.get("previous")),
                    (200, True, {"pokemon": {"file": "export.csv", "rows": 3, "skus": 3}}),
                    "the ordinary case: the export downloads, `exports_for` rules on it "
                    "before anything is joined, and the receipt carries what the last join "
                    "used — per game, its file, rows and SKUs — and refuses nothing on it",
                )
                checks.equal(
                    (body.get("skus"), body.get("games")),
                    (3, ["pokemon"]),
                    "and the report is in the terms the operator filters the portal in: how "
                    "many SKUs came back, and which game the file answers for off its own "
                    "Product Line cells rather than off its name",
                )
                # identity-follows-sku.md §3.2, fill point 1: THE SAME FETCH ALSO FOLDS ITS
                # ROWS INTO THE `skus` TABLE, in the same press that keeps the file — never a
                # second request. All three of `write_export`'s own seam SKUs land, and the
                # ordinary Pokemon SKU splits into a grade and a printing.
                sku_table = Store().read().skus.entries
                checks.ok(
                    all(sku in sku_table for sku in SEAM_SKUS),
                    "every SKU the fetch carried is in the table after the press, with no "
                    "second call",
                    f"table keys: {sorted(sku_table.keys())}",
                )
                if DUNSPARCE_SKU in sku_table:
                    dunsparce_row = sku_table[DUNSPARCE_SKU]
                    checks.equal(
                        (dunsparce_row.product_line, dunsparce_row.grade),
                        ("Pokemon", "Near Mint"),
                        "and the row carries the game's own Product Line cell and the grade "
                        "`store/skus.py:split_condition` reads off its own Condition cell",
                    )
                kept_now = fetched_files()
                checks.equal(
                    len(kept_now), 1, "exactly one file is kept, it is the one just fetched"
                )
                checks.equal(
                    kept_now[0] if kept_now else None,
                    body.get("file"),
                    "the response NAMES the file it wrote, which is what the join is then "
                    "handed — a fetch that kept a file the client could not name would be a "
                    "server-only capability",
                )
                checks.ok(
                    any(seen == cookie for seen in stub["seen"]),
                    "the cookie reached the socket — a fetch that quietly sent none would "
                    "look identical here against a stub that does not check it",
                )

                # ------------------------------------- THE OPSEC RULE, ASSERTED NOT ASSUMED
                leaked = sorted(
                    entry.name
                    for entry in directory.iterdir()
                    if entry.is_file() and cookie.encode() in entry.read_bytes()
                )
                checks.equal(
                    leaked,
                    [],
                    "and the session cookie is in NO file this run holds. It is a bearer "
                    "instrument, `.env` is the only place it lives, and a run directory is "
                    "the one thing here meant to be read later by somebody else",
                )

                # ------------------------------------------- the fetched file reaches join
                status, raw, _ = request(
                    port,
                    "POST",
                    f"/pipeline/runs/{directory.name}/join",
                    payload={"fetched": [kept_now[0]]},
                )
                checks.equal(
                    (status, json.loads(raw or b"{}").get("ok")),
                    (200, True),
                    "the join takes the fetched file BY NAME rather than by re-upload — the "
                    "server already holds the bytes, and sending a megabyte back through the "
                    "browser to arrive at them is not a step",
                )
                recorded = runs.open_run(directory).exports_by_game.get("pokemon")
                checks.equal(
                    recorded.name if recorded else None,
                    kept_now[0],
                    "and the manifest now records THAT file as what pokemon was joined "
                    "against, which is the seam: a route that fetched a file the join never "
                    "used would report success and change nothing",
                )

                # ------------------------------------------- IDENTICAL BYTES, ONE FILE
                #
                # The name put a one-second stamp BEFORE the digest, so no two fetches a
                # second apart ever composed the same name and a re-fetch of identical bytes
                # always added a copy — run `2026-08-31-box3-01` holds two byte-identical
                # 366 KB exports 29 seconds apart, while the comment above the name claimed
                # the opposite. The digest is looked up first now, and a hit IS the file.
                #
                # FORCED, AND THAT IS WHAT MAKES IT A DEDUPE TEST. Without `refresh` this
                # press would answer out of the file already on disk without opening a
                # socket — which is a different saving and would leave the dedupe itself
                # unexercised. Forcing the fetch is what puts identical bytes back through
                # the digest lookup, which is the thing being asserted.
                status, raw, _ = fetch({"refresh": True})
                body = json.loads(raw or b"{}")
                checks.equal(
                    (status, body.get("ok"), fetched_files(), body.get("file")),
                    (200, True, kept_now, kept_now[0]),
                    "a re-fetch of identical bytes lands on the file the run already holds "
                    "— still one file, and the receipt names it — rather than adding a "
                    "second copy under a later stamp",
                )
                checks.equal(
                    (body.get("previous") or {}).get("pokemon", {}).get("file"),
                    kept_now[0],
                    "and `previous` names that same file, because it is what the last join "
                    "used: the receipt says so rather than refusing over a comparison of a "
                    "file with itself",
                )

                # --------------------------------------------------- naming a file by hand
                for wanted, expected_status, expected, label in (
                    (
                        ["../../etc/passwd"],
                        400,
                        "fetched_invalid",
                        "a name that is not a fetched export refuses by SHAPE, so nothing "
                        "built from a request is ever joined onto a path",
                    ),
                    (
                        ["export-uploaded.csv"],
                        400,
                        "fetched_invalid",
                        "and an ordinary uploaded export cannot be named here either: only "
                        "a file THIS route wrote carries the prefix",
                    ),
                    (
                        [pipeline_routes.FETCHED_PREFIX + "19700101-000000.csv"],
                        404,
                        "no_such_file",
                        "a well-shaped name for a file the run does not hold is a 404 — "
                        "which is exactly what a client holding the name from a fetch that "
                        "later refused would send",
                    ),
                    (
                        [],
                        400,
                        "fetched_invalid",
                        "and an EMPTY list is refused rather than read as `use the old "
                        "file`, the rule `exports` already follows: a selection that failed "
                        "to send must not silently become the previous answer",
                    ),
                ):
                    status, raw, _ = request(
                        port,
                        "POST",
                        f"/pipeline/runs/{directory.name}/join",
                        payload={"fetched": wanted},
                    )
                    checks.equal(
                        (status, error_code(raw)), (expected_status, expected), label
                    )

                # ------------------------------------------- A NARROWER FILE IS REPORTED
                #
                # D65's delta guard refused this file: Dunsparce has a Near Mint row and a
                # Near Mint Reverse Holofoil row, and a file carrying only the first turns it
                # into a number the CATALOG decides (D3 rung 2). Retired 2026-09-02 (D65,
                # amended): D65 names the scope, so the positive check is the whole guard,
                # and the delta refused every run's FIRST fetch by construction. What the
                # receipt keeps is the comparison — the last joined export's rows beside this
                # one's — so the narrowing is visible without a refusal in the way.
                source = tcgcsv.read_export(FIXTURE_EXPORT)
                by_sku = source.by_sku()
                thinner = home / "thinner.csv"
                tcgcsv.write_csv(
                    thinner, source.header, [by_sku[DUNSPARCE_SKU], by_sku[ARTICUNO_SKU]]
                )
                stub["body"] = thinner.read_bytes()
                status, raw, _ = fetch({"refresh": True})
                body = json.loads(raw or b"{}")
                checks.equal(
                    (status, body.get("ok")),
                    (200, True),
                    "an export narrower than the one this run was last joined against is "
                    "KEPT — nothing refuses on the comparison any more, because the scope "
                    "was named and the file is checked for that instead",
                )
                checks.equal(
                    len(fetched_files()),
                    2,
                    "and different bytes get a name of their own beside the earlier file: "
                    "the digest lookup finds identical bytes and nothing else",
                )
                checks.equal(
                    (
                        body.get("rows"),
                        (body.get("previous") or {}).get("pokemon", {}).get("rows"),
                    ),
                    (2, 3),
                    "and the receipt states the delta the guard used to refuse on — two rows "
                    "now against the three the last join used — as information the operator "
                    "reads rather than a wall they press through",
                )

                # ------------------------------------ a first fetch has nothing earlier
                stub["body"] = whole.read_bytes()
                bare = runs.create("t7-unjoined")
                bare.write_identifications(identifications_for(cards))
                hint_run(bare.directory, len(cards))
                status, raw, _ = request(
                    port, "POST", f"/pipeline/runs/{bare.directory.name}/export", payload={}
                )
                body = json.loads(raw or b"{}")
                checks.equal(
                    (status, body.get("ok"), body.get("previous")),
                    (200, True, {}),
                    "a run with no previous export reports NONE rather than refusing — a run "
                    "directory is new per run, so `export_unverified` fired on every run's "
                    "first fetch and cost each one an acknowledgement and a second download "
                    "of the same file (D65, amended 2026-09-02)",
                )

                # ------------------------------ THE GATE IS WHAT PROTECTS THE CREDENTIAL
                #
                # `capture_server.py`'s CSRF paragraph used to justify itself with "there
                # are no credentials in this product", and D65 falsified that half: this
                # route spends the owner's TCGplayer session. The comment is corrected
                # there; this is the assertion it now leans on. A page in another tab must
                # not be able to make this server spend that session, and the refusal has
                # to land BEFORE the cookie is read — which is what `_dispatch` doing the
                # origin check ahead of the handler buys, and why the export route carries
                # no check of its own.
                stub["seen"] = []
                status, raw, _ = request(
                    port,
                    "POST",
                    f"/pipeline/runs/{directory.name}/export",
                    origin="https://evil.example",
                    payload={},
                )
                checks.equal(
                    (status, error_code(raw)),
                    (403, "origin_not_allowed"),
                    "a POST from an origin this server does not know is refused — the route "
                    "that spends the owner's marketplace session is behind the same gate as "
                    "the hard delete, and weakening SAFE_METHODS is a bigger decision than "
                    "it was before this route existed",
                )
                checks.equal(
                    stub["seen"],
                    [],
                    "and the cookie was never read for it: the gate is in `_dispatch`, "
                    "ahead of the handler, so a refused request reaches nothing that could "
                    "spend a credential",
                )

                # ------------------------------------- a run that cannot answer for itself
                #
                # A 500 IS THE ONE ANSWER THIS ROUTE MAY NOT GIVE. `exports_for` reaches
                # the run's identifications and the live store to learn which games it
                # holds, and every way that can fail — no identifications yet, an
                # unregistered game, an unreadable store — arrives here as a `RunError`
                # rather than as a value. Caught and named, because a traceback on the
                # screen is the one refusal an operator cannot act on.
                empty = runs.create("t7-no-idents")
                status, raw, _ = request(
                    port, "POST", f"/pipeline/runs/{empty.directory.name}/export", payload={}
                )
                checks.equal(
                    (status, error_code(raw)),
                    (409, "export_refused"),
                    "a run with no identifications refuses by name and carries the "
                    "command's own sentence — `run pkmnscan identify first` — rather than "
                    "letting a RunError out as a 500 with a traceback in it",
                )
                checks.equal(
                    [
                        entry.name
                        for entry in empty.directory.iterdir()
                        if entry.name.startswith(pipeline_routes.FETCHED_PREFIX)
                    ],
                    [],
                    "and it keeps nothing either, which is the rule every refusal here "
                    "follows: a refusal tears down what it built",
                )

                # ---------------------------------------------------------- the wrong file
                before = fetched_files()
                stub["body"] = (
                    Path(FIXTURE_EXPORT).parent / "riftbound_export_untouched.csv"
                ).read_bytes()
                status, raw, _ = fetch({"refresh": True})
                checks.equal(
                    (status, error_code(raw)),
                    (409, "export_wrong_game"),
                    "an export for a game this run holds no card of is refused by name — the "
                    "category this process asked for came back carrying another product "
                    "line, which is a registry or endpoint fault rather than a file to join "
                    "against",
                )
                checks.equal(
                    len(fetched_files()),
                    len(before),
                    "and that refusal keeps nothing either",
                )
                checks.equal(
                    fetched_files(),
                    before,
                    "and the files the earlier GOOD fetches wrote survive it untouched — a "
                    "refusal deletes only what it built, never a recorded export",
                )
                message = str(
                    (json.loads(raw or b"{}").get("error") or {}).get("message") or ""
                )
                checks.ok(
                    "pokemon" in message
                    and "Riftbound League of Legends Trading Card Game" in message
                    and "Pricing tab" not in message,
                    "and the sentence names the game that was asked for and the product line "
                    "that arrived, and sends nobody to the Pricing tab — since D65 the "
                    "category is named by this process, so the portal's saved filter is not "
                    "what is wrong",
                    message[:400],
                )
                # --------------------------- THE VOCABULARY THE CAPTURE SCREEN OFFERS
                #
                # `GET /tcg/sets` (D65). The capture screen is the RIG, and D19 measures its
                # cadence in milliseconds — so the property worth asserting is not that this
                # answers, but that it answers 200 WITH AN EMPTY LIST when it cannot, rather
                # than refusing. A hint field that would not open because an autocomplete
                # failed would be a worse product than one with no autocomplete.
                status, raw, _ = request(port, "GET", "/tcg/sets?game=pokemon")
                body = json.loads(raw or b"{}")
                checks.equal(
                    (status, body.get("game")),
                    (200, "pokemon"),
                    "the set vocabulary answers 200 for a game that has a category",
                )
                checks.equal(
                    [row["name"] for row in body.get("sets") or []],
                    ["SV09: Journey Together"],
                    "and it drops the portal's `All Set Names` row, which is a filter option "
                    "rather than a set and would be offered as one",
                )
                status, raw, _ = request(port, "GET", "/tcg/sets?game=misc")
                body = json.loads(raw or b"{}")
                checks.equal(
                    (status, body.get("sets"), body.get("reason")),
                    (200, [], "no_category"),
                    "a game with no TCGplayer category answers 200 with an empty list and a "
                    "reason — never a refusal, because this is drawn on the rig's own screen "
                    "and a capture must not stop for a missing convenience",
                )
                status, raw, _ = request(port, "GET", "/tcg/sets?game=not-a-game")
                body = json.loads(raw or b"{}")
                checks.equal(
                    (status, body.get("sets")),
                    (200, []),
                    "and a game the registry does not know answers the same 200 and an empty "
                    "list — `game_registry.get` raises `UnknownGame`, and it was a 500",
                )

                # ------------------------------ THE HINT VOCABULARY IS NOT TCGPLAYER'S
                #
                # `match_sets` DIRECTLY, because it is pure and the interesting inputs are the
                # ones the store does not happen to hold. Two vocabularies name one set: the
                # operator types the community code and TCGplayer publishes its own name, and
                # NO STRING RULE BRIDGES THEM — `MEG` is not a prefix, an initialism or a
                # colon-token of `ME01: Mega Evolution`. Measured against the live category
                # list before the alias table existed: `OGN`, `MEG`, `TEF` and `JTG` all
                # resolved to nothing and silently widened to every set in the category.
                catalog_sets = [
                    {"Text": "All Set Names", "Value": "0"},
                    {"Text": "SV09: Journey Together", "Value": "4242"},
                    {"Text": "Origins", "Value": "77"},
                    {"Text": "Origins: Proving Grounds", "Value": "78"},
                ]
                aliases = {"JTG": "SV09"}
                for hint, expected, label in (
                    (
                        "SV09",
                        (4242,),
                        "a TCGplayer-style code resolves by SHAPE and needs no alias — the "
                        "name's own token before the colon",
                    ),
                    (
                        "JTG",
                        (4242,),
                        "and the community code resolves only through the table, which is "
                        "why the table exists rather than a cleverer rule",
                    ),
                    (
                        "Origins",
                        (77,),
                        "an exact name beats the prefix it shares with its own sub-set — "
                        "`Origins` against `Origins: Proving Grounds`, which is why "
                        "substring is not one of the rules",
                    ),
                ):
                    got, _ = tcg_export.match_sets([hint], catalog_sets, aliases)
                    checks.equal(got, expected, label)

                widened_ids, widened_missed = tcg_export.match_sets(
                    ["ZZZ"], catalog_sets, aliases
                )
                checks.equal(
                    (widened_ids, widened_missed),
                    ((), ("ZZZ",)),
                    "a hint nothing matches resolves to NO set and is reported unresolved, "
                    "so the fetch widens to the whole category — slower, larger and correct, "
                    "where guessing a set the box is not in would not be",
                )

                # ------------------------------ THE SCOPE THE RUN IMPLIES IS THE SCOPE SENT
                #
                # D65's whole claim in one assertion. The export is no longer whatever the
                # portal's saved filter last was: this process NAMES a category and a set,
                # and what makes the file complete within scope by construction is that the
                # request said so. Read off the POST body the stub recorded, because a
                # response that merely looks right proves nothing about what was asked for.
                stub["mode"] = "csv"
                stub["body"] = whole.read_bytes()
                stub["posted"] = []
                fetch({"refresh": True})
                sent = json.loads(
                    urllib.parse.parse_qs(stub["posted"][-1])["model"][0]
                ) if stub["posted"] else {}
                checks.equal(
                    sent.get("CategoryId"),
                    "3",
                    "the run's game decides the category, and it travels as the STRING the "
                    "portal wants — an integer here answers `System Error`, a 200 carrying "
                    "an HTML page that reads exactly like a rejected cookie",
                )
                checks.equal(
                    sent.get("SetNameIds"),
                    ["4242"],
                    "and the run's own cards decide the SET — this box is unanimous, so the "
                    "request names the one set rather than the category. This asserted the "
                    "widening (`['0']`, the portal's all-sets row) while the baseline run "
                    "here carried no hint; the baseline is unanimous now, because Pokemon "
                    "has to be, and both the widening and the `0` convention are asserted "
                    "below where the hint rules are what is under test",
                )
                checks.equal(
                    (
                        sent.get("MyInventory"),
                        sent.get("PrintingIds"),
                        sent.get("ExcludeListos"),
                    ),
                    (False, ["0"], True),
                    "and THREE fields are never negotiable, asserted on the wire rather than "
                    "in the literal: the CATALOG rather than the operator's current "
                    "listings; All Printings, because a number stocked in several finishes "
                    "must arrive with all of them or D3 rung 2 decides it from whichever "
                    "survived; and listings-with-photos EXCLUDED, which is the owner's "
                    "standing instruction and the one of the three that nothing downstream "
                    "could ever catch — D65 measured `Photo URL` empty in every export, "
                    "filtered and unfiltered, so a wrong value here is invisible in the file "
                    "it narrows (D76)",
                )

                # ------------------- A HINT IS EVIDENCE ABOUT ITS OWN CARD AND NO OTHER
                #
                # D76, AND THE DEFECT IT IS NAMED FOR. D65 gathered the hints that EXISTED
                # and never counted the cards carrying none, so a box sorted by rarity with
                # one set hint on one card scoped the whole export to that one set — and
                # every unhinted card queued `no_catalog_row` behind a fetch that reported
                # success and a positive check that PASSED, because the set asked for did
                # arrive. Measured on the owner's own Riftbound box, and reproduced on a
                # synthetic 200-card run before the fix: `SetNameIds` came back `["77"]`.
                #
                # ASSERTED OFF THE POST BODY, never off the response: a fetch that answers
                # with the right file proves nothing about what was asked for, and asking
                # for too little is precisely the failure that still returns a valid CSV.
                # `hint_cards` and `identifications` are hoisted to the top of this block —
                # the baseline fetch needed them, because an unhinted Pokemon run no longer
                # reaches a socket.

                def sent(payload=None):
                    """What went out on the wire for this scope. ALWAYS FORCES THE FETCH.

                    EVERY CHECK BELOW IS ABOUT THE REQUEST, so it must make one. A press whose
                    game already holds a covering export answers without opening a socket
                    (D166), and a wide file covers every narrower scope — so
                    without `refresh` these would read the LAST request's body, or no body at
                    all, and report it as the scope this run implies. Which is the same class
                    of error as an outcome assertion that cannot see a saving, pointed the
                    other way: here the saving would hide the assertion.
                    """
                    stub["mode"] = "csv"
                    stub["body"] = whole.read_bytes()
                    stub["posted"] = []
                    asking = dict(payload or {})
                    asking["refresh"] = True
                    fetch(asking)
                    return json.loads(
                        urllib.parse.parse_qs(stub["posted"][-1])["model"][0]
                    ) if stub["posted"] else {}

                hint_cards(2)
                checks.equal(
                    sent().get("SetNameIds"),
                    ["4242"],
                    "a box where EVERY card carries a hint and the hint resolves still "
                    "narrows to that set — D65's saving is intact, and D76 narrows the "
                    "condition rather than removing it",
                )
                # D76'S WIDENING IS STILL PROVED, AND IT IS PROVED WITH THE HINT REQUIREMENT
                # HELD OFF.
                #
                # `pokemon` carries `export_needs_hint` now, so the two runs below REFUSE on
                # this game rather than widening — which is the whole point of that field and
                # is asserted directly after this. But D76's defect is about the WIDENING
                # rule, which every game without the field still uses, and an assertion
                # deleted because one game stopped reaching it is coverage silently dropped.
                # So the flag is lifted for exactly these two, the way `MAX_BYTES` is lowered
                # further down rather than a 32 MB body being put through the harness: read
                # off the module at call time, restored in `finally`.
                # `pipeline_routes` holds this module as `game_registry` and looks the name
                # up on it per call, so patching the module attribute here is what the route
                # actually reads — the same indirection `MAX_BYTES` is lowered through.
                was_needs = games.export_needs_hint
                games.export_needs_hint = lambda key: False
                try:
                    hint_cards(1)
                    checks.equal(
                        sent().get("SetNameIds"),
                        ["0"],
                        "and one hinted card among unhinted ones widens to the whole "
                        "category. This is the defect: the hints describe part of the box, a "
                        "filter built from them cuts the export to that part, and every card "
                        "outside it queues no_catalog_row behind a fetch that reported "
                        "success",
                    )
                    hint_cards(0)
                    checks.equal(
                        sent().get("SetNameIds"),
                        ["0"],
                        "a box with no hint at all widens, as it always did",
                    )
                finally:
                    games.export_needs_hint = was_needs

                # ------------- AND A GAME THAT CANNOT AFFORD THE WIDENING REFUSES INSTEAD
                #
                # THE CLIFF, CLOSED AT THE CAUSE. Measured 2026-09-12: the whole Pokemon
                # category is 32,629,598 B — 97.24% of `MAX_BYTES`, 903 KB of headroom —
                # against 238,482 B for the one set the owner's 543 Pokemon cards name. D76
                # held that a widening is always safe; here it is 903 KB short of a refusal,
                # and D76's own unanimity rule means ONE unhinted card reaches it. So the two
                # runs above, which widen on any other game, are refused on this one.
                #
                # BOTH DIRECTIONS, AND THE SAME CARDS IN EACH. A refusal that never fires and
                # a refusal that always fires both leave an outcome assertion green, so the
                # unanimous run is asserted to pass THROUGH this immediately below — the
                # `["4242"]` narrowing at the top of this block is that same proof off the
                # wire. The only thing that differs between the two is which cards carry a
                # hint.
                for hinted, code, phrase, label in (
                    (
                        0,
                        "export_needs_set_hint",
                        "none of its 2 cards carries one",
                        "a Pokemon run where NO card names its set is refused before a "
                        "socket is opened, and the sentence counts the cards rather than "
                        "naming the rule",
                    ),
                    (
                        1,
                        "export_needs_set_hint",
                        "1 of its 2 do not",
                        "and so is the partial box, which is the case that matters: one "
                        "unhinted card is the whole difference between a 238 KB fetch and a "
                        "32.6 MB one, because unanimity is what D76 narrows on",
                    ),
                ):
                    hint_cards(hinted)
                    before_posts = len(stub["posted"])
                    status, raw, _ = fetch({"refresh": True})
                    message = str(
                        (json.loads(raw or b"{}").get("error") or {}).get("message") or ""
                    )
                    checks.equal(
                        (status, error_code(raw), phrase in message, len(stub["posted"])),
                        (409, code, True, before_posts),
                        label,
                    )
                    checks.equal(
                        ("32.6 MB" in message, "97%" in message, "Manage box" in message),
                        (True, True, True),
                        "and it carries the three things a refusal owes: what the widening "
                        "would have weighed, how close that is to the ceiling the download "
                        "is refused past, and the screen that sets the hint on the cards "
                        "that lack one — a refusal with no way forward strands the cards it "
                        "protects",
                    )

                # AND THE PREVIEW DRAWS IT RATHER THAN FAILING ON IT. One refusal, two
                # behaviours: `POST .../export` is a 409 that spends nothing, and
                # `GET .../scope` — which presses nothing by construction — reports the same
                # code as DATA with the counts still drawn beside it, because that route
                # already reads a `PipelineRefusal` that way (D76). This is where the
                # operator meets it, ahead of the money gate.
                status, raw, _ = request(
                    port, "GET", f"/pipeline/runs/{directory.name}/scope"
                )
                preview = json.loads(raw)
                checks.equal(
                    (
                        status,
                        preview["reason"],
                        preview["asked"],
                        "32.6 MB" in str(preview["message"]),
                        [g["unhinted"] for g in preview["games"] if g["game"] == "pokemon"],
                    ),
                    (200, "export_needs_set_hint", None, True, [1]),
                    "the press-nothing preview answers 200 and DRAWS the refusal — the code, "
                    "the sentence with the width in it, and the unhinted count still on the "
                    "game row — so the operator reads it on the screen that costs nothing "
                    "rather than discovering it by pressing the one that would",
                )

                # AND THE OPERATOR STILL OUTRANKS IT, WHICH IS WHY NOTHING IS EVER STRANDED.
                # D76's three voices are unchanged: `chosen_by` is the whole predicate, and it
                # is `cards` only where the CARDS under-specified the scope. Somebody asking
                # for the category is making a claim about the box, and this refusal has no
                # opinion about that — it exists to stop the machine widening on a guess, not
                # to stop a person.
                checks.equal(
                    sent({"scope": "category"}).get("SetNameIds"),
                    ["0"],
                    "an operator asking for `category` on the same unhinted run fetches it — "
                    "the refusal reads the cards' silence, never the operator's word, so the "
                    "escape hatch D76 already published is the reason a refused run is never "
                    "a stranded one",
                )
                checks.equal(
                    sent({"set_ids": [4242]}).get("SetNameIds"),
                    ["4242"],
                    "and naming the sets outright narrows it on a run with no hint at all, "
                    "which is the second half of the same override",
                )

                # ------------------- THE SECOND DOCUMENT: THE OPERATOR'S OWN LIVE LISTINGS
                #
                # D104, AND EVERY VALUE HERE WAS MEASURED RATHER THAN DESIGNED. The first build
                # guessed a filtered POST with `MyInventory: True` and `CategoryId: "0"`, on the
                # reasoning that `"0"` is the portal's all-row everywhere else. It is not: the
                # category select is the ONE field on that form with no `0=All` option, and the
                # portal answered the guess with a valid CSV header and ZERO rows. Measured
                # against the owner's account: `CategoryId: "0"` → 0 rows, `"3"` → 333.
                #
                # The real request came off the portal's own `Export From Live` button, whose
                # tooltip reads "Export your entire Live inventory":
                #     GET /Admin/Pricing/DownloadMyExportCSV?type=Pricing&exportLowestListingNotMe=true
                stub["mode"] = "csv"
                stub["got"] = []
                stub["live_body"] = whole.read_bytes()
                answer = pipeline_routes.do_live_export()
                asked = urllib.parse.parse_qs(
                    urllib.parse.urlparse(stub["got"][-1]).query
                ) if stub["got"] else {}

                checks.equal(
                    (asked.get("type"), asked.get("exportLowestListingNotMe")),
                    (["Pricing"], ["true"]),
                    "THE LIVE DOWNLOAD'S TWO QUERY PARAMETERS, ON THE WIRE. `type=Pricing` is "
                    "the LIVE tab rather than Staged — a different document, and the one D87 "
                    "reconciles the store against, so this value decides what `live` means for "
                    "every SKU",
                )
                checks.equal(
                    sorted(k for k in asked if k not in ("type", "exportLowestListingNotMe")),
                    [],
                    "AND NOTHING ELSE. A live inventory has no scope: no category, no sets, no "
                    "conditions, no `MyInventory`. Every narrowing this request could carry is "
                    "a way for it to come back silently short",
                )
                checks.ok(
                    answer["fetched"].startswith(pipeline_routes.LIVE_PREFIX)
                    and answer["fetched"].endswith(".csv"),
                    "the file is KEPT and NAMED, so both consumers can act on one reading "
                    "rather than two downloads taken minutes apart",
                )
                checks.ok(
                    (files.inventory_dir() / pipeline_routes.LIVE_DIR / answer["fetched"]).is_file(),
                    "and it is on disk under a name `_open_live_export` will accept",
                )
                # identity-follows-sku.md §3.2, fill point 2: the live export folds into the
                # `skus` table in the SAME transaction as the readings replace above it, no
                # second write.
                live_sku_table = Store().read().skus.entries
                checks.ok(
                    all(sku in live_sku_table for sku in SEAM_SKUS),
                    "the live export's own SKUs are in the table too, through the identical "
                    "fold the Filtered Export used",
                    f"table keys: {sorted(live_sku_table.keys())}",
                )

                # THE SILENT FAILURE, MADE LOUD. This endpoint answers a request it cannot
                # satisfy with a well-formed 216-byte header and no rows — measured, on the
                # owner's account. Unrefused, that is a lens drawing an empty live inventory
                # and a reconcile writing `live: 0` across the store.
                stub["got"] = []
                stub["live_body"] = whole.read_bytes().splitlines()[0] + b"\r\n"
                try:
                    pipeline_routes.do_live_export()
                    checks.ok(False, "a header-only export refuses", "it reported success")
                except pipeline_routes.PipelineRefusal as refusal:
                    checks.equal(
                        refusal.code,
                        "tcg_export_empty",
                        "AN EXPORT WITH NO ROWS IS REFUSED AND NOT REPORTED. A store with "
                        "listings does not answer nothing, and unlike the filtered endpoint "
                        "this one does not announce a bad request with `System Error` — it "
                        "answers emptily, which is why the refusal has to be here",
                    )
                stub["live_body"] = whole.read_bytes()

                # -------------------------------------- THE GAME'S OWN RULE, AND THE OPERATOR
                checks.equal(
                    (games.export_scope("riftbound"), games.export_scope("pokemon")),
                    ("category", "sets"),
                    "the registry carries the per-game rule: riftbound's whole English "
                    "catalogue is one 10078-row file and has nothing a set filter would buy, "
                    "and Pokemon's whole category is not measured so it still narrows",
                )
                checks.equal(
                    games.export_scope("nobody_registered_this"),
                    games.DEFAULT_EXPORT_SCOPE,
                    "and a game outside the registry answers the DEFAULT rather than raising "
                    "— unlike `games.get`, because the question is how wide to ask rather "
                    "than what a card is, and the safe answer to the first is the wider one",
                )

                hint_cards(2)
                checks.equal(
                    sent({"scope": "category"}).get("SetNameIds"),
                    ["0"],
                    "the operator widens a box the cards would have narrowed — `scope` is "
                    "the axis, and asking for more than the inference is always safe",
                )
                hint_cards(0)
                checks.equal(
                    sent({"set_ids": [4242]}).get("SetNameIds"),
                    ["4242"],
                    "and ticking sets by hand narrows a box that carries no hint at all. A "
                    "hint is a guess about one card; a person ticking a set is making the "
                    "claim about the BOX that the inference was trying to reconstruct",
                )
                status, raw, _ = fetch({"set_ids": [999999]})
                checks.equal(
                    (status, error_code(raw)),
                    (400, "set_ids_unknown"),
                    "a set id the portal's own category does not publish is refused HERE, "
                    "because the portal answers a body it cannot read with a 200 carrying "
                    "its System Error page — which reads exactly like a rejected cookie",
                )
                status, raw, _ = fetch({"scope": "everything"})
                checks.equal(
                    (status, error_code(raw)),
                    (400, "scope_invalid"),
                    "and an axis that is not one of the two is refused by name rather than "
                    "falling through to the game's rule, which would silently answer a "
                    "different question from the one asked",
                )

                # ------------------------------- THE LEVER'S POSITION, BEFORE IT IS PULLED
                #
                # `GET .../scope` (D76). The receipt named the scope AFTER the file was on
                # disk, so the one moment an operator could correct a wrong scope was the one
                # moment it was not on screen. FREE and it presses nothing — asserted by the
                # POST count, because "it did not fetch" is the property, not a side effect.
                hint_cards(1)
                stub["posted"] = []
                status, raw, _ = request(
                    port, "GET", f"/pipeline/runs/{directory.name}/scope"
                )
                body = json.loads(raw or b"{}")
                checks.equal(
                    (status, stub["posted"]),
                    (200, []),
                    "the scope preview answers 200 and POSTs nothing — it reads the run and "
                    "the portal's set list, and never asks for a file",
                )
                checks.equal(
                    [(g["game"], g["cards"], g["hinted"], g["policy"]) for g in body["games"]],
                    [("pokemon", 2, 1, "sets")],
                    "and it publishes the evidence the rule reads — how many cards, how many "
                    "carry a hint, and this game's own rule — which is the fact that was "
                    "invisible while one hinted card could scope a whole box's export",
                )
                # THE VOICE AND THE REASON, READ WITH THE HINT REQUIREMENT HELD OFF. On
                # `pokemon` this exact run is now refused `export_needs_set_hint` and `asked`
                # comes back null — asserted where that refusal is built. What is under test
                # HERE is that a widening still NAMES its voice, which is the half of D76
                # every game without the field still relies on, so the flag is lifted rather
                # than the assertion weakened to whichever shape the code happens to produce.
                was_needs = games.export_needs_hint
                games.export_needs_hint = lambda key: False
                try:
                    status, raw, _ = request(
                        port, "GET", f"/pipeline/runs/{directory.name}/scope"
                    )
                    asked_now = json.loads(raw or b"{}")["asked"]
                finally:
                    games.export_needs_hint = was_needs
                checks.equal(
                    (asked_now["scope"], asked_now["reason"]),
                    ("category", "partial_hints"),
                    "and it says WHICH of the three voices chose the scope and why, in the "
                    "same shape the fetch's own receipt carries — a scope is only "
                    "correctable by somebody who can see what decided it",
                )
                # BACK TO THE HINTED BASELINE, because everything below this fetches for
                # real. This line used to clear the hints; on a game that needs one that
                # leaves every fetch in the next two sections refused.
                hint_cards(len(cards))

                # ================= THE EXPORT IS A PROPERTY OF THE GAME (D166)
                #
                # EVERY ASSERTION IN THIS SECTION THAT MATTERS COUNTS REQUESTS, AND THAT IS
                # DELIBERATE. PR A's arm 9 is the lesson: deleting its work-saving gate left
                # every other assertion green, because the old path and the new one agree on
                # every OUTCOME and differ only in the work done to reach them. A reuse and a
                # fetch here produce the same file, the same rows, the same SKUs, the same
                # receipt figures and the same join — so an outcome assertion can say nothing
                # at all about whether the socket was opened. `stub["posted"]` is the counter.
                # BYTES OF ITS OWN, so every count below is a DELTA this block caused rather
                # than a total the sections above happen to have reached. An absolute count
                # here reads as a dedupe failure the moment another case adds a file.
                stub["mode"] = "csv"
                mine = home / "one-sku.csv"
                tcgcsv.write_csv(mine, source.header, [by_sku[DUNSPARCE_SKU]])
                stub["body"] = mine.read_bytes()

                def posts():
                    return len(stub["posted"])

                # --------------------------------------- the file leaves the run directory
                before_posts, before_kept = posts(), len(kept())
                status, raw, _ = fetch({"refresh": True})
                first = json.loads(raw)
                checks.equal(
                    (status, first["ok"], posts() - before_posts),
                    (200, True, 1),
                    "a fetch of bytes nothing on disk carries opens exactly one socket",
                )
                checks.equal(
                    (len(kept()) - before_kept, first["file"] in kept()),
                    (1, True),
                    "and the file lands in `inventory/.exports/<game>/` — the export is a "
                    "property of the GAME, and a per-run copy is what made the dedupe below "
                    "blind to its own siblings",
                )
                checks.equal(
                    run_local(),
                    [],
                    "and NOT in the run directory, which is the whole move: five "
                    "byte-identical 1,733,052 B copies landed in five run directories in "
                    "eighteen seconds on the owner's store because each run deduped against "
                    "itself alone",
                )
                checks.equal(
                    Path(first["store"]).name,
                    "pokemon",
                    "and the receipt says where it went, because a client that built a "
                    "download path out of the run's name would otherwise break in silence",
                )

                # ------------------------------ A SECOND RUN OF THE SAME GAME OPENS NOTHING
                #
                # THE MEASUREMENT THIS IS BUILT FOR. Re-joining the owner's store meant
                # pressing Fetch once per run: seven presses over nine minutes, five of them
                # eighteen seconds apart, every one asking TCGplayer for bytes the machine
                # already held. Store-wide the real rules produce TWO requests for that whole
                # store — one per game — and this is the arm that makes that true.
                second, _ = seam_run(checks, cards)
                hint_run(second.directory, len(cards))
                before_posts = posts()
                status, raw, _ = request(
                    port,
                    "POST",
                    f"/pipeline/runs/{second.directory.name}/export",
                    payload={},
                )
                reuse = json.loads(raw)
                checks.equal(
                    (status, reuse["ok"], reuse["reused"], posts() - before_posts),
                    (200, True, True, 0),
                    "A SECOND RUN OVER THE SAME GAME ISSUES ZERO NETWORK REQUESTS and "
                    "answers out of the file already on disk. This is the assertion no "
                    "outcome can make: every other figure on this receipt is identical to "
                    "the fetched one, so only the request count can see the saving",
                )
                checks.equal(
                    len(kept()) - before_kept,
                    1,
                    "and nothing new is written either — one game, one file, however many "
                    "runs join against it",
                )
                checks.equal(
                    (reuse["rows"], reuse["skus"]),
                    (first["rows"], first["skus"]),
                    "and the receipt it answers with is the fetched one's, figure for "
                    "figure — which is exactly why the count above had to be asserted",
                )

                # ---------------------- A WIDER FILE COVERS A NARROWER NEED, NEVER THE OTHER
                #
                # ASSERTED ON THE RULE ITSELF, because the reuse path cannot be steered to it
                # from here: a category-scoped export is already on disk and legitimately
                # covers every narrower scope, so a route-level case would reuse THAT file and
                # prove nothing about the asymmetry. The direction is what is load-bearing —
                # a file fetched for {A} serving a run needing {A, B} leaves every card of B
                # queueing `no_catalog_row` behind a press that reported success, which is
                # D76's defect arriving through a different door.
                checks.equal(
                    (
                        pipeline_routes._covers(
                            {"category_id": 3, "set_ids": []},
                            tcg_export.Scope(category_id=3, set_ids=(4242,)),
                        ),
                        pipeline_routes._covers(
                            {"category_id": 3, "set_ids": [4242]},
                            tcg_export.Scope(category_id=3, set_ids=()),
                        ),
                        pipeline_routes._covers(
                            {"category_id": 3, "set_ids": [4242]},
                            tcg_export.Scope(category_id=3, set_ids=(4242, 99)),
                        ),
                        pipeline_routes._covers(
                            {"category_id": 89, "set_ids": []},
                            tcg_export.Scope(category_id=3, set_ids=()),
                        ),
                    ),
                    (True, False, False, False),
                    "the whole category covers one set; one set does NOT cover the category "
                    "or a superset of itself; and another game's file covers nothing here",
                )

                # ------------------- A REUSE OBSERVED NOTHING, SO IT MAY NOT DATE THE READING
                #
                # `describe_source` READS AN EXPORT'S OBSERVATION TIME OFF ITS MTIME, and
                # `Listing.live_reading` weighs that against the store's own stamps. Touching
                # it on a reuse would date a reading nobody took and let a stale export
                # outrank a newer sale — silently, and only in the arithmetic.
                held = exports_root / "pokemon" / first["file"]
                was_mtime = held.stat().st_mtime
                request(
                    port,
                    "POST",
                    f"/pipeline/runs/{second.directory.name}/export",
                    payload={},
                )
                checks.equal(
                    held.stat().st_mtime,
                    was_mtime,
                    "a reuse leaves the mtime alone, because it took no reading",
                )

                # ------------------------- AND A READING OLDER THAN THE WINDOW IS RE-TAKEN
                #
                # EVERY FILE THE GAME HOLDS IS AGED, not just the one this block fetched.
                # `_reusable` walks the whole directory newest first and answers with the
                # first covering file — which is right, and means ageing one of several
                # proves nothing: the press would reuse a sibling and the check would read
                # as a reuse that ignored the window.
                stale = was_mtime - pipeline_routes.EXPORT_REUSE_S - 60
                for entry in (exports_root / "pokemon").glob("*.csv"):
                    os.utime(entry, (stale, stale))
                was_mtime = held.stat().st_mtime
                before_posts = posts()
                status, raw, _ = request(
                    port,
                    "POST",
                    f"/pipeline/runs/{second.directory.name}/export",
                    payload={},
                )
                checks.equal(
                    (json.loads(raw)["reused"], posts() - before_posts),
                    (False, 1),
                    "an export older than EXPORT_REUSE_S is re-fetched rather than reused — "
                    "the window is sized to a SITTING, and a reuse long enough that the "
                    "operator thinks they refreshed and did not is worse than the request",
                )
                checks.equal(
                    held.stat().st_mtime > was_mtime,
                    True,
                    "and THAT one touches the mtime, because identical bytes arriving from "
                    "the portal really are a fresh observation of the same reading",
                )

                # ------------------------------------------ `refresh` FORCES THE SOCKET OPEN
                before_posts = posts()
                status, raw, _ = request(
                    port,
                    "POST",
                    f"/pipeline/runs/{second.directory.name}/export",
                    payload={"refresh": True},
                )
                forced = json.loads(raw)
                checks.equal(
                    (status, forced["reused"], posts() - before_posts),
                    (200, False, 1),
                    "`refresh: true` opens the socket whatever the age — an operator who "
                    "means to take a new reading must be able to, or the reuse window is a "
                    "trap rather than a saving",
                )
                checks.equal(
                    len(kept()) - before_kept,
                    1,
                    "AND THE IDENTICAL BYTES DEDUPE STORE-WIDE: a real fetch that produces "
                    "bytes already on disk lands on the file that holds them, ACROSS RUNS. "
                    "5 of the 6 redundant copies on the owner's store are cross-run and so "
                    "are outside anything a per-run glob could ever have reached",
                )

                # A FILE COUNT CANNOT PROVE THE DEDUPE, AND MEASURING THAT IS WHY THIS EXISTS.
                #
                # THE NAME IS `stamp-digest`, SO IDENTICAL BYTES INSIDE ONE SECOND COMPOSE THE
                # IDENTICAL PATH. `write_bytes` then OVERWRITES rather than adds, and every
                # count above reads the same whether the digest was looked up or not — this
                # whole block runs inside one second on this machine (measured: three files
                # all stamped at the same second), so deleting the lookup outright left all 88
                # checks green. That is T7's own same-second collision showing up as a hole in
                # the test rather than in the product.
                #
                # SO THE ASSERTION IS THE RECEIPT'S OWN FILE NAME, against a held file whose
                # stamp CANNOT collide: rename it into the past, re-fetch the same bytes, and
                # the press must answer with the renamed file. That is the digest lookup and
                # nothing else, and no clock can make it pass by accident.
                held_now = exports_root / "pokemon" / forced["file"]
                earlier = held_now.with_name(
                    f"{pipeline_routes.FETCHED_PREFIX}19700101-000000-"
                    f"{forced['file'].rsplit('-', 1)[1]}"
                )
                held_now.rename(earlier)
                pipeline_routes._note_path(held_now).rename(
                    pipeline_routes._note_path(earlier)
                )
                status, raw, _ = fetch({"refresh": True})
                landed = json.loads(raw)
                checks.equal(
                    (status, landed["file"], len(kept()) - before_kept),
                    (200, earlier.name, 1),
                    "a re-fetch of bytes already on disk answers with the file that HOLDS "
                    "them, whatever its name — found by digest and compared in full, because "
                    "32 bits of digest is a name and not a proof",
                )
                earlier.rename(held_now)
                pipeline_routes._note_path(earlier).rename(
                    pipeline_routes._note_path(held_now)
                )

                # ------------------------------------- THE PREVIEW STILL PRESSES NOTHING
                before_posts = posts()
                status, raw, _ = request(
                    port, "GET", f"/pipeline/runs/{second.directory.name}/scope"
                )
                scope_body = json.loads(raw)
                checks.equal(
                    (status, posts() - before_posts),
                    (200, 0),
                    "`GET .../scope` opens no export socket — it is the lever's position "
                    "drawn before the press, and a preview that fetched would be the press",
                )
                checks.equal(
                    bool(scope_body["reusable"]),
                    True,
                    "and it says the next press would answer without a request, so the "
                    "operator is not re-fetching bytes this machine holds",
                )
                width = scope_body["width"]
                checks.equal(
                    (
                        isinstance(width, dict)
                        and width["bytes"] > 0
                        and width["max_bytes"] == tcg_export.MAX_BYTES
                        and width["headroom"] == width["max_bytes"] - width["bytes"]
                    ),
                    True,
                    "AND IT DRAWS WHAT THE PRESS WOULD WEIGH AGAINST THE CAP (D65/D76). "
                    "Measured 2026-09-12: the whole Pokemon category is 32,629,598 B — "
                    "97.24% of MAX_BYTES, 903 KB of headroom — against 238,482 B for the "
                    "one set the owner's 543 Pokemon cards name. A widening is 137x and "
                    "lands two per cent short of a refusal, so it may not be silent",
                )

                # --------------------- AND A WIDENED FETCH THAT IS TOO LARGE SAYS WHY (D76)
                #
                # THE CAP IS LOWERED RATHER THAN THE BODY RAISED. `MAX_BYTES` is read off the
                # module at call time by both the reader and the check, so moving it exercises
                # the same path a 32 MB body would — without putting 32 MB through a harness
                # that runs at every turn end.
                # AND THE HINT REQUIREMENT IS HELD OFF FOR IT, for the same reason as the two
                # widening checks above: the sentence under test is the `partial_hints`
                # wording, which every game WITHOUT `export_needs_hint` still reaches, and on
                # `pokemon` those cards no longer get as far as a download. The wide paths
                # that survive on this game are the operator's two, and they are asserted
                # where the refusal is. Both patches are read off the module at call time.
                hint_cards(1)
                was_max = tcg_export.MAX_BYTES
                was_needs = games.export_needs_hint
                tcg_export.MAX_BYTES = 64
                games.export_needs_hint = lambda key: False
                try:
                    status, raw, _ = fetch({"refresh": True})
                finally:
                    tcg_export.MAX_BYTES = was_max
                    games.export_needs_hint = was_needs
                message = str(
                    (json.loads(raw or b"{}").get("error") or {}).get("message") or ""
                )
                checks.equal(
                    (status, error_code(raw), "THE SCOPE IS WHY" in message),
                    (502, "tcg_export_too_large", True),
                    "the transport's own sentence blames the download and hands the "
                    "operator nothing to act on — it still says the widest export this "
                    "project has read is under 2 MB, and the widest it can ASK for is "
                    "31.12 MB. The actionable half is that the scope went wide, and why",
                )
                checks.equal(
                    "carry no set hint" in message,
                    True,
                    "and it names the cards that widened it — D76's own defect, said at the "
                    "moment it costs something rather than left to be inferred",
                )
                # AND BACK TO THE HINTED BASELINE AGAIN, for the join seam below.
                hint_cards(len(cards))
                stub["mode"] = "csv"

                # ------------------- THE MANIFEST KEEPS THE PATH AND THE DIGEST, AND USES IT
                #
                # THE RECORD IS THE ONLY LINK BACK once the file is not inside the run, and a
                # shared directory is exactly where a path CAN change under a run that a
                # run-local copy never could. So the digest is not decoration.
                #
                # AND THE JOIN ITSELF OPENS NO SOCKET, asserted rather than assumed. This is
                # the second run over this game and it resolves against the file the FIRST
                # one's press left in `inventory/.exports/pokemon/` — so the whole
                # fetch-and-join pass for run two costs zero requests. Counted, because the
                # join's own output says nothing about whether TCGplayer was asked.
                before_posts = posts()
                status, raw, _ = request(
                    port,
                    "POST",
                    f"/pipeline/runs/{second.directory.name}/join",
                    payload={"fetched": [first["file"]]},
                )
                joined = runs.open_run(second.directory)
                recorded = (joined.manifest.get("exports") or {}).get("pokemon") or {}
                export_path = Path(str(recorded.get("path") or ""))
                checks.equal(
                    (
                        json.loads(raw)["ok"],
                        export_path.parent.name,
                        len(str(recorded.get("sha256") or "")),
                        posts() - before_posts,
                    ),
                    (True, "pokemon", 64, 0),
                    "the join records the file it resolved against — path AND digest, under "
                    "the GAME's directory rather than the run's — and ISSUES ZERO NETWORK "
                    "REQUESTS doing it, which is the half no join output can report",
                )
                checks.equal(
                    runs.sha256_of(export_path),
                    recorded["sha256"],
                    "and the digest recorded is the digest of the file that was read",
                )

                # THE PATH MOVES AND THE DIGEST FINDS IT. A recorded export renamed under the
                # shared directory is RECOVERED rather than refused — by full sha256, never by
                # position, so this can never quietly join a run against a newer reading.
                moved = export_path.with_name("export-tcgplayer-19700101-000000-" +
                                              recorded["sha256"][:8] + ".csv")
                export_path.rename(moved)
                plan = resolve.exports_for(joined, None)
                checks.equal(
                    plan.by_game["pokemon"],
                    moved,
                    "a recorded export whose PATH has moved is found by the DIGEST the "
                    "manifest recorded beside it — which is what makes that record "
                    "load-bearing rather than a note",
                )
                moved.rename(export_path)

                # A DIGEST THAT MATCHES NOTHING IS A REFUSAL, NEVER A SUBSTITUTE.
                export_path.rename(export_path.with_suffix(".hidden"))
                try:
                    resolve.exports_for(joined, None)
                    checks.equal(False, True, "unreachable")
                except runs.RunError as caught:
                    checks.equal(
                        "recorded digest" in str(caught),
                        True,
                        "and a run whose file is gone entirely refuses exactly as before, "
                        "naming the digest it looked for — a recovery that fell back to "
                        "'some export of this game' would join against a newer reading in "
                        "silence, which is the hazard the shared directory creates",
                    )
                export_path.with_suffix(".hidden").rename(export_path)

                # AND THE MATCH IS THE FULL DIGEST, NOT THE 32 BITS IN THE NAME. The name
                # carries `sha256[:8]` and that is a NAME rather than a proof — the same
                # sentence `_keep_export` follows one module over. A recovery that trusted the
                # filename would hand a run somebody else's file with a colliding prefix, and
                # the join would be silently against the wrong reading.
                impostor = export_path.with_name(
                    "export-tcgplayer-19700102-000000-" + recorded["sha256"][:8] + ".csv"
                )
                impostor.write_bytes(thinner.read_bytes())
                export_path.rename(export_path.with_suffix(".hidden"))
                try:
                    impostor_plan = resolve.exports_for(joined, None)
                    checks.equal(
                        impostor_plan.by_game.get("pokemon"),
                        None,
                        "a file whose NAME carries the recorded digest but whose bytes do "
                        "not is refused, not adopted",
                    )
                except runs.RunError:
                    checks.ok(
                        True,
                        "a file whose NAME carries the recorded digest but whose bytes do "
                        "not is refused — the recovery verifies the full sha256, because 32 "
                        "bits of digest is a name and not a proof",
                    )
                export_path.with_suffix(".hidden").rename(export_path)
                impostor.unlink()

                # ------------------------- A LEGACY RUN GOES ON JOINING ITS OWN LOCAL COPY
                #
                # THE OWNER'S STORE HOLDS 19 OF THESE. A run directory is an immutable input,
                # so a run joined against a file inside it keeps that file and that answer.
                legacy_name = pipeline_routes.FETCHED_PREFIX + "20260101-000000-abcdef12.csv"
                (second.directory / legacy_name).write_bytes(whole.read_bytes())
                before_posts = posts()
                status, raw, _ = request(
                    port,
                    "POST",
                    f"/pipeline/runs/{second.directory.name}/join",
                    payload={"fetched": [legacy_name]},
                )
                checks.equal(
                    (status, json.loads(raw)["ok"], posts() - before_posts),
                    (200, True, 0),
                    "a fetched export still inside a run directory is found there first and "
                    "joined against — the legacy location is not a fallback, it is where "
                    "those 19 files are and where they stay",
                )

                # ------------------------------------- THE COOKIE ROTATES, AND `get` CANNOT
                #
                # THE REFUSAL'S OWN REMEDY, EXERCISED. `tcg_session_expired` tells the
                # operator to sign in again and replace the value in `.env` — and
                # `envfile.get` caches per process AND cannot replace a name it already
                # lifted out of the file, so under D138's supervisor (days of uptime, and it
                # does not watch `.env`) that remedy would not have worked. The refusal
                # would have repeated forever over a cookie already fixed.
                #
                # DRIVEN THROUGH THE REAL FETCH rather than through the reader, because what
                # has to be true is that the SOCKET sees the new value. The stub records
                # every Cookie header it is sent, so this reads what actually went out.
                dotenv = home / "rotating.env"
                was_file, was_env = envfile.ENV_FILE, os.environ.pop(
                    "TCGPLAYER_STORE_COOKIE", None
                )
                envfile.ENV_FILE = dotenv
                try:
                    stub["mode"] = "csv"
                    stub["body"] = whole.read_bytes()

                    dotenv.write_text("TCGPLAYER_STORE_COOKIE=TCGAuthTicket_Production=one\n")
                    stub["seen"] = []
                    # FORCED, for `sent()`'s reason: this asserts what reached the SOCKET,
                    # and a press that reuses a covering export never reaches one.
                    fetch({"refresh": True})
                    checks.equal(
                        stub["seen"][-1] if stub["seen"] else None,
                        "TCGAuthTicket_Production=one",
                        "a cookie placed in `.env` while the server is already running "
                        "reaches the socket — `envfile.get` returns early once loaded, so "
                        "adding one to a long-running server was invisible to it. The "
                        "value carries its own `=` — a Cookie header is `name=value` — "
                        "so this pins that `.env` splits a line on its FIRST separator",
                    )

                    dotenv.write_text("TCGPLAYER_STORE_COOKIE=TCGAuthTicket_Production=two\n")
                    stub["seen"] = []
                    # FORCED, for `sent()`'s reason: this asserts what reached the SOCKET,
                    # and a press that reuses a covering export never reaches one.
                    fetch({"refresh": True})
                    checks.equal(
                        stub["seen"][-1] if stub["seen"] else None,
                        "TCGAuthTicket_Production=two",
                        "and a REPLACED one reaches it too, which is the case that matters: "
                        "the session expires, and `load` will not overwrite a name it set "
                        "itself even with force — so the fix printed by tcg_session_expired "
                        "has to actually work",
                    )

                    os.environ["TCGPLAYER_STORE_COOKIE"] = "TCGAuthTicket_Production=from-env"
                    stub["seen"] = []
                    # FORCED, for `sent()`'s reason: this asserts what reached the SOCKET,
                    # and a press that reuses a covering export never reaches one.
                    fetch({"refresh": True})
                    checks.equal(
                        stub["seen"][-1] if stub["seen"] else None,
                        "TCGAuthTicket_Production=from-env",
                        "and a real environment variable still outranks the file, which is "
                        "the precedence `envfile` has always promised so CI can set one "
                        "without editing anything",
                    )
                finally:
                    envfile.ENV_FILE = was_file
                    os.environ.pop("TCGPLAYER_STORE_COOKIE", None)
                    if was_env is not None:
                        os.environ["TCGPLAYER_STORE_COOKIE"] = was_env

            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(5)
    finally:
        portal.shutdown()
        portal.server_close()
        portal_thread.join(5)
        envfile.ENV_FILE, restore_from_file, envfile._loaded = env_before
        envfile._from_file.clear()
        envfile._from_file.update(restore_from_file)
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

def check_key_rotation(checks: Checks) -> None:
    """`identify/batch.py:_client` and `envfile` — the API key survives a rotation (2026-09-11).

    THE DEFECT, ON THE OWNER'S OWN RIG: the key expired, they pasted a new one into `.env`, and
    `./pkmnscan identify` and the `#/runs` press both kept failing with the dead one. `make
    down` / `make up` picked it up, and nothing short of that did — which is the restart
    discipline D138 exists to make unnecessary.

    TWO CAUSES, ONE PER HALF OF THIS BLOCK, AND THE FIRST HALF ALONE DOES NOT FIX IT.

      - `_client` constructed `anthropic.Anthropic()` with NO KEY and let the SDK read
        `os.environ` itself, so the value the process was STARTED with was the only value it
        could ever send. `envfile.get_live` is the fix D65 already built, for the cookie.
      - and `get_live` could not see the rotation either, one process down. `_from_file` — the
        half of the precedence rule that says "this came out of a file" — is a process global,
        and every child here is spawned with `dict(os.environ)`. D138's supervisor reads ONE
        `.env` line (`PKMNSCAN_LAN_NAME`) and `load` lifts them all, so the capture server
        inherits the key as a REAL environment variable and `get_live`, correctly by its own
        rule, declines to read the file again. `envfile.FROM_FILE_ENV` carries the set across
        the spawn.

    DRIVEN THROUGH `_client` AND THROUGH A REAL CHILD PROCESS, not through the reader. What has
    to be true is that the SDK gets the new key, and that it gets it in the process `identify`
    actually runs in — a reader that answers correctly in the parent is exactly what this repo
    already had.

    THE CHILD IS HERMETIC: `envfile.py` is COPIED into a throwaway tree, so `ENV_FILE` resolves
    beside the copy and the real `.env` is not in the picture at all. `verdict-selftest` runs
    its reporter the same way and for the same reason.

    NO KEY IS EVER PUT IN AN ASSERTION MESSAGE. Every arm asserts a TAG for the value it
    resolved, so a red arm on a machine that has a real `.env` cannot print a live credential
    into a harness log — `.claude/settings.json` denies reading that file for the same reason.
    """
    one = "sk-ant-fixture-one"
    two = "sk-ant-fixture-two"
    exported = "sk-ant-fixture-exported"
    argument = "sk-ant-fixture-argument"
    tags = {one: "one", two: "two", exported: "exported", argument: "argument"}

    def tag(value: str) -> str:
        return tags.get(value, "other") if value else "nothing"

    env_before = (envfile.ENV_FILE, set(envfile._from_file), envfile._loaded)
    previous = {
        name: os.environ.get(name)
        for name in (batch.API_KEY_ENV, envfile.FROM_FILE_ENV)
    }
    with tempfile.TemporaryDirectory() as raw:
        home = Path(raw)
        dotenv = home / "rotating.env"
        try:
            for name in previous:
                os.environ.pop(name, None)
            envfile.ENV_FILE = dotenv
            envfile._from_file.clear()

            # ------------------------------------------- THE KEY THE SDK IS HANDED, TWICE
            #
            # `load` takes the path EXPLICITLY here rather than through `envfile.ENV_FILE`,
            # because its default is bound at def time and reassigning the module global does
            # not move it — the trap `check_export_fetch`'s header writes up from the other
            # side.
            dotenv.write_text(f"{batch.API_KEY_ENV}={one}\n")
            envfile.load(path=dotenv, force=True)
            checks.equal(
                tag(batch._client().api_key),
                "one",
                "the key in `.env` reaches the SDK as an explicit argument — `_client` used "
                "to construct with none and leave the read to the SDK, which is what made "
                "the value this process started with the only one it could use",
            )

            dotenv.write_text(f"{batch.API_KEY_ENV}={two}\n")
            checks.equal(
                tag(batch._client().api_key),
                "two",
                "AND A REPLACED ONE REACHES IT IN THE SAME PROCESS, which is the whole "
                "defect: the operator pastes a new key into `.env` and the next construction "
                "has to send it, with no restart of a server that is meant to run for days",
            )
            checks.equal(
                tag(batch._client(api_key=argument).api_key),
                "argument",
                "and an explicit `api_key=` still outranks both, which is how `run_batch`'s "
                "callers and the harness pass one",
            )

            # --------------------------------- AND THE DISTINCTION REACHES EVERY CHILD ENV
            #
            # READ OFF THE REAL SPAWN SITES rather than a copy of their composition. Both
            # build `dict(os.environ)`, which is correct — a child that did not inherit
            # `PKMNSCAN_HOME` would run against another store (D43) — and is also how the
            # process-global half of the precedence rule was lost at the first boundary.
            checks.ok(
                envfile.FROM_FILE_ENV in serve._child_env(_SERVE_ROOT),
                "the supervisor hands the lifted names to the capture server, so a value it "
                "took out of `.env` is not mistaken for one the operator exported",
            )
            checks.ok(
                envfile.FROM_FILE_ENV in pipeline_routes._env(),
                "and the capture server hands them to the `identify` child, which is the "
                "process that actually spends the key",
            )
            checks.equal(
                os.environ.get(envfile.FROM_FILE_ENV, "").split(),
                [batch.API_KEY_ENV],
                "and it carries NAMES ONLY — the values are already in the environment "
                "beside it, and a secret copied to a second place is a second place to "
                "leak it",
            )

            # --------------------------------------- A REAL EXPORT STILL WINS, AS PROMISED
            #
            # THE FAITHFUL SETUP IS THE SEQUENCE, not a hand-edited `_from_file`: an exported
            # variable is one `load` never lifted, so it is set BEFORE the load that would
            # have — and the marker goes with it, because a process whose parent lifted
            # nothing inherits no claim about this name. Written the other way round first,
            # this arm read `two`: a marker left over from the block above still said the key
            # came from a file, and re-reading the file was the right answer to it.
            envfile._from_file.clear()
            envfile._loaded = False
            os.environ.pop(envfile.FROM_FILE_ENV, None)
            os.environ[batch.API_KEY_ENV] = exported
            envfile.load(path=dotenv, force=True)
            checks.equal(
                tag(batch._client().api_key),
                "exported",
                "a real environment variable still outranks the file, which is the "
                "precedence `envfile` has always promised so CI can set one without "
                "editing anything",
            )
            checks.ok(
                envfile.FROM_FILE_ENV not in os.environ,
                "and nothing is published when nothing was lifted, so a marker cannot "
                "claim a name the operator exported themselves",
            )

            # ------------------------------------------------ AND NOW ONE PROCESS FURTHER
            #
            # THE CHILD IS THE CASE THAT WAS BROKEN. Reproduced as a real spawn, with the
            # dead key inherited exactly as the capture server inherits it, and the fresh one
            # only in the file. The child prints a TAG, never a value.
            copied = home / "envfile.py"
            copied.write_bytes((_SERVE_ROOT / "envfile.py").read_bytes())
            (home / ".env").write_text(f"{batch.API_KEY_ENV}={two}\n")
            script = home / "inherit.py"
            script.write_text(
                "import sys\n"
                "import envfile\n"
                "name, fresh, stale = sys.argv[1:4]\n"
                "value = envfile.get_live(name)\n"
                "print({fresh: 'fresh', stale: 'stale'}.get(value, 'other' if value "
                "else 'nothing'))\n"
            )

            def inherit(marker: Optional[str]) -> str:
                """One child, started the way the supervisor starts one: with a copy of an
                environment that already carries the key."""
                child = dict(os.environ)
                child[batch.API_KEY_ENV] = one  # the dead key, inherited
                child.pop(envfile.FROM_FILE_ENV, None)
                if marker is not None:
                    child[envfile.FROM_FILE_ENV] = marker
                done = subprocess.run(
                    [sys.executable, str(script), batch.API_KEY_ENV, two, one],
                    cwd=str(home), env=child, capture_output=True, text=True,
                    timeout=60, check=False,
                )
                return done.stdout.strip() or f"child failed: {done.returncode}"

            checks.equal(
                inherit(batch.API_KEY_ENV),
                "fresh",
                "A CHILD SPAWNED WITH THE DEAD KEY IN ITS ENVIRONMENT READS THE LIVE ONE "
                "OUT OF THE FILE, because the marker tells it that value came from a file "
                "and not from a shell — this is the arm the whole defect lived in",
            )
            checks.equal(
                inherit(None),
                "stale",
                "and WITHOUT the marker the same child answers the dead key, which is this "
                "block's own mutation: it fails red if the carry is deleted, rather than "
                "going quietly green on a machine where the parent happened to be right",
            )
            checks.equal(
                inherit("SOMETHING_ELSE"),
                "stale",
                "and a marker that does not name this key leaves it alone, so the carry "
                "widens nothing: a name the operator exported is still theirs",
            )
        finally:
            envfile.ENV_FILE, restore_from_file, envfile._loaded = env_before
            envfile._from_file.clear()
            envfile._from_file.update(restore_from_file)
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


CHECKS = (
    check_crop_preview,
    check_export_fetch,
    check_key_rotation,
)
