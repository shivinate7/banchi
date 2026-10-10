## D-no-owner-quotes — Records keep no owner quotes

**The owner ruled it.** A record states each ruling in plain words. A record does not keep the owner's own words. A reader needs the ruling only. A quote adds tokens, and it goes stale with the ruling it described.

**What follows.** A new decision record holds no owner quote. It holds no line that introduces one, such as `The owner's words` or `verbatim:`. It holds no quoted owner message. Each ruling takes the fewest words. Style is not the aim.

**A rewrite drops words, never facts.** A cut pass rewrites one file in place, to the fewest words. It keeps every fact. Quotes in a record go when the cut pass rewrites that file. Until then, they stay.

**Why.** Records stay short and true. A reader spends the fewest tokens to learn a ruling. No quote outlives the ruling it described.

**Sibling rule.** D308, no dates in repo prose, has the same shape. It keeps a date out of prose. This rule keeps a quote out of records.

**Mechanism.** A docs-audit row refuses the markers above in decision records. It keeps a list of existing offenders that only shrinks. D280, offender lists replace pinned counts, sets that shape. The `no owner quotes` row of `make docs-audit` reads `docs/` and the list `scripts/no-owner-quotes-allow.json`. It fails on a new marker and on a stale entry.

**NOT MECHANIZED (the quoted-message half).** The `no owner quotes` row sees the markers `The owner's words` and `verbatim:`. A machine cannot tell an owner's message from another quote without reading intent, so a quote with no marker passes.
