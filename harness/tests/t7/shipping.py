"""T7 group: shipping lane, routes and stamps.

Part of `harness/tests/t7_store_and_seams.py` (one verdict). `CHECKS` is this group's checks in
the order `CHECK_ORDER` runs them.
"""

from __future__ import annotations

import codecs
import contextlib
import csv
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from decimal import Decimal
from fractions import Fraction
from harness.tests import Checks
from cli import resolve
from pipeline import join, pirateship, shipping
from server import capture_server, order_transport, shipping_routes
from store.session import Store
from harness.tests.t7.common import (
    REPO_ROOT,
    answers,
    capture_payload,
    isolated_home,
)


def shipping_refusal(checks: Checks, fn, code: str, label: str) -> None:
    """`refusal`'s shape for the shipping module's own exception.

    It cannot raise `capture_server.BadRequest` — capture_server imports it, so the reverse
    import is the cycle `PipelineRefusal` exists to avoid. The seam is one `except` clause at
    the dispatch site, and one helper here so the cases read the same as every other route's.
    """
    try:
        fn()
    except shipping_routes.ShippingRefusal as caught:
        checks.equal(caught.code, code, label)
    except Exception as caught:  # noqa: BLE001 — any other exception is the failure
        checks.ok(False, label, f"raised {type(caught).__name__}: {caught}")
    else:
        checks.ok(False, label, "did not refuse")

# ------------------------------------------------------- the shipping lane (D61)

# A relative literal, which is what `scripts/docs-audit.py`'s `tested_by reach` row can
# actually see — see the note above the price-history fixtures for why a path assembled
# from segments is invisible to it.
SHIPPING_FIXTURE = "fixtures/orders-shipping.csv"

SHIPPING_EXPORT = REPO_ROOT / SHIPPING_FIXTURE


def _shipment(**overrides) -> shipping.Shipment:
    """One synthetic export row. Every column present, so the reader's contract holds.

    CONSTRUCTED, AND THE BLOCK BELOW SAYS SO EVERY TIME IT USES ONE. The fixture is 331
    real orders and carries the SHAPE — five exact ratios, the empty band, 97 weightless
    rows — and it is what the lane counts are asserted against. What it cannot carry is a
    row that has never occurred, and `sub_single_weight` is exactly that: `docs/specs/
    shipping-export.md` names it as a real mechanism with no example. A case for it has to
    be built, and building one is not evidence that it happens.
    """
    cells = {column: "" for column in shipping.CANONICAL_HEADER}
    cells.update(
        {
            "Order #": "TEST-0001",
            "FirstName": "Buyer001",
            "LastName": "Placeholder",
            "Address1": "101 Example St",
            "City": "Springfield",
            "State": "WV",
            "PostalCode": "17919",
            "Country": "US",
            "Product Weight": "0.70",
            "Item Count": "10",
            "Value Of Products": "10.00",
        }
    )
    cells.update(overrides)
    return shipping.Shipment(cells=cells)


def check_shipping_lane(checks: Checks) -> None:
    """`pipeline/shipping.py` and `pipeline/pirateship.py` — the router and the emitter.

    THREE LANES, NOT A $50 LINE, and the middle lane is why this is a router: a $12 sealed
    booster box may not go in a stamped envelope and a $600 single may not go untracked, so
    a rule reading only the money and a rule reading only the contents are each wrong about
    one real order.

    THE ASSERTIONS THAT MATTER MOST ARE THE ONES ABOUT ORDER AND ABOUT ABSENCE, because
    both are satisfiable by a plausible wrong build:

      THE SEQUENCE. Asking the value question before the weight question is not a style
      choice — 58 of the fixture's 97 weightless orders are at or over $50 and are answered
      with certainty by a rule that needs no weight. A router that abstained first would
      still produce three lanes, still count correctly on every weight-bearing row, and
      still look right; it would abstain on 97 orders instead of 39, one of which is the
      $1750 order `docs/specs/shipping-export.md` names as its own worst case. So the
      $1750 order is asserted BY NAME.

      THE WEIGHT IS NEVER DERIVED. `Package Weight` comes out blank even though the
      shipment in hand carries a `Product Weight`, and that emptiness is asserted. It is
      the single most likely thing for a later session to "fix", and it is wrong in the
      expensive direction: the catalog constant counts the cardboard and not the mailer, so
      it buys postage for less than the parcel weighs and the bill arrives at the far end.

      INSURANCE IS REFUSED. D86's rule in another lane. A row carrying an insurance column
      raises rather than being dropped, because dropping it silently is an operator who
      believes they asked for insurance and did not.

    WHAT THIS BLOCK DOES NOT COVER, named so a green harness is not misread: whether Pirate
    Ship's importer accepts these headers. Nobody has fed it this file. Their wizard maps
    column names on their side of a seam no committed fixture can hold — the same standing
    as T6's synthetic composites, and the reason `Name` is PRE-JOINED here rather than left
    to their mapper to work out from two of ours.
    """
    checks.note("")
    checks.note("SHIPPING LANE — the router over a real Export Shipping, and the emitter")

    with isolated_home() as home:
        export = shipping.read_shipping(SHIPPING_EXPORT)

        # ---------------------------------------------------------------- the reader
        checks.equal(len(export), 331, "the committed Export Shipping reads 331 orders")
        checks.equal(
            export.header,
            shipping.CANONICAL_HEADER,
            "and its header is the documented 17 columns, in order",
        )
        checks.raises(
            shipping.MalformedShipping,
            lambda: shipping.parse(b"Order #,FirstName\r\n"),
            "a header that is not that one refuses, rather than reading every order as "
            "unjudgeable — 331 silent abstentions look like a quiet afternoon",
        )
        checks.raises(
            shipping.MalformedShipping,
            lambda: shipping.parse(
                b"\xef\xbb\xbf" + ",".join(shipping.CANONICAL_HEADER).encode() + b"\n"
            ),
            "and a BOM refuses; the real export has none",
        )

        # ----------------------------------------------------------------- the lanes
        routings = shipping.route_all(export.shipments)
        checks.equal(
            shipping.lane_counts(routings),
            {"envelope": 166, "parcel": 126, "unjudged": 39},
            "331 real orders land 166 envelope / 126 parcel / 39 unjudged",
        )
        checks.equal(
            shipping.reason_counts(routings),
            {
                "value_at_threshold": 112,
                "non_card_signal": 14,
                "cards_only": 166,
                "no_weight_data": 39,
                "no_value_data": 0,
                "sub_single_weight": 0,
            },
            "and every lane carries its grounds — two reasons reach `parcel`, and one of "
            "them is a fact while the other is an 18x inference",
        )

        # THE SEQUENCE, ASSERTED AS THE ARITHMETIC RATHER THAN AS A NUMBER. 97 rows report
        # no weight and only 39 survive to abstain, which is the value rule doing its work
        # ahead of the proxy. Pinning 39 alone would go green on a build that abstained
        # first and happened to be re-fitted; this cannot.
        weightless = [s for s in export.shipments if s.weight is None]
        rescued = [r for s, r in zip(export.shipments, routings) if s.weight is None and r.judged]
        checks.equal(len(weightless), 97, "97 of the 331 report no weight at all")
        checks.equal(
            len(rescued),
            58,
            "and 58 of those 97 are still answered — with certainty, by a rule that never "
            "needed a weight. Abstention is 39 of 331 (11.8%), not 97 (29%)",
        )
        checks.ok(
            all(r.reason == shipping.VALUE_AT_THRESHOLD for r in rescued),
            "every one of the 58 is answered by the value, which is the only fact a "
            "weightless row carries",
        )

        # THE SPEC'S OWN WORST CASE, BY NAME. `docs/specs/shipping-export.md`: "It abstains
        # on 29% of orders, and one of them is a $1750 order." It does not abstain on that
        # one, and this is the assertion that says so.
        big = next(r for r in routings if r.order == "A2FFC195-0000F4-006AC")
        checks.equal(
            (big.lane, big.reason, big.certain, str(big.value)),
            ("parcel", "value_at_threshold", True, "1750.00"),
            "the $1750 weightless order the spec names as unjudgeable is judged — tracked, "
            "with certainty, without consulting the proxy",
        )

        # THE BOUNDARY. TCGplayer mandates tracking above $49.99, so exactly 50.00 is
        # tracked. The fixture holds exactly one such row, which is why it is worth pinning.
        fifty = [r for r in routings if r.value == Decimal("50.00")]
        checks.equal(len(fifty), 1, "the fixture holds exactly one order at exactly $50.00")
        checks.equal(
            (fifty[0].lane, fifty[0].reason),
            ("parcel", "value_at_threshold"),
            "and $50.00 is ON the tracked side — the mandate is above $49.99",
        )
        checks.equal(
            shipping.route(_shipment(**{"Value Of Products": "49.99"})).lane,
            "envelope",
            "a constructed $49.99 order of pure singles is not — the two sit either side "
            "of one comparison",
        )

        # ------------------------------------------------- abstention is a third answer
        unjudged = [r for r in routings if not r.judged]
        checks.equal(len(unjudged), 39, "39 orders cannot be placed by either signal")
        parcel_orders = {routing.order for _, routing in shipping.parcel_lane(export)}
        checks.ok(
            not (parcel_orders & {r.order for r in unjudged}),
            "and not one of them is swept into the Pirate Ship lane. Sweeping them in is a "
            "postage charge the operator did not choose, which is the objection insurance "
            "gets one module over",
        )
        checks.equal(
            len(parcel_orders), 126,
            "the emitter's input is the 126 the router placed there, and nothing else",
        )

        # -------------------------------------------- exact arithmetic, never a float
        # `docs/specs/shipping-export.md` records that a float pass "reported a phantom
        # sub-0.07 row" on a distribution whose true minimum is exactly 0.07 — and sub-0.07
        # is the one band this router treats as impossible, so a float would manufacture
        # the outcome. 115/86 is the fixture's non-terminating ratio and is the row that
        # cannot survive a float round trip intact.
        ratios = {s.weight_per_item for s in export.shipments if s.weight_per_item is not None}
        checks.ok(
            Fraction(115, 86) in ratios,
            "the fixture's non-terminating ratio parses to exactly 115/86",
        )
        checks.ok(
            all(r >= shipping.SINGLES_WEIGHT for r in ratios),
            "and no observed ratio is below the singles constant — the floor the spec "
            "confirmed with rational arithmetic after floats reported a phantom row",
        )

        # THE FALSE-NEGATIVE PATH THE SPEC NAMES, WHICH THE FIXTURE CANNOT SHOW. One card
        # plus one weightless non-card reads 0.035 oz/item — BELOW the singles constant, so
        # a router comparing only against the 0.30 cut calls it `cards_only` and puts a
        # playmat in a stamped envelope, silently. CONSTRUCTED, because no such row occurs.
        sub = shipping.route(_shipment(**{"Product Weight": "0.07", "Item Count": "2"}))
        checks.equal(
            (sub.lane, sub.reason),
            ("unjudged", "sub_single_weight"),
            "a ratio below the singles constant abstains rather than reading as safer than "
            "pure singles — no combination of catalog weights can produce it, so the proxy "
            "does not apply and this router has nothing to say",
        )
        checks.equal(
            shipping.route(_shipment(**{"Product Weight": "0.00"})).reason,
            "no_weight_data",
            "and a zero weight is absent data rather than a light order — a different "
            "abstention with a different remedy",
        )
        # THIS CASE FOUND A REAL DEFECT AND IS WHY IT IS PINNED ON THE REASON RATHER THAN
        # ON THE LANE. The guard was a COMMENT in `route` before it was a line of code, and
        # a valueless order of pure singles fell through to `cards_only` — a $600 single
        # going out untracked in a stamped envelope. CONSTRUCTED: `Value Of Products` is
        # present on all 331 fixture rows, so nothing observed reaches it.
        valueless = shipping.route(_shipment(**{"Value Of Products": ""}))
        checks.equal(
            (valueless.lane, valueless.reason),
            ("unjudged", "no_value_data"),
            "an order whose value nobody knows is exactly the one not to make a postage "
            "decision about — and the proxy may not rescue it, because a cards-only ratio "
            "is the shape an expensive single takes",
        )

        # -------------------------------------------------------------- the emitter
        # CHOSEN FOR ITS WEIGHT, NOT TAKEN FIRST, and the first draft of this block took
        # the first row and failed: 58 of the 126 in this lane are `value_at_threshold` and
        # carry no weight at all, so the negative below would have been asserting that a
        # blank column stayed blank. The order that makes it mean something is one the
        # router reached THROUGH the weight — those are the ones whose `Product Weight` is
        # most tempting to carry across.
        shipment, routing = next(
            (s, r) for s, r in shipping.parcel_lane(export)
            if r.reason == shipping.NON_CARD_SIGNAL
        )
        parcel = shipping.to_parcel(shipment, stamps=("Box 3 · Card 31",))
        data = pirateship.render([parcel])
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))

        checks.equal(
            tuple(rows[0]), pirateship.COLUMNS,
            "every column is written, blanks included — a column absent from the file is "
            "one Pirate Ship's wizard cannot map and cannot show the operator",
        )
        checks.equal(
            rows[0]["Name"],
            f"{shipment.cells['FirstName']} {shipment.cells['LastName']}",
            "`Name` is PRE-JOINED from the two columns TCGplayer holds it in, because we "
            "own the columns and their mapper does not have to guess",
        )
        checks.equal(
            pirateship.Parcel.from_parts(
                "Buyer001", "", address="", city="", state="", zipcode="", country="",
                order_id="x",
            ).name,
            "Buyer001",
            "and a record carrying only one half joins to one word, not to a word and a "
            "trailing space that survives onto the printed label",
        )
        checks.equal(
            rows[0]["Order ID"], shipment.order,
            "the TCGplayer order number rides along, which is what closes the loop — "
            "`Tracking #` and `Carrier` are empty on all 331 rows of the export",
        )
        checks.equal(
            rows[0]["Rubber Stamp 1"], "Box 3 · Card 31",
            "and the physical location prints on the label, so the label IS the pick "
            "instruction",
        )

        # THE NEGATIVE THIS BLOCK EXISTS FOR. The shipment in hand carries a real
        # `Product Weight` and the emitted cell is still blank.
        checks.ok(
            shipment.weight is not None and routing.reason == shipping.NON_CARD_SIGNAL,
            "this order reports a Product Weight AND was routed by it, so the temptation to "
            "carry it across is at its strongest",
        )
        checks.equal(
            rows[0]["Package Weight"], "",
            "and `Package Weight` is STILL BLANK. The catalog constant counts the cardboard "
            "and not the mailer, so writing it buys postage for less than the parcel "
            "weighs — under-paid at the far end, weeks later. Nothing is defaulted on the "
            "owner's behalf (D86)",
        )

        # ------------------------------------------------------------ what is refused
        # ASSERTED ON THE GUARD RATHER THAN THROUGH `render`, and that is the point of the
        # guard existing separately. `to_row` builds only `COLUMNS`, so no `Parcel` can
        # carry an insurance cell — the case this closes is a row that reached the writer by
        # some OTHER path, which is `tcgcsv.check_only_writable_changed`'s shape and the
        # same argument: the rule that matters is the one the bytes have to pass.
        checks.raises(
            pirateship.InsuranceRefused,
            lambda: pirateship.check_no_insurance({"Insured Value": "50.00"}),
            "an insurance column is REFUSED, not dropped — the owner chooses insurance per "
            "order inside Pirate Ship, looking at the card",
        )
        checks.raises(
            pirateship.InsuranceRefused,
            lambda: pirateship.check_no_insurance({" insured  VALUE ": "50.00"}),
            "and the match folds case and whitespace, so a differently-spelled column "
            "cannot slip past the one guard that stops it",
        )
        checks.raises(
            pirateship.MalformedParcel,
            lambda: pirateship.Parcel(
                name="x", address="1 St", city="Springfield", state="WV", zipcode="17919",
                country="US", order_id="TEST-0001", stamps=("a", "b", "c", "d"),
            ),
            "a fourth rubber stamp refuses — the label has three corners, which is knowable "
            "from the format, unlike a stamp's length, which nobody here has measured",
        )

        # ------------------------------------------------------------- the byte format
        # T2's rules, and the one case a naive writer corrupts silently: a street address
        # carries a comma by construction, and the symptom is a package at another building.
        comma = pirateship.render([pirateship.Parcel(
            name='O\'Nare, Billy', address="Apt 4, Building C", city="Springfield",
            state="WV", zipcode="17919", country="US", order_id="TEST-0001",
        )])
        checks.equal(
            list(csv.DictReader(io.StringIO(comma.decode(), newline="")))[0]["Address"],
            "Apt 4, Building C",
            "an address with a comma round-trips — real CSV library only (v1 bug 2)",
        )
        checks.ok(
            comma.endswith(b"\r\n") and comma.count(b"\n") == comma.count(b"\r\n"),
            "CRLF throughout including the final record, with no bare LF — the IMPORT "
            "shape (T2), which is not the LF the export it was read from uses",
        )
        checks.ok(
            not comma.startswith(b'"') and not comma.startswith(codecs.BOM_UTF8),
            "unquoted header, no BOM",
        )
        checks.ok(
            comma.split(b"\r\n")[1].startswith(b'"') and comma.split(b"\r\n")[1].endswith(b'"'),
            "and every data field quoted, empties included",
        )

        # `write_csv` is the only thing here that touches a disk, and it writes exactly
        # where it is told — buyer PII passes through and is not persisted, so nothing in
        # either module reaches the store.
        out = home / "pirateship-import.csv"
        written = pirateship.write_csv(out, [parcel])
        checks.equal(
            out.read_bytes(), written,
            "`write_csv` writes exactly the bytes it returns, and only where it is told",
        )

# ------------------------------------------------------------- the shipping routes


def home_files(home):
    """Every path under a store home, EXCEPT SQLite's own journal.

    `store.sqlite-wal` and `store.sqlite-shm` are created by OPENING the database in WAL mode —
    by a read, not by a write — and SQLite deletes them when the last connection closes
    cleanly. Whether they survive to the end of a check is therefore a fact about connection
    lifetime and about the platform, not about anything having been persisted.

    THIS COST A RED MAIN ON 2026-09-06. The stamp check compares this snapshot before and after
    to assert D61's rule that buyer PII passes through and is never kept. It passed on macOS
    for a year and failed the first time it ran on Linux, where the two files outlived the
    read; the diff was exactly `-shm` and `-wal` and nothing else, so nothing had been
    persisted and the assertion was reading "the database was opened" as "a file was kept".

    What the check is FOR still works: a cache directory, a temp file or a log line carrying a
    row is a real path and still appears here. Only the engine's own journal is excluded, and
    only because its presence was never evidence of the thing being asserted.
    """
    return sorted(
        str(path.relative_to(home))
        for path in home.rglob("*")
        if path.suffix not in (".sqlite-wal", ".sqlite-shm")
        and not path.name.endswith(("-wal", "-shm"))
    )


def check_shipping_routes(checks: Checks) -> None:
    """`server/shipping_routes.py` and `server/order_transport.py` — the two seams that hold
    somebody else's personal data, asserted on what they DO NOT carry.

    `check_shipping_lane` covers the router and the emitter over the same 331-order export.
    THIS COVERS THE ROUTE, which is a different question: the module above is the one file in
    this server that ever holds a buyer's real name and street address, and every assertion
    worth making about it is an ABSENCE. An absence is exactly what a plausible build
    satisfies by accident and loses by accident, so each one is pinned as an ABSOLUTE — the
    whole reason dict, the whole key set of a row, the whole set of files under the home —
    rather than as a lookup that goes on passing while a field is added beside it.

    FOUR ABSENCES, AND EACH ONE IS A REAL COST IF IT STOPS BEING TRUE:

      no PII on the list wire   the union of every row's keys is asserted as a set, and the
                                fixture's own first buyer name and street are asserted absent
                                from the whole serialized answer. A later field is then
                                argued for here rather than slipped in.
      the abstention is not in  none of the 39 unjudged order ids appears in the rendered
      the file                  import. Being swept into the parcel lane to be safe is a
                                postage charge the operator did not choose.
      no weight is ever derived every `Package Weight` cell is empty, including on a
                                `non_card_signal` order — the case where deriving it looks
                                most reasonable, and the case where it buys postage for less
                                than the parcel weighs.
      nothing is persisted      the store's file list is identical before and after reading a
                                331-order export, rendering the import and downloading it.
                                D61's rule that buyer PII passes through and is not kept is
                                what `pirateship.render` returning BYTES exists to make
                                possible, and one cache line here would undo it.

    THE WAY BACK IS ASSERTED TO ACTUALLY FORGET, and the holding is asserted to be BOUNDED.
    Without the first, the Forget button is a lie; without the second, how much buyer PII this
    process can hold at once is a comment rather than a fact.

    THE TRANSPORT HALF RUNS WITH NO SOCKET AT ALL (T3, D69). `server/order_transport.py`'s
    authenticated success path has never run and this section does not pretend otherwise: what
    is asserted is the part that is decidable without a live session — that the projection
    drops `buyerName` and `shippingAddress` where it parses them, that the body that goes out
    is a plain JSON document and NOT D65's `model=` form-encoded shape (the first thing a
    reader will try to "fix" it into), that a missing seller key and an expired session are
    two codes and not one (403 on that host is the REQUEST, measured — folding it into "sign
    in again" sends the operator to re-copy a working cookie over a bug in this file), that a
    problem+json body yields its `traceId` and nothing else, and that no refusal message
    carries the credential. The one request that is built is handed to a stubbed opener that
    raises rather than connecting, so the harness opens nothing — this suite runs behind the
    Stop hook at the end of every turn, and a case that reached a third party would put a
    stranger's uptime on the path that decides whether work is done.

    ITS OWN `isolated_home`, and here it is load-bearing rather than hygienic: one of the
    assertions IS that the home is byte-identical afterwards.
    """
    checks.note("")
    checks.note(
        "SHIPPING ROUTES AND THE ORDER TRANSPORT — the two seams that hold buyer PII "
        "(D61, D63, D69)"
    )

    fixture = SHIPPING_EXPORT.read_text("utf-8")

    with isolated_home() as home:
        before = home_files(home)

        answer = answers(
            checks,
            lambda: shipping_routes.do_shipping_batches(
                {"name": "orders-shipping.csv", "content": fixture}
            ),
            "POST /shipping/batches reads the committed 331-order Export Shipping file",
        )
        if answer is None:
            return

        rows = answer["rows"]
        checks.equal(answer["shipments"], 331, "331 orders reach the screen")
        checks.equal(
            answer["lane_counts"],
            {"envelope": 166, "parcel": 126, "unjudged": 39},
            "and the route publishes the router's own three lanes unchanged — 166 / 126 / 39",
        )
        checks.equal(
            answer["parcel_count"],
            126,
            "the import file is rendered from the 126 the router placed in the parcel lane, "
            "and from nothing else",
        )
        checks.equal(
            answer["reason_counts"],
            {
                "value_at_threshold": 112,
                "non_card_signal": 14,
                "cards_only": 166,
                "no_weight_data": 39,
                "no_value_data": 0,
                "sub_single_weight": 0,
            },
            "EVERY REASON INCLUDING THE TWO ZEROS, as one absolute dict. Asserting the whole "
            "thing rather than six lookups is what catches a route that filtered the empty "
            "ones out — 'nothing was unjudged' and 'nothing was checked' must not be the "
            "same payload",
        )
        checks.equal(
            {row["reason"] for row in rows if row["certain"]},
            {"value_at_threshold"},
            "`certain` IS EXACTLY THE FACT AND NEVER THE INFERENCE: the only rows carrying "
            "it are the ones answered by the published value. The 18x weight proxy is a "
            "reading of a catalog constant, and a screen that drew the two the same way "
            "would let an inference look like a measurement",
        )
        checks.equal(
            sum(1 for row in rows if row["certain"]),
            112,
            "and that is 112 of the 331",
        )

        keys = set()
        for row in rows:
            keys |= set(row)
        checks.equal(
            keys,
            {"order", "lane", "reason", "certain", "value", "weight_per_item_oz",
             "item_count", "stamp"},
            "NO PII ON THE LIST WIRE. The union of every row's key set is exactly these "
            "eight — an ABSOLUTE set, so a name, a city or a postcode added to the row later "
            "is argued for HERE rather than slipped in behind a lookup that still passes",
        )
        cells = list(csv.reader(io.StringIO(fixture)))[1]
        serialized = json.dumps(answer)
        checks.ok(
            cells[1] not in serialized and cells[3] not in serialized,
            "and the fixture's own first buyer name and first street address appear NOWHERE "
            "in the serialized answer. Asserted against the file's real cells rather than "
            "against a literal, so the case cannot go stale against a re-exported fixture",
            f"name {cells[1]!r} / street {cells[3]!r}",
        )

        blob, kind = shipping_routes.do_shipping_file(answer["batch"], "pirateship-import.csv")
        checks.equal(kind, "text/csv", "the download is served as text/csv")
        unjudged = [row["order"] for row in rows if row["lane"] == "unjudged"]
        checks.equal(len(unjudged), 39, "39 orders were left unjudged")
        checks.ok(
            not any(order.encode("utf-8") in blob for order in unjudged),
            "AND THE ABSTENTION IS NOT IN THE FILE — not one of those 39 order ids appears "
            "in the rendered import. Sweeping them into the parcel lane to be safe is a "
            "postage charge the operator did not choose; sweeping them into the envelope "
            "lane is a playmat in a stamped mailer. Both are the operator's decision, made "
            "looking at the order",
        )

        checks.equal(
            len(blob),
            14786,
            "the import file is 14,786 bytes — pinned, so a column quietly added or dropped "
            "moves a number rather than passing on a shape check",
        )
        data_lines = [chunk for chunk in blob.split(b"\r\n") if chunk.strip()][1:]
        checks.equal(len(data_lines), 126, "126 data lines, one per parcel-lane order")
        checks.ok(
            all(chunk.endswith(b',"","",""') for chunk in data_lines),
            "and every one of them ends in three empty rubber stamps — the seam the future "
            "stamps route fills, present and empty rather than absent",
        )
        parsed = list(csv.reader(io.StringIO(blob.decode("utf-8"), newline="")))
        checks.equal(
            {row[7] for row in parsed[1:]},
            {""},
            "NO WEIGHT IS EVER DERIVED: every `Package Weight` cell is empty. `Product "
            "Weight` is a summed catalog constant and therefore a LOWER BOUND on what the "
            "parcel weighs, so writing it buys postage for less than the package weighs and "
            "the bill arrives at the far end weeks later",
        )
        signaled = next(row for row in rows if row["reason"] == "non_card_signal")
        signaled_line = [row for row in parsed[1:] if row[8] == signaled["order"]]
        checks.equal(
            [row[7] for row in signaled_line],
            [""],
            "AND IT IS STILL EMPTY ON A `non_card_signal` ORDER, which is the case where "
            "carrying it across would look most reasonable: that order was routed BY its "
            "weight, so the number is in the hand of the code writing the row",
        )
        checks.ok(
            b"Insurance" not in blob and b"Insured" not in blob and b"Shipsurance" not in blob,
            "NO INSURANCE COLUMN IN ANY SPELLING. Insurance is a per-order judgement the "
            "owner makes inside Pirate Ship, and a file that quietly carried the column "
            "would let a caller think it had been asked for",
        )
        checks.ok(
            answer["stamps"] is None and all(row["stamp"] is None for row in rows),
            "THE STAMP SEAM IS PRESENT AND EMPTY — `stamps` on the batch and `stamp` on "
            "every row are nulls rather than absent keys, so the route that fills them "
            "changes no type and no component",
        )
        checks.equal(
            blob.split(b"\r\n")[0],
            b"Name,Address,Address Line 2,City,State,Zipcode,Country,Package Weight,"
            b"Order ID,Rubber Stamp 1,Rubber Stamp 2,Rubber Stamp 3",
            "the header is the twelve columns UNQUOTED, in order — a column absent from the "
            "file is one Pirate Ship's wizard cannot map and cannot show the operator",
        )
        checks.ok(
            blob.endswith(b"\r\n") and not blob.startswith(codecs.BOM_UTF8),
            "CRLF to the last record and no BOM — T2's import shape, which is not the LF the "
            "export it was read from uses",
        )

        # ------------------------------------------------------- every refusal by its code
        shipping_refusal(
            checks,
            lambda: shipping_routes.do_shipping_batches(
                {"name": "x.csv", "content": fixture, "stamps": []}
            ),
            "field_not_settable",
            "a third key on the body refuses by name — this route sets two things",
        )
        shipping_refusal(
            checks,
            lambda: shipping_routes.do_shipping_batches({"content": "   "}),
            "export_empty",
            "whitespace is an empty file rather than a file with a blank first line",
        )
        shipping_refusal(
            checks,
            lambda: shipping_routes.do_shipping_batches({"content": "not-a-spreadsheet\nx"}),
            "export_not_csv",
            "a first line with no comma in it refuses cheaply, before the parser can answer "
            "with a missing column for a file that was never a spreadsheet",
        )
        shipping_refusal(
            checks,
            lambda: shipping_routes.do_shipping_batches(
                {"content": (REPO_ROOT
                             / "fixtures" / "sv09_export_untouched.csv").read_text("utf-8")}
            ),
            "export_not_shipping",
            "AND THE FILTERED EXPORT REFUSES ON THE HEADER RATHER THAN ON THE COMMA CHECK. "
            "It has commas in line 1, so it passes the cheap test and has to be caught by "
            "the parse — which is the mistake an operator actually makes, two exports one "
            "tab apart in the same portal",
        )
        shipping_refusal(
            checks,
            lambda: shipping_routes.do_shipping_batches(
                {"content": "a,b\n" + "x" * shipping_routes.MAX_EXPORT_CHARS}
            ),
            "export_too_large",
            "and a body past the ceiling names the FILE rather than the request, because an "
            "operator who just picked a 40 MB file needs to be told it was the file",
        )
        for name in ("pricing.json", "../../inventory.json", ""):
            shipping_refusal(
                checks,
                lambda wanted=name: shipping_routes.do_shipping_file(answer["batch"], wanted),
                "file_name_invalid",
                f"{name!r} is not a file of this batch. The name is checked by MEMBERSHIP "
                f"and not by pattern — the batch holds exactly one file, so membership IS "
                f"the shape check and no traversal rule has to be written or maintained",
            )
        shipping_refusal(
            checks,
            lambda: shipping_routes.do_shipping_file("not-a-batch-id", "pirateship-import.csv"),
            "no_such_batch",
            "an unknown batch id refuses with the sentence that says the server restarts on "
            "every Python edit — a refusal that reads like a bug costs a support round trip",
        )

        # ----------------------------------------------------------- the way back, and the bound
        checks.equal(
            answers(
                checks,
                lambda: shipping_routes.do_shipping_forget(answer["batch"]),
                "DELETE /shipping/batches/<batch> answers rather than 204-ing",
            ),
            {"batch": answer["batch"], "forgotten": True},
            "and it names what it just dropped, which is where the app's own sentence comes "
            "from",
        )
        shipping_refusal(
            checks,
            lambda: shipping_routes.do_shipping_file(answer["batch"], "pirateship-import.csv"),
            "no_such_batch",
            "THE WAY BACK ACTUALLY FORGETS: the file is gone the moment Forget is pressed. "
            "Without this assertion the button is a lie, and the buyer addresses sit in this "
            "process for the rest of the TTL",
        )
        shipping_refusal(
            checks,
            lambda: shipping_routes.do_shipping_forget(answer["batch"]),
            "no_such_batch",
            "and a second Forget refuses rather than reporting a second success",
        )

        # A one-row export, so the bound is asserted without parsing 331 orders five times.
        small = "\r\n".join(fixture.splitlines()[:2]) + "\r\n"
        ids = [
            shipping_routes.do_shipping_batches({"name": "s.csv", "content": small})["batch"]
            for _ in range(shipping_routes.BATCH_LIMIT + 1)
        ]
        shipping_refusal(
            checks,
            lambda: shipping_routes.do_shipping_file(ids[0], "pirateship-import.csv"),
            "no_such_batch",
            f"THE HOLDING IS BOUNDED AT {shipping_routes.BATCH_LIMIT}: read one more export "
            f"and the oldest is evicted. This is how much buyer PII the process can hold at "
            f"once, asserted rather than commented",
        )
        answers(
            checks,
            lambda: shipping_routes.do_shipping_file(ids[-1], "pirateship-import.csv"),
            "and the newest one is still there, so the eviction is oldest-first rather than "
            "a table that emptied itself",
        )
        for spare in ids:
            with contextlib.suppress(shipping_routes.ShippingRefusal):
                shipping_routes.do_shipping_forget(spare)

        after = home_files(home)
        checks.equal(
            after,
            before,
            "NOTHING WAS PERSISTED. Reading a 331-order export, rendering the import file "
            "and downloading it wrote NOT ONE FILE into the store. D61's rule that buyer PII "
            "passes through and is never kept is what `pirateship.render` returning BYTES "
            "exists to make possible, and a cache directory, a temp file or a log line "
            "carrying a row would each be one line to add here",
        )

    # ----------------------------------------- T3: the order transport, with no socket at all
    env_keys = ("BANCHI_TCG_ORDERS_URL",)
    previous = {name: os.environ.get(name) for name in env_keys}
    seen = []

    class _Stub:
        """An opener that records the request and refuses to connect.

        The point of the whole seam: `_open` builds a `Request` and hands it to whatever
        `build_opener` returned, so the request that WOULD have gone out is inspectable
        without a socket, a thread or a stub server. The `URLError` is what a dead socket
        raises, so the refusal it produces is the real one.
        """

        def open(self, request, data=None, timeout=None):  # noqa: A003
            seen.append(request)
            raise urllib.error.URLError("stubbed: this test opens no socket")

    real_opener = urllib.request.build_opener
    try:
        os.environ["BANCHI_TCG_ORDERS_URL"] = "http://127.0.0.1:1"

        projected = order_transport.project_order(
            {
                "orderNumber": "A2FFC195-000001-00007",
                "createdAt": "2026-05-30",
                "status": "Processing",
                "buyerName": "Buyer001 Placeholder",
                "shippingAddress": {"line1": "101 Example St", "city": "Springfield"},
                "sellerName": "banchi",
                "paymentType": "Visa",
                "transaction": {"total": "88.80"},
                "trackingNumbers": ["1Z999"],
                "allowedActions": ["ship"],
                "products": [
                    {
                        "skuId": 9191486, "quantity": 3, "name": "Moonfall",
                        "unitPrice": 11.88, "buyerName": "Buyer001 Placeholder",
                    }
                ],
            }
        )
        checks.equal(
            sorted(projected),
            ["buyer", "orderDate", "orderNumber", "products", "status"],
            "THE PROJECTION IS AN ALLOWLIST AND ITS KEY SET IS THE SECURITY BOUNDARY — five "
            "keys now, asserted whole. `buyer` joined it on the owner's ruling "
            "(D193); a denylist would return a field TCGplayer adds "
            "later and nothing would fail",
        )
        checks.equal(
            projected["buyer"],
            "Buyer001 Placeholder",
            "the display name is the one fact about a person that survives the projection",
        )
        serialized = json.dumps(projected)
        checks.equal(
            serialized.count("Buyer001 Placeholder"),
            1,
            "AND IT SURVIVES EXACTLY ONCE. The fixture repeats the name on a product line "
            "too (`products[].buyerName`), and that copy stays dropped — a projection that "
            "let the name back in via `products[]` would still pass a naive 'is buyer "
            "present' check while doubling the PII surface",
        )
        checks.ok(
            "101 Example St" not in serialized and "Visa" not in serialized,
            "and `shippingAddress` and `paymentType` are DROPPED WHERE THEY ARE PARSED",
        )
        checks.equal(
            projected["products"],
            [{"skuId": "9191486", "quantity": 3, "name": "Moonfall", "unitPrice": "11.88"}],
            "WHAT SURVIVES IS THE PICK: the SKU and the quantity, with the SKU COERCED TO A "
            "STRING at the boundary. `Card.sku` is a string because it came out of a CSV "
            "cell and this feed sends an int; `\"9191486\" == 9191486` is False, and an "
            "uncoerced one makes every line unresolvable while raising nothing and logging "
            "nothing",
        )
        checks.equal(
            sorted(order_transport.project_summary(
                {"orderNumber": "X-1", "orderDate": "2026-05-30",
                 "orderStatus": "Processing", "buyerName": "Buyer001 Placeholder"}
            )),
            ["buyer", "orderDate", "orderNumber", "status"],
            "and the SEARCH result is projected too, which is not belt-and-braces: the list "
            "endpoint carries `buyerName` beside `shippingAddress`, and `buyer` is the one "
            "of those two that survives — the same allowlist, one call earlier",
        )

        body = order_transport.search_body("LastThreeMonths", 25, 0, "a2ffc195")
        checks.equal(
            body["filters"],
            {"sellerKey": "a2ffc195"},
            "the search body carries the seller key in the field whose ABSENCE this host "
            "answers 403 to — measured, not assumed",
        )
        cookie = "TCGAuthTicket_Production=t7-not-a-real-session; other=1"
        urllib.request.build_opener = lambda *args, **kwargs: _Stub()
        unreachable = None
        try:
            order_transport._call(
                f"{order_transport.base_url()}/orders/search?api-version=2.0",
                cookie=cookie,
                data=json.dumps(body).encode("utf-8"),
            )
        except order_transport.FetchRefusal as caught:
            unreachable = caught
        finally:
            urllib.request.build_opener = real_opener

        checks.ok(
            unreachable is not None and unreachable.code == "order_unreachable",
            "a dead socket refuses `order_unreachable` and says nothing was read and "
            "nothing was written",
            f"got {unreachable!r}",
        )
        checks.ok(
            unreachable is not None and cookie not in unreachable.message,
            "AND THE CREDENTIAL IS IN NO REFUSAL MESSAGE. Every string this module builds is "
            "composed from a status code, a header it chose, a constant, an order number or "
            "a trace id — never a vendor body and never the session, because a refusal that "
            "echoes a request is how a bearer instrument ends up in a log line",
        )
        checks.equal(
            [request.get_method() for request in seen],
            ["POST"],
            "exactly one request was built, and it was the search POST",
        )
        sent = seen[0]
        checks.equal(
            sent.get_header("Content-type"),
            "application/json",
            "THE BODY IS A PLAIN JSON DOCUMENT. D65's other host takes a form-encoded "
            "`model=<json>` field and this one does not — that is the first thing a reader "
            "will try to 'fix' this into, and it fails against the real API",
        )
        checks.ok(
            not sent.data.startswith(b"model=")
            and isinstance(json.loads(sent.data.decode("utf-8")), dict),
            "the bytes on the wire parse as a JSON object and carry no `model=` prefix",
            f"starts {sent.data[:24]!r}",
        )
        checks.equal(
            sent.get_header("Cookie"),
            cookie,
            "and the session reaches the socket — it goes to the host and to nothing else",
        )

        missing = None
        try:
            order_transport.search_body("LastThreeMonths", 25, 0, "")
        except order_transport.FetchRefusal as caught:
            missing = caught
        expired = None
        try:
            order_transport._check_status(401, {}, b"")
        except order_transport.FetchRefusal as caught:
            expired = caught
        rejected = None
        problem = json.dumps(
            {
                "type": "about:blank", "title": "Forbidden", "status": 403,
                "traceId": "0HN-9ZQ:00000123",
                "detail": "Cookie TCGAuthTicket_Production=SECRETVALUE was rejected",
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/problem+json"}
        try:
            order_transport._check_status(403, headers, problem)
        except order_transport.FetchRefusal as caught:
            rejected = caught
        checks.equal(
            [None if refused is None else refused.code
             for refused in (missing, expired, rejected)],
            ["order_seller_key_missing", "order_session_expired", "order_seller_key_rejected"],
            "A MISSING SELLER KEY, AN EXPIRED SESSION AND A REJECTED KEY ARE THREE CODES AND "
            "NOT ONE. 403 on this host is usually the REQUEST rather than the session — "
            "measured — so a client folding it into 'sign in again' sends the operator to "
            "re-copy a working cookie over a bug in this file, which is the exact defect D65 "
            "recorded on the other host",
        )
        checks.equal(
            order_transport.problem_note(headers, problem),
            " (traceId 0HN-9ZQ:00000123)",
            "problem+json is PARSED AND REDUCED TO ITS TRACE ID — the one field the operator "
            "would quote if they ever had to ask TCGplayer why a request was refused",
        )
        checks.ok(
            rejected is not None
            and "0HN-9ZQ:00000123" in rejected.message
            and "SECRETVALUE" not in rejected.message
            and "Forbidden" not in rejected.message,
            "AND THE TRACE ID IS CARRIED INTO THE MESSAGE WHILE THE BODY IS NOT — `title` "
            "and `detail` are dropped precisely because they are the fields most likely to "
            "quote the request, credential and all, back at a log",
            f"got {None if rejected is None else rejected.message!r}",
        )
    finally:
        urllib.request.build_opener = real_opener
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

# ------------------------------------------------------- T2b: the rubber stamps (D61, D63)


def check_shipping_stamps(checks: Checks) -> None:
    """`POST /shipping/batches/<batch>/stamps` — the Rubber Stamp fill, and its abstention.

    `docs/specs/order-pipeline.md`'s T2b states the Done in one sentence and this section is
    that sentence twice over: **a batch whose orders are in the ledger renders with its
    Rubber Stamp columns filled, and one whose orders are not renders them empty rather than
    guessing.** Both halves run against the SAME 331-order export in the SAME store, because
    a filled corner and an empty one are only meaningfully different side by side — a build
    that stamped everything and a build that stamped nothing each satisfy one of them alone.

    WHAT IS ASSERTED BEYOND THE TWO HALVES, EACH ONE A THING A PLAUSIBLE BUILD GETS WRONG:

      one label formula       what lands in `Rubber Stamp 1` is compared against
                              `cli/resolve.py:box_views(...).at(...).label` — the REPORTER's
                              walk, the other implementation of D58's counting space, and
                              deliberately not the `_Places` the route composed it with. A
                              second renderer here prints a card number nobody counting the
                              box arrives at, on a label somebody carries to a shelf.
      four corners is none    an order needing more positions than the label has corners gets
                              NONE. Slicing it to three reads as a complete pick list, which
                              is the wrong-shelf failure `pirateship.Parcel` refuses to
                              enforce a stamp LENGTH over, said one register up.
      pulled is not pending   an order already fully pulled is MATCHED and NOT STAMPED. D90
                              sells a copy as it is pulled and the box closes up behind it
                              (D58), so stamping where it was sends a hand to an index whose
                              occupant has changed.
      the press is idempotent two presses render byte-identical files, because a parcel's
                              stamps are SET on every press and never added to. A route that
                              appended would grow a fourth stamp on the second press and be
                              refused by `Parcel` outright on the third.
      matched is shipments    `matched` counts every shipment the ledger holds and
                              `stamped`/`unstamped` count PARCELS, because the file is the
                              parcel lane and nothing else. An envelope order in the ledger
                              is what tells the two apart, and it gets its pick location on
                              the SCREEN while appearing in no row of the CSV.
      nothing is persisted    the store's file list is identical across all of it. D61's rule
                              is what `pirateship.render` returning BYTES exists to make
                              possible, and this is the route that gave that module a reason
                              to open the store at all.

    ITS OWN `isolated_home`, load-bearing rather than hygienic for the reason
    `check_shipping_routes`' is: one of the assertions IS that the home did not change.
    """
    checks.note("")
    checks.note(
        "SHIPPING STAMPS — POST /shipping/batches/<batch>/stamps, the Rubber Stamp fill (T2b)"
    )

    fixture = SHIPPING_EXPORT.read_text("utf-8")
    export_rows = list(csv.reader(io.StringIO(fixture)))[1:]
    # Four parcel-lane orders off the committed export, picked by their own published value
    # rather than by row number — the fixture is real and its ordering is not this file's to
    # assume.
    lane = [row[0] for row in export_rows if Decimal(row[13]) >= Decimal("50")]
    # THE UNKNOWN ORDER IS THE FIRST PARCEL AND THE KNOWN ONE THE SECOND, DELIBERATELY. The
    # ledger holds these three in ingest order and the export lists them in its own, so a
    # build that zipped labels onto parcels positionally instead of looking each one up by
    # order id would hand THIS row's corners to the order above it. With the two the other
    # way round that misalignment lands empty-on-empty and passes; this ordering is what
    # makes the abstention below load-bearing rather than lucky.
    absent, known, packed, wide = lane[0], lane[1], lane[2], lane[3]
    # AND ONE ORDER FROM THE OTHER LANE. The import file is the parcel lane and nothing else,
    # but the SCREEN lists every shipment — so an envelope order the ledger holds is where
    # `matched` (shipments) and `stamped` (parcels) are told apart, and where the row's own
    # `stamp` is shown to reach an order that is in no file at all.
    envelope = next(
        routing.order
        for routing in shipping.route_all(shipping.parse(fixture.encode("utf-8")).shipments)
        if routing.lane == shipping.LANE_ENVELOPE
    )

    def stock(box: int, count: int, sku: str, prefix: str) -> None:
        """`count` identified copies of one SKU in `box`, each with its own capture id."""
        # THROUGH `capture_payload`, WHICH MINTS A PHOTOGRAPH PER CALL. The bytes were keyed
        # on the index within the box, so box 3's card 1 and box 4's card 1 sent the same
        # blob — and two cards cannot share one name since D172 (`cards_cid` is UNIQUE).
        for at in range(1, count + 1):
            capture_server.do_capture(capture_payload(box, capture_id=f"{prefix}{at}"))
        with Store().write() as snapshot:
            for at in range(1, count + 1):
                snapshot.inventory.record_identification(
                    f"{box}/{at}", name="Moonfall", number="198/219",
                    printed_total="219", confidence="high",
                )
                snapshot.inventory.cards[f"{box}/{at}"].sku = sku

    def sale(number: str, sku: str, quantity: int, placed: str) -> dict:
        return {
            "orders": [
                {
                    "source": "TCGplayer",
                    "number": number,
                    "placed_at": placed,
                    "lines": [{"sku": sku, "quantity": quantity}],
                }
            ]
        }

    with isolated_home() as home:
        # THREE SKUs so the three ledger orders cannot compete for one pool. `resolve_all`
        # shares copies across orders by design (that is the whole of its no-`resolve_one`
        # rule), and a shortfall engineered by this fixture would read here as a stamping bug.
        stock(3, 2, "9191486", "k")
        stock(4, 1, "9191487", "q")
        stock(5, 4, "9191488", "w")
        stock(6, 1, "9191489", "e")

        capture_server.do_order_ingest(sale(known, "9191486", 2, "2026-08-27T10:00:00.000+00:00"))
        capture_server.do_order_ingest(sale(packed, "9191487", 1, "2026-08-27T11:00:00.000+00:00"))
        capture_server.do_order_ingest(sale(wide, "9191488", 4, "2026-08-27T12:00:00.000+00:00"))
        capture_server.do_order_ingest(
            sale(envelope, "9191489", 1, "2026-08-27T13:00:00.000+00:00")
        )

        # `packed` is pulled to the end — D90's press, which sells every copy it records.
        capture_server.do_order_pull(
            {
                "source": "TCGplayer",
                "number": packed,
                "sku": "9191487",
                "targets": [{"box": 4, "index": 1, "capture_id": "q1"}],
            }
        )

        before = home_files(home)

        batch = answers(
            checks,
            lambda: shipping_routes.do_shipping_batches(
                {"name": "orders-shipping.csv", "content": fixture}
            ),
            "a batch is read out of the committed 331-order export",
        )
        if batch is None:
            return
        checks.ok(
            batch["stamps"] is None and all(row["stamp"] is None for row in batch["rows"]),
            "and it arrives UNSTAMPED — `stamps` null on the batch and `stamp` null on every "
            "row, which is the seam this route fills rather than a state it invents",
        )

        answer = answers(
            checks,
            lambda: shipping_routes.do_shipping_stamps(
                batch["batch"], {}, capture_server._order_stamps
            ),
            "POST /shipping/batches/<batch>/stamps answers over that batch",
        )
        if answer is None:
            return

        rows = {row["order"]: row for row in answer["rows"]}
        blob, _ = shipping_routes.do_shipping_file(batch["batch"], "pirateship-import.csv")
        written = {
            row[8]: row[9:12]
            for row in list(csv.reader(io.StringIO(blob.decode("utf-8"), newline="")))[1:]
        }

        # ------------------------------------------ half one: in the ledger, corners filled
        views = resolve.box_views(Store().read().inventory)
        expected = [views.get(3, join.BoxView()).at(3, at).label for at in (1, 2)]
        checks.equal(
            written.get(known),
            [expected[0], expected[1], ""],
            "HALF ONE OF T2b's DONE: an order the ledger holds renders with its Rubber Stamp "
            "columns FILLED — one corner per copy, in pick order, and the third left blank "
            "because this order wants two cards and not three. ONE LABEL FORMULA: the two "
            "strings are what `cli/resolve.py:box_views` renders for the same positions, "
            "which is the REPORTER's walk and the other implementation of D58's counting "
            "space, not the `_Places` this route composed them with",
        )
        checks.ok(
            all(", Section " in part and ", Card " in part for part in expected),
            "and that formula really did produce a pick instruction rather than an empty "
            "string both sides agreed on — a comparison of two nulls passes and stamps "
            "nothing",
            f"labels {expected!r}",
        )
        checks.equal(
            rows[known]["stamp"],
            " / ".join(expected),
            "the row carries the same two as ONE string, joined by ` / ` and never by the "
            "label's own ` · `. The screen field is singular and the format is not, and a "
            "join on ` · ` spells the boundary between two CARDS exactly like the boundary "
            "between a section and a card number — one address to a reader, and the wrong "
            "shelf to a hand",
        )

        # ----------------------------------- half two: not in the ledger, empty not guessed
        checks.equal(
            written.get(absent),
            ["", "", ""],
            "HALF TWO OF T2b's DONE: an order the ledger does not hold renders its three "
            "corners EMPTY rather than guessing. Nothing is inferred from the row — the "
            "export and the ledger agree about an order number or they do not",
        )
        checks.equal(
            rows[absent]["stamp"],
            None,
            "and its row's `stamp` is null, which is the same abstention on the wire",
        )

        # ------------------------------------------------- the three determinations, pinned
        checks.equal(
            written.get(packed),
            ["", "", ""],
            "AN ORDER ALREADY PULLED STAMPS NOTHING. D90 sells each copy as it is recorded "
            "and the box closes up behind it (D58), so the index it came out of now holds a "
            "DIFFERENT card — stamping where it WAS is a pick instruction to the wrong "
            "shelf. There is nothing left to pick, and empty corners say so",
        )
        checks.equal(
            written.get(wide),
            ["", "", ""],
            "AND AN ORDER WANTING FOUR COPIES STAMPS NOTHING EITHER: the label has three "
            "corners, there is no fourth to say `and one more`, and a pick list sliced to "
            "fit reads as a complete one. That is the wrong-shelf failure "
            "`pirateship.Parcel` refuses to enforce a stamp LENGTH over, said one register "
            "up — all three corners or none",
        )
        # ------------------------------------ the other lane: on the screen, in no file
        envelope_label = views.get(6, join.BoxView()).at(6, 1).label
        checks.equal(
            rows[envelope]["stamp"],
            envelope_label,
            "AN ENVELOPE-LANE ORDER GETS ITS PICK LOCATION ON THE SCREEN. The import file is "
            "the parcel lane and nothing else, but the operator still has to walk to that "
            "card — so the row carries the stamp even though no row of the CSV ever will",
        )
        checks.ok(
            envelope not in written,
            "and that order is in NO ROW OF THE FILE, which is `shipping.parcel_lane`'s "
            "abstention holding: the stamps route widened what the screen knows and moved "
            "nothing between lanes",
            f"{envelope!r} in the import",
        )
        checks.equal(
            answer["stamps"],
            {"ledger_orders": 4, "matched": 4, "stamped": 1, "unstamped": 125},
            "THE FOUR COUNTS AS ONE ABSOLUTE DICT. `matched` is 4 and `stamped` is 1, so an "
            "order that IS in the ledger and earned no corner stays distinguishable from one "
            "nobody has read in — collapsing those would make `we have never heard of this "
            "sale` and `this sale is already packed` the same figure on screen, and "
            "`ledger_orders` is what lets an empty ledger say so in its own words. `matched` "
            "counts SHIPMENTS and the other two count PARCELS, which is why 4 and 1 are not "
            "the same kind of number: the fourth match is the envelope order above, matched "
            "on the screen and in no file",
        )
        checks.equal(
            answer["stamps"]["stamped"] + answer["stamps"]["unstamped"],
            answer["parcel_count"],
            "and those two partition the PARCEL lane, because the file is the parcel lane "
            "and nothing else — which is what the screen's `N of parcel_count carry a pick "
            "location` divides by",
        )

        # ------------------------------------------------------------------- the properties
        second = answers(
            checks,
            lambda: shipping_routes.do_shipping_stamps(
                batch["batch"], {}, capture_server._order_stamps
            ),
            "a second press answers rather than refusing",
        )
        again, _ = shipping_routes.do_shipping_file(batch["batch"], "pirateship-import.csv")
        checks.equal(
            again,
            blob,
            "AND IT IS BYTE-IDENTICAL. Every parcel's `stamps` is SET on every press — "
            "empty where the order earned none — and never added to, so pressing twice "
            "re-asks the ledger rather than compounding what the first press wrote. A route "
            "that appended instead would grow a fourth stamp on the second press and be "
            "refused by `Parcel` outright on the third",
        )
        if second is not None:
            checks.equal(
                second["stamps"], answer["stamps"], "and it reports the same four counts"
            )
            checks.equal(
                second["file"]["bytes"],
                len(blob),
                "`file.bytes` is read off the re-rendered blob rather than remembered, so "
                "the size the screen offers is the size of the file it hands over",
            )

        checks.equal(
            sum(
                1
                for chunk in [c for c in blob.split(b"\r\n") if c.strip()][1:]
                if chunk.endswith(b',"","",""')
            ),
            125,
            "125 of the 126 parcel rows still end in three empty rubber stamps — present and "
            "empty rather than absent, which is what makes a column Pirate Ship's wizard can "
            "show the operator as blank",
        )

        shipping_refusal(
            checks,
            lambda: shipping_routes.do_shipping_stamps(
                batch["batch"], {"stamps": ["Box 3"]}, capture_server._order_stamps
            ),
            "field_not_settable",
            "A CALLER CANNOT HAND THE STAMPS IN. This route sets NOTHING out of its body — "
            "the corners come from the ledger and the one label formula — and a body that "
            "could carry a string would be a second way to write a pick location",
        )
        shipping_refusal(
            checks,
            lambda: shipping_routes.do_shipping_stamps(
                "not-a-batch-id", {}, capture_server._order_stamps
            ),
            "no_such_batch",
            "and an unknown batch refuses with the same sentence the download does, before "
            "the ledger is opened at all",
        )

        after = home_files(home)
        checks.equal(
            after,
            before,
            "NOTHING WAS PERSISTED BY ANY OF IT. Stamping re-reads the store, re-renders the "
            "import and hands it over without writing one file — D61's rule that buyer PII "
            "passes through and is never kept, asserted over the one route that gave that "
            "module a reason to reach the store at all",
        )


CHECKS = (
    check_shipping_lane,
    check_shipping_routes,
    check_shipping_stamps,
)
