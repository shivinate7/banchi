## D78 — A run's reason for adding nothing is a heading, the rows under it sink, and a hold sinks on the reopening

**Built 2026-08-31, on the owner's ask, over a screenshot of `#/pricing` on a Riftbound box.** Two sentences, one after the other: *"can we have it so that 'every copy in this run is already listed or sold' rows go to the bottom?"* and *"instead of each of those rows having that quoted subtext, instead it's a header and these rows fall under it"*. They are one change, and the second is what makes the first worth doing.

**What was on that screen.** Of the eight LISTED rows visible, five carried `every copy in this run is already listed or has left the box` in their own right margin — including the top two, at $39.10 and $30.93. The list is sorted market-descending (`cli/cmd_join.py:_pricing_table`, and it stays that way), so the run's most expensive **non-questions** stood where the eye starts, five copies of one sentence ran down the column, and the rows that actually wanted a price were read around them.

**The rule: a row this run can add nothing for sinks to the bottom of its own section, under a heading naming why.** Inside every group the market order is untouched. The sections are untouched — nothing crosses one, because `bucket` is still decided by the Market cell alone.

**Grouped by the SENTENCE, not by `at_cap`, and that is D59 held to.** `pipeline/join.py:SkuMatch.nothing_to_add` composes three of them — every copy already listed or gone, at the live cap, or held by an import this pipeline has not seen land — because they have three different remedies. Three headings, then, in first-appearance order down the wire; never one bucket of leftovers under a word like *skipped*, which would be the client re-deciding that the three are the same thing. A `pricing.json` an older join wrote carries `at_cap` with no sentence beside it, and those rows group under the bare fact, which is all `at_cap` means.

**D28 is why this may be done at all.** The list must not move under a finger already travelling to the next field. Every input to this order — `bucket`, `at_cap`, `nothing_to_add` — is written by `join` and read off disk, so nothing the operator types on this screen can move a row out of its group, the same way nothing typed can move one between sections. The heading is deliberately not `sticky` for the same reason: a heading that detaches and rides the scroll is that motion arriving from the other direction.

**The advance now steps the order that is DRAWN, and the bug it would otherwise have been is worth recording.** `Enter` and the arrows walked the wire array. That was correct only by coincidence: the wire is market-descending with `None` last, which puts the three buckets in the same order the three sections are drawn in. Sinking a group moves a row within its section and ends the coincidence — stepping the wire would have sent the focus from a row near the top down to one drawn at the bottom of the section and back up again, on a screen whose whole gesture is type, Enter, type.

**The row's second line is the operator's own note now, and it gained a string it used to swallow.** The reason won that line over the hold's note, on the argument that the reason is the fact about the run and the note is an aside. With the reason a heading, a row that is both at the cap and withheld draws the note — the one string on that line nothing else on the screen holds a copy of. The 13px reservation that keeps every row the same height is unchanged and still carries the machine token beside it.

**What would reopen this: a group with one row in it, over and over.** The heading costs a line, and it buys nothing over a row's own margin when it covers a single row. Measured on the shape that produced this — five rows, one reason — it is plainly right. If a real run draws three headings of one row each, the answer is a threshold, not a return to the subtext.

### Amended the same day — a held row sinks too, and it sinks on the REOPENING

**The owner, an hour later:** *"make it so that upon a reopening that page those that were held are also moved down in their own category (after prices, before all are sold/listed)"*. Three tiers now, and the order is theirs: the rows still wanting a price, then the ones already answered with a hold, then the ones this run can add nothing for.

**The timing is in the ask, and it is the part that matters.** The two sinks have different inputs. `bucket`, `at_cap` and `nothing_to_add` are the join's and cannot change while the screen is open, so sinking on them is free of D28. **A hold is this screen's own answer** (D49), and a row that dropped down the list the instant `H` was pressed would take the next row up to meet a finger already travelling to it — the exact motion D28 closed. So the group is read from `sunkHolds`, the set as it stood when `load` last ran, and it re-sorts on the next opening.

**Read the way a ROW reads it, which is why the snapshot walks the table rather than the two answer maps.** `targetOf` decides which map a row's answer lives in, so a stale `overrides` key for a `no_market_data` SKU draws nothing and must sink nothing. The group and the word `Holding` are then the same test, run once each.

**`"unlisted"` counts as held, and it is not an edge.** It is the answer a `no_market_data` row takes to say this card is not being listed, it draws `Holding` in the price column exactly as a reasoned hold does, and it keeps the card out of the same import file. A group of rows that will not list is the honest set; taking the reasoned half alone would leave the other half among the unanswered rows looking like work.

**ONE heading over all the holds, unlike the cap tier's one per sentence.** The reason is per SKU and is already drawn on the row as `withheld: <reason>` — the string D49 spent a line of chrome on precisely so it can be grepped from the screen to `decisions.json`. A heading per reason would scatter three rows across three headings to restate what each row already says.

**Where a row is both held and at the cap, the cap wins the placement.** The hold changes nothing about a SKU this run was never going to add a row for, so the deeper fact takes it; the `withheld` token still draws beside it, so the hold is not lost by being outranked. This is the same precedence the row's note line used to have, kept rather than reinvented.

**A row can outlive its group for one session, and that is the trade, taken with eyes open.** Release a hold and the row keeps its place under the heading until the next load, drawing a price field. The row tells the truth about itself and the heading says why the group is there; the alternative is the list moving under the release, which is the thing being bought. The browser case asserts both halves in one test — a case checking only the press passes against a screen that never sinks holds, and one checking only the reload passes against a screen that sinks them on the press.

---

---
