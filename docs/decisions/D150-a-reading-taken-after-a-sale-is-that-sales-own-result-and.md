## D150 — A reading taken after a sale is that sale's own result, and it ages the claim

**`cli/resolve.py:_copies_out` ages a stuck `pushed` claim by the SKU's sales where the export corroborates them, and a reading of ZERO taken AFTER a sale is corroboration.** Built 2026-09-11, from the operator's report that two cards they had just scanned into box 1 could not be sent: *"you are aware that I scanned in new falling star and a new fizz and so i should ideally when everything is fixed have some quantity that could be pushed out on that pricing run?"* They were right, and `docs/DEBTS.md` §24 — written the same day, by the branch that fixed D147's ordering defect — had recorded this as deliberately unfixed.

### The expression, and the premise that was false

`pushed` is a count of copies SENT and it has **no drawdown**: `cli/cmd_emit.py` writes it, `cli/cmd_reconcile.py` moves it to `staged`, and `cli/cmd_join.py` draws `staged` down by the RISE in live quantity. Nothing anywhere decrements it on a sale. So once an import lands, the claim counts copies TCGplayer has already sold, and the copies on hand are committed against a shelf that no longer exists.

A SALE is the one event that proves a sent copy has left, so the claim is aged by the sales — but only where the export vouched for the copies having been there:

    sold = (positions - copies_not_sold) if read > 0 else 0
    out[sku] = max(live, claim - sold)

The comment on that gate argued: *"A sale reduces what TCGplayer holds only if the copy was LIVE there, and with `Total Quantity` at zero nothing of ours ever was."*

**That conflates "never was live" with "was live, sold, and now reads zero."** The store already dates both facts and nothing was reading them together — `Card.state_at` for the sale, `Listing.live_as_of` for the reading:

| sku | card | sale(s) | the reading |
|---|---|---|---|
| 8925672 | Falling Star | 09-07 | 2026-09-11T22:50:36Z |
| 9035516 | Fizz, Trickster | 09-02, 09-07, 09-07 | 2026-09-11T22:50:36Z |

A zero read four days after the copies sold is the sale's own result. **This is D115's rule pointed the other way**: that entry clears the store's counted sales where it adopts a reading taken after them, on exactly this reasoning about exactly these two stamps.

### The arithmetic, worked rather than asserted

The reading is the only witness this Mac has to a copy having been at TCGplayer, and it can answer two questions rather than one:

- **A reading that reports copies LIVE vouches for every sale of the SKU.** Our copies reach that shelf, so a copy that sold sold from it, whenever it sold. `sold` is every sale ever — the arm that has always been here.
- **A reading of NOTHING vouches for exactly the sales it was taken AFTER.** `Inventory.sales_before` is that count. A sale after a zero reading is still not aged: the reading said nothing of ours was live at its own time, so a copy that sold later cannot be shown to have been one of the copies this claim counts.

**Neither arm double-counts, and the comment this replaced said one did.** The two are a `max` over two independent estimates and never a sum, and `claim` is never decremented by a sale, so a sale the reading has already absorbed is one the claim has NOT. Four sentences of arithmetic, since a claim about double-counting has to be checkable:

| case | reading | sales | `live` arm | `claim - sold` | out | truth |
|---|---|---|---|---|---|---|
| landed live, sales after it | 4 @ T | 2 @ T+ | 4 − 2 = 2 | 4 − 2 = 2 | **2** | 2 |
| landed live, reading after the sales | 2 @ T+ | 2 @ T | 2 − 0 = 2 | 4 − 2 = 2 | **2** | 2 |
| sold out, reading after the sale | 0 @ T+ | 1 @ T | 0 | 1 − 1 = 0 | **0** | 0 |
| pushed, never read, sold here | none | 1 | 0 | 1 − 0 = 1 | **1** | 1 |

Row 1 is the case a naive date rule gets wrong — age only by sales BEFORE the reading and it answers 4, stranding two copies — which is why the fix is a second arm on the gate and not a replacement for the first. Row 3 is the operator's. Row 4 is D59's negative case.

### What `check_listing_commands`' re-emit idempotence case does under this change

**Nothing. It has no reading at all.** Four pushed, one sold, export silent: an emit takes no reading of `live` and that case asserts `live_as_of is None` by name, so `reading_taken_at` returns None, `sales_before` counts nothing, the claim stands at four and no fifth row is offered. Proved by mutation rather than by reading: dropping the gate outright takes that case red at *"and the re-emit adds nothing (D54)"*, expected 4 and actual 5 — the exact regression the old comment predicted.

Three mutation arms, all run:

| arm | what breaks |
|---|---|
| the old gate back (`else 0`) | the new positive case, `(0, 1, 0)` for `(0, 0, 1)` |
| no gate at all (age by every sale) | the new negative case AND D54's re-emit idempotence |
| the date comparison reversed | all three |

### What it is worth, measured on the operator's real store

Run `2026-09-11-box1-01`, joined against its own fetched export, read-only against a copy of `inventory/store.sqlite`:

| | before | after |
|---|---|---|
| matched SKUs offering a copy | 239 of 246 | **246 of 246** |
| copies `emit` would send | 310 | **317** |
| SKUs adding nothing | 7 | **0** |

The seven are §24's own table, Falling Star and Fizz, Trickster among them. Store-wide, against each listing's own stored reading: **32 SKUs and 58 copies** where `live` is 0, the claim is stuck, a sale predates the reading and stock is physically on hand.

**And the false report sentence goes with them.** §24 recorded that those seven print `SkuMatch.nothing_to_add`'s *"every copy in this run is already listed or has left the box"* over a card sitting in the box, and that patching it needed the sold count threaded onto the match. It needed no such thing: the sentence was false because the arithmetic was, and with the claim aged the rows are offered rather than named.

### Why not just tell the operator to reconcile

`pkmnscan reconcile --live` writes `live` and the old gate opens on its own. **The operator does not run it**, D59 opens on their saying so, and a fix available only to someone who runs a command they do not run is not a fix. Nothing here writes: the ageing is derived per resolve from two stamps the store already holds.

### The three rules stay in one place each

`Listing.live_reading` answers WHICH reading to believe, `Listing.sales_pending` answers which counted sales survive it, and `Listing.reading_taken_at` — new here — answers its DATE. Its branches mirror `live_reading` exactly, including the stampless one, so `_copies_out` cannot ask "was this sale before the reading" of a reading that was not the one used. That is D87's amendment's own property, extended to a third fact rather than abandoned for it.

### What is left, and it is named rather than papered over

**A SKU whose import landed in Staged and never went live reads zero too.** A copy sold by hand against that state ages a claim it should not, and the copies are still sitting in TCGplayer's staged channel. Telling that from a sold-out listing needs D59's own reopener — a marker that a copy actually reached an import file, one field on `Card` written by `cmd_emit`'s push loop beside the `sku` stamp. **`docs/DEBTS.md` §24 is now that residue** rather than this whole defect; it is the third entry to turn on not having that field, after D147 and §24 itself.