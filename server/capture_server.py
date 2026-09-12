"""Capture server — build-order step 5, plus the routes steps 7a and 7b add.

    POST   /capture                        take a photo into the next position in a box
    GET    /status                         counts, next index per box, store health
    GET    /photo/<box>/<index>            the stored JPEG bytes
    GET    /inventory                      the whole card map, each row carrying its label
    PUT    /inventory/<box>/<index>        correct one card's capture claims (PUT_FIELDS)
    PUT    /inventory/<box>                apply capture-claim corrections to every
                                           eligible card in a box, all-or-nothing
    DELETE /inventory/<box>/<index>        undo the newest capture: every trace of one position
    GET    /queues                         both standing queues, in the order they are worked
    POST   /review/<box>/<index>/answer    the human picks a candidate row, or takes it back
    POST   /review/<box>/<index>/stand-down close a queued question without answering it —
                                           the card is untouched, only the question closes
    POST   /review/group-answer            answer a homogeneous group in one write — one
                                           shared reason, one candidate row per card
    POST   /inventory/<box>/<index>/sold   mark one copy sold, or put its state back
    POST   /inventory/<box>/<index>/retire mark one copy retired — it left without a sale —
                                           or put its state back (D26)
    POST   /inventory/<box>/<index>/photo  re-shoot: replace the photo and sidecar in place,
                                           record untouched, allocator never involved (D26)
    POST   /inventory/<box>/<index>/remove delete one capture mid-box and slide every higher
                                           card down one index (D10, owner ruling 1)
    DELETE /boxes/<box>                    delete a whole box — records, photos, sidecars,
                                           queue entries, cache, registry (D10, owner ruling
                                           3, amended D134 — a departed record no longer
                                           blocks the delete; it is buried instead)
    GET    /graveyard                      every departed card: still sold/retired/moved in
                                           a standing box, or buried by a deleted one (D134)
    GET    /boxes/<box>/listings           what this box's SKUs are believed to be holding,
                                           and what a release would give up. FREE (D34)
    GET    /boxes/<box>/photos             what a reclaim would delete: sold cards whose
                                           photograph is still on disk, and the bytes (D89)
    POST   /boxes/<box>/photos/reclaim     delete those photographs, keep every record, keep
                                           each one's digest. `confirm: true`. No undo.
    POST   /boxes/<box>/listings/release   give up what this box's copies could account for,
                                           on the operator's word (D34)
    GET    /search?q=<text>                find a card by name, number, SKU, set hint or note
    GET    /games                          the per-game registry, as `pipeline/games.py` authors it
    GET    /codes                          the code ledger: counts, tiers, every code (C8)
    GET    /codes/lots                     every lot built so far, newest first
    POST   /codes/lots                     plan a lot, or BUILD one — reserving its codes
    POST   /codes/scan                     decode a box's photographs into the ledger. FREE
    POST   /codes/export                   preview a channel export, or COMMIT one to an order
    GET    /boxes                          every box: its dividers, its fill, its capacity
    POST   /boxes                          register a box before any card goes into it
    PUT    /boxes/<box>                    rename it, declare its dividers, seal or unseal it
    POST   /boxes/<box>/sections           put ONE divider in front of the next card, at the
                                           moment the real one goes in (D10, the capture
                                           screen's `S`). Takes no index: the store reads it
    POST   /pipeline/preflight             what a run would cost. FREE, creates no run
    POST   /pipeline/crop-preview          what the reading sends: the cut, and the digits
    POST   /pipeline/identify              START A RUN. THE ONE THAT SPENDS MONEY
    GET    /tcg/sets                       D65's real set names for a game, for the hint field
    GET    /pipeline/runs                  every run, newest first, with its phase
    GET    /pipeline/runs/<name>           one run: manifest, console tail, artefacts
    GET    /pipeline/runs/<name>/file      one artefact's bytes — the import CSVs, the report
    GET    /pipeline/runs/<name>/pricing   the per-SKU pricing table and this run's answers
    GET    /pipeline/runs/<name>/scope    what a fetch would ask TCGplayer for, and why
    POST   /pipeline/runs/<name>/export   fetch this run's Filtered Export from TCGplayer
    GET    /pipeline/runs/<name>/history   what one SKU has been selling for. Public hosts
    GET    /pipeline/runs/<name>/trends    many SKUs' shape at once, for the row strip
    POST   /pipeline/runs/<name>/<step>    join | emit | reconcile. Free, run in the request
    GET    /pipeline/markdowns             every stale-listing markdown, newest first (D100)
    POST   /pipeline/markdowns             which live listings are not selling, and what each
                                           would be re-priced to. FREE; `write` makes the
                                           worklist and uploads it nowhere
    POST   /pipeline/markdowns/<stamp>/push    that import file into TCGplayer's STAGED copy,
                                               which no buyer can see
    POST   /pipeline/markdowns/<stamp>/publish move that staged upload LIVE — the one route
                                               here that changes what a buyer pays
    POST   /pipeline/markdowns/<stamp>/apply   the edited worklist back; `write` produces the
                                           price-only import CSV. Every row it writes carries
                                           `Add to Quantity` 0, so it cannot move a quantity
    GET    /pipeline/markdowns/<stamp>/file    the worklist to edit, and the import to upload

The first five are build-order step 5 in `docs/GATES.md`. The sixth is the capture app's
undo, and it lives here rather than in the app because deleting a record, a sidecar, a
photo, two queue entries and a paid answer together is a store write, and D13 keeps exactly
one writer for those — the app has no filesystem and no lock. The last three are 7b's three
screens — the review queue, the inventory views, and the Fulfillment view's mark-sold — and
they are here for the same reason: each of them ends in a write to `inventory.json`,
`review.json` or `parked.json`, and there is one writer for those.

THE LAST FOUR ARE D20's, and they are the first routes in this file that are not about a
card. A box was previously a number a card happened to name — `docs/specs/capture-server.md`
§5.4 put it as "there is no box object anywhere in `store/`" — so it could not be created
empty, named, listed, or sealed, and a mistyped box number was caught only by `new_box`
AFTER a photo had been written. `store/master.py:Box` is now an object with a lifecycle, and
these three routes are its whole surface: create it before the first card, declare its
dividers, seal it when the lid goes on. `GET /search` is the fourth and is a read: D7 maps a
SKU to every position holding it, and until now nothing served that map to a screen.

THE REMOVE AND BOX-DELETE ROUTES ARE D10's THREE OWNER RULINGS OF 2026-08-23, and they are
the two most destructive things this server can be asked to do. Ruling 1 overrules "nothing
that renumbers may exist" for exactly one case — a junk capture pulled out of a contiguous
stack, where the cards behind it really do slide forward — and `do_remove_card` holds the
boundary that keeps the old rule's reason alive: no sold or retired gap above, no listed
SKU above, refused as `renumber_blocked` otherwise. Ruling 2 narrows the capture-undo to
`captured` alone (`UNDOABLE_STATES` below has the argument). Ruling 3 lets a whole box go,
refused as `box_not_empty_of_commitments` while anything in it is sold, retired or
listing-held — those records are history and commitments, not clutter. The routes are the
gate's mechanism; the typed confirmation `docs/DESIGN.md`'s destructive-action clause asks
for is the app's, on top of these refusals, never instead of them.

THAT REFUSAL HAD TWO GROUNDS AND ONE DOOR UNTIL D34, and the missing one is a PAIR of routes:
`GET /boxes/<box>/listings` and `POST /boxes/<box>/listings/release`. A box held open by a
sold or retired card can be freed — both states reverse on their own routes, and the refusal
names them. A box held open by a LISTING could not be, ever: `staged` is drawn down in one
place, by the rise in live quantity a fresh export reports, so an import that never landed
left counts nothing in this repo could clear. Box 1's 53 cards sat behind 45 such records.

The release's answer is unlike everything else in this file: it deletes nothing, moves no
record, touches no file, and its entire content is a claim by the operator about a system
this process cannot see. So it takes D33's `confirm` field and always writes a history line.

AND IT IS BUDGETED BY THE CALLING BOX'S UNSOLD COPIES — the owner's ruling, overruling a
first build that zeroed each SKU outright. A listing is per SKU and copies are fungible (D7
amended), so zeroing let a release reached from box 1 give up commitments only box 3's copies
could ever have backed. Each SKU now gives up at most what THIS box holds, which makes that
impossible structurally. Where a SKU is shared the remainder stays and the box stays refused,
deliberately; the GET names that outcome (`frees_box`, `still_held`) BEFORE the press, which
is D33's preflight shape one register down and the half the first build got wrong by putting
the blast radius in the receipt. `_release_plan` is the single source for both routes.

EVERY CARD ANSWER NOW CARRIES A `place` BLOCK, and it is D20's sentence rather than a
convenience. A bare index tells you nothing about where to put your thumb; "#40 of 250, 16%
in" does, and that needs a denominator — the box's frozen capacity when it is sealed, and
its fill so far while it is open. `_Places` below builds one block for every route that used
to add a bare `label`, so there is one renderer for it and not four. The three old keys
(`label`, `section`, `card`) are still on every one of those answers, unmoved: `app/src/`
reads them today, and a place block that arrived by breaking the screens that already work
would not be an improvement.

7b IS BUILT BEFORE GATE B, WHICH `docs/specs/capture-app.md` SECTION 0 SAYS NOT TO DO. The
owner authorised it explicitly on this branch. The consequence to keep in mind while reading
the three routes below is not that they are unverified — T7 covers every one of them — but
that the DATA they move was hand-built until Gate B. That run produced the first real
entries on 2026-08-22 — 16 of them — and the shape survived contact: same keys, same
candidate rows, every one answered through the route below. What it did not widen is the
range. All 16 carried one reason code, `metadata_detection_disagreement`, at prices that
parked every one of them — a queue holding more than one kind of card is still something
no run has produced, so wherever `docs/DESIGN.md`
does not settle a behaviour the route says so in a comment naming what would settle it,
rather than picking the plausible-looking option and leaving no trace.

THE LAST SEVEN ARE THE PIPELINE SEAM, AND THEY CHANGE WHAT THIS FILE IS. Its header said
for months: *"Still absent and still deliberate: no identification, no pricing, no UI. This
process never spends money: it holds no API key and makes no outbound call."* Both halves of
the last sentence are still literally true — nothing here reads a key and nothing here opens
a socket to Anthropic — but it was written to mean something stronger than its letter, and
`POST /pipeline/identify` starts a child that spends. Rewriting the sentence rather than
leaning on its letter is the point: a promise that quietly narrows to a technicality is the
drift D16 exists to catch.

The owner asked for it in as many words — *"how do i get api calls/pushing from our
localhost server so that i can actually push runs at box/section/whatever-level i want, get
data back, and manage CSVs?"* — and until those routes existed the answer was that they
could not. Every run this project has done was driven by an agent typing commands, which
made the pipeline the one capability in the product with no way in, and `CLAUDE.md`'s
route-is-not-a-feature rule pointed straight at it.

What replaces the promise, since a guarantee deleted and not replaced is a regression: ONE
route spends and is named for it; it refuses without an explicit `confirm`; it refuses a
second run over a capture directory a live run is already reading; and the preflight beside
it is free, creates no run directory at all, and is what the screen shows first. The rest of
the seam — every read, and `join`/`emit`/`reconcile` — is free and re-runnable, which is the
property D1 gave the two-phase split. `server/pipeline_routes.py` carries the whole argument
and every handler; this file dispatches to it and translates one exception type.

Still absent and still deliberate: no UI, no pricing rule, no identification logic. This
file computes nothing about a card that `pipeline/` does not already decide.

READS ARE OPEN AND WRITES ARE ORIGIN-CHECKED, as of this change. `Access-Control-Allow-Origin: *`
on every route meant any page in any other tab of the owner's browser could send
`DELETE /inventory/3/17` — D10's hard delete of a record, a sidecar and a photo, with no
backup — and nothing here could tell it from the capture app. POST, PUT and DELETE now
require an `Origin` this server knows (or none at all, which is what a non-browser client
sends); GET is unchanged and still `*`, because `GET /photo` is loaded as an image by two
screens. The argument, the allowlist and the environment variable that extends it are at
`SAFE_METHODS` below. It is a CSRF gate, NOT authentication, and it still adds none.

THE REASON IT USED TO GIVE FOR THAT IS NOW FALSE, AND IT IS CORRECTED RATHER THAN LEFT
STANDING (D64). This sentence read "there are no credentials in this product and this adds
none", and the first half was deleted by a change made later: `server/tcg_export.py` reads a
TCGplayer session cookie out of `.env` and `POST /pipeline/runs/<name>/export` spends it. A
premise quietly falsified by a later change, with its conclusion left in place, is the
failure D41 records for a comment that had outlived a layout — and here it would understate
what this gate is for, by telling a reader there is nothing behind it worth reaching.

WHAT IS BEHIND IT NOW: a page in another tab could otherwise make this server spend the
owner's marketplace session. The gate answers 403 before the route runs, so the cookie is
never read for a request whose origin this server does not know — which is why the export
route needs no check of its own, and why weakening `SAFE_METHODS` is a bigger decision than
it was when this paragraph was written.

EVERY WRITE GOES THROUGH `store.session.Store.write()`. The server never touches
`inventory.json` and never writes a photo outside that lock. `store/__init__.py` calls it
"a second writer, not a second owner", which concretely means the server holds no
authoritative copy of anything between requests: no cache, no dirty set, no periodic flush.
Reads take no lock at all, because every write is an atomic replace — and because the lock
is exclusive-only, a server that locked to read would serialise both devices' polling
behind every write and then fail after the 30-second timeout.

POSITIONS ARE NEVER CHOSEN HERE. `Inventory.allocate_capture` assigns them, takes no index,
and runs inside the same lock as the record it writes. Any design where this file computes
an index and hands it to a writer is the lost update `store/__init__.py` exists to warn
about — two devices both showing "next: 17", both posting, the second silently overwriting
the first.

PHOTO LAYOUT is box-keyed (D6, D13), under `<home>/captures/cards/box<N>/<index>.jpg` with
a JSON sidecar beside it. The `cards` level is not decoration: `identify.sidecar.scan`
walks its root recursively and turns EVERY file with a photo suffix into a capture and
therefore a paid Batch request, and `scripts/screenshot.sh` writes UI renders into
`captures/ui/`. Rooting at `captures/` would bill every screenshot. Nothing but card photos
and their sidecars may ever be written below `captures/cards/`.

T7 REACHES THIS FILE, as of 2026-08-13, and the paragraph here used to say the opposite —
which was true when this module shipped at step 5 and stopped being true the day
`harness/tests/t7_store_and_seams.py` landed. It imports this module and calls every route
in it: allocation and its refusal codes, `/status` on a healthy store and on a corrupt
record, the sidecar seam `identify.sidecar` reads back, `GET /inventory` and the position it
renders, two- and four-way concurrent captures over real sockets, and each of the DELETE
route's rules — what it removes, that it removes only the newest card in a box, and that it
refuses once `emit` has written the card's row into an import file. 7b's three routes landed
with their own cases in the same test, which is the schedule `docs/specs/capture-app.md`
section 3 set for the undo route and the one thing it got right about scheduling.

WHAT T7 STILL DOES NOT REACH, from `docs/DEBTS.md`, so a green harness is read for what it
is. Two named cases rather than a package nobody looks at:

  twenty-way contention   T7 runs two and four simultaneous captures, matching D5's two
                          devices. The twenty-way case is what found `request_queue_size`
                          at its default of 5 — 8 served, 12 reset by the OS — and if that
                          constant below is ever lowered, nothing will notice.
  the bare-interpreter    `make server` runs this on system `python3` with no venv. T7
  start                   imports the module under whichever interpreter runs the harness,
                          so it cannot see a missing dependency that the harness supplies.

THE THIRD CASE WAS THE MISSING HISTORY LINE, AND IT IS WRITTEN NOW (2026-08-13). Three
routes here write without moving a card between states — the PUT correction, the undo, and
the review answer — and each appends its own event, argued at `SERVER_EVENTS` below and
again at each route. The paragraph this replaces recorded the omission with a shrug: the
store logs state transitions and none of these is one. That much is true and was never the
question, since `store/__init__.py` calls this file the audit trail and says the history IS
inventory truth over time — which is a claim about the physical positions in a box, not
about the state enum. `docs/DEBTS.md` now records what the three lines still do not cover.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import json
import os
import re
import signal
import sys
import concurrent.futures
import threading
import time
import uuid
from bisect import bisect_left, bisect_right
from dataclasses import asdict, replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import parse_qs, urlparse

# `make server` runs this by path, so sys.path[0] is server/ and the project packages are
# not importable without this. Same idiom and same reason as harness/run.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codes import products  # noqa: E402
from pipeline import games, join, tcgcsv  # noqa: E402
from pipeline import orders as order_engine  # noqa: E402
from cli import runs as cli_runs  # noqa: E402
from store import Store, files, master, queues  # noqa: E402
from store import orders as order_store  # noqa: E402

# The pipeline seam, in its own module because it is the one part of this server that can
# cause money to be spent — see its header for what replaced the promise this file's own
# header used to make. Imported here rather than inlined so that the boundary is a file
# boundary: everything above this line still holds no key, opens no socket, and starts no
# child process. THE TWO ORDER IMPORTS ABOVE DO NOT WEAKEN THAT: `pipeline/orders.py` is a
# pure resolver over an `Inventory` handed to it and `store/orders.py` is one more JSON
# document beside the four this store already writes — stdlib-only, no credential, no
# socket, no child — so the line is where it always was and the promise it makes is
# unbroken.
#
# THAT SENTENCE IS NOW TRUE OF THIS FILE AND FALSE OF THE PROCESS, and it is rewritten rather
# than qualified (D64). `server/tcg_export.py` reads the TCGplayer session cookie out of
# `.env` and opens a socket to `store.tcgplayer.com` to download the operator's own Filtered
# Export — so this server does hold a secret and does make an outbound call, and saying "no
# socket TO ANTHROPIC" instead would be the technicality-narrowing D16 exists to catch. What
# still holds, and what the boundary is for: the call is one host, one method, one route, in
# one module reached only from `pipeline_routes`, and it cannot cause a charge. The one route
# that can is still `POST /pipeline/identify`, and it is still named for it.
# `from server import ...` and not a bare `import pipeline_routes`: this file is run BOTH
# ways — by path as `make server` does, where sys.path[0] is server/, and as a package
# module as `harness/tests/t7_store_and_seams.py` imports it. Only the package form works
# under both, and the sys.path line above is what makes it work under the first.
from server import codes_routes  # noqa: E402
from server import pipeline_routes  # noqa: E402
# The shipping seam, below the line for the same reason and by the same rule (D61). It opens
# no socket and holds no key, but it does hold a buyer's ADDRESS in memory for half an hour,
# which is its own boundary worth keeping in one file rather than inlined here.
from server import shipping_routes  # noqa: E402
# The order transport, and it is the SECOND outbound call this process makes (D63/D66). Below
# the line and beside the two above for the reason the paragraph gives: it reads the
# TCGplayer session cookie out of `.env` and opens a socket to
# `order-management-api.tcgplayer.com`. It cannot cause a charge — it is a read of this
# account's own orders — so the one route that spends is still `POST /pipeline/identify`.
from server import order_transport  # noqa: E402
from server import ports  # noqa: E402

HOST = "0.0.0.0"

# One identity per process, reported by `GET /status` so the app can tell a restart from a
# reload. Computed at import, which is exactly the point: it changes when, and only when, this
# module is loaded again.
BOOT_ID = uuid.uuid4().hex[:12]
STARTED_AT = time.time()

# On every response as well as in `GET /status`, so the app notices a restart on traffic it was
# making anyway rather than on a poll of its own. Must be listed in `Access-Control-Expose-Headers`
# or it is present on the wire and unreadable from JavaScript — see `_cors_headers`.
BOOT_HEADER = "X-Pkmnscan-Boot"

# DERIVED PER CHECKOUT, NOT A CONSTANT (D46). It was `8000` here while `store/files.py:home()`
# already defaulted to the checkout the code runs from — so every worktree served a DIFFERENT
# store on the SAME port, and whichever process won the bind answered everyone. The main tree
# still answers 8000 and every doc that says so stays true; a linked worktree gets its own.
# `server/ports.py` carries the argument and `PKMNSCAN_PORT` overrides.
PORT = ports.capture_port()

# WHERE THE BUILT APP IS, AND IT IS A PROPERTY OF THE CHECKOUT RATHER THAN OF THE STORE
# (D138). `app/dist/` beside this tree's own `app/src/`, so a worktree serves the bundle it
# built from its own source on its own port, exactly as it serves its own store (D43) — the
# two facts are the same fact and neither needs a new variable to say it.
#
# NOT AN ENVIRONMENT VARIABLE, and the frozen-release form of `docs/specs/one-process.md` §7
# is the only thing that would want one. Read through `app_dist()` at call time rather than
# baked into a default argument, which is what lets T7 point one server at a temporary build
# without a knob this product does not otherwise have.
APP_DIST = Path(__file__).resolve().parent.parent / "app" / "dist"

# The eight types `vite build` emits, and nothing else is served. A map rather than
# `mimetypes.guess_type`: that module reads the machine's own `/etc/mime.types`, so the
# Content-Type of this product's JavaScript would depend on which Mac it is running on —
# and `.webmanifest` is absent from it entirely on macOS, which is the one file whose type
# decides whether the dock app installs (D108).
APP_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webmanifest": "application/manifest+json",
    ".woff2": "font/woff2",
    ".json": "application/json",
}

# Vite content-hashes everything under `assets/`, so a name that changes when the bytes do can
# be cached forever; `index.html` and the manifest are the two files whose NAME is stable and
# whose bytes move on every build, so they must never be held — a cached index would go on
# asking for hashed assets that the swap has already deleted.
APP_IMMUTABLE = "public, max-age=31536000, immutable"
APP_NO_STORE = "no-store"

CAPTURES_DIRNAME = "captures"
CARDS_DIRNAME = "cards"
PHOTO_SUFFIX = ".jpg"
SIDECAR_SUFFIX = ".json"
INDEX_PAD = 4

# A 24 MB ceiling on one decoded image. A phone JPEG is 2-5 MB; this refuses a body that
# would sit in memory on a threaded server rather than trusting the client's Content-Length.
MAX_IMAGE_BYTES = 24 * 1024 * 1024

# The server writes `.jpg` and only `.jpg`, so `GET /photo` can find a file from a box and
# an index alone. It therefore verifies the bytes rather than converting them: re-encoding
# at capture time belongs to the batch step, and writing a PNG under a `.jpg` name is a lie
# that surfaces three stages downstream.
JPEG_MAGIC = b"\xff\xd8\xff"

# --------------------------------------------------------------------------------- CORS
#
# THIS SERVER USED TO ANSWER `Access-Control-Allow-Origin: *` ON EVERY ROUTE, INCLUDING THE
# ONES THAT DESTROY THINGS, and that was a hole rather than a looseness. `*` plus
# `Allow-Methods: DELETE` plus a preflight that answered 204 for any path means ANY page the
# owner happens to have open in another tab could send
# `DELETE http://localhost:8000/inventory/3/17` — D10's hard delete of the record, the
# sidecar and the photo, with no backup — or mark a card sold. Nothing read `Origin`, so
# nothing could tell that request from the capture app's.
#
# THE FIX IS AN ORIGIN ALLOWLIST ON THE THREE MUTATING VERBS, AND IT IS NOT AUTHENTICATION.
# It stops a page the owner did not open from spending his inventory, which is exactly the
# CSRF shape and exactly what the browser's own `Origin` header is for. Anything holding a
# shell on this machine was never in scope: `curl` sends no `Origin`, and a request without
# one is allowed through — see `_origin_allowed` for why that is the right default and not a
# hole of its own.
#
# GET STAYS `*` DELIBERATELY. `GET /photo/<box>/<index>` is D6's route and both the review
# queue and the pull preview load it as an image; an `<img>` sends no `Origin` at all, and
# narrowing the read side would break the two screens the photo service exists for while
# protecting nothing — a read of a photo of a card is not a write.
#
# WHY THIS IS WORTH MORE THAN IT LOOKS: the roadmap puts this server on the LAN so the
# Fulfiller can reach it from his phone (D5, D13). At that point `*` is not exposed to the
# owner's own tabs, it is exposed to every device on the network.
#
# HEAD IS IN BOTH LISTS, FOR THE REASON GET IS IN THEM: it writes nothing. `do_HEAD` runs
# `do_GET` with the body withheld, so a HEAD cannot reach a mutating route at all — and
# gating it would answer 403 to a READ, which is the one thing every paragraph above says
# this server does not do. It is in `ALL_METHODS` as well because an origin this server
# knows may never be told less than one it does not.
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
ALL_METHODS = ("GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS")

# The Vite dev server (`make dev`), on both spellings of this machine. Two entries and not
# one because a browser's `Origin` is the literal string in the address bar: `localhost` and
# `127.0.0.1` are the same host and are not the same origin, and the owner types both.
#
# THE PORT IS THIS CHECKOUT'S, NOT THE CONSTANT 5173, AND IT WAS THE CONSTANT UNTIL
# 2026-08-30 (D43, amended). That entry moved five readers of the dev port onto one
# derivation and missed this one, so a linked worktree served its app on its own port and
# then REFUSED EVERY WRITE THAT APP MADE — capture, undo, mark-sold, retire, the mid-box
# delete and the claim editor, all 403 `origin_not_allowed`. Reads are ungated, so every
# screen rendered and looked correct; the failure was a branch's app that could look at the
# inventory and never change it.
#
# IT IS D43's OWN SUBJECT WITH ONE FILE MISSED, and the second time: that entry's amendment
# records `.claude/launch.json` found the same way, and the lesson it drew is the one that
# applies here — a tracked constant cannot be right in every checkout, so it has to be asked
# for rather than written down.
#
# NOTHING MOVES IN THE MAIN TREE. `ports.dev_port()` answers 5173 there by construction, so
# this tuple is byte-identical to the constant it replaces and every doc naming 5173 stays
# true. Only a linked worktree changes, and only from "refuses everything" to "allows its
# own app".
#
# A CHECKOUT ALLOWS ITS OWN ORIGIN AND NOT THE MAIN TREE'S, which is the security half and
# is deliberate rather than incidental. Adding 5173 back for worktrees would let a page
# served by the MAIN tree write into a branch's store — the cross-tree write D43 exists to
# prevent, arriving through the one control in this repo that is supposed to stop a page
# from writing where it should not. Pointing one tree's app at another tree's server is a
# real thing to want and it is already a deliberate act (`VITE_CAPTURE_SERVER`), so it
# takes the deliberate answer below: name the origin in `PKMNSCAN_ALLOWED_ORIGINS`.
#
# COMPUTED ONCE AT IMPORT, unlike `allowed_origins()` below, and the difference is that this
# has no input that can change while the process runs: `dev_port` reads no environment and
# the checkout does not move. The env var is what is read fresh, and it is read fresh for
# the reason stated there.
# AND THE CAPTURE PORT ITSELF, SINCE D138 — THE APP IS SERVED FROM HERE NOW. That entry made
# this process serve `app/dist/` beside its own routes, so the product's own page is
# same-origin with the server it writes to, and a browser sends `Origin` on a same-origin
# write. The list named only the dev port, so the FIRST WRITE THE OWNER MADE FROM THE REAL
# APP WAS REFUSED — a box delete, 403 `origin_not_allowed`, reported 2026-09-11. Reads are
# ungated, so every screen drew correctly and only writing was broken: D43's own failure
# shape, arriving through the one control meant to stop a page writing where it should not,
# for the third time.
#
# SAME-ORIGIN IS THE SAFEST ENTRY IN THIS LIST, not a relaxation of it. A page this server
# itself served, asking this server to write, is the case the gate exists to permit; the
# cross-tree write it exists to refuse is unaffected, because a linked worktree derives its
# own capture port and still allows only its own.
#
# BOTH PORTS STAY. `make dev` runs beside `make up` (D138) on the dev port, against this
# server, and that loop is what a session editing screens uses — dropping it would refuse
# every write from the development app while looking like a tidy-up.
DEFAULT_ALLOWED_ORIGINS = tuple(
    f"http://{host}:{port}"
    for port in (ports.capture_port(), ports.dev_port())
    for host in ("localhost", "127.0.0.1")
)

# EXTENDED, NEVER REPLACED, and deliberately not able to re-enable `*`. The LAN move above
# needs one more origin — `http://the-mac.local:5173` — and rebuilding the whole list from an
# environment variable would let a typo silently switch the protection off while looking like
# configuration.
#
# THIS COMMENT USED TO CLAIM THE AUDIT GUARDS THIS NAME, AND BOTH HALVES WERE FALSE. It said
# the variable was "documented in the docs the same day it landed" — it was documented
# nowhere for the day and a half it existed — and that "an undocumented one here fails a
# commit", which the check cannot do: `scripts/docs-audit.py:check_env_vars` walks docs to
# code, so it catches a documented variable that is not real and is blind to a real one that
# is not documented. The row was green at "9 documented, all real" the entire time.
#
# Left as a correction rather than deleted, because the failure is the interesting part: a
# comment asserting its own safety net is exactly the sentence nothing mechanical can read,
# and this file is where the next person looks to find out whether adding a knob is safe.
# `docs/DEBTS.md` records the one-directional blind spot; `docs/specs/capture-server.md`
# documents the variable itself.
ORIGINS_ENV = "PKMNSCAN_ALLOWED_ORIGINS"


def _normalize_origin(origin: str) -> str:
    """Fold an origin to something two spellings of the same thing compare equal on.

    Scheme and host are case-insensitive and a trailing slash is not part of an origin at
    all, but `http://Localhost:5173/` is what a human types into a config file. The port is
    NOT defaulted in — `http://localhost` and `http://localhost:80` are the same origin to a
    browser and this treats them as different, which errs toward refusing rather than toward
    admitting, and the refusal names the string it wanted.
    """
    return origin.strip().rstrip("/").lower()


def allowed_origins() -> Tuple[str, ...]:
    """The origins that may WRITE, read fresh from the environment on every request.

    Not a module constant, because `make server` is a long-running process the owner starts
    once: reading at import time would mean adding a LAN origin requires a restart, and the
    restart is the step that gets skipped. The cost is one `os.environ` lookup and one split
    per mutating request, which is nothing beside the store lock the same request then takes.

    Split on commas OR whitespace. An origin can contain neither, so there is no ambiguity to
    resolve and no quoting rule for the owner to remember.
    """
    extra = os.environ.get(ORIGINS_ENV) or ""
    configured = [value for value in re.split(r"[,\s]+", extra) if value]
    return tuple(
        _normalize_origin(origin) for origin in DEFAULT_ALLOWED_ORIGINS + tuple(configured)
    )

_PHOTO_RE = re.compile(r"^/photo/(\d+)/(\d+)$")
_INVENTORY_ITEM_RE = re.compile(r"^/inventory/(\d+)/(\d+)$")
# The box-level claim apply: `PUT /inventory/<box>` is `PUT /inventory/<box>/<index>` one
# path segment broader — same verb, same claim vocabulary, one level up. Matched AFTER the
# item pattern in the PUT dispatch, though either order is correct: both are anchored, and
# a path cannot carry one segment and two.
_INVENTORY_BOX_RE = re.compile(r"^/inventory/(\d+)$")
_REVIEW_ANSWER_RE = re.compile(r"^/review/(\d+)/(\d+)/answer$")
_REVIEW_CATALOG_RE = re.compile(r"^/review/(\d+)/(\d+)/catalog$")
# D37. Its own path rather than a mode of the answer, because it is a different act: the
# answer says what the card IS, and this says the question is closed while the card is
# untouched. A flag on the answer route would have made "I decline to identify this" reach
# the code path whose entire job is validating an identification.
_REVIEW_STAND_DOWN_RE = re.compile(r"^/review/(\d+)/(\d+)/stand-down$")
_SOLD_RE = re.compile(r"^/inventory/(\d+)/(\d+)/sold$")
_RETIRE_RE = re.compile(r"^/inventory/(\d+)/(\d+)/retire$")
_RESHOOT_RE = re.compile(r"^/inventory/(\d+)/(\d+)/photo$")
# The mid-box delete (D10, owner ruling 1). A DISTINCT POST PATH, not a flag on the DELETE
# route, and the shape is load-bearing twice over. First, the old newest-only undo must not
# be one stray token away from an operation that renumbers a box: the capture screen's undo
# sends `DELETE /inventory/<box>/<index>` and nothing that mangles, retries or replays that
# request can ever reach this path. Second, the shift is NOT idempotent — after it runs, a
# different physical card sits at the deleted index, so a replayed request would aim at the
# neighbour that slid in — which both disqualifies the DELETE verb and requires a body:
# `do_remove_card` demands the target's own `capture_id` and refuses a mismatch, so a
# replay of a lost response refuses instead of deleting a second card.
_REMOVE_RE = re.compile(r"^/inventory/(\d+)/(\d+)/remove$")
# D83's third door. A POST beside `remove` and `retire`, for the identical shape of reason:
# a different verb on a path longer than `/inventory/<box>/<index>`, whose own regex is
# anchored to end there, so this cannot shadow the PUT and DELETE routes. Aim-checked like
# `remove` and not idempotent like a capture — see `MOVE_FIELDS`.
_MOVE_RE = re.compile(r"^/inventory/(\d+)/(\d+)/move$")
# The batched move (D83): every on-hand card in a box, or a ticked selection of them, in one
# write. Box-level like `_INVENTORY_BOX_RE` one register up, and matched after the single-
# card `_MOVE_RE` for the reader's sake — both are anchored and admit no ambiguity between
# them, since one carries an index and the other does not.
_MOVE_CARDS_RE = re.compile(r"^/inventory/(\d+)/move$")
# Digits only, like every other position pattern here: `/boxes/3`, never `/boxes/three`.
# A non-numeric box therefore falls through to `no_such_route` rather than reaching a
# handler that would refuse it in `box_invalid` — the same trade the four patterns above
# already make, and the reason `_require_box` still exists for the body of POST /boxes.
_BOXES_ITEM_RE = re.compile(r"^/boxes/(\d+)$")

# D34's one route. Under `/boxes/<box>` rather than under `/listings` because the operator
# arrives at it from a box — it is the box header's answer to the box header's refusal —
# even though what it writes is SKU-scoped and the response has to say so.
_BOX_LISTINGS_RE = re.compile(r"^/boxes/(\d+)/listings$")
_BOX_LISTINGS_RELEASE_RE = re.compile(r"^/boxes/(\d+)/listings/release$")
# D10's divider, opened one at a time from the capture screen. A POST on a sub-path rather
# than a `sections` field on `PUT /boxes/<box>`, and the difference is what the caller has
# to know: the PUT takes a whole layout the client must already hold, and this one takes
# nothing at all — the index comes from `next_index` inside the lock, which is the only
# place it can be read without a round trip that could go stale between the two halves.
_BOX_SECTIONS_RE = re.compile(r"^/boxes/(\d+)/sections$")
# D89's pair: the free count of what a reclaim would delete, and the reclaim itself.
_BOX_PHOTOS_RE = re.compile(r"^/boxes/(\d+)/photos$")
_BOX_PHOTOS_RECLAIM_RE = re.compile(r"^/boxes/(\d+)/photos/reclaim$")

# The pipeline routes. A run name is `<date>-<slug>-<nn>` and nothing else builds one, so
# the character class here is the same one `pipeline_routes._open_run` validates against —
# a path that reaches the handler is already known not to hold a separator.
_RUN_ITEM_RE = re.compile(r"^/pipeline/runs/([A-Za-z0-9._-]+)$")
_RUN_FILE_RE = re.compile(r"^/pipeline/runs/([A-Za-z0-9._-]+)/file$")
# The pricing table and this run's answers, in one read (D49). Matched before the
# run-item pattern for the same reason the download is: the more specific path reads
# first, for whoever is following this list rather than the regex engine.
_RUN_PRICING_RE = re.compile(r"^/pipeline/runs/([A-Za-z0-9._-]+)/pricing$")
# MATCHED BEFORE `_RUN_STEP_RE`, WHICH WOULD OTHERWISE SWALLOW IT. That pattern's second
# group is `[a-z]+` and `export` is `[a-z]+`, so the order of the two `if`s at the dispatch
# site is what keeps this route from being refused as `no_such_step` — the same care every
# GET-only sibling below needs, and the reason they are declared together.
_RUN_EXPORT_RE = re.compile(r"^/pipeline/runs/([A-Za-z0-9._-]+)/export$")
# The price history for ONE SKU, named on the query string (D62). Matched before the
# run-item and step patterns for the same reason the two above are: the more specific
# path reads first. `history` would otherwise be eaten by `_RUN_STEP_RE`, whose
# `[a-z]+` matches it exactly — and a GET never reaches that pattern, so the collision
# is latent rather than live. Ordered defensively all the same: the day somebody adds a
# GET step, the specific path is already above it.
_RUN_HISTORY_RE = re.compile(r"^/pipeline/runs/([A-Za-z0-9._-]+)/history$")

# D79's batched read, beside D62's single one. `/history` answers one SKU for the panel and
# `/trends` answers many for the row strip — two routes because they carry two different
# payloads for two different drawings, not one route with a mode: the panel needs every figure
# a reading has and the strip needs a shape and a sign, and a shared handler would send the
# panel's payload forty-six times to draw the strip's.
_RUN_TRENDS_RE = re.compile(r"^/pipeline/runs/([A-Za-z0-9._-]+)/trends$")
# What a fetch WOULD ask TCGplayer for, before one is pressed (D76). Same hazard as the
# three above and the same remedy: `scope` is `[a-z]+`, so `_RUN_STEP_RE` would answer it
# `no_such_step` if this were declared after it. GET only — it presses nothing.
_RUN_SCOPE_RE = re.compile(r"^/pipeline/runs/([A-Za-z0-9._-]+)/scope$")
_RUN_STEP_RE = re.compile(r"^/pipeline/runs/([A-Za-z0-9._-]+)/([a-z]+)$")

# The stale-listing markdown (D100). A stamp is `YYYYMMDD-HHMMSS` and nothing else mints one,
# so the character class here is narrower than the run patterns above and narrower still than
# what `pipeline_routes._open_markdown` validates against — a path that reaches either
# handler is already known to hold no separator, and is then checked for MEMBERSHIP as well.
# The download is declared first for the reason its run-scoped sibling is: the more specific
# path reads first, for whoever is following this list rather than the regex engine.
_MARKDOWN_FILE_RE = re.compile(r"^/pipeline/markdowns/([0-9]{8}-[0-9]{6})/file$")
_MARKDOWN_APPLY_RE = re.compile(r"^/pipeline/markdowns/([0-9]{8}-[0-9]{6})/apply$")
# THE TWO THAT REACH TCGPLAYER AND CHANGE SOMETHING THERE. Separate patterns and separate
# handlers, never one route taking "which": `push` changes the operator's own staged copy,
# which no buyer can see, and `publish` changes what a buyer pays. A single route with a mode
# flag is one typo away from doing the second when it meant the first, and the whole reason
# 2026-09-06's accidental upload was survivable is that those two are not one press.
_MARKDOWN_PUSH_RE = re.compile(r"^/pipeline/markdowns/([0-9]{8}-[0-9]{6})/push$")
_MARKDOWN_PUBLISH_RE = re.compile(r"^/pipeline/markdowns/([0-9]{8}-[0-9]{6})/publish$")
# The undo for a push, and only before it is published. Narrower than the portal's own
# control on purpose: `clearstagedinventory` empties the whole staged channel and takes no id.
_MARKDOWN_ROLLBACK_RE = re.compile(r"^/pipeline/markdowns/([0-9]{8}-[0-9]{6})/rollback$")
# The lens (D103): every live listing this survey saw, and the two readings over one of them.
# Structural siblings of the run-scoped pair below, for the reason `_history_for_entry` gives
# — the document holding the export row is what says what the card is, so the address names a
# document and the client never supplies a card's identity.
_MARKDOWN_TABLE_RE = re.compile(r"^/pipeline/markdowns/([0-9]{8}-[0-9]{6})/table$")
_MARKDOWN_HISTORY_RE = re.compile(r"^/pipeline/markdowns/([0-9]{8}-[0-9]{6})/history$")
_MARKDOWN_TRENDS_RE = re.compile(r"^/pipeline/markdowns/([0-9]{8}-[0-9]{6})/trends$")

# The shipping batches (D61). A batch id is 128 random bits rendered as hex by
# `server/shipping_routes.py:_new_batch_id`, and the character class here is the alphabet
# that mints them — a path that reaches either handler is already known to hold no
# separator and no dot, so nothing downstream needs a traversal rule.
#
# THE GET IS A SAFE METHOD AND IS THEREFORE NOT BEHIND THE ORIGIN GATE, which is exactly
# why the id is unguessable rather than a counter: `_dispatch` checks the origin only for
# the mutating verbs, so the id is the whole of what stands between a stray page and a
# buyer's address. The file path is matched before the item path for the reader's sake;
# the item pattern is anchored and admits no slash, so it could never swallow the longer
# one in any case.
_SHIPPING_FILE_RE = re.compile(r"^/shipping/batches/([A-Za-z0-9]{1,64})/file$")
# T2b's fill. Declared beside the download for the reader's sake and matched under POST,
# where the item pattern below is never consulted — it is a DELETE — so the two cannot
# collide however they are ordered.
_SHIPPING_STAMPS_RE = re.compile(r"^/shipping/batches/([A-Za-z0-9]{1,64})/stamps$")
_SHIPPING_ITEM_RE = re.compile(r"^/shipping/batches/([A-Za-z0-9]{1,64})$")

# ------------------------------------------------------- the capture claims, on the wire
#
# `store/master.py:CAPTURE_CLAIM_FIELDS` names every field a capture writes onto a record.
# This maps each one to the name it wears on the wire and in the sidecar, and it is the
# third of the three restatements `docs/DEBTS.md` named — the other two now read the tuple
# directly. Only `variant` differs from its record field: `metadata_finish` is what the
# store calls it, `variant` is what the sidecar and the request body have always called it,
# and renaming either would break a file `identify.sidecar` already reads.
CLAIM_WIRE_NAMES = {
    "set_hint": "set_hint",
    # D3 rung 1's finish claim, and SINCE 2026-08-23 A JSON LIST of the game's finishes —
    # the second set-valued claim in this map, not the only one. The key does not move: the
    # sidecar and the request body have called it `variant` since before it had a shape, and
    # `identify/sidecar.py` reads that spelling off files already on disk.
    #
    # A BARE STRING IS STILL READ, and it is what all 682 records written before the
    # amendment carry: one member, and D3 says nothing writes one any more. There is no
    # migration, so both shapes travel this wire permanently.
    "metadata_finish": "variant",
    "game": "game",
    # D23's multi-select stack claim: a JSON list of the game's exact `Rarity` cells.
    # `sidecar_payload`'s truthiness filter means an empty list is never written — absent
    # is no claim, exactly as `variant` and `set_hint` behave, and now for the same reason
    # rather than by coincidence: both claims are sets and an empty set is no claim (D3, D23).
    "rarity_claim": "rarity_claim",
    # C10's product claim. Same spelling on the wire, in the sidecar and on the record —
    # unlike `metadata_finish`/`variant` above, which differ only because that key was named
    # before it had a shape and files on disk already use it. A field on its first day gets
    # one name everywhere.
    "product": "product",
    "note": "note",
}

# The claims no client sends, so they are legitimately absent from the map above rather than
# forgotten. `photo` is derived — the path is not knowable until the index is allocated.
DERIVED_CLAIMS = ("photo",)

_unbound = [
    name
    for name in master.CAPTURE_CLAIM_FIELDS
    if name not in CLAIM_WIRE_NAMES and name not in DERIVED_CLAIMS
]
if _unbound:  # pragma: no cover - import-time contract, not a branch under test
    raise RuntimeError(
        "server/capture_server.py:CLAIM_WIRE_NAMES has no wire name for "
        + ", ".join(repr(name) for name in _unbound)
        + ", which store/master.py names in CAPTURE_CLAIM_FIELDS. Give it one, or add it to "
        "DERIVED_CLAIMS if no client ever sends it — a claim with neither reaches the record "
        "and never the sidecar, and `cli/cmd_identify.py` builds its card from the sidecar."
    )

# Fields a PUT may change. Every settable capture claim, DERIVED rather than listed, so a
# claim added to the store is correctable the same day it is capturable. That is the right
# default and not an accident of the derivation: this route exists precisely to correct a
# claim the operator got wrong, and a claim that could be recorded but never fixed would be
# the one thing worse than not having it. Nothing about listing state is settable here —
# those transitions belong to identify, join and emit, and `_reject_unknown` refuses them.
PUT_FIELDS = tuple(
    CLAIM_WIRE_NAMES[name]
    for name in master.CAPTURE_CLAIM_FIELDS
    if name in CLAIM_WIRE_NAMES
)

# What a review answer carries. The first two are copied verbatim off ONE candidate row the
# pipeline already offered — see `do_review_answer` for why the pair is checked against that
# row rather than trusted, and for why `condition` is required at all when the SKU implies it.
#
# `undo` IS THE THIRD, AND IT MAKES THIS ROUTE THE SECOND ONE IN THIS FILE THAT GOES BOTH WAYS
# (D28). Same shape as `SOLD_FIELDS` below and for the same reason: the reversal is one control
# on screen with one window, and a separate `/unanswer` path would let a client reach the
# reversal without ever having been told what it reverses. It is deliberately NOT a second
# route for the further reason that the app then reads one field to learn which way a call
# went, rather than comparing a card's SKU against a queue file to work it out.
ANSWER_FIELDS = ("sku", "condition", "undo", "from_catalog")

# ...and what the reversal carries, which is the flag alone. Two tuples rather than one,
# because a body carrying `undo` AND a SKU is a client that has confused the two directions,
# and the SKU it sent would be ignored — silently writing nothing where it believed it was
# writing an answer. `_reject_unknown` names what is settable, so the refusal reads as an
# instruction rather than as a rejection of a field this route has obviously heard of.
UNDO_FIELDS = ("undo",)

# What the group answer carries: the list, alone (docs/DECISIONS.md, "A homogeneous queue
# may be answered as a group" — the entry that reopens D4's one-card-at-a-time, narrowly).
# `undo` is deliberately NOT here. The group's reversal is the single undo looped over its
# positions by the screen holding the receipt, so a partial reversal reports per position
# rather than pretending a group has one outcome — see `do_review_group_answer` for why the
# write is all-or-nothing while the reversal is per-card.
GROUP_ANSWER_FIELDS = ("answers",)

# D37's stand-down: the reason alone in one direction, the flag alone in the other. Two
# tuples for `ANSWER_FIELDS`' reason — a body carrying `undo` AND a reason is a client that
# has confused the directions, and the reason would be silently ignored.
STAND_DOWN_FIELDS = ("reason", "undo")

# ...and what each of its elements may carry: the single route's own pair, plus the position
# it is for. The pair is copied off that entry's ONE offered row and re-validated against it,
# never trusted — `_answer_target` runs the same checks for both routes, so the group cannot
# accept a pair the single route would refuse.
GROUP_ANSWER_ENTRY_FIELDS = ("box", "index", "sku", "condition")

# Mark-sold's whole body. The sale itself needs nothing: the position is in the path and the
# state is a constant, so `{}` sells and `{"undo": true}` reverses. One route rather than a
# second `/unsold` path, because the two are one control on screen with one undo window
# (docs/DESIGN.md: undo present on every mark-sold, at least 10 seconds), and splitting them
# would let a client reach the reversal without ever having been told what it reverses.
SOLD_FIELDS = ("undo",)

# The retirement's whole body (D26). The recording direction carries `reason` — required,
# one of `master.RETIRE_REASONS` — and `{"undo": true}` reverses. One route rather than a
# second `/unretire` path, for `SOLD_FIELDS`'s reason: the two are one control on screen
# with one undo window. A body carrying `undo` AND a reason is a client that has confused
# the two directions, and the route refuses it against `UNDO_FIELDS` exactly as the review
# answer does — the reason it sent would otherwise be silently ignored.
RETIRE_FIELDS = ("reason", "undo")

# The re-shoot's whole body (D26): the new photograph, and its own capture_id. No claims —
# the sidecar is rebuilt from the RECORD, so a re-shoot cannot smuggle in a correction that
# should have gone through the PUT route and its `corrected` history line.
RESHOOT_FIELDS = ("image", "capture_id")

# The mid-box delete's whole body (D10, ruling 1): the TARGET's `capture_id`, required as a
# key and nullable as a value — send the id the inventory row carries, or null for a record
# that predates ids. It is an aim check, not an idempotency token like capture's: the shift
# moves a different physical card INTO the deleted index, so a replay of a lost response, or
# a screen holding a stale read of the box, would otherwise delete the neighbour that slid
# in. `capture_id_mismatch` refuses both with the same instruction — re-read, then aim
# again. The one target this cannot protect is a record with no id at all whose upstairs
# neighbour also has none; both are pre-server records, and the limit is named at the check.
REMOVE_FIELDS = ("capture_id",)

# One card's move (D83). `capture_id` is the SAME aim check `REMOVE_FIELDS` above takes and
# for the identical reason: `move_card` is not idempotent — a replayed request after a lost
# response must not move whatever card now happens to sit at this key, which after a first
# successful move is nothing at all (the key is a tombstone). `to_box` is the one thing this
# body adds that a delete does not need: a destination.
MOVE_FIELDS = ("capture_id", "to_box")

# The batched move (D83): a list of indices IN THIS BOX, or `null` for every on-hand one —
# the shape that makes a whole-box move (merge, from the caller's side) the same request as
# a ticked selection, with no second field to mean "everything". `to_box` is required either
# way; there is no such thing as moving nowhere.
MOVE_CARDS_FIELDS = ("indices", "to_box")

# What `POST /boxes/<box>/listings/release` accepts. `confirm` is required and must be
# exactly `true` — D33's field, reused rather than reinvented, and required for its reason:
# this route asserts a fact about a system this process cannot see, so a request that did
# not say so deliberately must not be able to make the assertion by accident.
RELEASE_FIELDS = ("confirm",)
# D89's reclaim takes the same one field, for the same reason: the route's whole content is
# a person's decision that these photographs are disposable, and a request that did not say
# so on purpose must not make it by accident.
RECLAIM_FIELDS = ("confirm",)

# `PUT /inventory/<box>` accepts the claims plus ONE non-claim field. `indices` narrows the
# sweep from "every eligible card in the box" to the ones the operator actually selected —
# the owner's mass-select, 2026-08-23.
#
# ON THE ROUTE RATHER THAN AS N CARD CALLS, and that is the whole argument for it. A client
# loop over `PUT /inventory/<box>/<index>` would be N requests with N chances to half-apply:
# the seventh refuses on a per-game vocabulary and the first six are already written, which
# is the partial bulk correction this route's all-or-nothing exists to prevent (D29's shape).
# One call keeps one validate-everything-then-write-everything block and one lock.
BOX_CLAIM_FIELDS = PUT_FIELDS + ("indices",)

# What POST /boxes accepts. Only `box` is required: D20 makes capacity retroactive and a
# name optional, so the minimum useful creation is a number and nothing else. `sections` is
# here rather than PUT-only because a box whose dividers are already in the physical box has
# no reason to be declared in two requests.
BOX_POST_FIELDS = ("box", "name", "sections")

# What PUT /boxes/<box> may change. `box` is deliberately absent — it is in the path, and a
# body that could rename a box NUMBER would be a renumber, which D10 forbids outright: every
# position key in `inventory.json`, every photo directory and every printed label is built
# from it.
BOX_PUT_FIELDS = ("name", "sections", "state", "section_names")

# ----------------------------------------------------------- the order screen, on the wire
#
# THESE SIX TUPLES ARE THE PII BACKSTOP AND THAT IS WHY THEY ARE THIS NARROW (D63, D66). An
# order feed carries a buyer's name and a shipping address, and this repo has no use for
# either: `server/order_transport.py` projects them away where it parses them, and a paste
# arriving from a screen has had no such pass made over it. `_reject_unknown` is called FIRST
# at every level of the ingest body — before a source is read, before an order is looked up —
# so an unprojected paste REFUSES BY NAME rather than being stored with the buyer's fields
# quietly trimmed. A trim is silent; a refusal names `buyer` and sends the caller back to
# project. That difference is the whole argument for an allowlist over a filter.
ORDER_INGEST_FIELDS = ("orders",)
ORDER_INGEST_ORDER_FIELDS = ("source", "number", "placed_at", "status", "lines")
ORDER_INGEST_LINE_FIELDS = (
    "sku",
    "quantity",
    "name",
    "number",
    "printing",
    "condition",
    "rarity",
    "unit_price",
    "kind",
)

# What `POST /orders/fetch` accepts: the search range, the preview flag, the statuses to detail
# and the delta flag (D91) — and NOT the page size or the ceiling. Every knob
# `server/order_transport.py` takes beyond these is a rate limit rather than a preference, and a
# route that let a client raise either would put this account's request budget in the hands of
# whatever page was open. `statuses` is the operator's tick list over the strings the preview
# returned; it is the one filter this route applies, and it is never a vocabulary of its own.
ORDER_FETCH_FIELDS = ("range", "preview", "statuses", "skip_known")

# A fetch names the statuses to detail. The preview answers a handful — the API's own words for
# an order's state — so a list past this is a client sending something other than what it ticked.
ORDER_FETCH_STATUS_LIMIT = 50

# What `POST /orders/pull` carries in each direction. TWO TUPLES, `ANSWER_FIELDS`'
# convention exactly: a body carrying `undo` AND an order key is a client that has confused
# the directions, and obeying it with the order ignored would reverse a pull the caller
# believed it was recording.
ORDER_PULL_FIELDS = ("source", "number", "sku", "targets", "undo")
ORDER_PULL_UNDO_FIELDS = ("undo", "targets")
ORDER_PULL_TARGET_FIELDS = ("box", "index", "capture_id")

# What `POST /orders/fill` and `POST /orders/line-kind` carry. The fill takes two tuples for
# `ORDER_PULL_FIELDS`' reason — a body carrying `undo` AND a reason is a client that has
# confused the directions, and a reversal does not need one.
ORDER_FILL_FIELDS = ("source", "number", "sku", "count", "reason")
ORDER_FILL_UNDO_FIELDS = ("source", "number", "sku", "count", "undo")
ORDER_LINE_KIND_FIELDS = ("source", "number", "sku", "kind")

# `POST /orders/close` stands whole orders down. Two tuples, `ORDER_PULL_FIELDS`' rule.
# TWO SCOPES, ONE OPERATION, AND THEY ARE MUTUALLY EXCLUSIVE. `orders` stands every line of the
# orders it names down; `lines` stands exactly the lines it names down and leaves their siblings
# alone. Both call `Ledger.close_line` — only the scope differs — so a second route would be two
# spellings of one write. A body carrying BOTH is a client that has not decided, and obeying it
# with one silently ignored is how a refunded line takes its siblings with it.
ORDER_CLOSE_FIELDS = ("orders", "reason")
ORDER_CLOSE_UNDO_FIELDS = ("orders", "undo")
ORDER_CLOSE_LINE_FIELDS = ("lines", "reason")
ORDER_CLOSE_LINE_UNDO_FIELDS = ("lines", "undo")

# A backlog ceiling. The owner's store had 69 orders needing this in one press on the day it
# was built, so a limit under that would have made the feature useless on its own first use;
# one that admits a whole exported history would take the store lock for the length of it.
ORDER_CLOSE_LIMIT = 200

# One press is one line's shortfall. A hand-fill has no `capture_id` to collide, so nothing
# below it can catch a runaway count but `OverFulfilled` and this — and `OverFulfilled` is
# bounded by the ORDER, which a fat-fingered paste could legitimately be under.
ORDER_FILL_LIMIT = 50

# A paste ceiling, not a page size. Two hundred orders is far past any day's work and well
# short of a whole exported history, which is the accident this guards: one paste of
# everything the marketplace ever sold would take the store lock for the length of it.
ORDER_INGEST_LIMIT = 200

# One press is one operator's armful of cards. Fifty is generous for that and refuses the
# script that meant to send the whole box.
ORDER_PULL_TARGET_LIMIT = 50

# The feed a fetched order is recorded under. `store/orders.py:order_key` folds case to
# compare and stores what it was given, so this is the spelling that reaches a screen.
ORDER_FETCH_SOURCE = "TCGplayer"

# States at which a card may still be undone — `captured` ALONE, since the owner's ruling
# of 2026-08-23 (D10, ruling 2). This tuple held `identified` from the day the route landed,
# on the argument that the model had answered, the fee was already spent, and nothing
# outside this Mac knew the card existed. The ruling reverses it: once a card has been
# identified it has made it into inventory proper, and the capture screen's rapid-fire undo
# may not reach it. An identified card's remedies are the ones built for it — re-shoot
# (`POST .../photo`, D26) for a bad photograph, retire (`POST .../retire`, D26) for a card
# that has left, and the mid-box delete (`POST .../remove`, D10 ruling 1) for a junk record,
# where its bounds allow — and `undo_too_late` names all three, because a refusal that does
# not say what would have worked costs a round trip.
#
# Still written as the ALLOWED set rather than the refused one, which is not a style choice:
# a state added to `store.master.STATES` later is refused by default. The inverse would
# silently permit whatever comes next. `retired` (D26) is the state that proved the point:
# it arrived, and undo refused it with no edit here. It MUST NOT be added — undo is a hard
# delete that releases the index back to the allocator, and a retired card's gap is
# permanent by definition; deleting the record would erase the departure and hand its
# position to the next capture. The reversal of a retirement is `{"undo": true}` on its own
# route, a state transition backwards like the sale's, never a delete.
#
# `_listing_hold` STAYS ON THE UNDO ROUTE, AND RULING 2 MADE IT NEARLY UNREACHABLE THERE
# RATHER THAN WRONG. It exists because D10 draws a second line at `emit`: after it, a file
# on disk — and then TCGplayer — would disagree with the inventory. A card with a SKU to
# hold is a card something identified, which this narrowed tuple now refuses one check
# earlier — so the hold fires on the undo route only for a record whose `sku` arrived
# outside the ordinary path. It is kept anyway: a guard on a destructive operation is
# priced by what it prevents, not by how often it runs, and `do_remove_card` reaches the
# same helper for the identified cards that route CAN delete.
UNDOABLE_STATES = (master.CAPTURED,)

# What this server appends to `history.jsonl` for a write that moves no card between states.
# `store/master.py:_log` is reached from `record_capture` and `set_state` alone, and every
# event either of them has ever written is a member of `master.STATES` — so the three routes
# named below wrote nothing at all until 2026-08-13, and each said so in a comment citing
# `docs/DEBTS.md`. The argument for each line is at its own route; what is common to all
# three is that they change a claim the pipeline will act on and spend money against, and
# that the file they change is overwritten in place.
#
# NONE OF THESE IS A STATE, AND WHAT ENFORCES THAT IS THEIR ABSENCE FROM `master.STATES`.
# `_state_before_sale` — one of the TWO scanners of the history, the other being
# `_state_before_retirement` — scans backwards for the last event naming a state and filters
# against that tuple, so a name added here is inert to BOTH by construction. This said "the
# only reader of `history.jsonl` in this repo" until 2026-09-05, and it was wrong twice over:
# the twin scanner arrived with D26 and `_state_before_sale` does not read the history at all,
# it is handed a sequence. The readers are `_answer_origin`, `_origin` and
# `_reverse_stand_down`. The invariant is unchanged; what was wrong was the count a later
# session would have reasoned from. A name that collided would restore a reversed sale to
# `corrected`. T7 asserts the two sets are disjoint rather than leaving that to whoever adds
# the next event — WHICH IS WHY THE ROSTER IS NOT COUNTED IN PROSE ANY MORE. The ordinals
# below number the route-written names in the order they arrived, and the tuple at the foot of
# this block is the register; a restated total is the thing that goes stale, and this block has
# said 'four' about a group of five before.
#
#   corrected   an operator changed a recorded claim: the set hint or the finish toggle (D3).
#   removed     undo deleted a record and released its position for the next capture (D10).
#   answered    a human chose one catalog row for a card the pipeline refused to guess (D4).
#   stood_down  a human closed a queued question WITHOUT answering it, and the card was left
#               alone — no SKU, no state, no listing count (D37). The same line carries the
#               reversal, flagged rather than named separately.
#   unanswered  he took that answer back inside the undo window, and the card is waiting again
#               (D28).
#
# THE FOURTH IS THE REVERSAL OF THE THIRD, AND IT IS A LINE RATHER THAN A DELETION for the
# reason this whole tuple exists: `history.jsonl` is append-only and `store/__init__.py` calls
# it inventory truth over time. Without it the log would say a SKU was written onto a real card
# and never say it was taken off, which is the one failure mode a log has — being believed. The
# name follows `removed`'s rule and not `undone`'s: it says what became true of the position,
# not which button was pressed.
#
# IT IS ALSO WHAT THE REVERSAL READS. `_answer_origin` scans backwards for the newest `answered`
# line at a position and lifts the pair the card carried BEFORE that answer out of it, which is
# how a request arriving twenty seconds later knows what to put back — the card itself no longer
# holds it. `unanswered` is inert to that scan by name and is not consulted by it; what stops a
# withdrawn answer from being restored twice is the queue entry, which is open again and refuses
# as `not_answered`.
CORRECTED = "corrected"
REMOVED = "removed"
ANSWERED = "answered"
# D37. Outside `master.STATES` like every other event name here — T7 asserts that, and a
# stand-down is emphatically not a card state: the card does not move, does not change, and
# does not leave. Only the QUESTION closes.
STOOD_DOWN = "stood_down"
UNANSWERED = "unanswered"

# THE SIXTH ROUTE-WRITTEN EVENT (D26): the photo and sidecar at a position were replaced in
# place — record untouched, label unchanged, allocator never involved. The old photo is
# REPLACED, not archived, which D26 states outright; this line is therefore the only trace
# the first photograph ever existed, and it carries both capture ids so the boundary between
# the two photographs is in the log the way `removed` is the boundary between two cards at
# one reused index. Not a state, exactly as the five above are not: the card is the same
# card in the same state, and only its picture changed. `retired`, by contrast, IS a state —
# it lives in `master.STATES`, is logged by `Inventory.retire` through the store's own
# `_log`, and is deliberately NOT in this tuple: putting it here too would be the exact name
# collision D26 renamed the state to avoid.
RESHOT = "reshot"

# THE SEVENTH AND EIGHTH ROUTE-WRITTEN EVENTS (D10's three owner rulings, 2026-08-23).
#
#   renumbered   a mid-box delete slid every higher card in one box down one index. Carries
#                the deleted position, the box, `from` (the deleted index) and `count` —
#                and that IS the whole old->new mapping, stated compactly: the shift is
#                always minus-one for every index above `from`, `count` of them. This is
#                the only event in this file that moves position KEYS, and it exists for
#                `removed`'s argument read forward: without it the log says 3/9 was
#                captured and never says the card now AT 3/9 arrived there from 3/10, so
#                every earlier line about 3/9 silently changes subject. Appended only when
#                at least one record actually moved — a remove at the top of a box deletes
#                and shifts nothing, and an event describing zero renumbers would be a line
#                that marks nothing among the lines that mark the change somebody is
#                looking for. Not a state: nothing about any one card changed but its
#                address, and the card that changed STATE got its own `removed` line in the
#                same commit.
#   box_deleted  a whole box left the store (D10, ruling 3, amended D134): records, photos,
#                sidecars, queue entries, cache entries and the registry entry, in one
#                write. Carries the box, the card count and the buried count. A box-level
#                event like D20's five, so it is the first line `_history` writes with no
#                `position` key — a box is not at a position, and `Inventory._log` draws
#                the same line.
RENUMBERED = "renumbered"
BOX_DELETED = "box_deleted"

# THE TENTH ROUTE-WRITTEN EVENT (D134, 2026-09-11). `box_deleted` used to be refused
# outright while any card in the box was sold, retired or moved — ruling 3's "history and
# commitments, not clutter". D134 keeps that sentence and gives it a different answer: the
# record IS the history, and it survives the box by being buried here rather than by the
# box standing undeletable forever. ONE LINE PER DEPARTED RECORD, WITH A `position` KEY —
# unlike `box_deleted`'s summary, this is the retained record itself and not a duplicate of
# one, so it carries the record whole rather than a count. `#/graveyard` reads these lines
# merged with the sold/retired/moved records still standing in boxes nobody has deleted.
BURIED = "buried"

# THE NINTH ROUTE-WRITTEN EVENT (D34): the operator stated that TCGplayer holds nothing for
# the SKUs a box's cards belong to, and every listing stage on them was zeroed. Box-level
# like `box_deleted`, so it carries no `position` — the write is per SKU and the box is only
# how the operator got there, which is why the line carries the SKU count and the copies
# given up rather than a list of positions.
#
# IT IS THE ONLY TRACE, and that is the whole argument for logging it at all. The counts it
# zeroes were the store's record of what TCGplayer was holding; after this line there is no
# other evidence they ever stood, and a box deleted immediately afterwards takes the cards
# that would have implied them. Not a state, for the ordinary reason: no card moved, and
# `pushed`/`staged`/`live` are not members of `master.STATES` in the first place.
LISTINGS_RELEASED = "listings_released"

# D20's five, and they differ from the route-written names above in WHO APPENDS THEM. Those are
# written here, by `_history`, because the store has no opinion about them. These five are
# written by `store/master.py:Inventory._log` from inside `set_sections`, `ensure_box`,
# `set_name`, `close_box` and `reopen_box` — the box routes below call those methods and
# append nothing themselves. They are named here anyway, and the reason is the paragraph below: this tuple
# is what the disjointness rule is stated over, and an event this server causes but does not
# spell would be outside it.
#
#   resectioned   a box's divider layout was declared or edited. Carries both layouts,
#                 because D10 (amended) lets an edit relabel every card behind the moved
#                 divider without touching one index — correct when the layout was wrong,
#                 and silent when the edit was.
#   box_created   a box entered the registry: by POST /boxes, or by `ensure_box` when a
#                 capture landed in a box nobody had registered.
#   box_renamed   a box's name was set, changed or cleared. Carries both names, and it is
#                 `resectioned`'s sibling one scale up: a name is how a box is addressed
#                 now, so a rename relabels every card IN the box the way a moved divider
#                 relabels every card behind it. `do_put_box` recorded the absence of this
#                 event as a known gap while a name was only a label; it is not only a
#                 label any more.
#   box_closed    the lid went on and capacity froze at the fill (D20).
#   box_reopened  the lid came off and capacity went back to unknown, rather than standing
#                 as a stale fact.
RESECTIONED = "resectioned"
BOX_CREATED = "box_created"
BOX_RENAMED = "box_renamed"
BOX_CLOSED = "box_closed"
BOX_REOPENED = "box_reopened"

# ASSERTION, stated here and worth a T7 case: NOT ONE OF THESE NAMES IS A MEMBER OF
# `master.STATES`, which is `(captured, identified, sold)`. Nothing enforces that at import
# time and nothing should — the check that matters is a test, because the failure is silent.
# `_state_before_sale` and its twin `_state_before_retirement` scan backwards for the last
# event naming a state; both filter against `master.STATES` precisely so that a name in this
# tuple is inert to them. (This claimed a single reader until 2026-09-05 — see the correction
# at the sibling comment above.) A collision would restore a reversed sale to
# `resectioned`.
#
# The five D20 names are a MIRROR of literals that live inside `store/master.py:_log` calls
# rather than constants imported from it, because that module exports none — so this tuple
# can drift from the strings actually written, and only a test comparing the two would
# notice. Recorded rather than worked around: naming them in `store/master.py` is the fix,
# and it is not this file's to make.
SERVER_EVENTS = (
    CORRECTED,
    REMOVED,
    ANSWERED,
    # D37's stand-down, in BOTH directions — the close and its reversal write this one name,
    # distinguished by the payload rather than by a second event. It was defined beside
    # `ANSWERED` and left out of this tuple, which is a gap in the registry rather than a live
    # defect: `_state_before_sale` filters POSITIVELY against `master.STATES`, so an unlisted
    # name was skipped there anyway. What the omission actually cost is the assertion — T7
    # checks this tuple against `master.STATES`, so `stood_down` was the one route-written
    # event nothing proved could never be read as a state.
    STOOD_DOWN,
    UNANSWERED,
    RESHOT,
    RENUMBERED,
    BOX_DELETED,
    BURIED,
    LISTINGS_RELEASED,
    RESECTIONED,
    BOX_CREATED,
    BOX_RENAMED,
    BOX_CLOSED,
    BOX_REOPENED,
)


class BadRequest(ValueError):
    """A request this server refuses, carrying the status and code to answer with."""

    def __init__(self, status: HTTPStatus, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


# --------------------------------------------------------------------------------- paths


def captures_root() -> Path:
    """Where card photos live. Moves with `PKMNSCAN_HOME`, as the rest of the store does."""
    return files.home() / CAPTURES_DIRNAME / CARDS_DIRNAME


def photo_path(box: int, index: int) -> Path:
    """`<root>/box3/0017.jpg`.

    The stem is the index and nothing else. `identify.sidecar` strips the box marker and
    then reads the LAST run of digits in what remains, so a stem like `0017.2` parses as
    index 2. Zero-padded to four because `scan()` sorts by path string.
    """
    return captures_root() / f"box{int(box)}" / f"{int(index):0{INDEX_PAD}d}{PHOTO_SUFFIX}"


def sidecar_path(photo: Path) -> Path:
    return photo.with_suffix(SIDECAR_SUFFIX)


def sidecar_payload(box: int, index: int, **claims) -> dict:
    """What `identify.sidecar.load` reads back.

    `**claims` ARE RECORD FIELD NAMES, translated to their wire spelling by
    `CLAIM_WIRE_NAMES` on the way out — so `metadata_finish=` here writes `"variant"` in the
    file, which is the key the reader has always looked for. Written this way rather than as
    named parameters because this is the third place the claim list used to be restated by
    hand, and the one furthest from where a missing claim would be noticed: a claim that
    reaches `inventory.json` and not the sidecar is invisible until an identify run reads
    the sidecar and takes D3 rung 2 as though no toggle had ever been set.

    Keys are chosen against that reader, not invented here. `box` is read from `box` alone;
    the index is read from `index`, and note that `position` is an accepted ALIAS for the
    same integer — never write it. `store.master.position_key` returns the string "3/17"
    for what it calls a position, and a sidecar carrying `{"position": "3/17"}` fails the
    integer coercion, falls back to the filename, and — because a valid `box` is also
    present — is recorded as having come from its sidecar with no problem noted. That is
    undetectable in exactly the shape this server writes, which is why only `index` appears.

    A hint or a toggle the operator did not set is omitted rather than written null. The
    reader treats absent and null identically, so this costs nothing and keeps the file a
    record of claims actually made (D3 rung 1: the toggle is a claim, not a hint).
    """
    unknown = sorted(set(claims) - set(CLAIM_WIRE_NAMES))
    if unknown:
        raise BadRequest(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "claim_not_written",
            f"sidecar_payload was handed {', '.join(unknown)}, which has no wire name. "
            f"Sidecar claims: {', '.join(CLAIM_WIRE_NAMES)}.",
        )
    payload = {"box": int(box), "index": int(index)}
    for field, value in claims.items():
        if value:
            payload[CLAIM_WIRE_NAMES[field]] = value
    return payload


# ---------------------------------------------------------------------- request decoding


def _require_box(payload: dict) -> int:
    raw = payload.get("box")
    if raw is None:
        raise BadRequest(HTTPStatus.BAD_REQUEST, "box_required", "Send a box number.")
    try:
        box = int(raw)
    except (TypeError, ValueError):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, "box_invalid", f"box was {raw!r}; send a whole number."
        ) from None
    if box < 1:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, "box_invalid", f"box was {box}; boxes start at 1."
        )
    return box


def _require_image(payload: dict) -> bytes:
    raw = payload.get("image")
    if not raw:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, "image_required", "Send the photo as base64 in `image`."
        )
    try:
        blob = base64.b64decode(raw, validate=True)
    except (binascii.Error, TypeError, ValueError):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, "image_invalid", "`image` is not valid base64."
        ) from None
    if len(blob) > MAX_IMAGE_BYTES:
        raise BadRequest(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "image_too_large",
            f"{len(blob)} bytes exceeds the {MAX_IMAGE_BYTES} byte ceiling.",
        )
    if not blob.startswith(JPEG_MAGIC):
        raise BadRequest(
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            "image_not_jpeg",
            "Send JPEG bytes. The server stores what it is given and never converts.",
        )
    return blob


def _variant_shape(payload: dict) -> Optional[List[str]]:
    """The shape half of the finish claim: a SET of finish strings. No vocabulary.

    Split from the membership check below for the same reason `_rarity_claim_shape` is —
    `do_put_card` can know the shape before it takes the lock and cannot know the game
    until it is inside one. The split arrived late here, and the lateness IS the bug: a
    finish has a per-game vocabulary and this file spent its whole life believing there
    was one global one.

    D3 RUNG 1'S CLAIM IS A SET (amended 2026-08-23), so this returns a list where it used to
    return one string. It also used to COERCE — `str(raw).strip()` turned a JSON array into
    the literal `"['normal', 'holo']"`, which then failed membership as `variant_invalid`,
    so a set-valued claim could not be made over this wire at all.

    A BARE STRING IS ACCEPTED AND WRAPPED, which is the one deliberate divergence from
    `_rarity_claim_shape` directly below — that one REFUSES a bare string, on the stated
    grounds that a live caller can fix its own request. This caller cannot, and that is the
    whole difference: `app/src/server.ts` typed `variant` as one `Finish` from the day it was
    written, so every client in the tree sends a string today and refusing one would break
    every capture in the product on the first request. The rarity claim never had a
    single-valued past to be compatible with; this one does, on the wire and on 682 records.
    It is the same read-side backfill D21 uses for `game` and D3 names for this field, and
    it is permanent for the same reason: there is no migration.

    An absent key, `""` and `[]` are all NO CLAIM and all return `None`. `[]` mapping to
    `None` rather than to itself is load-bearing rather than tidy — see `_check_variant_members`
    for what an empty list does to `record_capture`.
    """
    raw = payload.get("variant")
    if raw is None or raw == "":
        return None
    if isinstance(raw, str):
        members = [raw]
    elif isinstance(raw, list):
        members = raw
    else:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "variant_invalid",
            f"variant was {type(raw).__name__}; send one of this game's finish strings, or "
            "a JSON list of them. GET /games serves each game's finishes.",
        )
    cleaned: List[str] = []
    for item in members:
        if not isinstance(item, str) or not item.strip():
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "variant_invalid",
                f"variant member {item!r} is not a finish string.",
            )
        text = item.strip()
        if text not in cleaned:  # deduped — claiming one finish twice claims it once
            cleaned.append(text)
    return cleaned or None


def _check_variant_members(
    claim: Optional[List[str]], game: Optional[str]
) -> Optional[List[str]]:
    """The membership half: every member must be a finish THIS GAME stocks.

    IT WAS CHECKED AGAINST `variant.FINISHES` FOR EVERY GAME, AND THAT REFUSED REAL
    CAPTURES. `pipeline/variant.py` defines `FINISHES` as literally `_POKEMON["finishes"]`,
    so every game's capture was gated through Pokemon's three. A Riftbound stack claimed
    `foil` — the finish its own registry entry authors, the finish the capture screen had
    just OFFERED because `finish_by_rarity["Rare"]` narrowed to it — was refused
    `variant_invalid` at the lens, in a message naming three finishes that game does not
    have. The claim could not be made from a control that was working correctly.

    The claim's vocabulary is the game's, exactly as D23 makes the rarity claim's the
    game's. That D21/D23 ordering rule — decode the game first, because the claim cannot
    be judged until the game is known — always covered this claim too; only the rarity
    claim was ever written to obey it.

    A `game` of None is a client older than the field, validated against
    `games.DEFAULT_GAME` — the game its record will be READ as (D21's read-side backfill).
    Validation only: nothing here writes a default game anywhere.

    `misc` authors no finishes at all, so any finish under it refuses. That is right rather
    than harsh — the capture screen draws no Finish field for a game with an empty enum, so
    a finish arriving under one did not come from the control.

    ONE BAD MEMBER REFUSES THE WHOLE CLAIM, never just itself, and every offender is named.
    `pipeline/variant.py` takes the identical line one layer down (`UnknownFinish` out of
    `_check_claim`, asserted by T4): a silently shortened claim is a claim the operator did
    not make, and a two-member claim quietly reduced to one stops filtering and starts
    DETERMINING — the strictly worse failure, since it resolves rather than reviews.

    IT ALSO CANONICALISES, and that is the half a caller cannot skip. Members come back
    deduped and in the GAME'S OWN ENUM ORDER rather than the order they were tapped, which
    is what `pipeline/variant.py:_check_claim` and `identify/sidecar.py:_check_variant` both
    already do — three normalisers, one canonical form. Ordering has to happen HERE and not
    in `_variant_shape`, because the order is the game's and only this half knows the game.
    Without it `["holo", "normal"]` and `["normal", "holo"]` are two values for one claim,
    and the diff loops in `do_put_card` and `do_put_box_claims` would log a `corrected`
    event and rewrite a sidecar for a PUT that corrected nothing — a whole box of them for
    a restated sweep, which is exactly what those routes' docstrings promise does not happen.

    AN EMPTY CLAIM IS `None` AND NEVER `[]`, which `_variant_shape` guarantees on the way in
    and this preserves. `store/master.py:record_capture` upserts every claim that is
    truthy, so `[]` and `None` both correctly leave an incumbent claim alone — but that
    store-side guard is the backstop, not the contract. The contract is that no route in
    this file ever hands the store an empty claim to interpret.
    """
    if claim is None:
        return None
    entry = games.get(game if game else games.DEFAULT_GAME)
    vocabulary = tuple(entry["finishes"])
    unknown = [member for member in claim if member not in vocabulary]
    if unknown:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "variant_invalid",
            f"variant {', '.join(repr(u) for u in unknown)} is not a finish of "
            f"{entry['display']}. Stocked: {', '.join(vocabulary) or '(no finishes)'}. "
            "GET /games serves the registry.",
        )
    return [finish for finish in vocabulary if finish in claim]


def _optional_variant(payload: dict, game: Optional[str]) -> Optional[List[str]]:
    """Shape and membership in one call, for the route that has the game in hand."""
    return _check_variant_members(_variant_shape(payload), game)


def _finish_claim_form(value) -> Optional[List[str]]:
    """A stored finish claim in the list shape, FOR COMPARISON ONLY — never for writing.

    D3 rung 1 says a bare string reads as a one-member set and there is no migration, so
    `Card.metadata_finish` genuinely holds both shapes and will for as long as the 682
    records written before 2026-08-23 do. Every one of them carries a string.

    That makes `getattr(card, "metadata_finish") != value` the wrong question for the two
    diff loops in this file. A card holding `"holo"` and a PUT restating `["holo"]` is a
    claim that did not move, and comparing raw would call it a change: a `corrected` event
    that corrects nothing, a rewritten sidecar, and — at the box route — a whole box
    reported as `applied` for a sweep that restated what it already said. Both routes
    promise the opposite in their own docstrings, and the promise is what this keeps.

    It is not used to WRITE. A no-op PUT leaves the stored string exactly as it is rather
    than converting it, because D3's read-side backfill means nothing downstream needs the
    conversion and a write with no logged change is the thing those loops exist to avoid.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


def _claim_moved(field: str, current, value) -> bool:
    """Whether a claim actually changed — the diff test both correction routes share.

    Only `metadata_finish` has two spellings of one value (see `_finish_claim_form`), so
    only it is canonicalised. `rarity_claim` is compared raw: it is list-valued too, but it
    has no single-valued past on disk, and the ONE way to write it — `_rarity_claim_shape`,
    which dedupes and keeps tap order — is the shape every record carries. Two tap orders of
    one rarity claim would diff as a change, which is a real but separate gap and is not
    something this change introduces or should quietly repair from the side.
    """
    if field == "metadata_finish":
        return _finish_claim_form(current) != _finish_claim_form(value)
    return current != value


def _optional_indices(payload: dict) -> Optional[set]:
    """`indices` on the box-claims route: which cards the sweep is narrowed to.

    ABSENT MEANS THE WHOLE BOX, and an EMPTY LIST REFUSES rather than meaning the same
    thing. They read alike and they are opposite intents: absent is "I did not select", and
    empty is "I selected and the selection is gone" — which under a whole-box default would
    silently sweep every card the operator had just narrowed away from. That is the shape of
    a real accident, so it gets its own refusal.

    Membership against the box's actual contents is NOT checked here; it is checked inside
    the lock with the records in hand, where an index naming no card can be reported by
    number alongside everything else the call refuses for.
    """
    if "indices" not in payload:
        return None
    raw = payload.get("indices")
    if not isinstance(raw, list):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "indices_invalid",
            f"indices was {type(raw).__name__}; send a JSON list of card numbers, or omit "
            "it to apply to every eligible card in the box.",
        )
    if not raw:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "indices_invalid",
            "indices was an empty list. Omit it to mean the whole box; an empty selection "
            "is not the same request and is refused rather than widened.",
        )
    chosen = set()
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, int) or item < 1:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "indices_invalid",
                f"indices member {item!r} is not a card number.",
            )
        chosen.add(int(item))
    return chosen


def _optional_game(payload: dict) -> Optional[str]:
    """A registered, processable game, or a refusal. Absent stays absent.

    TWO REFUSALS, BECAUSE THEY ARE TWO DIFFERENT ANSWERS and the remedies do not overlap:

      game_invalid      the string is not a game at all. A typo, or a client written against
                        a registry this server does not have.
      game_unverified   the game is registered and NOBODY HAS SEEN A TCGPLAYER EXPORT FOR IT
                        (D22), so it has no `Product Line` and no rarities. Capturing into one
                        would write records no join can ever resolve, so the honest answer is
                        to stop here and say why. No entry carries the flag as of 2026-08-23 —
                        `riftbound` and `one_piece` had it until their exports arrived — and
                        the branch stays because the flag is what an entry is BORN with.

    `unverified` IS THE TEST, AND `catalogued` IS DELIBERATELY NOT. That is the whole of how a
    permanently-uncatalogued game is told apart from a not-yet-measured one, and getting it
    backwards would break the commoner case. `games.require` refuses on BOTH — right for the
    join, where a game with no vocabulary has no export to join against — and wrong here,
    because `misc` is `catalogued: False` FOREVER, by the owner's ruling, and is a perfectly
    good thing to photograph: it is captured, located, and described in a free-text note. If
    this route refused on `require`, every misc capture would fail, and the one settled,
    correct state in the registry would read as an error on screen for good.

    ABSENT IS NOT REFUSED. D21 makes `game` required OF THE CLAIM — the picker always has an
    answer and always sends one — while a body without it is a client older than the field,
    and D21's own remedy for that is a read-side backfill, not a 400. Writing a default here
    would be the write-side default D21 forbids: "the operator said Pokemon" and "nobody was
    asked" would become the same bytes on disk.
    """
    raw = payload.get("game")
    if raw is None or raw == "":
        return None
    text = str(raw).strip().lower()
    try:
        entry = games.get(text)
    except games.UnknownGame:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "game_invalid",
            f"game was {raw!r}; use one of {', '.join(games.keys())}. "
            "GET /games serves the registry.",
        ) from None
    if entry["unverified"]:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "game_unverified",
            f"{entry['display']} has no TCGplayer export yet, so nothing captured under it "
            "could be identified, priced or listed. Obtain a Filtered CSV export for it and "
            "author its rarities in pipeline/games.py; until then, capture it as another "
            "game or leave it out of the box.",
        )
    return text


def _rarity_claim_shape(payload: dict) -> Optional[List[str]]:
    """The `rarity_claim` body field's SHAPE, checked without a vocabulary.

    Split from the membership check below because the two run at different moments in
    `do_put_card`: shape is knowable before the lock, membership needs the card's game and
    the card lives inside it. `do_capture` uses `_optional_rarity_claim`, which is both.

    A BARE STRING IS REFUSED, NOT WRAPPED, and the asymmetry with `identify/sidecar.py` is
    deliberate: that reader defends hand-written files that already exist on disk and can
    only be salvaged or dropped, while this refuses a live request whose author can fix it
    — the same posture as every other refusal in this file. Absent or an empty list is no
    claim at all: nothing lands on the record and `sidecar_payload` writes no key.
    """
    raw = payload.get("rarity_claim")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "rarity_claim_invalid",
            f"rarity_claim was {type(raw).__name__}; send a JSON list of this game's "
            "exact Rarity strings. GET /games serves each game's rarities.",
        )
    cleaned: List[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "rarity_claim_invalid",
                f"rarity_claim member {item!r} is not a rarity string.",
            )
        text = item.strip()
        if text not in cleaned:  # deduped, order kept — resending one twice claims it once
            cleaned.append(text)
    return cleaned or None


def _check_rarity_members(
    claim: Optional[List[str]], game: Optional[str]
) -> Optional[List[str]]:
    """The membership half: every member must be a rarity the game can claim.

    `game` IS READ BEFORE THE CLAIM WHEREVER THIS IS CALLED — the vocabulary is per-game,
    which is the ordering D23 makes load-bearing. A `game` of None is a client older than
    the field, and its record will be read as `games.DEFAULT_GAME` (D21's read-side
    backfill), so that is the vocabulary the claim is honest against. Validation only:
    nothing here writes a default game anywhere.

    Checked against `rarities` and deliberately not `rarities_not_claimed`: `Code Card` is
    a real Pokemon cell and never a stack claim (D22). `misc` declares no rarities at all,
    so any claim under it refuses here — there is no vocabulary to claim from.
    """
    if claim is None:
        return None
    entry = games.get(game if game else games.DEFAULT_GAME)
    vocabulary = tuple(entry["rarities"])
    unknown = [member for member in claim if member not in vocabulary]
    if unknown:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "rarity_claim_invalid",
            f"rarity_claim {', '.join(repr(u) for u in unknown)} is not a rarity of "
            f"{entry['display']}. Claimable: {', '.join(vocabulary) or '(none)'}. "
            "GET /games serves the registry.",
        )
    return claim


def _optional_rarity_claim(payload: dict, game: Optional[str]) -> Optional[List[str]]:
    """Shape and membership in one call, for the route that has the game in hand."""
    return _check_rarity_members(_rarity_claim_shape(payload), game)


def _optional_product(payload: dict) -> Optional[str]:
    """C10's product claim, checked against `codes/products.py`. Absent is no claim.

    NOT SCOPED TO THE GAME, unlike the finish and the rarity claim directly above. Those two
    are per-game vocabulary the registry authors (D22), so both need the game in hand. The
    product vocabulary belongs to the code-card track and there is one game that carries it;
    taking a game here would imply a per-game product list that does not exist.

    REFUSED RATHER THAN CARRIED, which is the opposite of what `identify/sidecar.py` does
    with the same value, and the difference is the direction of travel. The sidecar READS a
    file that already exists and must never drop what it cannot understand. This route is a
    WRITE from a client that has just been served the vocabulary by `GET /games` — so a
    product outside it is a client bug, and accepting it would put a value in the store that
    no screen can render and no channel export can tier.
    """
    text = _optional_text(payload, "product")
    if text is None:
        return None
    key = text.strip().lower()
    if key not in products.KEYS:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "product_invalid",
            f"product was {text!r}; use one of {', '.join(products.KEYS)}. "
            "GET /games serves the product vocabulary.",
        )
    return key


def _optional_text(payload: dict, key: str) -> Optional[str]:
    raw = payload.get(key)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _require_text(payload: dict, key: str, code: str, message: str) -> str:
    """A non-empty string, or a refusal in this route's own code."""
    text = _optional_text(payload, key)
    if text is None:
        raise BadRequest(HTTPStatus.BAD_REQUEST, code, message)
    return text


def _reject_unknown(payload: dict, allowed: Sequence[str]) -> None:
    """One code for "you named a field this route does not set", shared by three routes.

    Lifted out of `do_put_card`, which had it inline and had it FIRST — before the position
    is even looked up. That order is the point and is why this is shared rather than copied:
    a body carrying an unrecognised key is almost always a client written against a
    different route, and answering it with the position's own problem sends the reader off
    debugging the wrong thing. The message names what this route does accept, so the next
    request is the right one rather than another guess.
    """
    unknown = sorted(set(payload) - set(allowed))
    if unknown:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "field_not_settable",
            f"Cannot set {', '.join(unknown)} here. Settable: {', '.join(allowed)}.",
        )


def _optional_flag(payload: dict, key: str, code: str) -> bool:
    """A JSON boolean, or a refusal. Absent means False.

    NOT `bool(raw)`, and that is the whole reason this exists rather than a `.get`. The
    string `"false"` is truthy in Python, so a client that stringified its flag — the one
    mistake this shape invites — would reverse a sale while asking not to. A flag whose two
    values are "do it" and "undo it" is the last place to accept a value it had to guess at.
    """
    raw = payload.get(key)
    if raw is None:
        return False
    if not isinstance(raw, bool):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            code,
            f"{key} was {raw!r}; send the JSON literal true or false, not a string.",
        )
    return raw


def _optional_name(payload: dict) -> Optional[str]:
    """A box's name, or None. A non-string refuses rather than being stringified.

    `_optional_text` above coerces with `str()`, which is right for a set hint typed into a
    text field and wrong here: a client sending `{"name": {"en": "ME01 commons"}}` would get
    a box called `{'en': 'ME01 commons'}` and no indication anything went wrong. A name is
    the only human-readable thing a box carries and it is what the Boxes screen sorts and
    searches on, so a garbled one is worth a refusal.

    A NAME OF WHITESPACE IS NO NAME, not a refusal. `"   "` is the shape a text input
    produces when it is cleared, and clearing a name is a legitimate edit — it puts the box
    back to unnamed, which is what `ensure_box` creates in the first place.
    """
    raw = payload.get("name")
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "name_invalid",
            f"name was {raw!r}; send a string, or null to clear it.",
        )
    return raw.strip() or None


def _optional_sections(payload: dict) -> Optional[Tuple[int, ...]]:
    """A validated divider layout, or None when the request does not mention one.

    THE VALIDATION IS `master.check_sections` AND NOT A SECOND COPY OF IT. That function is
    where the rule lives — first divider at index 1, sorted, no repeats — and it refuses
    rather than repairing, deliberately, because a silently sorted layout relabels a box
    without saying so. All this adds is the wire-level guard `check_sections` cannot make:
    a JSON string is iterable, so `"1,31"` would reach it and come back as a complaint about
    the character `'1'` rather than about the type.

    AN EMPTY LIST IS LEGAL AND MEANS UNDECLARED (D10, amended). It is how a box says its
    dividers are wherever the default rule puts them, and it is what every box migrated from
    v1 carries — so `[]` un-declares a layout rather than being refused as empty.
    """
    raw = payload.get("sections")
    if raw is None:
        return None
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "sections_invalid",
            f"sections was {raw!r}; send a JSON array of the index each section starts at, "
            f"like [1, 31, 56]. Send [] to go back to the default divider size.",
        )
    try:
        return master.check_sections(raw)
    except master.BadSections as exc:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "sections_invalid",
            f"{exc}. Sections are the index each one STARTS at, so the first is 1 and the "
            f"list climbs without repeating: [1, 31, 56] is three dividers.",
        ) from None


def _optional_section_names(payload: dict) -> Optional[Dict[int, Optional[str]]]:
    """Section names by ORDINAL, or None when the body carries none. D132.

    THE BODY SPEAKS ORDINALS — `Section 6` is what every screen prints and what the operator
    types beside — and the store keeps the divider INDEX the section starts at
    (`Box.section_names`), so a moved divider keeps its name. `Inventory.set_section_names`
    is the one place the two are joined; this only checks the shape of what arrived.

    A blank or null value CLEARS that section's name, the same edit a cleared text field
    sends for `name`. A key that is not a section number refuses here; a number the layout
    does not reach refuses in the store as `section_unknown`.
    """
    raw = payload.get("section_names")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "section_names_invalid",
            f"section_names was {raw!r}; send an object keyed by section number, like "
            f'{{"2": "Rares"}}. A blank value clears the name.',
        )
    out: Dict[int, Optional[str]] = {}
    for key, value in raw.items():
        try:
            ordinal = int(str(key).strip())
        except (TypeError, ValueError):
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "section_names_invalid",
                f"section_names key {key!r} is not a section number.",
            ) from None
        if value is not None and not isinstance(value, str):
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "section_names_invalid",
                f"section {ordinal}'s name was {value!r}; a name is text.",
            )
        out[ordinal] = value
    return out


def _optional_box_state(payload: dict) -> Optional[str]:
    """`open` or `closed`, or None when the request does not mention the lid.

    Its own code rather than `field_not_settable`, because the field IS settable and the
    value is not one of the two. The message names both, since this is the control that
    freezes a box's capacity and a client guessing at `"sealed"` deserves better than a
    generic refusal.
    """
    raw = payload.get("state")
    if raw is None:
        return None
    if not isinstance(raw, str) or raw.strip() not in master.BOX_STATES:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "box_state_invalid",
            f"state was {raw!r}; send {' or '.join(master.BOX_STATES)}. Closing a box "
            f"freezes its capacity at the cards it holds; opening one puts capacity back "
            f"to unknown.",
        )
    return raw.strip()


def _require_query(query: str) -> str:
    """The search text, or a refusal. Whitespace is not a search.

    A blank `q` is refused rather than answered with every card in the store. The screen
    that calls this draws a row per copy with a photo behind each one, and "the operator
    cleared the box" is not a request for all of it — `store/queues.py` makes the same call
    for the same reason when it declines to treat an empty queue as a full one.
    """
    text = (query or "").strip()
    if not text:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "query_required",
            "Send `q` — a name, a collector number, a SKU or a set hint to look for.",
        )
    return text


# ------------------------------------------------------------------------------- history


def _history(inventory: master.Inventory, event: str, key: Optional[str], **extra) -> None:
    """Append one event to `history.jsonl`. Call it inside the caller's `Store.write()`.

    `key` MAY BE None FOR A BOX-LEVEL EVENT, and then `position` is dropped rather than
    written null — a box is not at a position, and a null one would read as a card whose
    position went missing. The rule and its wording are `Inventory._log`'s; `box_deleted`
    is the first event this file writes that needs it.

    THE APPEND GOES ONTO `Inventory.events`, WHICH IS WHY THE CALL SITE MATTERS. `Store.write()`
    drains that list after it has replaced the four JSON files, so the line and the change it
    describes commit together or neither does — and an exception anywhere in the block
    discards both, which `check_store` in T7 already asserts for a capture. Writing to
    `history.jsonl` from here directly would put a line in an append-only file for a change
    that a later raise in the same block throws away, and a log that disagrees with the store
    is worse than no log: it is believed.

    IT REBUILDS `Inventory._log`'s RECORD RATHER THAN CALLING IT, and both alternatives were
    worse. Reaching across the package for a private method makes a rename break a write path
    at runtime with nothing to catch it first. Giving `store/master.py` a public wrapper puts
    these three names beside the state vocabulary, which is the exact confusion
    `docs/DEBTS.md` was guarding against when it called an `undone` event a D10 question
    rather than a logging one — the store goes on logging states only, and the route that
    knows why a write happened names it. What that costs is a second copy of a three-key
    record, so T7 asserts the shape against a capture event the store wrote itself.

    NONE-VALUED EXTRAS ARE DROPPED, which is `_log`'s own convention and not a detail: an
    absent key reads as a fact nobody recorded, and `null` reads as a fact recorded as
    nothing. A before-value that IS None therefore travels nested inside a non-None mapping —
    see `do_put_card`, where the difference decides whether a cleared set hint is legible.
    """
    record = {"at": master.now(), "event": event}
    if key is not None:
        record["position"] = key
    record.update({key_: value for key_, value in extra.items() if value is not None})
    inventory.events.append(record)


# --------------------------------------------------------------------------------- place


# One box's walk, as `_Places._walk` caches it: the located non-terminal records ascending
# as `(index, name)`, the located terminal indices — D30's permanent holes — and the
# POSITIONS into the first tuple that carry a name, which is what D116's outward walk
# bisects rather than scans.
_Boxmates = Tuple[
    Tuple[Tuple[int, Optional[str]], ...],
    Tuple[int, ...],
    Tuple[int, ...],
]


class _Places:
    """Every `place` block in this server, and one box lookup per box rather than per card.

    D20's sentence is "#40 of 250 · 16% in", and every part of it after the 40 is a property
    of the BOX: its divider layout decides the section, its capacity or its fill is the
    denominator, and its name is what the operator actually calls the thing on the shelf.
    Four routes used to answer with `label`, `section` and `card` and nothing else, which
    left the app with a position and no way to say where in the box it sits.

    ONE RENDERER, INSTANTIATED PER REQUEST, and both halves of that matter.

      one renderer      `_card_summary`, `_card_row`, `do_inventory` and `do_search` all
                        call `.of()`. The alternative is four copies of a fraction and a
                        section-end fallback, which is the second-renderer failure
                        `do_inventory`'s own docstring already spent a paragraph on — there
                        it was TypeScript recomputing D10's arithmetic, and four Python
                        copies would be the same mistake with a shorter commute.
      per request       `Inventory.box_fill` is O(cards): it walks every record in the store
                        and coerces each one. Rendering 5,000 cards with an uncached
                        denominator is 25M coercions on the route the app POLLS. The cache
                        is per instance and an instance never outlives a request, so it
                        cannot serve a stale denominator to the next one — the same rule
                        this file's header sets for the server as a whole: no cache, no
                        dirty set, nothing authoritative held between requests.

    IT MAY RAISE, AND ITS CALLERS DECIDE WHAT THAT MEANS. `box_fill` raises `BadPosition` on
    a record whose box or index will not coerce, and `sections_for` raises `BadSections` on a
    hand-edited layout that never went through `set_sections`. Neither is caught here,
    because the right answer differs by route: `do_inventory` leaves that row undecorated
    (its docstring has why a placeholder label is worse than none), `do_boxes` reports the
    box without a layout, and the write routes let it reach the dispatcher — a capture into
    a box whose declared dividers cannot be read is refused rather than labelled by a rule
    that box no longer follows.

    A POOLED GAME'S CARD GETS A PLACE BLOCK WITH NO PLACE IN IT, and this renderer is where
    that is decided — one door, exactly as for the label itself. `pipeline/games.py`'s
    `located` flag is the owner's ruling that a code card is a count, not a location: the
    index stays as the KEY (the photo and sidecar are named after it, and the photo route
    needs `box` and `index` to serve them), but `label`, `section`, `card` and `fraction`
    all answer null and `located` answers false, with the game's key and display name
    beside them so a screen can say the pooled fact instead of drawing a gap. The block
    stays rather than disappearing because absence already means something else here — a
    record whose position will not coerce — and a design fact must not share a shape with
    a fault. THE SERVER KEEPS SERVING THE ROW EVERYWHERE: the owner's screens still need
    the count and the map, so nothing is filtered on this side — which view may show a
    pooled card is each view's own ruling, and the Fulfillment view's is asserted in
    `app/tests/fulfillment.spec.ts`.

    NEIGHBOURS AND THE SECTION'S GAP COUNT — D30's digital half. `Card 17` is the
    seventeenth SLOT, not the seventeenth card you can count, and once a section has holes
    (every sale and every retirement makes one, permanently — D10) the two stop being the
    same number and every label in the section becomes uncountable by hand. So a located
    block also says what makes the label countable again: `neighbors` — the nearest NAMED
    non-terminal record on either side in the same box, each as `{index, slot, name,
    skipped}`, null at the box's ends and null where nothing that way can be named — and
    `section_gaps`, how many indices inside this card's own section bounds hold a record
    that is sold or retired. Permanent gaps only: an unallocated tail index has no record
    and is not a gap, and counting terminal RECORDS is what makes that true by
    construction rather than by a bounds check.

    A CARD NOBODY HAS NAMED IS NOT A LANDMARK, WHICH IS D116. The walk passes over an
    unnamed on-hand card the way it passes over a departed one and keeps going, and
    `skipped` says how many it passed so the row can state the distance rather than
    quietly move a landmark. `_company` has the argument.

    THE DECORATION DEGRADES WHOLE, AND IT NEVER GUESSES. The walk that finds a neighbour
    is a scan over every record's own `box` and `index` — the same fields `box_fill`'s
    scan coerces, with the same failure mode: one record whose position will not read.
    Skipping such a record would keep the sentence rendering while possibly naming the
    wrong neighbour, and "between X and Y" is a claim somebody counts slots against, so a
    wrong one sends a hand to the wrong slot — the exact failure a position label may
    never cause. So one unreadable record costs every card in the store its `neighbors`
    and `section_gaps` (both null, the shape the app draws as no sentence) and costs
    nobody their label or their block — the same split the denominator comment below
    argues, applied to the decoration this class gained after it.
    """

    def __init__(self, inventory: master.Inventory):
        self._inventory = inventory
        self._cache: Dict[
            int, Tuple[Optional[master.Box], Tuple[int, ...], int, Optional[Tuple[int, ...]]]
        ] = {}
        # D30's walk, one scan per instance, lazily: box -> (occupants, gaps, named), where
        # `occupants` is every located, non-terminal record as (index, name) sorted by
        # index, `gaps` is the sorted indices of the located TERMINAL records — the
        # permanent holes — and `named` is the positions into `occupants` that carry a
        # name, which is D116's landmark set. `_boxmates` is None after the scan has met a record it cannot
        # read (the whole-store degrade the docstring argues); `_walked` says whether it
        # has run at all. Cached for the same reason `_cache` above is: this class is
        # instantiated per request, so `do_inventory` renders 5,000 rows against one walk
        # rather than 5,000.
        # PER BOX SINCE D88, and lazily: `Inventory.records_in` answers one box out of the
        # `cards` table without building the other boxes' records, which is what keeps a
        # capture's `_card_summary` from loading the whole store to label one card. The
        # degrade is still whole-store — `records_in` refuses on an unreadable record
        # ANYWHERE, exactly as the scan it replaces did — so `_degraded` is one flag and
        # not one per box.
        self._degraded = False
        self._boxmates: Dict[int, _Boxmates] = {}

    def view(self, box) -> Tuple[Optional[master.Box], Tuple[int, ...], int, Optional[Tuple[int, ...]]]:
        """`(registry entry or None, validated layout, denominator, on-hand indices)`.

        `occupied` is D58's counting space: every located, non-terminal index in this box,
        ascending — the cards a person opening it would count. It is `None`, not `()`, when
        the walk could not be made, and the two mean opposite things: an empty box has no
        cards to count and a degraded walk cannot count the cards it has.
        """
        number = int(box)
        cached = self._cache.get(number)
        if cached is None:
            entry = self._inventory.box(number)
            layout = self._inventory.sections_for(number)
            # THE DENOMINATOR IS THE WHOLE OF D20's LIFECYCLE, and it is `_denominator`
            # rather than two lines here because `GET /boxes` needs the same answer: a box
            # that said "40 of 250" on one screen and "40 of 53" on the other would be the
            # second-renderer failure with a number in it instead of a label.
            #
            # THE DENOMINATOR FAILS ALONE. `box_fill` is a whole-box scan and raises
            # `BadPosition` on ANY record IN THE STORE — `next_index` coerces every
            # record before filtering by box, so one corrupt record costs EVERY box its
            # denominator, not just its own. Measured by T7's degrade case; this comment
            # once said 'in the box' and understated it — so
            # letting it escape here cost every neighbour its label over one corrupt row, on
            # the route the app polls. T7 caught exactly that and it was right to: a label
            # needs only this record's own two integers and the box's layout, neither of
            # which the scan is involved in. Only "of 250" needs it.
            #
            # So the two degrade separately. A bad neighbour costs this box its denominator
            # — `box_total` 0 and `fraction` null, which the app already draws as "no
            # fraction" — and costs nobody their position. `BadSections` is NOT caught: a
            # layout that will not validate means the section and card numbers themselves
            # are unknown, and that is the one case where no label is the honest answer.
            #
            # THE DENOMINATOR IS THE CARDS ON HAND SINCE D58, AND `capacity` NO LONGER
            # FEEDS IT. Forced rather than chosen: the numerator is now a count of cards
            # (`Position.slot`), and a count of cards over a frozen capacity computes a
            # fraction that drifts further wrong with every sale — on a 543-card box that
            # has sold 200, `#100 of 543` would put a thumb a third of the way from where
            # the card is. `capacity` keeps its D20 job of recording how full the box got,
            # and `GET /boxes` still reports it; it is simply not what anything divides by.
            #
            # ONE WALK, BOTH RENDERERS. `_box_row` reads `occupied` from this same
            # instance, so the `place` block and the box row cannot come to disagree about
            # the denominator — the property `_denominator` used to buy by being one
            # function, now held structurally by being one scan.
            walked = self._walk(number)
            occupied = tuple(i for i, _ in walked[0]) if walked is not None else None
            total = len(occupied) if occupied is not None else 0
            cached = (entry, layout, int(total), occupied)
            self._cache[number] = cached
        return cached

    def total(self, box) -> int:
        return self.view(box)[2]

    def occupied(self, box) -> Optional[Tuple[int, ...]]:
        return self.view(box)[3]

    def game_entry(self, box, index) -> Optional[dict]:
        """The registry entry for the card at this position, or None when it cannot be known.

        Read off the record's own `game` claim (D21), with the read-side backfill applied
        here because this is a read: a record written before the field existed is a
        Pokemon card. None comes back for an unregistered game string, and the caller
        treats that as located — the loud stop for a typo'd game belongs to the pipeline
        (`join.lookup_for` refuses it by name), never to the route the app polls.
        """
        return self._game_of(self._inventory.cards.get(master.position_key(int(box), int(index))))

    def _game_of(self, card: Optional[master.Card]) -> Optional[dict]:
        """`game_entry`'s lookup for a record already in hand — one rule, two doors in."""
        claimed = getattr(card, "game", None) if card is not None else None
        try:
            return games.get(str(claimed) if claimed else games.DEFAULT_GAME)
        except games.UnknownGame:
            return None

    def _walk(self, box: int) -> Optional[_Boxmates]:
        """One box's `(occupants, gaps, named)` for D30's decoration, or None — degraded.

        The scan reads every record's own `box` and `index`, coerced the way the rest of
        this file coerces them (`int()` — a string-typed "3" counts, the regression T7
        keeps). A record either of whose positions will not read degrades the WHOLE
        decoration to None, for every box: the class docstring has the argument, and the
        precedent is `next_index`'s own rule that an unparsable record stops the scan
        rather than being skipped past. A pooled record is skipped by ruling, not by
        failure — it has no slot, so it is nobody's neighbour and no section's gap (D24).

        `named` IS THE POSITIONS INTO `occupants` THAT CARRY A NAME, and it exists so
        D116's outward walk is a bisect rather than a scan. Without it, the search for the
        nearest NAMED neighbour is O(box) per card in the one case that matters most: a box
        freshly off the feeder, where every card is unnamed until `join` has run, and where
        `do_inventory` would then be O(n²) over 723 records. It is positions and not
        indices because that is what both readers need — the slot is a position plus one,
        and the count of cards skipped is a difference of positions.
        """
        if self._degraded:
            return None
        number = int(box)
        cached = self._boxmates.get(number)
        if cached is not None:
            return cached
        rows: List[Tuple[int, Optional[str], bool]] = []
        try:
            for at, _, card in self._inventory.records_in(number):
                entry = self._game_of(card)
                if entry is not None and not entry["located"]:
                    continue
                name = card.name if isinstance(card.name, str) and card.name else None
                rows.append((at, name, card.state in master.TERMINAL_STATES))
        except (master.BadPosition, TypeError, ValueError):
            self._degraded = True
            self._boxmates = {}
            return None
        occupants = tuple((i, name) for i, name, gone in sorted(rows) if not gone)
        cached = (
            occupants,
            tuple(i for i, _, gone in sorted(rows) if gone),
            tuple(where for where, (_, name) in enumerate(occupants) if name is not None),
        )
        self._boxmates[number] = cached
        return cached

    def _company(
        self, box: int, at: int, start: int, end: Optional[int]
    ) -> Tuple[Optional[dict], Optional[int]]:
        """`(neighbors, section_gaps)` for one located card, both None when degraded.

        `neighbors` walks OUTWARD from `at` over the box's non-terminal records: the
        nearest NAMED card on each side, `{index, slot, name, skipped}`, null past either
        end of the box. A sold or retired record is passed over rather than named — a
        departed card cannot be the thing you count from, which is the whole reason D30
        wants the sentence.

        AND SO IS A CARD NOBODY HAS NAMED, WHICH IS D116 AND IS NEW. This used to stop at
        the nearest non-terminal record whatever it was, sending `name: null` for a card no
        identification ever produced a name for, and the app drew `#270` for it. That
        number is a real live card at a real count — the owner read it as a sold card
        leaking into the ladder, which it never was — but a bare figure names nothing you
        can recognise while flipping a box, which is the ladder's only job. So an unnamed
        on-hand card is now passed over as a LANDMARK, exactly as a departed one is, and
        the walk keeps going outward until it finds a card it can name.

        `skipped` IS WHAT KEEPS THAT HONEST, and it is why the skip is a count rather than
        a silence. D30 forbids a sentence that sends a hand to the wrong slot, and a
        landmark two cards away instead of one does exactly that unless the row says so.
        It is the number of on-hand cards passed over on that side — never the departed
        ones, which are not between anything: the box closed up over them (D58) and
        `section_gaps` is where they are counted.

        A SIDE WITH NO NAMED CARD BEYOND IT IS NULL, the same answer the box's own edge
        gives, and it is honest for the same reason: there is nothing over there this
        sentence can name. A box straight off the feeder — every card captured, none
        identified — therefore draws no ladder at all rather than a ladder of figures.

        BOTH NUMBERS, BECAUSE THE ROW DRAWS ONE AND A FUTURE CALLER WANTS THE OTHER (D92).
        `index` is the store key — `/inventory/<box>/<index>`, the `<index>.jpg` — and
        `slot` is D58's count, this neighbour's ordinal among the cards actually in the box.
        They are the same number only in a box nothing has left, and box 3 is 76 apart. The
        renderer draws `slot` and nothing may draw `index`: a bare `#` on these screens is a
        count, so the `#41` this decoration used to be rendered as named a card that is not
        the one a hand counting to 41 arrives at. `index` stays on the wire unread because
        D45 makes a copies list a way back into the walk, and a click target needs the key.

        THE SLOT IS THE ORDINAL AND IS NOT RECOMPUTED. `occupants` is already every on-hand
        index ascending — the same sequence `Position.occupied` bisects — so a neighbour's
        slot is its place in it. Deriving it any other way would be a second spelling of
        `Position.slot` in the one function that can see both.

        `section_gaps` counts the terminal records inside `[start, end]` — this card's
        own section bounds, exactly as the block states them. `end` is None only for a
        section with no end (the block's own fallback found no fill), and then the count
        runs to the top of the box, which is the same claim the block makes by answering
        `section_end: null`.
        """
        mates = self._walk(box)
        if mates is None:
            return None, None
        occupants, gaps, named = mates

        indices = [i for i, _ in occupants]
        before = bisect_left(indices, at) - 1
        after = bisect_right(indices, at)

        # `where + 1` IS THE SLOT: `occupants` is ascending and holds only cards on hand, so
        # a neighbour's ordinal in it is `Position.slot` by the same bisect that property
        # runs. `from_` is the position the search STARTED at, so the cards passed over are
        # the distance between the two — one subtraction, in the space both numbers live in,
        # rather than a second count of the same cards.
        def side(where: int, from_: int) -> dict:
            return {
                "index": occupants[where][0],
                "slot": where + 1,
                "name": occupants[where][1],
                "skipped": abs(where - from_),
            }

        # The outward walk, as two bisects into `named` rather than a scan over `occupants`
        # — see `_walk` for why: an unidentified box is the case where a scan is O(n²), and
        # it is the case a box has just after the feeder and before `join`.
        back = bisect_right(named, before) - 1
        prev_of = None if before < 0 or back < 0 else side(named[back], before)
        forward = bisect_left(named, after)
        next_of = (
            None
            if after >= len(occupants) or forward >= len(named)
            else side(named[forward], after)
        )

        low = bisect_left(gaps, start)
        high = len(gaps) if end is None else bisect_right(gaps, end)
        return {"prev": prev_of, "next": next_of}, max(0, high - low)

    def of(self, box, index) -> dict:
        """The `place` block for one position."""
        number = int(box)
        at = int(index)

        # The pooled branch, BEFORE the box view: a pooled card's block borrows nothing
        # from the box — no denominator, no layout, no name — so the whole-box scan is
        # work done to fill fields this block answers null for, and a corrupt neighbour
        # must not cost a pooled card its block over a denominator it does not carry.
        # The class docstring argues the shape; `box` and `index` stay because they are
        # the key and the photo route's arguments, not because they are a place.
        game = self.game_entry(number, at)
        if game is not None and not game["located"]:
            return {
                "located": False,
                "label": None,
                "box": number,
                "index": at,
                "slot": None,
                "section": None,
                "card": None,
                "box_name": None,
                "section_name": None,
                "section_start": None,
                "section_end": None,
                "box_total": 0,
                "box_closed": False,
                "fraction": None,
                # D30's decoration answers null with the rest of the place: a pooled card
                # has no slot to count from and no section to have gaps in. Null and not
                # zero for `section_gaps`, because zero would claim a countable section
                # with no holes, which is a different fact from "no section at all".
                "neighbors": None,
                "section_gaps": None,
                "game": str(game["key"]),
                "game_display": str(game["display"]),
            }

        entry, layout, total, occupied = self.view(number)
        section_names = self._inventory.section_names_for(number)

        # D58 — THE LABEL COUNTS THE CARDS IN THE BOX, and this is the one line that puts
        # it in that space. `occupied` is None only when the walk met a record it could not
        # read, and then there IS no honest label: the numbers are a count of cards, and
        # the cards could not be counted. Answering the index-space label instead would put
        # a second numbering system on the screen with nothing saying which one it is,
        # which is the failure this change exists to remove. Same call `BadSections` makes
        # four lines below in `view` — a layout that will not validate means the section
        # and card numbers are unknown, and no label is the honest answer.
        if occupied is None:
            return {
                "located": True,
                "label": None,
                "box": number,
                "index": at,
                "slot": None,
                "section": None,
                "card": None,
                "box_name": entry.name if entry is not None else None,
                "section_name": None,
                "section_start": None,
                "section_end": None,
                "box_total": 0,
                "box_closed": bool(entry.closed) if entry is not None else False,
                "neighbors": None,
                "section_gaps": None,
                "fraction": None,
            }

        position = join.Position(number, at, layout, occupied)
        slot = position.slot

        # `Position.section_end` IS None FOR THE FINAL DECLARED SECTION, on purpose: it runs
        # to wherever the box ends, and only the box knows where that is. This is the caller
        # its docstring means. `total or None` rather than a bare `total`, so a box holding
        # nothing answers "no end" instead of claiming its last section ends at card 0.
        #
        # AN UNDECLARED BOX NOW ALWAYS REACHES THIS BRANCH, and it used never to. It had a
        # 25-card window whatever the fill, so an open box with 5 cards said its first
        # section ended at card 25 — a boundary nobody had put in the plastic. D10's
        # amendment of 2026-08-29 deletes that rule: an undeclared box is ONE section, its
        # end is the box's end, and this is the line that fills it in. The consequence is
        # that `section_end` for such a box now degrades with the denominator rather than
        # standing on its own — which is correct and is asserted as such in T7. A number
        # derived from a count cannot survive the count being unreadable.
        end = position.section_end
        if end is None:
            end = total or None

        # D30's decoration is still read in INDEX space, and must be: `_company` bisects the
        # walk's own index lists to find the nearest cards either side, which is a question
        # about what is physically next to this one. `section_start`/`end` are now counts,
        # so they are mapped back to indices for it — `section_gaps` then counts the
        # departed records between the same two cards. It answers zero for a box where
        # nothing has left, and `placeSentence` already draws no gap phrase at zero, so the
        # sentence quietly stops carrying a clause that D58 made structurally empty.
        first = occupied[position.section_start - 1] if occupied else at
        last = occupied[end - 1] if (end is not None and 0 < end <= len(occupied)) else None
        neighbors, section_gaps = self._company(number, at, first, last)

        return {
            # True by construction on this path: the pooled branch above already answered
            # for every game whose flag says otherwise. Stamped so every client reads the
            # located question off one field in one block, old servers simply omitting it.
            "located": True,
            "label": position.label,
            "box": number,
            "index": at,
            # D58 — this card's number among the cards in the box, which is what every
            # rendered number on the screen counts in. `index` above it is the STORE KEY:
            # the route path, the photo filename and what every write aims by. They differ
            # by the number of departed cards in front of this one, and both are on the
            # wire because they answer different questions.
            "slot": slot,
            # THE CARD HAS NO NUMBER; ITS SECTION STILL EXISTS. A departed record belongs to
            # a real part of a real box — the one it sat in — and the walk groups by this, so
            # nulling it would file every sold card under a third heading that is not a
            # section. `Position.section` answers where its index falls, which is that fact.
            # What is null is `slot` and `card`: the NUMBERS, which now belong to the card
            # that closed up behind it.
            "section": position.section,
            "card": position.card,
            "box_name": entry.name if entry is not None else None,
            # D132 — the section's own name, joined at read time like the box's and for the
            # same reason: a run directory never holds one, so a rename reaches every label.
            "section_name": section_names.get(position.section),
            # Bounds of the SECTION rather than of the card, for the reason above: the walk
            # draws a section header from whichever row it meets first, and a departed one
            # must describe the same section its neighbours do.
            "section_start": position.section_start,
            "section_end": end,
            "box_total": total,
            "box_closed": bool(entry.closed) if entry is not None else False,
            # D30's digital half: what makes `Card 17` countable by hand again once the
            # section has holes. Both null together when the walk degraded — the app
            # draws no sentence, which is the honest rendering of "cannot say".
            "neighbors": neighbors,
            "section_gaps": section_gaps,
            # 0-BASED: card 1 of 250 is 0.0 of the way in, not 0.004. The number answers
            # "how much of the box do I pass before I reach this card", which is the
            # question a thumb asks — the first card needs no travel at all. Null rather
            # than zero when the denominator is 0, because there is no fraction of an empty
            # box, and a 0.0 there would draw a progress bar at the start of nothing.
            #
            # Raw, unrounded. Formatting it to "16%" is the app's, and rounding here would
            # decide a precision for every screen that reads it.
            #
            # OFF `slot`, NOT `index` (D58). The denominator counts cards, so the numerator
            # must too, or the bar draws a card at a percentage of a box it is not at. A
            # departed card has no fraction for the same reason it has no label.
            "fraction": ((slot - 1) / total) if (total and slot is not None) else None,
        }


# -------------------------------------------------------------------------------- routes


def do_capture(payload: dict) -> Tuple[HTTPStatus, dict]:
    """Allocate the next position in a box, store the photo, record the card.

    Order matters and is not arbitrary. The index is unknown until `allocate_capture`
    returns, and the filename is derived from it, so the photo cannot be written first.
    Everything therefore happens inside one `Store.write()`: if the photo or sidecar write
    raises, the exception leaves the block and the session commits nothing, so there is no
    record pointing at a file that was never written.
    """
    box = _require_box(payload)
    capture_id = _optional_text(payload, "capture_id")
    # THE CLAIMS THIS BODY CARRIES, KEYED BY RECORD FIELD NAME so they pass straight through
    # `allocate_capture` and `sidecar_payload`, both of which speak that vocabulary.
    #
    # `note` IS DELIBERATELY NOT HERE, AND THE TIMING IS THE REASON. It is free text a human
    # types, and the feeder emits a card every ~623 ms — a control that has to be filled in
    # before the shutter would put a keyboard on the critical path of a run whose whole point
    # is hands on cards. So a note is a CORRECTION applied to a position that already exists,
    # through `PUT /inventory/<box>/<index>`, which corrects and never creates. Nothing about
    # a capture waits for it, and a card whose note is added a minute later — or never — is a
    # perfectly good record.
    # `game` IS DECODED BEFORE BOTH CLAIMS THAT HAVE A VOCABULARY, and the order is
    # load-bearing rather than stylistic: a claim's vocabulary is the game's (D21, D23), so
    # neither the finish nor the rarity claim can be judged until the game is known.
    #
    # THE FINISH JOINED THIS SENTENCE LATE, WHICH IS WHY IT SAID `rarity_claim` ALONE. The
    # finish was checked against Pokemon's three enum members whatever game was named, so a
    # Riftbound `foil` — offered by the screen, authored by the registry — was refused at
    # the lens. `_check_variant_members` carries the full account.
    #
    # A body with no game validates against `games.DEFAULT_GAME`, which is the game its
    # record will be READ as (D21's read-side backfill) — validation only, never a write.
    game = _optional_game(payload)
    claims = {
        "set_hint": _optional_text(payload, "set_hint"),
        "metadata_finish": _optional_variant(payload, game),
        "game": game,
        "rarity_claim": _optional_rarity_claim(payload, game),
        "product": _optional_product(payload),
    }
    # AFTER THE CLAIMS, WHICH IS A CHANGE OF ORDER AND NOT AN OVERSIGHT. The claims are three
    # cheap string comparisons; this base64-decodes a photograph that can be tens of
    # megabytes. A body that names a game this server does not know is refused whatever its
    # bytes are, so decoding first is work done to reach a refusal that was already decided.
    # Same ordering argument `allocate_capture` makes about the sealed-box check: a refusal
    # should burn nothing. The cost is that a request with BOTH a bad game and no image now
    # hears about the game first; both statements are true and either sends the client back
    # to fix its request.
    blob = _require_image(payload)

    with Store().write() as snapshot:
        card, created = snapshot.inventory.allocate_capture(
            box, capture_id=capture_id, **claims
        )
        if created:
            path = photo_path(card.box, card.index)
            path.parent.mkdir(parents=True, exist_ok=True)
            files.write_atomic(path, blob)
            files.write_json(
                sidecar_path(path), sidecar_payload(card.box, card.index, **claims)
            )
            # Set after the write, because the path is not knowable before the index. The
            # history event `record_capture` already appended carries the position and a
            # null photo for that reason; the record itself carries the path.
            card.photo = str(path)
        body = _card_summary(snapshot.inventory, card, created=created)

    return (HTTPStatus.CREATED if created else HTTPStatus.OK), body


def _card_summary(inventory: master.Inventory, card: master.Card, *, created: bool) -> dict:
    """Where a card landed. `place` is the block; the three loose keys are compatibility.

    THE LOOSE `label`, `section` AND `card` ARE THE SAME VALUES AS THE ONES INSIDE `place`,
    read off one `Position`. They are duplicated rather than moved because `app/src/` reads
    them at this level today and a rename is not this change's to make — but there is only
    one renderer behind both, so they cannot come to disagree. Whoever moves the app onto
    `place` deletes the three lines here and changes nothing else.

    THE POOLED CARD IS THE ONE EXCEPTION TO "THE SAME VALUES", and it is deliberate. The
    block's `label` is null — a pooled card has no position to name (`_Places` has the
    ruling) — but the loose `label` is the string the capture screen prints out loud for
    where the card landed, and a screen that prints nothing after a capture reads as a
    capture that did not land. So the loose key carries the pooled fact instead
    (`join.pooled_label` — "Pokémon code cards · pooled"), a true sentence about where the
    card went, while the block's null stays the true answer to "which slot". Two
    consumers, two questions, one composer each.
    """
    place = _Places(inventory).of(card.box, card.index)
    return {
        "box": int(card.box),
        "index": int(card.index),
        "key": card.key,
        # NON-NULL BY CONTRACT — the capture screen prints this out loud, and a screen
        # that prints nothing after a capture reads as a capture that did not land. A
        # pooled card answers the pooled fact; a card the walk could not count answers its
        # store key, which is the only handle left and is what `place_text` already falls
        # back to for the same reason.
        "label": (
            (place["label"] or f"{int(card.box)}/{int(card.index)}")
            if place["located"]
            else join.pooled_label(str(place["game"]))
        ),
        "section": place["section"],
        "card": place["card"],
        "place": place,
        # True only on the first capture into a box. The app should confirm the box number
        # with the operator when it sees this: a typo like box 33 for box 3 is a valid int,
        # a real photo and a real listing, and nothing downstream can tell. It catches the
        # FIRST typo only — a second into the same phantom box looks ordinary.
        "new_box": created and int(card.index) == 1,
        "created": created,
        "photo": card.photo,
        "capture_id": card.capture_id,
    }


def _flat_place(place: dict) -> dict:
    """The three flat decorations a located row carries beside its `place` block.

    ONE COMPOSER FOR TWO ROW BUILDERS (`_card_row` and `do_inventory`), which had the same
    four lines written out twice and now have a rule that cannot drift between them.

    A KEY IS OMITTED RATHER THAN SENT NULL, and `app/src/types.ts` types all three optional
    for it. `server.ts:positionLabel` answers null on an absent label, and
    `BoxBrowse.tsx:rowSlot` tests `card !== undefined` — so a null there would render the
    string `null` in the walk's left cell, where an absent one correctly falls through to
    the label.

    WHAT EACH ABSENCE MEANS, since there are now three and they are not the same fact:
      no `label`   the walk could not count this box, so no number is knowable (D58)
      no `card`    this card has left the box, so it is in no slot — but `section` stays,
                   because the section it sat in is still a real part of a real box and is
                   what the walk groups by
      no block     a pooled card, which never had a slot at all (D24); the caller answers
                   that one, since it has the `located` flag in hand
    """
    if place["label"] is None:
        return {}
    flat: dict = {"label": place["label"], "section": place["section"]}
    if place["card"] is not None:
        flat["card"] = place["card"]
    return flat


def _card_row(
    inventory: master.Inventory, box: int, index: int, card: master.Card
) -> dict:
    """One whole inventory record, decorated exactly as `GET /inventory` decorates its rows.

    THE SAME FOUR FIELDS AND THE SAME RENDERER, so a screen holding this answer against a
    row of `GET /inventory` compares field for field — `app/src/types.ts` already types that
    shape as `InventoryCard`, and the routes below need no fourth vocabulary for a card. The
    whole record rather than `_card_summary`'s eight fields because 7b's answers change
    `sku`, `condition` and `state`, none of which that summary carries: it answers "where did
    this card land", and these two answer "what does this card say now".

    THE POSITION IS RENDERED FROM THE CALLER'S OWN INTEGERS, not from `card.box` and
    `card.index`. The record was found under `position_key(box, index)`, so those two
    integers are what identify it, and they arrive here having already matched `(\\d+)/(\\d+)`
    in the route. The stored fields may be strings — `Inventory.parse` coerces nothing — and
    rendering from them is the one way this could raise on a record the caller has already
    located. `do_inventory` has to read the record's own fields because it has no caller-
    supplied position to use, and that is exactly why it needs the try/except this does not.

    WIRE-ONLY, the same constraint `do_inventory` works under: `Inventory.parse` filters on
    `Card.__annotations__`, so a `label` reaching `inventory.json` is dropped silently on the
    next reload. `asdict` copies the record out, so there is nothing here for a commit to
    pick up even though these routes run inside `Store.write()`.

    `place` IS WIRE-ONLY FOR THE SAME REASON THE OTHER THREE ARE, and it is a bigger object,
    so it is worth being explicit: a `place` written into `inventory.json` would carry a copy
    of a box's fill and its capacity, and `parse` would drop it on the next reload. What it
    must never become is a stored denominator — D20 puts that on the `Box`, and one is
    enough.
    """
    place = _Places(inventory).of(box, index)
    row = asdict(card)
    # A pooled card gets the block and not the flat decoration, matching `do_inventory`
    # row for row — the flat `label` is what `server.ts:positionLabel` reads, and a pooled
    # card must answer null there exactly as an inventory row does. The pooled fact rides
    # inside `place` (`game_display`), where the screens that may show it go looking.
    if place["located"]:
        row.update(_flat_place(place))
    row["place"] = place
    # D67's decoration, wire-only like the four above it and unconditional unlike them: a
    # number is a fact about the card rather than about where it is, so a pooled record and
    # one whose position will not coerce both still get theirs.
    row["number_display"] = _number_display(card)
    return row


def _queue_depth(queue: queues.Queue) -> Tuple[Optional[int], Optional[str]]:
    """How many cards are still waiting in one queue, or None and a finding. Never raises.

    `len(Queue)` IS A SORT, which is not obvious from the call and is what made this
    necessary. It runs `open_entries`, which orders by `QueueEntry.sort_key` — so a `market`
    that is not a number raises `decimal.InvalidOperation`, and a `box` that arrived as a
    JSON string raises `TypeError` on the tuple compare (`Queue.parse` coerces nothing).
    Both were measured escaping `/status`, the one route you reach for when something is
    wrong. It already refuses to be taken down by a bad inventory record; this is the same
    rule applied to the file 7b taught it to read.

    NULL RATHER THAN A SUBSTITUTE NUMBER. Falling back to `len(queue.entries)` would answer
    with the count of every record in the file, cleared or not — the number `do_status`
    stopped publishing on purpose, because it says there is work left after the last card
    has been answered. A count that is wrong in the direction of "there is more to do" is
    worse here than no count, since this is the number the owner works from.

    PER QUEUE, so a corrupt `review.json` does not also hide what is sitting in parked.
    """
    try:
        return len(queue), None
    except (ArithmeticError, TypeError, ValueError) as exc:
        return None, (
            f"the {queue.name} queue holds an entry that cannot be ordered "
            f"({type(exc).__name__}: {exc}), so the {queue.name} queue cannot be counted."
        )


def do_status() -> dict:
    """Lock-free. Counts, the next index per box, and whether the inventory parses.

    Deliberately does NOT probe the lock. The only primitive the store exposes is an
    acquire, so reporting on it would make a read route a writer.

    NOTHING IN HERE MAY RAISE ON BAD DATA. Every finding is reported in `problem` and the
    field it belongs to answers null. That rule is older than this route's queue counts and
    is why they are guarded the same way the inventory scan is.
    """
    snapshot = Store().read()
    inventory = snapshot.inventory
    problems: List[str] = []

    body = {
        # WHICH PROCESS IS ANSWERING. `scripts/serve.py` restarts this server when a watched
        # Python file changes, and a restart is otherwise invisible from the app — the port is
        # the same, the store is the same, and the only symptom of NOT having restarted is the
        # one docs/GATES.md records: whole-second timestamps written hours after the
        # millisecond fix landed, because the process predated it.
        #
        # A uuid rather than a pid or a start time. A pid is recycled and a clock can go
        # backwards; the only question the client asks is "is this the same process as last
        # time", and identity is the honest answer to it. `started_at` is beside it for the
        # human reading the JSON, and nothing compares it.
        "boot_id": BOOT_ID,
        "started_at": STARTED_AT,
        "captures_root": str(captures_root()),
        "store": str(files.inventory_dir()),
        "store_exists": files.inventory_dir().is_dir(),
        "cards": len(inventory.cards),
        "states": inventory.counts(),
        # OPEN entries, which is what `len(Queue)` returns, what `Queue.summary` prints in
        # every run report, and what `GET /queues` hands the review screen. This counted
        # `entries` — every record in the file, cleared or not — until 7b, and the two were
        # indistinguishable because NOTHING IN THIS REPO HAD EVER SET `cleared_by_human`;
        # `store/queues.py` and `store/cache.py` both say so in their headers.
        # `do_review_answer` below is its first writer, so from here the two numbers diverge:
        # a card the owner has already answered would go on being counted here forever while
        # disappearing from the screen that works the queue. This is the number he reads to
        # decide whether there is work left, so it is the one that must not drift.
        #
        # Each side answers null when its file holds an entry that cannot be ordered —
        # `_queue_depth` has why, and why the count is not faked. `app/src/types.ts` types
        # this pair and has to widen to `number | null` to match.
        "queues": {queues.MAIN: None, queues.PARKED: None},
    }

    # Keyed off each queue's own `name`, which is where `_queue_depth` reads its filename
    # from too — so the two wire keys and the finding that explains a null one cannot come to
    # disagree about which file is meant.
    for queue in (snapshot.review, snapshot.parked):
        depth, finding = _queue_depth(queue)
        body["queues"][queue.name] = depth
        if finding:
            problems.append(finding)

    # A corrupt record must not take down the health endpoint — that is the one route you
    # reach for when something is wrong. Report it as a finding instead.
    try:
        boxes = _boxes_named(inventory)
        body["next_index"] = {str(box): inventory.next_index(box) for box in boxes}
    except (master.BadPosition, TypeError, ValueError) as exc:
        body["next_index"] = None
        problems.append(
            f"the inventory holds a card whose box or index is not a number ({exc}). "
            "Positions cannot be allocated until it is corrected."
        )

    # ONE `problem` STRING, JOINED, rather than a list or a second key. Two independent
    # findings can now be true at once, and the alternatives both cost more than they pay
    # for: a `problems` array changes the shape every client already reads for a case that
    # is rare, and a second key invites a screen that shows one of them. With one finding
    # the string is byte-identical to what this route has always answered, which is the
    # property that made joining the cheap option.
    if problems:
        body["problem"] = " ".join(problems)

    return body


def do_games() -> dict:
    """The registry, verbatim (D21, D22). The capture screen's game picker reads this.

    THE ONLY COPY OF THE VOCABULARY IS `pipeline/games.py`, AND IT REACHES THE APP OVER THE
    WIRE. An `app/src/games.ts` mirror was considered and rejected: it would be a second
    hand-authored copy of a hand-authored file, kept in step by nobody, buying nothing this
    route does not already give. The app has one place it can learn what a game is, and it is
    the same place the pipeline learns it.

    SERVED AS AUTHORED, NOT PROJECTED. Every field goes out, including the ones no screen
    reads today — `join_key`, `prompt`, `crop_bands`, `card_aspect`. Choosing a subset here
    would be a third opinion about what a game is, and the first new screen that wanted a
    field would have to change a route to get it. Tuples become JSON arrays; nothing else
    is transformed.

    THE SERVER MAY IMPORT THE REGISTRY BECAUSE IT IS STDLIB-PURE (D22) — it imports `typing`
    and nothing from this repo, which is the property that lets `scripts/docs-audit.py` read
    it with `ast`. Nothing here runs at request time but a dict copy.

    `default` IS D21's READ-SIDE BACKFILL, PUBLISHED RATHER THAN GUESSED AT. The screen needs
    a game to start on, and the alternative — the app picking the first entry, or hardcoding
    `pokemon` — is a second decision that has to agree with `games.DEFAULT_GAME` and would
    silently stop agreeing the day the registry is reordered.
    """
    return {
        "default": games.DEFAULT_GAME,
        "games": [dict(entry) for entry in games.GAMES],
        # C10's product vocabulary, served BESIDE the registry rather than inside it. It
        # belongs in this answer because the capture screen's product picker needs it and
        # `GET /games` is already the one route that teaches the app a capture vocabulary —
        # a second route for one list would be a second thing to fetch before the first
        # shutter.
        #
        # NOT A FIELD ON THE `pokemon_code` REGISTRY ENTRY, and that is a hard constraint
        # rather than a preference: `scripts/docs-audit.py` reads `pipeline/games.py` with
        # `ast.literal_eval`, so that file may import nothing from this repo. Putting the
        # list there would mean either a second hand-authored copy of `codes/products.py`
        # or an import that breaks the audit.
        "product_game": products.GAME,
        "products": [
            {
                "key": entry["key"],
                "display": entry["display"],
                "premium": entry["premium"],
                "redeem_limit": entry["redeem_limit"],
            }
            for entry in products.PRODUCTS
        ],
    }


def app_dist() -> Path:
    """The built app's directory, read at call time. See `APP_DIST` for why not a constant."""
    return APP_DIST


def app_claims(path: str) -> bool:
    """Is this a path the built app answers? The root, or a file of the build.

    NARROW ON PURPOSE, AND THE HASH ROUTER IS WHY (D138). The usual SPA host serves
    `index.html` for every unmatched path, because its router owns real URLs and a deep link
    has to survive a reload. `App.tsx` is a HASH router: every screen is `/#/inventory`, the
    part after `#` is never sent, and so the only paths the app has are `/` and its own
    asset files. A catch-all here would buy nothing and cost the thing this server cannot
    afford to lose — `GET /boxes/abc` and `GET /statuss` would answer 200 with HTML instead
    of the JSON refusal that names what was wrong, and every such refusal in this file would
    quietly stop being reachable.

    So: the root, or a final segment whose extension is one `vite build` emits. Everything
    else is still `no_such_route`, exactly as it was before the app moved in here.
    """
    wanted = path.lstrip("/")
    if not wanted:
        return True
    return Path(wanted).suffix in APP_TYPES


def do_app_file(path: str) -> Tuple[bytes, str, str]:
    """A file out of the built app. `app_claims` decides what reaches here (D138).

    THE LAST RESORT OF `do_GET` AND NEVER A ROUTE. Every route in this server is matched
    first and this is what the fall-through reaches, so a path this product serves on the
    wire can never be shadowed by a file somebody dropped into `app/dist/` — which is the
    one way a static serve bolted onto an API goes wrong.

    WHAT IT REFUSES, AND WHY EACH ONE IS CHECKED RATHER THAN ARGUED. `..` and a NUL byte are
    refused by shape, before anything touches the filesystem, and the resolved path is then
    required to be inside `app/dist/` — belt and braces on purpose, because the first check
    is about the string the client sent and the second is about the file it reached, and a
    symlink inside `dist/` satisfies the first while defeating it. The alternative to both is
    `GET /..%2f..%2finventory/store.sqlite` reading the store over a route whose whole job is
    to hand out bytes.

    IT SERVES EIGHT EXTENSIONS AND REFUSES THE REST. `dist/` holds nothing else after a
    `vite build`, so an unknown extension there means something that is not the build — and a
    404 for it is the honest answer rather than `application/octet-stream` over a file this
    server was never meant to have an opinion about.

    NO PHOTOGRAPH AND NO STORE IS REACHABLE FROM HERE, which is what makes serving a
    directory out of this process an ordinary thing rather than an opsec question:
    `app/dist/` is compiled output under the CHECKOUT, and every card, sidecar and code-card
    image lives under `PKMNSCAN_HOME`, which this function cannot name. `GET /photo` is
    still the only way a captured byte leaves this server.
    """
    root = app_dist()
    if not (root / "index.html").is_file():
        # THE APP IS NOT BUILT, AND THIS IS THE ONLY SENTENCE THAT SAYS SO. Not a page and
        # not styled: a screen here would be a second front end, maintained forever, for the
        # ten seconds before the supervisor's first build lands (D138 §1.1). 503 rather than
        # 404 because the resource is not missing, it is not ready — and a 404 would read to
        # a browser, and to the operator, as a wrong address.
        raise BadRequest(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "app_not_built",
            "The app is not built. `make up` builds it; see .serve/supervisor.log.",
        )
    wanted = path.lstrip("/")
    if "\x00" in wanted or ".." in wanted.split("/"):
        raise BadRequest(
            HTTPStatus.NOT_FOUND, "no_such_file", "No such file."
        )
    candidate = (root / wanted) if wanted else (root / "index.html")
    try:
        resolved = candidate.resolve()
        inside = resolved.is_relative_to(root.resolve())
    except (OSError, ValueError):
        inside = False
    if not inside or not resolved.is_file() or resolved.suffix not in APP_TYPES:
        # A NAMED FILE THAT IS NOT THERE IS A 404, NOT THE APP. `app_claims` has already
        # decided this path looks like a file of the build, so reaching here means the build
        # does not have it — a stale `index.html` asking for an asset the swap deleted, or a
        # typo. Answering with HTML under a `.js` name would hand the browser a syntax error
        # to report instead of the missing file.
        raise BadRequest(HTTPStatus.NOT_FOUND, "no_such_file", f"No such file {path}.")
    cache = APP_IMMUTABLE if wanted.startswith("assets/") else APP_NO_STORE
    return resolved.read_bytes(), APP_TYPES[resolved.suffix], cache


def app_owns(path: str) -> bool:
    """Is the app answering this path right now? For the write verbs' 405.

    A write to a path the app is serving is a METHOD error and not a missing route, and that
    is the whole of what this decides: `POST /` against a server handing out the app at `/`
    should say the method is wrong rather than that there is nothing there. Both halves are
    required — the path has to be one the app claims AND there has to be a build behind it,
    because an unbuilt tree genuinely has nothing at `/` and 404 is then the truth.
    """
    return app_claims(path) and (app_dist() / "index.html").is_file()


def do_photo(box: int, index: int) -> Tuple[bytes, str]:
    """The stored capture, and a validator for it. D6's route, D52's validator.

    THE URL NAMES A SLOT, NOT A PHOTOGRAPH, AND THAT IS WHY THE SECOND RETURN VALUE EXISTS.
    `/photo/2/180` means "whatever is in box 2's slot 180 today", and three operations move
    a different card into a slot the browser has already cached: D10 ruling 1's mid-box
    delete slides every higher card down one, D10's undo releases an index the next capture
    reuses, and D26's re-shoot replaces the bytes outright. `app/src/server.ts:photoUrl`
    has recorded the hazard for the undo case since it was written and named this repair in
    as many words — "the fix is a cache header on the server" — while the response carried
    no `Cache-Control`, no `ETag` and no `Last-Modified` at all.

    WHAT IT COST, MEASURED ON A REAL BOX 2 (2026-08-29). Deleting box 2's card 180 shifted
    363 cards down one index in 288 ms and the walk redrew in 500 ms — and the screen went
    on showing the photograph of the card that had just been deleted, over the facts of the
    card that had slid into its slot. `performance.getEntriesByType` reported the displayed
    image at `transferSize: 0`; the same URL fetched with a cache-buster returned the right
    card. **The operator's reading of that screen is that the delete did not happen**, and
    the next press deletes the card that slid in, which is a real capture with a real
    photograph. The staleness is not one card either: every slot above the deleted one is
    now off by one for as long as its entry survives in the browser's cache.

    A STRONG ETag OVER THE BYTES, RATHER THAN A STAT TRIPLE. `os.replace` preserves the
    moved file's own mtime, so a renumbered slot's timestamp is the neighbour's capture time
    and not the rename — a validator built from mtime and size would be arguing about
    whether two photographs can share both, and an inode is reusable once a photo is
    deleted. A digest of what is actually being sent cannot be wrong about any of that.
    Measured at ~0.15 ms per photograph on top of the read this route already does, against
    ~0.6 ms for the read itself.

    TRUNCATED TO 128 BITS because an ETag is an opaque string a browser compares for
    equality, and the full digest is 64 characters on every photo response for no reader.
    """
    path = photo_path(box, index)
    if not path.is_file():
        raise BadRequest(
            HTTPStatus.NOT_FOUND,
            "photo_not_found",
            f"No photo stored at box {box}, card {index}.",
        )
    blob = path.read_bytes()
    return blob, '"' + hashlib.sha256(blob).hexdigest()[:32] + '"'


def do_inventory() -> dict:
    """The whole card map, each row decorated with its rendered position.

    DECORATED BECAUSE THE ALTERNATIVE IS A SECOND RENDERER, and the alternative is what
    happened: an undecorated row carries `box` and `index` and nothing else, so the app
    reimplemented D10's section arithmetic in TypeScript to draw a label with.
    Two copies of the rule that says where a physical card is, one edit away from
    disagreeing about it. `_card_summary` already answers POST and PUT with exactly these
    three fields, so this makes the two shapes agree rather than inventing a third.

    THE DECORATION IS WIRE-ONLY, and that is the constraint that shapes the code below.
    `Inventory.to_payload` is the on-disk format: `inventory.json` is parsed back by
    `Inventory.parse`, which filters on `Card.__annotations__` and would drop a `label`
    silently on the next reload. So the fields are added to the dict `to_payload` has just
    built out of `asdict`, on a snapshot this function then discards — they cannot reach a
    write, because nothing here holds the snapshot long enough to commit it.

    A RECORD WHOSE POSITION WILL NOT COERCE IS LEFT UNDECORATED rather than labelled. Both
    alternatives are worse. Raising takes the entire card map down over one bad row, on the
    route the app polls. A placeholder label — `Box ? · Section ?` — names a position that
    does not exist, which is the one thing a position label may never do, since D10's whole
    argument is that a printed label is worth trusting a year later. `do_status` is where a
    record like that is reported, and it reports it already.

    `BadPosition` AND `BadSections` JOIN THAT RULE RATHER THAN GETTING ONE OF THEIR OWN. The
    first is what `_Places` raises when SOME OTHER record in the box will not coerce — the
    denominator is a whole-box scan, so one bad row now costs its neighbours their place
    block. The second is a box whose stored `sections` never went through `set_sections` and
    will not validate. In both cases the row still arrives, carrying every field it has ever
    carried except the decoration, which is the same trade this route already makes: the
    card map is what the app polls, and it must not go down over one row.

    `boxes` AND `listings` RIDE ALONG WITHOUT A LINE OF CODE HERE, because `to_payload` is
    the whole schema and v2 added both. That is deliberate rather than incidental — the app
    needs a box's name and capacity to render a place block it did not ask the server for,
    and a second route to fetch them would be a second thing to keep in step.
    """
    inventory = Store().read().inventory
    payload = inventory.to_payload()
    places = _Places(inventory)
    for record in (payload.get("cards") or {}).values():
        # BEFORE THE POSITION, AND BEFORE THE `continue` BELOW (D67). A number is a fact about
        # the card and not about where it is, so a row whose box or index will not coerce keeps
        # its number row even though it can carry no label. Composed off the payload's own two
        # fields rather than off a `master.Card` — `to_payload` writes both verbatim, and this
        # loop has the dict in hand where `_card_row` has the record.
        record["number_display"] = join.display_number(
            record.get("number"), record.get("printed_total")
        )
        try:
            place = places.of(record["box"], record["index"])
        except (KeyError, TypeError, ValueError, master.BadSections):
            # `BadPosition` is a `ValueError` and is caught by that clause; `BadSections` is
            # too, and is named anyway so this reads as the two failures it is.
            continue
        # A pooled card is served UNDECORATED BUT NOT BARE: no flat `label`/`section`/
        # `card` — `positionLabel` answers null, which is the ruling that the label is
        # never rendered for one — while `place` still arrives carrying `located: false`
        # and the game's display name, so a screen can tell the design fact from the
        # coerce-failure above, which leaves a row with no `place` at all.
        if place["located"]:
            record.update(_flat_place(place))
        record["place"] = place
    return payload


def do_put_card(box: int, index: int, payload: dict) -> dict:
    """Correct a capture claim on one card that already exists: set hint, variant, game, rarity claim, note.

    THE SETTABLE SET IS `PUT_FIELDS`, DERIVED FROM `store/master.py:CAPTURE_CLAIM_FIELDS` —
    every claim a capture can write, this route can fix. `note` is the one that is ONLY ever
    written here: it is free text about a card the pipeline will never identify, and it is
    typed after the shutter rather than before it so a keyboard never sits on the critical
    path of a feeder run. See `do_capture` for that argument in full.

    Per-position, never a whole-document replace: rebuilding every card from a client's
    stale snapshot is the same lost update the allocator is shaped to avoid, with a wider
    blast radius.

    This mutates the stored card directly rather than going through `record_capture`, whose
    first branch CREATES a card from whatever it is handed. A PUT naming a position that
    does not exist would otherwise invent one — logged as a capture, answered with a
    success, flagged to nobody.

    IT REWRITES THE SIDECAR TOO, and that is not housekeeping. `cli/cmd_identify.py` builds
    its card from `identify.sidecar`, not from the inventory record, so a correction that
    stopped at `inventory.json` would never reach the variant ladder: the run would take D3
    rung 2 or 3 as though no toggle had ever been set. Worse, it would not survive — the
    upsert in `record_capture` writes the sidecar's value back over the record whenever the
    sidecar has one, so a correction against a sidecar that already named a finish would be
    silently reverted by the next identify run. Measured both ways before this was written.

    The sidecar is skipped when the photo is absent — a card recorded by `emit` rather than
    captured has nothing for the reader to find, and a lone `.json` under the capture tree
    would serve no one.

    IT APPENDS A `corrected` EVENT, AND THE REASON IS THE PARAGRAPH ABOVE. This route
    overwrites the record in place and then overwrites the sidecar with the same values, so
    the moment it returns there is nowhere left holding the claim the operator just replaced.
    That is fine for a typo and expensive for the case the route exists for: D3 rung 1 makes
    the toggle a *claim* the ladder trusts ahead of the catalog, so the value corrected here
    is what decides which condition row the card matches and therefore what it is priced and
    listed as. A card sold as the wrong finish is answerable a month later only if something
    kept what it used to say. `docs/DEBTS.md` recorded the omission as "the store logs state
    transitions and a correction is not one", which is true of the store and not an argument
    about whether this belongs in the audit trail.
    """
    key = master.position_key(box, index)
    _reject_unknown(payload, PUT_FIELDS)

    # Decoded before the lock is taken, keyed by RECORD field name so the diff below and the
    # sidecar write share one mapping. Each claim has its own decoder and they are not
    # interchangeable — `game` is checked against the registry, `variant` and `rarity_claim`
    # against THAT GAME's vocabularies, and a note is prose with nothing to check it against
    # — so this is a table of calls rather than a loop over `CLAIM_WIRE_NAMES`.
    #
    # This comment used to say `variant` was checked "against an enum", singular, which is
    # what the code did and what was wrong with it: the enum was Pokemon's under every game.
    #
    # A KEY ABSENT FROM THE BODY IS NOT A CLEARED CLAIM. Only fields actually present are
    # applied, which is what lets one screen correct the finish without also wiping a set
    # hint it never rendered.
    incoming = {}
    if "set_hint" in payload:
        incoming["set_hint"] = _optional_text(payload, "set_hint")
    if "game" in payload:
        incoming["game"] = _optional_game(payload)
    # SHAPE ONLY, FOR THE FINISH TOO — its vocabulary is the game's, and the game is either
    # in this body or on the card inside the lock. Exactly the rarity claim's split, added
    # when the finish turned out to have been judged against Pokemon's enum under every
    # game; `_check_variant_members` carries that account.
    variant_shape = _variant_shape(payload) if "variant" in payload else None
    # SHAPE ONLY, HERE — membership needs the card's game and the card lives inside the
    # lock. Kept out of `incoming` until it is checked, so the apply loop below never sees
    # an unvalidated claim.
    claim_shape = _rarity_claim_shape(payload) if "rarity_claim" in payload else None
    if "product" in payload:
        incoming["product"] = _optional_product(payload)
    if "note" in payload:
        incoming["note"] = _optional_text(payload, "note")

    with Store().write() as snapshot:
        card = snapshot.inventory.cards.get(key)
        if card is None:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "card_not_found",
                f"No card at box {box}, card {index}. This route corrects; it never creates.",
            )

        # The claim's membership check, now that the game it is judged against is known:
        # the game this same PUT sets, or failing that the game the card already claims.
        # A refusal here leaves the block before anything is assigned, so a PUT carrying a
        # good game and a bad claim changes nothing — the session commits only whole
        # corrections. A PUT that changes the game while an existing claim stands is NOT
        # re-validated here: the stale members cost a recorded problem at the next sidecar
        # read (`identify/sidecar.py` drops them, loudly) rather than a refusal that would
        # force every game correction to restate a claim it never mentioned.
        judged_against = incoming.get("game", card.game)
        if "variant" in payload:
            # The RETURN is what lands, not `variant_shape`: this is where the claim is put
            # into the game's enum order, and only this side knows the game (D3 rung 1's set
            # — see `_check_variant_members`).
            incoming["metadata_finish"] = _check_variant_members(
                variant_shape, judged_against
            )
        if "rarity_claim" in payload:
            incoming["rarity_claim"] = _check_rarity_members(claim_shape, judged_against)
        # THE PRIOR VALUE IS READ BEFORE THE ASSIGNMENT, which is the whole of what the log
        # line is for, and it is why these are not two bare assignments any more.
        #
        # ONLY A VALUE THAT ACTUALLY MOVED IS RECORDED. A PUT restating what the card already
        # says changed no claim — the app re-saving a screen is the shape that produces one —
        # and logging it would fill the file with lines that mark nothing, in among the lines
        # that mark the change somebody is looking for. The question this event answers is
        # *when did the claim change*, so a no-op has no answer to contribute. The cost is
        # that a PUT which only repairs a sidecar that had drifted from the record leaves no
        # trace; `docs/DEBTS.md` records that as uncovered.
        #
        # KEYED BY THE RECORD'S FIELD NAMES, `metadata_finish` and not the wire's `variant`.
        # Every other key this file writes into the log — `position`, `sku`, `run` — is a
        # `Card` field, and a history line is read while holding `inventory.json` open. The
        # wire name belongs to the request body and the sidecar, which are both inputs.
        #
        # `_claim_moved` RATHER THAN `!=`, since D3's amendment gave one claim two spellings.
        # A card holding the bare `"holo"` every record written before 2026-08-23 carries,
        # restated by a client that now always sends `["holo"]`, is a claim that did not move
        # — and a raw `!=` would log it as one on the first PUT that so much as mentions the
        # finish. `from` is still the RAW stored value, not the canonical one: this line
        # answers "what did the record say", and the record said a string.
        changed = {}
        for field, value in incoming.items():
            current = getattr(card, field)
            if _claim_moved(field, current, value):
                changed[field] = {"from": current, "to": value}
                setattr(card, field, value)

        photo = photo_path(card.box, card.index)
        wrote_sidecar = photo.is_file()
        if wrote_sidecar:
            # EVERY SIDECAR CLAIM, READ OFF THE RECORD — not just the ones this request
            # touched. The sidecar is rewritten whole, so composing it from `incoming` would
            # drop the claims the body did not mention.
            files.write_json(
                sidecar_path(photo),
                sidecar_payload(
                    card.box,
                    card.index,
                    **{name: getattr(card, name) for name in CLAIM_WIRE_NAMES},
                ),
            )

        # NESTED UNDER ONE `changed` MAPPING, and not flattened into `field`/`from`/`to`.
        # `_history` drops a None extra, so a flat `from` would VANISH exactly when it is
        # doing the most work — a hint that was cleared back to no claim, or a finish set on
        # a card that had never carried one, would leave a line indistinguishable from one
        # where that field was never touched. Inside a mapping the filter cannot see it. The
        # shape also carries both fields from one PUT without a second event.
        if changed:
            _history(snapshot.inventory, CORRECTED, key, changed=changed)

        body = _card_summary(snapshot.inventory, card, created=False)
        body["sidecar"] = str(sidecar_path(photo)) if wrote_sidecar else None

    return body


def do_put_box_claims(box: int, payload: dict) -> dict:
    """Apply capture-claim corrections to every eligible card in one box, in one write.

    THE OWNER'S ASK, 2026-08-23, verbatim: "if i accidentally didn't do it at the capture
    level, i'd like to be able to do it retroactively" — at the card level AND the box
    level. The card level already existed (`do_put_card` above); this is the box half, and
    it is the same claim vocabulary applied to many positions rather than a new one:
    `PUT_FIELDS`, decoded by the same decoders, judged by the same per-game validators,
    written with the same `corrected` history line. A box captured under the wrong game,
    or with the finish toggle forgotten for a whole stack, is corrected in one call.

    VALIDATE EVERYTHING, THEN WRITE EVERYTHING, OR WRITE NOTHING — D29's group-answer
    shape, borrowed because it exists for exactly this situation: a partial bulk write
    over a box is the worst outcome available, a box in a state nobody asked for that no
    single request describes. Every refusal below fires before any card is assigned to.

    MIXED BOXES ARE LEGAL (D21), AND THE VOCABULARY IS PER-GAME (D21/D23), so a claim is
    judged against the game THIS call sets when the body carries one, and against EACH
    CARD's own game when it does not — `do_put_card`'s `judged_against` rule, per card.
    When any card's vocabulary rejects the claim, the WHOLE call refuses naming up to
    eight of them (`claim_not_stocked_by_game`), rather than applying to the cards that
    fit: a sweep that silently corrected some of a box teaches the operator it corrected
    the box. The remedy is in the refusal — set `game` in the same call, or correct the
    odd cards through the card route.

    SOLD AND RETIRED CARDS ARE SKIPPED AND COUNTED, NEVER TOUCHED. Their record is
    history (D10, D26): nothing re-lists them, and a bulk sweep is exactly the
    indiscriminate write a terminal record deserves protection from. The response names
    up to eight skipped positions, and the card-level PUT remains the deliberate,
    one-position door for the rare case a terminal record's claim genuinely needs
    fixing.

    CLAIMS ONLY. `state`, listing counts and positions all have their own routes and
    their own rulings, and `_reject_unknown` over `PUT_FIELDS` is what keeps them out of
    this body.

    SIDECARS ARE REWRITTEN FOR CHANGED CARDS ONLY — unlike the card route, which rewrites
    on every call. A no-op restatement over a 400-card box would otherwise churn 400
    files to say nothing; the drift-repair the card route incidentally performs stays the
    card route's, and `docs/DEBTS.md` already records that repair as unlogged there.

    ONE `corrected` LINE PER CHANGED POSITION, carrying the same `changed` mapping the
    card route logs, plus `bulk` — the number of cards this call changed — so a reader of
    `history.jsonl` can tell one sweep from forty hand corrections, exactly as the group
    answer's `group` tag tells one press from sixteen (D29). One event for the box was
    considered and rejected: it would lose which cards moved, and the moved cards are
    what the line exists to answer for.
    """
    _reject_unknown(payload, BOX_CLAIM_FIELDS)
    if not any(field in payload for field in PUT_FIELDS):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "nothing_to_apply",
            f"Send at least one claim to apply. Settable: {', '.join(PUT_FIELDS)}.",
        )
    selected = _optional_indices(payload)

    # The same decode table as `do_put_card`, phase for phase: shapes before the lock,
    # membership inside it where the game each claim is judged against is known.
    incoming = {}
    if "set_hint" in payload:
        incoming["set_hint"] = _optional_text(payload, "set_hint")
    if "game" in payload:
        incoming["game"] = _optional_game(payload)
    variant_shape = _variant_shape(payload) if "variant" in payload else None
    claim_shape = _rarity_claim_shape(payload) if "rarity_claim" in payload else None
    # `product` WAS MISSING FROM THIS TABLE FROM D70 UNTIL 2026-09-05, and the comment above
    # said the two tables matched the whole time. `BOX_CLAIM_FIELDS` is DERIVED from
    # `PUT_FIELDS`, so `_reject_unknown` accepted the key, the `any(field in payload ...)`
    # guard passed, `incoming` never got it and the apply loop moved nothing: the route
    # answered 200 with `"applied": 0, "unchanged": N` — a silent no-op that reads exactly
    # like "the box already said that". `make docs-audit`'s `claim decode` row now reconciles
    # both tables against `PUT_FIELDS` so a derived tuple can never outrun its decoder again.
    if "product" in payload:
        incoming["product"] = _optional_product(payload)
    if "note" in payload:
        incoming["note"] = _optional_text(payload, "note")

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        if inventory.box(box) is None and not _box_holds_cards(inventory, box):
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "box_not_found",
                f"No box {box}. Create it with POST /boxes, or capture into it — a box "
                f"registers itself the first time a card lands in it.",
            )

        # Every record in the box, coerced the way every destructive walk here coerces —
        # an unreadable record refuses (`BadPosition` -> `inventory_conflict`) rather
        # than being skipped, since it cannot be proven to be outside the box.
        targets: List[Tuple[int, str, master.Card]] = []
        skipped: List[Tuple[int, str]] = []
        for at, key, card in inventory.records_in(box):
            if selected is not None and at not in selected:
                continue
            if card.state in master.TERMINAL_STATES:
                skipped.append((at, card.state))
                continue
            targets.append((at, key, card))
        targets.sort()
        skipped.sort()

        # A SELECTION THAT NAMES A CARD THIS BOX DOES NOT HOLD REFUSES THE WHOLE CALL, with
        # every missing number listed. Applying to the ones that do exist would be the
        # partial sweep this route refuses everywhere else, and a selection is a statement
        # about a set: if the operator is wrong about one member they may be wrong about
        # which box they are looking at. Terminal cards are NOT counted missing — they are
        # in the box and they are reported as skipped, which is a different sentence.
        if selected is not None:
            present = {at for at, _, _ in targets} | {at for at, _ in skipped}
            missing = sorted(selected - present)
            if missing:
                raise BadRequest(
                    HTTPStatus.NOT_FOUND,
                    "card_not_found",
                    f"Box {box} holds no card at "
                    + ", ".join(str(at) for at in missing[:8])
                    + (f" (+{len(missing) - 8} more)" if len(missing) > 8 else "")
                    + ". Nothing was changed.",
                )

        # PHASE ONE — membership, against the game each card will be read as. A body that
        # sets the game is judged once (one vocabulary, and the validator's own refusal is
        # the right answer); a body that does not is judged per card, and any rejection
        # refuses the whole call with the cards named.
        if "game" in incoming:
            if "variant" in payload:
                _check_variant_members(variant_shape, incoming["game"])
            if "rarity_claim" in payload:
                _check_rarity_members(claim_shape, incoming["game"])
        elif "variant" in payload or "rarity_claim" in payload:
            rejected: List[Tuple[int, str]] = []
            for at, _key, card in targets:
                try:
                    if "variant" in payload:
                        _check_variant_members(variant_shape, card.game)
                    if "rarity_claim" in payload:
                        _check_rarity_members(claim_shape, card.game)
                except BadRequest as refused:
                    rejected.append((at, str(refused)))
            if rejected:
                named = "; ".join(f"card {at}: {text}" for at, text in rejected[:8])
                more = f"; and {len(rejected) - 8} more" if len(rejected) > 8 else ""
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "claim_not_stocked_by_game",
                    f"Box {box} holds cards whose game does not stock this claim: "
                    f"{named}{more}. Nothing was changed — a sweep that corrected only "
                    f"the cards that fit would leave the box in a state nobody asked "
                    f"for. Set `game` in this same call to judge every card against it, "
                    f"or correct the odd cards one at a time through "
                    f"PUT /inventory/{box}/<index>.",
                )

        # PHASE TWO — the card route's apply, per position: only fields present in the
        # body, only values that actually moved, prior values into the log.
        applied: List[Tuple[int, str, dict]] = []
        unchanged = 0
        sidecars = 0
        for at, key, card in targets:
            fields = dict(incoming)
            if "variant" in payload:
                # RE-CHECKED PER CARD RATHER THAN REUSING `variant_shape`, and phase one is
                # what makes that safe: every card was validated against exactly this game
                # above, so this call cannot raise. What it is here for is the canonical
                # form — the game's enum order (D3 rung 1's set; see
                # `_check_variant_members`) — and the order is the CARD's game's on a mixed
                # box, which is a per-card fact. Writing the raw shape would put tap order
                # on disk and make the next restated sweep diff as a change.
                fields["metadata_finish"] = _check_variant_members(
                    variant_shape,
                    incoming.get("game", card.game),
                )
            if "rarity_claim" in payload:
                fields["rarity_claim"] = claim_shape
            changed = {}
            for field, value in fields.items():
                current = getattr(card, field)
                # `_claim_moved`, for `do_put_card`'s reason and with more at stake: a raw
                # `!=` against a box captured before D3's amendment would report every card
                # as `applied` and rewrite every sidecar for a sweep that restated what the
                # box already said — the exact churn this route's docstring rules out.
                if _claim_moved(field, current, value):
                    changed[field] = {"from": current, "to": value}
                    setattr(card, field, value)
            if not changed:
                unchanged += 1
                continue
            applied.append((at, key, changed))
            photo = photo_path(box, at)
            if photo.is_file():
                files.write_json(
                    sidecar_path(photo),
                    sidecar_payload(
                        box,
                        at,
                        **{name: getattr(card, name) for name in CLAIM_WIRE_NAMES},
                    ),
                )
                sidecars += 1

        for _at, key, changed in applied:
            _history(inventory, CORRECTED, key, changed=changed, bulk=len(applied))

    return {
        "box": int(box),
        # The receipt, counted per kind like every destructive response here: what was
        # eligible, what moved, what already said this, and what was left alone because
        # its record is history.
        "eligible": len(targets),
        "applied": len(applied),
        "unchanged": unchanged,
        "skipped_terminal": len(skipped),
        "skipped": [
            {"index": at, "state": state} for at, state in skipped[:8]
        ],
        "sidecars_rewritten": sidecars,
    }


def _listing_hold(
    inventory: master.Inventory, card: master.Card
) -> List[Tuple[str, int]]:
    """Every non-zero listing stage on this card's SKU, or an empty list. D7 amended.

    THIS IS WHERE `undo_too_late` NOW GETS ITS FACT FROM, and the move is the whole of what
    v2 did to that refusal. D10 draws undo's line at `emit`: before it, nothing outside this
    Mac knows the card exists and deleting it costs the identification fee and nothing else;
    after it, a file on disk — and then TCGplayer itself — disagrees with the inventory. The
    test used to be `card.state == pushed`, and under v2 there is no such state to test:
    `pushed`, `staged` and `live` are counts on the SKU's `Listing`, and the card reads
    `identified` either way. The guard had silently lost its teeth, and would have hard-
    deleted the record, the sidecar and the photo of a listed card while leaving the SKU's
    counts claiming a copy that is no longer in the building.

    IT ASKS ABOUT THE SKU, NOT ABOUT THIS COPY, and that is not a compromise — it is what D7
    amended means. Copies of one SKU are fungible and which of them back the `live` count is
    deliberately unrecorded, so there is no such thing as "this particular copy was the one
    that got pushed". If three copies are staged, any three are, and every copy of that SKU
    is one of the candidates. The conservative reading is the only sound one.

    A CARD WITH NO SKU IS NOT HELD. Nothing has been emitted for it, by construction — every
    import row carries a `TCGplayer Id`. Nor is a SKU whose listing record exists with all
    three at zero: an emitted row that was reconciled away and then sold down leaves the
    record behind at zeros, and zeros mean TCGplayer is not holding anything.

    ALL NON-ZERO STAGES, not the first or the furthest along. The refusal message names them,
    and "2 pushed, 3 staged" tells the operator exactly which file and which screen to go and
    look at — while picking one would have to pick a rule for picking, and there is no
    argument for either direction that survives ten seconds of thought.
    """
    if not card.sku:
        return []
    entry = inventory.listings.get(card.sku)
    if entry is None:
        return []
    return _stages_held(entry)


def _stages_held(entry: master.Listing) -> List[Tuple[str, int]]:
    """Every non-zero stage on one listing record, or an empty list.

    `_listing_hold`'s second half, lifted out when `do_release_box_listings` needed the same
    question asked of a SKU rather than of a card. Shared rather than copied for the reason
    the unreadable-count branch below exists at all: it is a rule about how to read a number
    on a guard path, and a second copy of it is a second chance to read it the other way.
    """
    held: List[Tuple[str, int]] = []
    for stage in master.LISTING_STAGES:
        try:
            count = int(getattr(entry, stage))
        except (TypeError, ValueError):
            # A hand-edited count that will not coerce is treated as "something is there".
            # This is a guard on a destructive operation: the safe reading of an unreadable
            # number is not zero.
            held.append((stage, 0))
            continue
        if count > 0:
            held.append((stage, count))
    return held


def _unlink(path: Path) -> bool:
    """Delete a file, reporting whether one was there. Absence is not a failure.

    A card recorded by `emit` rather than captured has no photo and no sidecar, and an undo
    of one must answer 200 rather than a 500 that reads like a bug in this file. Caught
    rather than probed with `is_file()` so there is no window between the two calls — the
    store lock closes that window for other writers, but not for the operator's own Finder.
    """
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def _position_int(value, where: str) -> int:
    """Coerce a stored box or index for the two destructive box walks, or refuse.

    `store/master.py:_as_position_int` with the same message shape and the same public
    exception, restated rather than imported because that name is private and `_history`'s
    docstring already argues why this file does not reach across the package for privates.
    The rule it enforces is `next_index`'s: an unreadable record REFUSES the scan rather
    than being skipped past, because a walk that renumbers or deletes around a record it
    could not read either strands it or collides with it, silently, later. `BadPosition`
    reaches the dispatcher as `inventory_conflict`.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        raise master.BadPosition(f"{where} is {value!r}, which is not an integer") from None


def _drop_from_stores(snapshot, key: str) -> Tuple[bool, bool, bool]:
    """Pop one position's queue entries and its paid answer. `(review, parked, cache)`.

    THE OTHER THREE STORES ARE KEYED BY POSITION TOO, and this is the whole of what made
    the undo route leave wreckage before it existed. Measured before it was written: after
    undoing 3/2 the record, the photo and the sidecar were gone, while `review.json` still
    held an entry whose `photo` field named the file the route had just deleted,
    `identifications.json` still held the paid answer, and `GET /status` went on counting
    the phantom in `queues.review`. The orphan was PERMANENT rather than untidy: a
    position with no photo is never scanned, so never processed, so never released by
    `Queue.release`.

    `entries.pop` RATHER THAN `Queue.release`, which is the method that already removes
    queue entries, and the difference is deliberate. `release` preserves anything a human
    cleared, on the stated grounds that the answer should outlive the question. Here the
    question, the card and the photograph are all going together — every caller of this
    helper is deleting the RECORD, after which the position is either released back to the
    allocator (undo), occupied by a different physical card (the mid-box shift), or gone
    with its whole box — so a preserved answer would be a human's ruling about card A
    attached to physical card B. `Cache.put` refuses to overwrite a cleared answer for the
    same reason and would be wrong here for the same reason. A stale answer on a new card
    is worse than the orphan this replaces, so removal here is unconditional.

    THREE CALLERS, ONE RULE: `do_delete_card`, `do_remove_card` and `do_delete_box`. Each
    reports what this gave up in its own response, because a route that destroys something
    says what it destroyed — and the paid answer going in the bin is the one destruction
    here that money can measure.
    """
    review_deleted = snapshot.review.entries.pop(key, None) is not None
    parked_deleted = snapshot.parked.entries.pop(key, None) is not None
    cache_deleted = snapshot.cache.entries.pop(key, None) is not None
    return review_deleted, parked_deleted, cache_deleted


def do_delete_card(box: int, index: int) -> dict:
    """Undo one capture: the record, the queue entries and the paid answer, then the files.

    IT DELETES AND IT DOES NOT TOMBSTONE (D10). No `undone` state, no deleted flag, nothing
    in the response hinting at a third condition between captured and absent. `sold` stays
    the only way a position stops being listable while keeping its record, and it means
    sold. A soft delete was rejected in the spec rather than here, and the reason is that it
    puts a record in `inventory.json` that every consumer downstream has to learn to skip.

    ONLY THE NEWEST CARD IN THE BOX. `next_index` is a high-water mark, so deleting from the
    middle leaves a gap that can never be reused and that reads, a year later, exactly like
    the permanent gap a sale leaves. The refusal names the position that *is* undoable,
    because a refusal that does not say what would have worked costs a round trip. Deleting
    the newest releases its index instead, and that release is the allocator's own
    behaviour rather than anything arranged here: the high-water scan simply stops finding
    the record. T7 asserts it against `Inventory.next_index` directly for that reason.

    ONLY A `captured` CARD, SINCE THE OWNER'S RULING OF 2026-08-23 (D10, ruling 2). This
    route reached `identified` for as long as it existed — the fee was spent, nothing
    outside this Mac knew the card — and the ruling reverses that: once a card has been
    identified it has made it into inventory proper, and the capture screen's rapid-fire
    undo may not reach it. The boundary is the state, not the money. An identified card's
    remedies are the ones built for it, and the `undo_too_late` refusal names all three:
    re-shoot in place (`POST .../photo`), retire (`POST .../retire`), or the mid-box
    delete with its contiguous shift (`POST .../remove`), where that route's own bounds
    allow. `UNDOABLE_STATES` carries the rest of the argument.

    REPEATED CALLS WALK BACKWARDS, one card each, and that costs no code — every call
    deletes whatever is newest by the time it runs.

    IT CLEARS ALL FOUR STORES KEYED BY THIS POSITION, not just the inventory. The snapshot
    carries `review`, `parked` and `cache` as well, and `Store.write()` writes every one of
    them back on the way out — so dropping the record alone does not leave the others
    untouched, it commits them unchanged around a position that no longer exists. Details
    below, at the code.

    ONE `Store.write()`, the same shape `do_capture` uses — and it is NOT a transaction
    spanning the store and the filesystem, because no such thing is available here. What is
    actually guaranteed, stated exactly rather than as "atomic":

      a failing unlink        escapes the block, so nothing commits. Every edit above is
                              discarded, the record keeps its photo, and the request can be
                              repeated.
      a failure in the        leaves the record in place with its photo already gone. Undo
      commit, after the       again repairs it: the card is still the newest, still in an
      unlinks have run        undoable state, and `_unlink` treats an absent file as no
                              failure — so the retry commits what the first attempt could
                              not.

    THE FILESYSTEM WORK IS DELIBERATELY NOT MOVED AFTER THE BLOCK, which would make the
    first row cover everything and is the obvious repair. Outside the block it runs after
    the commit, and then a partial failure strands a PHOTO with no record —
    `identify.sidecar.scan` finds captures by photo suffix, so that orphan is a paid Batch
    request for a card nothing else knows about, silent until the bill. The
    record-without-photo above costs nothing and heals on a retry. Cheap and retryable beats
    expensive and silent.

    The limit underneath all of it, from `docs/specs/capture-server.md` §6.5: the session
    replaces four JSON files and appends history after the yield, each atomically but not
    together. The commit is per file, so this route cannot promise more than the rows above
    however it is ordered.

    THE PHOTO IS UNLINKED BEFORE THE SIDECAR, and that ordering is the money rule from the
    other direction. `identify.sidecar.scan` finds captures by photo suffix and reads
    sidecars beside them, so a stranded sidecar costs nothing while a stranded PHOTO is a
    paid Batch request for a card that no longer exists. Deleting the expensive one first
    means every partial failure left after it is a cheap one.

    IT APPENDS A `removed` EVENT, WHICH `docs/DEBTS.md` SPENT A PARAGRAPH ARGUING AGAINST,
    and the argument does not survive the index release two paragraphs above. What it said:
    naming a transition for a record that no longer exists reads as the tombstone
    `docs/specs/capture-app.md` section 3 forbids. A tombstone is a record left in
    `inventory.json` that every consumer downstream has to learn to skip, and there is still
    none — the card map has no key for this position, and nothing in the response hints at a
    third condition between captured and absent. `history.jsonl` is a different kind of file:
    append-only, and already holding the `captured` event for a record that is gone. The
    question was never whether it may describe a deleted card. It is whether it may describe
    one *once* and then stop.

    THE DECIDING FACT IS THAT THE POSITION IS REUSED. D10 settles undo as a delete precisely
    so the released index goes to the next capture, so without this line the log reads
    `captured 3/2`, `captured 3/2`, with nothing between them — one key over two physical
    cards, indistinguishable from a re-record of one. D10's first paragraph is what makes a
    printed position label worth trusting a year later; this event is that same guarantee for
    the only file that holds a box over time, and it is the boundary between the two cards.

    THE NAME IS `removed` AND NOT `undone`. `undone` names the button, which is a fact about
    a screen; this names what happened to the record. It is also deliberately outside
    `master.STATES` — see `SERVER_EVENTS` — so nothing can read it as the third state D10
    refuses.
    """
    key = master.position_key(box, index)

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        card = inventory.cards.get(key)
        # The high-water mark minus one: the newest card in this box, or 0 if it is empty.
        # Read inside the lock like everything else here — a value read before it would be
        # a stale claim about which position is undoable.
        newest = inventory.next_index(box) - 1

        if card is None:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "card_not_found",
                f"No card at box {box}, card {index}. "
                + (
                    f"The newest capture in that box is card {newest}."
                    if newest >= 1
                    else "That box holds no cards at all."
                ),
            )

        # STATE AND LISTING ARE BOTH CHECKED BEFORE POSITION, deliberately, and the second
        # of them inherits the argument the first was written with. The other order answers a
        # request to undo a listed card in the middle of a box with "card 12 is the newest,
        # undo that instead" — which invites the operator to delete good captures one at a
        # time on the way to one that could never have been removed at all.
        if card.state not in UNDOABLE_STATES:
            # ONE CODE, AND THE MESSAGE NAMES THE REMEDY THE STATE ACTUALLY HAS. For the two
            # terminal states the departure this record holds is reversed on its own route —
            # the sale's, or since D26 the retirement's — never by deleting the record of
            # it; "reverse the sale" on a retired card would send the operator to a route
            # that will refuse. For `identified` — refused here since 2026-08-23 (D10,
            # ruling 2) — there are three remedies and the message names all of them,
            # because which one is right depends on what is wrong with the card, and only
            # the operator knows that.
            if card.state == master.IDENTIFIED:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "undo_too_late",
                    f"Box {box}, card {index} is identified — it has made it into "
                    f"inventory proper, and undo stops at `captured` (D10, ruling 2, "
                    f"2026-08-23). What is wrong with it decides the remedy: a bad photo "
                    f"is re-shot in place (POST /inventory/{box}/{index}/photo), a card "
                    f"that has left the box is retired "
                    f"(POST /inventory/{box}/{index}/retire), and a junk record is "
                    f"deleted with the cards behind it slid forward "
                    f"(POST /inventory/{box}/{index}/remove) — allowed while every "
                    f"higher card in box {box} is still unsold, unretired and unlisted.",
                )
            departure, route = (
                ("a retirement", "retire")
                if card.state == master.RETIRED
                else ("a sale", "sold")
            )
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "undo_too_late",
                f"Box {box}, card {index} is {card.state}, and {departure} is not undone "
                f"by deleting the card that left. Undo removes a capture that was never "
                f"listed — it reaches {' and '.join(UNDOABLE_STATES)} only. Send "
                f"{{\"undo\": true}} to `/inventory/{box}/{index}/{route}` to reverse it, "
                f"and leave the position alone.",
            )

        # THE SECOND HALF OF THE SAME REFUSAL, and it is the half that used to be the state
        # check above. `_listing_hold` has the argument in full; the short version is that
        # `pushed` stopped being a card state in v2, so "has this card's row been emitted"
        # is now a question about `inventory.listings` and this is where it gets asked.
        # Same code, because the reason has not changed — only where the fact lives.
        held = _listing_hold(inventory, card)
        if held:
            summary = ", ".join(f"{count} {stage}" for stage, count in held)
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "undo_too_late",
                f"Box {box}, card {index} is one copy of SKU {card.sku}, and that SKU is "
                f"already out of this Mac: {summary}. Deleting this copy here would leave "
                f"an import file — and then TCGplayer — disagreeing with the inventory, and "
                f"the listing counts claiming a copy that is no longer in the box. Undo "
                f"stops at `emit`. Pull the listing on TCGplayer, or mark this copy sold "
                f"if it has left; either way, leave the position alone.",
            )

        if int(index) != newest:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "undo_not_newest",
                f"Box {box}, card {index} is not the newest capture, and a position is "
                f"never reused once it is passed. Undo removes box {box}, card {newest}; "
                f"press it again to walk back one card at a time.",
            )

        photo = photo_path(card.box, card.index)
        sidecar = sidecar_path(photo)

        # `card.photo` is deliberately not consulted as the path to delete. The layout is
        # derived from the position, the same way `do_put_card` derives it, because that is
        # the one layout this server ever writes — and a record created by `emit` carries a
        # null photo while a stale absolute path from another machine's store would send
        # this at a file that is not ours.
        del inventory.cards[key]

        # `_drop_from_stores` has the argument in full — the wreckage undo used to leave in
        # the queue files and the answer cache, and why the pops are unconditional where
        # `Queue.release` would preserve a cleared entry. The overlap that makes it live on
        # THIS route narrowed with ruling 2 but did not close: a queued card is usually
        # `identified`, which now refuses above, but a card whose identification FAILED —
        # `identification_failed`, `card_not_detected` — queues while still `captured`, and
        # that is exactly the junk capture this route exists to walk back.
        review_deleted, parked_deleted, cache_deleted = _drop_from_stores(snapshot, key)

        photo_deleted = _unlink(photo)
        sidecar_deleted = _unlink(sidecar)
        released = inventory.next_index(box)

        # LOGGED LAST, after every deletion this route performs, so the line describes work
        # that actually happened rather than work that was about to be attempted. It commits
        # with them or not at all — `_history` has why that is a property of where it appends
        # and not of this ordering.
        #
        # WHAT IT CARRIES IS WHAT COST SOMETHING. The state at removal says whether an
        # identification fee was spent on this photograph; `sku` and `run` say what the
        # pipeline had already concluded about it, and both drop out for a card that was
        # never identified. `cache_deleted` is the paid answer going in the bin, which is the
        # one destruction here that money can measure — the two queue booleans in the
        # response are about a question rather than about the card, and a discarded question
        # leaves nothing to reconcile against later. The photo path is not carried: it is
        # derived from the position, and naming a file that this route has just deleted only
        # invites a reader to go looking for it.
        _history(
            inventory,
            REMOVED,
            key,
            state=card.state,
            sku=card.sku,
            run=card.run,
            cache_deleted=cache_deleted,
        )

    return {
        "deleted": key,
        "box": int(box),
        "index": int(index),
        "photo_deleted": photo_deleted,
        "sidecar_deleted": sidecar_deleted,
        # What the other three stores gave up, reported the same way and for the same
        # reason: an undo says what it destroyed, and a card that was sitting in a review
        # queue with a paid answer against it is the case where that matters most. Booleans
        # rather than counts, because each of these files holds at most one entry per
        # position — a count could only ever be 0 or 1, and printing it as a number invites
        # the next reader to believe otherwise.
        "review_deleted": review_deleted,
        "parked_deleted": parked_deleted,
        "cache_deleted": cache_deleted,
        # The index this box will hand out next, after the release. The app redraws its
        # position from this rather than decrementing its own counter, which would drift the
        # moment the other device (D13) captured into the same box.
        "next_index": released,
    }


def do_remove_card(box: int, index: int, payload: dict) -> dict:
    """Delete one capture mid-box and slide every higher card down one index. D10, ruling 1.

    THE ONE SANCTIONED RENUMBER. "Nothing that renumbers may exist" stood from the day D10
    was written until 2026-08-23, and the owner's ruling overrules it for exactly one case:
    a junk capture pulled out of a contiguous stack of uncommitted cards, where the cards
    behind it really do slide forward — the digital operation is the physical truth of it.
    The BOUNDARY is what keeps the old rule's reason alive, and it is checked before
    anything is touched: every higher-index card in this box must be `captured` or
    `identified` with no listing hold. A sold or retired gap above refuses
    (`renumber_blocked`), because shifting across it would close a gap that means
    something; a listed SKU above refuses the same way, because its row is already in a
    file that names its position. Below the deleted index nothing moves, so gaps down
    there keep meaning what they meant.

    THE TARGET ITSELF answers by its own doors: a sold card refuses as `card_sold` and a
    retired one as `card_retired` — deleting either would erase the record of a departure
    (D10 makes those gaps permanent on purpose) — and a listing-held target refuses as
    `card_listed`, `_listing_hold`'s argument verbatim. `captured` and `identified` both
    pass, which is half of what ruling 2 means by pointing an identified card here.

    THE BODY IS AN AIM CHECK. `capture_id` is required — the target's own id, or null for
    a record that predates ids — and a mismatch refuses (`capture_id_mismatch`). The shift
    is the reason: after it runs, a DIFFERENT physical card sits at the deleted index, so
    a replayed request after a lost response, or a screen aiming off a stale read of the
    box, would delete the neighbour that slid in. The undo route needs no such check
    because its replay finds nothing at the deleted position and refuses on its own; this
    route's replay would find a card. The one target this cannot protect is a pre-server
    record with no id whose upstairs neighbour also has none — named here rather than
    papered over, because both halves of that are records this server never wrote.

    FILES MOVE FIRST, INSIDE THE BLOCK, ASCENDING — and the ordering argument is
    `do_delete_card`'s money rule extended to a rename. The session commits records only
    at block exit, so a crash mid-shift discards every record edit while leaving some
    photos already at their new names. Three properties make that recoverable rather than
    wrong:

      the first rename CONSUMES the target's photo   `os.replace(N+1 -> N)` atomically
                                                     overwrites the doomed file. Nothing
                                                     ever unlinks the target's photo while
                                                     there are cards to shift, so no retry
                                                     can blindly unlink a slot that a
                                                     partial shift has already refilled
                                                     with a NEIGHBOUR's photo — the one
                                                     ordering that destroys a photo of a
                                                     card that still exists.
      a rename RESUMES rather than repeating         source missing while the record says
                                                     the card has a photo means an earlier
                                                     attempt already moved it; the loop
                                                     takes the destination as done and
                                                     walks on. The RECORD is what breaks
                                                     the tie — a card that never had a
                                                     photo is distinguishable from one
                                                     whose photo has already moved, which
                                                     is what makes the retry safe where a
                                                     bare `is_file()` probe would misread
                                                     the target's leftovers as a moved
                                                     photo.
      sidecars are REGENERATED, not renamed          written whole from the record at the
                                                     new index (`write_atomic`), old one
                                                     unlinked after — idempotent on a
                                                     retry, and the reader can never find
                                                     a sidecar whose `index` disagrees
                                                     with its filename.

    What a crash between renames costs, stated exactly: until the operation is retried to
    completion, records point at photo names a partial shift has already moved, so an
    identify run in that window would attribute photos one position off. The window is
    closed by retrying the remove, which the `capture_id` check permits precisely because
    the store was never committed. Past the block, the commit is per file (capture-server
    spec §6.5), exactly as every other route here — this one cannot promise more.

    EVERYTHING KEYED BY A SHIFTED POSITION MOVES WITH IT: record key and its `box`/`index`
    fields, photo, sidecar, queue entries (`position`, `box`, `index`, the rendered
    `label`, and `photo` re-pointed), cache entries re-keyed. `capture_id`s ride along
    untouched — they name photographs, and no photograph changed. A CLEARED queue entry
    moves too, flag intact: the answer is about the physical card, and the physical card
    is what slid down.

    TWO HISTORY LINES, COMMITTED WITH THE CHANGE OR NOT AT ALL: `removed` for the target —
    same shape as undo's, because the same thing happened to that record — and
    `renumbered` carrying the whole mapping compactly (`from`, `count`: minus-one for
    every index above `from`). Without the second line, every earlier `history.jsonl`
    line about a shifted position silently changes subject.
    """
    _reject_unknown(payload, REMOVE_FIELDS)
    if "capture_id" not in payload:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "capture_id_required",
            "Send the target's own capture_id — the one its inventory row carries, or "
            "null for a record that predates capture ids. It is what stops a stale or "
            "replayed request from deleting the card that slid into this position.",
        )
    aimed_at = _optional_text(payload, "capture_id")

    key = master.position_key(box, index)

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        card = inventory.cards.get(key)
        if card is None:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "card_not_found",
                f"No card at box {box}, card {index}. This route deletes a record that "
                f"exists; there is nothing here to shift onto.",
            )
        if card.state == master.SOLD:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "card_sold",
                f"Box {box}, card {index} is sold, and its gap is the permanent record of "
                f"that sale (D10) — deleting it would erase a departure and renumber the "
                f"cards behind a slot that must keep meaning what it means. If the sale "
                f"was recorded in error, send {{\"undo\": true}} to "
                f"`/inventory/{box}/{index}/sold` first.",
            )
        if card.state == master.RETIRED:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "card_retired",
                f"Box {box}, card {index} is retired ({card.retire_reason}) — it left "
                f"inventory by its own door, and that departure keeps its record and its "
                f"permanent gap (D26). If it is back in the box, send "
                f"{{\"undo\": true}} to `/inventory/{box}/{index}/retire` first.",
            )
        if card.state == master.MOVED:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "card_moved",
                f"Box {box}, card {index} was moved to {card.moved_to} (D83) — this key is "
                f"a permanent tombstone, the same as a sold or retired one, and deleting it "
                f"would put a future capture into a box this card's own history still "
                f"claims. The card itself is not gone: move the transplant at "
                f"{card.moved_to} instead.",
            )
        held = _listing_hold(inventory, card)
        if held:
            summary = ", ".join(f"{count} {stage}" for stage, count in held)
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "card_listed",
                f"Box {box}, card {index} is one copy of SKU {card.sku}, and that SKU is "
                f"already out of this Mac: {summary}. Deleting this copy would leave an "
                f"import file — and then TCGplayer — disagreeing with the inventory. Pull "
                f"the listing on TCGplayer and reconcile, or mark this copy sold if it "
                f"has left; either way, leave the position alone.",
            )
        if (card.capture_id or None) != aimed_at:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "capture_id_mismatch",
                f"The card at box {box}, card {index} is not the one this request "
                f"describes — its capture_id is {card.capture_id!r}, not {aimed_at!r}. "
                f"The box has probably shifted since it was read. Re-read the inventory "
                f"and aim again; nothing was deleted.",
            )

        # The layout, validated BEFORE any file is touched — `BadSections` escapes as
        # `sections_invalid`, and a refusal that early burns nothing.
        #
        # ITS ORIGINAL REASON IS GONE AND THE CALL IS KEPT DELIBERATELY (D92). This read
        # "every re-keyed queue entry carries a rendered label, and a layout that will not
        # validate means the labels this shift would write are unknowable" — and no label is
        # written here any more, so that sentence is void. What remains is a narrower claim
        # this route can still make honestly: a box whose dividers will not parse is a box
        # whose cards cannot be LABELLED after the shift either, by `_queue_row` or by
        # `_box_view`, and renumbering into that state quietly is worse than refusing.
        #
        # Kept rather than dropped because deleting a refusal is a wider decision than the
        # one D92 took, and nothing asserts this one — no harness case reaches
        # `sections_invalid` through this route, so its removal would have been invisible.
        # The result is unbound because nothing reads it; the call is here for the raise.
        inventory.sections_for(box)

        # EVERY RECORD IN THIS BOX ABOVE THE TARGET, coerced the way `next_index` coerces —
        # and like that scan, an unparsable record REFUSES rather than being skipped
        # (`BadPosition` escapes as `inventory_conflict`). Skipping one would renumber
        # around a record that may well be in this box, and the collision lands later, on
        # the allocator, against a printed label.
        movers: List[Tuple[int, str, master.Card]] = []
        blockers: List[Tuple[int, str]] = []
        for at, other_key, other in inventory.records_in(box):
            if at <= int(index):
                continue
            movers.append((at, other_key, other))
            if other.state in master.TERMINAL_STATES:
                gone = (
                    f"retired: {other.retire_reason}"
                    if other.state == master.RETIRED
                    else "sold"
                )
                blockers.append((at, f"card {at} is {gone}"))
            else:
                other_held = _listing_hold(inventory, other)
                if other_held:
                    other_summary = ", ".join(
                        f"{count} {stage}" for stage, count in other_held
                    )
                    blockers.append(
                        (at, f"card {at} is one copy of SKU {other.sku} ({other_summary})")
                    )
        if blockers:
            blockers.sort()
            named = "; ".join(text for _, text in blockers[:8])
            more = f"; and {len(blockers) - 8} more" if len(blockers) > 8 else ""
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "renumber_blocked",
                f"Deleting box {box}, card {index} would renumber every higher card in "
                f"the box, and that shift is blocked: {named}{more}. A sold or retired "
                f"gap up there is a permanent record a shift would close, and a listed "
                f"copy's position is already in a file (D10, ruling 1). Reverse a "
                f"departure recorded in error on its own route, wait for held listings "
                f"to reconcile away — or leave the gap, which is D10's default answer.",
            )
        movers.sort()

        # ------------------------------------------------------------------- the files
        target_photo = photo_path(box, index)
        target_sidecar = sidecar_path(target_photo)
        photo_deleted = target_photo.is_file()
        sidecar_deleted = target_sidecar.is_file()

        if not movers:
            # The target is the top of its box: nothing shifts, and the files go the way
            # undo's do — photo before sidecar, the money rule, so any partial failure
            # left behind is a cheap one.
            photo_deleted = _unlink(target_photo)
            sidecar_deleted = _unlink(target_sidecar)
        else:
            for at, _, other in movers:
                src = photo_path(box, at)
                dst = photo_path(box, at - 1)
                if src.is_file():
                    # Atomic on one filesystem, and on the first pass `dst` is the
                    # target's photo — consumed by overwrite, never unlinked ahead of
                    # time. On later passes `dst` was vacated by the previous rename, so
                    # the only thing this can ever clobber is a recordless orphan, which
                    # was a billable hazard anyway.
                    os.replace(src, dst)
                    moved = True
                elif other.photo:
                    # The record says this card has a photograph and the file is not at
                    # its old name: an interrupted earlier attempt already moved it, and
                    # the destination is the photograph. If it is at NEITHER name the
                    # file is genuinely gone from disk, and a renumber that cannot prove
                    # where a photo is refuses rather than guessing.
                    if not dst.is_file():
                        raise BadRequest(
                            HTTPStatus.CONFLICT,
                            "photo_missing",
                            f"Box {box}, card {at}'s record names a photo, and the file "
                            f"is at neither {src.name} nor {dst.name}. A renumber moves "
                            f"files it can prove exist — re-shoot that card "
                            f"(POST /inventory/{box}/{at}/photo) or restore the file, "
                            f"then retry. Nothing has been committed.",
                        )
                    moved = True
                else:
                    # A card that never had a photograph (recorded by `emit`, not
                    # captured). Nothing to move — and whatever target leftovers sit at
                    # `dst` still have to go, photo before sidecar as ever.
                    _unlink(dst)
                    moved = False
                if moved:
                    files.write_json(
                        sidecar_path(dst),
                        sidecar_payload(
                            box,
                            at - 1,
                            **{name: getattr(other, name) for name in CLAIM_WIRE_NAMES},
                        ),
                    )
                else:
                    _unlink(sidecar_path(dst))
                _unlink(sidecar_path(src))

        # ----------------------------------------------------------------- the records
        del inventory.cards[key]
        review_deleted, parked_deleted, cache_deleted = _drop_from_stores(snapshot, key)

        for at, old_key, other in movers:
            new_index = at - 1
            new_key = master.position_key(box, new_index)
            del inventory.cards[old_key]
            other.box = int(box)
            other.index = new_index
            dst = photo_path(box, new_index)
            # Derived fresh rather than string-edited, for `do_delete_card`'s reason: the
            # layout below `captures/cards/` is the one this server writes, and a stale
            # absolute path from another machine's store must not survive a renumber.
            other.photo = str(dst) if dst.is_file() else None
            inventory.cards[new_key] = other

            # NO LABEL IS WRITTEN HERE, AND THAT IS THE POINT (D92). This wrote one in INDEX
            # space — `join.Position` with no `occupied` — while every route serves a label
            # re-rendered in COUNT space by `_queue_row`. Nothing read it, so the wrong
            # number never reached a screen; what it left behind was a field holding a
            # plausible, wrong rendering indistinguishable from the correct ones
            # `cli/resolve.py` writes, one forgotten `places` argument away from being
            # served. D56's rule is that a rendering nobody can correct is joined at read
            # time and not stored, and `_queue_row` already does exactly that.
            for queue in (snapshot.review, snapshot.parked):
                entry = queue.entries.pop(old_key, None)
                if entry is None:
                    continue
                entry.position = new_key
                entry.box = int(box)
                entry.index = new_index
                if entry.photo:
                    entry.photo = str(dst)
                # No collision possible: `new_key`'s entry, if there was one, belonged to
                # the target (popped above) or to the previous mover (already re-keyed).
                queue.entries[new_key] = entry
            cached = snapshot.cache.entries.pop(old_key, None)
            if cached is not None:
                snapshot.cache.entries[new_key] = cached

        # ----------------------------------------------------------------- the history
        _history(
            inventory,
            REMOVED,
            key,
            state=card.state,
            sku=card.sku,
            run=card.run,
            cache_deleted=cache_deleted,
        )
        if movers:
            _history(
                inventory,
                RENUMBERED,
                key,
                box=int(box),
                count=len(movers),
                **{"from": int(index)},
            )
            # ONE STATE LINE PER SHIFTED CARD, AT ITS NEW POSITION — and this is what keeps
            # `_state_before_sale` and `_state_before_retirement` true across a renumber.
            # Both scan a POSITION's history backwards for the last state-named line, and
            # after a shift the lines under a position belong to its previous occupant.
            # Index reuse after undo never had this problem because the next occupant
            # always logs its own `captured` line; a shifted card arrives at its key
            # without one, so the roll call below is that line — the same fact
            # `record_capture` logs for a new card, stamped for a moved one. Measured
            # before this was written: a retire-then-reverse at a shifted position
            # restored the PREVIOUS occupant's state. The event name is the card's own
            # current state, which is exactly what those scans exist to find;
            # `renumbered_from` says why the line exists.
            for at, old_key, other in movers:
                _history(
                    inventory,
                    str(other.state),
                    master.position_key(box, at - 1),
                    sku=other.sku,
                    run=other.run,
                    renumbered_from=old_key,
                )
        released = inventory.next_index(box)

    return {
        "deleted": key,
        "box": int(box),
        "index": int(index),
        "photo_deleted": photo_deleted,
        "sidecar_deleted": sidecar_deleted,
        "review_deleted": review_deleted,
        "parked_deleted": parked_deleted,
        "cache_deleted": cache_deleted,
        # How many records slid down one index — 0 when the target was the top of its
        # box. The mapping is implied and total: every index above `index`, minus one.
        "shifted": len(movers),
        # The index this box hands out next. After a shift that is the old high-water
        # mark: the top slot emptied, so the box got one position shorter.
        "next_index": released,
    }


def _move_one(
    snapshot, inventory: master.Inventory, key: str, box: int, index: int, to_box: int
) -> dict:
    """One card's whole move, against an ALREADY-OPEN snapshot. `do_move_card`'s body,
    lifted out so `do_move_cards` can call it in a loop inside ONE `Store.write()` — the
    same reason `_sell` is snapshot-only rather than opening its own session.

    THE STATE CHECKS ARE ROUTE-LEVEL, NOT `Inventory.move_card`'s, mirroring
    `do_remove_card`'s three-way check rather than leaning on the generic `CardDeparted`
    that method itself raises as a backstop. The reason is the same one every other
    terminal-state refusal in this file gives: a person reading `card_sold` knows to send
    `undo` to `/sold` first, and `card_departed` naming nothing would send them hunting.
    `CardNotFound`/`CardDeparted`/`BoxClosed`/`PositionOccupied` still reach `_dispatch`'s
    generic handlers for any caller that skips these checks — store/master.py's own
    defense, not duplicated here, just not solely relied upon.

    FILES MOVE AFTER THE STORE CALL, not before, and that is a real difference from
    `do_remove_card`'s "files first" rule — worth stating rather than silently diverging.
    That rule exists because the shift's destination indices are deterministic (`at - 1`)
    before a single record is touched. This move's destination index is not knowable until
    `Inventory.move_card` allocates it, so the file move necessarily comes after. What this
    costs, named rather than engineered around: a crash between the successful file rename
    and this block's commit leaves a photo at the new path while `inventory.json` on disk
    still names the old one. Recovery is manual in that narrow window — move the file back,
    or finish the record side by hand — the same class of accepted risk this file already
    takes with `_sale_origin`'s unlocked read, stated rather than hidden.
    """
    card = inventory.cards.get(key)
    if card is None:
        raise BadRequest(
            HTTPStatus.NOT_FOUND,
            "card_not_found",
            f"No card at box {box}, card {index}. A move relocates a card that exists.",
        )
    if card.state == master.SOLD:
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "card_sold",
            f"Box {box}, card {index} is sold, and its gap is the permanent record of "
            f"that sale (D10) — a sold card has already left through the other door. If "
            f"the sale was recorded in error, send {{\"undo\": true}} to "
            f"`/inventory/{box}/{index}/sold` first.",
        )
    if card.state == master.RETIRED:
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "card_retired",
            f"Box {box}, card {index} is retired ({card.retire_reason}) — it already "
            f"left inventory by its own door (D26). If it is back in the box, send "
            f"{{\"undo\": true}} to `/inventory/{box}/{index}/retire` first.",
        )
    if card.state == master.MOVED:
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "card_moved",
            f"Box {box}, card {index} was already moved to {card.moved_to} (D83). Move "
            f"the transplant at {card.moved_to} instead.",
        )

    had_photo = bool(card.photo)
    tombstone, transplant = inventory.move_card(key, to_box)
    new_key = transplant.key

    photo_moved = False
    sidecar_moved = False
    if had_photo:
        src = photo_path(box, index)
        dst = photo_path(transplant.box, transplant.index)
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
            photo_moved = True
        elif dst.is_file():
            # A retry of a request that already moved the file — same "source missing
            # means an earlier attempt already moved it" reasoning `do_remove_card` uses,
            # narrower here because there is only ever one destination to check.
            photo_moved = True
        else:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "photo_missing",
                f"Box {box}, card {index}'s record names a photo, and the file is at "
                f"neither its old path nor the new one. A move relocates a file it can "
                f"prove exists — re-shoot the card first, or restore the file, then "
                f"retry. Nothing has been committed.",
            )
        transplant.photo = str(dst)
        files.write_json(
            sidecar_path(dst),
            sidecar_payload(
                transplant.box,
                transplant.index,
                **{name: getattr(transplant, name) for name in CLAIM_WIRE_NAMES},
            ),
        )
        sidecar_moved = True
        _unlink(sidecar_path(src))

    # Re-keyed, not dropped — `do_remove_card`'s rule and its reason: an open review
    # question or a paid identification answer follows the physical card to its new
    # address, because the card is the same card and the question is still open.
    #
    # NO LABEL IS WRITTEN, for the reason `do_remove_card` states at its own re-key (D92):
    # this composed one in INDEX space and no route serves a stored label. A move is the
    # worse of the two cases, because the entry crosses INTO ANOTHER BOX — so the stale
    # string named a section and card number belonging to a different box's layout. The
    # `sections_for` lookup went with it; nothing else here wanted it.
    review_moved = False
    parked_moved = False
    for queue in (snapshot.review, snapshot.parked):
        entry = queue.entries.pop(key, None)
        if entry is None:
            continue
        entry.position = new_key
        entry.box = int(transplant.box)
        entry.index = transplant.index
        if entry.photo and photo_moved:
            entry.photo = transplant.photo
        queue.entries[new_key] = entry
        if queue is snapshot.review:
            review_moved = True
        else:
            parked_moved = True
    cache_moved = False
    cached = snapshot.cache.entries.pop(key, None)
    if cached is not None:
        snapshot.cache.entries[new_key] = cached
        cache_moved = True

    return {
        "moved": key,
        "to": new_key,
        "box": int(box),
        "index": int(index),
        "new_box": int(transplant.box),
        "new_index": int(transplant.index),
        "photo_moved": photo_moved,
        "sidecar_moved": sidecar_moved,
        "review_moved": review_moved,
        "parked_moved": parked_moved,
        "cache_moved": cache_moved,
    }


def do_move_card(box: int, index: int, payload: dict) -> dict:
    """Move one card to a fresh index in another box. D83 — the third door, addressed.

    A THIRD DOOR OUT OF A BOX, NOT A SHIFT. `do_remove_card` above cascades every higher
    card down one slot; this touches no card but the one named. The position at `box`,
    `index` becomes a permanent tombstone (`store/master.py:Inventory.move_card` carries
    the full argument for why: D58 already re-argued and rejected moving the stored index
    for exactly this class of change), and the card itself is recorded fresh at a newly
    allocated index in `to_box` — the ordinary `next_index` mechanism, not a slide.

    NO LISTING-HOLD GUARD, DELIBERATELY, unlike `do_remove_card`'s `card_listed` refusal.
    D7 already treats a SKU's backing copies as fungible and position-independent — which
    physical copy backs a stage is unrecorded on purpose — so a card carrying an active
    listing hold is free to change boxes; the hold travels with the transplant's `sku`
    untouched, and nothing about `_release_plan`/`_listing_hold` reads a card's box.

    UNDO IS THIS SAME ROUTE, RUN AGAIN. The transplant is not terminal, so moving it back
    is an ordinary second move — it lands at a fresh index in the original box, and the
    first tombstoned key is never reclaimed, same as any other permanent gap.

    See `_move_one` for the state checks, the file-move ordering and its one named risk.
    """
    _reject_unknown(payload, MOVE_FIELDS)
    if "capture_id" not in payload:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "capture_id_required",
            "Send the target's own capture_id — the one its inventory row carries, or "
            "null for a record that predates capture ids. It is what stops a stale or "
            "replayed request from moving the card that now sits at this position.",
        )
    aimed_at = _optional_text(payload, "capture_id")
    to_box = _require_to_box(payload)

    key = master.position_key(box, index)

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        card = inventory.cards.get(key)
        if card is not None and (card.capture_id or None) != aimed_at:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "capture_id_mismatch",
                f"The card at box {box}, card {index} is not the one this request "
                f"describes — its capture_id is {card.capture_id!r}, not {aimed_at!r}. "
                f"The box has probably shifted since it was read. Re-read the inventory "
                f"and aim again; nothing was moved.",
            )
        result = _move_one(snapshot, inventory, key, box, index, to_box)
        result["card"] = _card_row(
            inventory, result["new_box"], result["new_index"],
            inventory.cards[result["to"]],
        )

    return result


def _require_to_box(payload: dict) -> int:
    raw = payload.get("to_box")
    if raw is None:
        raise BadRequest(HTTPStatus.BAD_REQUEST, "to_box_required", "Send a destination box number.")
    try:
        to_box = int(raw)
    except (TypeError, ValueError):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, "to_box_invalid", f"to_box was {raw!r}; send a whole number."
        ) from None
    if to_box < 1:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, "to_box_invalid", f"to_box was {to_box}; boxes start at 1."
        )
    return to_box


def do_move_cards(box: int, payload: dict) -> dict:
    """Move several cards from `box` to `to_box` in one write. D83.

    `indices: null` MOVES EVERY ON-HAND CARD — a whole-box move, which is what a merge
    is from the caller's side: nothing about this route needs to know it is being used
    that way. `indices: [...]` is a ticked selection or a section's membership, computed
    by the caller from the box's own live rendering (`GET /boxes` already draws
    `sections_detail`) — this route trusts the list rather than recomputing section
    boundaries itself, the same trust `PUT /inventory/<box>`'s `indices` narrowing
    already extends to a caller's mass-select.

    ONE `Store.write()` FOR THE WHOLE LIST, so a crash or a refusal partway through
    leaves nothing half-migrated — every earlier card's move is discarded along with the
    one that failed, the same all-or-nothing shape `_sell` gives a multi-copy sale.

    ORDER IS THE CALLER'S, ASCENDING BY CONVENTION, AND IT IS WHAT MAKES THE LANDING
    CONTIGUOUS. Each move consumes the destination's next `next_index` in turn — see
    `store/master.py:Inventory.move_cards` — so cards sent in ascending source-index
    order land in that same relative order at the destination, with no separate
    bookkeeping for it.

    A card no longer on hand (already sold, retired, or moved by an earlier request) is
    a real refusal here, not silently skipped — `CLAUDE.md` forbids dropping a card
    without saying so, and a ticked selection that raced another session's write is
    exactly the case that refusal exists for.
    """
    _reject_unknown(payload, MOVE_CARDS_FIELDS)
    to_box = _require_to_box(payload)
    raw_indices = payload.get("indices")
    if raw_indices is not None:
        if not isinstance(raw_indices, list) or not raw_indices:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "indices_invalid",
                "indices must be a non-empty list of card numbers, or null to move "
                "every on-hand card in the box.",
            )
        try:
            wanted = sorted({int(v) for v in raw_indices})
        except (TypeError, ValueError):
            raise BadRequest(
                HTTPStatus.BAD_REQUEST, "indices_invalid", f"{raw_indices!r} is not a list of whole numbers."
            ) from None

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        if raw_indices is None:
            wanted = sorted(
                at
                for at, _, card in inventory.records_in(box)
                if card.state not in master.TERMINAL_STATES
            )
            if not wanted:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "box_empty",
                    f"Box {box} holds no on-hand cards to move.",
                )
        if int(to_box) == int(box):
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "to_box_same",
                f"to_box is box {box} itself — nothing to move.",
            )
        results = []
        for at in wanted:
            key = master.position_key(box, at)
            results.append(_move_one(snapshot, inventory, key, box, at, to_box))

    return {
        "box": int(box),
        "to_box": int(to_box),
        "moved": len(results),
        "cards": results,
    }


def _release_plan(inventory: master.Inventory, box: int) -> Tuple[List[dict], dict]:
    """What a release from this box WOULD do, per SKU. Read-only; the one source for both.

    ONE FUNCTION BECAUSE TWO ROUTES NEED THE SAME ANSWER, and D33 already learned this the
    expensive way about money: the preflight and the act must be the same arithmetic, or the
    number on screen is a second implementation that is free to be wrong. `do_box_listings`
    renders this and `do_release_box_listings` executes it, and neither computes anything the
    other does not.

    IT SIMULATES BY COPYING THE RECORD AND CALLING THE REAL METHOD. `dataclasses.replace`
    gives a detached `Listing`; `Listing.release` runs on the copy exactly as it will run on
    the original. A re-implementation of the least-committed-first walk would be the same
    second implementation one layer down — this way the preview cannot drift from the write
    even if that method's ordering rule changes.

    THE BUDGET IS THE BOX'S UNSOLD COPIES, WHICH IS THE OWNER'S RULING OF 2026-08-24.
    `TERMINAL_STATES` are excluded because a sold or retired copy has already left: a sale
    is counted against `live` where there is a record to count it against (D7, D115), and a departed card is not one of the copies a
    remaining commitment could be backed by. It is also what the operator counts when they
    look in the box, which is the number they will check this screen against.
    """
    copies_here: Dict[str, int] = {}
    elsewhere: Dict[str, Dict[int, int]] = {}
    for card_key, card in inventory.cards.items():
        if not card.sku:
            continue
        at_box = _position_int(card.box, f"box of card {card_key}")
        if card.state in master.TERMINAL_STATES:
            continue
        sku = str(card.sku)
        if at_box == int(box):
            copies_here[sku] = copies_here.get(sku, 0) + 1
        else:
            elsewhere.setdefault(sku, {})
            elsewhere[sku][at_box] = elsewhere[sku].get(at_box, 0) + 1

    rows: List[dict] = []
    for sku in sorted(copies_here):
        entry = inventory.listings.get(sku)
        if entry is None or not _stages_held(entry):
            continue
        before = {stage: max(0, int(getattr(entry, stage) or 0)) for stage in master.LISTING_STAGES}
        gave = replace(entry).release(copies_here[sku])
        after = {stage: before[stage] - gave.get(stage, 0) for stage in master.LISTING_STAGES}
        rows.append(
            {
                "sku": sku,
                "condition": entry.condition,
                "copies_here": copies_here[sku],
                "before": {k: v for k, v in before.items() if v},
                "releases": gave,
                "after": {k: v for k, v in after.items() if v},
                # THE FIELD THE WHOLE PREFLIGHT EXISTS FOR. A shared SKU leaves a remainder,
                # and a remainder keeps `_listing_hold` non-empty — so the box stays refused
                # even after a successful release. Discovering that at the press is what the
                # owner's ruling asked to fix.
                "still_held": any(after.values()),
                "also_in_boxes": [
                    {"box": at, "copies": n}
                    for at, n in sorted(elsewhere.get(sku, {}).items())
                ],
            }
        )

    totals = {stage: 0 for stage in master.LISTING_STAGES}
    for row in rows:
        for stage, count in row["releases"].items():
            totals[stage] += count
    reached = sorted({e["box"] for row in rows for e in row["also_in_boxes"]})
    summary = {
        "box": int(box),
        "skus": len(rows),
        "releases": {stage: count for stage, count in totals.items() if count},
        "still_held": [row["sku"] for row in rows if row["still_held"]],
        "also_in_boxes": reached,
        # Whether the box would actually become deletable. NOT the same as "something was
        # released": a box every one of whose SKUs is shared can release real copies and stay
        # refused, which is precisely the case this flag is here to state up front.
        "frees_box": bool(rows) and not any(row["still_held"] for row in rows),
    }
    return rows, summary


def do_box_listings(box: int) -> dict:
    """What this box's SKUs are believed to be holding, and what a release would give up.

    FREE, READ-ONLY, AND THE STEP THAT COMES FIRST. D33's shape one register down: the money
    route has a preflight that creates no run, and this is the same idea applied to a claim
    instead of an invoice. The screen draws this on opening the panel, and the control that
    releases does not exist until it has answered — so the SKUs, the counts and the boxes the
    release will reach are unavoidably on screen before anything can be pressed.

    IT EXISTS BECAUSE THE FIRST BUILD PUT THE BLAST RADIUS IN THE RECEIPT. `also_in_boxes` was
    reported honestly and reported too late: an operator releasing from box 1's header learned
    that box 3 was involved after the write. The owner asked for it moved ahead of the press,
    and moving it is what turned this into two routes rather than one.

    NO REFUSAL FOR AN EMPTY ANSWER. Unlike the release it feeds, this is a read, and a box
    holding no listing is a perfectly ordinary thing for a screen to ask about — most boxes
    are that. It answers with zero rows and the screen draws nothing.
    """
    # LOCK-FREE, like `do_boxes` above and for its reason: this is a read, and the plan it
    # builds is re-computed under the lock by the release itself before anything is written.
    inventory = Store().read().inventory
    if inventory.box(box) is None and not _box_holds_cards(inventory, box):
        raise BadRequest(
            HTTPStatus.NOT_FOUND,
            "box_not_found",
            f"No box {box} — nothing registered under that number and no card names it.",
        )
    rows, summary = _release_plan(inventory, box)
    return {**summary, "listings": rows}


def do_release_box_listings(box: int, payload: dict) -> dict:
    """Give up what this box's copies could account for, on the operator's word. D34.

    THE OTHER HALF OF `box_not_empty_of_commitments`, and it exists because that refusal had
    two grounds and one door. A box held open by a SOLD or RETIRED card has a way out: `/sold`
    and `/retire` both reverse, and the refusal names them. A box held open by a LISTING had
    none — `staged` is drawn down in exactly one place, `cli/cmd_join.py`, by the rise in live
    quantity a fresh Filtered Export reports, which is the right answer for an import that
    lands and no answer at all for one that does not. `Listing.release` carries the full
    account of how that stranded box 1's 53 cards behind 45 records claiming staged copies
    TCGplayer had not held for two days.

    IT ASSERTS RATHER THAN MEASURES, WHICH DECIDES EVERY OTHER CHOICE HERE. No export this
    pipeline reads can say "nothing is staged" (see `Listing.release`), so the operator
    standing in front of TCGplayer is the only available authority — and a route whose whole
    content is a human's claim owes three things it would not otherwise owe:

      `confirm: true`, required          D33's field and its argument, one register down.
                                         That route refuses without it because the next thing
                                         that happens costs money; this one refuses because
                                         the next thing that happens is a fact being recorded
                                         on somebody's word.
      a history line, always             `LISTINGS_RELEASED`. After this write there is no
                                         other evidence the counts ever stood, and a box
                                         deleted straight afterwards takes the cards that
                                         would have implied them.
      the plan, ahead of the press       `do_box_listings` above, which the screen must draw
                                         first. Both come from `_release_plan`, so the
                                         preview and the write are one arithmetic.

    THE BUDGET IS PER BOX, AND THAT IS WHAT THIS ROUTE PROMISES. Each SKU gives up at most the
    number of unsold copies THIS box holds. A release reached from box 1 therefore cannot give
    up a commitment only box 3's copies could account for — structurally, not by care. Where
    that leaves a remainder the box stays refused, `still_held` says so before and after, and
    that is the honest outcome rather than a failure of the route.

    THIS IS NOT SCOPED TO DELETABLE CARDS in one direction and is scoped in another, which is
    worth stating because the two look inconsistent and are not. Terminal copies do not COUNT
    toward the budget — a sold card has left and is not backing anything — but this route does
    not care whether the box is otherwise deletable, because releasing a stale listing is
    worth doing on a box nobody is deleting at all.

    `nothing_to_release` RATHER THAN A 200 OF ZEROS. A no-op that answers 200 invites a screen
    that offers the control when there is nothing to release, and then an operator who presses
    it and cannot tell whether it worked. The control is drawn from the same plan this refusal
    is computed from, so in ordinary use it is unreachable — it is here for the replayed
    request and the stale screen, which is exactly when a cheerful 200 would be a lie.

    NO FILES ARE TOUCHED AND NO RECORD MOVES. Unlike its neighbours in this file this route
    deletes nothing: it edits counts and appends one line. It is the one destructive-adjacent
    operation here that a mistake does not make unrecoverable — the counts are re-established
    by staging again. That is why the screen gates it with a press over a preflight and not
    with the typed box number the delete demands: the gesture should be as heavy as the act.
    """
    _reject_unknown(payload, RELEASE_FIELDS)
    if payload.get("confirm") is not True:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "Releasing a listing hold records your word that TCGplayer is holding none of "
            "these copies — nothing here can check it. Send `confirm: true`, and show the "
            "plan from GET /boxes/<box>/listings first.",
        )

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        if inventory.box(box) is None and not _box_holds_cards(inventory, box):
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "box_not_found",
                f"No box {box} — nothing registered under that number and no card names "
                f"it. There is nothing here to release.",
            )

        rows, summary = _release_plan(inventory, box)
        if not rows:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "nothing_to_release",
                f"Box {box} holds no listing at any stage: there is nothing to release. If "
                f"the box is still refusing to delete, what is holding it is a sold or "
                f"retired card, and those reverse on their own routes.",
            )

        gave: Dict[str, int] = {stage: 0 for stage in master.LISTING_STAGES}
        for row in rows:
            # The SAME budget the plan was computed from, applied to the real record. The
            # plan ran `Listing.release` on a copy, so this cannot diverge from what the
            # screen showed unless the store changed under the lock — which it cannot,
            # because both reads happen inside it.
            for stage, count in inventory.listings[row["sku"]].release(row["copies_here"]).items():
                gave[stage] += count

        _history(
            inventory,
            LISTINGS_RELEASED,
            None,
            box=int(box),
            skus=len(rows),
            copies={stage: count for stage, count in gave.items() if count},
            # Named on the line because it is the half a later reader cannot re-derive: the
            # counts that remain belong to SKUs this box shares, and without it the log would
            # say a release happened and not that it was partial.
            still_held=summary["still_held"] or None,
        )
        stages = inventory.listing_counts()

    return {
        "box": int(box),
        "released": len(rows),
        # Every SKU touched, with what each gave up and what it kept. The whole list rather
        # than a sample: it is what makes the claim checkable against TCGplayer afterwards.
        "listings": rows,
        "skus": [row["sku"] for row in rows],
        "given_up": {stage: count for stage, count in gave.items() if count},
        "still_held": summary["still_held"],
        "frees_box": summary["frees_box"],
        "also_in_boxes": summary["also_in_boxes"],
        # Store-wide totals after, the same closing line `join` and `reconcile` print.
        "listings_after": {stage: count for stage, count in stages.items() if count},
    }


def _reclaimable(inventory: master.Inventory, box: int) -> Tuple[list, list]:
    """`(reclaimable, reclaimed)` — the sold cards in `box` whose photograph is still on disk,
    each as `(index, key, card, path, bytes)`, and the ones already reclaimed as `(index, key,
    card)`. One walk, shared by the count and the write so the two cannot disagree (D89).

    SOLD ONLY, AND THE OTHER DOORS ARE LEFT ALONE ON PURPOSE. A retired card's photograph is
    what lets the retirement be questioned later (D26); a moved tombstone has none; a card on
    hand is a card whose photograph the pull preview exists to show (D6). The owner's ruling
    is "photos are disposable once a card is sold through", and this is that sentence and no
    wider.

    A STAT PER SOLD CARD, not `bool(card.photo)`: `_copy_row` records why — the field and the
    file come apart in both directions — and here the file is the thing being deleted, so
    the file is what is counted.
    """
    reclaimable = []
    reclaimed = []
    for at, key, card in inventory.records_in(box):
        if card.state != master.SOLD:
            continue
        if card.photo_reclaimed_at:
            reclaimed.append((at, key, card))
            continue
        path = photo_path(box, at)
        try:
            size = path.stat().st_size
        except OSError:
            continue
        reclaimable.append((at, key, card, path, size))
    return reclaimable, reclaimed


def do_box_photos(box: int) -> dict:
    """What a reclaim over this box would delete. FREE, READ-ONLY, AND THE STEP THAT COMES
    FIRST — `do_box_listings`' shape, for `do_box_listings`' reason: the count and the bytes
    are on screen before the control that deletes them exists (D33, one register down).

    `reclaimable` is sold cards with a photograph on disk; `reclaimed` is sold cards whose
    photograph already went, with the digest each kept. `on_hand_photos` is what the box
    would still hold afterwards, so the panel can say what a reclaim does NOT touch.
    """
    inventory = Store().read().inventory
    if inventory.box(box) is None and not _box_holds_cards(inventory, box):
        raise BadRequest(
            HTTPStatus.NOT_FOUND,
            "box_not_found",
            f"No box {box} — nothing registered under that number and no card names it.",
        )
    reclaimable, reclaimed = _reclaimable(inventory, box)
    on_hand = sum(
        1 for at, _, card in inventory.records_in(box)
        if card.state not in master.TERMINAL_STATES and photo_path(box, at).is_file()
    )
    return {
        "box": int(box),
        "reclaimable": {
            "cards": len(reclaimable),
            "bytes": sum(size for *_, size in reclaimable),
            "indices": [at for at, *_ in reclaimable],
        },
        "reclaimed": {
            "cards": len(reclaimed),
            "indices": [at for at, *_ in reclaimed],
        },
        "on_hand_photos": on_hand,
    }


def do_reclaim_box_photos(box: int, payload: dict) -> dict:
    """Delete the photographs of every sold card in this box, keeping every record (D89).

    THE THIRD SHAPE, and the one this store did not have. Capture-undo deletes the record AND
    the photograph (D10); `sold` and `retired` keep both (D26). What the 100k pile needs is a
    record kept and a photograph reclaimed — measured at ~1.8 MB per photograph, ~176 GB at
    100,000 cards, and ~9 GB once the sold-through ones are gone.

    WHAT THE RECORD KEEPS IS THE DIGEST, and it is computed here, from the bytes, in the
    moment before they go. D36 makes the photograph the truth and `photo_sha256` the binding
    between a run and a slot; a box whose sold photographs are gone can no longer be checked
    that way FOR THOSE CARDS, and D89 gives that up on purpose for cards that have left the
    box. The digest on the record is what keeps the history able to say what was there, and
    what a dispute about which copy sold can still be answered with.

    FILES GO INSIDE THE LOCK, AFTER THE RECORDS ARE MARKED, PHOTO ONLY. The sidecar stays: it
    is a few hundred bytes of the operator's own claims and `identify.sidecar.scan` keys on
    the photograph, so a sidecar with no photograph beside it is inert. A crash after some
    unlinks leaves records marked for photographs that are gone — which is exactly what the
    records say — and records unmarked for photographs still there, which the next press
    finishes; `_unlink` treats absence as no failure, so a retry is safe.

    NO UNDO, AND IT GATES. The bytes are gone and the card is not in your hand, so this sits
    with the whole-box delete under docs/DESIGN.md's "genuinely destructive actions may still
    gate" clause: `confirm: true` on the wire, and on the screen the count and the bytes
    drawn by the free route above before the control that fires exists.
    """
    _reject_unknown(payload, RECLAIM_FIELDS)
    if payload.get("confirm") is not True:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "Reclaiming deletes photographs that nothing can regenerate. Send `confirm: "
            "true`, and show the count from GET /boxes/<box>/photos first.",
        )

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        if inventory.box(box) is None and not _box_holds_cards(inventory, box):
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "box_not_found",
                f"No box {box} — nothing registered under that number and no card names it.",
            )
        reclaimable, already = _reclaimable(inventory, box)
        if not reclaimable:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "nothing_to_reclaim",
                f"Box {box} holds no sold card with a photograph still on disk"
                + (f" — {len(already)} were reclaimed already" if already else "")
                + ". A photograph is reclaimed from a SOLD card only; a retired card keeps "
                "its photograph (D26), and a card on hand needs it for the pull preview.",
            )

        freed = 0
        keys = []
        for _at, key, _card, path, size in reclaimable:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            inventory.record_photo_reclaimed(key, sha256=digest, size=size)
            if _unlink(path):
                freed += size
            keys.append(key)

    return {
        "box": int(box),
        "reclaimed": len(keys),
        "bytes": freed,
        "keys": keys,
        "already_reclaimed": len(already),
    }


def do_delete_box(box: int) -> dict:
    """Delete a whole box: records, photos, sidecars, queue entries, cache, registry.

    D10, OWNER RULING 3 (2026-08-23), AMENDED BY D134 (2026-09-11), and the third door out
    of the store. Undo walks back the newest capture, the remove route above excises one
    record and closes its gap, and this deletes a box entire — the case both of those are
    too small for: a shakedown box of junk frames, a box captured under a mistyped number,
    a test run that was never real, or — since D134 — a box every on-hand card has left,
    by a sale, a retirement, or a merge into another box (D83) that carried the on-hand
    cards and left the departed ones behind. Gated as the genuinely destructive action
    `docs/DESIGN.md`'s clause means: the UI adds a typed confirmation on top, and this
    route is the refusal side it sits on.

    `box_not_empty_of_commitments` NOW NAMES ONLY LISTING HOLDS (D134). Ruling 3 read "a
    departure is history and a commitment, not clutter" as a reason to refuse the whole
    box; D134 keeps the sentence and changes what answers it — a sold, retired or moved
    record IS the history, and it survives the box by being BURIED (below) rather than by
    the box standing forever with nothing left to do in it. What still blocks is a held
    SKU: copies in an import file, or on TCGplayer itself, where deleting the copy here
    would leave the listing counts claiming a card that is no longer anywhere. The refusal
    names up to eight of them, oldest position first.

    AN UNREADABLE RECORD REFUSES THE WHOLE OPERATION, the same rule the remove route and
    `next_index` follow: a record whose box will not coerce cannot be proven to be
    OUTSIDE this box, and a whole-box delete that skipped it might strand it — or destroy
    it — either way silently. `BadPosition` escapes as `inventory_conflict`.

    A DEPARTED RECORD IS BURIED BEFORE ITS FILES GO (D134). One `buried` history line per
    sold, retired or moved record, carrying the record whole: name, number, game, set
    hint, SKU, condition, state and when it changed, when it was captured, the run, the
    box's own name as it stood, the order this copy was pulled against if `holder_of`
    finds one, and the photograph's digest — read off the card if `record_photo_reclaimed`
    already set it, or computed from the bytes here if not (a moved tombstone's file
    already relocated with the transplant, so its digest is whatever the card already
    carries, usually none). That line is what "a history log" means for a card leaving
    through a deleted box: it is no longer a row anywhere, it is not undoable, and its
    photograph goes with everything else in the box — but what it was, and how and when
    it left, is not lost. `#/graveyard` reads exactly these lines, merged with every
    sold/retired/moved record still standing in a box nobody has deleted, so one screen
    answers both.

    FILES GO INSIDE THE BLOCK, PHOTO BEFORE SIDECAR PER CARD — `do_delete_card`'s money
    rule at box scale, unchanged for every record, buried or on hand. A failing unlink
    escapes and nothing commits; a crash after some unlinks leaves records whose photos are
    gone, and retrying the delete finishes the job, since `_unlink` treats absence as no
    failure. The box DIRECTORY is removed only if the record-named files were all it held:
    a stray file this route never enumerated is not silently destroyed, the `rmdir` quietly
    fails, and the response says so in `directory_removed` — a leftover directory under
    `captures/cards/` is visible, and a photo-suffixed stray in it is a paid Batch request
    waiting to happen, which is worth a person looking at.

    THE REGISTRY ENTRY GOES TOO, sections, capacity and name with it. A deleted box is
    not a sealed box and not an empty box; it is a box the store has never heard of, and
    recreating the number later starts from nothing — same as a number that was never
    used. One `box_deleted` history line carries the box, the card count and the buried
    count; the per-card `removed` lines stay deliberately unwritten for an on-hand card —
    a hundred lines describing one decision would bury the decision, and the count is on
    the one line that describes it — but a departed card's own `buried` line is not that
    kind of line: it is the retained record itself, not a duplicate of one.
    """
    with Store().write() as snapshot:
        inventory = snapshot.inventory
        registered = inventory.box(box)

        holds: List[Tuple[int, str, master.Card]] = []
        blockers: List[Tuple[int, str]] = []
        for at, card_key, card in inventory.records_in(box):
            holds.append((at, card_key, card))
            if card.state not in master.TERMINAL_STATES:
                # D134: a departed record (sold, retired, moved) no longer blocks — it is
                # buried below. Only an ON-HAND card can still hold a listing.
                held = _listing_hold(inventory, card)
                if held:
                    summary = ", ".join(f"{count} {stage}" for stage, count in held)
                    blockers.append(
                        (at, f"card {at} is one copy of SKU {card.sku} ({summary})")
                    )

        if registered is None and not holds:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "box_not_found",
                f"No box {box} — nothing registered under that number and no card names "
                f"it. There is nothing here to delete.",
            )
        if blockers:
            blockers.sort()
            named = "; ".join(text for _, text in blockers[:8])
            more = f"; and {len(blockers) - 8} more" if len(blockers) > 8 else ""
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "box_not_empty_of_commitments",
                f"Box {box} cannot be deleted: {named}{more}. Listed copies are "
                f"commitments, not clutter (D10, ruling 3): wait for them to reconcile "
                f"away, release them, or leave the box standing. Sold, retired and moved "
                f"cards no longer stand in the way (D134) — they are buried in the "
                f"graveyard when the box goes.",
            )

        holds.sort()
        photos = 0
        sidecars = 0
        review_dropped = 0
        parked_dropped = 0
        cache_dropped = 0
        buried = 0
        box_name = registered.name if registered is not None else None
        for at, card_key, card in holds:
            photo = photo_path(box, at)
            if card.state in master.TERMINAL_STATES:
                digest = card.photo_sha256
                if digest is None:
                    try:
                        digest = hashlib.sha256(photo.read_bytes()).hexdigest()
                    except OSError:
                        digest = None
                order = None
                if card.capture_id:
                    held_by = snapshot.ledger.holder_of(card.capture_id)
                    if held_by is not None:
                        order = held_by[0]
                _history(
                    inventory,
                    BURIED,
                    card_key,
                    box=int(box),
                    # THE DRAWER'S TRUE INDEX, FROZEN ONTO THE RECORD THAT OUTLIVES IT
                    # (D145). `box_name` beside it is already frozen for this
                    # reason; the number is the one field here that is handed straight back
                    # out to the next drawer (D20), so on its own it cannot say which `Box 1`
                    # this card was buried out of. Nothing draws it — `#/graveyard` reads the
                    # name — and it is what lets a later question be answered at all.
                    bid=registered.bid if registered is not None else None,
                    index=at,
                    box_name=box_name,
                    state=card.state,
                    state_at=card.state_at,
                    captured_at=card.captured_at,
                    capture_id=card.capture_id,
                    run=card.run,
                    game=card.game,
                    name=card.name,
                    number=card.number,
                    printed_total=card.printed_total,
                    set_hint=card.set_hint,
                    sku=card.sku,
                    condition=card.condition,
                    rarity_claim=card.rarity_claim,
                    product=card.product,
                    note=card.note,
                    retire_reason=card.retire_reason,
                    moved_to=card.moved_to,
                    photo_sha256=digest,
                    photo_reclaimed_at=card.photo_reclaimed_at,
                    order=order,
                )
                buried += 1
            if _unlink(photo):
                photos += 1
            if _unlink(sidecar_path(photo)):
                sidecars += 1
            del inventory.cards[card_key]
            review_gone, parked_gone, cache_gone = _drop_from_stores(snapshot, card_key)
            review_dropped += review_gone
            parked_dropped += parked_gone
            cache_dropped += cache_gone

        registry_entry = inventory.boxes.pop(str(int(box)), None)
        registry_deleted = registry_entry is not None
        # WHAT THE DRAWER WAS, CAPTURED BEFORE ITS ROW GOES (D145). The number is
        # handed straight back out by `next_box_number` (D20), so after this line nothing in
        # the store can say which drawer `Box 1` meant — except this history line. The id is
        # what a run joins against; the name is what a screen draws for a run that outlived
        # its box.
        deleted_bid = None if registry_entry is None else registry_entry.bid
        deleted_name = None if registry_entry is None else registry_entry.name

        directory_removed = False
        folder = captures_root() / f"box{int(box)}"
        try:
            folder.rmdir()
            directory_removed = True
        except OSError:
            # Not empty (a stray this route never enumerated), or never existed. Either
            # way the honest answer is False, and a stray is left VISIBLE rather than
            # swept — the docstring has why.
            directory_removed = False

        _history(
            inventory, BOX_DELETED, None, box=int(box), bid=deleted_bid,
            name=deleted_name, cards=len(holds), buried=buried,
        )

    return {
        "deleted_box": int(box),
        # What went, counted per kind the way `do_delete_card` reports booleans — these
        # are counts because a box holds many of each, and the numbers are the receipt
        # the confirmation screen shows. `buried` is the subset of `cards` that left
        # through a departure door rather than as on-hand junk (D134).
        "cards": len(holds),
        "buried": buried,
        "photos": photos,
        "sidecars": sidecars,
        "review_deleted": review_dropped,
        "parked_deleted": parked_dropped,
        "cache_deleted": cache_dropped,
        "registry_deleted": registry_deleted,
        "directory_removed": directory_removed,
    }


def _departed_row(
    *,
    left_at,
    how,
    box,
    index,
    box_name,
    name,
    number,
    game,
    set_hint,
    sku,
    condition,
    retire_reason,
    moved_to,
    order,
    run,
    captured_at,
    photo_sha256,
    buried,
    buried_at,
) -> dict:
    """One `#/graveyard` row, the same shape whether it came from a live box or a burial
    line (D134) — the merge point `do_graveyard` exists to make, so the screen reads one
    kind of record rather than two."""
    return {
        "left_at": left_at,
        "how": how,
        "box": box,
        "index": index,
        "box_name": box_name,
        "name": name,
        "number": number,
        "game": game,
        "set_hint": set_hint,
        "sku": sku,
        "condition": condition,
        "retire_reason": retire_reason,
        "moved_to": moved_to,
        "order": order,
        "run": run,
        "captured_at": captured_at,
        "photo_sha256": photo_sha256,
        "buried": buried,
        "buried_at": buried_at,
    }


def do_graveyard() -> dict:
    """Every departed card the store still knows about, newest departure first (D134).

    TWO SOURCES, ONE SHAPE. A SOLD, RETIRED or MOVED record can be standing in a box
    nobody has deleted — the same records `#/inventory` already renders as departed
    (`isDeparted`, `join.departed_label`) — or it can be a `buried` event, the retained
    half of a record whose box WAS deleted (`do_delete_box`). `_departed_row` is the one
    shape both become, so this screen never has to know which door a card left through.

    THE TWO SOURCES NEVER OVERLAP, BY CONSTRUCTION. A record moves from "in a box" to
    "buried" exactly once, at the moment `do_delete_box` deletes its box, and there is no
    route that un-buries one — burial has no reversal, the same as the delete it rides in
    on. So a card counted here is never counted twice.

    LOCK-FREE ON BOTH HALVES. The in-box half is `Store().read()`'s ordinary snapshot,
    filtered by the indexed `state` column — three `where()` calls, one per member of
    `master.TERMINAL_STATES`, the same shape `_positions_in`'s callers already use rather
    than a full-table load. The buried half is `Store().buried()`, its own second
    connection over the `event = 'buried'` rows only (`store/db.py:events_named`) — never
    `history()`'s whole log.

    `order` IS A BEST-EFFORT JOIN, NOT A STORED FIELD. Neither a `Card` nor a buried line
    carries an order number; `Ledger.holder_of(capture_id)` is the reverse index D63 built
    for exactly this question, walked once per departed record with a capture id. A record
    from before capture ids existed, or one never pulled against an order, answers `None`.
    """
    snapshot = Store().read()
    inventory = snapshot.inventory
    ledger = snapshot.ledger

    rows: List[dict] = []
    for state in master.TERMINAL_STATES:
        for card in inventory.cards.where(state=state):
            registered = inventory.box(card.box)
            order = None
            if card.capture_id:
                held_by = ledger.holder_of(card.capture_id)
                if held_by is not None:
                    order = held_by[0]
            rows.append(
                _departed_row(
                    left_at=card.state_at,
                    how=card.state,
                    box=int(card.box),
                    index=int(card.index),
                    box_name=registered.name if registered is not None else None,
                    name=card.name,
                    number=card.number,
                    game=card.game,
                    set_hint=card.set_hint,
                    sku=card.sku,
                    condition=card.condition,
                    retire_reason=card.retire_reason,
                    moved_to=card.moved_to,
                    order=order,
                    run=card.run,
                    captured_at=card.captured_at,
                    photo_sha256=card.photo_sha256,
                    buried=False,
                    buried_at=None,
                )
            )

    for event in Store().buried():
        rows.append(
            _departed_row(
                left_at=event.get("state_at"),
                how=event.get("state"),
                box=event.get("box"),
                index=event.get("index"),
                box_name=event.get("box_name"),
                name=event.get("name"),
                number=event.get("number"),
                game=event.get("game"),
                set_hint=event.get("set_hint"),
                sku=event.get("sku"),
                condition=event.get("condition"),
                retire_reason=event.get("retire_reason"),
                moved_to=event.get("moved_to"),
                order=event.get("order"),
                run=event.get("run"),
                captured_at=event.get("captured_at"),
                photo_sha256=event.get("photo_sha256"),
                buried=True,
                buried_at=event.get("at"),
            )
        )

    rows.sort(key=lambda row: row["left_at"] or "", reverse=True)
    return {"departed": rows}


# ------------------------------------------------------------------------ standing queues


def _queue_row(
    entry: queues.QueueEntry, places: "Optional[_Places]" = None
) -> dict:
    """One waiting card, as the review screen reads it.

    `asdict` WHOLE rather than a hand-picked subset, for the reason `app/src/types.ts` gives
    for keeping the server's own field names: the first thing anyone debugging a run does is
    hold what the screen shows against `review.json`, and a projection turns that comparison
    into a lookup. It also means `candidates`, `reason`, `market` and `photo` — the four
    things `docs/DESIGN.md` draws a queue row out of — arrive because they are fields of the
    record, not because this function remembered them.

    `age_days` IS THE ONE ADDITION, and it is here because it is a property rather than a
    field, so `asdict` does not carry it. `docs/DESIGN.md` lists age among the metadata a
    queue row shows in the utility face; computing it in the app would put a second copy of
    `_age_days`'s date arithmetic there, which is the same argument `do_inventory` makes for
    the position label. Null when `first_seen` is missing or unparsable — `_age_days` already
    refuses to guess, and a placeholder age would be a claim about how long a card has waited.

    `cleared_by_human` is present and is always false in this payload, because
    `open_entries` filters on exactly that. Kept rather than stripped: it is a real field of
    the record, and a subtraction maintained by hand is the thing that drifts.

    `photo` IS A FILESYSTEM PATH ON THE MAC, exactly as `Card.photo` is — a browser cannot
    load one, and `GET /photo/<box>/<index>` is D6's route and the only way to show it.
    """
    row = asdict(entry)
    row["age_days"] = entry.age_days
    # BOX 0 MEANS "NO POSITION" (`cli/resolve.py:failure_entry` — D10 starts at 1), and
    # such an entry keeps the label the join gave it. There is no box to count and nothing
    # to re-render against; asking anyway would answer `Box 0 · departed`, which is a claim
    # about a card that has left rather than about one that never had a slot.
    try:
        addressable = int(entry.box) >= 1 and int(entry.index) >= 1
    except (TypeError, ValueError):
        addressable = False
    if places is not None and addressable:
        # THE LABEL IS RE-RENDERED AT READ TIME AND THE STORED ONE IS NEVER SERVED (D58,
        # on D56's rule). `QueueEntry.label` is written once by `cli/resolve.py` at join
        # time and never recomputed, so it is a snapshot of a rendering — and every rule
        # that moves a rendering leaves it behind. Measured on the owner's real store the
        # day this landed: 15 of 92 entries carried a label drawn against
        # `CARDS_PER_SECTION = 25`, the divider rule D10's amendment DELETED on 2026-08-29.
        # Box 1 declares no dividers at all and its queue held both
        # `Box 1 · Section 1 · Card 108` and `Box 1 · Section 5 · Card 18` — a section that
        # does not exist, on the screen the owner answers cards from.
        #
        # D56 states the rule for exactly this shape one register up, about a run's box
        # name: never write down an answer nobody can correct; join it when it is read. The
        # entry keeps its stored `label` on disk so nothing already written moves, and no
        # route serves it.
        place = places.of(entry.box, entry.index)
        row["label"] = (
            place["label"]
            if place["located"]
            else join.pooled_label(str(place.get("game") or games.DEFAULT_GAME))
        )
    return row


def do_queues() -> dict:
    """Both standing queues, in the order they are meant to be worked.

    THE ORDER IS THE PAYLOAD'S WHOLE POINT. `Queue.open_entries` sorts priced first and
    descending, unpriced last, then box-walk order by box and index — built, running today,
    and the sort every run report has already printed. `docs/DESIGN.md` says the screen's job
    is to make that ordering visible rather than to recompute it, so this route hands the
    list over in that order and the app must not re-sort. An app-side sort is a second copy
    of `QueueEntry.sort_key` one edit away from disagreeing with the report the owner read
    before he opened the screen.

    TWO LISTS AND NOT ONE, because the separation is the point (`store/queues.py`): main is
    work, parked is the low-value queue an unidentifiable card may never be worth a tap on.
    Concatenating them here and letting the app filter would put the merge in the one place
    that cannot see why the split exists.

    LOCK-FREE, like `do_status` and `do_inventory`. Every write is an atomic replace, so a
    reader sees one whole file (`store/__init__.py`) — and a route the queue screen polls
    must not serialise itself behind a running `./pkmnscan join`, which holds the lock for
    the length of a join.

    CLEARED ENTRIES ARE ABSENT, which is what `open_entries` means. They stay in the file:
    `Queue.release` preserves them deliberately, so a human's answer outlives the question it
    answered. This route answers "what is left to do", and an answered card is not that.
    """
    snapshot = Store().read()
    # One walk for both queues and every entry in them, the same instance `do_inventory`
    # renders 5,000 rows against — so a card's label on the review screen and its label on
    # the inventory screen are the same string by construction rather than by care.
    places = _Places(snapshot.inventory)
    return {
        "review": [_queue_row(entry, places) for entry in snapshot.review.open_entries],
        "parked": [_queue_row(entry, places) for entry in snapshot.parked.open_entries],
    }


def _candidate_with_sku(candidates: Sequence[dict], sku: str) -> Optional[dict]:
    """The offered row carrying this SKU, or None.

    String comparison on both sides. A candidate's `sku` comes from the export's
    `TCGplayer Id` column and is a string there; a client sending the same value as a JSON
    number would otherwise miss its own candidate and be told it invented one.
    """
    for candidate in candidates:
        if str(candidate.get("sku") or "") == sku:
            return candidate
    return None


def _answer_before(events: Sequence[dict], key: str) -> Optional[dict]:
    """The `{sku, condition}` the card carried before the newest answer here. None if unknown.

    THE PRIOR PAIR IS NOT ON THE CARD, because the answer overwrote it — that is what an answer
    IS. So the reversal reads it back out of `history.jsonl`, exactly as `_state_before_sale`
    reads the state a sale replaced, and for the identical reason: the log already records
    every change either route makes, and a `previous_sku` field on `Card` would be a second
    piece of state to keep true through every join, emit and reconcile in the pipeline for the
    sake of one twenty-second window on one screen.

    IT WAS ALSO THE BLOCKER. `_history(ANSWERED, ...)` logged the sku and condition the route
    WROTE and not the ones it OVERWROTE, so until 2026-08-23 nothing anywhere could say what an
    undo should put back — the answer was unreversible not by policy but by bookkeeping. The
    `answered` line now carries `restores_to`, and this is its only reader.

    THE NEWEST `answered` LINE WINS AND THE SCAN STOPS THERE, which is `_state_before_sale`'s
    rule and not an optimisation. An older line's pair is the state of the card two answers ago;
    restoring that would put back a SKU the operator replaced deliberately, which is worse than
    refusing. So a newest line carrying no pair — an answer written by a server that predates
    this field — returns None here rather than falling through to one that does.

    A LINE THAT IS NOT A MAPPING IS NO PAIR EITHER. This log is hand-editable and the file is
    the one thing standing between a request and a real card's SKU; `str()` on whatever was
    there would write `{'sku': None}` onto a card as a catalog id. Both members are read as
    optional strings because `master.Card` declares them that way — a card queued for review
    has usually never carried a SKU at all, and None is that fact rather than a missing value.

    A `renumbered` LINE THIS POSITION SITS ABOVE IS A HARD STOP (D10, ruling 1). The mid-box
    delete slides a DIFFERENT physical card into every index above the deleted one, so an
    `answered` line older than the shift belongs to the position's previous occupant, and
    restoring its pair would write one card's history onto another. The two state scans
    survive a shift because the re-key logs each mover's own state at its new position;
    an answer has no equivalent line to refresh, so the honest reading here is None — the
    reversal refuses, and the queue entry is re-answered instead. An `answered` line
    written AFTER the shift is met before the boundary and restores normally.
    """
    try:
        at_box, at_index = (int(part) for part in str(key).split("/"))
    except (TypeError, ValueError):
        at_box = at_index = None
    for event in reversed(list(events)):
        if (
            at_box is not None
            and event.get("event") == RENUMBERED
            and event.get("box") == at_box
            and isinstance(event.get("from"), int)
            and at_index >= event["from"]
        ):
            return None
        if event.get("position") != key:
            continue
        if event.get("event") != ANSWERED:
            continue
        previous = event.get("restores_to")
        if not isinstance(previous, dict):
            return None
        pair = {}
        for field in ("sku", "condition"):
            value = previous.get(field)
            if value is not None and not isinstance(value, str):
                return None
            pair[field] = value
        return pair
    return None


def _answer_origin(store: Store, key: str) -> Tuple[Optional[dict], Optional[str]]:
    """The pair to put back, or None and the reason it cannot be known. Never raises.

    `_sale_origin`'s twin, one section down, and the shape is copied on purpose so the two
    reversals in this file fail the same way. What differs is how much a broken log costs, and
    it is less here: a sale reads history on the way IN as well, so `_sale_origin` degrading
    rather than raising is what keeps a real-world sale recordable through a corrupt line. The
    answer path never reads this file. So an unreadable log costs the reversal and nothing else
    — no card is stopped from being answered by it.

    THE READ STAYS INSIDE THE LOCK, for `_sale_origin`'s reason unchanged: a snapshot taken
    before the lock is the lost update the lock exists to prevent, and D13 puts a second device
    on this store with no session between them.
    """
    try:
        events = store.history()
    except (files.StoreError, OSError, ValueError) as exc:
        # Broad on purpose, as at `_sale_origin`: a bad line, an unreadable file and non-UTF-8
        # bytes are one condition to this route — history cannot say — and the operator needs
        # to be told which file to go and look at rather than handed a 503.
        return None, f"the store's history could not be read ({type(exc).__name__}: {exc})"
    previous = _answer_before(events, key)
    if previous is None:
        return None, "the store's history records no answer here that says what it replaced"
    return previous, None


def _catalog_answer(card, sku: str) -> dict:
    """The catalog row `sku` names, in this card's own export, or a refusal (D46).

    THE SERVER RE-READS THE ROW; IT NEVER TAKES THE CLIENT'S WORD FOR ONE. The request
    carries a SKU and nothing else that matters — the name, the number, the condition and
    the price all come back off the export here. That is what makes this an answer chosen
    from a catalog rather than a free-text write into the field `CLAUDE.md` protects, and it
    is why the condition on the request is discarded rather than validated: a client that
    sends the wrong one gets the right one, not an error.

    THE SAME EXPORT THE CARD WAS JOINED AGAINST, via `_catalog_for_card`, not "some export".
    A SKU is only meaningful inside the file that defines it, and answering out of a
    different export would write a row this run never saw.

    `sku_not_in_catalog` is its own code rather than reusing `sku_not_a_candidate`: that one
    means "not one of the rows offered" and prints the ones that were, which for a card with
    no candidates is an empty list and a confusing message.
    """
    catalog, _game = _catalog_for_card(card)
    row = catalog.row_for_sku(sku)
    if row is None:
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "sku_not_in_catalog",
            f"{sku} is not in the export run {card.run!r} was joined against, so it cannot "
            f"be what this card is. Search the catalog on the review screen and choose a "
            f"row from it.",
        )
    return _catalog_row(row)


def _answer_target(
    snapshot,
    box: int,
    index: int,
    sku: str,
    condition: str,
    *,
    from_catalog: bool = False,
) -> Tuple[
    master.Card,
    List[Tuple[queues.Queue, queues.QueueEntry]],
    queues.Queue,
    queues.QueueEntry,
    dict,
    str,
]:
    """One answer's validation — the whole of it, shared verbatim by the single route and
    the group route, and IT WRITES NOTHING. Returns (card, holders, offering queue,
    governing entry, chosen row, offered condition) or raises the refusal the single route
    has always raised, in the same code with the same message. One implementation rather
    than two, because the group route's promise is that it re-validates each card "exactly
    as the single answer does" — and a second copy of these checks is the copy that stops
    being exact the first time one of them changes.

    THE CARD IS CHECKED BEFORE THE QUEUE, deliberately, and the other order was
    considered. The answer is written onto the card record, so a position with no
    record has nothing to answer onto — and telling the operator "that card is not in
    a queue" about a position that holds no card at all sends him to read the wrong
    file. This is reachable rather than theoretical: `cli/resolve.py` queues a card
    from a run's identifications, and a run recovered without its captures has entries
    whose positions the store never recorded.
    """
    key = master.position_key(box, index)

    card = snapshot.inventory.cards.get(key)
    if card is None:
        raise BadRequest(
            HTTPStatus.NOT_FOUND,
            "card_not_found",
            f"No card at box {box}, card {index}. This route answers a card that "
            f"exists; it never creates one.",
        )

    holders: List[Tuple[queues.Queue, queues.QueueEntry]] = []
    already: List[str] = []
    for queue in (snapshot.review, snapshot.parked):
        entry = queue.entries.get(key)
        if entry is None:
            continue
        if entry.cleared_by_human:
            already.append(queue.name)
        else:
            holders.append((queue, entry))

    if not holders:
        # TWO CODES, NOT ONE, because the remedies are opposite. An already-answered card
        # is the two-device case D5 and D13 describe — the Fulfiller or the other browser
        # tab got there first — and the operator should reload, not retry. A position
        # that was never queued is a client asking about the wrong card.
        if already:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "already_answered",
                f"Box {box}, card {index} has already been answered and is no longer "
                f"in a queue. Reload the queue — the answer may have come from the "
                f"other device.",
            )
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "not_in_queue",
            f"Box {box}, card {index} is not waiting in the review or parked queue, so "
            f"there is nothing to answer. Reload the queue.",
        )

    # ONE ENTRY GOVERNS THE OFFER, and it is the main-queue one whenever the position is
    # in both. `holders` is built review-first above, so this is `holders[0]` and not a
    # search. Every alternative was worse:
    #
    #   the union of both    what this did, and the bug. A stale parked entry launders a
    #                        SKU the review entry never offered, and the laundering is
    #                        invisible afterwards — the card carries a real SKU from a
    #                        real catalog row, just not one that was ever proposed for it.
    #   the intersection     safe and unanswerable. `cli/resolve.py:failure_entry` records
    #                        no candidates at all, so a position sitting in both files
    #                        with one of them a failure entry would refuse every answer
    #                        forever, including the correct one.
    #   naming the queue     the client would send which file its row came from. That is a
    #   in the request       field the screen has no reason to know (it taps a position),
    #                        and it puts the choice of what may be answered on the wire,
    #                        where a stale client picks it.
    #
    # Main wins because main is the queue that is worked — `store/queues.py` splits them
    # exactly so: work versus the low-value queue a card may never be worth a tap on. A
    # card in both is a card the owner answers from the review screen.
    offering, governing = holders[0]
    candidates: List[dict] = list(governing.candidates)
    if from_catalog:
        # D46 — THE ROW CAME OUT OF THE EXPORT, SO IT IS NOT FREE TEXT.
        #
        # D77 WIDENED WHICH ENTRIES THIS REACHES, AND CHANGED NOTHING ABOUT WHAT IT CHECKS.
        # The condition was `not candidates and from_catalog` until 2026-08-31, on D46's
        # reasoning that a card the pipeline found rows for already has its answer on screen.
        # Box 3 card 66 is the counter-example and it was the only open entry in the store:
        # `Nasus, Ascended` read with its number misread as `8/298`, which is a REAL key in
        # that export and belongs to `Get Excited!` — so the entry carries two confident
        # candidate rows for a different card, at $0.07 and $0.29, while the card's own row
        # (`9405493`, `046/166`, Near Mint Foil, $0.74) sat in the same file. The old gate
        # made "the pipeline offered nothing" the test for whether a human may point at a
        # row, and the test that was wanted is "the pipeline is wrong", which is not a thing
        # the entry can know about itself. Measured on that card: the lookup returns the
        # right row FIRST for an empty query, because the read's NAME was right all along.
        #
        # WHAT IS UNCHANGED IS THE PART THAT WAS EVER LOAD-BEARING. The SKU is re-read out of
        # THIS CARD'S OWN EXPORT below, inside the write lock; the condition comes off that
        # row and never off the request; an unknown SKU refuses. So no string a client sends
        # can become a listing on its own — the property the original refusal protected — and
        # an answer that does NOT set this flag still reaches `sku_not_a_candidate` and may
        # still only choose from the rows the pipeline offered.
        #
        # The refusal below names the evidence it stands on: "Every one of them wanted a
        # re-export or a re-shoot, never a typed SKU". That was true of the cards it was
        # written about and it is not true of the case that reopened it. Box 1's
        # `Master Yi, Wuju Master` has a good photograph — measured, statistically identical
        # to two copies of the same card that read perfectly — and its row was sitting in the
        # export the whole time. A re-shoot repairs nothing; the read was simply wrong, in a
        # way a person looking at the card can see and the pipeline cannot.
        #
        # WHAT KEEPS THE ORIGINAL GUARD INTACT: the SKU is re-read out of THIS CARD'S OWN
        # EXPORT here, inside the write lock, and the condition is taken from that row rather
        # than from the request. A SKU that is not in the export refuses; a condition the
        # client invented is discarded rather than believed. So no string a client sends can
        # become a listing on its own — which is the property the refusal was protecting, and
        # it is unchanged. What changed is that a human may now point at a row the pipeline
        # failed to find, instead of only being able to walk away from it.
        chosen = _catalog_answer(card, sku)
        offered_condition = str(chosen.get("condition") or "")
        return card, holders, offering, governing, chosen, offered_condition
    if not candidates:
        # `cli/resolve.py:failure_entry` records no candidates at all — an identification
        # that failed, or a card with no position, has no rows for a human to choose
        # between. `docs/DESIGN.md` describes a screen of candidate rows and says nothing
        # about what to do when there are none, so this refuses rather than inventing a
        # free-text path into the one field the hard rule protects. Gate B fired the
        # trigger, and the answer is not a flat zero. Its accepted run queued 16
        # entries, every one with candidate rows; the same cards joined against a
        # commons-only export produced 23 `no_catalog_row` cards, which are
        # candidate-less by construction — `pipeline/variant.py` returns that reason
        # only when `found.rows` is empty, and `pipeline/join.py` copies that same
        # empty tuple into the entry. Every one of them wanted a re-export or a
        # re-shoot, never a typed SKU, so the refusal stands on the evidence it asked
        # for.
        #
        # WHAT IT NO LONGER MEANS IS "THIS CARD CANNOT BE ANSWERED". D46 gave it a remedy
        # and the sentence went on describing the dead end for two days; D77 widened the
        # remedy to every entry and the sentence would have been wrong in a second way. It
        # names the flag now, because the operator reading this refusal on a screen has the
        # control that satisfies it a few pixels away.
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "no_candidates",
            f"Box {box}, card {index} is queued in {offering.name} as "
            f"`{governing.reason}` and records no candidate rows, so there is nothing here "
            f"to choose. Search this card's own export and answer with `from_catalog`, or "
            f"re-shoot it.",
        )

    chosen = _candidate_with_sku(candidates, sku)
    if chosen is None:
        offered = ", ".join(sorted(str(c.get("sku") or "") for c in candidates))
        # The queue is NAMED, because the case this refusal now catches is a card sitting
        # in both files whose two entries disagree — and "that is not one of the rows
        # offered" reads as a bug to anyone looking at the other row on screen.
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "sku_not_a_candidate",
            f"{sku} is not one of the rows offered for box {box}, card {index}. "
            f"Offered in {offering.name}: {offered}. Answer with one of those, or reload "
            f"the queue if it has been re-joined since this screen was drawn.",
        )

    offered_condition = str(chosen.get("condition") or "")
    if condition != offered_condition:
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "condition_mismatch",
            f"{sku} is offered as {offered_condition!r}, not {condition!r}. The screen "
            f"was drawn from an older queue file — reload it and choose again.",
        )

    # D137 — AND THE GRADE ITSELF IS CHECKED, NOT ONLY THAT THE TWO AGREE.
    #
    # The three refusals above ask whether this answer matches the row that was OFFERED. None
    # of them asks whether the row should have been offered at all, and for ten days it should
    # not have been: the catalog carried every play grade, so `Damaged Foil` sat on screen as a
    # tappable chip beside `Near Mint Foil` and answering it would have written that SKU onto a
    # card this product sells at Near Mint (D12). Nothing downstream would have disagreed —
    # `join_batch` rung 0 re-finds the answered row by its own condition string, so the wrong
    # grade travels all the way into the import file.
    #
    # `Catalog.from_export` now makes this unreachable from the screen, which is exactly why it
    # is worth having: the entries in the store TODAY were written before that filter existed
    # and still carry their played rows until the next join rewrites them. This is the floor
    # under those, and under any client that builds its own POST.
    #
    # THE SET IS THE CATALOG'S, NOT A SECOND OPINION ABOUT IT. Near Mint plus sealed, the same
    # two clauses `from_export` keeps — a row that survives the catalog satisfies this by
    # construction, so the two can never drift into disagreeing about one row.
    #
    # `or DEFAULT_GAME` IS D21'S READ-SIDE BACKFILL AND NOT A GUESS, and it is the same
    # expression `cli/resolve.py` uses to decide which catalog a card is joined against. A
    # record predating D21 carries no claim, is READ as the default game, and is therefore
    # offered the default game's rows — so asking a different question here would refuse a card
    # the join had just answered correctly. T7 found this on the first run with a `game`-less
    # fixture card; `games.require` raises `UnknownGame` on `None` rather than defaulting,
    # which is right for a registry lookup and wrong for a read of an old record.
    listable = _near_mint_conditions(
        str(getattr(card, "game", None) or games.DEFAULT_GAME)
    ) | {tcgcsv.SEALED_CONDITION}
    if offered_condition not in listable:
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "condition_not_listed",
            f"{sku} is a {offered_condition!r} row, and this product lists "
            f"{', '.join(sorted(listable))} (D12). It was offered by a queue entry written "
            f"before the catalog stopped carrying play grades — re-join this run and the "
            f"entry will be rewritten with the rows the ladder would actually pick. Nothing "
            f"was written.",
        )

    return card, holders, offering, governing, chosen, offered_condition


# How many catalog rows one lookup may return. Nine because `app/src/ReviewQueue.tsx` keys
# candidates on the digits and stops at `MAX_KEYED_CANDIDATES = 9`; a tenth row would draw a
# blank chip and be mouse-only, which is the trap `docs/DESIGN.md` records for that screen.
# The count is reported alongside so a truncated search says so rather than looking complete.
CATALOG_LOOKUP_LIMIT = 9


def _near_mint_conditions(game: str) -> Set[str]:
    """The Condition strings this game's Near Mint rows carry (D12 hardcodes Near Mint).

    Read off the registry rather than restated, so a game whose finishes change here changes
    in one place. `variant.resolve` narrows to exactly these when it builds candidates, and a
    lookup that offered `Lightly Played Foil` would be offering a row the ladder never would.
    """
    entry = games.require(game)
    return {str(v) for v in dict(entry["condition_by_finish"]).values()}


def _catalog_for_card(card) -> Tuple[object, str]:
    """The export THIS card was joined against, and the game it was read as.

    THE EDGE IS ON THE CARD, NOT ON THE QUEUE ENTRY, and that distinction is the whole reason
    this function is short. `store/queues.py:QueueEntry` records no run, no game and no export,
    and `Queue.parse` drops any key it does not declare — so nothing about a run can be written
    into `review.json` without a schema change. `master.Card` has carried `run` since
    identification wrote it (`Inventory.record_identification`) and `game` since D21, and
    `_answer_target` already loads the card before it looks at any queue. So the lookup is
    exact: card -> run -> that run's manifest -> the export for that card's game.

    Guessing the run by scanning `runs/` for one whose scope covers this box was the
    alternative and it is unsound: three runs exist on this machine, two of them touch box 1,
    `first_seen` is date-only so it cannot separate two runs on one day, and `Queue.upsert`
    preserves `first_seen` across re-joins anyway. An exact edge that is sometimes absent beats
    an inferred one that is always present and sometimes wrong.

    Every way this can fail is a named refusal rather than a traceback, because most of them
    are ordinary history rather than corruption:

      no_run_recorded   a card identified before `run` was written, or never identified.
      run_not_found     the run directory has been deleted. Runs are disposable; the store is
                        not, so this is expected rather than alarming.
      no_export_for_game  the run was never joined, or was joined for another game.
      export_missing    THE LEGACY CASE, and the one worth naming. A join driven from a
                        terminal records the `--export` path it was given, which is typically
                        `~/Downloads/...` and may be long gone; a join driven from the app
                        uploads the file INTO the run (`pipeline_routes._store_upload`) so the
                        run holds the exact bytes. Both are legal and only the second survives.
    """
    run_name = str(getattr(card, "run", "") or "")
    if not run_name:
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "no_run_recorded",
            f"Card {card.box}/{card.index} records no run, so there is no export to look "
            f"the catalog up in. Identify it first.",
        )
    # The name is validated as a NAME before it is joined onto a path, the same posture
    # `pipeline_routes._open_run` takes. It comes off a stored record rather than off a
    # request, so this is defence in depth rather than the front line — but a record is a
    # file, and a `..` that reached `runs_dir() / run_name` would read outside the store.
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_name):
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "run_not_found",
            f"Card {card.box}/{card.index} records {run_name!r} as its run, which is not a "
            f"run name. The record is malformed; re-identify the box.",
        )
    directory = files.runs_dir() / run_name
    if not directory.is_dir():
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "run_not_found",
            f"Run {run_name!r} is not on disk any more, so the export it was joined "
            f"against cannot be read. Re-join the box to rebuild the queue.",
        )
    game = str(getattr(card, "game", "") or games.DEFAULT_GAME)
    # `exports_by_game`, never the `export_path` property — that one answers the DEFAULT
    # game's file only, which for a riftbound card is silently the wrong question. It also
    # carries the scalar-era backfill for manifests written before per-game exports existed.
    #
    # NARROW EXCEPT, DELIBERATELY. This was `except Exception` for one draft and it turned a
    # real coding error — calling the property with an argument — into a confident
    # `no_export_for_game` refusal about a manifest that named the export perfectly well. A
    # catch wide enough to hide a TypeError is a catch that makes its own bugs unreportable.
    # `open_run`, not `Run(directory)` — `Run` is a dataclass whose `manifest` field defaults
    # to an EMPTY DICT and never reads disk, so constructing one directly answers "this run
    # records no export" for every run that ever existed. Cost one debugging pass.
    try:
        path = cli_runs.open_run(directory).exports_by_game.get(game)
    except (KeyError, TypeError, ValueError, OSError, cli_runs.RunError):
        path = None
    if not path:
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "no_export_for_game",
            f"Run {run_name!r} records no export for game {game!r}, so there is no catalog "
            f"to search. Join the run against an export for that game first.",
        )
    source = Path(str(path))
    if not source.is_file():
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "export_missing",
            f"Run {run_name!r} names its {game!r} export as {source}, and that file is not "
            f"there. A join driven from a terminal records the path it was handed; a join "
            f"driven from the app keeps the bytes inside the run. Re-join from the app, or "
            f"put the file back.",
        )
    export = tcgcsv.read_export(source)
    return join.Catalog.from_export(export, game), game


def _catalog_matches(catalog, game: str, query: str) -> List[dict]:
    """Catalog rows a human might mean by `query`, best first.

    THE MATCH IS DELIBERATELY LOOSE IN BOTH DIRECTIONS, and that is what makes it useful for
    the case it was built for. `Master Yi, Wuju Master` was read as `Wuju Master` — the
    epithet, with the champion dropped — so an exact fold finds nothing and a
    query-contains-name test finds nothing either. Only name-contains-query recovers it.
    The mirror case is real too: the same run read `Master Yi, Tempered` as `Master Yi`.
    Measured on that export, 490 of 494 epithets identify exactly one product and only 38 of
    98 champion names do, so both directions are worth offering and neither is worth trusting
    without a human looking at the photograph.

    NOTHING HERE DECIDES ANYTHING. It ranks rows for a person to choose between, so a loose
    match costs a row on a list rather than a wrong card in an import file. That is the whole
    reason this is allowed to do what `CLAUDE.md` forbids the JOIN to do.

    Near Mint only (D12), read off the registry, because those are the rows the ladder itself
    would have offered.
    """
    wanted = join.name_index_key(query)
    number = join.number_index_key(query)
    conditions = _near_mint_conditions(game)
    scored: List[Tuple[int, str, dict]] = []
    # `Catalog.from_export` has already filtered `export.rows` to this game's product
    # line, so walking them here cannot reach another game's rows. There is no
    # every-row accessor on `Catalog` and this deliberately does not add one: the
    # indexes it does expose are all exact-match, and a substring search is not a
    # lookup the JOIN should ever be able to make.
    for row in catalog.export.rows:
        if str(row.get(tcgcsv.CONDITION_COLUMN, "")) not in conditions:
            continue
        name = join.name_index_key(row.get(tcgcsv.NAME_COLUMN, ""))
        cell = join.number_index_key(row.get(tcgcsv.NUMBER_COLUMN, ""))
        sku = str(row.get(tcgcsv.SKU_COLUMN, ""))
        if wanted and name == wanted:
            rank = 0
        elif (number and cell == number) or (sku and sku == query.strip()):
            rank = 1
        elif wanted and wanted in name:
            rank = 2  # the epithet case: the read is part of the catalogued title
        elif wanted and name in wanted:
            rank = 3  # the read carries more than the title does
        else:
            continue
        scored.append((rank, name, row))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [_catalog_row(row) for _rank, _name, row in scored]


def _catalog_row(row) -> dict:
    """One catalog row in the shape the review screen already draws.

    Identical keys to `cli/resolve.py:_candidate_rows`, deliberately: the screen renders these
    through the same component as the pipeline's own candidates, so a divergence here would be
    a second row shape nothing audits.
    """
    return {
        "sku": row[tcgcsv.SKU_COLUMN],
        "name": row[tcgcsv.NAME_COLUMN],
        "set": row.get(tcgcsv.SET_COLUMN, ""),
        "number": row[tcgcsv.NUMBER_COLUMN],
        "condition": row[tcgcsv.CONDITION_COLUMN],
        "market": row[tcgcsv.MARKET_PRICE_COLUMN],
    }


def do_review_catalog(box: int, index: int, query: str) -> dict:
    """What this card COULD be, out of the export it was actually joined against.

    THE GAP THIS CLOSES, in the owner's words: *"it should've brought up what cards it could
    have matched too (along with letting me literally just enter what it is)"*. A queued card
    with no candidate rows was a dead end — `POST /review/<box>/<index>/answer` refuses it as
    `no_candidates`, so the only moves were skip (which writes nothing and asks again next
    session) and stand-down (which closes the question without answering it). The row was
    sitting in the export the whole time.

    FREE, READ-ONLY, AND IT CREATES NOTHING. No run directory, no store write, no lock. It
    reads one CSV the run already holds — measured at ~40 ms for a 10,000-row export — and
    answers. `Store().read()` is used for the card lookup alone.

    WITH NO QUERY IT SUGGESTS, USING THE CARD'S OWN READ. That is the half that answers the
    owner's first clause: arriving at the card, the screen already shows what it could have
    been, without anyone typing. With a query it searches, which is the second clause.

    IT OFFERS; IT NEVER ANSWERS. Nothing here writes a SKU onto a card — the operator still
    presses a digit, and `do_review_answer` still validates what they picked. This route is
    the evidence, not the decision.

    IT WAS NEVER GATED ON THE CARD HAVING NO CANDIDATES AND STILL IS NOT, which under D46
    was an accident of it being free and read-only, and under D77 is the point. The gate
    lived entirely in the two places that decide: the screen, which drew the search only in
    the zero-candidate arm, and `_answer_target`, which honoured `from_catalog` only there.
    Both are widened; this route did not have to move, because searching an export the
    operator is already looking at was never a thing worth refusing.
    """
    # `Store().read()` answers a snapshot outright rather than a context manager — this
    # route takes no lock because it writes nothing.
    snapshot = Store().read()
    key = master.position_key(box, index)
    card = snapshot.inventory.cards.get(key)
    if card is None:
        raise BadRequest(
            HTTPStatus.NOT_FOUND,
            "card_not_found",
            f"No card at box {box}, card {index}.",
        )
    read_name = ""
    for holder in (snapshot.review, snapshot.parked):
        entry = holder.entries.get(key)
        if entry is not None:
            read_name = str((entry.read or {}).get("name") or "")
            break
    card_name = str(getattr(card, "name", "") or "")

    catalog, game = _catalog_for_card(card)
    # The typed query wins; failing that the queue entry's own read, failing that the card
    # record's name. The last two are usually the same string and the fallback matters for a
    # card whose entry has been re-joined since.
    term = query.strip() or read_name or card_name
    if not term:
        return {
            "box": box,
            "index": index,
            "game": game,
            "query": "",
            "rows": [],
            "found": 0,
            "truncated": False,
        }
    matches = _catalog_matches(catalog, game, term)
    return {
        "box": box,
        "index": index,
        "game": game,
        "query": term,
        "searched": bool(query.strip()),
        "rows": matches[:CATALOG_LOOKUP_LIMIT],
        "found": len(matches),
        "truncated": len(matches) > CATALOG_LOOKUP_LIMIT,
    }


def do_review_answer(box: int, index: int, payload: dict) -> dict:
    """D4's one-tap choice: the human picks one candidate row and the card takes it.

    THE SKU MUST BE ONE THE PIPELINE OFFERED, and that refusal is the reason this route is
    not a general "set the sku on a card" PUT. `CLAUDE.md`'s hard rule — never guess an
    identification, ambiguity goes to the review queue with its photo — is a rule about the
    pipeline, and a screen that could write an arbitrary SKU onto a card would be that rule
    broken by hand instead: an answer the pipeline never proposed, indistinguishable
    afterwards from one it did, on the card it was least sure about in the first place. The
    candidates recorded on the entry are the whole of what may be chosen.

    THE CONDITION IS CHECKED, NOT TRUSTED, and is required even though the SKU implies it.
    Every candidate row is one `TCGplayer Id`, so the pair is redundant on the wire — which
    is exactly what makes it worth carrying: the client says which row it believes it is
    picking, and a disagreement means the screen was drawn from a queue file that has since
    been rewritten by a join. Deriving the condition silently would accept that stale click
    and write the wrong finish onto a real card. The alternative — accepting the SKU alone —
    is one field shorter and cannot tell those two cases apart.

    IT CLEARS THE ENTRY RATHER THAN DELETING IT. `cleared_by_human` is the flag
    `store/queues.py` was built around and had never been written by anything:
    `Queue.upsert` refuses to re-queue a cleared position, `Queue.release` refuses to drop
    one, and `open_entries` hides it. Popping the entry instead would leave the next
    `./pkmnscan join` free to ask the same question again, which is the one thing that file
    says must never happen. `do_delete_card` pops rather than clears, and the difference is
    principled: there the card, the question and the photograph are all gone.

    BOTH QUEUES ARE SEARCHED AND BOTH ARE CLEARED. A position can hold an entry in each file
    — nothing in `store/queues.py` prevents it and `do_delete_card` already clears both for
    that reason — so an answer that cleared only the first would leave the screen still
    showing a card whose answer is already written.

    BUT ONLY ONE ENTRY'S CANDIDATES ARE THE OFFER, and until 2026-08-13 this validated
    against the UNION of both. Measured before this was written: a position in both files,
    review offering one SKU and a stale parked entry offering another, accepted the parked
    SKU, wrote it onto the card and cleared both queues. That is the hard rule this route
    exists to keep — never guess an identification — defeated by bookkeeping: the answer was
    one no screen ever showed for the row being answered, and afterwards it is
    indistinguishable from one the pipeline proposed. See the code for which entry governs.

    IT APPENDS AN `answered` EVENT, and the reason is that the card record is the only place
    the human's choice lands — and it is not this route's to keep. `Inventory.set_state`
    takes a `sku` and writes it, and a later `emit` re-derives its own join and writes the
    row it produced onto the same card, so a run can overwrite what was chosen here while
    `review.json` goes on saying `cleared_by_human` beside it. The queue entry records
    that a person answered; without this line, nothing records WHAT he answered, and the
    two-field pair the whole route is built to validate is unreconstructible an hour after
    the tap. The refusals above enforce the hard rule at the moment of the choice and never
    again — afterwards a laundered SKU and an offered one are both just catalog rows on a
    card. `docs/DEBTS.md` recorded the omission as "writing a SKU onto a card is not a state
    transition", which is true and is a fact about the store's vocabulary rather than an
    argument about the audit trail.

    WHAT IT DELIBERATELY DOES NOT DO, two things, because each is a plausible-looking
    addition that `docs/DESIGN.md` does not ask for:

      it does not change state   The card stays `identified`. A state written here would be
                                 a second owner of a transition (`app/src/types.ts`: the app
                                 reads state and never sets it), and since v2 there is no
                                 listing state left for it to write anyway — `pushed`,
                                 `staged` and `live` are counts on the SKU, moved by the
                                 commands that learn them. The event name above is outside
                                 `master.STATES` for the same reason.
      it does not touch the      `store/cache.py` says the review screen writes
      identification cache       `cleared_by_human` there too, and this route does not.
                                 Marking a model answer human-cleared claims a person vouched
                                 for the NAME AND NUMBER the model read, while what was
                                 actually picked is a catalog row; the two coincide for a
                                 `low_confidence` card and come apart for a finish
                                 disagreement, where the read was never in doubt. Gate B
                                 answered the first half on 2026-08-22: all 16 real
                                 queue entries were `metadata_detection_disagreement` and
                                 none was `low_confidence`, and the owner answered every one
                                 through this route — so every real answer so far is the
                                 come-apart case. Whether the chosen row should replace the
                                 model's answer in `identifications.json` now has that
                                 evidence behind it and is still unmade.

    THE ANSWER IS CONSUMED DOWNSTREAM, as of 2026-08-22 — and it was not when this route
    shipped. Gate B's first re-join proved it: sixteen answered cards re-derived their
    disagreement and re-parked forever, listed never. `cli/resolve.py` now reads the
    answered SKU and condition off `inventory.json` onto the card the join sees, and
    `join_batch` applies them as rung 0 (`variant.HUMAN_ANSWERED`) before the ladder walks.
    A SKU the current export no longer carries falls through to the ladder rather than
    being guessed at. What this route writes is therefore the input to that rung, not a
    record that only takes the card off the owner's screen. `cli/cmd_emit.py` re-derives its join from the run's identifications and writes
    import rows for matched positions, so a card answered here is recorded on its own record
    and does not appear in any CSV. That is not a defect in this route — it is the seam 7b
    could not build against, because it has never seen a real review queue. What would settle
    it: Gate B produces one, and then a decision on whether `emit` reads human answers off
    `inventory.json`. Until it is made, the honest description of this route is that it
    records the owner's answer and takes the card off his screen.

    IT GOES BOTH WAYS AS OF 2026-08-23, AND THE REVERSAL IS `_reverse_answer` BELOW (D28).
    `{"undo": true}` on this same path takes the answer back: the pair comes off the card, every
    queue entry this route cleared is reopened, and the card is waiting again. The dispatch is
    three lines here and the whole argument is down there, for the reason `do_mark_sold` keeps
    its two directions on one path — a reversal reachable without going through the thing it
    reverses is a route a stale client can find on its own.

    WHAT THAT COSTS THIS DIRECTION IS ONE FIELD AND ONE HISTORY EXTRA, AND THE HISTORY EXTRA WAS
    THE BLOCKER. `_history(ANSWERED, ...)` recorded the sku and condition this route WROTE and
    never the ones it OVERWROTE — so the log held everything needed to audit an answer and
    nothing needed to reverse one. The `answered` line now carries `restores_to`, the pair read
    off the card inside this lock before it is overwritten, and `_answer_before` is its reader.

    `restores_to` COMES BACK ON THE ANSWER TOO, and it is the field `SaleResult` already carries
    for the same job: null means do not draw the undo control. The two things that make it null
    are at the body below.
    """
    # Read before `_reject_unknown`, because which fields are settable depends on which
    # direction this is. A stringified flag refuses rather than being coerced — see
    # `_optional_flag`, where a truthy `"false"` reversing a sale is the case that shaped it.
    undo = _optional_flag(payload, "undo", "undo_invalid")
    if undo:
        _reject_unknown(payload, UNDO_FIELDS)
        return _reverse_answer(box, index)

    _reject_unknown(payload, ANSWER_FIELDS)
    # D46. Opt-in, per request, and only this route ever passes it.
    #
    # THE GROUP ROUTE STILL DOES NOT, AND D77 CHANGED THE REASON RATHER THAN THE RULE. The
    # old reason was arithmetic — a group is uniform over ONE shared candidate row, so a
    # zero-candidate entry could never qualify and the flag had nothing to reach. Widening
    # the flag to entries that DO have candidates retires that argument, so the real one has
    # to be said: a catalog row is found by a person looking at ONE photograph, and D29's
    # group answer is a claim about a set of cards nobody is looking at individually.
    # Pointing at a row found for card A and applying it to fifteen others is the laundering
    # this whole guard exists to prevent, arriving by the one door that skips the looking.
    from_catalog = _optional_flag(payload, "from_catalog", "from_catalog_invalid")
    sku = _require_text(
        payload,
        "sku",
        "sku_required",
        "Send `sku` — the TCGplayer Id of the candidate row being chosen.",
    )
    condition = _require_text(
        payload,
        "condition",
        "condition_required",
        "Send `condition` — the condition string of the candidate row being chosen, "
        "copied from that row.",
    )

    key = master.position_key(box, index)

    with Store().write() as snapshot:
        # EVERY REFUSAL LIVES IN `_answer_target`, which is this route's validation moved
        # whole so the group route can run the identical checks — card before queue, one
        # governing entry, the pair checked against the offered row. Nothing is written
        # until it returns.
        card, holders, offering, governing, _, offered_condition = _answer_target(
            snapshot, box, index, sku, condition, from_catalog=from_catalog
        )

        # READ BEFORE THE WRITE, WHICH IS THE ENTIRE REASON THE UNDO IS POSSIBLE (D28). This is
        # the pair the reversal puts back, and this lock is the last moment anything knows it —
        # two lines down the card carries the answer instead. It travels into the `answered`
        # line below and comes back out through `_answer_before` when the undo arrives.
        #
        # A MAPPING WITH NULL MEMBERS IS THE NORMAL CASE AND NOT AN EMPTY ONE. A card queued for
        # review has usually never carried a SKU — that is why it is in a queue — so the pair is
        # `{sku: null, condition: null}`, and putting THAT back is exactly right: the reversal
        # returns the card to carrying no answer. The mapping is what makes it legible, per the
        # `do_put_card` rule above: `_history` drops a None extra, so a flat `previous_sku`
        # would vanish precisely when the answer was written onto a blank card, and a line
        # recording nothing would be indistinguishable from a line recording no change.
        restores_to = {"sku": card.sku, "condition": card.condition}

        card.sku = sku
        card.condition = offered_condition

        cleared = {queues.MAIN: False, queues.PARKED: False}
        for queue, entry in holders:
            entry.cleared_by_human = True
            cleared[queue.name] = True

        # THE GOVERNING QUEUE IS NAMED, not the pair that was cleared. Which files had this
        # position in them is bookkeeping about the question; which file's rows the answer
        # was allowed to come from is the thing the laundering refusal above turns on, and it
        # is what a reader needs to check a choice against `review.json` afterwards.
        #
        # `reason` RIDES ALONG BECAUSE IT IS FREE AND BECAUSE IT IS THE SAME STRING
        # EVERYWHERE. `docs/DESIGN.md` requires the machine reason code on screen beneath its
        # human label precisely so it stays greppable from the screen to the run report to
        # `review.json`; this makes the history the fourth place it reads identically, and
        # `no_market_data` answered as a holofoil is a different kind of session from
        # `metadata_detection_disagreement` answered the same way.
        #
        # `restores_to` IS ON THE LINE WHATEVER THE ANSWER BELOW REPORTS, and the two are
        # deliberately allowed to disagree. This line is the audit trail and records what is
        # true; the field on the response is a question about a control — "should the screen
        # offer an undo" — which the listing hold can answer no to while the pair itself remains
        # perfectly knowable. An operator who pulls the listing an hour later and repairs the
        # card by hand needs this line, and suppressing it to match a button would be the log
        # editing itself to agree with a screen.
        _history(
            snapshot.inventory,
            ANSWERED,
            key,
            sku=sku,
            condition=offered_condition,
            queue=offering.name,
            reason=governing.reason,
            restores_to=restores_to,
            # D46. Present only when it is true, because `_history` drops a None extra — so
            # every line already on disk keeps its exact shape and a reader can tell a row the
            # PIPELINE offered from a row a HUMAN went and found. Those are different claims
            # about how much the machine knew, and after the write there is no other evidence
            # which one happened.
            #
            # D77 DROPPED THE `not governing.candidates` HALF, AND THAT IS THE FLAG FINALLY
            # MEANING WHAT ITS NAME SAYS. Under D46 the two conditions could not come apart,
            # so the extra clause cost nothing and read as belt-and-braces; now they can, and
            # keeping it would have written `from_catalog` off a card that had rows and
            # silently omitted it off a card whose rows were wrong — which is exactly the
            # answer the line most needs to distinguish, because it is the one where the
            # pipeline had a confident offer and a human overruled it.
            from_catalog=True if from_catalog else None,
        )

        # WHETHER THE UNDO WILL BE ALLOWED, ANSWERED NOW RATHER THAN AT THE TAP THAT FAILS. This
        # is the whole contract of the field and it is `SaleResult.restores_to`'s, transplanted:
        # a control offered for a reversal the server has already decided to refuse has exactly
        # one behaviour, which is to tell its user to press it again.
        #
        # ONE THING MAKES IT NULL HERE, AND IT IS `undo_too_late`. `_listing_hold` asks whether
        # the SKU just written is already out of this Mac — the same question `do_delete_card`
        # asks, with the same answer: reversing an answer whose row is sitting in an emitted
        # import file leaves that file, and then TCGplayer, disagreeing with the inventory. It
        # is checked AFTER the write because the card now carries the answered SKU, which is
        # the SKU the reversal will be asked about twenty seconds from now.
        #
        # The other null — history cannot say what the answer replaced — cannot arise on this
        # path, because this call is the thing writing that history. It is why the field is
        # nullable all the same: `_reverse_answer` refuses in `answer_origin_unknown` for a log
        # written by a server older than this change, and one shape reads both directions.
        held = _listing_hold(snapshot.inventory, card)

        body = {
            "answered": key,
            # THE SAME STRING UNDER THE NAME THE SALE ROUTE USES, and both are kept. `answered`
            # is this route's own word and predates the reversal; `position` is what makes one
            # client type read an answer and its undo without asking which direction it is
            # holding. Neither is dropped: T7 asserts `answered`, and a wire contract is not
            # renamed to tidy up a second one arriving beside it.
            "position": key,
            # False on this direction. The app reads it rather than comparing a card's SKU
            # against a queue file, so one field says which way the call went.
            "undone": False,
            "box": int(box),
            "index": int(index),
            "sku": sku,
            "condition": offered_condition,
            # What an undo of THIS call would put back, or null when it would be refused. Read
            # it as present-or-null and never for its contents: both members are legitimately
            # null for a card that had no answer before this one, which is most of them.
            "restores_to": None if held else restores_to,
            # Reported the way undo reports what it removed, and for the same reason: a
            # write says what it touched. Both true is the entry-in-both-queues case, which
            # is worth seeing rather than smoothing over — and it is the case the client
            # needs, since a screen holding both lists must drop BOTH rows on one answer or
            # go on showing a card whose answer is already written. Both keys are always
            # present, false rather than absent, so the app reads two booleans and never has
            # to tell "not cleared" from "the server did not say".
            "review_cleared": cleared[queues.MAIN],
            "parked_cleared": cleared[queues.PARKED],
            "card": _card_row(snapshot.inventory, box, index, card),
        }

    return body


def _clearing_event(events, key: str):
    """The newest event that CLOSED this position's question, or None. D37.

    `_answer_before`'s scan, generalised to the two events that set `cleared_by_human`:
    `answered` and `stood_down`. The reversal of either has to know which one it is looking
    at, because reopening a queue entry is the same store operation for both and the wrong
    one would take back an answer the operator never meant to touch.

    A `renumbered` LINE THIS POSITION SITS ABOVE IS A HARD STOP, exactly as it is there and
    for the identical reason (D10, ruling 1): the mid-box delete slides a DIFFERENT physical
    card into every index above the deleted one, so a clearing line older than the shift
    belongs to this slot's previous occupant. Reversing it would reopen one card's question
    against another card's record.
    """
    try:
        at_box, at_index = (int(part) for part in str(key).split("/"))
    except (TypeError, ValueError):
        at_box = at_index = None
    for event in reversed(list(events)):
        if (
            at_box is not None
            and event.get("event") == RENUMBERED
            and event.get("box") == at_box
            and isinstance(event.get("from"), int)
            and at_index >= event["from"]
        ):
            return None
        if event.get("position") != key:
            continue
        if event.get("event") in (ANSWERED, STOOD_DOWN):
            return event
    return None


def do_review_stand_down(box: int, index: int, payload: dict) -> dict:
    """Close a queued question without answering it, and leave the card alone. D37.

    THE CONTROL docs/DESIGN.md ASKED FOR BY NAME. That file has carried Skip as an OPEN
    QUESTION since the review screen was built — *"If nothing is ever skipped, delete the
    control. If most of a queue is, the screen needs a real defer that records a reason, and
    that is a decision entry rather than a button."* The owner pulled that trigger on
    2026-08-25, asking for *"a stand down on the flag ... i get that this is a wasted
    position"*. This is the real defer, and D37 is the decision entry.

    IT IS NOT AN ANSWER AND IT IS NOT A DEPARTURE, which is the whole of what makes it a
    third thing worth having:

      an answer (D4)      writes a SKU and a condition onto the card. The pipeline is told
                          what the card IS, and every later join reads it back as rung 0.
      a retirement (D26)  writes a terminal state. The CARD has left inventory; the record
                          stays and the gap is permanent.
      a stand-down        writes NOTHING to the card. It does not move, change, or leave. It
                          keeps its slot, its photograph and its place in the box walk, and
                          it stays sellable if it is ever identified properly. What closes is
                          the QUESTION.

    SO IT SETS `cleared_by_human` AND NOTHING ELSE, and that flag was already exactly this
    idea. `store/queues.py` was built around it — `Queue.upsert` refuses to re-queue a cleared
    position, `Queue.release` refuses to drop one, `open_entries` hides it — so the machinery
    for "stop asking, and keep not asking across every future run" has existed since before
    the review screen did. Until now the only thing that could set it was an answer, and an
    answer costs a SKU written onto a real card. That is the gap: the operator who wanted to
    dismiss a question had to either invent an identification or press Skip, which
    deliberately writes nothing at all and is forgotten on reload.

    THE REASON IS REQUIRED, AND THAT IS docs/DESIGN.md's WORDING RATHER THAN A PREFERENCE —
    "a real defer that RECORDS A REASON". Without it the queue file would carry a population
    of dismissed cards indistinguishable from answered ones, and the instrument that decides
    whether Skip should exist at all would still not exist. `store/queues.py`'s three reasons
    are its own vocabulary and not `master.RETIRE_REASONS`, because those four all mean the
    card is gone.

    BOTH QUEUES ARE CLEARED, for `do_review_answer`'s reason: a position can hold an open
    entry in each file, and clearing one would leave the screen still showing the card.

    IT GOES BOTH WAYS, and the reversal is `_reverse_stand_down`. Same twenty-second shape
    the answer and the sale already ship (D28), same dispatch on one path so a stale client
    cannot reach the reversal without having been told what it reverses.

    NO LISTING HOLD IS CONSULTED, and it is worth saying why this route is not `undo_too_late`'s
    customer. That guard asks whether a SKU this Mac wrote is already out in an import file.
    A stand-down writes no SKU, changes no SKU, and moves no listing count — there is nothing
    downstream that could disagree with anything, in either direction.
    """
    undo = _optional_flag(payload, "undo", "undo_invalid")
    if undo:
        _reject_unknown(payload, UNDO_FIELDS)
        return _reverse_stand_down(box, index)

    _reject_unknown(payload, STAND_DOWN_FIELDS)
    reason = _require_text(
        payload,
        "reason",
        "reason_required",
        "Send `reason` — why this question is being closed without an answer: "
        + ", ".join(queues.STAND_DOWN_REASONS),
    )
    try:
        reason = queues.check_stand_down_reason(reason)
    except queues.UnknownStandDownReason as exc:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "stand_down_reason_invalid",
            f"{reason!r} is not a stand-down reason. One of: "
            + ", ".join(queues.STAND_DOWN_REASONS)
            + ". Never coerced and never defaulted — the reason is the record.",
        ) from exc

    key = master.position_key(box, index)

    with Store().write() as snapshot:
        holders = [
            (queue, queue.entries[key])
            for queue in (snapshot.review, snapshot.parked)
            if key in queue.entries
        ]
        if not holders:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "not_in_queue",
                f"{key} is in no queue file, so there is no question to stand down from.",
            )
        open_holders = [(q, e) for q, e in holders if not e.cleared_by_human]
        if not open_holders:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "already_cleared",
                f"{key} has already been settled — answered or stood down. Nothing was "
                f"written. Reload to see the queue as it stands.",
            )

        governing = open_holders[0][1]
        for _, entry in open_holders:
            entry.cleared_by_human = True

        _history(
            snapshot.inventory,
            STOOD_DOWN,
            key,
            reason=reason,
            queue=open_holders[0][0].name,
            # The QUEUE's reason for asking, beside the operator's reason for declining to
            # answer. Two different strings that both matter, and the pair is what makes the
            # log answerable to "which questions get waved off, and why" — which is the
            # measurement docs/DESIGN.md says has never been taken.
            queue_reason=governing.reason,
        )

        return {
            "position": key,
            "box": int(box),
            "index": int(index),
            "stood_down": True,
            "undone": False,
            "reason": reason,
            "queue_reason": governing.reason,
            "queues_cleared": [q.name for q, _ in open_holders],
            # Always reversible on this route: nothing downstream can be holding a stand-down,
            # because it writes nothing a downstream reader looks at. Stated as a field anyway
            # so one client shape reads this route and the answer route alike.
            "reversible": True,
        }


def _reverse_stand_down(box: int, index: int) -> dict:
    """Put a stood-down question back on the screen. D37, and the answer undo's twin.

    THREE REFUSALS, AND THE MIDDLE ONE IS THE WHOLE REASON THIS IS NOT `_reverse_answer`:

      not_in_queue      no entry in either file. The question is gone — a later run released
                        it, or the client is asking about another card.
      not_stood_down    the entry is open (nothing to reverse — which is also what a SECOND
                        undo gets, exactly as the answer's reversal does), or it was cleared
                        by an ANSWER rather than a stand-down. That second case is the guard:
                        reopening it here would take back a real identification through a
                        control the operator pressed to un-dismiss something.
      stand_down_origin_unknown
                        the log cannot say which event closed this question — written by a
                        server older than this route, or a position sitting above a
                        `renumbered` line, where the clearing line belongs to the slot's
                        previous occupant. `answer_origin_unknown`'s exact twin.

    IT PUTS BACK NOTHING BUT THE FLAG, because the flag is all the stand-down wrote. No SKU,
    no state, no count — so unlike the answer's reversal there is nothing to read out of
    history and nothing that can have drifted underneath it.
    """
    key = master.position_key(box, index)
    store = Store()

    with store.write() as snapshot:
        holders = [
            (queue, queue.entries[key])
            for queue in (snapshot.review, snapshot.parked)
            if key in queue.entries
        ]
        if not holders:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "not_in_queue",
                f"{key} is in no queue file, so there is nothing to put back.",
            )
        cleared = [(q, e) for q, e in holders if e.cleared_by_human]
        if not cleared:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "not_stood_down",
                f"{key} is already waiting in its queue — nothing is standing to reverse.",
            )

        # INSIDE THE LOCK, for `_answer_origin`'s reason unchanged: a history read taken
        # before the lock is the lost update the lock exists to prevent, and D13 puts a
        # second device on this store with no session between them. Broad except for the
        # same reason too — a bad line, an unreadable file and non-UTF-8 bytes are one
        # condition here ("the log cannot say") with one remedy.
        try:
            event = _clearing_event(store.history(), key)
        except (files.StoreError, OSError, ValueError):
            event = None
        if event is None:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "stand_down_origin_unknown",
                f"the log cannot say what closed {key}'s question, so nothing here will "
                f"guess. Answer the card instead, or reopen it with a fresh join.",
            )
        if event.get("event") != STOOD_DOWN:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "not_stood_down",
                f"{key} was closed by an ANSWER, not a stand-down. Take that back on "
                f"POST /review/{box}/{index}/answer with {{\"undo\": true}} — reversing it "
                f"here would drop a real identification through the wrong control.",
            )

        reopened = [q.name for q, _ in cleared if q.reopen(key)]

        _history(
            snapshot.inventory,
            STOOD_DOWN,
            key,
            undone=True,
            reason=event.get("reason"),
        )

        return {
            "position": key,
            "box": int(box),
            "index": int(index),
            "stood_down": False,
            "undone": True,
            "reason": event.get("reason"),
            "queues_reopened": reopened,
        }


def _reverse_answer(box: int, index: int) -> dict:
    """Take one review answer back. D28, and the server half of the twenty-second window.

    IT UNDOES EXACTLY WHAT THE ANSWER DID AND NOTHING ELSE, which is a short list because the
    answer's own list is short: `card.sku`, `card.condition`, and `cleared_by_human` on every
    queue entry it cleared. `do_review_answer` writes no state, moves no listing count and does
    not touch `store/cache.py` — it says so in its own docstring and each of those is argued
    there — so there is nothing else here to put back. A reversal that reached further than the
    write it reverses would be a second opinion about what an answer is.

    THE WINDOW IS THE SCREEN'S AND THERE IS NO CLOCK HERE. That is the owner's ruling, taken on
    the day: screen-held now, server-enforced only if it bites. It matches `do_mark_sold`
    exactly, and the reason `do_mark_sold` gives holds unchanged — a server-side deadline fails
    the reversal precisely when the store is slow to lock, and turns a mistake noticed a minute
    later into something only a hand-edit can repair.

    WHAT THAT COSTS IS WORTH WRITING DOWN RATHER THAN DISCOVERING. The window lives in
    `app/src/ReviewQueue.tsx` as a wall-clock deadline on a receipt in component state, so it
    does not survive a reload of that page, and D13's second device knows nothing about it: a
    browser that never saw the answer will never draw its undo. Both are accepted rather than
    overlooked. The trigger for revisiting is the first answer actually lost to a refresh, and
    the fix if it fires is a deadline on the `answered` line — which this route could enforce
    without any new state, since `_answer_before` is already reading that line's timestamp
    neighbourhood.

    FIVE REFUSALS, IN THIS ORDER, AND THE ORDER IS THE POINT:

      card_not_found         no record at that position. Same code and same reasoning as the
                             answer direction: a position with no card has nothing to reverse
                             ONTO, and telling the operator it is not in a queue would send him
                             to read the wrong file.
      not_in_queue           no entry in either queue file. The question is gone entirely — a
                             later run released it, or the client is asking about another card.
      not_answered           the entry is there and open. Nothing cleared it, so there is no
                             answer standing. This is also what a SECOND undo gets, and that is
                             the guard rather than a coincidence: the first reversal reopened
                             the entry, so the second finds it open and stops. Nothing has to
                             remember that a reversal happened.
      undo_too_late          the SKU is already out of this Mac. Not a new code and not a new
                             fact: `_listing_hold` is `do_delete_card`'s guard and its argument
                             transfers whole — an import file, and then TCGplayer, would be left
                             disagreeing with an inventory that no longer claims the SKU.
      answer_origin_unknown  `sold_origin_unknown`'s exact twin. The log cannot say what the
                             answer replaced, so nothing here guesses. Reachable for an answer
                             written before `restores_to` existed, and for a log that will not
                             parse.

    THE HOLD IS CHECKED BEFORE THE ORIGIN because they are refusals of different strength. "I
    cannot know what to put back" is a gap in the record and its remedy is a hand-repair; "you
    may not put it back" is a prohibition and stands whether the record is complete or not.
    Answering with the weaker one first would send an operator to fix a log for a reversal he
    was never going to be allowed.

    BOTH QUEUES ARE REOPENED, for the reason the answer clears both: a position can hold an
    entry in each file, and a reversal that reopened one would leave the card half-answered —
    waiting on one screen and cleared on the other, with `open_entries` disagreeing between
    them. `Queue.reopen` refuses anything that is not present and cleared, and its return is
    checked rather than assumed for `do_mark_sold`'s reason: a silent no-op reported as a
    success is v1 bug 5.
    """
    key = master.position_key(box, index)
    store = Store()

    with store.write() as snapshot:
        card = snapshot.inventory.cards.get(key)
        if card is None:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "card_not_found",
                f"No card at box {box}, card {index}. This route reverses an answer written "
                f"onto a card that exists; it never creates one.",
            )

        present: List[queues.Queue] = []
        cleared: List[queues.Queue] = []
        for queue in (snapshot.review, snapshot.parked):
            entry = queue.entries.get(key)
            if entry is None:
                continue
            present.append(queue)
            if entry.cleared_by_human:
                cleared.append(queue)

        if not present:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "not_in_queue",
                f"Box {box}, card {index} has no entry in the review or parked queue, so "
                f"there is no answer here to take back. A later run may have released it. "
                f"Reload the queue.",
            )

        if not cleared:
            # NOT `already_answered`'s OPPOSITE NUMBER BY ACCIDENT. The answer direction refuses
            # a cleared entry and this one refuses an open entry, and both send the operator to
            # reload for the same reason: whichever it is, this screen is holding a queue the
            # store has moved past. The likeliest cause of THIS one is the second device (D5,
            # D13) having reversed it already, and the second likeliest is a second press of an
            # undo that worked.
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "not_answered",
                f"Box {box}, card {index} is still waiting in the queue, so there is no "
                f"answer standing to reverse. It may already have been taken back — here, or "
                f"on the other device. Reload the queue.",
            )

        held = _listing_hold(snapshot.inventory, card)
        if held:
            summary = ", ".join(f"{count} {stage}" for stage, count in held)
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "undo_too_late",
                f"Box {box}, card {index} was answered as SKU {card.sku}, and that SKU is "
                f"already out of this Mac: {summary}. Taking the answer back would leave an "
                f"import file — and then TCGplayer — holding a listing the inventory no longer "
                f"claims. Undo stops at `emit`. Pull the listing on TCGplayer first if the "
                f"answer was wrong, or correct the card by hand; either way the queue entry "
                f"stays as it is.",
            )

        previous, origin_unknown = _answer_origin(store, key)
        if previous is None:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "answer_origin_unknown",
                # The reason travels, exactly as it does for a sale: "no line says what it
                # replaced" and "the log will not parse" are one refusal and two repairs, and
                # the second one is a file to go and fix.
                f"Box {box}, card {index} carries an answer, but {origin_unknown}, so there "
                f"is nothing to put back. Leave the answer as it is, or set the card's SKU by "
                f"hand — a card restored to a SKU nobody recorded is a wrong listing rather "
                f"than a missing one.",
            )

        withdrawn = {"sku": card.sku, "condition": card.condition}
        card.sku = previous["sku"]
        card.condition = previous["condition"]

        reopened = {queues.MAIN: False, queues.PARKED: False}
        for queue in cleared:
            if not queue.reopen(key):
                # Unreachable through this function — `cleared` was built from the same
                # entries inside the same lock — and checked anyway, because the alternative
                # to checking is reporting a success for a write that did not happen, on the
                # one screen whose whole promise is that the card comes back.
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "inventory_conflict",
                    f"Box {box}, card {index} left the {queue.name} queue between being read "
                    f"and being written. Retry; if it repeats, another process is writing "
                    f"the queue files outside the store lock.",
                )
            reopened[queue.name] = True

        # THE LINE THAT KEEPS THE LOG FROM LYING. Without it `history.jsonl` says a SKU was
        # written onto this card and never says it came off, and `store/__init__.py` calls this
        # file inventory truth over time — a log is only worth having while it can be believed.
        # It carries both pairs because both are facts a reader wants and neither is derivable
        # from the other once the card has moved on again: what was taken off, and what went
        # back on.
        _history(
            snapshot.inventory,
            UNANSWERED,
            key,
            withdrew=withdrawn,
            restored=previous,
            queues=", ".join(queue.name for queue in cleared),
        )

        body = {
            "position": key,
            # True: this call reversed an answer. Same field, same meaning, same job as the
            # sale route's — the app reads it instead of comparing before-and-after states.
            "undone": True,
            "box": int(box),
            "index": int(index),
            "sku": card.sku,
            "condition": card.condition,
            # Always null on a reversal, and it means only that there is nothing left to
            # reverse. `SaleResult` states the same rule in the same words: do not read it as
            # a second undo being available.
            "restores_to": None,
            # Which files this put a card back into, mirroring the answer's two cleared flags.
            # Always present and false rather than absent, so the screen reads two booleans and
            # never has to tell "not reopened" from "the server did not say".
            "review_reopened": reopened[queues.MAIN],
            "parked_reopened": reopened[queues.PARKED],
            "card": _card_row(snapshot.inventory, box, index, card),
        }

    return body


# ------------------------------------------------------------------------ the group answer


def _require_group_answers(payload: dict) -> List[Tuple[int, int, str, str, str]]:
    """The group body's shape, checked field by field. Returns (box, index, sku, condition,
    key) per element, in request order, or refuses — shape only, nothing about the store.

    POSITIONS COME FROM THE BODY HERE AND FROM THE PATH EVERYWHERE ELSE, which is why this
    route has shape refusals no other write needs. The path regexes admit digits or nothing,
    so `do_review_answer` never sees a boolean box; this one can, and `True` is an `int` to
    `isinstance`, so booleans are refused by name before the int check passes them.

    A DUPLICATE POSITION IS REFUSED, NOT DEDUPLICATED. Both elements would validate against
    the same open entry and both would then write, and the second write's `restores_to`
    would record the FIRST answer as what it replaced — an undo that puts back a SKU the
    operator never meant the card to keep. A body that names one card twice is a client bug,
    and deduplicating it here would be this server guessing which of two answers was meant.
    """
    _reject_unknown(payload, GROUP_ANSWER_FIELDS)
    answers = payload.get("answers")
    if not isinstance(answers, list) or not answers:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "answers_required",
            "Send `answers` — a non-empty list with one element per card, each carrying "
            "`box`, `index`, `sku` and `condition` copied off that card's own single "
            "candidate row.",
        )

    parsed: List[Tuple[int, int, str, str, str]] = []
    seen: set = set()
    for at, element in enumerate(answers):
        where = f"answers[{at}]"
        if not isinstance(element, dict):
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "answer_invalid",
                f"{where} is not an object. Each element carries "
                f"{', '.join(GROUP_ANSWER_ENTRY_FIELDS)} and nothing else.",
            )
        unknown = sorted(k for k in element if k not in GROUP_ANSWER_ENTRY_FIELDS)
        if unknown:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "answer_invalid",
                f"{where} names {', '.join(unknown)}, which this route does not read. "
                f"Each element carries {', '.join(GROUP_ANSWER_ENTRY_FIELDS)} and nothing "
                f"else — in particular no `undo`: a group is taken back per card through "
                f"POST /review/<box>/<index>/answer.",
            )
        box = element.get("box")
        index = element.get("index")
        if isinstance(box, bool) or isinstance(index, bool) or not isinstance(box, int) or not isinstance(index, int):
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "answer_invalid",
                f"{where} needs integer `box` and `index` — the position being answered, "
                f"as GET /queues reported it.",
            )
        sku = element.get("sku")
        condition = element.get("condition")
        if not isinstance(sku, str) or not sku.strip():
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "answer_invalid",
                f"{where} needs `sku` — the TCGplayer Id of that card's own candidate row.",
            )
        if not isinstance(condition, str) or not condition.strip():
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "answer_invalid",
                f"{where} needs `condition` — the condition string of that row, copied "
                f"from it.",
            )
        key = master.position_key(box, index)
        if key in seen:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "duplicate_position",
                f"{where} repeats {key}, which an earlier element already answers. One "
                f"element per card — remove the duplicate and send the group again.",
            )
        seen.add(key)
        parsed.append((box, index, sku.strip(), condition.strip(), key))
    return parsed


def _condition_grade(target: dict) -> str:
    """The GRADE a group member's answer writes — its condition with the finish folded away.

    THE GROUP USED TO CLUSTER ON THE CONDITION STRING, AND THAT SPLIT EVERY REAL QUEUE IN
    TWO. `Near Mint` and `Near Mint Foil` are one grade and two finishes, so a queue whose
    grade was never in question still arrived as two groups differing only by whether the
    card is foil. Measured on the owner's store the day this changed: of the 52 entries their
    runs generated, 40 offered exactly one row, every one of those rows Near Mint — 21
    `Near Mint` and 19 `Near Mint Foil`. Times three reason codes, that is up to six presses
    to confirm a grade D137 had already fixed by rule. The operator's words for it: *"i also
    somehow had to still claim items in bulk that they're near mint rather than it being
    default."*

    THE FINISH IS NOT A THING THE GROUP DECIDES, which is why folding it away is safe rather
    than merely convenient. Each member is answered with ITS OWN lone candidate row, and that
    row's finish was chosen by the ladder from that card's own metadata claim and detection —
    per card, before this route was reached. Answering thirteen normals and fourteen foils
    together writes each of the twenty-seven exactly the row it would have got alone. What
    the uniformity rule protects is that the question is the same and the reply is forced;
    neither depends on every card being the same finish.

    THE GRADE IS READ OFF THE REGISTRY AND NEVER PARSED OUT OF THE STRING. `Near Mint Foil`
    starting with `Near Mint` is a fact about Pokemon's and Riftbound's vocabulary rather
    than a rule, and a game whose Near Mint row is spelled some other way would silently
    become its own grade under a prefix test. A condition the game does not call Near Mint —
    `Unopened` is the live one — is its own grade and still groups only with itself, so a
    sealed product can never be swept into a group of singles.
    """
    game = str(getattr(target["card"], "game", "") or games.DEFAULT_GAME)
    condition = str(target["offered"])
    try:
        near_mint = _near_mint_conditions(game)
    except Exception:  # noqa: BLE001 - an unvocabularied game grades as itself, never as NM
        return condition
    return "near mint" if condition in near_mint else condition


def do_review_group_answer(payload: dict) -> dict:
    """Answer a homogeneous group of queued cards in one write.

    THE RULING IS docs/DECISIONS.md's "A homogeneous queue may be answered as a group" —
    the entry that reopens D4's one-card-at-a-time, narrowly, on Gate B's evidence: 16 of
    53 queued, every one the same reason code, detection agreeing with itself across every
    duplicate pair. One systematic fact about the rig's lighting, sixteen identical taps.
    Its narrowness IS the spec, and this route ENFORCES it rather than trusting the screen
    with it: without the uniformity refusal below, this route is a general bulk write any
    client can reach with a loop, which is exactly what that entry says may not exist.

    "EVERY ENTRY OFFERS THE SAME SINGLE CANDIDATE" IS READ AS: EACH ENTRY OFFERS EXACTLY
    ONE ROW — ITS OWN — AND THAT ROW SAYS THE SAME THING ON EVERY CARD. Three checks:
    one shared reason code across the group, exactly one candidate row per entry, and one
    condition string across those rows. What is deliberately NOT required is a shared SKU,
    and could not be: sixteen different physical cards are sixteen different catalog rows,
    and the entry cannot mean "answer card A with card B's SKU" — that is not a reading of
    it, it is data corruption wearing one, and it would put a real SKU from a real catalog
    row onto a card it was never proposed for, invisibly. What makes the sixteen taps
    identical is the SHAPE of each answer, not its row: the same question (the shared
    reason), one possible reply each (the lone row), every reply of one kind (the shared
    condition). Gate B's queue is the picture — 16 metadata_detection_disagreements, each
    offering only its own card's Near Mint row. The group write answers each card with its
    own lone candidate and nothing else.

    VALIDATE EVERYTHING, THEN WRITE EVERYTHING, INSIDE ONE `Store.write()`. The shape is
    `emit`'s — report and route before anything is written — applied at route scale. Phase
    one walks every position through `_answer_target`, which IS the single route's
    validation, and touches nothing; any refusal abandons the block, and `Store.write()`
    commits only on a clean exit, so a refused group changes NOTHING — not the cards that
    would have passed, not a queue flag, not a history line. A partial group must not
    report success: a body saying "eleven of sixteen landed" hands the screen a state
    neither queue file matches and the operator a question — which eleven? — that nothing
    on his screen can answer.

    TWO GROUP REFUSALS ON TOP OF THE SHAPE ERRORS, and they send the operator two
    different ways:

      group_entry_refused   one or more positions fail the single answer's own checks —
                            `already_answered`, `sku_not_a_candidate`,
                            `condition_mismatch` and the rest. The group may well have
                            qualified when the screen drew it; the store has moved past
                            that screen. Every failing position is named WITH ITS OWN CODE
                            in the message, so one 409 still reports per position. Reload
                            and re-filter.
      group_not_uniform     the group never qualified: more than one reason code, an entry
                            offering more than one row, or two condition strings across
                            the group. Those cards are answered one at a time, each beside
                            its own photograph — which is D4 unchanged, and the reason
                            this refusal exists at all.

    Entry failures are checked before uniformity, deliberately: a stale screen's remedy is
    a reload, and telling it "not uniform" about a group whose real problem is that half
    of it is already answered would send the operator to un-filter a queue that simply
    needs re-reading.

    THE REVERSAL IS NOT ON THIS ROUTE, AND THAT IS THE UNDO'S SHAPE RATHER THAN A GAP.
    Each position gets its own `answered` history line with its own `restores_to`, exactly
    as a single answer writes it — so `{"undo": true}` on POST /review/<box>/<index>/answer
    reverses any member of the group as if it had been answered alone, and the screen
    holding the group receipt loops that route per position. The write is all-or-nothing
    because a partial write reports a state no file matches; the reversal is per-card
    because a partial REVERSAL is real and must be reportable per position — one card's
    SKU already out in an emitted file (`undo_too_late`) must not hold fifteen reversible
    answers hostage, and must not be silently skipped either.

    `restores_to` COMES BACK PER POSITION, under the single answer's contract: null means
    an undo of that answer would be refused, and a screen offers the group's undo only
    when every member can come back — a group control that reverses eleven of sixteen on
    its best day is the defect `SaleResult` records, at scale.
    """
    parsed = _require_group_answers(payload)

    with Store().write() as snapshot:
        # PHASE ONE — every position validated, nothing touched. `_answer_target` writes
        # nothing, so a group refused here leaves the block having made no edit for
        # `Store.write()` to commit.
        targets: List[dict] = []
        refused: List[Tuple[str, BadRequest]] = []
        for box, index, sku, condition, key in parsed:
            try:
                card, holders, offering, governing, _chosen, offered = _answer_target(
                    snapshot, box, index, sku, condition
                )
            except BadRequest as exc:
                refused.append((key, exc))
                continue
            targets.append(
                {
                    "box": box,
                    "index": index,
                    "sku": sku,
                    "key": key,
                    "card": card,
                    "holders": holders,
                    "offering": offering,
                    "governing": governing,
                    "offered": offered,
                }
            )

        if refused:
            named = "; ".join(f"{key}: {exc.code} — {exc}" for key, exc in refused)
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "group_entry_refused",
                f"{len(refused)} of {len(parsed)} cards refused, so the whole group is "
                f"refused and nothing was written. Reload the queue and filter again — "
                f"the store has moved past the screen that drew this group. {named}",
            )

        # ELIGIBILITY — the ruling's two conditions, checked here and not only on the
        # screen. `governing` is the entry the single route would validate against, so a
        # position in both queue files is judged by its review entry exactly as a single
        # answer is.
        reasons = sorted({target["governing"].reason for target in targets})
        many_rows = [
            f"{target['key']} offers {len(target['governing'].candidates)} rows"
            for target in targets
            if len(target["governing"].candidates) != 1
        ]
        grades = sorted({_condition_grade(target) for target in targets})
        if len(reasons) > 1 or many_rows or len(grades) > 1:
            findings = []
            if len(reasons) > 1:
                findings.append(f"reasons {', '.join(reasons)} are mixed")
            findings.extend(many_rows)
            if len(grades) > 1:
                findings.append(f"grades {', '.join(grades)} are mixed")
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "group_not_uniform",
                f"This group may not be answered as one: {'; '.join(findings)}. A group "
                f"write needs one shared reason code, exactly one candidate row per card, "
                f"and one condition GRADE across the group — anything looser is answered "
                f"one card at a time, each beside its own photograph (D4). Nothing was "
                f"written.",
            )

        # PHASE TWO — the single route's write, per position, in request order. Same
        # fields, same history line, same read-before-write for the undo; the one addition
        # is `group` on the line, so a reader of history.jsonl can tell one press from
        # sixteen — the answers are identical in every other respect, which is exactly why
        # the log has to say so.
        results = []
        cleared_positions = []
        for target in targets:
            card = target["card"]
            restores_to = {"sku": card.sku, "condition": card.condition}
            card.sku = target["sku"]
            card.condition = target["offered"]

            cleared = {queues.MAIN: False, queues.PARKED: False}
            for queue, held_entry in target["holders"]:
                held_entry.cleared_by_human = True
                cleared[queue.name] = True

            _history(
                snapshot.inventory,
                ANSWERED,
                target["key"],
                sku=target["sku"],
                condition=target["offered"],
                queue=target["offering"].name,
                reason=target["governing"].reason,
                restores_to=restores_to,
                group=len(targets),
            )

            held = _listing_hold(snapshot.inventory, card)
            cleared_positions.append(target["key"])
            results.append(
                {
                    "position": target["key"],
                    "box": int(target["box"]),
                    "index": int(target["index"]),
                    "sku": target["sku"],
                    "condition": target["offered"],
                    # The single answer's contract, per member: null means the undo of
                    # THIS answer would be refused, decided now rather than at the press
                    # that fails.
                    "restores_to": None if held else restores_to,
                    "review_cleared": cleared[queues.MAIN],
                    "parked_cleared": cleared[queues.PARKED],
                }
            )

        body = {
            "answered": cleared_positions,
            "count": len(results),
            # The shared facts, stated once at the top because the whole route just
            # proved they are shared — the screen's receipt line is built from them.
            #
            # `grade` REPLACED `condition` ON 2026-09-12, because the group stopped being
            # one condition string. A member is answered with its own row's condition and
            # those may now differ by finish, so a single `condition` at the top would be a
            # lie about the other half of the group. What IS shared, and what the route just
            # checked, is the grade. Each member's own condition is on its own result row
            # below, where it has always been.
            "reason": reasons[0],
            "grade": grades[0],
            "results": results,
        }

    return body


# ------------------------------------------------------------------------------ mark sold


def _state_before_sale(events: Sequence[dict], key: str) -> Optional[str]:
    """The state to put back, read out of `history.jsonl`. None when it cannot be known.

    THE PRIOR STATE IS NOT STORED ON THE CARD, and it deliberately is not: `store/master.py`
    holds one `state` per card, `Inventory.parse` filters on `Card.__annotations__`, and a
    `previous_state` field would be a second piece of state to keep true through every
    transition in the pipeline for the sake of one ten-second window on one screen.

    IT DOES NOT NEED TO BE. `history.jsonl` is append-only and already records every
    transition — `set_state` and `record_capture` both log one — so the state a card was in
    before it sold is a fact the store has held all along. Reading it back needs no new event
    name either, and the reversal still adds none: a sale and its reversal read as
    `identified, sold, identified`, which is what happened.

    THE RULE IS THE LAST EVENT FOR THIS POSITION NAMING A STATE OTHER THAN `sold`. Scanning
    backwards rather than taking the second-to-last entry, so a position that somehow carries
    two adjacent `sold` events still restores to the state underneath them instead of to
    `sold`. Filtered against `master.STATES` so a non-state event in this log cannot be
    handed to `set_state` as one — which stopped being hypothetical on 2026-08-13, when the
    three routes above began appending `SERVER_EVENTS`. A card corrected between being listed
    and being sold has a `corrected` line sitting directly under its `sold` line, and this
    filter is the whole of why the reversal skips past it to `identified`. T7 asserts that
    path, and v2 widened the filter's job: the four D20 box events are in this log too, and
    `resectioned` sitting under a `sold` line is the same hazard `corrected` was.

    NONE IS A REFUSAL AND NOT A DEFAULT. Defaulting to `identified` is the obvious guess, and
    it is wrong for exactly the card that has never been identified — a copy captured and
    sold in person before any run touched it restores to `captured`, and only the log knows
    that. The vocabulary shrank in v2 and the argument did not: two states are still two, and
    guessing between them is still a listing that disagrees with TCGplayer. A store whose
    history was truncated gets told so.

    `retired` IS IN `master.STATES` NOW AND A SALE'S UNDO MUST NEVER ANSWER IT (D26). It
    cannot arise through these routes — `card_retired` refuses the sale of a retired card,
    and leaving `retired` logs the restored state, so the backwards scan from any real
    `sold` line meets that restored state first. A `retired` line directly under a `sold`
    one therefore means the history was edited by hand, and the branch below REFUSES rather
    than choosing either wrong answer: returning it would resurrect a departed card as
    `retired`-with-a-live-listing, and scanning past it to an older state would silently
    erase the retirement. `sold_origin_unknown` names a file to go and look at, which is
    what this situation is.

    `moved` IS `retired`'s SIBLING GUARD (D83), and for a sharper reason than symmetry:
    `set_state` accepts `moved` without complaint — it is a plain member of `master.STATES`
    — but `store/master.py:Inventory.move_card` is the ONLY correct way to reach it, and it
    never uses `set_state` at all. A `moved` line directly under a `sold` one is therefore
    not just hand-edited history, the way a `retired` one is; if this scan let it through as
    `previous` and a caller passed it to `set_state`, the card would land in state `moved`
    with no `moved_to`, no transplant, and no tombstone shape — a card claiming to have left
    through a door it never went through. Refused for the same reason `retired` is.
    """
    for event in reversed(list(events)):
        if event.get("position") != key:
            continue
        state = event.get("event")
        if state in (master.RETIRED, master.MOVED):
            return None
        if state in master.STATES and state != master.SOLD:
            return str(state)
    return None


def _state_before_retirement(events: Sequence[dict], key: str) -> Optional[str]:
    """`_state_before_sale`'s twin for the retirement's reversal (D26). Same rules.

    The prior state is read out of `history.jsonl` for the reasons the twin's docstring
    argues in full — it is not stored on the card, it does not need to be, and None is a
    refusal rather than a default. The scan is the mirror image: the last event for this
    position naming a state other than `retired`, filtered against `master.STATES` so the
    route-written `SERVER_EVENTS` stay inert to it. A `reshot` line under a `retired` one is
    this reader's version of the `corrected`-under-`sold` hazard, and the filter is what
    steps over it.

    `sold` REFUSES FOR THE MIRROR of the twin's `retired` guard. It cannot arise through
    these routes — `already_sold` refuses the retirement of a sold card, and a reversed sale
    logs its restored state on top — so a `sold` line directly under a `retired` one is
    hand-edited history, and restoring to it would fabricate a sale this store never
    recorded. `retired_origin_unknown` sends the operator to the file instead.

    `moved` REFUSES TOO (D83), same reason `_state_before_sale` refuses it: `moved` is
    reachable only through `Inventory.move_card`, which never calls `set_state`, so handing
    it back as a state to restore TO would put a card in that state with none of the
    tombstone shape `move_card` guarantees — no `moved_to`, no transplant.
    """
    for event in reversed(list(events)):
        if event.get("position") != key:
            continue
        state = event.get("event")
        if state in (master.SOLD, master.MOVED):
            return None
        if state in master.STATES and state != master.RETIRED:
            return str(state)
    return None


def _sale_origin(store: Store, key: str) -> Tuple[Optional[str], Optional[str]]:
    """The state to put back, or None and the reason it cannot be known. Never raises.

    A MALFORMED LINE IN `history.jsonl` DEGRADES TO "ORIGIN UNKNOWN" RATHER THAN TAKING THE
    ROUTE DOWN, which is the whole reason this wrapper exists. `files.read_jsonl` refuses the
    entire file over one bad line, and this read runs before either branch — so a single
    corrupt line stopped the SALE as well as the reversal and answered a Fulfiller's tap with
    `store_unavailable`. Measured: a hand-appended `{not json` left a card `captured` after a
    503. A sale is the one event in this product that has already happened in the physical
    world, and `CLAUDE.md`'s standing trade is that unlisted is fine and unrecorded is not.

    WHAT DEGRADING COSTS IS THE UNDO CONTROL AND NOTHING ELSE, which is why it is the right
    trade rather than a shrug. `restores_to` is already null-when-unknown and the app reads
    that null as "do not offer undo", so the Fulfiller sees a recorded sale with no undo
    button instead of a failed tap — and a reversal attempted anyway refuses in
    `sold_origin_unknown`, exactly as it does for a truncated history. Nothing guesses.

    THE READ STAYS INSIDE THE LOCK, which is the other repair that was considered. Moving it
    out addresses the parse cost — O(history), and history only ever grows — but addresses
    nothing about the corrupt line, and it pays for that with a value read before the lock
    was taken. `store/session.py` opens by explaining that a snapshot from before the lock is
    the lost update the lock exists to prevent: a card re-sold by the other device (D13)
    between the read and the lock would restore to the state it held two sales ago, and the
    reversal is the one thing here that must be exact. The cost is real and is recorded
    rather than hidden — one parse per sale, under a lock `Store.write()` already holds for a
    whole-store read.
    """
    return _origin(store, key, _state_before_sale)


def _retirement_origin(store: Store, key: str) -> Tuple[Optional[str], Optional[str]]:
    """The state a reversed retirement puts back, or None and why. `_sale_origin`'s twin.

    Everything that docstring argues holds here unchanged: a malformed history line degrades
    to "origin unknown" rather than blocking the RETIREMENT — the card really has left the
    box, and unrecorded is worse than unreversible — what degrading costs is the undo
    control and nothing else, and the read stays inside the lock.
    """
    return _origin(store, key, _state_before_retirement)


def _origin(store: Store, key: str, reader) -> Tuple[Optional[str], Optional[str]]:
    """The shared body of the two origin readers. Never raises — the arguments are theirs."""
    try:
        events = store.history()
    except (files.StoreError, OSError, ValueError) as exc:
        # Broad on purpose: a bad line, an unreadable file and non-UTF-8 bytes are one
        # condition to this route — history cannot say — and each of them must leave the
        # sale writable. Narrowing this to StoreError alone would re-open the same hole for
        # the next way a log file goes wrong.
        return None, f"the store's history could not be read ({type(exc).__name__}: {exc})"
    state = reader(events, key)
    if state is None:
        return None, "the store's history records no earlier state for it"
    return state, None


def _sell(snapshot, box: int, index: int, undo: bool) -> dict:
    """`do_mark_sold`'s whole body against an ALREADY-OPEN snapshot.

    Writes nothing to disk: the caller's `Store.write()` commits, so a refusal raised here
    discards every earlier card's state change AND its queued history lines. That is what
    lets one order pull mark three copies sold as one operation.

    Snapshot-only, deliberately, so it has the same shape as `_answer_target` above: one
    handle to keep in step rather than two. `_sale_origin` needs a `Store` because
    `Snapshot` has no `history()`, and `Store(snapshot.directory)` reads the identical
    `history.jsonl`.

    Raises exactly the refusals `do_mark_sold` raises and no others.
    """
    key = master.position_key(box, index)

    card = snapshot.inventory.cards.get(key)
    if card is None:
        raise BadRequest(
            HTTPStatus.NOT_FOUND,
            "card_not_found",
            f"No card at box {box}, card {index}. A sale is recorded against a card "
            f"that exists; this route never creates one.",
        )

    # Read inside the lock, before either branch writes. The `sold` event of the sale
    # being reversed was committed by an earlier request, so it is on disk by now —
    # `Store.write()` appends history after the yield, which is why this cannot see an
    # event the CURRENT request has queued and does not need to. `_sale_origin` never
    # raises: an unreadable history makes the origin unknown, it does not block the sale.
    # A caller selling SEVERAL positions inside one session must de-duplicate its positions
    # first: a position sold twice in the same session computes `previous` from pre-session
    # history both times, so the second sale's `restores_to` names the state the card held
    # before the first one rather than before it.
    previous, origin_unknown = _sale_origin(Store(snapshot.directory), key)
    was = card.state

    if undo:
        if was != master.SOLD:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "not_sold",
                f"Box {box}, card {index} is {was}, not sold, so there is no sale to "
                f"reverse. It may already have been reversed on the other device.",
            )
        if previous is None:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "sold_origin_unknown",
                # The reason is carried rather than assumed: "no earlier state" and "the
                # log will not parse" are one refusal and two repairs, and the second one
                # is a file to go and fix.
                f"Box {box}, card {index} is sold, but {origin_unknown}, so there is no "
                f"state to put back. Set it by hand rather than letting this guess — a "
                f"card restored to the wrong state is a listing that disagrees with "
                f"TCGplayer.",
            )
        restored = previous
    else:
        if was == master.SOLD:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "already_sold",
                f"Box {box}, card {index} is already sold. Send {{\"undo\": true}} to "
                f"reverse that sale; marking it again would record a second sale of one "
                f"physical card.",
            )
        if was == master.RETIRED:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "card_retired",
                f"Box {box}, card {index} is retired ({card.retire_reason}) — it left "
                f"inventory without a sale, and a sale recorded over that would replace "
                f"the record of a departure with a transaction that did not happen. If "
                f"it genuinely sold after all, send {{\"undo\": true}} to "
                f"`/inventory/{box}/{index}/retire` first, then mark it sold.",
            )
        if was == master.MOVED:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "card_moved",
                f"Box {box}, card {index} was moved to {card.moved_to} (D83) — this key "
                f"is a tombstone, not the card. Mark the transplant at {card.moved_to} "
                f"sold instead.",
            )
        restored = master.SOLD

    # `set_state` returns False only for a position with no record, and the card was
    # found above inside this same lock. Checked anyway rather than assumed: a silent
    # no-op reported as a success is v1 bug 5's exact shape, which is the reason that
    # return value exists at all.
    if not snapshot.inventory.set_state(key, restored):
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "inventory_conflict",
            f"Box {box}, card {index} vanished between being read and being written. "
            f"Retry; if it repeats, another process is writing inventory.json outside "
            f"the store lock.",
        )

    # THE SALE MOVES THE SKU'S `live` COUNT, WHICH IS THE HALF OF A SALE THAT USED TO BE
    # FREE. Until v2 a sold copy simply stopped wearing `live`, so the number of live
    # copies was a count of positions and it fell on its own. `live` is now a quantity on
    # `Listing` (D7 amended) and nothing decrements it unless this route does — a
    # Fulfiller pulling three copies would otherwise leave TCGplayer's cap arithmetic
    # (`Add to Quantity = min(cap - live, backstock)`) refilling against three copies
    # that are in the post.
    #
    # ONLY AN EXISTING LISTING IS TOUCHED, and `Inventory.listing()` is deliberately not
    # used even though it is the sanctioned accessor: it CREATES the record. A sale of a
    # card whose SKU was never emitted would then write a listing of all zeros, and — far
    # worse — the reversal of that sale would find the record it had just invented and
    # bump `live` to 1, claiming a copy is for sale on TCGplayer that was never pushed
    # there. A read on a route that may not have a listing is `.get`.
    #
    # WHAT IT IS AND IS NOT — AND THE TRADE IN THIS PARAGRAPH WAS RE-TAKEN AT D115. It used
    # to `bump(master.LIVE, -1)` and to read: "one edge is left standing rather than papered
    # over — `bump` floors at zero, so selling a copy while `live` is already 0 loses the
    # decrement, and a later reversal still adds one … Accepted, because the alternative is
    # recording a per-sale delta somewhere in order to reverse it exactly, which is a fourth
    # thing the store would have to explain for a number the export overwrites anyway."
    #
    # `sold_here` IS THAT PER-SALE DELTA, and two things changed to make it worth its keep.
    # First, the number the export "overwrites anyway" turned out to be the same number this
    # line was writing: `reconcile --live` wrote TCGplayer's figure, which ALREADY reflected
    # the sale, and this line then subtracted the same copy again — measured on the owner's
    # store as a SKU reading zero while TCGplayer held one. Second, D87's amendment dated the
    # readings, so "the export overwrites it anyway" stopped being true: an export overwrites
    # it only where it is NEWER, and a sale was making itself newer by forging a reading time.
    # The drift the paragraph accepted is closed by the same move, because the floor now lives
    # on `live_estimate` and on nothing stored.
    #
    # ONLY AN EXISTING LISTING IS TOUCHED — see the paragraph above, unchanged: `.get` rather
    # than `Inventory.listing()`, so a sale of a never-emitted SKU cannot invent a record.
    listing = snapshot.inventory.listings.get(card.sku) if card.sku else None
    if listing is not None:
        listing.sale(undone=undo)

    body = {
        "position": key,
        "box": int(box),
        "index": int(index),
        # True when this call reversed a sale. The app reads this rather than comparing
        # states, so one field answers "which way did that go" in both directions.
        "undone": bool(undo),
        "state": card.state,
        "previous_state": was,
        # What an undo of THIS call would put back, or null when history cannot say.
        # Null on a reversal because there is then nothing to reverse; null on a sale
        # means the undo control should not be offered, which is worth knowing at the
        # moment of the sale rather than at the tap that fails.
        "restores_to": None if undo else previous,
        # What this sale did to the SKU's counts, or null when it did nothing — the card
        # carries no SKU, or its SKU has no listing record. Added rather than left
        # implicit because every other write in this file says what it touched, and
        # because this is the one field on the response that is about the OTHER copies:
        # a Fulfiller pulling the third of four wants to see two still live. Additive to
        # the contract `app/src/Fulfillment.tsx` reads — every key it already reads,
        # including `restores_to`, is unmoved.
        "listing": asdict(listing) if listing is not None else None,
        "card": _card_row(snapshot.inventory, box, index, card),
    }

    return body


def do_mark_sold(box: int, index: int, payload: dict) -> dict:
    """Mark one copy sold, or put its state back. D10, and the server half of undo.

    SOLD IS A STATE, NEVER A REMOVAL (D10). The record stays, the position stays, and the
    position is never reused — `Inventory.next_index` is a high-water mark that counts every
    state, so the gap a sale leaves is permanent and a printed label is still true a year
    later. Nothing here deletes anything, and that is the difference from
    `do_delete_card`: undo of a CAPTURE removes a card that was never listed, undo of a SALE
    is a state transition backwards.

    ONE COPY, NOT ONE SKU. D7 keeps every copy as its own position with its own photo
    precisely so an order pull can mark one of them sold and leave the rest listed. The
    position in the path is the whole of the selection.

    THE UNDO WINDOW IS THE APP'S; THE REVERSIBILITY IS THIS ROUTE'S. `docs/DESIGN.md`
    requires undo on every mark-sold with at least a ten-second window, and there is
    deliberately no expiry here. A server-side deadline would fail the reversal exactly when
    the network was slow, and would turn a mistake noticed a minute later — a Fulfiller
    tapping the row above the one he meant — into something only the owner can repair by
    hand. What the ten seconds govern is how long the control is on screen.

    NO CONFIRM DIALOG IS IMPLIED BY ANY OF THIS. `docs/DESIGN.md` bans one on a reversible
    action, and this route is what makes the action reversible.

    WHICH STATES MAY BE SOLD FROM — anything but the two terminal ones, and the second is
    new. The permissive half stands on its original grounds: `docs/DESIGN.md` and D10 say
    what a sale IS and never say which cards may have one, and refusing a card whose SKU was
    never listed on TCGplayer would leave a person holding a card he has genuinely sold with
    no way to record it — against `CLAUDE.md`'s standing trade that unlisted is fine and
    unrecorded is not. The cost of being wrong is one reversible state change.

    `retired` REFUSES, AND THE NARROWING IS D26's OWN LOGIC APPLIED BACK. The paragraph this
    replaces recorded the open edge in as many words: a card pulled out, damaged or given
    away had no state of its own, so the permissive rule was "today the only way to record
    one" — a sale record that lies. That entry is ratified, the lie has a truthful
    replacement, and a sale recorded over a retirement would overwrite the record of a
    departure with the record of a transaction that did not happen. It is also what makes
    the reversal exact: with `card_retired` refusing here, no `sold` line can ever sit
    directly on a `retired` one, so `_state_before_sale` can never be asked to restore a
    sale to `retired` — and it refuses rather than answers if a hand-edited history asks
    anyway. A retired card that then genuinely sells is two honest steps: reverse the
    retirement, record the sale.

    ONE `Store.write()` for either direction, and nothing outside the store is touched — no
    photo, no sidecar, no queue entry. A sold card keeps its capture photo, which is what the
    pull preview shows (D6) and what makes a dispute answerable afterwards.

    IT MOVES TWO THINGS NOW, NOT ONE: the card's state, and the SKU's `live` count. The
    second is new with v2 and is not bookkeeping — `live` used to fall out of a scan over
    positions and now nothing decrements it unless this route does. The comment at the bump
    has the whole argument, including the one edge it accepts rather than hides.

    A SALE IS NEVER BLOCKED BY `history.jsonl`. The log is read here to say what an undo
    would put back, and `_sale_origin` degrades an unreadable one to "origin unknown" rather
    than refusing — the reversal is what loses, and only the reversal. Its own docstring has
    the argument, including why the read stays inside the lock.
    THE BODY LIVES IN `_sell`, AND THIS ROUTE IS THE THIN HALF OF IT. A second caller — an
    order pull marking several copies sold and writing the order ledger — has to do all of
    it inside ONE `Store.write()`, and a caller looping this route would take the lock once
    per copy and lose all-or-nothing. The precedent is `_answer_target` above, shared
    verbatim by the single review answer and the group one for the same reason: one
    implementation rather than two, because the second copy is the one that stops being
    exact the first time a check changes.
    """
    _reject_unknown(payload, SOLD_FIELDS)
    undo = _optional_flag(payload, "undo", "undo_invalid")
    with Store().write() as snapshot:
        return _sell(snapshot, box, index, undo)


def do_retire(box: int, index: int, payload: dict) -> dict:
    """Mark one copy retired — it left inventory without a sale — or put its state back.

    `sold`'s SIBLING, RATIFIED AS D26: a card pulled out, damaged, lost or given away.
    Before this route the store offered exactly two ways to record one, and D26 names them
    both as the problem — a sale record that lies, or the mid-box delete D10 forbids. Like a
    sale it is a terminal STATE and never a removal: the record stays, the position stays,
    the gap is permanent, and the capture photo stays where it is, which is what lets the
    retirement be questioned later.

    THE REASON IS REQUIRED, ONE OF `master.RETIRE_REASONS`, AND TRAVELS THREE PLACES AT
    ONCE: onto the record (`retire_reason`), into the history line `Inventory.retire`
    appends, and back in the response. It is the one fact about the departure nothing can
    re-derive, so recording the state without it would answer "where is this card" with
    "gone" and nothing else.

    MIRRORS `do_mark_sold` DELIBERATELY, refusal for refusal. One route in both directions
    with `{"undo": true}`; the undo window is the app's and the reversibility is this
    route's, with no server-side expiry; one `Store.write()` either way; no queue entry, no
    photo and no sidecar are touched. `already_sold` is the boundary with the sibling: a
    sold card is not retirable — it left by the other door, and retiring it would overwrite
    the record of a real sale. The mirror-image guard lives on the sale route as
    `card_retired`, and the pair is what keeps each terminal state's history clean enough
    for the other's reversal to read.

    IT DOES NOT TOUCH THE SKU'S LISTING COUNTS, AND THE ASYMMETRY WITH THE SALE IS THE
    POINT. `do_mark_sold` COUNTS its sale in `sold_here` (D115) because a TCGplayer sale moves TCGplayer's own
    quantity and the local number estimates that. A retirement is invisible to TCGplayer —
    the listing, if there is one, is still up with one fewer copy behind it — so the honest
    local estimate is UNCHANGED. What shrinks is `copies_on_hand`, which now excludes
    terminal states, so the next emit's refill arithmetic stops counting the copy; pulling
    the live listing down is a TCGplayer action the next join then observes (D8, D11).

    THE REVERSAL CLEARS THE REASON AS WELL AS THE STATE. A captured card carrying
    `retire_reason: "damaged"` would read as a fifth state nothing defines; the reason
    survives in the history line, which is the record of the retirement that WAS, exactly
    as `unanswered` leaves the `answered` line standing.
    """
    _reject_unknown(payload, RETIRE_FIELDS)
    undo = _optional_flag(payload, "undo", "undo_invalid")
    if undo:
        # A reversal carrying a reason has confused the two directions — the reason it sent
        # would be silently ignored. Same rule, same code as the review answer's undo.
        _reject_unknown(payload, UNDO_FIELDS)
        reason: Optional[str] = None
    else:
        raw = _optional_text(payload, "reason")
        if raw is None or raw not in master.RETIRE_REASONS:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "retire_reason_invalid",
                f"reason was {payload.get('reason')!r}; send one of "
                f"{', '.join(master.RETIRE_REASONS)}. The reason is required because it is "
                f"the one fact about the departure the record cannot re-derive later.",
            )
        reason = raw

    key = master.position_key(box, index)
    store = Store()

    with store.write() as snapshot:
        card = snapshot.inventory.cards.get(key)
        if card is None:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "card_not_found",
                f"No card at box {box}, card {index}. A retirement is recorded against a "
                f"card that exists; this route never creates one.",
            )

        # Read inside the lock, before either branch writes — `do_mark_sold` has the full
        # argument, including why this cannot and need not see the event the current
        # request has queued. `_retirement_origin` never raises: an unreadable history
        # makes the origin unknown, it does not block the retirement.
        previous, origin_unknown = _retirement_origin(store, key)
        was = card.state

        if undo:
            if was != master.RETIRED:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "not_retired",
                    f"Box {box}, card {index} is {was}, not retired, so there is no "
                    f"retirement to reverse. It may already have been reversed on the "
                    f"other device.",
                )
            if previous is None:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "retired_origin_unknown",
                    # The reason is carried rather than assumed — one refusal, two repairs,
                    # and the second one is a file to go and fix. `sold_origin_unknown`'s
                    # twin, for the twin operation.
                    f"Box {box}, card {index} is retired, but {origin_unknown}, so there "
                    f"is no state to put back. Set it by hand rather than letting this "
                    f"guess — a card restored to the wrong state is a listing that "
                    f"disagrees with TCGplayer.",
                )
            # Checked for the reason `do_mark_sold` checks it: a silent no-op reported as a
            # success is v1 bug 5's exact shape.
            if not snapshot.inventory.set_state(key, previous):
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "inventory_conflict",
                    f"Box {box}, card {index} vanished between being read and being "
                    f"written. Retry; if it repeats, another process is writing "
                    f"inventory.json outside the store lock.",
                )
            # After the state write and inside the same session, so the two commit together
            # or neither does. See the docstring for why the reason does not outlive the
            # retirement on the CARD while its history line stands.
            card.retire_reason = None
        else:
            if was == master.SOLD:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "already_sold",
                    f"Box {box}, card {index} is sold — it left inventory by the other "
                    f"door, and retiring it would overwrite the record of a real sale. If "
                    f"the sale is the mistake, send {{\"undo\": true}} to "
                    f"`/inventory/{box}/{index}/sold` first.",
                )
            if was == master.RETIRED:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "already_retired",
                    f"Box {box}, card {index} is already retired "
                    f"({card.retire_reason}). Send {{\"undo\": true}} to reverse it; "
                    f"retiring it again would record a second departure of one physical "
                    f"card.",
                )
            if was == master.MOVED:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "card_moved",
                    f"Box {box}, card {index} was moved to {card.moved_to} (D83) — this "
                    f"key is a tombstone, not the card. Retire the transplant at "
                    f"{card.moved_to} instead.",
                )
            # `Inventory.retire` is the state write, the reason write and the history line
            # in one method — see its docstring for why the three must not come apart. The
            # return value is checked exactly as `set_state`'s is above.
            if not snapshot.inventory.retire(key, reason):
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "inventory_conflict",
                    f"Box {box}, card {index} vanished between being read and being "
                    f"written. Retry; if it repeats, another process is writing "
                    f"inventory.json outside the store lock.",
                )

        body = {
            "position": key,
            "box": int(box),
            "index": int(index),
            # True when this call reversed a retirement. The app reads this rather than
            # comparing states, so one field answers "which way did that go".
            "undone": bool(undo),
            "state": card.state,
            "previous_state": was,
            # What an undo of THIS call would put back, or null when history cannot say.
            # Null on a reversal because there is then nothing to reverse; null on a
            # retirement means the undo control should not be offered, known at the moment
            # of the write rather than at the tap that fails.
            "restores_to": None if undo else previous,
            # The reason as the record now carries it: the vocabulary word on a retirement,
            # null after a reversal. The history line is where a reversed retirement's
            # reason survives.
            "reason": card.retire_reason,
            "card": _card_row(snapshot.inventory, box, index, card),
        }

    return body


def do_reshoot(box: int, index: int, payload: dict) -> dict:
    """Replace the photo and sidecar at an existing position. The record is untouched.

    D26's SECOND HALF, AND NOT A DELETE, NOT A CAPTURE: a bad photograph discovered later
    than D10's undo can reach — undo walks back only the newest capture — previously had no
    remedy at all, and `undo_too_late` told the operator to leave the position alone. The
    operation that fits D10 is this one: new bytes and a rebuilt sidecar at the SAME
    position, record untouched, position label unchanged, allocator never involved. The
    card's identity, state, claims and `captured_at` all describe the card and the capture
    session, not the picture, so none of them moves.

    THE OLD PHOTO IS REPLACED, NOT ARCHIVED — D26 says so in as many words. An archive
    would also be a live hazard, not just clutter: `identify.sidecar.scan` turns EVERY
    photo-suffixed file under `captures/cards/` into a capture and therefore a paid Batch
    request, so an archived copy would be billed and identified as a second card. The
    replace is `files.write_atomic`, so a crash mid-write leaves the old bytes whole rather
    than half of each. What survives of the first photograph is the `reshot` history line,
    carrying both capture ids — the boundary between the two pictures, the way `removed` is
    the boundary between two cards at a reused index.

    THE SIDECAR IS REBUILT FROM THE RECORD, never from the request. `RESHOOT_FIELDS`
    carries no claims, so a re-shoot cannot smuggle in a correction: changing what the
    operator SAID about the card is `PUT /inventory/<box>/<index>`'s job, with its
    `corrected` history line. The rebuild is byte-for-byte the PUT route's — every claim in
    `CLAIM_WIRE_NAMES`, read off the card — because a sidecar the reader cannot trust to
    match the record would send D3 rung 1 a claim nobody made.

    A SOLD OR RETIRED CARD REFUSES — a photo of a card that left is a photo of nothing.
    For a sold card the stored photo is also the dispute record (`do_mark_sold`: what makes
    a dispute answerable afterwards is that the sold card keeps its capture photo), and
    replacing it would swap the evidence for a picture of whatever is in the stand today.
    Two codes, because the remedies differ and each names its own way back.

    `capture_id` IS REQUIRED AND IS THE NEW PHOTOGRAPH'S — one id per photograph, exactly
    as at capture. It lands on the record because the record's `capture_id` names the
    photograph stored at the position, and that is now this one; the id it replaces goes
    into the history line. A replay of this same request (the lost-response retry) finds
    its own id already on this card and rewrites the same bytes, burning nothing; the same
    id on a DIFFERENT card refuses, because writing it would poison the replay lookup with
    a `DuplicateCaptureId` for every later capture.
    """
    _reject_unknown(payload, RESHOOT_FIELDS)
    capture_id = _require_text(
        payload,
        "capture_id",
        "capture_id_required",
        "Send the new photograph's capture_id — one per photograph, held by the caller "
        "across any retry of it.",
    )
    blob = _require_image(payload)

    key = master.position_key(box, index)

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        card = inventory.cards.get(key)
        if card is None:
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "card_not_found",
                f"No card at box {box}, card {index}. A re-shoot replaces the photo of a "
                f"card that exists; a new card is a capture — POST /capture.",
            )
        if card.state == master.SOLD:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "card_sold",
                f"Box {box}, card {index} is sold, and its stored photo is the record of "
                f"what was sold — replacing it would swap the evidence a dispute is "
                f"answered with. If the sale was recorded in error, send "
                f"{{\"undo\": true}} to `/inventory/{box}/{index}/sold` first.",
            )
        if card.state == master.RETIRED:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "card_retired",
                f"Box {box}, card {index} is retired ({card.retire_reason}) — it has left "
                f"inventory, and a photo of a card that left is a photo of nothing. If it "
                f"is back in the box, send {{\"undo\": true}} to "
                f"`/inventory/{box}/{index}/retire` first.",
            )
        if card.state == master.MOVED:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "card_moved",
                f"Box {box}, card {index} was moved to {card.moved_to} (D83) — this key "
                f"is a tombstone with no photo of its own. Re-shoot the transplant at "
                f"{card.moved_to} instead.",
            )

        holder = inventory.card_by_capture_id(capture_id)
        if holder is not None and holder.key != key:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "capture_id_in_use",
                f"capture_id {capture_id!r} already names the capture at {holder.key}. "
                f"Every photograph gets a fresh id — mint a new one rather than reusing "
                f"another card's.",
            )

        previous_capture_id = card.capture_id

        # The caller's own integers, exactly as `_card_row` renders from them: the record
        # was found under their key, and they have already matched (\\d+)/(\\d+) in the
        # route, while the stored fields may be strings `Inventory.parse` never coerced.
        path = photo_path(box, index)
        path.parent.mkdir(parents=True, exist_ok=True)
        files.write_atomic(path, blob)
        files.write_json(
            sidecar_path(path),
            sidecar_payload(
                box,
                index,
                **{name: getattr(card, name) for name in CLAIM_WIRE_NAMES},
            ),
        )
        # Normally a no-op — the path is derived from the position and the position did not
        # move. It is a real write for one record shape: a card recorded by `emit` carries
        # a null photo, and a re-shoot of it is the first photograph that position has.
        card.photo = str(path)
        card.capture_id = capture_id

        _history(
            inventory,
            RESHOT,
            key,
            capture_id=capture_id,
            # None is dropped by `_history`'s own filter, so a record that predates capture
            # ids simply carries no `replaced_capture_id` — absent reads as "nobody
            # recorded one", which is the truth.
            replaced_capture_id=previous_capture_id,
        )

        body = _card_summary(inventory, card, created=False)
        body["sidecar"] = str(sidecar_path(path))

    return body


# -------------------------------------------------------------------------------- search

# Three ranks, and the order is the answer to "what did the operator most likely mean".
# `docs/DESIGN.md` does not specify this screen, so it is written as an assumption with the
# reasoning attached rather than as a rule:
#
#   exact number   `197/197` or `031` typed in full is a person reading a card in their
#                  hand. Nothing else they could have meant.
#   name prefix    `char` for Charizard. This is what typing feels like — a prefix is a
#                  word being started, and a substring is a word being searched for.
#   substring      everything else that matched anywhere, including SKU and set hint.
#
# A SKU MATCH IS DELIBERATELY NOT RANKED ABOVE THE OTHERS, and the reason it costs nothing
# is that a `TCGplayer Id` is unique: a query that matches one produces exactly one group,
# so where that group sorts among no other groups is not a question.
_RANK_EXACT_NUMBER = 0
_RANK_NAME_PREFIX = 1
_RANK_SUBSTRING = 2


def _card_number_key(card: master.Card) -> str:
    """`031/197` for this card, or "" when it has not been identified.

    `join.join_key` and not an f-string of the two fields: the zfill to three digits is the
    join key's own rule (`161/159` is a secret rare, not an error), and a second copy of it
    here would be a search that stops finding cards the pipeline can match.
    """
    if not card.number or not card.printed_total:
        return ""
    return join.join_key(card.number, card.printed_total)


def _number_display(card: master.Card) -> Optional[str]:
    """`198/219` for this card as a SCREEN draws it, or None where it has no number (D67).

    ONE FIELD RATHER THAN A COMPOSITION EACH SCREEN MAKES FOR ITSELF, and that is the defect
    rather than the tidying. Three files composed this in TypeScript and two of them tested
    `printed_total === null` a line below a test of `number` for null OR blank — so the 174
    records that store `""` there rendered `198/219/`. `pipeline/join.py:display_number` is
    now the only spelling of it, and it also removes the set code D55 removes for the key, so
    the ten glued reads stop reaching the screen as `UNL • 198/219`.

    THE RAW FIELDS STILL TRAVEL BESIDE IT, UNTOUCHED. `number` and `printed_total` are what
    the model read and `app/src/types.ts` says so; this is a fourth wire-only decoration in
    the shape `label`/`section`/`card` already take, and it is drawn rather than stored. The
    review queue deliberately does NOT get it — see D67: that screen is judging the read, and
    a cleaned-up number there would hide the evidence it exists to show.
    """
    return join.display_number(card.number, card.printed_total)


def _match_rank(card: master.Card, query: str) -> Optional[int]:
    """How well this card answers `query` (lowercased), or None if it does not.

    CASE-INSENSITIVE SUBSTRING ACROSS SIX FIELDS, and one of them is the join key rather than
    a stored column: `031/197` is how a collector says which card this is, and it is
    the string the run report and the queue file both print, so it is what gets pasted into
    a search box. Nothing here touches the catalog — this searches what the store recorded.

    `note` IS IN THE SUBSTRING PASS AND IN NO OTHER RANK, and that placement is the point of
    the field. A card the pipeline never identifies has no name, no number and no SKU — so
    the note is the ONLY thing it can be found by, and leaving it out would make the feature
    write-only. It is deliberately not a prefix or exact rank: it is prose a human typed
    ("blue-eyes, japanese"), not an identifier, and ranking it beside a collector number
    would let a chatty note outrank a real card's own name.
    """
    name = str(card.name or "")
    number = str(card.number or "")
    key = _card_number_key(card)
    # WHAT THE SCREEN DREW IS SEARCHABLE, WHICH IS D67 CLOSING ITS OWN SIDE EFFECT. Once the
    # copies list draws `198/219` for a record stored as `UNL • 198/219`, an operator reading
    # that row and typing it back had no way to find the card again — the fix to the render
    # would have created a string the search could not answer. Both spellings match now: the
    # raw field is still here, and the display form joins it.
    shown = _number_display(card) or ""

    if query in {number.strip().lower(), key.lower(), shown.lower()} - {""}:
        return _RANK_EXACT_NUMBER
    if name.lower().startswith(query):
        return _RANK_NAME_PREFIX
    for field in (
        name,
        number,
        str(card.sku or ""),
        str(card.set_hint or ""),
        str(card.note or ""),
        key,
        shown,
    ):
        if query in field.lower():
            return _RANK_SUBSTRING
    return None


def _distinct(values: Iterable) -> List[str]:
    """Non-empty values, deduplicated, first-seen order kept."""
    out: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _agreed(values: Iterable) -> Optional[str]:
    """The one value every copy agrees on, or None when they disagree or none has it.

    None-on-disagreement rather than first-wins, and it is the whole reason this helper
    exists. The SKU-less group collects every unidentified card that matched — cards with
    nothing in common but the operator's query — so a `number` lifted off whichever of them
    the dict happened to yield first would be a confident answer about a group that has none.
    """
    seen = _distinct(values)
    return seen[0] if len(seen) == 1 else None


def _copy_row(places: _Places, card: master.Card) -> dict:
    """One physical copy in a search result: where it is, what state it is in, its photo.

    `has_photo` IS A STAT, NOT `bool(card.photo)`, because the consumer is a browser deciding
    whether to request `GET /photo/<box>/<index>` — and that route serves from `photo_path`,
    not from the recorded field. The two come apart in both directions: a card recorded by
    `emit` rather than captured carries a null `photo` and may still have one on disk under
    the derived name, and a record copied from another machine's store carries an absolute
    path that is a lie here. One `stat` per matched copy, bounded by the result set.

    A COPY WHOSE POSITION WILL NOT RENDER STILL APPEARS, with a null `place`. Same rule
    `do_inventory` works under and for the same reason: the row is what the operator asked
    for, and dropping it would answer a search with silence about a card that matched.

    `capture_id` IS HERE FOR ONE READER AND IT IS THE ONE D90 NAMED (D93). The order walk aims
    every copy it records by this string — it is checked against the card actually at the slot
    (`capture_id_mismatch`), which is what makes a write survive a mid-box delete — and without
    it on this row the walk could aim only at the copies the resolver had already picked, so
    choosing a different copy meant walking to it first. The carve-out this reopens is the one
    in `app/src/types.ts:SearchCopy`, and it is narrower than it reads: what was refused there
    is a SECOND INVENTORY VIEW growing inside a search result — `confidence`, the run, the
    metadata. An identity is not a view. It is null for a record captured before ids were
    written, and a screen that needs one has to handle its absence.
    """
    try:
        key = card.key
    except (TypeError, ValueError):
        key = f"{card.box}/{card.index}"
    try:
        place = places.of(card.box, card.index)
        has_photo = photo_path(card.box, card.index).is_file()
    except (TypeError, ValueError, master.BadSections):
        place, has_photo = None, False
    return {
        "key": key,
        "state": card.state,
        "state_at": card.state_at,
        "has_photo": has_photo,
        "capture_id": card.capture_id,
        "place": place,
    }


def do_search(query: str) -> dict:
    """Find a card by name, number, SKU or set hint. Grouped by SKU, D7's map made visible.

    THE ANSWER IS A SKU AND ITS POSITIONS, WHICH IS THE SHAPE D7 ALREADY DESCRIBES: one
    import row, every copy kept as its own position with its own photo, and the app mapping
    SKU -> all positions holding it. `Inventory.positions_for_sku` and `copies_on_hand` have
    existed since the store did and nothing served them to a screen — so the question "where
    are my four Eiscues" was answerable only by reading `inventory.json`.

    THE SCAN IS ONE PASS AND THE COPIES COME FROM THE STORE'S OWN ACCESSORS. Matching walks
    every card once to find which SKUs answered; each surviving SKU is then rendered whole by
    `positions_for_sku`, in box-walk order, with `copies_on_hand` for the count. Building the
    copy list out of the matched cards instead would be a second scan AND a wrong answer: a
    query that matches on `set_hint` matches only the copies from that stack, and a group
    that showed three of five copies because two were captured with a different hint is worse
    than no search at all.

    A GROUP IS THE SKU, WHOLE — including copies that did not match the query themselves.
    That is the deliberate consequence of the paragraph above.

    UNIDENTIFIED CARDS GROUP UNDER `null` AND SORT LAST. They have no SKU to aggregate on and
    no listing behind them, so the group is a bag of individual cards rather than a product:
    its scalar fields answer null unless every card in it agrees (`_agreed`), and `names`
    carries whatever names there are. Last because a card the pipeline has not identified is
    not the one being looked for when a real match is on the same screen — and never dropped,
    because a card the pipeline could not name is exactly the card an operator searches for.

    LOCK-FREE, like every read here. THERE IS NO `cap` FIELD ANY MORE (D7, amended
    2026-09-08): the standing cap is deleted, so the only bound on a SKU is the shelf and
    `listable` is what the box holds. It stays on the wire as its own field rather than
    leaving the client to read `on_hand` twice — `app/src/CardLocations.tsx:headroom` is its
    reader and the arithmetic there is unchanged.
    """
    text = _require_query(query)
    needle = text.lower()

    inventory = Store().read().inventory
    places = _Places(inventory)

    ranked: Dict[str, int] = {}
    loose: List[master.Card] = []
    for card in inventory.cards.values():
        rank = _match_rank(card, needle)
        if rank is None:
            continue
        sku = str(card.sku).strip() if card.sku else ""
        if not sku:
            loose.append(card)
            continue
        # The BEST rank any copy achieved. Copies of one SKU differ in `set_hint` and can
        # differ in `name` (a re-identify writes what the model read that time), so one copy
        # can match on a prefix while another matches on a substring — and the group is as
        # good as its best member.
        ranked[sku] = min(rank, ranked.get(sku, rank))

    groups: List[dict] = []
    for sku, rank in ranked.items():
        copies = inventory.positions_for_sku(sku)
        listing = inventory.listings.get(sku)
        on_hand = len(inventory.copies_on_hand(sku))
        groups.append(
            {
                "sku": sku,
                "names": _distinct(card.name for card in copies),
                "number": _agreed(card.number for card in copies),
                "printed_total": _agreed(card.printed_total for card in copies),
                # AGREED ON WHAT THE SCREEN DRAWS, NOT ON WHAT THE MODEL TYPED (D67). The two
                # raw fields above stay exactly as they were and go on disagreeing: five
                # copies of Moonfall store `198/219` twice and `UNL • 198/219` and
                # `UNL - 198/219` once each, so `number` is correctly None and the group's
                # number row went silent while every copy's own row showed its own variant.
                # Folded through `display_number` all five say `198/219` and the group can
                # speak again. Measured on the owner's store: 11 of 102 SKU groups draw no
                # number today and **7 of them recover** — the other four disagree for real
                # (`044/106` against `044/166`, a digit misread) and stay silent, which is
                # `_agreed`'s job and is not what this changes.
                "number_display": _agreed(_number_display(card) for card in copies),
                "set_hint": _agreed(card.set_hint for card in copies),
                "condition": _agreed(card.condition for card in copies)
                or (listing.condition if listing is not None else None),
                # ZEROS RATHER THAN NULL FOR A SKU WITH NO LISTING RECORD. "Nothing has been
                # emitted for this SKU" is a fact, not an absence — `emit` creates the record
                # when it writes the row — so the screen can draw 0/0/0 without having to
                # tell "not listed" from "the server did not say".
                "listed": {
                    stage: (int(getattr(listing, stage)) if listing is not None else 0)
                    for stage in master.LISTING_STAGES
                },
                # BESIDE `listed` AND NOT INSIDE IT (D115). `listed` is a walk over
                # `LISTING_STAGES` and the counter is deliberately not a stage — putting it in
                # that dict would make it a fourth listing stage on three screens and inside
                # D34's release. These two are what a screen needs to draw both figures: the
                # READING TCGplayer gave and WHEN, and what has sold here since. The estimate
                # is `live - sold_here`, floored, and the client subtracts because a derived
                # value never rides `asdict`.
                "sold_here": int(getattr(listing, "sold_here", 0) or 0) if listing is not None else 0,
                "live_as_of": getattr(listing, "live_as_of", None) if listing is not None else None,
                "on_hand": on_hand,
                # D7 IN ONE FIELD: "listed quantity is min(cap, on hand)". The cap above is the
                # RULE and this is what the rule comes to for THIS SKU, which are different
                # numbers whenever the shelf holds fewer than a playset — and the screen wants
                # the second one. `cap` alone was drawn as the denominator of `listed N of ...`
                # and read as a target: a card the owner has exactly one of said "listed 0 of 4",
                # claiming three copies of headroom that do not exist. `pipeline/join.py`'s
                # `add_to_quantity` has always bounded the same way (`min(room, uncommitted)`),
                # so this reports what the pipeline would do rather than a ceiling above it.
                #
                # Computed HERE and not in the browser: `app/src/server.ts` records that the app
                # is forbidden from computing the live cap, and a `Math.min` over `cap` in
                # TypeScript is that rule living in two places.
                # NO CAP MEANS EVERY COPY ON HAND IS LISTABLE (D7, rewritten). D7's `min(cap, on hand)`
                # survives wherever a cap is set; with none, the shelf is the only bound and
                # `listable` is `on_hand` — which is what the screen must draw, or it reports
                # headroom against a ceiling nobody asked for.
                "listable": on_hand,
                "copies": [_copy_row(places, card) for card in copies],
                "_rank": rank,
            }
        )

    # Rank first, then the name the group is most likely to be recognised by, then the SKU
    # so the order is total and two runs of the same query cannot swap two rows.
    groups.sort(key=lambda g: (g["_rank"], (g["names"] or [""])[0].lower(), g["sku"]))
    for group in groups:
        del group["_rank"]

    if loose:
        loose.sort(key=lambda c: (str(c.box), str(c.index)))
        # Counted here rather than through `copies_on_hand`, which takes a SKU and these have
        # none. The rule it applies is the one D7 states as amended by D26 — a copy is on hand
        # because it exists and has not left, by either door — and it is one comparison against
        # the same tuple that method uses.
        loose_on_hand = sum(1 for card in loose if card.state not in master.TERMINAL_STATES)
        groups.append(
            {
                "sku": None,
                "names": _distinct(card.name for card in loose),
                "number": _agreed(card.number for card in loose),
                "printed_total": _agreed(card.printed_total for card in loose),
                # The same fold on the SKU-less bag, where `_agreed`'s None matters most: these
                # cards have nothing in common but the query, so a number here is only ever the
                # one every one of them carries.
                "number_display": _agreed(_number_display(card) for card in loose),
                "set_hint": _agreed(card.set_hint for card in loose),
                "condition": _agreed(card.condition for card in loose),
                "listed": {stage: 0 for stage in master.LISTING_STAGES},
                # THE LOOSE BAG HAS NO SKU, so it has no listing record and no reading —
                # zero and null, the same shape every other row carries (D115).
                "sold_here": 0,
                "live_as_of": None,
                "on_hand": loose_on_hand,
                # The same min as the keyed group above. Zero listing stages and no SKU to list
                # under, so this can only ever be read as "what it WOULD be worth if identified"
                # — which is the honest thing for it to say rather than a bare cap.
                "listable": loose_on_hand,
                "copies": [_copy_row(places, card) for card in loose],
            }
        )

    return {"query": text, "groups": groups}


# --------------------------------------------------------------------------------- boxes


# `_denominator` WAS HERE AND IS NOT (D58). It answered D20's question — a sealed box's
# frozen capacity, or an open box's fill so far — and existed as one function because two
# renderers needed the same answer, a box that said "40 of 250" on one screen and "40 of 53"
# on the other being the second-renderer failure with a number in it instead of a label.
#
# THE ANSWER IS NOW THE CARDS ON HAND, FOR AN OPEN BOX AND A SEALED ONE ALIKE, and that is
# forced by the numerator rather than chosen: `Position.slot` counts cards, so dividing it
# by a frozen capacity draws a card at a percentage of a box it is not at, drifting further
# wrong with every sale. `capacity` keeps its D20 job of recording how full the box got.
#
# The property the function bought is now held structurally instead, which is stronger:
# `_Places.view` computes it from the walk it already runs, and `_box_row` reads it off the
# SAME `_Places` instance rather than deriving its own. Two renderers, one scan, nothing to
# keep in step.


def _section_spans(
    box: int,
    layout: Tuple[int, ...],
    total: int,
    occupied: Tuple[int, ...],
    names: Optional[Dict[int, str]] = None,
) -> List[dict]:
    """Every section of one box: where it starts, where it ends, how many cards are in it.

    DERIVED BY WALKING `Position`, NEVER BY RE-DIVIDING THE INDEX. `pipeline/join.py` holds
    the only label formula in the repo and this is a view of the same thing one level up, so
    it asks `Position` where each section starts and ends and jumps to the next one — which
    means an undeclared box comes out as the ONE section it has and a declared box out of its
    dividers, with nothing here knowing which of the two it is looking at. That is what made
    deleting the 25-card default (D10, amended 2026-08-29) a change to one property rather
    than to this walk: an undeclared box now yields a single span from card 1 to the fill,
    and this loop discovers that the same way it discovers everything else.

    THE WALK IS BOUNDED BY SECTIONS, NOT BY CARDS. One `Position` per section rather than one
    per index, so a hand-edited capacity of a million costs a handful of iterations rather
    than a hung request.

    A DECLARED DIVIDER PAST THE FILL IS STILL A DIVIDER. The loop stops at the last index the
    box actually reaches, so the second pass adds any declared section the cards have not
    grown into yet, with a count of zero — a box whose layout was typed in before it was
    filled should show the layout that was typed in.

    `count` COUNTS THE CARDS ON HAND, AND THIS SENTENCE USED TO SAY THE OPPOSITE. It read
    "counts records, sold ones included", on the argument that a sold card keeps its
    position and the section still holds it as far as the physical box is concerned. D58
    retires that argument at its root: the box closes up behind a departure, so the section
    does NOT still hold it, and a count including it would disagree with what a person
    counts — which is the one thing every number in this walk now promises.

    EVERY NUMBER HERE IS IN `Position.slot`'s SPACE (D58), which is what keeps the dividers
    editor honest: it seeds from `start` and posts in the same space, and `do_put_box` maps
    it back through the same `occupied` before the store sees an index.
    """
    per_section: Dict[int, int] = {}
    for index in occupied:
        section = join.Position(box, index, layout, occupied).section
        per_section[section] = per_section.get(section, 0) + 1

    mapped = join.Position(box, 1, layout, occupied).layout

    spans: List[dict] = []
    seen: Set[int] = set()
    at = 1
    while at <= total:
        position = join.Position(box, occupied[at - 1], layout, occupied)
        end = position.section_end
        spans.append(
            {
                "section": position.section,
                "start": position.section_start,
                "end": end if end is not None else (total or None),
                "count": per_section.get(position.section, 0),
                # D132 — the operator's word for the section, joined by ordinal at read time
                # the way `box_name` is (D56); null where none was given.
                "name": (names or {}).get(position.section),
            }
        )
        seen.add(position.section)
        if end is None:
            break
        at = end + 1

    for ordinal, start in enumerate(mapped, start=1):
        if ordinal in seen:
            continue
        spans.append(
            {
                "section": ordinal,
                "start": start,
                "end": mapped[ordinal] - 1 if ordinal < len(mapped) else None,
                "count": per_section.get(ordinal, 0),
                "name": (names or {}).get(ordinal),
            }
        )

    spans.sort(key=lambda span: span["section"])
    return spans


def _box_row(
    inventory: master.Inventory, box: int, places: "Optional[_Places]" = None
) -> dict:
    """One box, as `GET /boxes` renders it and as both write routes answer with it.

    ONE RENDERER FOR THREE ROUTES, so a box that was just created and a box read back a
    second later are the same object on the wire. `POST` and `PUT` answer with this rather
    than with a summary of what they changed, because the Boxes screen redraws a row from
    the response and a summary would send it back for the rest.

    A BOX THAT HOLDS CARDS BUT HAS NO REGISTRY ENTRY RENDERS AS OPEN AND UNDECLARED. That is
    what it is: `Inventory.parse`'s migration and `ensure_box` both create exactly that shape,
    so a box the registry has never heard of is not a special case, it is the same case one
    step earlier. Listing it is the point — until D20 a box existed only because a card named
    one, and refusing to show those would hide every box captured before this change.

    NOTHING HERE MAY RAISE ON BAD DATA, `do_status`'s rule applied to the screen where a bad
    box is fixed. Two independent failures, degraded separately: a `sections` list that never
    went through `set_sections` and will not validate leaves `sections_detail` empty while the
    raw list is still echoed in `sections`, so the operator can see what is wrong with it; and
    a card record whose box or index will not coerce takes `fill`, `next_index` and the spans
    to null while `cards` and `sold` still count what could be read.

    `cards` COUNTS RECORDS THAT NAME THIS BOX AND `fill` IS THE HIGH-WATER MARK — they are
    different numbers and both are wanted. Sold cards leave permanent gaps IN THE INDEX, so
    a box with 53 records can have a fill of 60, and the difference is exactly how many holes
    the allocator has left behind it.

    `on_hand` IS THE THIRD NUMBER AND IT IS THE ONE ON THE SCREEN (D58). It counts located
    records that have not left by either door — the cards a person opening the box would
    count — and it is what every rendered number divides by now. The other two stay verbatim
    because `BoxOps` promises its census greps to `inventory.json` and they still do; what
    changed is that neither of them is the denominator any more.

    IT TAKES A `_Places` SO THE TWO RENDERERS CANNOT DISAGREE. `on_hand` and `sections_detail`
    both come off that instance's one walk, which is the same walk every `place` block on the
    screen was rendered from — the property `_denominator` used to buy by being one function,
    held structurally instead. `do_boxes` passes one instance down its whole list, so a
    thirteen-box read costs one scan rather than thirteen.
    """
    entry = inventory.box(box)
    view = (places or _Places(inventory)).view(box)
    occupied = view[3]

    cards = 0
    sold = 0
    retired = 0
    moved = 0
    listed = 0
    for card in inventory.cards.where(box=int(box)):
        try:
            if int(card.box) != int(box):
                continue
        except (TypeError, ValueError):
            # Skipped rather than refused, unlike `next_index`, and the difference is the
            # question being asked. That method refuses because it is about to hand out an
            # index and a skipped record hides the collision it would cause; this one is
            # counting what names box 3, and a record nobody can place names no box.
            continue
        cards += 1
        if card.state == master.SOLD:
            sold += 1
        elif card.state == master.RETIRED:
            retired += 1
        elif card.state == master.MOVED:
            # D83's third door. Reported for the same reason `sold`/`retired` are: once a
            # move can be one of `box_not_empty_of_commitments`'s grounds (a merged-away box
            # is left holding only tombstones), the delete panel needs to say so before the
            # operator presses anything, not discover it from a refusal.
            moved += 1
        # `elif` on the states and a SEPARATE `if` here, because they answer different
        # questions: the states are exclusive of each other, and a listing hold is a
        # fact about the SKU that a sold copy has as much as an identified one.
        if _listing_hold(inventory, card):
            listed += 1

    try:
        layout: Optional[Tuple[int, ...]] = inventory.sections_for(box)
    except master.BadSections:
        layout = None

    try:
        fill: Optional[int] = inventory.box_fill(box)
        next_index: Optional[int] = inventory.next_index(box)
    except (master.BadPosition, TypeError, ValueError):
        fill = next_index = None

    # D58: the denominator and the spans both come off the walk. A walk that degraded says
    # so with a null `on_hand` — not a zero, which would claim an empty box — and takes the
    # spans with it, exactly as an invalid layout already does one line down.
    on_hand: Optional[int] = len(occupied) if occupied is not None else None
    detail = (
        _section_spans(int(box), layout, len(occupied), occupied, inventory.section_names_for(box))
        if layout is not None and occupied is not None
        else []
    )

    return {
        "box": int(box),
        # THE TRUE INDEX OF THIS DRAWER, NEVER DRAWN (D145). It is here so a CLIENT can tell
        # two drawers that have worn one number apart — which is the whole of what the capture
        # screen's restore needs and the one question the number cannot answer.
        #
        # `bid` AND NOT `box_bid`, because this record IS a box. `server/pipeline_routes.py`
        # spells it `box_bid` on a run row, where `box`, `box_name` and `box_bid` are three
        # facts ABOUT some other object; here it sits beside `box` and `name` as this object's
        # own, which is the spelling `store/master.py`'s column and that module's scope block
        # already use.
        #
        # None IS AN ORDINARY ANSWER AND NOT A FAULT. A box holding cards with no registry
        # entry has no id to give (see above), and so does a store an older build migrated.
        # `app/src/CaptureScreen.tsx` has a named arm for it: where the store cannot tell its
        # drawers apart, the rule that predates the id decides, unchanged.
        "bid": master.int_or_none(entry.bid) if entry is not None else None,
        "name": entry.name if entry is not None else None,
        # The STORED list, not the validated tuple. They differ only when the file was edited
        # by hand, and that is exactly when the operator needs to see what is in it.
        "sections": list(entry.sections) if entry is not None else [],
        "state": entry.state if entry is not None else master.BOX_OPEN,
        "capacity": entry.capacity if entry is not None else None,
        "fill": fill,
        "next_index": next_index,
        "cards": cards,
        # D58 — what the box holds now, and the denominator of every number on the screen.
        # `cards` counts records and `fill` is the allocator's high-water mark; this counts
        # what a person would count, which is none of the same thing once anything has been
        # sold, retired or captured as a pooled card.
        "on_hand": on_hand,
        "sold": sold,
        # D34's two, and they are here so the delete panel can name WHICH of
        # `box_not_empty_of_commitments`'s three grounds is holding a box open before the
        # operator presses anything. `sold` was already reported and the other two were not,
        # which left a screen able to say a box has commitments and never which kind — and
        # the two kinds have different remedies: sold and retired reverse on their own
        # routes, a listing hold is released (D34) or waited out.
        #
        # COUNTED IN THE WALK THAT WAS ALREADY RUNNING, so this costs one comparison and one
        # dict lookup per card rather than a second pass. `listed` counts CARDS whose SKU
        # holds a stage, not SKUs and not copies: it is the number the refusal would name.
        "retired": retired,
        "moved": moved,
        "listed": listed,
        "sections_detail": detail,
    }


def _boxes_named(inventory: master.Inventory) -> List[int]:
    """Every box number a card names, ascending — refusing on a record whose box is not one.

    One `DISTINCT` over the indexed column since D88 rather than a walk over every record,
    and the refusal is kept: a NULL in that column is exactly a record `int()` refused, so
    it is loaded and coerced to raise `BadPosition` naming the card, as the walk did.
    """
    values = inventory.cards.distinct("box")
    if None in values:
        for key, _ in inventory.cards.select(("box",), box=None):
            _position_int(inventory.cards[key].box, f"box of card {key}")
    return sorted(int(value) for value in values if value is not None)


def _same_box(card: master.Card, box: int) -> bool:
    """Does this record name this box? Never raises; an unreadable record names none."""
    try:
        return int(card.box) == int(box)
    except (TypeError, ValueError):
        return False


def _box_holds_cards(inventory: master.Inventory, box: int) -> bool:
    """Does any record name this box? Never raises; an unreadable record is not evidence."""
    return bool(inventory.cards.select(("box",), box=int(box)))


def do_boxes() -> dict:
    """Every box this store knows about: the registry, plus any box a card names.

    THE UNION, NOT THE REGISTRY. `Inventory.parse`'s v1 migration registers every box a card
    names and `allocate_capture` calls `ensure_box`, so the two sets agree in practice — this
    is the read that keeps agreeing if they ever stop. A box that holds cards and is missing
    from the registry would otherwise be invisible on the one screen that could repair it.

    LOCK-FREE. `_box_row` is O(cards) and this calls it once per box, which is the same cost
    `Inventory.box_fill` already pays per call; boxes are counted in handfuls, and the
    alternative — one fused pass with the high-water rule reimplemented here — would put a
    second copy of `next_index` in the file that answers what `next_index` returns.
    """
    inventory = Store().read().inventory

    numbers: Set[int] = set()
    for key in inventory.boxes:
        try:
            numbers.add(int(key))
        except (TypeError, ValueError):
            continue
    for value in inventory.cards.distinct("box"):
        if value is not None:
            numbers.add(int(value))

    places = _Places(inventory)
    return {"boxes": [_box_row(inventory, box, places) for box in sorted(numbers)]}


def do_create_box(payload: dict) -> Tuple[HTTPStatus, dict]:
    """Register a box before a single card goes into it. D20's whole reason for existing.

    THE BOX THAT HOLDS NOTHING IS THE POINT. Before D20 a box could not be created empty, so
    the first thing that ever declared box 4 was a photograph landing in it — and a typo like
    33 for 3 was a valid int, a real photo and eventually a real listing, caught only by the
    `new_box` flag on the capture response and only on the first card. Creating the box first
    turns that into a number the operator typed once, on a screen, with the existing boxes
    listed beside it.

    CAPACITY IS NOT A FIELD HERE AND WILL NEVER BE. D20: nobody knows a box's capacity when
    they start filling it, and the number that matters is the one frozen when the lid goes
    on. A capacity accepted at creation would be a guess that every fraction drawn from the
    box then inherits.

    `box_exists` RATHER THAN AN UPSERT. `ensure_box` is idempotent and returns the incumbent,
    which is right for capture — a photo must never be refused because its box is already
    known — and wrong here: a create that quietly succeeded against an existing box would let
    the Boxes screen silently rename box 3 while the operator believed they were adding one.

    `box` IS NO LONGER REQUIRED, AND THAT IS THE POINT OF NAMES. The owner addresses a box by
    what it is called and does not care what number it carries: *"can't we have that box
    number primary key be something I don't care about though?"* So a request naming a box
    and no number gets the lowest free one from `next_box_number`, and the paragraph above
    about the operator typing a number once, with the existing boxes listed beside it, stops
    describing the common path — the 33-for-3 typo it guards against cannot be made at all
    when nobody types a number.

    ONE OF THE TWO IS STILL REQUIRED. A request with neither is not a box, it is an empty
    body, and inventing both halves of an object nobody described is how a registry fills
    with rows no one meant to make.
    """
    _reject_unknown(payload, BOX_POST_FIELDS)
    name = _optional_name(payload)
    if payload.get("box") is None and name is None:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "box_or_name_required",
            "Send a box number, a name, or both. A number alone registers an unnamed box "
            "the way this route always has; a name alone takes the lowest free number.",
        )
    sections = _optional_sections(payload)

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        # ASSIGNED INSIDE THE LOCK, never before it. `next_box_number` reads the registry and
        # the cards, and a number chosen outside the write would be a number another request
        # could take between the read and the write — the same race `allocate_capture` holds
        # this lock to prevent one scale down.
        box = _require_box(payload) if payload.get("box") is not None else inventory.next_box_number()
        if inventory.box(box) is not None:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "box_exists",
                f"Box {box} is already registered. Rename it or declare its dividers with "
                f"PUT /boxes/{box}; this route only creates.",
            )
        inventory.ensure_box(box, name=name)
        if sections is not None:
            # Through `set_sections` rather than by assignment, so the layout is validated
            # once, in the one place that owns the rule, and the `resectioned` event lands
            # with both layouts on it. On a new box that reads `[] -> [1, 31]`, which is the
            # honest description of what happened.
            inventory.set_sections(box, sections)
        body = _box_row(inventory, box)

    return HTTPStatus.CREATED, body


def do_put_box(box: int, payload: dict) -> dict:
    """Rename a box, declare its dividers, name its sections, seal it, or open it again.

    THE FOUR FIELDS ARE THE FOUR THINGS A BOX HAS THAT A HUMAN DECIDES — `section_names` is
    the fourth as of D132, keyed by the ordinal the screen prints. Its number is not
    among them — it is in the path, and a body that could change it would be a renumber,
    which D10 forbids outright: every position key, every photo directory and every label the
    operator has read off a screen is built from that number.

    SEALING IS THE ONE THAT MATTERS, and it is a write of exactly one number. `close_box`
    freezes `capacity` at the fill, and from that moment every `place` block in the product
    divides by it instead of by a total that grows — which is the difference between "#40 of
    53 so far" and D20's "#40 of 250 · 16% in". Re-opening puts capacity back to unknown
    rather than leaving a stale number standing, and refuses nothing: a box re-opened to take
    more cards is an ordinary correction.

    RE-SECTIONING RELABELS CARDS AND MOVES NO INDEX (D10, amended). Every card behind a moved
    divider renders in a different section from the moment this returns. That is correct when
    the layout was wrong and silent when the edit was, which is why `set_sections` logs both
    layouts rather than refusing the operation — the trail is the safety, not a confirmation
    dialog `docs/DESIGN.md` would ban anyway.

    IT ADOPTS A BOX THE REGISTRY HAS NEVER HEARD OF but that cards already name, rather than
    refusing it. `GET /boxes` lists exactly that box, so refusing here would put a row on a
    screen with a dead rename control on it. `box_not_found` is kept for the case it actually
    describes: a number nothing in this store has ever seen.

    A RENAME NOW APPENDS `box_renamed`, AND THE PARAGRAPH THIS REPLACES SAID WHY IT DID NOT.
    It read: "a name is a label, not a claim the pipeline spends money against". That was
    true while the box NUMBER was the only address — a duplicate or a changed name cost
    nothing but a confusing row on the Boxes screen. It stopped being true when the capture
    screen started finding a box by name: a rename relabels every card in the box, exactly
    as moving a divider relabels every card behind it, and D10 answered that case with a
    `resectioned` event carrying both layouts rather than by restricting the operation.

    The old paragraph also named the right place to put it, and that is where it went:
    `store/master.py:set_name` owns the event, so it is in the store's vocabulary rather
    than this file's — the confusion `SERVER_EVENTS` argues against for the three it does
    own. This route assigns nothing itself any more; it calls the method that logs.

    A DUPLICATE NAME NOW REFUSES, `name_taken`. Same reason: two boxes answering to one
    name is an ambiguous physical address the moment the name is how a box is reached.
    """
    _reject_unknown(payload, BOX_PUT_FIELDS)
    name = _optional_name(payload)
    sections = _optional_sections(payload)
    section_names = _optional_section_names(payload)
    state = _optional_box_state(payload)

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        if inventory.box(box) is None and not _box_holds_cards(inventory, box):
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "box_not_found",
                f"No box {box}. Create it with POST /boxes, or capture into it — a box "
                f"registers itself the first time a card lands in it.",
            )

        entry = inventory.ensure_box(box)
        if "name" in payload:
            # Through `set_name` rather than by assignment, which is what buys the
            # `box_renamed` line and the duplicate check. It takes `None` as "clear the
            # name" — the shape a cleared text field sends and a legitimate edit — where
            # `ensure_box`'s keyword only ever SETS one and could not express it.
            inventory.set_name(box, name)
        if sections is not None:
            # THE BODY SPEAKS COUNT SPACE AND THE STORE KEEPS INDICES (D58). `sections_detail`
            # renders every divider as the card number it stands in front of, and the editor
            # seeds from that — so an operator who types "section 3 starts at 168" is typing
            # the number they can see on the screen, and this is the one line that turns it
            # back into the 171 the store holds. `join.divider_index` is `Position._divider`
            # run backwards, beside it in the same file so the two cannot drift.
            #
            # THE FRONT OF THE BOX IS INDEX 1 WHATEVER HAS SOLD OUT OF IT, which is what
            # keeps `check_sections`' own rule — a layout starts at 1, because there is no
            # card before the front of a box — true when card 1 itself has left.
            occupied = _Places(inventory).occupied(box)
            if occupied is not None:
                gone = tuple(
                    sorted(
                        int(card.index)
                        for card in inventory.cards.where(box=int(box))
                        if _same_box(card, box) and card.state in master.TERMINAL_STATES
                    )
                )
                sections = master.check_sections(
                    [join.divider_index(k, occupied, gone) for k in sections]
                )
            inventory.set_sections(box, sections)
        if section_names is not None:
            # AFTER the layout, so a body that declares dividers and names them in one
            # request names the sections it just made. The store speaks divider indices and
            # refuses an ordinal past the layout — a typo, not a declaration (D132).
            try:
                inventory.set_section_names(box, section_names)
            except master.BadSections as exc:
                raise BadRequest(HTTPStatus.BAD_REQUEST, "section_unknown", str(exc)) from None

        # THE LID IS MOVED LAST, after any layout change in the same request, so a box that
        # is being declared and sealed together freezes its capacity with the layout already
        # in place. Only a real change is applied: re-opening an open box would otherwise
        # write a `box_reopened` event for a request that changed nothing, which is the
        # no-op-logging `do_put_card` refuses to do. Sealing a sealed box is NOT skipped the
        # same way — `close_box` raises, and the refusal is worth more than the silence,
        # because the alternative reading is that this call re-froze capacity at a new fill.
        if state == master.BOX_CLOSED:
            inventory.close_box(box)
        elif state == master.BOX_OPEN and entry.closed:
            inventory.reopen_box(box)

        body = _box_row(inventory, box)

    return body


def do_open_section(box: int, payload: dict) -> dict:
    """Put a divider in front of the next card, from the capture screen. D10 (amended).

    THE ROUTE EXISTS BECAUSE THE ACT DOES. D10 has said since 2026-08-23 that a box "carries
    its own list of divider indices, set by a **New section** control on the capture screen
    at the moment the real divider goes in" — and that control was never built. What shipped
    was `PUT /boxes/<box>` taking a whole layout, typed into a field on `#/inventory`, which
    is a different operation wearing the same words: it is performed later, from another
    screen, and it needs the operator to remember which card they were on. This is the one
    the entry described.

    IT TAKES NO INDEX, AND THAT IS THE WHOLE OF ITS SAFETY. `Inventory.open_section` reads
    `next_index` inside the store lock, so the divider lands in front of the card the next
    capture will actually take. A client that computed the index would be reading a
    high-water mark over the wire and sending it back — two lock acquisitions with a round
    trip between them, which `next_index`'s own docstring names as the lost update this
    store is built to avoid, and which at a 623 ms feeder cadence is not a theoretical race.

    A BODY IT DOES NOT READ, and it reads it anyway. `_body()` refuses an empty request as
    `body_required` for every write in this server, and mark-sold already documents the
    convention: send `{}`. `_reject_unknown` with no allowed fields is what makes a client
    that sends `{"at": 41}` — the obvious wrong guess about this route — get told the index
    is not settable rather than get a divider somewhere else.

    NO CONFIRM, AND IT IS NOT AN OVERSIGHT. D33's money gate and D34's release both refuse
    without one; neither reason applies here. Nothing is spent, nothing is destroyed, no
    fact is recorded on somebody's word that only they can check: the layout is editable
    from `#/inventory` and `resectioned` carries the layout it moved from, so a mis-press is
    reversed by typing the old list back. Adding a dialog to the screen the owner shoots a
    box from at feeder pace is what `docs/DESIGN.md` refuses in as many words.

    ANSWERS WITH THE BOX ROW, so the capture screen redraws the same object `GET /boxes`
    gave it — and, more to the point, gets `sections_detail` back. The screen's receipt says
    which section was opened and where it starts, and both numbers are the SERVER's own
    rendering of the layout rather than a length and a last element the client added up
    itself. `BoxOps.tsx` spends a comment on why that distinction is not pedantic.
    """
    # `_reject_unknown` with nothing allowed would render "Settable: ." — the one caller
    # for which its message does not compose. Same code, same first-thing-checked order,
    # and a sentence that says what to do instead of naming an empty list.
    if payload:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "field_not_settable",
            f"Cannot set {', '.join(sorted(payload))} here — this route takes an empty "
            f"body. The divider goes in front of the card the store's own next index "
            f"names, and nothing in a request can move it. To place one somewhere else, "
            f"send the whole layout to PUT /boxes/{box}.",
        )

    with Store().write() as snapshot:
        inventory = snapshot.inventory
        if inventory.box(box) is None and not _box_holds_cards(inventory, box):
            raise BadRequest(
                HTTPStatus.NOT_FOUND,
                "box_not_found",
                f"No box {box}. Create it with POST /boxes, or capture into it — a box "
                f"registers itself the first time a card lands in it.",
            )
        inventory.open_section(box)
        body = _box_row(inventory, box)

    return body


# --------------------------------------------------------------------------- the orders
#
# D66'S SCREEN HALF, AND IT IS FOUR ROUTES. `GET /orders` says which physical copies fill
# which line and why a line found nothing; `POST /orders/fetch` asks TCGplayer for this
# account's own orders and hands back a body the next route accepts unchanged; `POST
# /orders/ingest` takes the feed's word for what was bought; `POST /orders/pull` records
# the copies as they come out of the box and marks them sold in the same lock.
#
# D63 IS THE STORE UNDERNEATH — two maps, and the split between them is the guard. An
# ingest writes `ledger.orders` and nothing else: not a card, not a listing count, not one
# byte of `inventory.json`, which is true by construction because `store/orders.py` holds
# no `Inventory` at all. Only the pull writes the other map, and it writes the store
# beside it in the same `Store.write()`.


def _order_text(payload: dict, field: str, code: str, message: str) -> str:
    """A non-empty JSON STRING, or a refusal. Never `str()` over whatever arrived.

    `_require_text` above coerces, which is right for a hint typed into a text box and
    wrong for everything on this screen: a `source` of `{"en": "TCGplayer"}` would become
    the order key `{'en': 'tcgplayer'}` and nothing anywhere would say so. These values are
    identifiers, and an identifier this route had to guess at is a record nobody can find
    again.
    """
    raw = payload.get(field)
    if not isinstance(raw, str) or not raw.strip():
        raise BadRequest(HTTPStatus.BAD_REQUEST, code, message)
    return raw.strip()


def _order_optional_text(
    payload: dict, field: str, code: str, message: str
) -> Optional[str]:
    """An optional string the feed said, kept verbatim. A number is coerced; nothing else is.

    A feed spelling a unit price as `11.88` rather than `"11.88"` is the one coercion worth
    making — the value is the feed's own words either way and nothing joins on it. A list or
    an object in one of these fields is a caller sending a shape this route has never seen,
    and it refuses rather than storing the repr.
    """
    raw = payload.get(field)
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
        raise BadRequest(HTTPStatus.BAD_REQUEST, code, message)
    text = str(raw).strip()
    return text or None


def _engine_order(
    record: order_store.OrderRecord, ledger: order_store.Ledger
) -> order_engine.Order:
    """`store.orders.OrderRecord` → `pipeline.orders.Order`. THE ONLY ADAPTER, and it is here.

    Neither package may hold it. `store/orders.py` is a document and knows nothing about an
    `Inventory`; `pipeline/orders.py` is a resolver and stores nothing — a shared carrier
    would make each import the other's vocabulary to say what it already says. The server is
    where the two meet, so the mapping is one function at that seam.

    THE RESOLVER IS ASKED FOR WHAT IS STILL OWED, NOT FOR THE ORDER'S QUANTITY. Until the
    order walk arrived this passed `line.quantity` raw, and the ledger's recorded pulls were
    subtracted nowhere: after one of three copies was pulled the resolver still wanted three,
    found the two unsold and reported `short` — while the ledger said two were owed — and in
    a store with five copies it allocated three picks against a line owed two, taking a copy
    from every other order for that SKU. `Ledger.outstanding` is the quantity that reaches the
    engine now. A line owed nothing arrives wanting ZERO: the engine picks none and answers
    `resolved` with the breakdown still counted, which is how the screen keeps drawing a
    filled line's figures without a second implementation of `_Draw`.

    `kind` IS PASSED ONLY WHERE IT IS TRUTHY, and that is not a tidiness. The store leaves
    `kind` unvalidated and uses `None` for "the feed said nothing"; the engine's own default
    is `single` and its `__post_init__` raises `UnknownLineKind` for anything outside
    `LINE_KINDS` — `None` included. Passing the None through would make every line no feed
    classified take the whole screen down.
    """
    lines = []
    for line in record.lines:
        # THE OPERATOR'S CLAIM WINS OVER THE FEED'S SILENCE, AND NEVER OVER ITS WORD.
        # `Ledger.declared_kind` is what somebody ticked on `#/orders`; `line.kind` is what
        # the feed said. The feed is preferred where it said anything at all, because it is
        # describing its own catalogue — the operator's claim exists for the case D113 was
        # built for, which is a feed that says nothing (this one never does) and a line that
        # is plainly not a card. Reversed, one stale tick would silently outrank a
        # marketplace that later learned to classify its own products.
        declared = ledger.declared_kind(record.key, line.sku)
        chosen = line.kind or declared
        claimed = {"kind": chosen} if chosen else {}
        lines.append(
            order_engine.OrderLine(
                sku=line.sku,
                quantity=ledger.outstanding(record.key, line.sku),
                name=line.name,
                number=line.number,
                printing=line.printing,
                condition=line.condition,
                rarity=line.rarity,
                unit_price=line.unit_price,
                **claimed,
            )
        )
    return order_engine.Order(
        number=record.number, lines=tuple(lines), placed_at=record.placed_at
    )


def _order_stamps(numbers: Sequence[str]) -> Tuple[int, Dict[str, Tuple[str, ...]]]:
    """T2b's `locate`: order number -> the labels of the copies that still have to be picked.

    `server/shipping_routes.py:do_shipping_stamps` hands this the order numbers off one
    uploaded Export Shipping file and writes what comes back into Pirate Ship's three Rubber
    Stamp corners. It lives HERE and not there for the reason `_engine_order` lives here:
    that module holds a buyer's name and street address and must not also learn to open the
    store, and it cannot import this file in any case.

    A KEY OF THE MAP MEANS "THE LEDGER HOLDS THIS ORDER" AND ITS VALUE MEANS "AND HERE IS
    WHERE ITS COPIES ARE". The two are separate answers and the caller counts them
    separately: an absent key is an order nobody has read in, and an empty tuple is an order
    that is in the ledger with nothing left to pick. Collapsing them would make "we have
    never heard of this sale" and "this sale is already packed" the same figure on screen.

    IT STAMPS WHAT IS STILL OWED AND NEVER WHAT HAS ALREADY BEEN PULLED, and that is the one
    determination in here worth arguing. The obvious alternative is to stamp every copy of
    the order at the position it was recorded from, which fills more corners on a real store
    — 17 of the owner's 20 orders are fully pulled — and is actively harmful: D90 sells a
    copy as it is pulled, a sold card renders `join.departed_label` (`B3 #96`), and the box
    closes up behind it (D58), so that index now holds a DIFFERENT card. A stamp is a pick
    instruction, and one naming a slot whose occupant has changed sends a hand to the wrong
    shelf. An order with nothing outstanding has nothing to pick, and empty corners are the
    true answer for it.

    THE RESOLUTION IS THE WHOLE STORE'S IN ONE PASS, exactly as `do_orders` runs it, and this
    is not an efficiency choice. `pipeline/orders.py` refuses to offer a `resolve_one` because
    a per-order resolver cannot see what another order has already been promised and hands two
    buyers the same physical card; asking it only about the orders in this export would be
    that defect wearing a shipping label. The batch's numbers filter the ANSWER, never the
    question.

    A NUMBER TWO RECORDS SPELL IS NOT MATCHED AT ALL. `Ledger` keys on `source:number`
    precisely because a number is unique to a marketplace and not across two, and a shipping
    export carries the number alone — so where two sources spell one number there is no way
    to tell which sale this row is, and a guess would stamp one buyer's envelope with another
    buyer's shelf. It leaves the corners empty and is counted as unmatched.

    NOTHING IS LOGGED AND NOTHING IS WRITTEN. One snapshot read, `_Places` built and dropped
    inside this call, strings out.
    """
    wanted: Dict[str, str] = {}
    for raw in numbers:
        text = str(raw or "").strip()
        if text:
            wanted.setdefault(text.casefold(), text)

    snapshot = Store().read()
    ledger = snapshot.ledger
    if not wanted:
        return len(ledger.orders), {}

    # `None` PARKED IN THE SLOT for a number two records spell, so the second sighting is
    # what disqualifies it rather than the last one silently winning.
    seen: Dict[str, Optional[order_store.OrderRecord]] = {}
    for record in ledger.orders.values():
        folded = str(record.number or "").strip().casefold()
        if folded not in wanted:
            continue
        seen[folded] = None if folded in seen else record
    found = {folded: record for folded, record in seen.items() if record is not None}
    if not found:
        return len(ledger.orders), {}

    # THE SAME SEQUENCE `do_orders` RESOLVES IN, and the same reason: `Ledger.unfulfilled`
    # and `pipeline/orders.py:order_sequence` sort oldest-placed first with a missing stamp
    # LAST, so the screen deciding who gets the last copy and the label naming where it is
    # cannot disagree about which order comes first.
    sequence = sorted(
        ledger.orders.values(),
        key=lambda record: (record.placed_at is None, record.placed_at or "", record.key),
    )
    open_keys = {record.key for record in ledger.unfulfilled()}
    open_records = [record for record in sequence if record.key in open_keys]
    asked = [_engine_order(record, ledger) for record in open_records]
    behind = {id(order): record for order, record in zip(asked, open_records)}
    resolution = order_engine.resolve_all(snapshot.inventory, asked)

    places = _Places(snapshot.inventory)
    by_key = {record.key: folded for folded, record in found.items()}
    stamps: Dict[str, Tuple[str, ...]] = {wanted[folded]: () for folded in found}

    for answer in resolution.orders:
        folded = by_key.get(behind[id(answer.order)].key)
        if folded is None:
            continue
        labels: Optional[List[str]] = []
        for line in answer.lines:
            for pick in line.picks:
                try:
                    label = places.of(pick.box, pick.index).get("label")
                except (master.BadPosition, master.BadSections, TypeError, ValueError):
                    label = None
                if not label:
                    # ONE UNLABELLABLE COPY COSTS THIS ORDER EVERY CORNER, and it is the
                    # same call `_Places` makes for its own decoration: a degraded walk, a
                    # hand-edited divider layout or a pooled copy means the numbers on the
                    # label cannot be counted to, and a partial pick list looks complete.
                    labels = None
                    break
                labels.append(str(label))
            if labels is None:
                break
        stamps[wanted[folded]] = () if labels is None else tuple(labels)

    return len(ledger.orders), stamps


def _pulled_positions(inventory: master.Inventory, copies) -> List[dict]:
    """Where each pulled copy sits RIGHT NOW: `{capture_id, box, index}`, composed per answer.

    THE JOIN THE COPIES PANEL NEEDS AND NOTHING STORES (D36). The ledger holds capture ids,
    the walk is keyed by position, and a pulled copy is sold — so it is in no pick, and the
    walk has nothing but this to say which slot it came out of. The panel's `GET /search` rows
    do carry a capture id since D93, so a client COULD match them here; that would be a second
    implementation of a join the store is already indexed for, and the one that ran in the
    browser would be the one with no `card_by_capture_id` to be right about duplicates.
    `card_by_capture_id` is an
    indexed lookup under D88 and is answered here, once per recorded copy; a card that is
    gone, or a duplicate id the store refuses to guess between, answers nulls rather than
    taking `GET /orders` down.
    """
    out: List[dict] = []
    for capture_id in copies:
        try:
            card = inventory.card_by_capture_id(str(capture_id))
        except master.DuplicateCaptureId:
            card = None
        out.append(
            {
                "capture_id": str(capture_id),
                "box": card.box if card is not None else None,
                "index": card.index if card is not None else None,
            }
        )
    return out


def _order_progress(
    ledger: order_store.Ledger, record: order_store.OrderRecord, inventory: master.Inventory
) -> List[dict]:
    """What WE have recorded against each line of one order. The ledger's own half.

    `recorded` rather than `progress`, which is the accessor that INVENTS an empty row and
    stores it — a read that created a fulfilment entry would put a row in the ledger
    claiming a pull that never happened, every time a screen was drawn.
    """
    key = record.key
    rows = []
    for line in record.lines:
        row = ledger.recorded(key, line.sku)
        rows.append(
            {
                "sku": str(line.sku).strip(),
                "wanted": int(line.quantity),
                "recorded": int(row.fulfilled),
                "outstanding": ledger.outstanding(key, line.sku),
                # Normally zero, and never created by a pull. A later ingest that REDUCES a
                # quantity underneath a legitimate pull is what makes it non-zero, and that
                # state has to be readable rather than a crash — `Ledger.over` has the
                # argument.
                "over": ledger.over(key, line.sku),
                "copies": list(row.copies),
                "pulled": _pulled_positions(inventory, row.copies),
                # D113. `recorded` is the whole count and these two are how it was reached:
                # `by_hand` copies closed with nothing in the store behind them, `reason`
                # why that was honest. A screen drawing `recorded` alone cannot tell a
                # pulled line from a hand-filled one, and the difference is the audit.
                "by_hand": int(row.by_hand),
                "reason": row.reason,
                # The operator's claim about what this line IS, or None. Never the feed's —
                # that rides on the line itself, and `_engine_order` prefers it.
                "declared_kind": row.kind,
                "at": row.at,
            }
        )
    return rows


def _order_row(
    ledger: order_store.Ledger,
    record: order_store.OrderRecord,
    is_open: bool,
    inventory: master.Inventory,
) -> dict:
    """One order as the feed said it, with our own progress beside it.

    `open` IS THE LEDGER'S ANSWER AND NEVER THE FEED'S `status` STRING. The status is stored
    verbatim and unvalidated on purpose (`store/orders.py` argues why a closed vocabulary
    there would refuse a marketplace that learned a new word), so nothing may branch on it.
    Whether an order still owes copies is a question this store owns, and
    `Ledger.unfulfilled` computes it from its own two maps.
    """
    progress = _order_progress(ledger, record, inventory)
    return {
        "key": record.key,
        "source": record.source,
        "number": record.number,
        "placed_at": record.placed_at,
        "status": record.status,
        "first_seen": record.first_seen or None,
        "changed_at": record.changed_at,
        "wanted": record.wanted,
        "recorded": sum(row["recorded"] for row in progress),
        "open": bool(is_open),
        "lines": [asdict(line) for line in record.lines],
        "progress": progress,
    }


def _pick_row(
    inventory: master.Inventory, places: _Places, held: Dict[str, dict], pick
) -> dict:
    """One physical copy the resolver offered, as it stands RIGHT NOW.

    NOT A DURABLE ADDRESS (D36). `box` and `index` are true of the snapshot this was computed
    from and of no other, and `place` is composed by `_Places.of` — the one renderer — rather
    than assembled here: `pipeline/join.py:Position` is the only label formula in this repo
    and a second one on this screen would be the failure it has already recorded three times.

    `held_by` IS THIS REQUEST'S OWN REVERSE INDEX AND IS NEVER STORED. It says that this
    exact card is already recorded against a line, so the screen can draw it as spoken for
    rather than offering it twice. Keyed by `capture_id`, which is the one identity a
    renumber cannot move.
    """
    card = inventory.cards.get(master.position_key(pick.box, pick.index))
    return {
        "box": pick.box,
        "index": pick.index,
        "capture_id": pick.capture_id,
        "source": pick.source,
        "run": pick.run,
        "card_name": card.name if card is not None else None,
        "card_number": card.number if card is not None else None,
        "condition": card.condition if card is not None else None,
        "state": card.state if card is not None else None,
        "held_by": held.get(str(pick.capture_id)) if pick.capture_id else None,
        "place": places.of(pick.box, pick.index),
    }


def _line_answer(
    inventory: master.Inventory,
    places: _Places,
    held: Dict[str, dict],
    record: order_store.OrderRecord,
    line,
) -> dict:
    """One resolved line: the reason, the breakdown behind it, and the copies it found.

    `order_key` travels beside `order` because the resolver keys on the NUMBER alone and this
    store keys on `source:number` — a number is unique to a marketplace and not across two,
    so a screen that wanted to act on this line would have nothing to name it by.
    """
    ordered = record.line_for(line.sku)
    return {
        "order": line.order,
        "order_key": record.key,
        "sku": line.sku,
        "reason": line.reason,
        # `wanted` IS THE ORDER'S QUANTITY AND `owed` IS THE LEDGER'S. The resolver was asked
        # for `owed` (see `_engine_order`), so its own `wanted` is that figure; the buyer's
        # number comes off the record so the screen can draw "2 of 3" as recorded of wanted.
        "wanted": int(ordered.quantity) if ordered is not None else line.wanted,
        "owed": line.wanted,
        "fulfilled": line.fulfilled,
        "outstanding": line.outstanding,
        "on_hand": line.on_hand,
        "sold": line.sold,
        "retired": line.retired,
        "pooled": line.pooled,
        "line": asdict(line.line),
        "picks": [_pick_row(inventory, places, held, pick) for pick in line.picks],
    }


def do_orders() -> dict:
    """`GET /orders` — every order, and where the copies for the open ones are.

    ONE SNAPSHOT, NO LOCK. This route writes nothing, so `Store().read()` answers a snapshot
    outright — the same call and the same reason as `do_review_catalog`. One snapshot rather
    than two is what keeps the order list and the resolution from disagreeing: read twice and
    a sale landing between them would show a card both on hand and gone.

    THE OPEN ORDERS ARE RESOLVED IN ONE CALL AND THERE IS DELIBERATELY NO `resolve_one`.
    `pipeline/orders.py` refuses to offer one, and its header says why: a per-order resolver
    cannot see what another order has already been promised, so it hands two buyers the same
    physical card and reports success twice. The picker walks to box 3 card 3 twice and the
    second envelope goes out short.

    NO `paperwork=` IS PASSED, AND THE COST IS NAMED RATHER THAN HIDDEN. The run-side backup
    would come from `cli/resolve.py:paperwork_for`, which takes ONE run, reads its
    `pricing.json` and its manifest, and calls `realign` — and `realign` HASHES EVERY
    PHOTOGRAPH OFF DISK and raises `runs.RunError` on an ambiguous digest. One bad run would
    take down the whole screen render, and `cli/runs.py` has no list function to walk the
    others with. So this is a pure card-first resolution: the picks are the copies whose own
    records carry the SKU, `source` is always `card`, and `sku_unknown` — the reason that
    fires only when a run's paperwork names a SKU no card wears — is UNREACHABLE HERE and
    draws a zero in `counts`. That zero is a limit of this route, not a fact about the store.

    THE ORDER LIST AND THE RESOLUTION AGREE ABOUT SEQUENCE, deliberately. Both are sorted the
    way `Ledger.unfulfilled` and `pipeline/orders.py:order_sequence` sort — oldest
    `placed_at` first, then the key, with a missing stamp LAST rather than first — so a
    screen listing what is outstanding and a resolver deciding who gets the last copy cannot
    disagree about which order comes first.
    """
    snapshot = Store().read()
    ledger = snapshot.ledger

    sequence = sorted(
        ledger.orders.values(),
        key=lambda record: (record.placed_at is None, record.placed_at or "", record.key),
    )
    open_keys = {record.key for record in ledger.unfulfilled()}
    open_records = [record for record in sequence if record.key in open_keys]

    asked = [_engine_order(record, ledger) for record in open_records]
    # KEYED BY OBJECT IDENTITY rather than by order number, because `order_sequence` sorts
    # the very objects it was handed and hands them back — so identity survives the pass,
    # while a number does not identify a record: two marketplaces may spell one number, and
    # `source:number` is the key for exactly that reason.
    behind = {id(order): record for order, record in zip(asked, open_records)}
    resolution = order_engine.resolve_all(snapshot.inventory, asked)

    # ONE `_Places` FOR THE WHOLE RESPONSE. It walks the entire store per instantiation, and
    # its own docstring measures what a per-card one costs; the instance never outlives this
    # request, so it cannot serve a stale denominator to the next one.
    places = _Places(snapshot.inventory)

    # The reverse index behind `held_by`, built in this request and NEVER stored. A stored
    # position-keyed index is the fourth thing no renumber path remaps — `pipeline/orders.py`
    # names the three that already exist — which is why this is keyed by `capture_id`.
    held: Dict[str, dict] = {}
    for key, rows in ledger.fulfilment.items():
        holder = ledger.orders.get(key)
        for sku, row in rows.items():
            for copy in row.copies:
                held[str(copy)] = {
                    "order": holder.number if holder is not None else key,
                    "sku": sku,
                }

    answered = []
    for answer in resolution.orders:
        record = behind[id(answer.order)]
        answered.append(
            {
                "key": record.key,
                "number": record.number,
                "complete": answer.complete,
                "outstanding": answer.outstanding,
                "lines": [
                    _line_answer(snapshot.inventory, places, held, record, line)
                    for line in answer.lines
                ],
            }
        )

    return {
        "summary": ledger.summary,
        "orders": [
            _order_row(ledger, record, record.key in open_keys, snapshot.inventory)
            for record in sequence
        ],
        "resolution": {
            # EVERY REASON, INCLUDING THE ZEROS — `Resolution.counts` returns all six and
            # nothing here filters them. Reporting only the reasons that fired would make
            # "nothing was short" and "nothing was checked" the same output.
            "counts": resolution.counts(),
            "orders": answered,
        },
    }


def _ingest_line(order_at: int, line_at: int, raw) -> order_store.OrderLine:
    """One line of a pasted order. `_reject_unknown` FIRST, before a value is read."""
    where = f"line {line_at} of order {order_at}"
    if not isinstance(raw, dict):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "line_invalid",
            f"{where.capitalize()} is not an object. A line is "
            f"{{\"sku\": …, \"quantity\": …}} plus whatever else the feed said.",
        )
    _reject_unknown(raw, ORDER_INGEST_LINE_FIELDS)

    # A SKU ARRIVES AS EITHER A STRING OR AN INT and both are the same identifier — a CSV
    # cell versus a JSON number. `"9191486" == 9191486` is False in Python, and an
    # uncoerced SKU makes every line unresolvable while raising nothing and logging
    # nothing, which is the silent total failure `pipeline/orders.py` opens by naming.
    sku = raw.get("sku")
    if isinstance(sku, bool) or not isinstance(sku, (str, int)):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "line_invalid",
            f"{where.capitalize()} carries {sku!r} as its sku; send the TCGplayer Id as a "
            f"string or a number.",
        )
    sku = str(sku).strip()
    if not sku:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "line_invalid",
            f"{where.capitalize()} carries a blank sku, so there is no way to find the card "
            f"it wants. Nothing was written.",
        )

    quantity = raw.get("quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "line_invalid",
            f"{where.capitalize()} wants {quantity!r} copies; send a whole number of at "
            f"least 1. A float refuses rather than being rounded — half a card is a paste "
            f"that went wrong upstream.",
        )

    # VALIDATED HERE EVEN THOUGH `store/orders.py` LEAVES IT UNVALIDATED ON PURPOSE. That
    # module is a document and a closed vocabulary in it would refuse a feed that learned a
    # new product category. This is the door, and a kind outside `LINE_KINDS` stored through
    # it raises `UnknownLineKind` at resolve time — which makes the WHOLE order screen
    # unreadable for one bad paste, with nothing on it saying which paste.
    kind = raw.get("kind")
    if kind is not None and (
        not isinstance(kind, str) or kind not in order_engine.LINE_KINDS
    ):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "line_kind_invalid",
            f"{where.capitalize()} declares kind {kind!r}. The kinds this repo resolves are "
            f"{', '.join(order_engine.LINE_KINDS)}, and a line may omit it — omitted means "
            f"the feed said nothing, which resolves as "
            f"{order_engine.LINE_KIND_SINGLE}. Nothing was written.",
        )

    said = f"{where.capitalize()} carries a value this route cannot store verbatim."
    return order_store.OrderLine(
        sku=sku,
        quantity=quantity,
        name=_order_optional_text(raw, "name", "line_invalid", said),
        number=_order_optional_text(raw, "number", "line_invalid", said),
        printing=_order_optional_text(raw, "printing", "line_invalid", said),
        condition=_order_optional_text(raw, "condition", "line_invalid", said),
        rarity=_order_optional_text(raw, "rarity", "line_invalid", said),
        unit_price=_order_optional_text(raw, "unit_price", "line_invalid", said),
        kind=kind,
    )


def _ingest_record(order_at: int, raw) -> order_store.OrderRecord:
    """One pasted order. `_reject_unknown` FIRST — that call is the PII backstop."""
    if not isinstance(raw, dict):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "order_invalid",
            f"Order {order_at} is not an object. Send "
            f"{{\"source\": …, \"number\": …, \"lines\": [...]}}.",
        )
    _reject_unknown(raw, ORDER_INGEST_ORDER_FIELDS)

    source = _order_text(
        raw,
        "source",
        "source_required",
        f"Order {order_at} names no `source` — the marketplace it came from, e.g. "
        f"TCGplayer. It is half of the key this order is stored under.",
    )
    number = _order_text(
        raw,
        "number",
        "number_required",
        f"Order {order_at} names no `number` — the order's own identifier at that "
        f"marketplace. It is the other half of the key.",
    )
    said = f"Order {order_at} carries a value this route cannot store verbatim."
    placed_at = _order_optional_text(raw, "placed_at", "order_invalid", said)
    status = _order_optional_text(raw, "status", "order_invalid", said)

    lines = raw.get("lines")
    if not isinstance(lines, list) or not lines:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "lines_required",
            f"Order {order_at} carries no `lines`. An order with nothing on it is a "
            f"purchase nobody can pick, and it is refused rather than stored empty.",
        )

    # THE KEY IS COMPOSED BEFORE ANYTHING IS WRITTEN so a bad one refuses by name rather
    # than as a 500 out of `Ledger.ingest`. The only real cause is a colon in the SOURCE —
    # a colon in the NUMBER is legal and must keep working, because the key splits on the
    # FIRST one.
    try:
        order_store.order_key(source, number)
    except order_store.BadOrderKey as exc:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST, "order_key_invalid", str(exc)
        ) from None

    return order_store.OrderRecord(
        source=source,
        number=number,
        placed_at=placed_at,
        status=status,
        lines=[_ingest_line(order_at, at, line) for at, line in enumerate(lines, start=1)],
    )


def do_order_ingest(payload: dict) -> dict:
    """`POST /orders/ingest` — take the feed's word for what was bought. D63's one map.

    IT TOUCHES ONE MAP AND THAT IS TRUE BY CONSTRUCTION. `Ledger.ingest` writes
    `ledger.orders` and can write nothing else, because `store/orders.py` holds no
    `Inventory`: no card state moves, no listing count moves, not one byte of
    `inventory.json` is rewritten with different content. Nothing is logged to
    `history.jsonl` either, and no state here is a member of `master.STATES` — an order is a
    fact about a marketplace, not a transition of a card.

    A SECOND IDENTICAL PASTE IS A NO-OP DOWN TO THE BYTE. `ingest` compares the feed-owned
    content, carries `first_seen` across, and stamps `changed_at` only where something
    actually moved — so `orders.json`, `inventory.json` and `history.jsonl` are all
    unchanged and the report says `unchanged`. There is deliberately no `last_synced_at`:
    one would move on every press and make the second press write.

    EVERY LEVEL IS ALLOWLISTED BEFORE IT IS READ. The three tuples are the PII backstop and
    their comment has the argument: an unprojected paste carrying `buyer` or
    `shippingAddress` refuses BY NAME rather than being stored with those fields silently
    trimmed.
    """
    _reject_unknown(payload, ORDER_INGEST_FIELDS)
    raw = payload.get("orders")
    if not isinstance(raw, list) or not raw:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "orders_required",
            "Send `orders` — a non-empty list of orders as the feed reported them. An empty "
            "paste is refused rather than reported as a sync that learned nothing, because "
            "those two are different answers to 'did that work'.",
        )
    if len(raw) > ORDER_INGEST_LIMIT:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "too_many_orders",
            f"{len(raw)} orders in one paste, and this route takes at most "
            f"{ORDER_INGEST_LIMIT}. That ceiling is a guard against pasting a whole "
            f"exported history, which would hold the store lock for the length of it. "
            f"Paste what is open.",
        )

    records = [_ingest_record(at, entry) for at, entry in enumerate(raw, start=1)]

    with Store().write() as snapshot:
        try:
            report = snapshot.ledger.ingest(records)
        except order_store.DuplicateOrderLine as exc:
            # A 409 rather than a 400 on this file's standing rule: the request was
            # well-formed and lost to something the STORE knows — fulfilment is keyed by
            # SKU, so two lines sharing one would make "how many have we pulled" a question
            # with two answers. Its own message says that, so it is answered with its text.
            raise BadRequest(HTTPStatus.CONFLICT, "duplicate_line", str(exc)) from None

    return {
        "added": report.added,
        "changed": report.changed,
        "unchanged": report.unchanged,
        "total": report.total,
        "wrote_nothing": report.wrote_nothing,
        "summary": report.summary,
        "keys": [record.key for record in records],
    }


def _known_orders(ledger: order_store.Ledger) -> Dict[str, str]:
    """`{number: status}` for every TCGplayer order the ledger holds — the fetch's delta (D91).

    The number is folded to compare, the way `order_key` folds it; the status is the feed's own
    word and is NOT folded, because a fold is the first step toward the vocabulary the
    transport refuses to hold. An order the ledger has at this exact status has already been
    detailed once and need not be again; one whose status moved is detailed afresh, which is
    how a shipped order's new word reaches the ledger without a full re-fetch.
    """
    known: Dict[str, str] = {}
    for record in ledger.orders.values():
        if str(record.source).strip().casefold() != ORDER_FETCH_SOURCE.casefold():
            continue
        known[str(record.number).strip().casefold()] = str(record.status or "").strip()
    return known


def do_order_fetch(payload: dict) -> dict:
    """`POST /orders/fetch` — ask TCGplayer for this account's own orders. FREE. Two bodies.

    IT IS NOT THE MONEY GATE AND CARRIES NO `confirm`. The one route in this server that can
    cause a charge is still `POST /pipeline/identify`, and it is still named for it. This is
    a READ against `order-management-api.tcgplayer.com` with the session cookie already in
    `.env` — the same account session `server/tcg_export.py` uses one host over — and it
    writes nothing: no card state, no listing count, no run directory, not even the ledger.

    TWO PRESSES SINCE D91, BECAUSE ONE PRESS NEVER WORKED HERE. Measured 2026-09-02 on the
    owner's account: `LastThreeMonths` holds 370 orders against a detail cap of 100, and every
    press of the single-body fetch answered `order_too_many` with a remedy — "ask for a
    narrower range" — the range vocabulary cannot express. So the route takes two bodies:

        {"preview": true, "range"?}
            -> {range, total, by_status: [{status, count, known}], writes_nothing: true}
        {"statuses": [...], "skip_known"?, "range"?}
            -> {orders: [...], matched, skipped_known, detailed, remaining}

    The preview walks the search pages — one request per 25 orders, NO detail call — and
    counts the window by the status STRING the wire returned, verbatim; `known` beside each is
    how many of those the ledger already holds at that status. The fetch details only the
    statuses the operator ticked, skips what the ledger holds unchanged when `skip_known` is
    set, details at most the transport's cap, and reports `remaining` for the next press. No
    vocabulary is coded here: the strings on the wire are the strings on the screen, and which
    of them mean "needs picking" is the operator's to say.

    `orders` IS STILL EXACTLY WHAT `POST /orders/ingest` ACCEPTS. The client forwards that
    array and nothing else — `ingestOrders(found.orders)` — so the counts beside it reach no
    allowlist; they are what the paste note says about the press. A wrapper that forwarded the
    whole answer would meet `field_not_settable` by name, which is the right refusal for it.

    THE PROJECTION HAPPENED UPSTREAM AND IS NOT REPEATED HERE. `server/order_transport.py`
    drops `buyerName`, `shippingAddress`, `paymentType` and the transaction breakdown where
    it parses them, by allowlist rather than by denylist, so a field TCGplayer adds later
    does not arrive through this route either. What this function does is rename the four
    surviving fields into this repo's own spelling.

    A REFUSAL IS THE TRANSPORT'S OWN CODE. One `except` at each of the two call sites is the
    whole seam, exactly as `_dispatch` does for `pipeline_routes.PipelineRefusal` — that
    module raises its own exception type because this file imports it and the reverse import
    would be a cycle. Every one of its codes carries a sentence saying what to fix.
    """
    _reject_unknown(payload, ORDER_FETCH_FIELDS)
    asked = payload.get("range")
    if asked is not None and not isinstance(asked, str):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "range_invalid",
            f"range was {asked!r}; send one of "
            f"{', '.join(order_transport.KNOWN_RANGES)} as a string, or omit it for "
            f"{order_transport.DEFAULT_RANGE}.",
        )
    wanted = (asked or "").strip() or order_transport.DEFAULT_RANGE
    preview = _optional_flag(payload, "preview", "preview_invalid")
    skip_known = _optional_flag(payload, "skip_known", "skip_known_invalid")
    statuses = payload.get("statuses")

    if preview:
        if statuses is not None or "skip_known" in payload:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "fields_conflict",
                "preview: true walks the summaries and details nothing; statuses and "
                "skip_known belong to the fetch body. Send one body or the other.",
            )
        known = _known_orders(Store().read().ledger)
        try:
            found = order_transport.summaries(wanted)
        except order_transport.FetchRefusal as exc:
            raise BadRequest(HTTPStatus.BAD_REQUEST, exc.code, exc.message) from None
        by_status: Dict[str, dict] = {}
        for entry in found:
            status = str(entry.get("status") or "").strip()
            row = by_status.setdefault(status, {"status": status, "count": 0, "known": 0})
            row["count"] += 1
            if known.get(str(entry["orderNumber"]).strip().casefold()) == status:
                row["known"] += 1
        # LARGEST FIRST, THEN BY NAME, so the screen's first row is the window's shape and two
        # equal counts do not swap places between presses.
        rows = sorted(by_status.values(), key=lambda row: (-row["count"], row["status"]))
        return {"range": wanted, "total": len(found), "by_status": rows, "writes_nothing": True}

    if (
        not isinstance(statuses, list)
        or not statuses
        or not all(isinstance(status, str) and status.strip() for status in statuses)
    ):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "statuses_required",
            "Send statuses: [...] — the strings the preview answered, ticked — or preview: "
            "true to see them. Since D91 a fetch details only the statuses you asked for: this "
            "account's window alone holds hundreds of orders, and one press taking all of them "
            "is what never worked.",
        )
    if len(statuses) > ORDER_FETCH_STATUS_LIMIT:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "too_many_statuses",
            f"{len(statuses)} statuses in one fetch; the preview answers far fewer than "
            f"{ORDER_FETCH_STATUS_LIMIT}. Send the ones you ticked.",
        )
    known = _known_orders(Store().read().ledger) if skip_known else None
    try:
        result = order_transport.fetch_open_orders(wanted, statuses=statuses, known=known)
    except order_transport.FetchRefusal as exc:
        raise BadRequest(HTTPStatus.BAD_REQUEST, exc.code, exc.message) from None

    return {
        "orders": [
            {
                "source": ORDER_FETCH_SOURCE,
                "number": order["orderNumber"],
                "placed_at": order["orderDate"],
                "status": order["status"],
                "lines": [
                    {
                        "sku": line["skuId"],
                        "quantity": line["quantity"],
                        "name": line["name"],
                        "unit_price": line["unitPrice"],
                    }
                    for line in order["products"]
                ],
            }
            for order in result.orders
        ],
        "matched": result.matched,
        "skipped_known": result.skipped_known,
        "detailed": result.detailed,
        "remaining": result.remaining,
    }


def _pull_target(at: int, raw) -> dict:
    """One position coming out of the box: `{box, index, capture_id}`, all three required.

    THE CAPTURE ID IS REQUIRED IN BOTH DIRECTIONS AND IT IS NOT BOOKKEEPING. Recording, it
    is the aim check — a mid-box delete (D10 ruling 1), a capture undo releasing an index,
    or a re-shoot all change which physical card sits at a slot, so a screen drawn a minute
    ago may be pointing at a different card than the operator is holding. Undoing, it is the
    whole of the lookup: the client does not name the line and cannot, so the server finds it
    by asking the ledger who holds this copy.
    """
    if not isinstance(raw, dict):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "target_invalid",
            f"Target {at} is not an object. Send "
            f"{{\"box\": …, \"index\": …, \"capture_id\": …}}.",
        )
    _reject_unknown(raw, ORDER_PULL_TARGET_FIELDS)
    box = raw.get("box")
    index = raw.get("index")
    if isinstance(box, bool) or not isinstance(box, int) or box < 1:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "target_invalid",
            f"Target {at} names box {box!r}; send a whole number, and boxes start at 1.",
        )
    if isinstance(index, bool) or not isinstance(index, int) or index < 1:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "target_invalid",
            f"Target {at} names index {index!r}; send a whole number. This is the STORED "
            f"index — the `/inventory/<box>/<index>` path and the `<index>.jpg` the "
            f"photograph is named after — never the slot a person counts to (D58).",
        )
    capture_id = raw.get("capture_id")
    if not isinstance(capture_id, str) or not capture_id.strip():
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "target_invalid",
            f"Target {at} carries no `capture_id`. Send the id the row you are looking at "
            f"carries: it is the aim check on the way in and the whole of the lookup on the "
            f"way back, and it is the one identity a renumber cannot move.",
        )
    return {"box": box, "index": index, "capture_id": capture_id.strip()}


def _prepare_targets(
    snapshot,
    places: "_Places",
    parsed: List[dict],
    sku: str,
    undo: bool,
    seen: Set[str],
) -> Tuple[List[dict], List[Tuple[str, BadRequest]]]:
    """Phase one of `POST /orders/pull`: validate every target and compute every PRE-WRITE
    place, writing nothing.

    A SEPARATE FUNCTION FOR A SECOND DOOR THAT NO LONGER EXISTS. It was lifted out of
    `do_order_pull` for D90's `/orders/fill`, which D96 deleted rather than wired up; the
    shape stays because it is the honest one either way. Refusals are COLLECTED rather than
    raised, because the caller — not this function — decides the unit that is refused whole,
    and `seen` is the caller's for the same reason.
    """
    prepared: List[dict] = []
    refused: List[Tuple[str, BadRequest]] = []
    for target in parsed:
        position = master.position_key(target["box"], target["index"])
        try:
            if position in seen:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "duplicate_target",
                    f"{position} is in this pull twice. One physical card is pulled "
                    f"once; a repeated position would record a second sale of it and "
                    f"compute the wrong state to restore.",
                )
            seen.add(position)

            card = snapshot.inventory.cards.get(position)
            if card is None:
                raise BadRequest(
                    HTTPStatus.NOT_FOUND,
                    "card_not_found",
                    f"No card at box {target['box']}, index {target['index']}.",
                )
            if not card.capture_id:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "copy_not_identifiable",
                    f"The card at {position} carries no capture_id, so this pull "
                    f"cannot be made idempotent and is refused rather than counted "
                    f"blind. Every record written by this server has one; this is a "
                    f"record that predates it.",
                )
            if str(card.capture_id) != target["capture_id"]:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "capture_id_mismatch",
                    f"The card at {position} is not the card the screen drew: it "
                    f"carries capture_id {card.capture_id!r} and the request aimed at "
                    f"{target['capture_id']!r}. A mid-box delete, a capture undo "
                    f"releasing an index, or a re-shoot all change a slot's occupant. "
                    f"Re-read the order screen, then aim again.",
                )
            if not undo and str(card.sku or "").strip() != sku:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "sku_mismatch",
                    f"The card at {position} carries SKU "
                    f"{str(card.sku or '') or 'nothing'}, and this pull is for {sku}. "
                    f"A copy fills a line by carrying its SKU; nothing here recategorises "
                    f"a card to make it fit.",
                )
            # COMPUTED BEFORE ANY WRITE — see `do_order_pull`'s docstring, phase one.
            place = places.of(target["box"], target["index"])
        except BadRequest as exc:
            refused.append((position, exc))
            continue
        prepared.append(
            {
                "box": target["box"],
                "index": target["index"],
                "capture_id": str(card.capture_id),
                "place": place,
            }
        )
    return prepared, refused


def _ledger_pull(
    snapshot, key: str, sku: str, copies: List[str], undo: bool
) -> Tuple[str, str, int]:
    """Phase two's ledger half: record or forget, and map the store's refusals to this
    server's codes. Answers `(key, sku, newly)` — for an undo the key and SKU are DISCOVERED
    from whoever holds the copies, because `/orders/pull`'s undo names no line at all, so a
    screen holding a stale order key cannot reverse the wrong one."""
    if undo:
        holders = []
        for copy in copies:
            holder = snapshot.ledger.holder_of(copy)
            if holder is None:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "pull_not_recorded",
                    f"The ledger has no record of the copy {copy!r} being pulled for an "
                    f"order, so this route did not do what is being undone. If it was "
                    f"marked sold on #/inventory, reverse it there.",
                )
            holders.append(holder)
        spanned = sorted(set(holders))
        if len(spanned) > 1:
            named = ", ".join(f"{held_key} SKU {held_sku}" for held_key, held_sku in spanned)
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "pull_spans_lines",
                f"These copies are held by more than one line ({named}). One press "
                f"pulled one line and one press reverses one; send the copies of a "
                f"single line.",
            )
        found_key, found_sku = spanned[0]
        return found_key, found_sku, int(snapshot.ledger.forget_pull(found_key, found_sku, copies))
    try:
        newly = snapshot.ledger.record_pull(key, sku, copies)
    except order_store.UnknownOrder:
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "order_not_ingested",
            f"Order {key} is not in this ledger, so there is nothing to fulfil. "
            f"Paste or fetch it first — inventing it here would put a shipment on "
            f"record for a purchase nobody can produce.",
        ) from None
    except order_store.UnknownOrderLine:
        raise BadRequest(
            HTTPStatus.CONFLICT,
            "sku_not_on_order",
            f"Order {key} has no line for SKU {sku}. The buyer did not order it, "
            f"and fulfilment is keyed by SKU.",
        ) from None
    except order_store.CopyNotIdentifiable as exc:
        raise BadRequest(HTTPStatus.CONFLICT, "copy_not_identifiable", str(exc)) from None
    except order_store.CopyAlreadyPulled as exc:
        raise BadRequest(HTTPStatus.CONFLICT, "copy_already_pulled", str(exc)) from None
    except order_store.OverFulfilled as exc:
        # NOTHING IS CLAMPED. Recording a fourth copy against an order for three is a
        # mistake with nothing to be gained by swallowing it — you cannot ship the fourth.
        raise BadRequest(HTTPStatus.CONFLICT, "over_fulfilled", str(exc)) from None
    return key, sku, int(newly)


def do_order_pull(payload: dict) -> dict:
    """`POST /orders/pull` — record copies against an order line and mark them sold. D63.

    BODY-ADDRESSED, NOT PATH-ADDRESSED, and that is forced rather than chosen. An order key
    is `source:number` and a NUMBER may legally contain a colon — `store/orders.py` splits on
    the FIRST one for exactly that reason — so a key in a path segment would need an escaping
    rule that the one place it is composed does not have.

    THE TWO DIRECTIONS TAKE DIFFERENT TUPLES, `do_review_answer`'s convention exactly. `undo`
    is read FIRST and the narrow tuple is checked against it, so an undo that also names an
    order REFUSES rather than being obeyed with the order silently ignored. The reversal
    names no line at all: the server asks `Ledger.holder_of` which line holds each copy, so a
    screen holding a stale order key cannot reverse the wrong one.

    ONE `Store.write()` FOR THE WHOLE CALL, IN TWO PHASES — D29's rule, and `store/orders.py`
    applies the same one inside `record_pull`.

      PHASE ONE validates every target and writes nothing, and it computes every `place`
      BEFORE ANY WRITE. A sale moves the box's occupancy (D58 — the numbers count the cards,
      not the slots), so a receipt composed afterwards would name where the operator is about
      to be rather than where they just were. A per-position refusal is collected rather than
      raised, and the whole set is answered as one `pull_entry_refused` — `group_entry_refused`'s
      shape — because a pull half-refused is an operator holding cards with no record of
      which ones went.

      `duplicate_target` IS REQUIRED HERE AND IS NOT TIDINESS. `_sell` reads `history.jsonl`
      FROM DISK to learn what an undo would restore, and it cannot see an event this session
      has queued — so the same position sent twice would compute `previous` from pre-session
      history both times and the second sale's `restores_to` would name the state the card
      held before the first one.

      PHASE TWO WRITES THE LEDGER FIRST, then sells. The ledger is the one call that can
      refuse on a fact neither the client nor phase one holds — the line's quantity against
      what is already recorded — and `Store.write()` commits only on a clean exit, so a raise
      anywhere discards every earlier state change and every history line queued behind it.
      Correctness therefore does not depend on the order; the reading order matches the
      refusal order.
    """
    # Read before `_reject_unknown`, because which fields are settable depends on which
    # direction this is. A stringified flag refuses rather than being coerced.
    undo = _optional_flag(payload, "undo", "undo_invalid")
    _reject_unknown(payload, ORDER_PULL_UNDO_FIELDS if undo else ORDER_PULL_FIELDS)

    raw = payload.get("targets")
    if not isinstance(raw, list) or not raw:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "targets_required",
            "Send `targets` — the positions coming out of the box, each as "
            "{box, index, capture_id}. A pull of nothing is refused rather than recorded "
            "as a pull of nothing.",
        )
    if len(raw) > ORDER_PULL_TARGET_LIMIT:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "too_many_targets",
            f"{len(raw)} positions in one press, and this route takes at most "
            f"{ORDER_PULL_TARGET_LIMIT}. One press is one armful of cards; a longer list is "
            f"a script that meant to send the whole box.",
        )
    parsed = [_pull_target(at, entry) for at, entry in enumerate(raw, start=1)]

    key = ""
    sku = ""
    if not undo:
        source = _order_text(
            payload,
            "source",
            "source_required",
            "Send `source` — the marketplace this order came from. It is half of the key "
            "the pull is recorded under.",
        )
        number = _order_text(
            payload,
            "number",
            "number_required",
            "Send `number` — the order's own identifier at that marketplace.",
        )
        sku = _order_text(
            payload,
            "sku",
            "sku_required",
            "Send `sku` — the TCGplayer Id of the line these copies fill. Fulfilment is "
            "keyed by SKU because that is the only line identity stable across two ingests.",
        )
        try:
            key = order_store.order_key(source, number)
        except order_store.BadOrderKey as exc:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST, "order_key_invalid", str(exc)
            ) from None

    with Store().write() as snapshot:
        places = _Places(snapshot.inventory)

        # ---------------------------------------------------------------- phase one
        prepared, refused = _prepare_targets(snapshot, places, parsed, sku, undo, set())
        if refused:
            named = "; ".join(f"{position}: {exc.code} — {exc}" for position, exc in refused)
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "pull_entry_refused",
                f"{len(refused)} of {len(parsed)} positions refused, so the whole pull is "
                f"refused and nothing was written — neither the ledger nor one card's "
                f"state. Re-read the order screen and aim again. {named}",
            )

        copies = [entry["capture_id"] for entry in prepared]

        # ---------------------------------------------------------------- phase two
        key, sku, newly = _ledger_pull(snapshot, key, sku, copies, undo)

        # `_sell`'s five refusals reach the dispatcher unchanged and unsoftened. A raise
        # here discards the ledger write above with everything else — `Store.write()`
        # commits only on a clean exit.
        sales = [
            _sell(snapshot, entry["box"], entry["index"], undo) for entry in prepared
        ]

        body = {
            "undone": bool(undo),
            "order_key": key,
            "sku": sku,
            "newly": int(newly),
            "recorded": snapshot.ledger.fulfilled(key, sku),
            "outstanding": snapshot.ledger.outstanding(key, sku),
            # The PRE-WRITE places, one per target in request order — where the operator
            # just was, not where the box has closed up to.
            "places": [entry["place"] for entry in prepared],
            "sales": sales,
        }

    return body


def _fill_line_key(payload: dict) -> Tuple[str, str]:
    """`(order key, sku)` off a body, or the refusal naming which part was missing.

    Shared by the fill and the kind declaration: both address one LINE, and both address it
    the same way `POST /orders/pull` does — in the body rather than the path, because an
    order key is `source:number` and a number may legally contain a colon.
    """
    source = _order_text(
        payload,
        "source",
        "source_required",
        "Send `source` — the marketplace this order came from. It is half of the key "
        "the line is recorded under.",
    )
    number = _order_text(
        payload,
        "number",
        "number_required",
        "Send `number` — the order's own identifier at that marketplace.",
    )
    sku = _order_text(
        payload,
        "sku",
        "sku_required",
        "Send `sku` — the TCGplayer Id of the line. Fulfilment is keyed by SKU because "
        "that is the only line identity stable across two ingests.",
    )
    try:
        return order_store.order_key(source, number), sku
    except order_store.BadOrderKey as exc:
        raise BadRequest(HTTPStatus.BAD_REQUEST, "order_key_invalid", str(exc)) from None


def _fill_count(payload: dict) -> int:
    """A positive whole number of copies, bounded. Never `int()` over whatever arrived."""
    raw = payload.get("count")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "count_invalid",
            "Send `count` — how many copies of this line are being closed by hand, as a "
            "whole number. A string or a float is a caller sending a shape this route has "
            "never seen, and it refuses rather than rounding one.",
        )
    if raw < 1:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "count_invalid",
            f"`count` is {raw}. A fill of nothing is refused rather than recorded as a "
            f"fill of nothing; to reverse one, send `undo`.",
        )
    if raw > ORDER_FILL_LIMIT:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "count_too_large",
            f"{raw} copies in one press, and this route takes at most "
            f"{ORDER_FILL_LIMIT}. A hand-fill carries no capture id, so nothing below this "
            f"can tell a fat-fingered paste from a real armful.",
        )
    return int(raw)


def do_order_fill(payload: dict) -> dict:
    """`POST /orders/fill` — close copies of a line with no card behind them. D113.

    THE WRITE `POST /orders/pull` CANNOT MAKE. That route records `capture_id`s and sells the
    cards they name; this one records a COUNT and sells nothing, because there is nothing in
    the store to sell. A sealed Holiday Calendar has no card record and never will; neither
    has a single that shipped from a pile this rig never photographed. Three real orders on
    the owner's store were permanently open for exactly this and no screen could move them.

    IT TOUCHES NO CARD, AND THAT IS THE WHOLE SAFETY ARGUMENT. `do_order_pull` runs two
    phases because it moves card state and a half-refused pull leaves the operator holding
    cards with no record of which went. This route has no card to move, so it is one ledger
    call inside one `Store.write()` — and it CANNOT reach a card, in `store/orders.py`'s own
    idiom: `Ledger` holds no `Inventory` and imports nothing that does, so the capability is
    absent rather than guarded.

    THE REASON IS REQUIRED AND CLOSED. A hand-fill is the one write here with nothing to
    check it against — no capture id to collide, no photograph, no slot — so the reason is
    the entire audit trail. `FILL_REASONS` is validated HERE and not in `store/orders.py`,
    which is `OrderLine.kind`'s rule exactly: that module is a document, and a closed
    vocabulary in it refuses a store that learned a new word.

    `undo` REVERSES BY COUNT AND CANNOT REACH A PULL. `Ledger.forget_fill` only ever
    decrements `by_hand`, so a line carrying two pulled copies and one hand-filled one
    reverses to two pulled copies. Reversing a pull is `POST /orders/pull {undo: true}`,
    which needs the capture ids this route never had.
    """
    undo = _optional_flag(payload, "undo", "undo_invalid")
    _reject_unknown(payload, ORDER_FILL_UNDO_FIELDS if undo else ORDER_FILL_FIELDS)

    key, sku = _fill_line_key(payload)
    count = _fill_count(payload)

    reason = ""
    if not undo:
        reason = _order_text(
            payload,
            "reason",
            "reason_required",
            "Send `reason` — why this line closes with no card behind it. It is the only "
            "record of that, so it is required rather than defaulted.",
        )
        if reason not in order_store.FILL_REASONS:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "fill_reason_invalid",
                f"{reason!r} is not a reason this store records. The reasons are "
                f"{', '.join(order_store.FILL_REASONS)} — {order_store.FILL_SEALED} for a "
                f"line that is not a single and was picked by hand, "
                f"{order_store.FILL_OFF_SYSTEM} for a single this store never "
                f"photographed, {order_store.FILL_SOLD_SEPARATELY} for a copy that was "
                f"here and left through #/inventory's sale rather than the order pull. A "
                f"refund or a cancellation is none of them and is not closed here: "
                f"`fulfilled` counts copies that went. Stand it down instead.",
            )

    with Store().write() as snapshot:
        if undo:
            moved = snapshot.ledger.forget_fill(key, sku, count)
        else:
            try:
                moved = snapshot.ledger.record_fill(key, sku, count, reason)
            except order_store.UnknownOrder:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "order_not_ingested",
                    f"Order {key} is not in this ledger, so there is nothing to fill. "
                    f"Paste or fetch it first — inventing it here would put a shipment on "
                    f"record for a purchase nobody can produce.",
                ) from None
            except order_store.UnknownOrderLine:
                raise BadRequest(
                    HTTPStatus.CONFLICT,
                    "sku_not_on_order",
                    f"Order {key} has no line for SKU {sku}. The buyer did not order it, "
                    f"and fulfilment is keyed by SKU.",
                ) from None
            except order_store.OverFulfilled as exc:
                raise BadRequest(
                    HTTPStatus.CONFLICT, "over_fulfilled", str(exc)
                ) from None

        return {
            "undone": bool(undo),
            "order_key": key,
            "sku": sku,
            "moved": int(moved),
            "recorded": snapshot.ledger.fulfilled(key, sku),
            "by_hand": int(snapshot.ledger.recorded(key, sku).by_hand),
            "outstanding": snapshot.ledger.outstanding(key, sku),
            "reason": snapshot.ledger.recorded(key, sku).reason,
        }


def do_order_close(payload: dict) -> dict:
    """`POST /orders/close` — stand whole orders down, or reopen them. D113.

    THE THIRD WAY A LINE STOPS OWING, AND IT COUNTS NOTHING. `POST /orders/pull` records
    copies and sells the cards; `POST /orders/fill` records a count for copies that went
    without a card record; this records NEITHER and says only that this store is no longer
    accounting for the order. Measured 2026-09-06 on the owner's store: 69 of 83 open orders
    were ones TCGplayer had already shipped, and the ledger had no way to say so.

    WHY NOT A FILL, WHICH IS THE TEMPTING ONE-MECHANISM ANSWER. Many of those 69 shipped
    using copies STILL sitting in the boxes as `identified` — this store never marked them
    sold because the sale did not go through it. A fill would add to `fulfilled`, so the
    count would read right while the card stayed on the shelf, live, and got offered to the
    next buyer. The stand-down leaves both facts true and unmerged: the order is not ours,
    the card is still here, and reconciling the second one is `#/inventory`'s job.

    AND WHY THIS IS NOT DONE AT INGEST, WHICH IS WHAT WAS ASKED FOR. `store/orders.py`'s two
    maps exist so `ingest` cannot write fulfilment at all, and `_order_row` states that
    `open` is the ledger's answer and never the feed's `status` string. The status is
    unvalidated and open-ended — the vocabulary was never published, and "everything that is
    not Ready to Ship" would swallow a `Cancelled` the day that word appears and record it
    as handled. So the status PROPOSES the set on the screen and the operator presses, which
    is `make merge`'s bargain exactly: automate the lookup, never the decision.

    ONE `Store.write()` FOR THE WHOLE PRESS, and every order is validated before any is
    written — `do_order_pull`'s phase rule. A backlog press that stood 40 orders down and
    then refused would leave the operator unable to tell which 40.
    """
    undo = _optional_flag(payload, "undo", "undo_invalid")

    # WHICH SCOPE, DECIDED BEFORE ANYTHING IS VALIDATED. Both fields present is a client that
    # has not decided, and picking one would stand lines down that nobody answered for.
    by_line = "lines" in payload
    if by_line and "orders" in payload:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "close_scope_ambiguous",
            "Send `orders` OR `lines`, never both. `orders` stands every line of an order "
            "down; `lines` stands exactly the lines it names down and leaves their siblings "
            "alone. A body carrying both has not decided which, and obeying one of them "
            "silently is how a refunded line takes the rest of the order with it.",
        )
    if by_line:
        _reject_unknown(
            payload, ORDER_CLOSE_LINE_UNDO_FIELDS if undo else ORDER_CLOSE_LINE_FIELDS
        )
    else:
        _reject_unknown(payload, ORDER_CLOSE_UNDO_FIELDS if undo else ORDER_CLOSE_FIELDS)

    raw = payload.get("lines" if by_line else "orders")
    if not isinstance(raw, list) or not raw:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "lines_required" if by_line else "orders_required",
            (
                "Send `lines` — the lines to stand down, each as {source, number, sku}. "
                if by_line
                else "Send `orders` — the orders to stand down, each as {source, number}. "
            )
            + "A close of nothing is refused rather than recorded as a close of nothing.",
        )
    if len(raw) > ORDER_CLOSE_LIMIT:
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "too_many_orders",
            f"{len(raw)} orders in one press, and this route takes at most "
            f"{ORDER_CLOSE_LIMIT}.",
        )

    reason = ""
    if not undo:
        reason = _order_text(
            payload,
            "reason",
            "reason_required",
            "Send `reason` — why these orders need nothing further. Nothing is counted "
            "here, so the reason is the only record of what happened.",
        )
        if reason not in order_store.CLOSE_REASONS:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "close_reason_invalid",
                f"{reason!r} is not a reason this store records. The reasons are "
                f"{', '.join(order_store.CLOSE_REASONS)} — "
                f"{order_store.CLOSE_SHIPPED_ELSEWHERE} for an order that went out without "
                f"this store tracking the copies, {order_store.CLOSE_NOT_SHIPPING} for one "
                f"that will never go. Neither claims a copy left.",
            )

    # `(order key, sku or None)`. `None` means every line of that order — the two scopes meet
    # here and the loop below is the same either way.
    aimed: List[Tuple[str, Optional[str]]] = []
    what = "Line" if by_line else "Order"
    for at, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            raise BadRequest(
                HTTPStatus.BAD_REQUEST,
                "line_invalid" if by_line else "order_invalid",
                f"{what} {at} of {len(raw)} is not an object. Nothing was written.",
            )
        _reject_unknown(entry, ("source", "number", "sku") if by_line else ("source", "number"))
        source = _order_text(
            entry, "source", "source_required",
            f"{what} {at} of {len(raw)} carries no `source`.",
        )
        number = _order_text(
            entry, "number", "number_required",
            f"{what} {at} of {len(raw)} carries no `number`.",
        )
        sku = (
            _order_text(
                entry, "sku", "sku_required",
                f"{what} {at} of {len(raw)} carries no `sku`. Fulfilment is keyed by SKU "
                f"because that is the only line identity stable across two ingests.",
            )
            if by_line
            else None
        )
        try:
            aimed.append((order_store.order_key(source, number), sku))
        except order_store.BadOrderKey as exc:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST, "order_key_invalid", str(exc)
            ) from None

    with Store().write() as snapshot:
        ledger = snapshot.ledger

        # VALIDATE EVERY ORDER BEFORE WRITING ONE. `Store.write()` commits only on a clean
        # exit, so a raise below would discard the lot — but the operator would be told
        # nothing about WHICH order was wrong, and a 69-order backlog press is exactly where
        # that matters.
        missing = [key for key, _ in aimed if ledger.orders.get(key) is None]
        if missing:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "order_not_ingested",
                f"{len(missing)} of {len(aimed)} are not in this ledger, so the whole press "
                f"is refused and nothing was written: {', '.join(missing[:10])}"
                + (" …" if len(missing) > 10 else ""),
            )
        # A SKU THE BUYER DID NOT ORDER IS REFUSED BEFORE ANY LINE MOVES, not skipped: a
        # stand-down aimed at a line that is not there means the screen and the store disagree,
        # and standing the others down would leave the operator believing all of them went.
        astray = [
            f"{key} SKU {sku}"
            for key, sku in aimed
            if sku is not None and ledger.orders[key].line_for(sku) is None
        ]
        if astray:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "sku_not_on_order",
                f"{len(astray)} of {len(aimed)} name a SKU that order does not carry, so the "
                f"whole press is refused and nothing was written: {', '.join(astray[:10])}"
                + (" …" if len(astray) > 10 else ""),
            )

        moved = 0
        lines = 0
        for key, sku in aimed:
            record = ledger.orders.get(key)
            # `None` is every line of the order; a SKU is exactly that one. The two scopes are
            # one loop, which is why they are one route.
            wanted = record.lines if sku is None else [record.line_for(sku)]
            touched = False
            for line in wanted:
                if undo:
                    changed = ledger.reopen_line(key, line.sku)
                else:
                    changed = ledger.close_line(key, line.sku, reason)
                if changed:
                    lines += 1
                    touched = True
            if touched:
                moved += 1

        return {
            "undone": bool(undo),
            "scope": "lines" if by_line else "orders",
            "orders": len(aimed),
            "moved": int(moved),
            "lines": int(lines),
            "reason": reason or None,
            # What the press was FOR, recomputed after it: how many orders still owe.
            "still_open": len(ledger.unfulfilled()),
        }


def do_order_line_kind(payload: dict) -> dict:
    """`POST /orders/line-kind` — record what the operator says a line IS. D113.

    SEPARATE FROM THE FILL ON PURPOSE, AND THE SHIPPING LANE IS WHY. A sealed product needs
    classifying BEFORE it goes out — that is what routes it to the parcel lane instead of an
    envelope it does not fit — and it is filled only once it has. One route doing both would
    make the routing answer unavailable until the moment it stopped mattering.

    IT WRITES INTO THE FULFILMENT MAP AND NOT ONTO THE ORDER RECORD, which is
    `store/orders.py`'s header argument in a second currency. `ingest` replaces an order
    record wholesale on any content change, so a kind written onto the feed's copy survives
    exactly until the marketplace moves the status string — at which point a sealed product
    silently becomes a single again and starts sending the picker into the boxes after a
    playmat.

    THE VOCABULARY IS VALIDATED HERE. `pipeline/orders.py:OrderLine.__post_init__` raises
    `UnknownLineKind` for anything outside `LINE_KINDS`, and that raise happens at RESOLVE
    time — which would take the whole order screen down for one bad write, with nothing on
    it saying which. `null` withdraws the claim and is how a mis-tick is undone.
    """
    _reject_unknown(payload, ORDER_LINE_KIND_FIELDS)
    key, sku = _fill_line_key(payload)

    raw = payload.get("kind")
    if raw is not None and (
        not isinstance(raw, str) or raw not in order_engine.LINE_KINDS
    ):
        raise BadRequest(
            HTTPStatus.BAD_REQUEST,
            "line_kind_invalid",
            f"Kind {raw!r} is not one this repo resolves. The kinds are "
            f"{', '.join(order_engine.LINE_KINDS)}, and `null` withdraws the claim so the "
            f"feed's own word (or its silence) stands again. Nothing was written.",
        )

    with Store().write() as snapshot:
        try:
            snapshot.ledger.declare_kind(key, sku, raw)
        except order_store.UnknownOrder:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "order_not_ingested",
                f"Order {key} is not in this ledger, so there is no line to classify.",
            ) from None
        except order_store.UnknownOrderLine:
            raise BadRequest(
                HTTPStatus.CONFLICT,
                "sku_not_on_order",
                f"Order {key} has no line for SKU {sku}. The buyer did not order it.",
            ) from None

        return {
            "order_key": key,
            "sku": sku,
            "kind": snapshot.ledger.declared_kind(key, sku),
        }


# ------------------------------------------------------------------------------- handler


class CaptureHandler(BaseHTTPRequestHandler):
    server_version = "pkmnscan-capture/1"
    protocol_version = "HTTP/1.1"

    #: AN IDLE KEEP-ALIVE CONNECTION LETS ITS THREAD GO. Without this the server holds one
    #: thread per open CONNECTION for as long as the peer keeps it, and `BaseHTTPRequestHandler`
    #: defaults `timeout` to None — so a thread parked on `readline` for the next request never
    #: comes back. `ThreadingHTTPServer` bounds neither the count nor the lifetime, and the two
    #: together are unbounded growth rather than a leak: nothing is lost, it is all still
    #: waiting.
    #:
    #: MEASURED ON THIS MACHINE, twice in one working day: 1,178 handler threads alive, every
    #: one of them blocked in `PyEval_AcquireThread` — waiting for the interpreter lock, not for
    #: the store — at 1,318% CPU, with the process holding :8182 and answering nothing. Restarts
    #: cleared it and it came back, because what accumulates is browser tabs and Playwright
    #: contexts across a long session, and every one of them is behaving correctly.
    #:
    #: FIFTEEN SECONDS, AND IT IS NOT A DEADLINE ON A REQUEST. It is the socket's timeout, so it
    #: bounds each read and write and not the handler's own work: a capture waiting out
    #: `files.LOCK_TIMEOUT_SECONDS` (30) behind `./pkmnscan identify` performs no socket
    #: operation while it waits and is never cut off mid-refusal. What it bounds is a thread
    #: parked on `readline` for a request that is not coming, which is every connection a closed
    #: tab leaves behind.
    #:
    #: WHAT IT DOES NOT FIX, said plainly so the next session does not mistake this for a cure:
    #: a burst of genuinely concurrent clients. Measured immediately after this landed — 80
    #: Playwright browsers under `make design-check`, 969 threads inside ten minutes at 338% CPU.
    #: Those connections are ACTIVE, and no idle timeout touches them. Bounding them needs a
    #: worker pool, and a pool over HTTP/1.1 keep-alive has to answer what happens when every
    #: worker is held by an idle connection — this class's own docstring records what happened
    #: the last time connections were refused rather than queued. That is its own task.
    timeout = 15

    #: IS THE REQUEST IN HAND A HEAD? Set by `do_HEAD` for the length of one request and read
    #: by `_send`, which sends every header and withholds the body when it is true.
    #:
    #: A CLASS ATTRIBUTE so `_send` has an answer on every response without `do_HEAD` having
    #: run. A flag that only existed once HEAD had been asked for would make the other four
    #: verbs depend on this one, which is a coupling nothing would notice until an
    #: `AttributeError` reached a 500 on an ordinary GET.
    _head = False

    # -------------------------------------------------------------------- responding

    def _origin(self) -> Optional[str]:
        """The request's `Origin`, folded, or None when it did not send one."""
        raw = self.headers.get("Origin")
        return _normalize_origin(raw) if raw else None

    def _origin_allowed(self) -> bool:
        """May this request WRITE? A request with no `Origin` may.

        THE ABSENT CASE IS ALLOWED ON PURPOSE, and it is the part worth being explicit about
        because it looks like the hole. `Origin` is set by the BROWSER and cannot be forged
        by a page — that is the entire reason the header exists — and browsers send it on
        every POST, PUT and DELETE, cross-origin or not. So an absent `Origin` means the
        request did not come from a page: `curl`, `./pkmnscan`, T7's own socket calls. None
        of those is the threat, because anything that can open a socket from this machine can
        also open `inventory.json` with an editor. What this gate stops is a page the owner
        did not open borrowing his browser to write, and that page cannot omit the header.
        """
        origin = self._origin()
        return origin is None or origin in allowed_origins()

    def _cors_headers(self) -> Tuple[Tuple[str, str], ...]:
        """CORS for THIS request, rather than one constant tuple for every response.

        Two things vary, and both only when the request carries an `Origin` this server does
        not know:

          the ACAO value   an allowed origin is echoed back, because `*` and credentials do
                           not mix and because echoing is what makes the browser's own check
                           agree with this server's. An unknown origin still gets `*`, which
                           keeps `GET /photo` embeddable — see the CORS block above for why
                           reads are deliberately open.
          the method list  an unknown origin is told GET and OPTIONS only, so its preflight
                           for a DELETE fails IN THE BROWSER and the request is never sent.
                           The dispatcher refuses it as well; this is the belt to that
                           braces, and it is the half that produces a legible console error
                           instead of a 403 nobody sees.

        `Vary: Origin` because the answer now depends on a request header, and a cache that
        did not know that could hand one origin's answer to another.
        """
        origin = self._origin()
        known = origin is not None and origin in allowed_origins()
        methods = ALL_METHODS if (origin is None or known) else SAFE_METHODS
        return (
            ("Access-Control-Allow-Origin", origin if known else "*"),
            ("Access-Control-Allow-Methods", ", ".join(methods)),
            ("Access-Control-Allow-Headers", "Content-Type"),
            # WITHOUT THIS THE BOOT HEADER IS INVISIBLE TO THE APP. A cross-origin response
            # exposes only the handful of CORS-safelisted headers to JavaScript; every other
            # one is present on the wire, visible in the network tab, and simply absent from
            # `Response.headers`. The app is served from the dev port and the server answers on
            # its own, so every request it makes is cross-origin — the header would have been
            # there and unreadable, which is the worst way for this to fail: nothing errors and
            # the notice silently never fires.
            ("Access-Control-Expose-Headers", BOOT_HEADER),
            ("Vary", "Origin"),
        )

    def end_headers(self) -> None:
        """`Connection: close` ON EVERY RESPONSE, INCLUDING THE ONES `_send` NEVER SEES.

        THE HANDLER HAS TO SEND THIS OR NOTHING DOES, and `close_connection = True` on the class
        looks like it would work and does not: `BaseHTTPRequestHandler.parse_request` resets it
        from the request's own `Connection` header every time, and CPython flips it back only
        when the HANDLER sends `Connection: close` — `send_header` watches for this keyword by
        name. So `CaptureServer`'s whole premise, one pooled worker per REQUEST rather than per
        connection, rests on this line.

        IT SITS HERE RATHER THAN IN `_send` BECAUSE `_send` IS NOT EVERY RESPONSE, AND THAT WAS
        NOT A HYPOTHETICAL. `_photo`'s 304 branch answers a conditional GET by hand —
        `send_response`, the ETag headers, `end_headers` — and never touches `_send`. From the
        pool landing on 2026-09-04 until this override, the app's most-requested route sent no
        `Connection: close` at all, and `do_photo` sets `Cache-Control: no-cache`, so a 304 is
        the NORMAL answer on any revisit rather than an edge: four concurrent revalidations held
        all four workers until `timeout = 15` reaped them, which is the starvation
        `CaptureServer`'s own comment calls a deadlock.

        Every response path ends in `end_headers` — `_send`, the 304 branch, and
        `BaseHTTPRequestHandler.send_error` — so stating the invariant once, here, is what stops
        the next hand-rolled branch from repeating it silently.
        """
        self.send_header("Connection", "close")
        super().end_headers()

    def _send(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
        extra: Sequence[Tuple[str, str]] = (),
    ) -> None:
        self.send_response(int(status))
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # WHICH PROCESS ANSWERED, ON EVERY RESPONSE — the same `boot_id` `GET /status` reports,
        # here so the app can notice a restart WITHOUT ASKING. `make up` restarts this server on
        # every Python edit (D53), and the alternative was a client that polled `/status` on a
        # timer: it worked, and it made every owner-side screen issue a request nothing had
        # asked for, in every Playwright spec, against whatever real server is listening —
        # which is the hazard `app/tests/inventory.spec.ts` documents in its own comment. A
        # header rides traffic the app already generates, so it costs no request at all.
        #
        # It is also the honest semantics. An idle app learns nothing, and it does not need to:
        # a stale server harms nothing until the next request, and the next request is exactly
        # what carries this.
        self.send_header(BOOT_HEADER, BOOT_ID)
        # `Connection: close` IS NOT SENT HERE. It rides `end_headers`, which every response
        # path reaches and `_send` is only one of — see that override for why.
        for header, value in self._cors_headers():
            self.send_header(header, value)
        for header, value in extra:
            self.send_header(header, value)
        self.end_headers()
        # THE BODY, UNLESS THIS IS A HEAD — and every header above was sent either way, which
        # is the whole of what RFC 9110 asks of a HEAD response and the reason the suppression
        # is one flag HERE rather than a second set of headers in `do_HEAD`. `Content-Length`
        # is still the length this body WOULD have had, because it was written before the flag
        # was consulted.
        if not self._head:
            self.wfile.write(body)

    def _photo(self, box: int, index: int) -> None:
        """`GET /photo/<box>/<index>`, as a conditional request. See `do_photo`.

        `no-cache` IS NOT `no-store`, AND THE DIFFERENCE IS THE WHOLE POINT. It tells the
        browser to keep the bytes and ask before reusing them, so an unchanged photograph
        costs a ~200-byte 304 rather than the 1.9 MB it measures on this rig. `no-store`
        was the cruder repair available and it would have made every arrow-key step of the
        box walk a fresh download — affordable over loopback and not over the LAN, which is
        exactly where D5's Fulfiller reads his photographs from.

        THE DIGEST IS COMPUTED EVEN WHEN THE ANSWER IS 304, because it is computed FROM the
        bytes and there is no cheaper validator this route can honestly offer (`do_photo`
        argues why). Measured at ~0.75 ms per photograph all in, on a route that serves one
        card at a time on the walk.

        `If-None-Match: *` IS HONOURED AS THE SPEC DEFINES IT — it matches whenever the
        resource exists — rather than being compared as a literal string. Nothing in this
        app sends it; a proxy or a `fetch` written later might, and a server that treated it
        as an ordinary tag would answer 200 forever and look like it worked.
        """
        blob, etag = do_photo(box, index)
        headers = (("ETag", etag), ("Cache-Control", "no-cache"))
        offered = [
            tag.strip()
            for tag in (self.headers.get("If-None-Match") or "").split(",")
            if tag.strip()
        ]
        # A weak comparison, which is what RFC 9110 requires of If-None-Match: a cache that
        # holds `W/"abc"` is holding the same photograph as `"abc"`, and refusing to say so
        # would send 1.9 MB to answer a question already answered.
        fresh = "*" in offered or etag in [
            tag[2:] if tag.startswith("W/") else tag for tag in offered
        ]
        if fresh:
            self.send_response(int(HTTPStatus.NOT_MODIFIED))
            for header, value in self._cors_headers():
                self.send_header(header, value)
            for header, value in headers:
                self.send_header(header, value)
            # No Content-Length and no body: RFC 9110 gives 304 no content at all, so
            # framing it as a zero-length entity would be a claim about a body that the
            # status code says does not exist.
            return self.end_headers()
        return self._send(HTTPStatus.OK, blob, "image/jpeg", headers)

    def _json(self, status: HTTPStatus, payload) -> None:
        self._send(status, json.dumps(payload).encode("utf-8") + b"\n", "application/json")

    def _fail(self, status: HTTPStatus, code: str, message: str) -> None:
        """Every error says what happened and what to do next — DESIGN.md's copy rule
        reaches here, because step 7 shows these strings to a person."""
        self._json(status, {"error": {"code": code, "message": message}})

    # ------------------------------------------------------------------------ input

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise BadRequest(
                HTTPStatus.BAD_REQUEST, "length_invalid", "Content-Length is not a number."
            ) from None
        if length <= 0:
            raise BadRequest(HTTPStatus.BAD_REQUEST, "body_required", "Send a JSON body.")
        # Base64 inflates by a third, and the decoded ceiling is enforced separately.
        if length > MAX_IMAGE_BYTES * 2:
            raise BadRequest(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body_too_large", "Request body is too large."
            )
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise BadRequest(
                HTTPStatus.BAD_REQUEST, "body_invalid", "Body is not valid JSON."
            ) from None
        if not isinstance(payload, dict):
            raise BadRequest(
                HTTPStatus.BAD_REQUEST, "body_invalid", "Body must be a JSON object."
            )
        return payload

    # ----------------------------------------------------------------------- routing

    def _dispatch(self, handler) -> None:
        """One place to turn a refusal into a response.

        `LockTimeout`'s own text blames the capture server for holding the lock, which is a
        lie about itself when the server is the one raising it — so it is answered with a
        message that points at the other process instead of being echoed.

        IT IS ALSO WHERE THE ORIGIN GATE RUNS, ahead of every handler and therefore ahead of
        every route that could be added later. Putting the check in the four `do_*` verb
        methods would be four places to remember; putting it here means a mutating route
        cannot be written that skips it.
        """
        # THE SLOT IS TAKEN BEFORE THE REQUEST COUNTS AS IN FLIGHT, AND THE ORDER IS
        # LOAD-BEARING. `_inflight` is what `drain()` waits on, and a request queued for a slot
        # has not started and cannot finish — counting it would make the drain wait on work that
        # is not happening and then kill it, which is the failure this whole bound is about.
        if not _slots.acquire(timeout=files.LOCK_TIMEOUT_SECONDS):
            self._fail(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "server_busy",
                f"This server is answering {REQUEST_SLOTS} requests already and this one waited "
                f"{files.LOCK_TIMEOUT_SECONDS:.0f}s for a turn. Nothing was read or written. "
                f"Retry, and if it keeps happening something is driving it harder than a person "
                f"can — see docs/DEBTS.md section 11.",
            )
            return
        _inflight_enter()
        try:
            # BEFORE THE BODY IS READ, let alone before the lock is taken. A page that is not
            # allowed to write should not get to make this process allocate a 24 MB buffer
            # for the image it was going to send.
            if self.command not in SAFE_METHODS and not self._origin_allowed():
                raise BadRequest(
                    HTTPStatus.FORBIDDEN,
                    "origin_not_allowed",
                    f"{self._origin()} is not allowed to change anything here. This server "
                    f"answers reads to anyone and writes only to the capture app "
                    f"({', '.join(DEFAULT_ALLOWED_ORIGINS)}). If this is your own app on "
                    f"another address, add it to {ORIGINS_ENV} — comma or space separated — "
                    f"and restart nothing: it is read on every request.",
                )
            handler()
        except BadRequest as exc:
            self._fail(exc.status, exc.code, str(exc))
        except codes_routes.CodesRefusal as exc:
            self._fail(exc.status, exc.code, str(exc))
        except pipeline_routes.PipelineRefusal as exc:
            # The pipeline module raises its own exception type rather than this file's,
            # because this file imports it and the reverse import would be a cycle. One
            # `except` clause is the whole of that seam; every refusal it carries already
            # holds the status and the code it wants to be answered with.
            self._fail(exc.status, exc.code, str(exc))
        except shipping_routes.ShippingRefusal as exc:
            # The shipping module's own exception type, for the identical reason one line
            # up: it cannot import `BadRequest` from here because this file imports IT, and
            # the reverse import would be a cycle. One `except` clause is the whole seam,
            # and every refusal already carries the status and the code it wants.
            self._fail(exc.status, exc.code, str(exc))
        except files.LockTimeout:
            self._fail(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "store_busy",
                "The inventory is locked by another process — most likely a running "
                "`./pkmnscan identify` or `./pkmnscan emit`. Wait for it, then retry.",
            )
        except (master.BadPosition, master.PositionOccupied, master.DuplicateCaptureId) as exc:
            self._fail(HTTPStatus.CONFLICT, "inventory_conflict", str(exc))
        # D20's THREE, CAUGHT HERE SO NONE OF THEM CAN LEAVE AS A 500. Each already carries a
        # message written for a person by `store/master.py` — `check_sections` names what is
        # wrong with a layout, `allocate_capture` names the sealed box and tells you to open
        # it or use another — so they are answered with their own text rather than a
        # substitute. `BoxClosed` reaches this from two directions and both are the same
        # sentence to the operator: a capture into a sealed box, and a request to seal a box
        # that is already sealed.
        #
        # `BadSections` IS 400 AND THE OTHER TWO ARE NOT, because a bad layout is something
        # the request said and the other two are something the store says. A sealed box is a
        # 409: the request was well-formed and lost a race with the lid.
        except master.BadSections as exc:
            self._fail(HTTPStatus.BAD_REQUEST, "sections_invalid", str(exc))
        except master.BoxClosed as exc:
            self._fail(HTTPStatus.CONFLICT, "box_closed", str(exc))
        # `open_section`'s two, and they are 409s on the rule the comment above draws: the
        # request was well-formed — it carries no index to be wrong about — and lost to
        # something the STORE knows, which is where the last divider already is. Each
        # already names that divider in a sentence written for a person, so both are
        # answered with their own text rather than a substitute.
        except master.SectionEmpty as exc:
            self._fail(HTTPStatus.CONFLICT, "section_empty", str(exc))
        except master.SectionAhead as exc:
            self._fail(HTTPStatus.CONFLICT, "section_ahead", str(exc))
        except master.UnknownBox as exc:
            self._fail(HTTPStatus.NOT_FOUND, "box_not_found", str(exc))
        # D83's move primitive, caught here as a backstop rather than the whole story: the
        # move routes run their own state checks first, with the richer per-door messages
        # `card_sold`/`card_retired`/`card_moved` already give — these two exist for any
        # caller that reaches `Inventory.move_card` without going through them, the same
        # belt-and-braces relationship `BoxClosed` already has with `allocate_capture`.
        except master.CardNotFound as exc:
            self._fail(HTTPStatus.NOT_FOUND, "card_not_found", str(exc))
        except master.CardDeparted as exc:
            self._fail(HTTPStatus.CONFLICT, "card_departed", str(exc))
        # A FOURTH JOINS THEM, for the same reason and with the same shape. `BoxNameTaken`
        # is a 409 rather than a 400 on the rule the comment above draws: the request was
        # well-formed and lost to something the STORE knows — another box already answers
        # to that name — which is exactly `BoxClosed`'s case one field over. Its message
        # names the incumbent box, so it is answered with its own text.
        except master.BoxNameTaken as exc:
            self._fail(HTTPStatus.CONFLICT, "name_taken", str(exc))
        except files.StoreError as exc:
            self._fail(HTTPStatus.SERVICE_UNAVAILABLE, "store_unavailable", str(exc))
        except Exception as exc:  # noqa: BLE001 — 500 is reserved for bugs, and this is one
            self.log_error("unhandled %s: %s", type(exc).__name__, exc)
            self._fail(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "server_error",
                f"{type(exc).__name__}: {exc}. This is a bug — check the server log.",
            )
        finally:
            _inflight_leave()
            _slots.release()

    def do_OPTIONS(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's naming
        """The preflight. It answers 204 for any path, and now not for any origin.

        NO PATH CHECK, ON PURPOSE: a preflight is a question about the SERVER's policy, and
        answering 404 for an unknown path here would make a browser report a routing problem
        as a CORS failure. What changed is that `_cors_headers` no longer advertises the
        mutating verbs to an origin this server does not know, so the browser refuses the
        request that would have followed rather than sending it to be refused.
        """
        self._send(HTTPStatus.NO_CONTENT, b"", "text/plain")

    def do_GET(self) -> None:  # noqa: N802
        """The reads. `/search` is the only route in this server with a query string.

        `parse_qs` RATHER THAN A SPLIT ON `=`, for the reason `CLAUDE.md` gives about CSV:
        a card called `Billy & O'Nare` is a real row in a real fixture, and its name reaches
        this route percent-encoded with an ampersand in it. Hand-parsing a query string is
        the same class of mistake as `split(",")` and fails on the same data.
        """

        def run():
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path == "/status":
                return self._json(HTTPStatus.OK, do_status())
            if path == "/inventory":
                return self._json(HTTPStatus.OK, do_inventory())
            if path == "/queues":
                return self._json(HTTPStatus.OK, do_queues())
            if path == "/boxes":
                return self._json(HTTPStatus.OK, do_boxes())
            # D134's graveyard: an exact string, matched by no other route's pattern, over
            # a lock-free read on both its sources.
            if path == "/graveyard":
                return self._json(HTTPStatus.OK, do_graveyard())
            if path == "/games":
                return self._json(HTTPStatus.OK, do_games())
            # D66's order screen. An exact string and therefore no ordering hazard, and a
            # read: it takes no lock, writes nothing, and resolves the open orders in one
            # pass so no two of them are offered the same physical card.
            if path == "/orders":
                return self._json(HTTPStatus.OK, do_orders())
            if path == "/codes":
                return self._json(HTTPStatus.OK, codes_routes.do_codes())
            if path == "/codes/lots":
                return self._json(HTTPStatus.OK, codes_routes.do_codes_lots())
            if path == "/search":
                # `keep_blank_values` so `?q=` reaches `_require_query` and is refused in
                # `query_required` rather than looking like a request with no `q` at all —
                # the two are one refusal, and the code says which to send next.
                query = parse_qs(parsed.query, keep_blank_values=True).get("q") or [""]
                return self._json(HTTPStatus.OK, do_search(query[0]))
            # D34's preflight. Matched BEFORE `_BOXES_ITEM_RE`'s explainer below, which
            # would otherwise answer a real route with "there is no GET /boxes/<n>" — that
            # regex is anchored one segment shorter, so it cannot match this path, and the
            # order here is for the reader rather than for correctness.
            # The review screen's catalog lookup. A query string like `/search` above, and
            # `keep_blank_values` for the same reason — except here a blank `q` is LEGAL and
            # means "suggest from the card's own read", which is the arriving-at-the-card
            # case. Free and read-only; it takes no lock and creates nothing.
            match = _REVIEW_CATALOG_RE.match(path)
            if match:
                query = parse_qs(parsed.query, keep_blank_values=True).get("q") or [""]
                return self._json(
                    HTTPStatus.OK,
                    do_review_catalog(
                        int(match.group(1)), int(match.group(2)), query[0]
                    ),
                )
            match = _BOX_LISTINGS_RE.match(path)
            if match:
                return self._json(HTTPStatus.OK, do_box_listings(int(match.group(1))))
            # D89's free count, the read that comes before the reclaim.
            match = _BOX_PHOTOS_RE.match(path)
            if match:
                return self._json(HTTPStatus.OK, do_box_photos(int(match.group(1))))
            match = _BOXES_ITEM_RE.match(path)
            if match:
                # One box on its own is deliberately NOT a route. `GET /boxes` is a handful
                # of rows and the screen wants all of them to draw a list; a per-box read
                # would be a second renderer of the same object for one caller that does not
                # exist yet. Answered explicitly rather than by falling through, so the
                # message says where the box is instead of `no such route`.
                raise BadRequest(
                    HTTPStatus.NOT_FOUND,
                    "no_such_route",
                    f"There is no GET /boxes/{match.group(1)}. Read /boxes and take the row "
                    f"you want; PUT /boxes/{match.group(1)} is where a box is changed.",
                )
            match = _PHOTO_RE.match(path)
            if match:
                # Its own method because it is the one read in this server that answers a
                # request HEADER — see `_photo`, and `do_photo` for what the validator is
                # protecting against.
                return self._photo(int(match.group(1)), int(match.group(2)))
            # The pipeline reads. All three are free and hold nothing: each one opens the
            # run directory, reads it, and answers — which is what lets a screen poll a run
            # this process did not start and would not otherwise know about.
            # D65's set vocabulary for the capture screen. A READ, and free: it opens a
            # socket to TCGplayer but spends nothing and writes nothing, and it answers 200
            # with an empty list on every failure because the rig must not stop for it.
            if path == "/tcg/sets":
                wanted = parse_qs(urlparse(self.path).query).get("game") or [""]
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_tcg_sets(wanted[0])
                )
            if path == "/pricing":
                # THE CORPUS (D86, amended). A read, free, and the same document whatever the
                # screen is showing — which is the whole difference from `/pipeline/pricing`
                # one branch down: that one answers which cards are in front of the operator,
                # this one answers what has been decided about them.
                return self._json(HTTPStatus.OK, pipeline_routes.do_pricing_corpus())
            if path == "/pipeline/pricing":
                # THE CROSS-RUN WORKLIST (D86). A read, free, and it presses nothing — the
                # per-run route one block down is what it delegates each leg to.
                #
                # `run` REPEATS rather than carrying a comma list, which is `_RUN_TRENDS_RE`'s
                # rule two routes down and `_RUN_SCOPE_RE`'s beside it, for their reason: a
                # comma inside a value is indistinguishable from the separator. With none, the
                # handler chooses every run that still has pricing work in it, which is the
                # state this screen opens in.
                #
                # A STATIC PATH AND THEREFORE NO REGEX, and it is declared ABOVE
                # `/pipeline/runs` for the reader rather than for the matcher: the two are
                # different literals and neither can swallow the other, but the pricing
                # worklist is the broader question and reads first.
                asked = parse_qs(parsed.query, keep_blank_values=True).get("run") or []
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_pipeline_worklist(asked)
                )
            if path == "/pipeline/value":
                # EVERY CARD ON HAND, RANKED BY WHAT IT IS WORTH. A read, free, and it presses
                # nothing — the store-wide sibling of the worklist one branch up: that one
                # answers what a run owes a price, this one answers what is in the drawers and
                # which end of the money it sits at. No band, no filter and no percentile in
                # the query string: every one of those is a slice of the one ranked list this
                # answers with, and the screen takes the slice (see `do_pipeline_value`).
                return self._json(HTTPStatus.OK, pipeline_routes.do_pipeline_value())
            if path == "/pipeline/runs":
                return self._json(HTTPStatus.OK, pipeline_routes.do_pipeline_runs())
            if path == "/pipeline/markdowns":
                # Every markdown this store has written (D100). Reads the directory and holds
                # nothing, the way `/pipeline/runs` does.
                return self._json(HTTPStatus.OK, pipeline_routes.do_markdowns())
            match = _MARKDOWN_TABLE_RE.match(path)
            if match:
                # THE LENS'S INPUT (D103): every live listing the survey saw, refused ones
                # included, each carrying the code that refused it. Free, reads one file.
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_markdown_table(match.group(1))
                )
            match = _MARKDOWN_HISTORY_RE.match(path)
            if match:
                # LEAVES THIS MACHINE, exactly as its run-scoped sibling does and under that
                # route's argument — free, public hosts, one press about one SKU.
                asked = parse_qs(parsed.query, keep_blank_values=True).get("sku") or [""]
                return self._json(
                    HTTPStatus.OK,
                    pipeline_routes.do_markdown_history(match.group(1), asked[0]),
                )
            match = _MARKDOWN_TRENDS_RE.match(path)
            if match:
                # `sku` REPEATS AND IS REQUIRED HERE. A survey is the whole live inventory and
                # an unfiltered walk over 441 rows is ~5.5 minutes at a public mirror, which
                # would make D62's press meaningless — the handler refuses an empty list.
                asked = parse_qs(parsed.query, keep_blank_values=True).get("sku") or []
                return self._json(
                    HTTPStatus.OK,
                    pipeline_routes.do_markdown_trends(match.group(1), asked),
                )
            match = _MARKDOWN_FILE_RE.match(path)
            if match:
                # The worklist the operator edits and the import CSV they upload. Forced as a
                # download rather than rendered, because a CSV shown in a browser tab is a
                # file somebody then has to work out how to save.
                wanted = parse_qs(parsed.query, keep_blank_values=True).get("name") or [""]
                blob, kind = pipeline_routes.do_markdown_file(match.group(1), wanted[0])
                return self._send(
                    HTTPStatus.OK,
                    blob,
                    kind,
                    (("Content-Disposition", f'attachment; filename="{wanted[0]}"'),),
                )
            match = _RUN_FILE_RE.match(path)
            if match:
                # The download. Matched BEFORE the run-item pattern, which would otherwise
                # never see it (the item regex is anchored and admits no slash) — ordered
                # this way for the reader, so the more specific path is the one above.
                wanted = parse_qs(parsed.query, keep_blank_values=True).get("name") or [""]
                blob, kind = pipeline_routes.do_pipeline_file(match.group(1), wanted[0])
                return self._send(HTTPStatus.OK, blob, kind)
            match = _RUN_PRICING_RE.match(path)
            if match:
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_pipeline_pricing(match.group(1))
                )
            match = _RUN_HISTORY_RE.match(path)
            if match:
                # THE ONE READ HERE THAT LEAVES THIS MACHINE. It is free, both hosts are
                # public, and it answers one press about one SKU — `server/pipeline_routes.py`'s
                # header carries the argument and names what it may not become. The SKU is a
                # query parameter rather than a path segment because it is a FILTER on the run
                # rather than a thing the run contains: `/history` with no `?sku=` is a
                # question this route refuses by name rather than a path that does not exist.
                asked = parse_qs(parsed.query, keep_blank_values=True).get("sku") or [""]
                return self._json(
                    HTTPStatus.OK,
                    pipeline_routes.do_pipeline_history(match.group(1), asked[0]),
                )
            match = _RUN_TRENDS_RE.match(path)
            if match:
                # THE SAME READ, BATCHED, AND IT LEAVES THIS MACHINE FOR THE SAME REASON.
                # D62 named this route and the condition for building it; D79 is the owner
                # answering that condition. It is still a press — nothing polls it — and what
                # changed is that one press covers the list instead of one card.
                #
                # `sku` REPEATS rather than carrying a comma list, which is `_RUN_SCOPE_RE`'s
                # own rule one route down and for the identical reason: a comma inside a value
                # would be indistinguishable from the separator. With none, the handler walks
                # the run's own table and skips the rows it can add nothing for.
                asked = parse_qs(parsed.query, keep_blank_values=True).get("sku") or []
                return self._json(
                    HTTPStatus.OK,
                    pipeline_routes.do_pipeline_trends(match.group(1), asked),
                )
            match = _RUN_SCOPE_RE.match(path)
            if match:
                # D76's lever, drawn before it is pulled. `game`, `scope` and `set_ids` are
                # the same three fields `POST .../export` takes, so the screen asks this
                # route the identical question it is about to press — which is what stops the
                # panel describing a scope different from the one the button would send.
                #
                # `set_ids` REPEATS rather than carrying a comma list, because a comma inside
                # one value is exactly how a query-string list starts lying and `parse_qs`
                # already gives the honest shape for free.
                asked = parse_qs(parsed.query, keep_blank_values=True)
                wanted: dict = {}
                if asked.get("game", [""])[0]:
                    wanted["game"] = asked["game"][0]
                if asked.get("scope", [""])[0]:
                    wanted["scope"] = asked["scope"][0]
                ids = [v for v in asked.get("set_ids", []) if v.strip()]
                if ids:
                    # NOT COERCED SILENTLY. A non-numeric id reaches the handler as the
                    # string it was and is refused there by name, rather than being dropped
                    # here into a scope that quietly means something else.
                    wanted["set_ids"] = [
                        int(v) if v.strip().isdigit() else v for v in ids
                    ]
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_pipeline_scope(match.group(1), wanted)
                )
            match = _RUN_ITEM_RE.match(path)
            if match:
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_pipeline_run(match.group(1))
                )
            # D61's Pirate Ship import file. `keep_blank_values` so `?name=` reaches the
            # handler's own refusal rather than looking absent — `/search` and
            # `_RUN_FILE_RE` above take the same care for the same reason. The
            # `Content-Disposition` rides on `_send`'s existing `extra` tuple, which until
            # now only `_photo` used, for its ETag.
            match = _SHIPPING_FILE_RE.match(path)
            if match:
                wanted = parse_qs(parsed.query, keep_blank_values=True).get("name") or [""]
                blob, kind = shipping_routes.do_shipping_file(match.group(1), wanted[0])
                return self._send(
                    HTTPStatus.OK,
                    blob,
                    kind,
                    (("Content-Disposition", 'attachment; filename="pirateship-import.csv"'),),
                )
            # THE APP ITSELF, AND IT IS THE LAST THING TRIED (D138). Every route above is
            # matched first, so nothing in `app/dist/` can shadow a route; what reaches here
            # is `/`, an asset, or an address somebody typed. `parsed.path` rather than the
            # stripped `path`, because a trailing slash is part of a file's name to a
            # filesystem and stripping it turned `/assets/` into a request for `/assets`.
            if app_claims(parsed.path):
                blob, kind, cache = do_app_file(parsed.path)
                return self._send(
                    HTTPStatus.OK, blob, kind, (("Cache-Control", cache),)
                )
            raise BadRequest(HTTPStatus.NOT_FOUND, "no_such_route", f"No GET route {path}.")

        self._dispatch(run)

    def do_HEAD(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's naming
        """`GET` with the body withheld. Every GET route, not only the app.

        UNTIL THIS EXISTED THE ANSWER WAS 501. `BaseHTTPRequestHandler` dispatches on the
        method name and this class defined no `do_HEAD`, so `curl -I http://localhost:8000/`
        answered `501 Unsupported method ('HEAD')`. That was harmless while this process was
        an API with no HTML on it — nothing HEADs a JSON route — and stopped being harmless
        the day D137 put the built app at `/` and its assets under `/assets/` on this same
        port. HEAD is the first thing an uptime monitor, a link checker, a proxy and `curl -I`
        reach for, and 501 to all four reads as "this server is broken" rather than as "this
        verb is unused".

        IT IS THE SAME DISPATCH, AND THAT IS THE POINT. RFC 9110 requires the header field
        values of a HEAD response to be the ones the GET would have sent, which is only
        truthfully achievable by PRODUCING the response and withholding the body — so this
        runs `do_GET` behind a flag `_send` reads. The alternative, a second table of paths
        with their headers spelled out beside them, is the drift this repo keeps audit rows
        to prevent: `X-Pkmnscan-Boot`, the CORS block and `Connection: close` are each
        composed in exactly one place, and a hand-rolled HEAD would be a second spelling of
        all three with nothing comparing it against the first.

        EVERY GET ROUTE AND NOT ONLY THE APP SURFACE, DELIBERATELY. The narrow answer — HEAD
        for `/` and the assets, a 405 everywhere else — was considered and refused on the
        grounds this change is about: `/status` is the likeliest thing of all to have a
        monitor pointed at it, and answering that 405 reproduces the defect one route over. It
        also needs a second place that knows which paths the app claims, and a route written
        later would silently lack HEAD with nothing failing. WHAT THE BROAD ANSWER COSTS is
        that a HEAD does the handler's work and throws the bytes away: an `/inventory` payload
        built and discarded, a photograph read and digested for its ETag, `/tcg/sets` opening
        its socket to TCGplayer. That is accepted, because every one of those is the cost of
        the GET the same client could have sent instead, and because no GET route in this
        server writes — the origin gate is on the mutating verbs and this verb is not one.

        THE TWO PATHS THAT DO NOT REACH `_send` ARE ALREADY RIGHT, and `end_headers`'s own
        override names them for this reason. `_photo`'s 304 branch sends no body under any
        verb, which is what RFC 9110 gives a 304. `BaseHTTPRequestHandler.send_error` tests
        `self.command` itself and withholds the body while still sending its `Content-Type`
        and `Content-Length` — the rule, kept by stdlib — and with this method defined it is
        no longer what answers a HEAD at all, only a request whose line did not parse.
        """
        self._head = True
        try:
            self.do_GET()
        finally:
            # RESET RATHER THAN TRUST THE CONNECTION TO CLOSE. `end_headers` sends
            # `Connection: close` on every response, so `handle_one_request` does not loop and
            # this instance answers one request — but a flag whose correctness rests on
            # another header staying the way it is today is the coupling this file spends its
            # comments removing.
            self._head = False

    def do_POST(self) -> None:  # noqa: N802
        """Capture, and 7b's two writes.

        BOTH OF 7b's READ A BODY, including mark-sold, whose sale needs nothing in it — send
        `{}`. `self._body()` refuses an empty request as `body_required`, and that uniformity
        is the reason rather than an oversight: every write in this server reads its body the
        same way, and a second reader that tolerated an absent one would be a second set of
        rules about request size and encoding. The cost is two characters on the wire.
        """

        def run():
            path = urlparse(self.path).path.rstrip("/") or "/"
            if path == "/capture":
                status, body = do_capture(self._body())
                return self._json(status, body)
            if path == "/boxes":
                status, body = do_create_box(self._body())
                return self._json(status, body)
            # An exact string, matched before the position regex it shares a prefix with —
            # for the reader, not for correctness: `_REVIEW_ANSWER_RE` admits digits only,
            # so `group-answer` could never reach it.
            if path == "/review/group-answer":
                body = do_review_group_answer(self._body())
                return self._json(HTTPStatus.OK, body)
            match = _REVIEW_ANSWER_RE.match(path)
            if match:
                body = do_review_answer(
                    int(match.group(1)), int(match.group(2)), self._body()
                )
                return self._json(HTTPStatus.OK, body)
            match = _REVIEW_STAND_DOWN_RE.match(path)
            if match:
                body = do_review_stand_down(
                    int(match.group(1)), int(match.group(2)), self._body()
                )
                return self._json(HTTPStatus.OK, body)
            # Matched after the review route and before the fallthrough. `/inventory/3/17`
            # keeps its own regex, anchored to end there, so this cannot shadow the PUT and
            # DELETE paths — a sale is a different verb on a longer path, not a mode of them.
            match = _SOLD_RE.match(path)
            if match:
                body = do_mark_sold(int(match.group(1)), int(match.group(2)), self._body())
                return self._json(HTTPStatus.OK, body)
            # D26's two, matched the same way and for the same reason as the sale: each is
            # a different verb on a longer path than `/inventory/<box>/<index>`, whose own
            # regex is anchored to end there, so neither can shadow the PUT and DELETE.
            match = _RETIRE_RE.match(path)
            if match:
                body = do_retire(int(match.group(1)), int(match.group(2)), self._body())
                return self._json(HTTPStatus.OK, body)
            match = _RESHOOT_RE.match(path)
            if match:
                body = do_reshoot(int(match.group(1)), int(match.group(2)), self._body())
                return self._json(HTTPStatus.OK, body)
            # The mid-box delete (D10, ruling 1). A POST and not a mode of the DELETE verb:
            # the regex comment at `_REMOVE_RE` has the argument — the shift is not
            # idempotent and must be unreachable from the undo path by any accident.
            match = _REMOVE_RE.match(path)
            if match:
                body = do_remove_card(
                    int(match.group(1)), int(match.group(2)), self._body()
                )
                return self._json(HTTPStatus.OK, body)
            # D83's third door: one card, to another box. Matched before the batched form
            # one register down, though the two patterns cannot collide — `_MOVE_RE` needs
            # two digit groups before `/move` and `_MOVE_CARDS_RE` needs exactly one.
            match = _MOVE_RE.match(path)
            if match:
                body = do_move_card(
                    int(match.group(1)), int(match.group(2)), self._body()
                )
                return self._json(HTTPStatus.OK, body)
            # D83's batched move: a ticked selection, a section (indices computed by the
            # caller from the box's own live rendering), or a whole box (`indices: null`) —
            # which is a merge, from the caller's side, with no separate route for it.
            match = _MOVE_CARDS_RE.match(path)
            if match:
                body = do_move_cards(int(match.group(1)), self._body())
                return self._json(HTTPStatus.OK, body)
            # D34's release, matched before the pipeline block for no reason but that it is
            # a box route and belongs beside the other ones. It is a POST rather than a PUT
            # on `/boxes/<box>` because it sets nothing the box carries: `PUT_BOX_FIELDS`
            # is the box's own record — name, dividers, lid — and a listing count is a fact
            # about a SKU that this box merely holds copies of.
            match = _BOX_LISTINGS_RELEASE_RE.match(path)
            if match:
                body = do_release_box_listings(int(match.group(1)), self._body())
                return self._json(HTTPStatus.OK, body)
            # D89's reclaim: the photographs of every sold card in the box, records kept.
            match = _BOX_PHOTOS_RECLAIM_RE.match(path)
            if match:
                body = do_reclaim_box_photos(int(match.group(1)), self._body())
                return self._json(HTTPStatus.OK, body)
            # D10's divider, opened at the rig. A POST rather than a field on the box's own
            # PUT because it sets no field: the index it writes is read from the store, not
            # from the request, which is exactly what `PUT_BOX_FIELDS` cannot express.
            match = _BOX_SECTIONS_RE.match(path)
            if match:
                body = do_open_section(int(match.group(1)), self._body())
                return self._json(HTTPStatus.OK, body)
            # THE PIPELINE WRITES, AND THE FIRST OF THEM IS THE ONLY ROUTE IN THIS SERVER
            # THAT CAN COST MONEY. It is named for it, it refuses without an explicit
            # `confirm`, and it refuses a second run over a capture directory a live run is
            # already reading — see `server/pipeline_routes.py`'s header for what that
            # replaces. The preflight beside it is free and creates no run at all, which is
            # what the screen must show before it may ask.
            # The codes track's two writes. FREE — no model call anywhere on this
            # track — so neither is behind D33's money gate. The export carries its own
            # two-step instead, for a different irreversible thing: a code handed to a
            # buyer cannot be un-handed. `server/codes_routes.py` has the argument.
            if path == "/codes/scan":
                status, body = codes_routes.do_codes_scan(self._body(), captures_root())
                return self._json(status, body)
            if path == "/codes/export":
                status, body = codes_routes.do_codes_export(self._body())
                return self._json(status, body)
            if path == "/codes/lots":
                status, body = codes_routes.do_codes_lot(self._body())
                return self._json(status, body)
            if path == "/pipeline/preflight":
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_pipeline_preflight(self._body())
                )
            # The crop preview, and it sits BEFORE the one that spends for the reason the
            # money gate itself gives: what the reading does to the bytes has to be legible
            # before the estimate is asked for, not after it. Free, writes nothing, and
            # unlike the preflight it does not even shell out.
            if path == "/pipeline/crop-preview":
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_pipeline_crop_preview(self._body())
                )
            if path == "/pipeline/live-export":
                # THE OPERATOR'S OWN LIVE LISTINGS, FETCHED (D104). FREE — it starts no child
                # and can put no number on an invoice — but it READS A SECRET AND OPENS A
                # SOCKET, which only `POST /pipeline/runs/<name>/export` did before it. The
                # second document, not a second scope: that route fetches the CATALOGUE at
                # `MyInventory: False`, and this fetches the opposite. `POST /pipeline/identify`
                # is still the only route in this server that can spend money.
                return self._json(HTTPStatus.OK, pipeline_routes.do_live_export())
            if path == "/pipeline/reconcile-live":
                # THE FOURTH COMMAND, OVER THE WHOLE STORE (D87). Free, and it writes only
                # when asked — the preview is the default. Not run-scoped: this is the one
                # shape that can report what TCGplayer holds and this pipeline never sent.
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_reconcile_live(self._body())
                )
            if path == "/queues/refresh":
                # THE STANDING QUEUES, RE-RESOLVED STORE-WIDE. `reconcile-live`'s shape one
                # file over: free, the preview is the default, and it writes only when asked.
                # DISPATCHED HERE BESIDE `GET /queues` because that is the pair an operator
                # thinks in, and IMPLEMENTED in `pipeline_routes` because it runs the CLI —
                # the same split `do_pipeline_worklist` already has.
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_queue_refresh(self._body())
                )
            if path == "/pipeline/markdowns":
                # THE STALE-LISTING MARKDOWN (D100). Free and store-wide, `reconcile-live`'s
                # shape: the preview is the default and `write` produces a WORKLIST, which
                # this process uploads nowhere. Every row it writes carries `Add to Quantity`
                # 0, so no file on this path can add, remove or delete a copy.
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_markdown_list(self._body())
                )
            match = _MARKDOWN_PUSH_RE.match(path)
            if match:
                # INTO STAGED, WHICH NO BUYER CAN SEE. Refuses without `confirm`, and pushes
                # the FILE on disk rather than re-deriving rows from the corpus — what is
                # uploaded has to be what the operator can open and diff.
                return self._json(
                    HTTPStatus.OK,
                    pipeline_routes.do_markdown_push(match.group(1), self._body()),
                )
            match = _MARKDOWN_PUBLISH_RE.match(path)
            if match:
                # **THE ONLY ROUTE IN THIS SERVER THAT CHANGES WHAT A BUYER PAYS.** It takes no
                # upload id: that is read off the push receipt on disk, so a replayed or
                # mistyped body cannot publish an upload this markdown never made.
                return self._json(
                    HTTPStatus.OK,
                    pipeline_routes.do_markdown_publish(match.group(1), self._body()),
                )
            match = _MARKDOWN_ROLLBACK_RE.match(path)
            if match:
                # THE UNDO, and the one outbound write here that makes the store SMALLER
                # rather than larger. Refuses once the upload has been published: there is
                # nothing staged to discard then, and a live price goes back the way it came
                # down — another markdown.
                return self._json(
                    HTTPStatus.OK,
                    pipeline_routes.do_markdown_rollback(match.group(1), self._body()),
                )
            match = _MARKDOWN_APPLY_RE.match(path)
            if match:
                # The edited worklist back, and the file the operator uploads to TCGplayer.
                # Previews without `write`, like every other half of this pair.
                return self._json(
                    HTTPStatus.OK,
                    pipeline_routes.do_markdown_apply(match.group(1), self._body()),
                )
            if path == "/pipeline/emit":
                # ONE IMPORT FILE OVER SEVERAL RUNS (D86). FREE — it reads runs, writes a CSV
                # and raises `pushed`; the route that can cause money to be spent is the one
                # directly below and is still named for it.
                #
                # A LIST AND NOT A WIDENED PER-RUN ROUTE, because the copies are deduped
                # across the send — a card in three runs is ONE row over the union of
                # positions, which holds with or without a cap. A cap this send asks for is
                # spent once across it too: `pipeline/join.py` spends `live_cap - copies_out`
                # per run, so N per-run presses at one cap ARE the over-push this prevents.
                # Measured at the old standing cap of four: three separate emits over three
                # real runs wrote two SKUs past it.
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_pipeline_merged_emit(self._body())
                )
            if path == "/pricing/clear":
                # THE MASS-CLEAR (D-a-typed-price-is-cleared-by-a-press). FREE, and it is the
                # only route in this server that DELETES a pricing answer. Beside `PUT
                # /pricing` rather than under `/pipeline/` because it acts on the store's one
                # corpus and not on any run — the same reason `GET /pricing` is not
                # `GET /pipeline/pricing`.
                #
                # A POST AND NOT A DELETE, because the request carries a scope, a window and a
                # revision, and the response carries the answers it removed — which is what the
                # undo is built from. A DELETE whose whole meaning is in its body is a POST
                # spelled to look tidier.
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_pricing_clear(self._body())
                )
            if path == "/pricing/restore":
                # THE WAY BACK, and the exact inverse of the route above. It writes only SKUs
                # the corpus does not currently answer, so an undo can never overwrite a price
                # typed since the clear.
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_pricing_restore(self._body())
                )
            if path == "/pipeline/identify":
                status, body = pipeline_routes.do_pipeline_identify(self._body())
                return self._json(status, body)
            # THE ONE OUTBOUND CALL, and it is not the one that spends. It fetches the
            # operator's own Filtered Export from TCGplayer with the session cookie in
            # `.env`, so `join` no longer needs a file downloaded and uploaded by hand.
            # Before `_RUN_STEP_RE`, whose `[a-z]+` would match `export` and refuse it as a
            # step that does not exist.
            match = _RUN_EXPORT_RE.match(path)
            if match:
                return self._json(
                    HTTPStatus.OK,
                    pipeline_routes.do_pipeline_export(match.group(1), self._body()),
                )
            match = _RUN_STEP_RE.match(path)
            if match:
                return self._json(
                    HTTPStatus.OK,
                    pipeline_routes.do_pipeline_step(
                        match.group(1), match.group(2), self._body()
                    ),
                )
            # D66's three writes, all exact strings — no regex, and therefore no ordering
            # hazard against each other or against anything above. NONE OF THEM SPENDS:
            # `/orders/fetch` is a read of this account's own orders at TCGplayer, and the
            # other two touch only this store. The one route that can cost money is still
            # `/pipeline/identify`.
            #
            # The pull is BODY-ADDRESSED rather than `/orders/<key>/pull`, and that is
            # forced: an order key is `source:number` and a number may legally carry a
            # colon.
            if path == "/orders/fetch":
                return self._json(HTTPStatus.OK, do_order_fetch(self._body()))
            if path == "/orders/ingest":
                return self._json(HTTPStatus.OK, do_order_ingest(self._body()))
            if path == "/orders/pull":
                return self._json(HTTPStatus.OK, do_order_pull(self._body()))
            # D113's two. `fill` closes a line with no card behind it and sells nothing;
            # `line-kind` records the operator's own classification, which routes the
            # shipment and must therefore be sayable BEFORE the fill rather than with it.
            if path == "/orders/fill":
                return self._json(HTTPStatus.OK, do_order_fill(self._body()))
            if path == "/orders/line-kind":
                return self._json(HTTPStatus.OK, do_order_line_kind(self._body()))
            if path == "/orders/close":
                return self._json(HTTPStatus.OK, do_order_close(self._body()))
            # D61's Export Shipping read. Free, re-runnable, and it spends nothing — what
            # it costs is memory holding buyer addresses, which the DELETE below is the way
            # back from.
            if path == "/shipping/batches":
                return self._json(
                    HTTPStatus.OK, shipping_routes.do_shipping_batches(self._body())
                )
            # T2b — the Rubber Stamp fill. Free, re-runnable and idempotent: it re-asks the
            # ledger and re-renders the held import, spending nothing and writing nothing.
            # `_order_stamps` is passed IN rather than reached FOR, because the shipping
            # module cannot import this file (this file imports it) and must not learn to
            # open the store: it is the one module that holds a buyer's address, and what
            # crosses the seam is order numbers one way and position labels the other.
            match = _SHIPPING_STAMPS_RE.match(path)
            if match:
                return self._json(
                    HTTPStatus.OK,
                    shipping_routes.do_shipping_stamps(
                        match.group(1), self._body(), _order_stamps
                    ),
                )
            if app_owns(path):
                # The app is served here and is read-only (D138). 405 and not 404,
                # because the resource exists — saying "no such route" about a path
                # this server answers on GET is a lie that reads as a routing bug.
                raise BadRequest(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    "method_not_allowed",
                    f"POST is not allowed on {path}. The app is served here.",
                )
            raise BadRequest(HTTPStatus.NOT_FOUND, "no_such_route", f"No POST route {path}.")

        self._dispatch(run)

    def do_PUT(self) -> None:  # noqa: N802
        """The two corrections: one card's recorded claims, and one box's own fields.

        Both are per-object and neither takes a whole-document replace, which is the same
        rule `do_put_card` states for cards applied to boxes: rebuilding a registry from a
        client's stale snapshot is the lost update the allocator is shaped to avoid, with a
        wider blast radius. A box is edited by naming it in the path.
        """

        def run():
            path = urlparse(self.path).path.rstrip("/") or "/"
            match = _INVENTORY_ITEM_RE.match(path)
            if match:
                body = do_put_card(int(match.group(1)), int(match.group(2)), self._body())
                return self._json(HTTPStatus.OK, body)
            # The box-level claim apply (owner's ask of 2026-08-23): the card correction
            # one path segment broader — same vocabulary, every eligible card in the box,
            # all-or-nothing.
            match = _INVENTORY_BOX_RE.match(path)
            if match:
                body = do_put_box_claims(int(match.group(1)), self._body())
                return self._json(HTTPStatus.OK, body)
            match = _BOXES_ITEM_RE.match(path)
            if match:
                return self._json(
                    HTTPStatus.OK, do_put_box(int(match.group(1)), self._body())
                )
            if path == "/pricing":
                # THE CORPUS, REPLACED WHOLESALE (D86, amended) — the read-modify-write the
                # retired per-run `PUT .../decisions` used, over one document for the store
                # instead of one per run. Wholesale because the screen round-trips every key
                # it does not understand, which is what keeps a hand-written `_note` alive.
                # That per-run route is DELETED (D86, amended 2026-09-02): it answered 409
                # for every run made after the corpus landed, because `join` no longer wrote
                # the file it edited.
                return self._json(
                    HTTPStatus.OK, pipeline_routes.do_pricing_corpus_write(self._body())
                )
            if app_owns(path):
                # The app is served here and is read-only (D138). 405 and not 404,
                # because the resource exists — saying "no such route" about a path
                # this server answers on GET is a lie that reads as a routing bug.
                raise BadRequest(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    "method_not_allowed",
                    f"PUT is not allowed on {path}. The app is served here.",
                )
            raise BadRequest(HTTPStatus.NOT_FOUND, "no_such_route", f"No PUT route {path}.")

        self._dispatch(run)

    def do_DELETE(self) -> None:  # noqa: N802
        """Undo, and the whole-box delete. No body is read: the path is the whole request.

        Answers 200 with a body rather than 204, because the app names what it just
        removed and this response is where that name comes from. A 204 would make the app
        compose it from what it believed it was deleting — and the two disagree exactly
        when the other device (D13) has captured since.

        THE MID-BOX DELETE IS DELIBERATELY NOT HERE. It is `POST .../remove`, because it
        is not idempotent — the shift slides a different card into the deleted index, so a
        replay needs the body's aim check — and because the renumbering operation must not
        be one stray token away from this verb's newest-only undo. `_REMOVE_RE` has the
        argument. Both routes that ARE here refuse a replay on their own: the undo finds
        nothing at the position, the box delete finds no box.
        """

        def run():
            path = urlparse(self.path).path.rstrip("/") or "/"
            match = _INVENTORY_ITEM_RE.match(path)
            if match:
                body = do_delete_card(int(match.group(1)), int(match.group(2)))
                return self._json(HTTPStatus.OK, body)
            # D10, ruling 3: the whole-box delete, gated behind
            # `box_not_empty_of_commitments` in the handler. Digits only, like every
            # other box pattern — a non-numeric box falls through to `no_such_route`.
            match = _BOXES_ITEM_RE.match(path)
            if match:
                body = do_delete_box(int(match.group(1)))
                return self._json(HTTPStatus.OK, body)
            # D61's way back. It drops a held batch — and the buyer addresses in it — now
            # rather than in half an hour, which is what CLAUDE.md's hard rule asks of
            # anything that makes this process hold one. Answers a body rather than a 204,
            # by this verb's own existing rule: the app names what it just removed, and
            # this response is where that name comes from.
            match = _SHIPPING_ITEM_RE.match(path)
            if match:
                return self._json(
                    HTTPStatus.OK, shipping_routes.do_shipping_forget(match.group(1))
                )
            if app_owns(path):
                # The app is served here and is read-only (D138). 405 and not 404,
                # because the resource exists — saying "no such route" about a path
                # this server answers on GET is a lie that reads as a routing bug.
                raise BadRequest(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    "method_not_allowed",
                    f"DELETE is not allowed on {path}. The app is served here.",
                )
            raise BadRequest(
                HTTPStatus.NOT_FOUND, "no_such_route", f"No DELETE route {path}."
            )

        self._dispatch(run)

    def log_message(self, fmt: str, *args) -> None:
        print(f"  {self.command:6} {fmt % args}")


# --------------------------------------------------------------------------- graceful drain

# IN-FLIGHT REQUESTS, NOT THREADS, AND THE DIFFERENCE IS THE WHOLE DESIGN.
#
# The obvious drain is to let `server_close()` join the handler threads, and it cannot work
# here for two independent reasons, both measured rather than assumed:
#
#   1. `ThreadingHTTPServer` sets `daemon_threads = True`, and `socketserver._Threads.append`
#      DISCARDS a daemon thread instead of recording it — so `_threads` is always empty and
#      the join inside `server_close()` is already a no-op. It looks like a drain and is not.
#   2. Setting `daemon_threads = False` does not fix it either. `protocol_version` is
#      HTTP/1.1, so a handler thread lives for the whole keep-alive CONNECTION rather than for
#      one request, and `BaseHTTPRequestHandler.timeout` is None — so the join would block
#      forever on an idle browser tab sitting on the review queue.
#
# Counting at `_dispatch` is the version that terminates. It is entered after the request line
# is parsed and before the body is read, so it counts a request being served and never an idle
# connection waiting for the next one.
#
# WHAT IT IS FOR: `scripts/serve.py` restarts this process whenever a watched Python file
# changes, which is many times a day rather than once. `store/session.py:Store.write()` replaces
# four JSON files in sequence — each atomic on its own, none atomic as a set — so a kill landing
# between them leaves a torn store. That risk exists today at Ctrl-C frequency; auto-restart
# would multiply it, and this is what pays for it.
_inflight_lock = threading.Condition()
_inflight = 0


# ------------------------------------------------------- the bound on concurrent requests
#
# WHAT RAN OUT WAS THE INTERPRETER, NOT THREADS, AND THAT IS WHY THE BOUND IS HERE.
# `docs/DEBTS.md` section 11 records the measurement this exists for: 969 handler threads under
# a Playwright fleet, every one of them blocked in `PyEval_AcquireThread` — waiting for the GIL,
# not for the store and not for the network — at 338% CPU, holding the port and answering
# nothing. The contended resource was Python itself.
#
# So the cap is on requests EXECUTING, and it is deliberately not a thread pool. A pool bounds
# thread count, which is the wrong number: a thread parked on `readline` between keep-alive
# requests consumes no interpreter at all, and `CaptureHandler.timeout` already reaps those. A
# pool would also have to answer what happens when idle connections hold every worker — N idle
# browser tabs starving a pool of N — which is the hardest question in this file and is not one
# this failure asks. A semaphore here composes with what exists instead: the timeout bounds idle
# connections, this bounds active ones, and neither needs a new lifetime concept.
#
# WHAT IT DOES NOT DO, said plainly so section 11 does not have to be read to learn it: it does
# not bound thread count. Under the same fleet the threads are still created — they park on this
# semaphore, releasing the GIL while they wait, so the server goes on answering. If thread count
# ever becomes the cost that bites, that is memory rather than CPU and only a real pool fixes it.
#
# THE WAIT IS THE STORE LOCK'S, NEVER A NEW CONSTANT. `files.LOCK_TIMEOUT_SECONDS` is what every
# other wait in this process is derived from, including `serve.py`'s drain grace, which is that
# plus ten — so a request queued for a slot either gets one and completes or refuses INSIDE the
# drain window, which is exactly the guarantee the drain needs and did not have.
REQUEST_SLOTS = 4
_slots = threading.BoundedSemaphore(REQUEST_SLOTS)


def slots_in_use() -> int:
    """For the harness: how many requests hold a slot right now. Never more than `REQUEST_SLOTS`."""
    return REQUEST_SLOTS - _slots._value  # noqa: SLF001 — the counter has no public reader


def _inflight_enter() -> None:
    global _inflight
    with _inflight_lock:
        _inflight += 1


def _inflight_leave() -> None:
    global _inflight
    with _inflight_lock:
        _inflight -= 1
        _inflight_lock.notify_all()


def inflight() -> int:
    """For the harness. Reading it needs the lock; asserting on it should not need the lock."""
    with _inflight_lock:
        return _inflight


def drain(timeout: float) -> bool:
    """Wait for in-flight requests to finish. True if they all did.

    The caller must have stopped accepting first, or this races a new arrival forever.
    """
    deadline = time.monotonic() + timeout
    with _inflight_lock:
        while _inflight > 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            _inflight_lock.wait(remaining)
    return True


# DERIVED FROM THE LOCK TIMEOUT, NEVER CHOSEN. `files.LOCK_TIMEOUT_SECONDS` is 30, and a
# capture posted while `./pkmnscan identify` holds the store lock legitimately takes that long
# before it answers `store_busy`. A shorter drain would convert a true refusal — a request that
# is behaving correctly and is about to say so — into a killed socket, which is the same
# argument `app/src/server.ts` makes one process over for having no client timeout below 30s.
DRAIN_SECONDS = files.LOCK_TIMEOUT_SECONDS + 5


class CaptureServer(ThreadingHTTPServer):
    """`ThreadingHTTPServer` with a listen backlog big enough for the real client.

    `socketserver` defaults `request_queue_size` to 5. That is the queue of connections the
    OS holds between SYN and `accept()`, and anything past it is reset before this process
    sees it — with HTTP/1.1 keep-alive a browser opens several connections per origin, and
    two devices (D13) reach that on their own.

    Measured before this was raised: 20 simultaneous captures, 8 served and 12 reset by the
    OS. Worth being exact about what that did and did not break, because the two are easy
    to confuse. The 8 that arrived got distinct contiguous indices, wrote 8 photos and 8
    records, and lost nothing — the lock and `allocate_capture` did their job. The other 12
    never reached the handler at all. A dropped connection is a capture the operator can
    see fail and retry; a duplicated index would be a card silently overwritten, and that
    is the failure this server is shaped to prevent.
    """

    request_queue_size = 128

    # ------------------------------------------------------------------ the worker pool
    #
    # ONE WORKER PER REQUEST, NOT PER CONNECTION, AND `Connection: close` IS WHAT MAKES THAT TRUE.
    # `ThreadingMixIn.process_request` spawns a thread per CONNECTION and bounds nothing, which is
    # the half `REQUEST_SLOTS` deliberately does not fix — a parked thread costs memory rather than
    # the interpreter. A fixed pool bounds the count. But a pool over keep-alive is the trap this
    # file already wrote down: a worker holding an idle connection serves nobody, so N idle browser
    # tabs starve a pool of N completely. Closing after every response is the answer, and it is why
    # a pool is safe here and would not have been before.
    #
    # MEASURED ON THE OWNER'S STORE, 150 concurrent connections, against the semaphore alone:
    # 45.5 requests/sec against 45.6, probe p50 3.94s against 3.84s — identical within noise — and
    # PEAK THREADS 5 AGAINST 153. The bound on threads is what this buys, and it costs nothing
    # measurable.
    #
    # THE SEMAPHORE STAYS, AND IT IS NOT A SECOND MECHANISM FOR ONE JOB. With one request per
    # worker the pool size is also the bound on concurrent execution, so `REQUEST_SLOTS` never
    # blocks today. It is the INVARIANT rather than the implementation: `protocol_version` is one
    # edit from restoring keep-alive, and on that day the pool bounds threads and the semaphore is
    # the only thing still bounding execution. T7 asserts the invariant, not the transport.
    _pool: Optional[concurrent.futures.ThreadPoolExecutor] = None

    def process_request(self, request, client_address) -> None:
        if self._pool is None:
            self._pool = concurrent.futures.ThreadPoolExecutor(
                max_workers=REQUEST_SLOTS, thread_name_prefix="capture"
            )
        self._pool.submit(self._serve_one, request, client_address)

    def _serve_one(self, request, client_address) -> None:
        """`ThreadingMixIn.process_request_thread`'s body, run on a pooled worker instead."""
        try:
            self.finish_request(request, client_address)
        except Exception:  # noqa: BLE001 — matches ThreadingMixIn's own contract
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)

    def server_close(self) -> None:
        super().server_close()
        if self._pool is not None:
            self._pool.shutdown(wait=False)


def serve(host: str = HOST, port: int = PORT) -> None:
    root = captures_root()
    root.mkdir(parents=True, exist_ok=True)
    try:
        httpd = CaptureServer((host, port), CaptureHandler)
    except OSError as exc:
        # `allow_reuse_address` is SO_REUSEADDR, which does not let a second process listen on
        # a port that is already bound — so this is what a stray `make server` beside a running
        # `make up` produces, and `errno 48` on its own is not a fix anybody can guess.
        print(f"cannot listen on {host}:{port} — {exc}")
        print("  Something is already serving this port. `make status` says who.")
        print("  If it is your own supervisor: `make down`, or just use the one that is up.")
        raise SystemExit(1) from exc

    # SIGTERM RAISES THE INTERRUPT THE CTRL-C PATH ALREADY HANDLES, so there is one shutdown
    # and not two. Without this the default disposition terminates the process outright — no
    # `server_close()`, no drain — which makes an unhandled SIGTERM strictly WORSE than Ctrl-C
    # for a store that commits four files in sequence.
    #
    # Guarded because `signal.signal` only works on the main thread: T7 constructs
    # `CaptureServer` in-process on an ephemeral port and never calls this function, but a
    # future caller that does should get a working server rather than a ValueError.
    def _term(_signum, _frame):
        raise KeyboardInterrupt

    with contextlib.suppress(ValueError):
        signal.signal(signal.SIGTERM, _term)

    print(f"pkmnscan capture server on http://{host}:{port}")
    print(f"  photos    {root}")
    print(f"  store     {files.inventory_dir()}")
    # WHICH CHECKOUT IS SERVING, printed because the two lines above are absolute paths that
    # differ between trees by one path segment nobody reads at a glance. A worktree's server
    # over a worktree's empty store looks exactly like the real one until a capture lands
    # somewhere that gets deleted with the branch — which is the failure D46 exists for.
    if ports.is_linked_worktree(ports.REPO_ROOT):
        print(f"  WORKTREE  {ports.REPO_ROOT.name} — this is NOT the main checkout's store")
        print(f"            main tree serves :{ports.CAPTURE_BASE_PORT}")
    print("  Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        # CLOSE FIRST, THEN DRAIN. In the other order the drain races arrivals it has no way
        # to refuse and can never reach zero on a busy server; closing the listener is what
        # makes the wait below finite.
        print()
        httpd.server_close()
        waiting = inflight()
        if waiting and drain(DRAIN_SECONDS):
            print(f"stopped — {waiting} request(s) finished first.")
        elif waiting:
            # LOUD, and D88 CHANGED WHAT IS AT RISK HERE rather than removing the risk.
            # `Store.write()` is one SQLite transaction over every table now, so a kill can no
            # longer leave the torn set of four JSON files this comment used to describe — the
            # tables commit or they do not. What a kill still cuts is everything that was never
            # in the transaction and still is not: the photograph, its sidecar, and
            # `codes.jsonl`, all written inside the flock but outside the commit. So the thing
            # to look at is no longer `history.jsonl`, which is a table now and not a file.
            print(f"STOPPED WITHOUT DRAINING — {inflight()} request(s) were cut after "
                  f"{DRAIN_SECONDS:.0f}s. The store's tables commit atomically; what a cut "
                  f"write can leave half-done is a photograph, its sidecar, or codes.jsonl.")
        else:
            print("stopped.")


if __name__ == "__main__":
    serve()
