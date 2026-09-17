## 1 — The reverse direction: five checks walk docs→code and never back

**One defect, five sites.** Each row proves everything *published* is consistent, and none can
see something real that was never published.

| check | what is invisible | live example |
|---|---|---|
| `tested_by reach` | a module a test exercises, carrying no claim | `store/cache.py` |
| `env vars` | a real variable documented nowhere | `PKMNSCAN_ALLOWED_ORIGINS` |
| `reason codes` | a reason the pipeline emits and nothing publishes | `rarity_claim_mismatch` |
| the game registry | a field whose consumer arrived, roster unstruck | five of six, silently |
| `governed_by` | the map may know less than the code, never more | three illustrative citations |

**THE BLOCKER IS ONE DECISION, AND IT IS THE SAME ONE FIVE TIMES.** Finding "a real
environment variable", "a reason rather than a ladder stage", "a module a test covers" each
needs a heuristic, and D16 puts a heuristic on a *blocking* row out of bounds — a row that
guesses and stops commits is how a gate gets switched off. The honest options are an
**advisory severity** or an **explicit roster the module publishes**.

**THE ROSTER OPTION IS NOW COSTED, BECAUSE IT WAS TAKEN FOR ONE OF THE FIVE (2026-09-05).**
`pipeline/variant.py:LADDER_REASONS` and `pipeline/routing.py:ROUTING_REASONS` publish the
thirteen review reasons, and `reason emissions` is a set comparison rather than a guess. The
whole cost was **two tuples and one runtime assertion** — no new concept, no severity change,
and `UNPRICEABLE_REASONS` had already made the idiom native to that file. Cheaper than the
paragraph above assumed.

**Two of the five are closed, by different means, and the difference is the useful part.**
`env names` needed no roster at all: `PKMNSCAN_*` is an exact naming convention, so the code
side is *already* enumerable and only the direction was missing. Reasons had no such
convention — `variant.py` spells finishes, ladder stages and reasons identically, eight of its
fourteen constants being non-reasons — so there the set had to be declared. **Ask which case
you have before reaching for a tuple:** where a convention already enumerates the set, a
roster is ceremony; where it does not, a roster is the only honest answer.

**What is still open is the other three**, and one of them may not want this shape at all: a
roster of "modules a test covers" would be a second place to maintain what `tested_by` already
says. **Fanning agents at these five separately produces five different answers to that one
question.** Settle it in a decision entry first; afterwards they are five independent edits in
five different modules.

**`tested_by`.** 39 claims, every cited test reaches the package it names. `store/cache.py` is
reached by T7 through a session, asserts nothing of its own, carries no claim, and
`docs/map.py` says so at the entry. `store/queues.py` was the second case until 2026-08-22,
when `check_queue_supersede` began asserting `queues.apply_run` and the entry gained the claim
it had earned — **nothing detected that; a human did.** Closing it means ruling that "a test
imports it" equals "a test covers it", which is what the row's own name refuses to say.

**`env vars`.** Walks docs→code only. Found 2026-08-23 by a test author, not by the audit:
`PKMNSCAN_ALLOWED_ORIGINS` — the allowlist standing between an unrelated browser tab and a
hard delete — existed for a day and a half documented nowhere while the row read "all real".
So did `PKMNSCAN_EXPORTS`. **The part worth keeping is the comment that sat above one of
them**, asserting in prose that the variable was documented the same day and that a blocking
check would fail a commit otherwise. Both halves false, the second about the very mechanism it
invoked. That comment is a correction now, kept where the next person looks.

**`reason codes`.** Four reconciliations, all starting from the labels or the doc. Found
2026-08-23 live: `rarity_claim_mismatch` was defined in `pipeline/variant.py`, emitted by the
ladder, carried by neither `REASON_LABELS` nor `docs/DESIGN.md` — and the row read **green**.
Had it fired, the queue would have drawn a bare machine string, the exact outcome the two-size
label rule exists to prevent. The fifth direction needs telling a reason from a ladder stage
by walking the AST for `Resolution(stage=REVIEW, reason=NAME)` — deterministic and
blocking-grade, but coupled to that call shape; or the roster `pipeline/routing.py` already
half has in `UNPRICEABLE_REASONS`. The row reads **14 enumerated, 14 labelled** on 2026-08-30:
twelve when the defect was live, thirteen after the hand repair, fourteen now. Every move was
made correctly by a session that remembered.

**The registry.** Four audit rows sweep `pipeline/games.py` and every one compares it against
the *exports*. Nothing compares it against the *code*, so a field can be perfectly consistent
and entirely inert — **and can stop being inert without anything saying so.** Re-walked
2026-08-30:

| field | 2026-08-23 | 2026-08-30 |
|---|---|---|
| `located`, `card_aspect`, `crop_bands` | closed | closed |
| `finish_by_rarity` | nothing | **`app/src/CaptureScreen.tsx` unions it over the claimed rarities. D23's chip narrowing is built** |
| `product_line` | nothing | **`pipeline/join.py`, `cli/resolve.py`, `pipeline/pricehistory.py`. D25's "real reader" is built** |
| `product_line_rarities` | nothing | **`pipeline/join.py` narrows a claimant's rows by it** |
| `rarities` | emptiness guard only | **validated at `identify/sidecar.py`, checked at `server/capture_server.py`, rendered as the stack claim** |
| `prompt` (per-card) | nothing | **still nothing — see cluster 3** |

D22 says "a field no consumer reads is a field nothing keeps honest". The correction is that
nothing kept the roster of unread fields honest either.

**`governed_by`.** Enforced one way: the map may not know less than the code's own citations,
and may say anything beyond them. Three files are listed under decisions they do not implement
— `scripts/docs-audit.py` names `D2` in a comment about citations, `scripts/decision-context.py`
names `D2` and `D3` as worked examples. Each is labelled as such in the map; the expensive side
would be the rule guessing which citations count.

---
