"""T10 — The Intelligent Mail barcode encoder, against USPS-B-3200's own four examples.

NEW 2026-09-03. It is its own test rather than a section of T7 because what it checks is
a different KIND of claim from everything else in this harness: not "does this repo agree
with itself" but "does this repo agree with a published external specification". Every
expected value below is transcribed from USPS-B-3200 Rev H, Appendix C, Tables 13-16 —
the Postal Service's own worked examples, with their own answers.

THE FOUR VECTORS SHARE ONE TRACKING CODE AND DIFFER ONLY IN ROUTING LENGTH. That is the
spec's design and it is why they are worth all four: routing is the field with four legal
shapes (0, 5, 9, 11 digits) and four different conversions, so running only the last one
would leave three branches of `_routing_value` asserted by nothing.

EVERY STEP IS CHECKED, NOT ONLY THE ANSWER. A wrong CRC and a wrong bar map both produce
65 wrong letters, and a test that compares only the final string says "the encoder is
broken" without saying which of six steps broke. The intermediates are published in the
same tables, so asserting them is free.

THE BAR MAP IS THE ONE TABLE NOTHING GENERATES, and `bar map is a bijection` is the check
that matters most in this file. Ten characters of thirteen bits is 130 bit positions;
sixty-five bars with a descender and an ascender each is 130 slots. Every position must be
used exactly once. A transcription typo that writes ("H", 2) where ("H", 3) belongs leaves
one position used twice and one unused — and the four vectors would very likely still
catch it, but only as "the answer is wrong". This names it.

WHAT A GREEN T10 DOES NOT MEAN. It does not mean an envelope gets scanned. The encoder is
arithmetic and this test is arithmetic about arithmetic; a barcode reports nothing unless
the Mailer ID in it is registered to an Informed Visibility subscription and the piece
runs on mail processing equipment. No barcode from this module has ever been printed, and
no envelope carrying one has ever been mailed. `docs/specs/order-pipeline.md` holds that
gap and this test cannot close it.
"""

from __future__ import annotations

from harness.tests import Checks, Result
from pipeline import imb

NAME = "T10"
DESCRIPTION = "The Intelligent Mail barcode encoder, against USPS-B-3200's four examples"
PASS_CRITERIA = (
    "all four of USPS-B-3200 Appendix C's examples reproduce byte for byte at every step "
    "— binary data, FCS, codewords, characters and the 65-bar string; the bar map uses "
    "each of the 130 character-bit positions exactly once; and every field-length rule "
    "refuses rather than pads"
)

# USPS-B-3200 Rev H, Appendix C. One tracking code, four routing codes.
#   barcode ID 01, service type 234, mailer ID 567094, serial 987654321
TRACKING = "01234567094987654321"

VECTORS = (
    # routing, binary data (hex), FCS, codewords (step 3), 65-bar string
    (
        "",
        "00000000001122103B5C2004B1",
        0x051,
        [0, 0, 0, 0, 559, 202, 508, 451, 124, 17],
        "ATTFATTDTTADTAATTDTDTATTDAFDDFADFDFTFFFFFTATFAAAATDFFTDAADFTFDTDT",
    ),
    (
        "01234",
        "0000000D138A87BAB5CF3804B1",
        0x065,
        [0, 0, 15, 14, 290, 567, 385, 48, 388, 333],
        "DTTAFADDTTFTDTFTFDTDDADADAFADFATDDFTAAAFDTTADFAAATDFDTDFADDDTDFFT",
    ),
    (
        "012345678",
        "000202BDC097711204D21804B1",
        0x606,
        [0, 110, 1113, 1363, 198, 413, 470, 468, 1333, 513],
        "ADFTTAFDTTTTFATTADTAAATFTFTATDAAAFDDADATATDTDTTDFDTDATADADTDFFTFA",
    ),
    (
        "01234567891",
        "016907B2A24ABC16A2E5C004B1",
        0x751,
        [14, 787, 607, 1022, 861, 19, 816, 1294, 35, 301],
        "AADTFFDFTDADTAADAATFDTDDAAADDTDTTDAFADADDDTFFFDDTTTADFAAADFTDAADA",
    ),
)

# Table 16's step 5, both halves — the only vector for which the spec prints the
# characters, which is why the character assertions ride on the fourth one alone.
CHARACTERS_RAW = [0x1234, 0x085C, 0x08E4, 0x0B06, 0x1922,
                  0x1740, 0x0839, 0x1200, 0x0DC0, 0x04D4]
CHARACTERS_NEGATED = [0x0DCB, 0x085C, 0x08E4, 0x0B06, 0x06DD,
                      0x1740, 0x17C6, 0x1200, 0x123F, 0x1B2B]


def run() -> Result:
    c = Checks()

    # ---- Step 6, the whole chain, on all four ---------------------------------------
    for routing, _, _, _, expected in VECTORS:
        c.equal(imb.encode(TRACKING, routing), expected,
                f"the 65-bar string for routing {routing or '(none)'} is the spec's")

    # ---- Steps 1 to 3, named so a break says which one ------------------------------
    for routing, binary_hex, fcs, words, _ in VECTORS:
        payload = imb._payload(TRACKING, routing)
        label = routing or "(none)"
        c.equal(payload.to_bytes(13, "big").hex().upper(), binary_hex,
                f"step 1 — the 13-byte binary data for routing {label}")
        c.equal(imb._crc11(payload), fcs,
                f"step 2 — the 11-bit FCS for routing {label} is 0x{fcs:03X}")
        c.equal(imb._codewords(payload), words,
                f"step 3 — the ten codewords for routing {label}")

    # ---- Steps 4 and 5, on the vector whose characters the spec prints ---------------
    payload = imb._payload(TRACKING, "01234567891")
    fcs = imb._crc11(payload)
    oriented = imb._orient(imb._codewords(payload), fcs)
    c.equal(oriented, [673, 787, 607, 1022, 861, 19, 816, 1294, 35, 602],
            "step 4 — J doubles for orientation and A takes FCS bit 10")

    negated = imb._characters(oriented, fcs)
    c.equal([negated[name] for name in imb.CHARACTER_NAMES], CHARACTERS_NEGATED,
            "step 5b — the ten characters after Table 21's FCS negation")
    c.equal([imb._characters(oriented, 0)[name] for name in imb.CHARACTER_NAMES],
            CHARACTERS_RAW,
            "step 5a — and the same ten before it, which is what isolates the negation "
            "from the lookup")

    # ---- The generated character tables, against the spec's published anchors --------
    c.equal(len(imb.TABLE_5_OF_13), 1287, "Table 19 generates 1,287 rows")
    c.equal(len(imb.TABLE_2_OF_13), 78, "Table 20 generates 78 rows")
    c.equal(imb.TABLE_5_OF_13[0], 0b0000000011111, "5-of-13 codeword 0 (Figure 3)")
    c.equal(imb.TABLE_5_OF_13[1286], 0b0000111110000, "5-of-13 codeword 1286 (Figure 3)")
    c.equal(imb.TABLE_5_OF_13[673], 0x1234, "5-of-13 codeword 673 is character A (Figure 3)")
    c.equal(imb.TABLE_2_OF_13[7], 0x1200,
            "2-of-13 codeword 7 is character H — codeword 1294 less 1287 (Figure 3)")
    c.ok(all(bin(v).count("1") == 5 for v in imb.TABLE_5_OF_13),
         "every 5-of-13 entry has exactly five bits set")
    c.ok(all(bin(v).count("1") == 2 for v in imb.TABLE_2_OF_13),
         "every 2-of-13 entry has exactly two bits set")
    c.equal(len(set(imb.TABLE_5_OF_13)) + len(set(imb.TABLE_2_OF_13)), 1287 + 78,
            "and no value appears twice in either table")

    # ---- The bar map, the one table nothing generates --------------------------------
    c.equal(len(imb.BAR_MAP), 65, "the bar map has one row per bar")
    positions = []
    for desc_char, desc_bit, asc_char, asc_bit in imb.BAR_MAP:
        positions.append((desc_char, desc_bit))
        positions.append((asc_char, asc_bit))
    every = {(name, bit) for name in imb.CHARACTER_NAMES for bit in range(13)}
    c.equal(sorted(set(positions)), sorted(every),
            "the bar map is a bijection: all 130 character-bit positions, each used once")
    c.equal(len(positions), len(set(positions)),
            "and none of them is used twice — the check a transcription typo trips first")

    # ---- The field rules refuse rather than pad --------------------------------------
    c.equal(imb.tracking_code("01", "234", "567094", "987654321"), TRACKING,
            "the four fields compose the spec's own tracking code")
    c.equal(imb.tracking_code("01", "234", "567094321", "987654"), TRACKING[:5] + "567094321987654",
            "a 9-digit mailer ID takes a 6-digit serial, and the total is still 20")

    c.raises(imb.ImbRefused,
             lambda: imb.tracking_code("05", "234", "567094", "987654321"),
             "a second barcode-ID digit above 4 refuses — step 1 multiplies it by 5")
    c.raises(imb.ImbRefused,
             lambda: imb.tracking_code("01", "234", "567094", "98765"),
             "a short serial refuses rather than being zero-padded into another piece")
    c.raises(imb.ImbRefused,
             lambda: imb.tracking_code("01", "234", "5670", "987654321"),
             "a mailer ID that is neither 6 nor 9 digits refuses")
    c.raises(imb.ImbRefused,
             lambda: imb.tracking_code("01", "23", "567094", "987654321"),
             "a 2-digit STID refuses")
    c.raises(imb.ImbRefused,
             lambda: imb.tracking_code("01", "23A", "567094", "987654321"),
             "a non-digit anywhere refuses")
    c.raises(imb.ImbRefused, lambda: imb.encode(TRACKING, "1234"),
             "a 4-digit routing code refuses — 0, 5, 9 and 11 are the only legal shapes")
    c.raises(imb.ImbRefused, lambda: imb.encode(TRACKING[:19], ""),
             "a 19-digit tracking code refuses")

    # A serial that differs by one digit must produce a different barcode. The point of
    # the field is uniqueness, so this is the property the whole scheme rests on.
    one = imb.encode(imb.tracking_code("01", "300", "567094", "000000001"), "20500")
    two = imb.encode(imb.tracking_code("01", "300", "567094", "000000002"), "20500")
    c.ok(one != two, "two serials one apart encode to different barcodes")
    c.equal(len(one), 65, "and a real-shaped call still returns 65 bars")

    return c.result()
