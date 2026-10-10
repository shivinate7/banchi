## 9 — The sigil check matches text, so a renamed local walks past it

`make sigil-check` (D92) refuses a bare `#` composed from an expression naming `index`, and the word form `Card {…index}`. It reads source text. `const n = side.index` on one line and `#{n}` or `Card {n}` on the next is a violation it cannot see, and so is any indirection through a helper, a destructure or a prop rename. One such violation shipped: `slotNumber` returned `String(target.index)` three functions away from the `#`. The bypass is `BANCHI_SIGIL=off`, or the per-line `sigil-ok: <why>`.

**Outcome at risk.** A slot number and a card count drawn with the same `#` on one screen, so a person reads a slot as a count of cards (D58).

**Closes when.** The owner rules on a nominal type over `slot` and `index` so the compiler refuses the swap. D92 rejected it on blast radius: both are plain numbers across the whole wire contract and about forty call sites. Until then a green run means only "no figure is drawn over a field literally named `index` on that line, in either spelling". The sweep for the rest is a person reading `app/src` and asking of each figure what number it is.
