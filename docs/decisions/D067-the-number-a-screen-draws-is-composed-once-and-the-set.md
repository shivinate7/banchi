## D67 — Compose the card number once

**One function per side of the wire composes the collector number, and a blank total folds.** `printed_total` arrives as `""`, not `null`, on a quarter of the store (every Riftbound card, which prints one identifier), and three copies of the composition disagreed about it and drew `198/219/`.

- **Client:** `app/src/cardNumber.ts` is the one composer. `numberCell` in the walk keeps the word `none`, because a fact row wants a word and a list wants nothing.
- **Server:** `number_display` is a wire-only decoration beside `label`, `section` and `card`, added by `_card_row` and `do_inventory`. It is unconditional, because a number is a fact about the card and not about where it is. It is optional in `types.ts`, and `cardNumber.ts` composes the raw pair when it is missing. A group agrees on the folded value, so copies stored as `198/219`, `UNL • 198/219` and `UNL - 198/219` do not disagree about the card. `_agreed` still returns `None` on real disagreement (a digit misread), and must. `_match_rank` folds the same way, so the string the screen printed is an exact number match.
- **The set-code shape stays in Python.** D55's shape is published as `join.strip_set_code`, and `_repair_set_code` reads it, because a second dialect of one fold made 950 rows join nothing once (`pipeline/join.py:number_index_key`). On a screen it strips unconditionally: there is no catalog miss to gate on, and the worst a wrong strip does is draw a shorter string. The record, `identifications.json` and the `code~:` counter keep the raw read. Normalizing at capture was refused, because a tidied store cannot say the prompt is being ignored.
- **The review queue does not get the fold.** `#/review` composes the raw pair and shows what the model returned, because that screen is judging the read. A queue that tidied it would hide its own evidence.

Reopen for a set code with no separator, or a game whose real `Number` cells are letters-first.
