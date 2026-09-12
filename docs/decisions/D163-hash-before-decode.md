## D163 — The cache is keyed by the digest, so the digest is what the press computes first

**`identify` decoded every photograph in the directory before it asked the store whether it already owned the answer.** `cli/cmd_identify.py` ran `geometry.detect_card` and
`images.prepare` over the whole capture directory, and consulted the cache afterwards. The
cache's own question is `Cache.reusable(key, photo_sha256)` — a position and a sha256 of the
bytes on disk — and `images.prepare` computed that sha256 *before opening the image*, on its
way past. **So the decode was never an input to the question being asked.** It was pure
waste on every card the store already had an answer for.

**The order is hash → cache → refuse → prepare.** Every photograph is hashed; the store is
asked what it owns; a card naming a game no registry entry answers is refused by name; and
only what is left is cropped and downscaled.

## What it is worth, measured on this machine

Box 4's own 678 JPEGs at the operator's flags (`--crop --max-edge 1200`), n=60, page cache
warmed for both arms first so neither gets the cold-read penalty:

| | per photograph |
|---|---|
| `sha256_of` | **0.687 ms** (median 0.690) |
| `detect_card` + `prepare` | **114.96 ms** (median 112.46) |
| ratio | **167x** |

The last real press, `2026-09-12-box4-01`, walked **678 photographs and submitted 214** —
464 of them cache hits. One dry-run leg of that directory, against a copy of the operator's
own store with those 214 cache rows removed to reproduce the state the press actually walked:

| | before | after |
|---|---|---|
| 464 hits / 214 sent | **79 s, 74 s** | **24 s, 25 s** |
| 678 hits / 0 sent (the store as it stands today) | **88 s** | **under 1 s** |

The press walks it twice, because `server/pipeline_routes.py:_preflight_leg` shells
`identify --dry-run` before the real one. **Hashing all 2,535 photographs in the store — 4.4 GB — takes 2.89 s**, which is what makes a store-wide press affordable at all: the same
214 misses over the whole store cost less than one drawer costs today.

**The submitted set did not move.** 214 before, 214 after, same 55.4 MB payload, same $0.28
estimate. The whole dry-run output is byte-identical except the crop line, which is below.

## The sentinel, which is the part that could have gone quietly wrong

**`prepared is None` meant two things at once, and hash-first pulls them apart.** It meant
*"this photograph could not be read"* AND *"there are no bytes to send for this card"* —
the same set, while every photograph was prepared. Under hash-first a **cache hit** is never
prepared either.

Five loops tested it — the cache consult, the prompt refusal, the `to_send` filter, the
`unreadable` roster, the retry rounds — and a sixth site wrote `item.prepared.sha256` into
the run payload. **A reorder that left those alone would have reported all 464 healthy cached cards as unreadable**, counted them as neither hit nor miss, and written
`photo_sha256: null` onto every one of their records — where `cli/resolve.py:1108` reads a
missing digest as `blind` and **D36's realign can no longer re-bind the card to the slot it is in today**. That is `CLAUDE.md`'s *"Never silently drop a card"*, four different ways, and
it is why this ships with a field rather than with a reordering.

**`Item.stage` is that field**: `pending` / `cached` / `unreadable` / `refused`. It is a
simplification rather than an addition — the old send filter read `not i.cached and
i.prepared is not None and i.status == "pending"`, which is those same three ways out of the
preflight spelled as three clauses.

**Not `Item.status`, which was already taken and is on the wire.** That field is the model's
answer, or the transport's refusal to ask for one, and it is written into
`identifications.json` and read downstream. **Nothing on the wire moved for this**: a
cache hit still records `succeeded`, an unreadable photograph still records `unreadable`, an
unregistered game still records `unknown_game`.

**`Item.photo_sha256` is the second field, and it exists for `resolve.py:1108` alone.** The
digest now belongs to the item rather than to the bytes that were sent. It is `None` in
exactly one case where it used to be `None` in two: a file whose bytes could not be READ at
all. A photograph that hashed and then failed to DECODE keeps its digest, so **`blind` is strictly smaller than it was**.

## Two counters changed denominator, and both say so on the line

**The crop counters moved to the send set, deliberately.** They ran over every photograph
because every photograph was prepared; a crop that is never made is not a crop. That is the
rule the counters were already written to — *"COUNTED OFF WHAT WAS ACTUALLY MADE, not off
what was asked for"* — carried one step further. **The preflight line now reads `N cropped of the M being sent`**, in those words rather than in a comment: this is the figure an
operator reads while deciding whether to spend, and a denominator that changes silently is a
published measurement rotting. On that box-4 press the line went from `655 cropped, 23 sent
whole (box unfit)` to `214 cropped of the 214 being sent` — and the 23 unfit-crop warnings it
used to print in detail were all cache hits, i.e. warnings about bytes that were not leaving
the machine.

**`cache hits` is counted rather than subtracted, and that is a repair.** It read
`len(items) - len(to_send) - len(unreadable)`, and a card refused for want of a prompt is
neither — so **every `unknown_game` and `unwritten_prompt` card in a directory was reported to the operator as a CACHE HIT**, on the one line they read to decide whether a run is worth
paying for. There is now a value that means cache hit.

## A third repair, which the reorder forced rather than chose

`images.prepare` calls `sha256_of` **outside** its own `try`, so an OSError there was never
an `ImageError` and `run` never caught it: a deleted file or a bad permission killed the
command on the first such photograph and said nothing about the other 677. Hashing is its
own step now, so that failure is caught where it happens and becomes a named failure bound
for the main queue like every other one.

## What proves it

**`make harness` T7 `check_identify_preflight_stage`** — one directory holding one of each
outcome at once: two readable Pokemon cards, one file with a `.jpg` name that no decoder
will take (its bytes hash perfectly well, which is the point), and one card naming a game no
registry answers. Two presses over it, the second paying nothing. Nineteen assertions, one
per consumer of the sentinel, asserted on **the operator's own preflight lines** rather than
on an internal count nobody sees.

**Mutation-tested by reverting each consumer to its pre-reorder form: seven of nine arms go red.** The cache consult, the prompt refusal, the `unreadable` roster, the run payload's
digest, the `cache hits` counter, the crop denominator — and the prepare pass's own gate.

**That last arm is the one that changed the check.** Deleting the gate — i.e. decoding
everything again, the old behaviour — left **every other assertion green**, because
hash-first and prepare-everything agree on every outcome and differ only in the work done to
reach them. So the check counts decodes: the second press must decode exactly one
photograph, the non-image it has to try before it can call it unreadable. Without that
assertion the guard watched the sentinel and not the change the sentinel exists to make safe.

**Two arms are equivalent mutants and are reported as such rather than claimed.** The
`to_send` filter's old three-clause form is still correct at the point it runs, because the
prepare pass immediately before it sets `prepared` on exactly the send set; the retry
rounds' `cached or prepared is None` selects the same items as `stage != STAGE_PENDING`,
since a refusal and an unreadable are both unprepared and a cache hit is `cached`. **Both were re-checked against the whole nine-test harness, not just the new check, and both still pass** — so they are equivalent, not merely unwatched. They were changed for the one-field
reading, and this entry says so instead of counting them.

## What this does not do

**It does not widen anything.** `identify` still takes one capture directory, the scope is
still a box, and no selection, flag or route moved. This is the reorder alone, and it ships
alone because it is the change that removes the only performance argument the drawer bound
ever had.
