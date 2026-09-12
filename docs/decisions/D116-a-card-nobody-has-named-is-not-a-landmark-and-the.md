## D116 — A card nobody has named is not a landmark, and the distance is what keeps the skip honest

**The after/before ladder names the nearest NAMED card still in the box on each side.**
It walks past an on-hand card no identification has named exactly as it walks past a departed
one, and it says how many it passed. Recorded and built 2026-09-07, on the owner's report that
cards being sold "are showing up as just a number in the before and after".

### The premise was wrong and the complaint was right

**They read `#270` in the ladder as a sold card leaking in. It was not one, and none ever was.**
`_Places._walk` has filtered `TERMINAL_STATES` out of `occupants` since D30 built the decoration
on 2026-08-23. Asserted over their own store before anything was changed, over every located
record in it and both sides of each: **1,625 place blocks, 0 terminal cards as a neighbour.**
The owner's
memory of the pre-Banchi build — *"the before and after was ONLY live cards that are remaining
in inventory"* — was exactly right about the rule, and the rule had never lapsed.

**What `#270` actually was: box 3, store index 425, on hand, photographed, and nameless.**
The model returned nothing for it (`confidence: low`, blank name, number and sku), it was queued
`no_catalog_row`, and it was closed without being answered under D37 — so it sits in the drawer
with no identity. **Seven cards on that store are in this state**, five in box 3 and two in box
5, and D92's own measurement already named them as the reason this row drew at all.

| | |
|---|---|
| place blocks on the owner's store | 1,625 |
| terminal cards named as a neighbour, before this entry | **0** |
| on-hand cards carrying no name | **7** — 5 in box 3, 2 in box 5 |
| neighbour rows that now reach past one | **27** |
| the screenshot's row | `B3 #426`, sold, `prev` was `#270` and is now `Rell, Noxus` |

**So the defect is not which cards qualify. It is that a figure is not a landmark.**
This block has one job — let a hand flipping through a box find the card — and `#270` is nothing
you can recognise between two pieces of cardboard. It also sat two lines under `B3 #426`, a
store key, so one row carried two bare numbers in two different spaces; D92 rules which one owns
the `#`, and a reader who has not read D92 sees two of them.

### The skip is stated, because a silent one is the wrong-slot claim D30 forbids

**`skipped` rides each side: how many ON-HAND cards the walk passed to reach that landmark.**
`after Rell, Noxus` for a card two along is a sentence somebody counts slots against and comes
out one short, and D30's whole rule is that a position claim may never send a hand to the wrong
slot. So the ladder draws `1 unidentified card between` under the name, and `placeParts` puts
one clause in `said` — the joined form the Fulfiller reads at 20px — covering both sides at
once, which is exact rather than loose: every card the walk passed lies strictly between the two
landmarks whichever side it was on.

**Departed cards are never counted in it.** The box closed up over them (D58), so they lie
between nothing; `section_gaps` is where they are counted, and the two numbers are pinned apart
in T7 on one card.

**A side with no named card beyond it is null, the same answer the box's own edge gives.**
A box straight off the feeder — every card captured, none identified — therefore draws no ladder
rather than a ladder of figures, which is the honest rendering of "nothing over there can be
named".

### What it cost, and the one thing that got faster

**The walk could not stay a scan.** The nearest-named search is O(box) per card in exactly the
case that is most common — a box before `join` has run, where every card is unnamed — so
`do_inventory` over a 723-card box would have been O(n²). `_walk` now also caches the POSITIONS
into `occupants` that carry a name, and `_company` bisects it twice. Measured on the owner's
store: 1,625 records, one full pass in 0.09s.

**The app's `#{slot}` fallback is now unreachable from a current server and stays anyway**, for
an older one. `PlaceNeighbor.skipped` is optional for the same reason, and `?? 0` is the honest
read of its absence: a server without it named the adjacent card because it had no other rule.

### What this does not reopen

**D92 is untouched.** The slot is still what a renderer draws, the index still rides unread for
D45's click target, and `B<box> #` is still the only sigilled key. What changed is that the one
render this entry's figure fired in — a nameless neighbour — no longer happens.

**D37 is untouched, on the owner's word.** Asked whether the seven unnamed cards should be
surfaced or left alone, they chose left alone: a closed question means the card is left alone,
and this entry gives those cards a better rendering rather than reopening their identity.

**What would reopen this**: a box where enough cards are unnamed that the skip counts get large
enough to be worth ranking rather than stating, or the neighbour row becoming a click target —
which is D92's own reopening condition and would make the passed-over card reachable instead of
merely counted.
