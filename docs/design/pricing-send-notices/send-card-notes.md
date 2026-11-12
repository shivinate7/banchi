# Send card: suggestions the send changed, design notes

Designer kind: informed. Mockup: `send-card.html`. Spec: `docs/specs/pricing-suggest.md`, the
paragraph on a kept suggestion that drifts between the draw and the press.

Deep links: `#s=few`, `#s=many`, `#s=gone`, `#s=one`, `#s=onegone`, `#s=none`. Add `&o=1` to
open the list, `&w=820`, and `&t=dark` (or `abyssal-bloom`, `carnival-midway`). With no `t`, the
page follows `prefers-color-scheme`. `&h=inline,two,receipt` hides options. `&tags=off` hides
the dashed Today and New tags.

Component: `SendCard.SuggestionNotes`, drawn by `SendCard` under `SendStanding` right after this
visit's own send. Data: `SendAnswer.moved` (`name`, `was`, `price`) and `SendAnswer.left_out`
(`name`, `price`, `now` or null). The CSS is the branch's own sheets, inlined at the time of
drawing. The proposed rules are at the end of the style block, under "PROPOSED". The caption
prints the measured push on "Prices as of" for each state.

1. **One line for both kinds.** A compact `Notice`, class `send-suggestions send-moves`, in
   place of today's two notices. Amber when any card was left out, blue when every card went.
   Gain: Prices as of moves down 60px at 1440 and 62px at 820. The failed review measured about
   166px. Loss: the tone covers both kinds, so the list's headings name the kind.
2. **The sentence counts. The list names.** Two or more cards: "2 cards went at a new price and
   1 was left out. Their prices changed since you loaded this list." The fold, "Show 3 Cards", is
   `MovesList`'s fold (`.send-moves`, `.send-toggle`). Open, the list floats over the worklist in
   its own scroll box, so the bar keeps its height (D313, nothing moves unless moved).
   Thirty-five rows scroll inside it.
3. **One card: no fold.** The sentence names the card and both prices. Moved: "Gardevoir ex went
   at $4.03, not $4.01. Its price moved since you loaded this list." Left out: "Iono was left
   out. Its price went from $11.00 to $13.10 since you loaded this list. Check it in your list
   and send again." Gone: "Roaring Moon ex was left out. It has no suggested price now."
4. **The list is one `ul.send-names`, in two groups.** Left out comes first, because it asks for
   a tick. A heading row in the `.send-more` style carries the kit's `Count`: "Left out,
   check them in your list" and "Went at the new price". Each row reads "name, $old to $new". A
   gone row reads "$5.45, no suggested price now". The price is right-aligned, so thirty rows
   scan down one edge.
5. **Every dollar is the kit's `Money`** (`.bn-money`, D221, money stays mono), in the sentence
   and in the rows.
6. **"since you loaded this list".** The server checks the price the press named, which is the
   price on screen (`send_routes`, its `drift_allowed` check). The "Prices as of" time is not
   used: the press rebuilds after that time, so a sentence tied to it could be false.
7. **"Left out", not "not sent".** "Left out" is this card's word (`PricesLeft`). `NotSent`
   says "Not sent" for a card gone from the store. One phrase keeps one meaning.
8. **"Check them in your list".** The spec says a kept tick holds only within the drift. A
   Needs-you row comes back unticked and a Suggested row comes back ticked at its new price, so
   the heading names where to look and not a tick state. A gone row has no suggestion to tick,
   and the heading still holds: the row is in the list.
9. **The fold's press is 40px at every pointer.** The brief asks for 40px targets. Today's
   `MovesList` press is 34px at a fine pointer. The line takes back that 6px from its own padding
   (`--bn-1-5`), so it stands as high as the receipt above it. Loss: two local rules on
   `.send-suggestions`.
10. **At 820 the press stays beside the sentence.** The kit puts a compact notice's press on a
    second row under a coarse pointer. Here that row cost 118px. Beside the sentence, a wrapped
    sentence costs 62px. Departs from: kit.css's compact-notice press row (the coarse-pointer
    block). Loss: a third local rule. Owner grant: no, the rule is local to this line.
11. **Option: inline when few.** Three cards or fewer list under the sentence, no fold. Gain: no
    press. Loss: about 20px a row in the sticky bar. Pick: no.
12. **Option: two lines, one per kind.** Gain: the tone says the kind. Loss: a second line, the
    height the review flagged. Pick: no.
13. **Option: inside the receipt.** The green receipt says it and carries the fold. Gain: no
    added height. Loss: a card that did not go reads in green, as if all is well. Pick: no.
