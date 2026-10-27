**Superseded:** the owner dropped Take All. Each entry has only its own press, and this page's Take All states are superseded.

# Pricing, take-offs owed: design notes

Lane kind: informed. Mockup: `pricing-owed.html`. Spec: `docs/specs/master-set.md`, section 5.
The frame draws my pick. The Options panel under it draws each alternative, and each has a
control that hides it. The retire receipt that feeds this list is `inventory-retire.html`.

Deep links: `#s=empty`, `#s=one`, `#s=several`, `#s=sending`, `#s=sent`, `#s=failed`,
`#s=nosession`, `#s=nothing`. Add `&w=820` and `&t=dark` (or `abyssal-bloom`, `carnival-midway`).
With no `t`, the page follows `prefers-color-scheme`. `&h=N1,L1` hides options.

Component: `SendCard.SendCard`, inside `Pricing`'s send bar (`.pricing-bar`), drawn when the
Unsent tab is open. The owed line is proposed: a new component in `SendCard.tsx`, drawn by
`SendCard` right under `.send-act`, when the status read lists at least one owed take-off. Its
data is the outbound log's take-off receipts (spec section 5), on the same read as the send
receipts. The CSS is the repo's own sheets, inlined at the time of drawing, with `SendCard.css`
and `Pricing.css`. The proposed rules are at the end, under "PROPOSED". The worklist under the
bar is a plain stand-in.

1. **The owed line is a compact `Notice` under the send press, first of the card's notices.** A
   receipt or a refusal that comes and goes draws under it, so the owed line never moves. Gain:
   one place, read at every visit. Loss: one row more in the sticky bar while a take-off is owed.
2. **One owed (`#s=one`): the sentence names the card and the copies, and the press is beside
   it:** "TCGplayer still lists 1 copy of Mimikyu ex from your master set." The press reads "Take
   It Off TCGplayer", the same words as the retire receipt (ux-one-plain-name).
3. **Several owed: one line, one press for all, and a fold.** Closed: the sentence, "Take All 6
   Copies Off", and "Show 5 Cards". Open (`#s=several`): the list floats over the worklist, one row
   per card with its own press. This is the fold `MovesList` already draws on this card
   (`.send-moves`), so the sticky bar keeps its height (D313). The toggle's two labels share one
   box (`.send-toggle`).
4. **Several owed as an inline list (option L1).** Gain: every press in view without a fold. Loss:
   the sticky bar grows one row per card, and ten owed cards cover the worklist. Pick: no.
5. **Each entry's press reads "Take It Off".** The line above names TCGplayer once. Option E1
   says "Take It Off TCGplayer" on every row. Loss of E1: the same long label five times
   (ux-label-once). Pick: the short form.
6. **One take-off at a time (`#s=sending`).** The pressed entry turns its ring in the press's own
   box. Take All, each other entry, Send and Download are off: the sends share one guard. This is
   how `SendCard` disables Download during a send today: the ring says what runs, and the card's
   `bn-sr` status names it to a screen reader. The mockup's `title` gives the reason on hover
   only, because a disabled button takes no focus. If the builder wants a visible reason, the
   card's own pattern is `.send-why` with `aria-describedby`; that line was not drawn, and at 820
   it may wrap the act row.
7. **Sent (`#s=sent`): the answer shows at the press.** "TCGplayer accepted: 1 copy of Mimikyu
   ex is off. Banchi checks again after 12:52." The entry keeps its place until the page reads
   again after the check, so a live check never pulls a row out from under the person (D313).
8. **Failed (`#s=failed`): the kit `Retry` shape.** "TCGplayer did not take Mimikyu ex off, so
   nothing went live. It stays on this list." The server's words sit behind "What the server
   said", in the grid place `Notice` gives it. Try again is the same press (owner's ruling).
9. **Every state of one entry's sentence and press sits in one grid cell; only the current one is
   visible.** So the line keeps its box from offer to sending, sent and failed. The headless check
   measured the bar in all seven owed states and all four themes: 173 px at 1440 and 232 px at 820
   in each.
10. **Not drawn: Take All's answer, and a failed entry inside the open list.** Proposal for the
    builder: Take All is one press and one send receipt, with one row per card, so one guard
    covers it. Its press turns its ring as an entry's does. Its answer replaces the line's
    sentence: "TCGplayer accepted 5 of 6 copies. 1 stays on this list." A card that failed stays
    in the list, and its press reads "Try again". The spec says every try is a receipt; whether
    one press for six cards writes one receipt or six is the builder's question to settle in the
    spec.
11. **No TCGplayer sign-in (`#s=nosession`): no take-off press, as the spec says for the
    receipt.** The sentence names the fix: "Sign in, then press Refresh." Refresh is the card's
    own door, one row above. The list still opens, without presses.
12. **No sign-in as a failed press (option N1).** `SendCard` already treats a lapsed sign-in as a
    retryable failure: the press stays, and "Try again" answers. Gain: the same shape as a lapsed
    sign-in on a send. Loss: the press is offered when it cannot pass. Pick: no. **Owner grant:
    yes**, because the spec gives no press without a sign-in.
13. **Owed with nothing else to send (`#s=nothing`).** Today `Pricing` draws no send bar when the
    worklist is empty, so the owed line would never show in the likeliest case: the owner retires
    a card when nothing waits to send. The bar stays while a take-off is owed, with the press off
    and "Nothing ready yet". "Everything is sent" stays under it; its sentence is still true.
    **Owner grant: yes**, because it changes when Pricing draws its bar.
14. **The owed line must arrive with the bar's first read.** If it lands on a later status read,
    the bar grows under the person's eyes. The builder reads it with the worklist, or reserves its
    line while the bar is pending.
15. **Tone.** Owed is `warn`: a listing is above what is on hand. Sent is `ok`. Failed is
    `danger`, as `Retry` draws it.
16. **At 820** every press and the "What the server said" summary measured 40 px or more, with the coarse-pointer heights the frame
    states. The compact notice's coarse-pointer layout (sentence on the first row, presses on the
    second) is stated in the frame for the same reason.
17. **Label once.** `label_once.py` on the rendered states found only set names in the worklist
    stand-in, which are data. Pass.
