"""The Intelligent Mail barcode, encoded here rather than bought from anybody.

USPS-B-3200 Rev H, 2015-04-20, steps 1 through 6 — the whole encoder, from four data
fields to the 65-bar string a barcode font prints. It is a PURE FUNCTION over digits.
No network, no account, no credential, no per-piece fee, and nothing in this module can
spend money. That is the finding this file exists to make concrete: the IMb itself is
arithmetic, and every service that sells PWE tracking sells the platform around it.

WHAT THIS MODULE IS NOT. It is not tracking. A barcode on an envelope produces scan
events only if USPS mail processing equipment reads it AND the Mailer ID it carries is
registered to somebody's Informed Visibility (IV-MTR) subscription. Both of those are
account facts this repo cannot hold and this module deliberately does not model. See
`docs/specs/order-pipeline.md` for what is still owed before a scan ever reaches here.

THE MAILER ID IS NOT OURS TO INVENT. `mailer_id` is an argument with no default on
purpose. A MID is assigned by USPS through the Business Customer Gateway, it identifies
the mailer to the postal system, and a made-up one either belongs to somebody else or to
nobody — the first is somebody else's scan data, the second is an envelope that is simply
never reported. There is no test value USPS publishes for live mail. The four vectors in
the harness use the SPEC'S OWN example MID, which is why they may only ever be a test.

    barcode ID    2 digits, and the second is limited to 0-4 (spec 2.2.1.2 B)
    service type  3 digits — the STID, which is what asks for IV-MTR. WHICH STID IS AN
                  ACCOUNT QUESTION, NOT AN ENCODING ONE: this module writes the three
                  digits it is handed and has no opinion. STID 300 is First-Class,
                  Basic/nonautomation, no address correction and NO tracing, so a piece
                  carrying it is correctly encoded and reports nothing.
    mailer ID     6 or 9 digits, assigned by USPS
    serial        9 digits behind a 6-digit MID, 6 digits behind a 9-digit MID — the two
                  always sum to 15, which is what makes the tracking code 20 digits
    routing       the delivery point ZIP: 0, 5, 9 or 11 digits, and 0 is a real choice
                  rather than a missing value

THE SERIAL IS STATE AND THIS MODULE DOES NOT HOLD IT. A serial must be unique per piece
within a MID or two envelopes report as one, which is a wrong answer that looks exactly
like a right one. Allocating it belongs beside the order ledger, not in an encoder.

Six steps, kept as six functions so a wrong one is named by the test that fails:

    1  _routing_value + _payload      the four fields become one 102-bit integer
    2  _crc11                          the frame check sequence, polynomial 0xF35
    3  _codewords                      base 636 / 1365 / 659, ten of them, J to A
    4  _orient                         J carries orientation, A carries FCS bit 10
    5  _characters                     codeword to 13-bit character, then FCS negation
    6  _bars                           130 bits become 65 bars, via BAR_MAP

The two character tables are GENERATED at import by the spec's own InitializeNof13Table
rather than transcribed. Table 19 is 1,287 rows and Table 20 is 78; a transcription of
1,365 hex values is 1,365 chances to typo one, and the generator is twenty lines whose
output the harness checks against the spec's published anchors.

BAR_MAP is transcribed, because nothing generates it. It is Table 22, 65 rows, and it is
the one place in this file where a silent typo produces a barcode that scans as a
DIFFERENT piece rather than as nothing. The four end-to-end vectors in `harness/tests/
t10_imb.py` are what stand under it: all four share one tracking code and differ only in
routing length, so they exercise every routing branch against a published answer.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

__all__ = ["ImbRefused", "tracking_code", "encode", "bars_to_letters"]


class ImbRefused(Exception):
    """A field that cannot be encoded. Never a silent coercion: a padded, truncated or
    guessed field produces a well-formed barcode for the wrong mailpiece."""


# ---------------------------------------------------------------------------------------
# Table 22: Bar to Character Mapping. Bar 1 is leftmost. Each row is the character and bit
# that supply this bar's DESCENDER, then the character and bit that supply its ASCENDER.
# ---------------------------------------------------------------------------------------

BAR_MAP: Tuple[Tuple[str, int, str, int], ...] = (
    ("H", 2, "E", 3),   ("B", 10, "A", 0),  ("J", 12, "C", 8),  ("F", 5, "G", 11),
    ("I", 9, "D", 1),   ("A", 1, "F", 12),  ("C", 5, "B", 8),   ("E", 4, "J", 11),
    ("G", 3, "I", 10),  ("D", 9, "H", 6),   ("F", 11, "B", 4),  ("I", 5, "C", 12),
    ("J", 10, "A", 2),  ("H", 1, "G", 7),   ("D", 6, "E", 9),   ("A", 3, "I", 6),
    ("G", 4, "C", 7),   ("B", 1, "J", 9),   ("H", 10, "F", 2),  ("E", 0, "D", 8),
    ("G", 2, "A", 4),   ("I", 11, "B", 0),  ("J", 8, "D", 12),  ("C", 6, "H", 7),
    ("F", 1, "E", 10),  ("B", 12, "G", 9),  ("H", 3, "I", 0),   ("F", 8, "J", 7),
    ("E", 6, "C", 10),  ("D", 4, "A", 5),   ("I", 4, "F", 7),   ("H", 11, "B", 9),
    ("G", 0, "J", 6),   ("A", 6, "E", 8),   ("C", 1, "D", 2),   ("F", 9, "I", 12),
    ("E", 11, "G", 1),  ("J", 5, "H", 4),   ("D", 3, "B", 2),   ("A", 7, "C", 0),
    ("B", 3, "E", 1),   ("G", 10, "D", 5),  ("I", 7, "J", 4),   ("C", 11, "F", 6),
    ("A", 8, "H", 12),  ("E", 2, "I", 1),   ("F", 10, "D", 0),  ("J", 3, "A", 9),
    ("G", 5, "C", 4),   ("H", 8, "B", 7),   ("F", 0, "E", 5),   ("C", 3, "A", 10),
    ("G", 12, "J", 2),  ("D", 11, "B", 6),  ("I", 8, "H", 9),   ("F", 4, "A", 11),
    ("B", 5, "C", 2),   ("J", 1, "E", 12),  ("I", 3, "G", 6),   ("H", 0, "D", 7),
    ("E", 7, "H", 5),   ("A", 12, "B", 11), ("C", 9, "J", 0),   ("G", 8, "F", 3),
    ("D", 10, "I", 2),
)

CHARACTER_NAMES = "ABCDEFGHIJ"

# The four bar states, as the letters the USPS barcode fonts take.
FULL, ASCENDER, DESCENDER, TRACKER = "F", "A", "D", "T"


def _reverse13(value: int) -> int:
    """The spec's ReverseUnsignedShort over 16 bits, then >> 3 — i.e. reverse 13 bits."""
    reverse = 0
    for _ in range(16):
        reverse = (reverse << 1) | (value & 1)
        value >>= 1
    return reverse >> 3


def _nof13(n: int, length: int) -> List[int]:
    """InitializeNof13Table, Table 18. Every 13-bit value with exactly `n` bits set,
    ordered so that a value and its bit-reverse are adjacent and the PALINDROMES sit at
    the end. That ordering is the table — an index into it is a codeword, so a table
    built in any other order encodes every character wrongly."""
    table = [0] * length
    lower, upper = 0, length - 1
    for count in range(8192):
        if bin(count).count("1") != n:
            continue
        reverse = _reverse13(count)
        if reverse < count:
            continue
        if reverse == count:
            table[upper] = count
            upper -= 1
        else:
            table[lower] = count
            table[lower + 1] = reverse
            lower += 2
    if lower != upper + 1:  # pragma: no cover - the spec's own FALSE return
        raise ImbRefused(f"{n}-of-13 table did not close: {lower} != {upper + 1}")
    return table


TABLE_5_OF_13 = _nof13(5, 1287)
TABLE_2_OF_13 = _nof13(2, 78)


def _digits(value: str, field: str) -> str:
    text = str(value)
    if not text.isdigit():
        raise ImbRefused(f"{field} must be digits only, got {value!r}")
    return text


def tracking_code(barcode_id: str, service_type: str, mailer_id: str, serial: str) -> str:
    """The 20-digit tracking code, with every length rule enforced rather than padded.

    The spec says a mailer "shall add leading or trailing zeroes to achieve the correct
    field length" — that is the CALLER's job and not this function's. Padding a short
    serial here would silently turn serial 7 into 000007 for one call and 7 into a
    different piece for another, and the two envelopes would report as one.
    """
    barcode_id = _digits(barcode_id, "barcode_id")
    service_type = _digits(service_type, "service_type")
    mailer_id = _digits(mailer_id, "mailer_id")
    serial = _digits(serial, "serial")

    if len(barcode_id) != 2:
        raise ImbRefused(f"barcode_id must be 2 digits, got {barcode_id!r}")
    if barcode_id[1] not in "01234":
        raise ImbRefused(
            f"the second barcode_id digit is limited to 0-4, got {barcode_id[1]!r} — "
            "step 1 multiplies it by 5, so a 5 through 9 there overflows into the digit "
            "beside it and encodes a different piece"
        )
    if len(service_type) != 3:
        raise ImbRefused(f"service_type (STID) must be 3 digits, got {service_type!r}")
    if len(mailer_id) not in (6, 9):
        raise ImbRefused(f"mailer_id must be 6 or 9 digits, got {mailer_id!r}")

    wanted = 9 if len(mailer_id) == 6 else 6
    if len(serial) != wanted:
        raise ImbRefused(
            f"a {len(mailer_id)}-digit mailer_id takes a {wanted}-digit serial, got "
            f"{serial!r} ({len(serial)} digits) — the two sum to 15 by construction"
        )
    return barcode_id + service_type + mailer_id + serial


def _routing_value(routing: str) -> int:
    """Table 4. Zero digits is a real answer — a piece with no delivery point ZIP — and
    is not the same as a missing one, which is why this refuses every other length."""
    routing = _digits(routing, "routing") if routing else ""
    if len(routing) == 0:
        return 0
    if len(routing) == 5:
        return int(routing) + 1
    if len(routing) == 9:
        return int(routing) + 100000 + 1
    if len(routing) == 11:
        return int(routing) + 1000000000 + 100000 + 1
    raise ImbRefused(
        f"routing must be 0, 5, 9 or 11 digits, got {len(routing)} ({routing!r})"
    )


def _payload(tracking: str, routing: str) -> int:
    """Step 1. The routing value, then the 20 tracking digits folded in — the second
    digit at base 5 and every other at base 10."""
    value = _routing_value(routing)
    value = value * 10 + int(tracking[0])
    value = value * 5 + int(tracking[1])
    for digit in tracking[2:]:
        value = value * 10 + int(digit)
    return value


def _crc11(payload: int) -> int:
    """Step 2, Table 17. The 13-byte array the C routine takes, with the leftmost two
    bits of the leftmost byte excluded."""
    data = payload.to_bytes(13, "big")
    polynomial, fcs = 0x0F35, 0x07FF

    byte = (data[0] << 5) & 0xFFFF
    for _ in range(2, 8):
        fcs = ((fcs << 1) ^ polynomial) if (fcs ^ byte) & 0x400 else (fcs << 1)
        fcs &= 0x7FF
        byte = (byte << 1) & 0xFFFF

    for index in range(1, 13):
        byte = (data[index] << 3) & 0xFFFF
        for _ in range(8):
            fcs = ((fcs << 1) ^ polynomial) if (fcs ^ byte) & 0x400 else (fcs << 1)
            fcs &= 0x7FF
            byte = (byte << 1) & 0xFFFF
    return fcs


def _codewords(payload: int) -> List[int]:
    """Step 3, Table 7. J is base 636, B through I are base 1365, and what is left is A."""
    value = payload
    words = [0] * 10
    words[9] = value % 636
    value //= 636
    for index in range(8, 0, -1):
        words[index] = value % 1365
        value //= 1365
    words[0] = value
    if not 0 <= words[0] <= 658:
        raise ImbRefused(f"codeword A out of range: {words[0]} (0-658)")
    return words


def _orient(words: Sequence[int], fcs: int) -> List[int]:
    """Step 4. J doubles to carry orientation; A takes FCS bit 10."""
    words = list(words)
    words[9] *= 2
    if fcs & 0x400:
        words[0] += 659
    return words


def _characters(words: Sequence[int], fcs: int) -> Dict[str, int]:
    """Step 5. Codeword to 13-bit character, then Table 21's negation: FCS bit 0 negates
    character A and bit 9 negates character J."""
    characters: Dict[str, int] = {}
    for index, word in enumerate(words):
        if word <= 1286:
            character = TABLE_5_OF_13[word]
        elif word <= 1364:
            character = TABLE_2_OF_13[word - 1287]
        else:
            raise ImbRefused(f"codeword {CHARACTER_NAMES[index]} out of range: {word}")
        if fcs & (1 << index):
            character ^= 0x1FFF
        characters[CHARACTER_NAMES[index]] = character
    return characters


def _bars(characters: Dict[str, int]) -> str:
    """Step 6. Each bar takes a descender bit from one character and an ascender bit from
    another; the two together pick one of four states."""
    letters = []
    for desc_char, desc_bit, asc_char, asc_bit in BAR_MAP:
        descender = (characters[desc_char] >> desc_bit) & 1
        ascender = (characters[asc_char] >> asc_bit) & 1
        if descender and ascender:
            letters.append(FULL)
        elif ascender:
            letters.append(ASCENDER)
        elif descender:
            letters.append(DESCENDER)
        else:
            letters.append(TRACKER)
    return "".join(letters)


def encode(tracking: str, routing: str = "") -> str:
    """The 65-letter barcode string for a 20-digit tracking code and a routing ZIP.

    `tracking` is what `tracking_code` returns. Passing a hand-built 20-digit string is
    allowed and is checked for length and shape here, but the field rules that make it
    the RIGHT twenty digits live in `tracking_code` and are not re-derivable from the
    concatenation.
    """
    tracking = _digits(tracking, "tracking")
    if len(tracking) != 20:
        raise ImbRefused(f"tracking code must be 20 digits, got {len(tracking)}")
    if tracking[1] not in "01234":
        raise ImbRefused(
            f"the second tracking digit is limited to 0-4, got {tracking[1]!r}"
        )
    payload = _payload(tracking, routing)
    fcs = _crc11(payload)
    words = _orient(_codewords(payload), fcs)
    return _bars(_characters(words, fcs))


def bars_to_letters(bars: str) -> str:
    """The barcode string, spaced for a human reading it off a screen. Never printed —
    the font takes the unspaced 65."""
    return " ".join(bars[i:i + 5] for i in range(0, len(bars), 5))
