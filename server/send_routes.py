"""The one press that sends copies to TCGplayer and makes them live, and the checks around it.

THE OWNER'S RULINGS, 2026-09-23 AND 2026-09-24 (`D-one-press-sends-and-makes-live`):

  - Banchi sends the listing file itself. "Download the file instead" stays as a second door.
  - ONE PRESS sends AND makes live. It amends D106 (the push and the publish are two presses).
  - Every send first reads what is live, by itself, and never doubles a quantity. When that
    read cannot run, the send REFUSES, says why, and the screen offers "Try again".
  - After the lag, the live check runs by itself: an open app when the wait ends, a closed app
    on its next visit to Pricing or Home. No server job runs unattended — this module has no
    timer, and `do_live_check` runs only when a request asks.
  - "Take them back" is offered ONLY AFTER a live check has run past the wait for that receipt
    (2026-09-24). Before that, the screen says when it will be safe.

WHAT ONE PRESS DOES, IN ORDER, AND WHERE EACH STEP STOPS (`do_send`):

  0. ONE PRESS AT A TIME in this server (`_press`): a second press while one runs is refused
     by name before it asks TCGplayer anything, so a dropped connection can never invite a
     second send while the first still runs.
  1. Fetch the live export (`pipeline_routes.do_live_export`). A refusal here is the send's
     refusal: nothing was written and nothing was sent.
  2. `reconcile --live --write` over that file, so the store's `live` figures are the ones
     TCGplayer just reported (D87). A non-zero exit refuses the send the same way.
  3. `emit --live-guard <that file> --send-dir <this press's own directory> --send-claim`:
     the listing file, trimmed so TCGplayer never holds more copies than are on hand
     (`pipeline/sendguard.py`), written where no other press can read it, and CLAIMED in the
     store write that counts the copies sent (`store/sendclaims.py`, D174's shape). A second
     press over the same copies is refused there, by name, whatever process it came from.
  4. For a download, stop here: the file is the answer, and its receipt says "written, not
     confirmed at TCGplayer".
  5. Push the file to Staged (`tcg_import.push_to_staged(listing=True)`), then publish that
     upload (`move_to_live`, scoped to it by a constant).

THE COPIES GO BACK ON THE LIST ONLY WHEN NOTHING CAN BE WAITING AT TCGPLAYER — no upload was
opened, or the portal ANSWERED its rollback. Every other failure is UNKNOWN (`_unknown`): a
publish TCGplayer answered 500 to, a publish that never answered, a rollback it refused. An
unknown send keeps its claim, so every later send is refused over its cards, and it is
resolved only by the live check past the wait. The adversarial review of 2026-09-24 found the
round-1 build putting copies back after a publish the portal may have done, which is the
double send this module exists to prevent.

THE RECEIPT IS A FILE BESIDE A COPY OF WHAT WENT, under `inventory/sends/<stamp>/`, written
BEFORE the first byte reaches TCGplayer and advanced at each step (`phase`), so a server that
dies mid-press leaves a receipt that says how far it got. `cli/cmd_reprice.py:
published_recently` reads it, so the lag guard (D106's measurement) covers a listing publish.

NOTHING HERE HAS EVER REACHED TCGPLAYER. Every path is proved against the loopback portal in
`harness/tests/t7_store_and_seams.py`. The first real send is the owner's to authorize.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from http import HTTPStatus
from pathlib import Path
from typing import Dict, Iterator, List, NoReturn, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli import cmd_reprice  # noqa: E402
from pipeline import tcgcsv  # noqa: E402
from server import pipeline_routes  # noqa: E402
from server import tcg_export  # noqa: E402
from server import tcg_import  # noqa: E402
from server.pipeline_routes import PipelineRefusal  # noqa: E402
from store import Store, files, master, sendclaims  # noqa: E402
from store.submissions import proc_start  # noqa: E402

#: Where every send's receipt lives. Named once, in `cli/cmd_reprice.py`, because the lag guard
#: there reads it too and a second spelling would be a second directory.
SENDS = cmd_reprice.SENDS
RECEIPT = "send.json"
#: A send's stamp: UTC to the second, then six hex characters of its own. THE TAIL IS THE FIX
#: for two presses in one second sharing a directory (the 2026-09-24 review); a round-1 stamp
#: without it still reads.
_STAMP = re.compile(r"^[0-9]{8}-[0-9]{6}(-[0-9a-f]{6})?$")
#: How many receipts `GET /pipeline/sends` returns. A screen shows the newest few; the rest
#: stay on disk as the record.
SENDS_SHOWN = 20

KIND_SEND = "send"
KIND_DOWNLOAD = "download"

#: How far PAST the lag the first automatic check is due. At the lag exactly, a check can read
#: an export the publish has not reached yet (the lag is a choice, not a reading — see
#: `cmd_reprice.PUBLISH_LAG_S`), and a copy that simply has not shown would be named missing.
CHECK_MARGIN_S = 2 * 60
#: How long a receipt's same bytes refuse a second push. Inside it the live read cannot see the
#: first push yet, so the digest is the only thing that can; past it, the live read and the
#: double-send guard can, and a legitimate later send of the same rows must not be refused
#: forever (the 2026-09-24 review, S3).
UPLOAD_WINDOW_S = cmd_reprice.PUBLISH_LAG_S + CHECK_MARGIN_S

#: The steps a press records as it goes. `done` is every receipt with an outcome.
PHASE_DECIDING = "deciding"
PHASE_SENDING = "sending"
PHASE_PUBLISHING = "publishing"
PHASE_DONE = "done"
IN_FLIGHT = (PHASE_DECIDING, PHASE_SENDING, PHASE_PUBLISHING)

#: THE MARK-DOWN'S CLAIM IS ITS OWN STAMP WITH THIS PREFIX, so a listing send and a price send
#: share one claims table without sharing a key.
MARKDOWN_CLAIM = "md-"


# ------------------------------------------------------------------ one press at a time


_PRESS = threading.Lock()
_RUNNING: Dict[str, str] = {}


@contextlib.contextmanager
def _press(kind: str) -> Iterator[None]:
    """Hold the server's one press, or refuse by name. Non-blocking: a second press is REFUSED.

    WHY A LOCK AS WELL AS THE STORE CLAIM. The claim is decided inside `emit`, after the live
    read — so without this, a second press would read TCGplayer and run a reconcile before being
    refused. With it, the second press is refused at once, and the refusal says what is running
    and since when. The claim is still the rule that holds across processes and restarts; this
    only stops the second press from getting that far.
    """
    if not _PRESS.acquire(blocking=False):
        since = _RUNNING.get("at", "")
        what = "a price change" if _RUNNING.get("kind") == "markdown" else "a send"
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "send_in_progress",
            f"Banchi is already sending {what} to TCGplayer (started {since}). Nothing was "
            f"sent again; its result shows here when TCGplayer answers.",
        )
    try:
        _RUNNING.clear()
        _RUNNING.update({"kind": kind, "at": _iso(_now())})
        yield
    finally:
        _RUNNING.clear()
        _PRESS.release()


_HOLDER: Dict[str, Optional[str]] = {}


def _holder() -> dict:
    """This server process, as a receipt records it: pid and `ps`'s start time for it."""
    pid = os.getpid()
    if _HOLDER.get("pid") != str(pid):
        _HOLDER["pid"] = str(pid)
        _HOLDER["start"] = proc_start(pid)
    return {"pid": pid, "proc_start": _HOLDER.get("start")}


def _holder_alive(holder: Optional[dict]) -> bool:
    """Is the process a receipt names still running? `store/submissions.py:holder_alive`'s rule,
    over a receipt's `holder` rather than a claim row. An unreadable answer reads LIVE."""
    if not isinstance(holder, dict):
        return False
    pid = holder.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    recorded = holder.get("proc_start")
    if not recorded:
        return True
    actual = proc_start(pid)
    return actual is None or actual == recorded


# ------------------------------------------------------------------------ the receipt


def sends_dir() -> Path:
    return files.inventory_dir() / SENDS


def _new_stamp() -> str:
    """A fresh send's stamp, AND ITS DIRECTORY, made in one step so no other press can take it.

    THE ROUND-1 SHAPE CHECKED THAT A NAME WAS FREE AND MADE THE DIRECTORY LATER, so two presses
    in one second both found the same name free (the 2026-09-24 review). Here the directory is
    created with `exist_ok=False`, which the filesystem answers atomically, and the random tail
    makes a clash a retry rather than a refusal.
    """
    sends_dir().mkdir(parents=True, exist_ok=True)
    base = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    for _ in range(16):
        stamp = f"{base}-{secrets.token_hex(3)}"
        try:
            (sends_dir() / stamp).mkdir(exist_ok=False)
        except FileExistsError:
            continue
        return stamp
    raise PipelineRefusal(
        HTTPStatus.CONFLICT, "send_busy", "Banchi could not name this send. Nothing was sent."
    )


def _open_send(stamp: str) -> Path:
    if not _STAMP.match(stamp or ""):
        raise PipelineRefusal(HTTPStatus.BAD_REQUEST, "stamp_invalid", f"{stamp!r} is not a send.")
    directory = sends_dir() / stamp
    if not (directory / RECEIPT).is_file():
        raise PipelineRefusal(HTTPStatus.NOT_FOUND, "no_such_send", f"No send named {stamp}.")
    return directory


def _read(directory: Path) -> dict:
    return files.read_json(directory / RECEIPT, {}) or {}


def _write(directory: Path, record: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / RECEIPT
    staged = directory / f".{RECEIPT}.{os.getpid()}"
    staged.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(staged, target)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _parse(stamp: Optional[str]) -> Optional[datetime]:
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(str(stamp))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _lag() -> timedelta:
    return timedelta(seconds=cmd_reprice.PUBLISH_LAG_S + CHECK_MARGIN_S)


def _wait_until(record: dict) -> Optional[datetime]:
    """The moment a live check can say what happened to this receipt's copies.

    A RECEIPT THAT RECORDED ITS OWN WAIT is read as written. One whose server died mid-press
    recorded none, so the wait is computed from how far it got: a publish that started at T
    has happened by T plus the transport's own timeout if it happened at all, and the lag runs
    from there. A press that died before it published is given the same wait from its start.
    """
    written = _parse(record.get("check_after"))
    if written is not None:
        return written
    started = _parse(record.get("publish_started_at"))
    if started is not None:
        return started + timedelta(seconds=tcg_export.TIMEOUT_S) + _lag()
    at = _parse(record.get("at"))
    return at + _lag() if at is not None else None


def _checked_past_wait(record: dict) -> bool:
    """Has a live check run for this receipt AFTER its wait? The take-back ruling's test."""
    checked = _parse(record.get("checked_at"))
    wait = _wait_until(record)
    return checked is not None and record.get("check") is not None and (
        wait is None or checked >= wait
    )


def state_of(record: dict, now: Optional[datetime] = None) -> str:
    """One word for where a send stands. The screen draws one sentence per word.

    - `sending`     the press is still running (its server is alive and has no outcome yet).
    - `unknown`     TCGplayer did not say whether the copies went live, or the server died
                    mid-press. The copies are held until a live check past the wait.
    - `failed`      the press was refused and nothing can be waiting at TCGplayer; the copies
                    went back on the list.
    - `taken_back`  the owner took copies back after a check.
    - `written`     a file the owner downloaded, not yet found at TCGplayer.
    - `waiting`     live, and the check has not run: before the wait, or since.
    - `checked`     the check found every copy.
    - `short`       the check ran and some copies were not found.
    """
    if record.get("taken_back_at"):
        return "failed" if record.get("failure") else "taken_back"
    check = record.get("check") or {}
    phase = record.get("phase") or PHASE_DONE
    if phase in IN_FLIGHT and _holder_alive(record.get("holder")) and not record.get("checked_at"):
        return "sending"
    uncertain = bool(record.get("unknown")) or phase in IN_FLIGHT
    if record.get("kind") == KIND_DOWNLOAD and not uncertain:
        if check and check.get("found", 0) >= check.get("expected", 0) > 0:
            return "checked"
        if check and _checked_past_wait(record):
            return "short"
        return "written"
    if uncertain:
        if not _checked_past_wait(record):
            return "unknown"
        return "short" if check.get("found", 0) < check.get("expected", 0) else "checked"
    if not record.get("published_at"):
        return "failed"
    if not record.get("checked_at"):
        return "waiting"
    if check.get("found", 0) < check.get("expected", 0):
        return "short"
    return "checked"


def _due(record: dict, now: datetime) -> bool:
    """Is this receipt one the live check should read now?"""
    state = state_of(record, now)
    if state == "written":
        # A DOWNLOADED FILE IS READ AT MOST ONCE PER LAG. The owner may not have uploaded it
        # yet, and a check on every visit would open a socket to TCGplayer each time.
        last = _parse(record.get("checked_at"))
        wait = _wait_until(record)
        if last is None:
            return wait is None or wait <= now
        return last + _lag() <= now
    if state not in ("waiting", "unknown"):
        return False
    wait = _wait_until(record)
    return wait is None or wait <= now


def _takeable(record: dict) -> Dict[str, int]:
    """SKU -> the copies "Take them back" would return now. Empty until a check past the wait.

    ONLY WHAT THE CHECK DID NOT FIND. A copy the check found is live at TCGplayer, and putting
    it back on the list would send it twice.
    """
    if record.get("taken_back_at") or not _checked_past_wait(record):
        return {}
    out: Dict[str, int] = {}
    for row in (record.get("check") or {}).get("missing") or []:
        gone = int(row.get("sent", 0)) - int(row.get("found", 0))
        if gone > 0:
            out[str(row.get("sku"))] = gone
    return out


def _summary(stamp: str, record: dict, now: datetime, held: frozenset = frozenset()) -> dict:
    state = state_of(record, now)
    pushed = record.get("pushed") or {}
    rows = pushed.get("rows") if pushed.get("rows") is not None else len(record.get("copies") or {})
    accepted = pushed.get("accepted")
    wait = _wait_until(record)
    offer = _takeable(record)
    waiting_to_take = state in ("unknown", "written") and not _checked_past_wait(record)
    return {
        "stamp": stamp,
        "kind": record.get("kind"),
        "state": state,
        "at": record.get("at"),
        "copies": int(record.get("copies_total") or 0),
        "rows": int(rows or 0),
        "published_at": record.get("published_at"),
        "check_after": _iso(wait) if wait is not None else None,
        "checked_at": record.get("checked_at"),
        "check": record.get("check"),
        "trimmed": (record.get("guard") or {}).get("trimmed") or [],
        "trimmed_copies": int((record.get("guard") or {}).get("trimmed_copies") or 0),
        "accepted": accepted,
        # THE ROWS TCGPLAYER TURNED AWAY, from its own count. Never more went live than it
        # accepted, and the screen reads this rather than `copies` for what it took.
        "turned_away": max(0, int(rows or 0) - int(accepted)) if accepted is not None else 0,
        "failure": record.get("failure"),
        "unknown": record.get("unknown"),
        "held": stamp in held,
        "takeable": sum(offer.values()),
        "take_back_after": _iso(wait) if waiting_to_take and wait is not None else None,
        "files": record.get("files") or [],
        "taken_back_at": record.get("taken_back_at"),
    }


def _receipts() -> List[Tuple[str, dict]]:
    """Every receipt, newest first. A directory with no receipt yet is a press still deciding
    or one that was refused before it wrote one, and is skipped."""
    root = sends_dir()
    if not root.is_dir():
        return []
    out = []
    for entry in sorted(root.iterdir(), reverse=True):
        if _STAMP.match(entry.name) and (entry / RECEIPT).is_file():
            out.append((entry.name, _read(entry)))
    return out


def _held_stamps() -> frozenset:
    """The stamps whose claim is still live: a send in flight, or one whose outcome is unknown."""
    return frozenset(claim.stamp for claim in Store().read().send_claims.live())


def _release(stamp: str, by: str) -> None:
    with Store().write() as writable:
        writable.send_claims.release(stamp, by)


# -------------------------------------------------------------------- the gate: live check


def _fetch_live(step: str) -> Tuple[str, Path]:
    """Fetch the live export, or refuse by name. `step` says which press is asking.

    EVERY FAILURE HERE IS THE SAME REFUSAL FROM THE SCREEN'S SIDE — "Banchi could not read
    what is live" — with TCGplayer's own reason carried beside it. The screen offers "Try
    again". A send never goes ahead blind (the owner's ruling).
    """
    try:
        fetched = pipeline_routes.do_live_export()
    except PipelineRefusal as refusal:
        raise PipelineRefusal(
            HTTPStatus.BAD_GATEWAY,
            "live_check_failed",
            f"Banchi could not read what is live at TCGplayer, so nothing was {step}. "
            f"{refusal}",
        ) from None
    name = str(fetched["fetched"])
    path = files.inventory_dir() / pipeline_routes.LIVE_DIR / name
    return name, path


def _reconcile(path: Path, step: str) -> str:
    """`reconcile --live --write`: the store's `live` becomes what TCGplayer just said (D87)."""
    code, console = pipeline_routes._run_sync(
        [str(pipeline_routes.PKMNSCAN), "reconcile", "--live", str(path), "--write"],
        pipeline_routes.STEP_TIMEOUT_S,
    )
    if code != 0:
        last = (console.strip().splitlines() or [""])[-1]
        raise PipelineRefusal(
            HTTPStatus.BAD_GATEWAY,
            "live_check_failed",
            f"Banchi read what is live but could not settle it against the store, so nothing "
            f"was {step}. {last}",
        )
    return console


def _live_quantities(path: Path, step: str) -> Dict[str, int]:
    """SKU -> live copies, or the named refusal when the file is not a live export."""
    from pipeline import sendguard

    try:
        export = tcgcsv.read_export(path)
        return sendguard.live_by_sku(export.rows, export.header)
    except (OSError, ValueError, tcgcsv.MalformedCsv) as exc:
        raise PipelineRefusal(
            HTTPStatus.BAD_GATEWAY,
            "live_check_failed",
            f"Banchi could not read what is live at TCGplayer ({exc}), so nothing was {step}.",
        ) from None


def _live_prices(path: Path) -> Dict[str, str]:
    """SKU -> the marketplace price a live export carries. Read for a mark-down's check."""
    return {
        str(row.get(tcgcsv.SKU_COLUMN) or "").strip(): str(row.get(tcgcsv.PRICE_COLUMN) or "")
        for row in tcgcsv.read_export(path).rows
    }


# --------------------------------------------------------------------------- the write


def _json_line(console: str, key: str) -> Optional[dict]:
    """A command's one JSON line carrying `key`, read from the end. `_extract_rescue_report`'s
    rule: the command prints a machine-readable line, and this is the whole of what reads it."""
    for line in reversed(console.splitlines()):
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get(key), dict):
            return parsed[key]
    return None


def _guard_line(console: str) -> Optional[dict]:
    """`emit --live-guard`'s report."""
    return _json_line(console, "send_guard")


def _copies(path: Path) -> Dict[str, int]:
    """SKU -> Add to Quantity, off the file that was written. The file is the record."""
    out: Dict[str, int] = {}
    for row in tcgcsv.read_export(path).rows:
        sku = str(row.get(tcgcsv.SKU_COLUMN) or "").strip()
        if sku:
            out[sku] = out.get(sku, 0) + tcgcsv.parse_quantity(row.get(tcgcsv.QUANTITY_COLUMN, ""))
    return out


def _names(path: Path) -> Dict[str, str]:
    return {
        str(row.get(tcgcsv.SKU_COLUMN) or "").strip(): str(row.get(tcgcsv.NAME_COLUMN) or "")
        for row in tcgcsv.read_export(path).rows
    }


def _sold_by_sku(skus) -> Dict[str, int]:
    """Copies marked sold, per named SKU, now. The check subtracts the sales made after a send.

    ONE INDEXED READ PER SKU (`Inventory.positions_for_sku`), never a walk of every card: the
    send names its SKUs, and `docs/specs/store-scaling.md` §0 is why a full-table read is not
    free here.
    """
    inventory = Store().read().inventory
    return {
        sku: sum(1 for card in inventory.positions_for_sku(sku) if card.state == master.SOLD)
        for sku in skus
    }


def _take_back(copies: Dict[str, int], stamp: str, by: str) -> int:
    """Put these copies back on the list and release the send's claim. One store write.

    `pushed` is a QUANTITY per SKU (D7 amended), and `emit` raised it by exactly the file's
    `Add to Quantity`. Lowering it by the same figure is the whole undo: `cli/resolve.py:
    _copies_out` reads it, so the next worklist offers these copies again. `bump` floors at 0.
    """
    moved = 0
    with Store().write() as writable:
        for sku, count in copies.items():
            listing = writable.inventory.listings.get(sku)
            if listing is None or count <= 0:
                continue
            before = listing.pushed
            listing.bump(master.PUSHED, -int(count))
            moved += before - listing.pushed
        writable.send_claims.release(stamp, by)
    return moved


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _already_pushed(digest: str, now: Optional[datetime] = None) -> Optional[str]:
    """A send that pushed these exact bytes INSIDE THE UPLOAD WINDOW, and was not undone — or None.

    D100 §2's doubling was one file uploaded twice. Inside the window the live export cannot
    show the first upload yet, so the digest is the only witness; past it the live read and the
    double-send guard can see it, and the same rows sent again a day later are a legitimate send
    (the round-1 rule refused them forever — the 2026-09-24 review, S3).
    """
    moment = now or _now()
    for stamp, record in _receipts():
        if record.get("digest") != digest or record.get("kind") != KIND_SEND:
            continue
        pushed = record.get("pushed")
        if not pushed or record.get("taken_back_at"):
            continue
        when = _parse(pushed.get("pushed_at")) or _parse(record.get("at"))
        if when is None or (moment - when).total_seconds() <= UPLOAD_WINDOW_S:
            return stamp
    return None


def _claim_refusal(console: str, step: str) -> Optional[PipelineRefusal]:
    """`emit`'s claim refusal, turned into the route's, or None when emit refused for another
    reason. Named `send_held` when a conflicting claim belongs to a send whose outcome is
    unknown, `send_in_progress` otherwise."""
    said = _json_line(console, "send_claim")
    if said is None:
        return None
    conflicts = said.get("conflicts") or []
    held = []
    for conflict in conflicts:
        stamp = str(conflict.get("stamp") or "")
        record = _read(sends_dir() / stamp) if _STAMP.match(stamp) else {}
        if record and state_of(record) == "unknown":
            held.append(conflict)
    if held:
        first = held[0]
        return PipelineRefusal(
            HTTPStatus.CONFLICT,
            "send_held",
            f"{len(first.get('skus') or [])} of these cards are in a send whose result "
            f"TCGplayer has not confirmed (started {first.get('started_at')}). They stay out of "
            f"every send until Banchi checks what is live after the wait. Nothing was {step}.",
        )
    if conflicts:
        first = conflicts[0]
        return PipelineRefusal(
            HTTPStatus.CONFLICT,
            "send_in_progress",
            f"Another send (started {first.get('started_at')}) is already sending "
            f"{len(first.get('skus') or [])} of these cards. Nothing was {step}.",
        )
    return PipelineRefusal(
        HTTPStatus.CONFLICT,
        "send_in_progress",
        f"Another send moved {len(said.get('stale') or [])} of these cards while this one was "
        f"deciding. Nothing was {step}; press again to send what is left.",
    )


def do_send(payload: dict) -> dict:
    """`POST /pipeline/send` — read what is live, write the file, send it, make it live.

    `runs` names the runs whose copies go (the worklist's own list). `download: true` stops
    after the write and records a receipt the screen names as "written, not confirmed".
    `split_threshold` is honoured on a download only: a send is one file.
    """
    wanted = payload.get("runs")
    if not isinstance(wanted, list) or not wanted:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST, "runs_required", "Send a non-empty `runs` list."
        )
    if len(wanted) > pipeline_routes.MAX_MERGED_RUNS:
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "too_many_runs",
            f"At most {pipeline_routes.MAX_MERGED_RUNS} runs in one send.",
        )
    download = bool(payload.get("download"))
    if not download and not bool(payload.get("confirm")):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "A send reaches TCGplayer and makes copies live. Send `confirm` once the owner has "
            "pressed it; nothing was sent.",
        )
    directories = [pipeline_routes._open_run(str(name)) for name in wanted]
    with _press("listing"):
        return _send(payload, directories, download)


def _send(payload: dict, directories: Sequence[Path], download: bool) -> dict:
    step = "written" if download else "sent"

    # 1-2. THE GATE. Refuses before anything is written.
    live_name, live_path = _fetch_live(step)
    _reconcile(live_path, step)
    live_before = _live_quantities(live_path, step)

    # 3. THE WRITE, INTO THIS PRESS'S OWN DIRECTORY, BEHIND THE GUARD AND THE CLAIM.
    stamp = _new_stamp()
    directory = sends_dir() / stamp
    record = {
        "stamp": stamp,
        "kind": KIND_DOWNLOAD if download else KIND_SEND,
        "at": _iso(_now()),
        "runs": [d.name for d in directories],
        "run": sorted(d.name for d in directories)[-1],
        "phase": PHASE_DECIDING,
        "holder": _holder(),
    }
    # WRITTEN BEFORE `emit` RUNS, so a server that dies after emit counted the copies leaves a
    # receipt naming them rather than a claim nobody can see.
    _write(directory, record)
    argv = [str(pipeline_routes.PKMNSCAN), "emit", *[str(d) for d in directories]]
    argv += ["--live-guard", str(live_path), "--send-dir", str(directory)]
    argv += ["--send-claim", stamp, "--claim-holder", str(os.getpid())]
    if download and payload.get("split_threshold"):
        argv.append("--split-threshold")
    argv += pipeline_routes._quantity_flags(payload)
    code, console = pipeline_routes._run_sync(argv, pipeline_routes.STEP_TIMEOUT_S)
    guard = _guard_line(console) or {}
    claim = Store().read().send_claims.get(stamp)
    written = sorted(directory.glob("import*.csv"))

    if claim is None or not written:
        # NOTHING WAS COUNTED SENT: `emit` refused, or wrote nothing new. The press's own
        # directory is its scratch and goes with it; no receipt is left for a press that sent
        # nothing.
        shutil.rmtree(directory, ignore_errors=True)
        refused = _claim_refusal(console, step)
        if refused is not None:
            raise refused
        trimmed = guard.get("trimmed") or []
        if code == 0 or trimmed or "nothing to write" in console or "nothing new" in console:
            held = f" {len(trimmed)} card{'s' if len(trimmed) != 1 else ''} held back." if trimmed else ""
            raise PipelineRefusal(
                HTTPStatus.CONFLICT,
                "nothing_to_send",
                f"Every copy on this list is already at TCGplayer or held back, so nothing "
                f"was {step}.{held}",
            )
        last = (console.strip().splitlines() or [""])[-1]
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "write_refused",
            f"The file was not written, so nothing was {step}. {last}",
        )

    kept = [path.name for path in written]
    copies: Dict[str, int] = {}
    names: Dict[str, str] = {}
    for path in written:
        for sku, count in _copies(path).items():
            copies[sku] = copies.get(sku, 0) + count
        names.update(_names(path))
    record.update(
        {
            "files": kept,
            "copies": copies,
            "copies_total": sum(copies.values()),
            "names": names,
            "live_export": live_name,
            "live_before": {sku: live_before.get(sku, 0) for sku in copies},
            "sold_before": _sold_by_sku(copies),
            "guard": guard,
            "pushed": None,
            "published_at": None,
            "check_after": None,
            "checked_at": None,
            "check": None,
            "taken_back_at": None,
            "failure": None,
            "unknown": None,
        }
    )
    if download:
        # A DOWNLOAD HOLDS NOTHING IN FLIGHT: the file is the owner's to upload, and the live
        # check past the wait is what confirms it. The claim goes; `pushed` keeps the copies
        # off the next file until the check or a take-back says otherwise.
        record["phase"] = PHASE_DONE
        record["check_after"] = _iso(_now() + _lag())
        _write(directory, record)
        _release(stamp, "written")
        return {"send": _summary(stamp, record, _now()), "console": console}

    record["phase"] = PHASE_SENDING
    _write(directory, record)
    try:
        return _push_and_publish(directory, record, console)
    except PipelineRefusal:
        raise
    except Exception as caught:  # noqa: BLE001 — anything else mid-press is UNKNOWN
        # AN ERROR THIS MODULE DID NOT FORESEE, AFTER THE COPIES WERE COUNTED. Whatever it is,
        # the one thing that must not happen is a take-back on a guess: the upload may exist.
        _unknown(directory, record, "error", None, None, f"{type(caught).__name__}")


def _push_and_publish(directory: Path, record: dict, console: str) -> dict:
    """Steps 5 and on: push, publish, and name what happened. Every exit writes the receipt."""
    stamp = record["stamp"]
    if len(record["files"]) != 1:
        _fail(directory, record, "write_split", "A send is one file, and this press wrote "
              f"{len(record['files'])}. Nothing was sent; the copies are back on the list.",
              HTTPStatus.CONFLICT)
    pushed_file = directory / record["files"][0]
    record["digest"] = _digest(pushed_file)
    earlier = _already_pushed(record["digest"])
    if earlier is not None:
        _fail(
            directory,
            record,
            "already_sent",
            f"These exact rows went to TCGplayer in the send of {earlier}, and TCGplayer cannot "
            f"show them yet. Sending them again would double every copy, so nothing was sent; "
            f"the copies are back on the list.",
            HTTPStatus.CONFLICT,
        )
    rows = tcg_import.rows_from_csv(pushed_file.read_text(encoding="utf-8"))
    try:
        upload = tcg_import.push_to_staged(rows, filename=record["files"][0], listing=True)
    except tcg_import.PushFailed as failed:
        if failed.upload_id is None or failed.rolled_back:
            rolled = " The upload was rolled back." if failed.rolled_back else ""
            _fail(directory, record, failed.code,
                  f"{failed.message}{rolled} Nothing is live; the copies are back on the list.")
        _unknown(directory, record, "push", failed.upload_id, False, failed.message)
    except tcg_import.FetchRefusal as refusal:
        # `_check`'s refusals: the file was turned away before a transaction existed.
        _fail(directory, record, refusal.code,
              f"{refusal.message} The copies are back on the list.")
    record["pushed"] = dict(upload.as_dict(), pushed_at=_iso(_now()))
    if int(upload.accepted or 0) <= 0:
        # TCGPLAYER TOOK NONE OF THE ROWS. There is nothing to publish; clear the upload.
        _rollback_then(directory, record, str(upload.upload_id), "tcg_nothing_accepted",
                       "TCGplayer took none of the rows in this send.")
    record["phase"] = PHASE_PUBLISHING
    record["publish_started_at"] = _iso(_now())
    _write(directory, record)
    try:
        answer = tcg_import.move_to_live(str(upload.upload_id))
    except tcg_import.FetchRefusal as refusal:
        if not tcg_import.unclear(refusal):
            _rollback_then(directory, record, str(upload.upload_id), refusal.code, refusal.message)
        # AN UNCLEAR PUBLISH: TCGplayer may have made these live. The rollback is still asked
        # for — if the upload was not published it stops it waiting in Staged — but its answer
        # cannot make the outcome known, so the copies stay held either way.
        rolled = _try_rollback(str(upload.upload_id))
        _unknown(directory, record, "publish", str(upload.upload_id), rolled, refusal.message)
    if isinstance(answer, dict) and answer.get("Success") is False:
        _rollback_then(directory, record, str(upload.upload_id), "tcg_publish_refused",
                       "TCGplayer answered that it did not make the upload live.")
    published = _now()
    record["published_at"] = _iso(published)
    record["publish_result"] = answer
    record["check_after"] = _iso(published + _lag())
    record["phase"] = PHASE_DONE
    _write(directory, record)
    _release(stamp, "published")
    return {"send": _summary(stamp, record, _now()), "console": console}


def _try_rollback(upload_id: str) -> bool:
    """Ask TCGplayer to roll one upload back. True only when it answered."""
    try:
        tcg_import.rollback(upload_id)
    except tcg_import.FetchRefusal:
        return False
    return True


def _rollback_then(
    directory: Path, record: dict, upload_id: str, code: str, message: str
) -> NoReturn:
    """A CLEAR refusal after an upload exists: roll it back, and only a confirmed rollback puts
    the copies back on the list. A refused rollback leaves the upload waiting in Staged."""
    if _try_rollback(upload_id):
        _fail(directory, record, code,
              f"{message} The upload was rolled back. Nothing is live; the copies are back on "
              f"the list.")
    _unknown(directory, record, "rollback", upload_id, False, message)


def _fail(
    directory: Path,
    record: dict,
    code: str,
    message: str,
    status: HTTPStatus = HTTPStatus.BAD_GATEWAY,
) -> NoReturn:
    """Record a refusal NOTHING AT TCGPLAYER CAN OUTLIVE, put the copies back, and raise it.

    ONLY TWO CALLERS' CASES REACH HERE: no upload was opened, or TCGplayer answered the
    rollback. Everything else is `_unknown`. The copies go back and the claim is released in
    one store write, before the receipt says so — a crash between the two leaves a receipt that
    still says "not taken back" over copies that are, the safe direction: the next send's
    guard reads TCGplayer, not this receipt.
    """
    _take_back(record.get("copies") or {}, str(record.get("stamp")), "failed")
    record["failure"] = {"code": code, "message": message}
    record["taken_back_at"] = _iso(_now())
    record["phase"] = PHASE_DONE
    _write(directory, record)
    raise PipelineRefusal(status, code, message)


def _unknown(
    directory: Path,
    record: dict,
    stage: str,
    upload_id: Optional[str],
    rolled_back: Optional[bool],
    cause: str,
) -> NoReturn:
    """Record that TCGplayer did not say what happened, HOLD the copies, and raise it.

    THE COPIES ARE NOT TAKEN BACK and the claim is NOT released: they may be live, or waiting
    in Staged where a person can publish them by hand. The wait runs from NOW, because whatever
    TCGplayer did, it did before now. The live check past the wait is what resolves it.
    """
    now = _now()
    # THE UPLOAD MAY STILL WAIT IN STAGED whenever one was opened and its rollback was not
    # answered — after an unclear publish too, if the publish did not in fact happen.
    waits = bool(upload_id) and not rolled_back
    record["unknown"] = {
        "stage": stage,
        "upload_id": upload_id,
        "rolled_back": rolled_back,
        "staged": waits,
        "file": (record.get("files") or [None])[0],
        "cause": cause,
        "at": _iso(now),
    }
    record["check_after"] = _iso(now + _lag())
    record["phase"] = PHASE_DONE
    _write(directory, record)
    wait = clock(now + _lag())
    staged = (
        f" The upload of {record['unknown']['file']} may still wait in TCGplayer's Staged "
        f"list: do not publish it there."
        if waits
        else ""
    )
    if stage == "publish" or stage == "error":
        first = "TCGplayer did not say whether these copies went live."
    else:
        first = "TCGplayer did not finish this send."
    message = (
        f"{first}{staged} Do not send them again: Banchi checks what is live after {wait} and "
        f"says what happened."
    )
    raise PipelineRefusal(HTTPStatus.BAD_GATEWAY, "send_unknown", message)


def clock(moment: datetime) -> str:
    """UTC, to the minute, for a refusal's sentence. The screen draws its own local time."""
    return moment.strftime("%H:%M UTC")


# ------------------------------------------------------------------ the status and the undo


def do_sends() -> dict:
    """`GET /pipeline/sends` — the newest receipts, what is unconfirmed, and when to check.

    `due` is the one bit the screen's timer and its visit check both read: true when a
    receipt is waiting and its wait has passed. `check_at` is the earliest moment one will be.
    """
    now = _now()
    receipts = _receipts()
    held = _held_stamps()
    shown = [_summary(stamp, record, now, held) for stamp, record in receipts[:SENDS_SHOWN]]
    unconfirmed = [
        (stamp, record)
        for stamp, record in receipts
        if state_of(record, now) in ("written", "unknown")
    ]
    pending = [
        _wait_until(record)
        for _, record in receipts
        if state_of(record, now) in ("waiting", "unknown", "written")
    ]
    pending += _markdown_waits()
    check_at = min((moment for moment in pending if moment is not None and moment > now), default=None)
    return {
        "sends": shown,
        "unconfirmed": {
            "copies": sum(int(record.get("copies_total") or 0) for _, record in unconfirmed),
            "stamps": [stamp for stamp, _ in unconfirmed],
        },
        "due": any(_due(record, now) for _, record in receipts) or _markdown_due(now),
        "check_at": _iso(check_at) if check_at else None,
        "now": _iso(now),
    }


def do_send_file(stamp: str, name: str) -> bytes:
    """`GET /pipeline/sends/<stamp>/file?name=<f>` — one file a send wrote, and only those.

    SHAPE, THEN MEMBERSHIP (`do_markdown_file`'s rule): the name must be one the receipt lists,
    so a request can never name a path.
    """
    directory = _open_send(stamp)
    if name not in (_read(directory).get("files") or []):
        raise PipelineRefusal(
            HTTPStatus.NOT_FOUND, "no_such_file", f"Send {stamp} wrote no file called {name!r}."
        )
    return (directory / name).read_bytes()


def do_take_back(stamp: str, payload: dict) -> dict:
    """`POST /pipeline/sends/<stamp>/take-back` — the copies a check did not find, back on the list.

    THE OWNER'S RULING, 2026-09-24: offered ONLY AFTER a live check has run past the wait for
    this receipt. Before that, a copy that has not shown may simply be late, and putting it
    back on the list would send it twice. What goes back is exactly what the check did not
    find, per SKU; a copy it found is live and stays counted.
    """
    directory = _open_send(stamp)
    record = _read(directory)
    offer = _takeable(record)
    if not offer:
        if not record.get("taken_back_at") and not _checked_past_wait(record):
            wait = _wait_until(record)
            raise PipelineRefusal(
                HTTPStatus.CONFLICT,
                "take_back_not_yet",
                f"These copies can be taken back once Banchi has checked what is live after "
                f"{clock(wait) if wait else 'the wait'}. Nothing changed.",
            )
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "not_takeable",
            "Every copy of this send was found at TCGplayer, or was already taken back. "
            "Nothing changed.",
        )
    if not bool(payload.get("confirm")):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "Taking copies back changes what the next send offers. Send `confirm`.",
        )
    moved = _take_back(offer, stamp, "taken_back")
    record["taken_back_at"] = _iso(_now())
    record["taken_back"] = offer
    _write(directory, record)
    return {"send": _summary(stamp, record, _now(), _held_stamps()), "moved": moved}


# ----------------------------------------------------------------------- the live check


def _copies_of(stamp: str, record: dict, claims) -> Dict[str, int]:
    """The copies a receipt sent: its own record, or — for a press that died after `emit`
    counted them and before the receipt named them — the claim `emit` wrote."""
    copies = record.get("copies")
    if copies:
        return {sku: int(n) for sku, n in copies.items()}
    claim = claims.get(stamp)
    return dict(claim.skus) if claim is not None else {}


def do_live_check(payload: dict) -> dict:
    """`POST /pipeline/live-check` — read what is live, settle the store, confirm the sends.

    IT RUNS ONLY WHEN ASKED. The screen asks when a receipt is due: its timer when the wait
    ends while the app is open, or its first visit to Pricing or Home after that. `force: true`
    is the manual "Check what is live" press, which runs even with nothing due.

    A SEND STILL INSIDE ITS WAIT IS NOT JUDGED BY A FORCED CHECK. Export From Live serves old
    figures for a while after a publish (D106, measured), so reading it early would call a copy
    missing that simply has not shown yet. `reconcile --live` holds those SKUs back itself.

    ONE RISE IS NEVER TWO CONFIRMATIONS (the 2026-09-24 review, S3). Two receipts that sent the
    same SKU from the same baseline used to each count the whole rise. Now the rise per SKU is
    measured once, from the OLDEST due receipt's baseline, and handed out oldest first: the
    older send is credited first, and the newer one only with what is left.
    """
    now = _now()
    receipts = _receipts()
    due = [(stamp, record) for stamp, record in receipts if _due(record, now)]
    due.reverse()  # OLDEST FIRST — `_receipts` is newest first.
    markdowns = _markdown_due_list(now)
    force = bool(payload.get("force"))
    if not due and not markdowns and not force:
        status = do_sends()
        return {"ran": False, "check_at": status["check_at"], "checked": []}

    name, path = _fetch_live("checked")
    console = _reconcile(path, "checked")
    live_now = _live_quantities(path, "checked")
    claims = Store().read().send_claims
    sent_by = {stamp: _copies_of(stamp, record, claims) for stamp, record in due}
    sold_now = _sold_by_sku({sku for copies in sent_by.values() for sku in copies})

    # THE POOL: per SKU, the rise since the oldest due baseline, plus what sold since then.
    pool: Dict[str, int] = {}
    for stamp, record in due:
        before = record.get("live_before") or {}
        sold_before = record.get("sold_before") or {}
        for sku in sent_by[stamp]:
            if sku in pool:
                continue
            sold_since = max(0, sold_now.get(sku, 0) - int(sold_before.get(sku, 0)))
            pool[sku] = max(0, live_now.get(sku, 0) - int(before.get(sku, 0)) + sold_since)

    checked = []
    for stamp, record in due:
        copies = sent_by[stamp]
        missing = []
        found_total = 0
        for sku, sent in copies.items():
            found = max(0, min(int(sent), pool.get(sku, 0)))
            pool[sku] = pool.get(sku, 0) - found
            found_total += found
            if found < sent:
                missing.append(
                    {
                        "sku": sku,
                        "name": (record.get("names") or {}).get(sku, ""),
                        "sent": int(sent),
                        "found": found,
                    }
                )
        record["check"] = {
            "export": name,
            "found": found_total,
            "expected": sum(int(n) for n in copies.values()),
            "missing": missing,
        }
        record.setdefault("copies", copies)
        record["copies_total"] = record.get("copies_total") or sum(copies.values())
        record["checked_at"] = _iso(now)
        _write(sends_dir() / stamp, record)
        # A CHECK PAST THE WAIT RESOLVES A HOLD: what is live is now known, and what is not can
        # be taken back. The claim goes whether the copies were found or not.
        if _checked_past_wait(record):
            _release(stamp, "checked")
        checked.append(_summary(stamp, record, now, _held_stamps()))

    for stamp in markdowns:
        _resolve_markdown(stamp, path, now)

    return {"ran": True, "export": name, "checked": checked, "console": console}


# ------------------------------------------------------------------ the mark-down, one press


def _markdown_skus(directory: Path) -> List[str]:
    return sorted(
        {
            str(row.get(tcgcsv.SKU_COLUMN) or "").strip()
            for row in tcgcsv.read_export(directory / cmd_reprice.IMPORT).rows
        }
        - {""}
    )


def _markdown_unknown(record: Optional[dict]) -> bool:
    return bool(record and record.get("unknown") and not record.get("published_at")
                and not (record.get("unknown") or {}).get("resolved"))


def do_markdown_send(stamp: str, payload: dict) -> dict:
    """`POST /pipeline/markdowns/<stamp>/send` — read what is live, push, publish. One press.

    THE SAME RULINGS AS `do_send`, OVER A FILE THAT ONLY CHANGES PRICES. D100's zero rule on
    the transport is untouched (`tcg_import._check` with `listing=False`), so this file still
    cannot move a copy. What this press adds is the live read in front of it, the publish
    behind it, and — since the 2026-09-24 review — the same one-press lock and the same store
    claim a listing send takes, so two presses over one mark-down push it once.

    A CLEARLY REFUSED PUBLISH ROLLS THE UPLOAD BACK. An UNCLEAR one (500, no answer) keeps the
    receipt with its upload id and holds the SKUs until the live check past the wait compares
    TCGplayer's prices with the file's. There is no "Put the old prices back" (the owner's
    ruling): the way a live price changes again is another mark-down.
    """
    directory = pipeline_routes._open_markdown(stamp)
    if not (directory / cmd_reprice.IMPORT).is_file():
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "no_import_file",
            "This mark-down has no file to send yet. Check the prices first; nothing was sent.",
        )
    if not bool(payload.get("confirm")):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "A send changes what buyers pay. Send `confirm` once the owner has pressed it; "
            "nothing was sent.",
        )
    with _press("markdown"):
        return _markdown_send(stamp, directory)


def _markdown_send(stamp: str, directory: Path) -> dict:
    record = pipeline_routes._read_push(directory)
    if record is not None and record.get("published_at"):
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "already_published",
            f"These prices went live at {record['published_at']}. Nothing was sent.",
        )
    if _markdown_unknown(record):
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "send_held",
            "TCGplayer has not confirmed this mark-down's last send. Banchi checks what is live "
            "after the wait and says what happened; nothing was sent again.",
        )
    if record is not None and (record.get("unknown") or {}).get("resolved"):
        record = None  # A RESOLVED, NOT-LIVE UPLOAD: this press starts a fresh one.
    claim = f"{MARKDOWN_CLAIM}{stamp}"
    skus = _markdown_skus(directory)
    with Store().write() as writable:
        conflicts = writable.send_claims.overlap(skus, excluding=claim)
        if not conflicts:
            writable.send_claims.claim(
                claim, sendclaims.KIND_MARKDOWN, {sku: 0 for sku in skus}, pid=os.getpid()
            )
    if conflicts:
        other, shared = conflicts[0]
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "send_in_progress",
            f"Another send (started {other.started_at}) holds {len(shared)} of these cards. "
            f"Nothing was sent.",
        )
    try:
        _, live_path = _fetch_live("sent")
        _reconcile(live_path, "sent")
    except PipelineRefusal:
        _release(claim, "failed")
        raise
    if record is None:
        rows = tcg_import.rows_from_csv(
            (directory / cmd_reprice.IMPORT).read_text(encoding="utf-8")
        )
        try:
            upload = tcg_import.push_to_staged(rows, filename=cmd_reprice.IMPORT)
        except tcg_import.PushFailed as failed:
            if failed.upload_id is None or failed.rolled_back:
                _release(claim, "failed")
                raise PipelineRefusal(HTTPStatus.BAD_GATEWAY, failed.code, failed.message) from None
            _markdown_hold(directory, {"upload_id": failed.upload_id}, "push", False, failed.message)
        except tcg_import.FetchRefusal as refusal:
            _release(claim, "failed")
            raise PipelineRefusal(HTTPStatus.BAD_GATEWAY, refusal.code, refusal.message) from None
        pipeline_routes._record_push(directory, upload)
        record = pipeline_routes._read_push(directory) or {}
    upload_id = str(record["upload_id"])
    try:
        answer = tcg_import.move_to_live(upload_id)
    except tcg_import.FetchRefusal as refusal:
        if not tcg_import.unclear(refusal):
            if _try_rollback(upload_id):
                (directory / pipeline_routes.PUSH_RECORD).unlink(missing_ok=True)
                _release(claim, "failed")
                raise PipelineRefusal(
                    HTTPStatus.BAD_GATEWAY,
                    refusal.code,
                    f"{refusal.message} The upload was rolled back, so no price changed.",
                ) from None
            _markdown_hold(directory, record, "rollback", False, refusal.message)
        _markdown_hold(directory, record, "publish", _try_rollback(upload_id), refusal.message)
    record["published_at"] = pipeline_routes._now_iso()
    record["result"] = answer
    pipeline_routes._write_push(directory, record)
    _release(claim, "published")
    return {"published": record, "stamp": stamp}


def _markdown_hold(
    directory: Path, record: dict, stage: str, rolled_back: Optional[bool], cause: str
) -> NoReturn:
    """A mark-down whose outcome is unknown: keep its receipt, hold its SKUs, and raise."""
    now = _now()
    record = dict(record)
    record.setdefault("published_at", None)
    record["unknown"] = {
        "stage": stage,
        "upload_id": record.get("upload_id"),
        "rolled_back": rolled_back,
        "cause": cause,
        "at": _iso(now),
    }
    record["check_after"] = _iso(now + _lag())
    pipeline_routes._write_push(directory, record)
    raise PipelineRefusal(
        HTTPStatus.BAD_GATEWAY,
        "send_unknown",
        f"TCGplayer did not say whether these prices went live. Do not send them again: Banchi "
        f"checks what is live after {clock(now + _lag())} and says what happened.",
    )


def _markdown_records() -> List[Tuple[str, Path, dict]]:
    out = []
    for stamp in pipeline_routes._stamps():
        directory = pipeline_routes._markdowns_dir() / stamp
        record = pipeline_routes._read_push(directory)
        if _markdown_unknown(record):
            out.append((stamp, directory, record))
    return out


def _markdown_waits() -> List[Optional[datetime]]:
    return [_parse(record.get("check_after")) for _, _, record in _markdown_records()]


def _markdown_due_list(now: datetime) -> List[str]:
    return [
        stamp
        for stamp, _, record in _markdown_records()
        if (_parse(record.get("check_after")) or now) <= now
    ]


def _markdown_due(now: datetime) -> bool:
    return bool(_markdown_due_list(now))


def _price(text: str) -> Optional[Decimal]:
    try:
        return Decimal(str(text).strip().lstrip("$"))
    except (InvalidOperation, ValueError):
        return None


def _resolve_markdown(stamp: str, live_path: Path, now: datetime) -> None:
    """A held mark-down, past its wait: did TCGplayer's prices become the file's?

    ALL MATCH: it went live, and the receipt says so. ANY DIFFERS: it did not, and the receipt
    is marked resolved so the next press starts a fresh upload. Either way the hold goes.
    """
    directory = pipeline_routes._markdowns_dir() / stamp
    record = pipeline_routes._read_push(directory) or {}
    wanted = {
        str(row.get(tcgcsv.SKU_COLUMN) or "").strip(): _price(row.get(tcgcsv.PRICE_COLUMN) or "")
        for row in tcgcsv.read_export(directory / cmd_reprice.IMPORT).rows
    }
    live = _live_prices(live_path)
    matched = all(_price(live.get(sku, "")) == price for sku, price in wanted.items() if sku)
    if matched:
        record["published_at"] = _iso(now)
    unknown = dict(record.get("unknown") or {})
    unknown["resolved"] = "live" if matched else "not_live"
    unknown["checked_at"] = _iso(now)
    record["unknown"] = unknown
    pipeline_routes._write_push(directory, record)
    _release(f"{MARKDOWN_CLAIM}{stamp}", "checked")
