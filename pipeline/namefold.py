"""The one name fold: typography is not identity (stdlib only, so any layer may import it).

Apostrophe look-alikes become `'` BEFORE NFKD, because NFKD turns U+00B4 into a space plus a
combining mark and the mark is then stripped with the accent. Dashes become `-`, accents go.
Case, whitespace and an embedded number are each caller's own business.
"""

from __future__ import annotations

import unicodedata

APOSTROPHES = "‘’ʼ´`"
DASHES = "‐‑‒–—―−"
_APOSTROPHES = str.maketrans({c: "'" for c in APOSTROPHES})
_DASHES = str.maketrans({c: "-" for c in DASHES})


def fold_name_typography(text) -> str:
    text = str(text or "").translate(_APOSTROPHES)
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return text.translate(_DASHES)
