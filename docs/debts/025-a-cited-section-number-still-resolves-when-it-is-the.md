## 25 — A cited section number still resolves when it is the wrong section, and no check can read what a sentence is about

**No work proposed.** Seven citations in this tree named section 11 for a record that has only
ever been in section 8. They were repaired by hand on 2026-09-11 under `D149`.
This section exists so the next session does not re-derive whether a guard was possible: it was
looked for, measured, and declined.

**The failure is that a stale or wrong section number STILL RESOLVES.** Every one of the seven
pointed at a real section that exists and reads plausibly — section 11 is the capture server's
concurrency debt, which is a coherent thing for a CI comment to cite and simply not what the
sentence was about. That is `docs/map.py`'s own rule about step ids arriving in this file:
*"a renumber leaves every one pointing at a real step that is not the one meant — which nothing
can detect, because a stale number still resolves."*

**It was a propagated wrong citation, not a renumber, and the history is unambiguous.** The flake
record entered this file in `86e70c2` (2026-09-11) already under section 8, and section 11 was
already the capture-server section on that same commit. Across every revision of this file,
section 11 has only ever carried two wordings of one subject — `The capture server has no bound
on concurrency…` and today's `…bounds concurrent requests, not threads…` — and the flake record
has only ever been in section 8. The first wrong citation and three of its copies landed in ONE
commit (`e06eb8a`, D136) across three files; `bc39785` (D141) then copied it into two more, and
the Makefile took it from the same source. **So no audit row would have caught this by watching
for a renumber**, which is the guard that would otherwise have been the obvious one to build.

**This file does not renumber, and section 15 is the proof.** It was CLOSED on 2026-09-07
(`db1903c`, D120 answered it) by deleting the heading and leaving 16 to 24 where they were. The
hole is deliberate, it is the same discipline `docs/map.py` applies to build-order ids, and it
means the renumber hazard is structurally absent here rather than merely unobserved.

### Why no `docs-audit` row, measured rather than argued

The shape a row would have to take is *the section a sentence cites must be the section that
section is about*, and deciding what a sentence is about is semantics. The nearest mechanical
proxy is the one this file's own section 1 already establishes for `server concurrency`: require
an ATTRIBUTED form — compare a phrase the citation quotes against the section it names, rather
than asking whether a bare number appears somewhere in it. **Measured over all 38 citations of a
`docs/DEBTS.md` section in this tree, across 15 files and 11 distinct sections:**

| | count |
|---|---|
| citations carrying any double-quoted span | 4 |
| of those, a span that is really a quotation of the section | 2 |
| of those, quotations that resolve TRUE against the section named | 1 |
| wrong citations the rule would have caught, of the seven | 1 |

The other three quoted spans are a code flag (`--shard=N/3 --workers=1`), an f-string fragment
(`can — see §11.`) and a slice of this very checker's own error text — all
three would be reported as broken citations, so the rule arrives at **one catch and three false
alarms.** The prose in this repo cites by narrating, not by quoting, and a row that is wrong three
times for every time it is right is one the next session turns off.

**And the most-repeated distinctive token cannot be matched literally at all.** Five of the seven
said `one-in-thirteen`; this file spells it `1 in 13`, in a table cell. A containment test on that
phrase fails against section 8 — the correct section — so the naive rule would flag the REPAIRED
text too.

**The remaining option is a hand-maintained (phrase → section) list**, which is a claim with a
reader that is itself unread — section 4's subject exactly — and which would have to be extended
by hand for every future pair of sections. That is the thing this file calls half-working, and it
is not built.

**What IS mechanically true and worth keeping**: all 38 citations name a section that exists, and
`_debts_section` can now address every live section in this file. It could not until this entry:
sections 20 to 24 were written `## N.` where that helper matches `## N — `, so five of the file's
twenty-three live sections were invisible to the one reader the audit has for it, and any check
built on it would have read them as absent. The headings were normalized in the same change and
**`make docs-audit`'s `debts headings` row is what stops the next one being written that way** —
it refuses a heading that shape and a section number used twice, because both make a section
that silently does not exist rather than one that fails. Mutation-tested, four arms: the dotted
form, a duplicate number, a number with no title, and an en-dash for the em-dash.

**That row is a guard over this file's SHAPE and not over what a citation MEANS**, and the gap
above is still open. The distinction is the whole of this section: a heading either parses or it
does not, which is decidable; whether a sentence is about the capture server or about a flake is
not.

**The number may move, and nothing allocates it.** 25 is what was next on 2026-09-11 — renumber
it rather than another branch's, the way this file's header already rules.
