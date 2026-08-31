"""The code-card track: deterministic QR decoding, the code ledger, the product table.

ITS OWN PACKAGE, AND D14 IS THE REASON RATHER THAN TIDINESS. "Two tracks, one rig" shares
the physical rig, the capture server, the capture app shell and the photo storage, and
shares NOTHING downstream: schemas, identification, sales channel and fulfilment are the
codes track's own. `identify/` is the singles track's identification — a paid vision call
against a prompt profile — and the primary path here is the opposite of that in every
respect that matters: local, deterministic, free, and correct or loudly absent rather than
confident. Putting a decoder that never calls a model inside the package whose docstring
opens "submit, wait, collect, cache" would make one package mean two things.

WHAT IS NOT HERE IS AS DELIBERATE. There is no second inventory, no second store and no
second capture path. A code card is captured by the same server into the same
`inventory.json` as every other card, carrying `game: pokemon_code`; D24's `located: False`
is the whole of the schema difference and it is one registry flag. This package reads that
store and writes the ledger beside it — it does not own a card.
"""
