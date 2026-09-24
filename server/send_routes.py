"""The one press that sends copies to TCGplayer and makes them live, and the checks around it.

THE OWNER'S RULINGS, 2026-09-23 (`D-one-press-sends-and-makes-live`):

  - Banchi sends the listing file itself. "Download the file instead" stays as a second door.
  - ONE PRESS sends AND makes live. It amends D106 (the push and the publish are two presses).
  - Every send first reads what is live, by itself, and never doubles a quantity. When that
    read cannot run, the send REFUSES, says why, and the screen offers "Try again".
  - After the lag, the live check runs by itself: an open app when the wait ends, a closed app
    on its next visit to Pricing or Home. No server job runs unattended — this module has no
    timer, and `do_live_check` runs only when a request asks.
  - Copies in a file that was written and never confirmed are named, with "Take them back".

WHAT ONE PRESS DOES, IN ORDER, AND WHERE EACH STEP STOPS (`do_send`):

  1. Fetch the live export (`pipeline_routes.do_live_export`). A refusal here is the send's
     refusal: nothing was written and nothing was sent.
  2. `reconcile --live --write` over that file, so the store's `live` figures are the ones
     TCGplayer just reported (D87). A non-zero exit refuses the send the same way.
  3. `emit --live-guard <that file>`: the listing file, with every row trimmed so TCGplayer
     never holds more copies than are on hand (`pipeline/sendguard.py`). A send the guard
     trims to nothing is refused, and the refusal names the trims.
  4. For a download, stop here: the file is the answer, and its receipt says "written, not
     confirmed at TCGplayer".
  5. Push the file to Staged (`tcg_import.push_to_staged(listing=True)`), then publish that
     upload (`move_to_live`, scoped to it by a constant). If either fails, the upload is rolled
     back and the copies go back on the list, so a copy is never marked sent when it was not.

THE RECEIPT IS A FILE BESIDE A COPY OF WHAT WENT, under `inventory/sends/<stamp>/`, the shape
`inventory/markdowns/<stamp>/push.json` already has. `cli/cmd_reprice.py:published_recently`
reads both, so the lag guard (D106's measurement) covers a listing publish too.

NOTHING HERE HAS EVER REACHED TCGPLAYER. Every path is proved against the loopback portal in
`harness/tests/t7_store_and_seams.py`. The first real send is the owner's to authorize.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, NoReturn, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli import cmd_reprice  # noqa: E402
from pipeline import tcgcsv  # noqa: E402
from server import pipeline_routes  # noqa: E402
from server import tcg_import  # noqa: E402
from server.pipeline_routes import PipelineRefusal  # noqa: E402
from store import Store, files, master  # noqa: E402

#: Where every send's receipt lives. Named once, in `cli/cmd_reprice.py`, because the lag guard
#: there reads it too and a second spelling would be a second directory.
SENDS = cmd_reprice.SENDS
RECEIPT = "send.json"
_STAMP = re.compile(r"^[0-9]{8}-[0-9]{6}$")
#: How many receipts `GET /pipeline/sends` returns. A screen shows the newest few; the rest
#: stay on disk as the record.
SENDS_SHOWN = 20

KIND_SEND = "send"
KIND_DOWNLOAD = "download"


# ------------------------------------------------------------------------ the receipt


def sends_dir() -> Path:
    return files.inventory_dir() / SENDS


def _new_stamp() -> str:
    """UTC to the second, the markdown directory's own shape. A clash waits one name over."""
    base = datetime.now(timezone.utc)
    for offset in range(0, 60):
        stamp = (base + timedelta(seconds=offset)).strftime("%Y%m%d-%H%M%S")
        if not (sends_dir() / stamp).exists():
            return stamp
    raise PipelineRefusal(
        HTTPStatus.CONFLICT,
        "send_busy",
        "Sixty sends in one minute is not a press. Nothing was sent.",
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
    (directory / RECEIPT).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


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


def state_of(record: dict, now: Optional[datetime] = None) -> str:
    """One word for where a send stands. The screen draws one sentence per word.

    - `taken_back`  the copies went back on the list.
    - `failed`      the press was refused after the file was written; the copies went back.
    - `written`     a file the owner downloaded, not yet found at TCGplayer.
    - `waiting`     live, and the check has not run: before the lag, or since.
    - `checked`     the check found every copy.
    - `short`       the check ran and some copies were not found.
    """
    if record.get("taken_back_at"):
        return "failed" if record.get("failure") else "taken_back"
    check = record.get("check") or {}
    if record.get("kind") == KIND_DOWNLOAD:
        if check and check.get("found", 0) >= check.get("expected", 0) > 0:
            return "checked"
        return "written"
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
        last = _parse(record.get("checked_at")) or _parse(record.get("at"))
        lag = timedelta(seconds=cmd_reprice.PUBLISH_LAG_S)
        return last is None or last + lag <= now
    if state != "waiting":
        return False
    after = _parse(record.get("check_after"))
    return after is None or after <= now


def _summary(stamp: str, record: dict, now: datetime) -> dict:
    return {
        "stamp": stamp,
        "kind": record.get("kind"),
        "state": state_of(record, now),
        "at": record.get("at"),
        "copies": int(record.get("copies_total") or 0),
        "rows": len(record.get("copies") or {}),
        "published_at": record.get("published_at"),
        "check_after": record.get("check_after"),
        "checked_at": record.get("checked_at"),
        "check": record.get("check"),
        "trimmed": (record.get("guard") or {}).get("trimmed") or [],
        "trimmed_copies": int((record.get("guard") or {}).get("trimmed_copies") or 0),
        "accepted": (record.get("pushed") or {}).get("accepted"),
        "failure": record.get("failure"),
        "files": record.get("files") or [],
        "taken_back_at": record.get("taken_back_at"),
    }


def _receipts() -> List[Tuple[str, dict]]:
    root = sends_dir()
    if not root.is_dir():
        return []
    out = []
    for entry in sorted(root.iterdir(), reverse=True):
        if _STAMP.match(entry.name) and (entry / RECEIPT).is_file():
            out.append((entry.name, _read(entry)))
    return out


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


def _live_quantities(path: Path) -> Dict[str, int]:
    from pipeline import sendguard

    return sendguard.live_by_sku(tcgcsv.read_export(path).rows)


# --------------------------------------------------------------------------- the write


def _import_files(directories: Sequence[Path]) -> Dict[str, Tuple[int, int]]:
    """Every import CSV in these run directories, by path, with (mtime_ns, size)."""
    seen = {}
    for directory in directories:
        for entry in directory.glob("import*.csv"):
            stat = entry.stat()
            seen[str(entry)] = (stat.st_mtime_ns, stat.st_size)
    return seen


def _guard_line(console: str) -> Optional[dict]:
    """`emit --live-guard`'s one JSON line, read from the end. `_extract_rescue_report`'s
    rule: the command prints a machine-readable line, and this is the whole of what reads it."""
    for line in reversed(console.splitlines()):
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("send_guard"), dict):
            return parsed["send_guard"]
    return None


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


def _take_back(copies: Dict[str, int]) -> int:
    """Put these copies back on the list: `pushed` down by what the file added, per SKU.

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
    return moved


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _already_pushed(digest: str) -> Optional[str]:
    """A send whose pushed file had these exact bytes, and was not undone — or None.

    D100 §2's doubling was one file uploaded twice. The press keeps a receipt, so it can refuse
    the second upload of the same bytes, which the hand path never could.
    """
    for stamp, record in _receipts():
        if record.get("digest") != digest or record.get("kind") != KIND_SEND:
            continue
        if record.get("pushed") and not record.get("taken_back_at"):
            return stamp
    return None


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
    step = "written" if download else "sent"

    # 1-2. THE GATE. Refuses before anything is written.
    live_name, live_path = _fetch_live(step)
    _reconcile(live_path, step)
    live_before = _live_quantities(live_path)

    # 3. THE WRITE, BEHIND THE GUARD.
    before = _import_files(directories)
    argv = [str(pipeline_routes.PKMNSCAN), "emit", *[str(d) for d in directories]]
    argv += ["--live-guard", str(live_path)]
    if download and payload.get("split_threshold"):
        argv.append("--split-threshold")
    argv += pipeline_routes._quantity_flags(payload)
    code, console = pipeline_routes._run_sync(argv, pipeline_routes.STEP_TIMEOUT_S)
    guard = _guard_line(console) or {}
    after = _import_files(directories)
    written = sorted(path for path, stamp in after.items() if before.get(path) != stamp)

    if code != 0 or not written:
        trimmed = guard.get("trimmed") or []
        # AN EMPTY SEND: `emit` exited 0 having written nothing new (D54), or said so in its
        # own words on the merged path, or the guard trimmed every row.
        if not written and (code == 0 or trimmed or "nothing to write" in console):
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

    stamp = _new_stamp()
    directory = sends_dir() / stamp
    directory.mkdir(parents=True, exist_ok=False)
    kept = []
    copies: Dict[str, int] = {}
    names: Dict[str, str] = {}
    for source in written:
        target = directory / Path(source).name
        target.write_bytes(Path(source).read_bytes())
        kept.append(target.name)
        for sku, count in _copies(target).items():
            copies[sku] = copies.get(sku, 0) + count
        names.update(_names(target))
    record = {
        "stamp": stamp,
        "kind": KIND_DOWNLOAD if download else KIND_SEND,
        "at": _iso(_now()),
        "runs": [d.name for d in directories],
        "run": sorted(d.name for d in directories)[-1],
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
    }
    if download:
        _write(directory, record)
        return {"send": _summary(stamp, record, _now()), "console": console}

    # 5. THE PUSH AND THE PUBLISH. One file only: a send is never split.
    if len(kept) != 1:
        _fail(directory, record, "write_split", "A send is one file, and this press wrote "
              f"{len(kept)}. Nothing was sent; the copies are back on the list.",
              HTTPStatus.CONFLICT)
    pushed_file = directory / kept[0]
    record["digest"] = _digest(pushed_file)
    earlier = _already_pushed(record["digest"])
    if earlier is not None:
        _fail(
            directory,
            record,
            "already_sent",
            f"These exact rows went to TCGplayer in the send of {earlier}. Sending them again "
            f"would double every copy, so nothing was sent; the copies are back on the list.",
            HTTPStatus.CONFLICT,
        )
    rows = tcg_import.rows_from_csv(pushed_file.read_text(encoding="utf-8"))
    try:
        upload = tcg_import.push_to_staged(rows, filename=kept[0], listing=True)
    except tcg_import.FetchRefusal as refusal:
        _fail(directory, record, refusal.code,
              f"{refusal.message} The copies are back on the list.")
    record["pushed"] = dict(upload.as_dict(), pushed_at=_iso(_now()))
    _write(directory, record)
    try:
        answer = tcg_import.move_to_live(str(upload.upload_id))
    except tcg_import.FetchRefusal as refusal:
        try:
            tcg_import.rollback(str(upload.upload_id))
            rolled = "The upload was rolled back"
        except tcg_import.FetchRefusal:
            rolled = "The upload could not be rolled back and waits in Staged"
        _fail(directory, record, refusal.code,
              f"{refusal.message} {rolled}; the copies are back on the list.")
    published = _now()
    record["published_at"] = _iso(published)
    record["publish_result"] = answer
    record["check_after"] = _iso(published + timedelta(seconds=cmd_reprice.PUBLISH_LAG_S))
    _write(directory, record)
    return {"send": _summary(stamp, record, _now()), "console": console}


def _fail(
    directory: Path,
    record: dict,
    code: str,
    message: str,
    status: HTTPStatus = HTTPStatus.BAD_GATEWAY,
) -> NoReturn:
    """Record the refusal, put the copies back on the list, and raise it.

    THE COPIES GO BACK BEFORE THE RECEIPT IS WRITTEN, so a crash between the two leaves a
    receipt that still says "not taken back" over copies that are — the safe direction: the
    next send's guard reads TCGplayer, not this receipt.
    """
    _take_back(record.get("copies") or {})
    record["failure"] = {"code": code, "message": message}
    record["taken_back_at"] = _iso(_now())
    _write(directory, record)
    raise PipelineRefusal(status, code, message)


# ------------------------------------------------------------------ the status and the undo


def do_sends() -> dict:
    """`GET /pipeline/sends` — the newest receipts, what is unconfirmed, and when to check.

    `due` is the one bit the screen's timer and its visit check both read: true when a
    receipt is waiting and its lag has passed. `check_at` is the earliest moment one will be.
    """
    now = _now()
    receipts = _receipts()
    shown = [_summary(stamp, record, now) for stamp, record in receipts[:SENDS_SHOWN]]
    unconfirmed = [
        (stamp, record) for stamp, record in receipts if state_of(record, now) == "written"
    ]
    waiting = [
        _parse(record.get("check_after"))
        for _, record in receipts
        if state_of(record, now) == "waiting"
    ]
    check_at = min((moment for moment in waiting if moment is not None), default=None)
    return {
        "sends": shown,
        "unconfirmed": {
            "copies": sum(int(record.get("copies_total") or 0) for _, record in unconfirmed),
            "stamps": [stamp for stamp, _ in unconfirmed],
        },
        "due": any(_due(record, now) for _, record in receipts),
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
    """`POST /pipeline/sends/<stamp>/take-back` — a written file's copies back on the list.

    ONLY A FILE THAT NEVER WENT THROUGH THE PRESS. A send that went live cannot be taken back
    here: its copies are at TCGplayer, and putting them back on the list would send them twice.
    """
    directory = _open_send(stamp)
    record = _read(directory)
    if state_of(record) != "written":
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "not_takeable",
            "Only copies written to a file and not yet found at TCGplayer can be taken back. "
            "Nothing changed.",
        )
    if not bool(payload.get("confirm")):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "Taking copies back changes what the next send offers. Send `confirm`.",
        )
    moved = _take_back(record.get("copies") or {})
    record["taken_back_at"] = _iso(_now())
    _write(directory, record)
    return {"send": _summary(stamp, record, _now()), "moved": moved}


# ----------------------------------------------------------------------- the live check


def do_live_check(payload: dict) -> dict:
    """`POST /pipeline/live-check` — read what is live, settle the store, confirm the sends.

    IT RUNS ONLY WHEN ASKED. The screen asks when a receipt is due: its timer when the wait
    ends while the app is open, or its first visit to Pricing or Home after that. `force: true`
    is the manual "Check what is live" press, which runs even with nothing due.

    A SEND STILL INSIDE THE LAG IS NOT JUDGED BY A FORCED CHECK. Export From Live serves old
    figures for a while after a publish (D106, measured), so reading it early would call a copy
    missing that simply has not shown yet. `reconcile --live` holds those SKUs back itself.
    """
    now = _now()
    receipts = _receipts()
    due = [(stamp, record) for stamp, record in receipts if _due(record, now)]
    force = bool(payload.get("force"))
    if not due and not force:
        status = do_sends()
        return {"ran": False, "check_at": status["check_at"], "checked": []}

    name, path = _fetch_live("checked")
    console = _reconcile(path, "checked")
    live_now = _live_quantities(path)
    sold_now = _sold_by_sku({sku for _, record in due for sku in (record.get("copies") or {})})

    checked = []
    for stamp, record in due:
        copies = {sku: int(n) for sku, n in (record.get("copies") or {}).items()}
        before = record.get("live_before") or {}
        sold_before = record.get("sold_before") or {}
        missing = []
        found_total = 0
        for sku, sent in copies.items():
            sold_since = max(0, sold_now.get(sku, 0) - int(sold_before.get(sku, 0)))
            gained = live_now.get(sku, 0) - int(before.get(sku, 0)) + sold_since
            found = max(0, min(sent, gained))
            found_total += found
            if found < sent:
                missing.append(
                    {
                        "sku": sku,
                        "name": (record.get("names") or {}).get(sku, ""),
                        "sent": sent,
                        "found": found,
                    }
                )
        record["check"] = {
            "export": name,
            "found": found_total,
            "expected": sum(copies.values()),
            "missing": missing,
        }
        record["checked_at"] = _iso(now)
        _write(sends_dir() / stamp, record)
        checked.append(_summary(stamp, record, now))

    return {"ran": True, "export": name, "checked": checked, "console": console}


# ------------------------------------------------------------------ the mark-down, one press


def do_markdown_send(stamp: str, payload: dict) -> dict:
    """`POST /pipeline/markdowns/<stamp>/send` — read what is live, push, publish. One press.

    THE SAME RULINGS AS `do_send`, OVER A FILE THAT ONLY CHANGES PRICES. D100's zero rule on
    the transport is untouched (`tcg_import._check` with `listing=False`), so this file still
    cannot move a copy. What this press adds is the live read in front of it and the publish
    behind it. The receipt is the markdown's own `push.json`, written by the routes this calls,
    so a reload of the old sheet and `published_recently` both read it unchanged.

    A FAILED PUBLISH ROLLS THE UPLOAD BACK. There is no "Put the old prices back" (the owner's
    ruling): the way a live price changes again is another mark-down.
    """
    directory = pipeline_routes._open_markdown(stamp)
    if not (directory / cmd_reprice.IMPORT).is_file():
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "no_import_file",
            "This mark-down has no file to send yet. Check the prices first; nothing was sent.",
        )
    record = pipeline_routes._read_push(directory)
    if record is not None and record.get("published_at"):
        raise PipelineRefusal(
            HTTPStatus.CONFLICT,
            "already_published",
            f"These prices went live at {record['published_at']}. Nothing was sent.",
        )
    if not bool(payload.get("confirm")):
        raise PipelineRefusal(
            HTTPStatus.BAD_REQUEST,
            "confirm_required",
            "A send changes what buyers pay. Send `confirm` once the owner has pressed it; "
            "nothing was sent.",
        )
    _, live_path = _fetch_live("sent")
    _reconcile(live_path, "sent")
    if record is None:
        pipeline_routes.do_markdown_push(stamp, {"confirm": True})
    try:
        published = pipeline_routes.do_markdown_publish(stamp, {"confirm": True})
    except PipelineRefusal as refusal:
        try:
            pipeline_routes.do_markdown_rollback(stamp, {"confirm": True})
            rolled = "The upload was rolled back, so no price changed."
        except PipelineRefusal:
            rolled = "The upload could not be rolled back and waits in Staged."
        raise PipelineRefusal(refusal.status, refusal.code, f"{refusal} {rolled}") from None
    return published
