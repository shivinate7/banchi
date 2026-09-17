## 9 — The sigil check matches text, so a renamed local walks past it

`make sigil-check` (D92) refuses a bare `#` composed from an expression naming `index`, which is
what keeps D58's count and the store key from being spelled the same way on one screen. It reads
SOURCE TEXT. `const n = side.index` on one line and `#{n}` on the next is a violation it cannot
see, and so is any indirection through a helper, a destructure or a prop rename.

**Its bypass is `PKMNSCAN_SIGIL=off`**, spelled the way `PKMNSCAN_DOCS=off`, `PKMNSCAN_GATE=off`
and `PKMNSCAN_MAIN=off` already are, and printed in every refusal for D42's reason: a guard with no
visible way past it gets disarmed at the config instead, and a disarmed `core.hooksPath` takes the
three opsec rules with it. The per-line form is `sigil-ok: <why>`, which is the better escape
because it argues the exception in the file next to the code rather than turning the whole check
off for a commit.

**The fix that could not be evaded was considered and rejected on blast radius.** A nominal type
over the two numbers — branding `slot` and `index` so the compiler refuses the swap — is the real
answer, and `slot` and `index` are plain numbers across the whole wire contract and forty call
sites. That is a refactor much larger than the bug, and D92 took the cheap check that runs on
every commit over the expensive one nobody would finish.

**What made the ceiling tolerable was where the mistake usually happens.** All four sites the
check found on its first run compose the `#` and the field on ONE line, at the point of render,
because that is what drawing a number looks like. The paragraph here used to end *"the evasion is
available and has never been taken"*, and it was wrong on the day it was written.

**THE TRIGGER HAS FIRED — one violation shipped through the gap, and was found by reading rather
than by running anything (2026-09-04, D92 amended).** `CaptureScreen.tsx` drew
`#{slotNumber(target)}` on every undo thumbnail, and `slotNumber` returned `String(target.index)`
whenever the target carried no rendered label — which is the target `undoStack` composes from the
server's high-water mark after any reload mid-run. The `#` and the field were three functions
apart, so the check read `slotNumber(target)`, found no `index` in it, and passed. It was green
over that line from the day it was written until the sweep D92 deferred was carried out.

**What that changes and what it does not.** It does not change what the check is worth on the
lines it can see: it read 61 files and the sweep found nothing it had missed except this one. It
does mean the nominal type this entry calls *the real answer* now has a shipped defect behind it
rather than a hypothetical, and D92's rejection of it on blast radius was made without one. That
is the owner's call and nobody else's; recording it is what this file is for.

**The cheap partial was taken first, on the owner's ruling (2026-09-04).** Asked whether the
nominal type should be argued now or the guard shipped first, the owner chose the guard. So the
check reads a second pattern: the word form, `Card {…index}`, which is the same claim as `#{…index}`
in the register a screen reader speaks. **It was measured before it was written rather than adopted
on the argument that it sounded cheap** — over every `.ts`/`.tsx` in `app/src` it returns four
violations and nothing else, all four in `RunsComposer.tsx`, and the eight legitimate `Card {…}`
renders standing in the tree fall outside it on the `index` requirement alone. Those eight are
self-test cases now, so the false-positive rate that made it adoptable is asserted rather than
remembered. **The four it found had shipped**: two of them `aria-label`s, on a panel whose figure
names a photograph the run is about to pay to have read.

**What the second pattern does NOT do is close this section.** It is the same text match one word
wider. `const n = side.index` then `Card {n}` walks past both patterns exactly as it walked past
one, and the ceiling this section was opened about is where it was. What changed is that the
sweep D92 deferred is no longer the only thing standing between this class and a screen — for the
two spellings the product actually uses. **Until the nominal type is ruled on, a green run means
"no figure is drawn over a field literally named index on that line, in either of two spellings",
which is more than it meant and still less than it sounds like, and the sweep that catches the rest
is a person reading `app/src` and asking of each figure what number it is.**

**Two the sweep can see and neither pattern can, left deliberately.** `Pricing.tsx:2641` draws
`` `no label · ${photoAt.box}/${photoAt.index}` `` and `Orders.tsx:1205` draws
`` `box ${target.box}, index ${target.index}` ``. Both spell the key in prose with no figure at
all, so no sigil rule reaches them and none should — naming the index *as* the index is the one
thing that is never the confusion. They are here because they are the shape a future reader will
check this file about.
