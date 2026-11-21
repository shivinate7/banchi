# Every Upload Has a Reverse: notes

Designer kind: informed. The idea: before a send, a check compares the file with the last send and holds it until each flagged card has a price; every send is kept, and "Make Reverse" builds a send that puts back the old prices for cards not sold since.
Plan: `p-trust-further.md` (first round `p-trust.md`). On screen the act is "send", Banchi's term (D273, one press sends listings live); "upload" stays only in the idea name.

**Click through.** Open `upload-reverse.html`. The State bar reaches every state of plan section 2: `#state=clean|outliers|high-value|history|reverse|reverse-check|reverse-of-reverse`; "Check This Reverse" opens `#state=ror-check`. Add `&t=dark|light` (none follows the system), `&cmp=live`, `&sold=cancel`, `&hv=slab`, `&labels=off`, `&hide=sales,risk,usemkt,keepall,retype,download,counts,orders`. Choices work: Keep New, Use Old, Use Market, the retype field, Send, Download then Mark Uploaded, Make Reverse, Back, Close.

**Where it lives.** `#/pricing` (`app/src/Pricing.tsx`). The check takes the place of today's `SendCard` bar; "Past Sends" is a page action that opens a kit `Sheet`. Nearest records: D273 and its send receipts ledger (published, unconfirmed, download), `docs/specs/stale-listings.md` sections 5 and 7, the value line in `docs/specs/pricing-suggest.md`, `docs/specs/undo.md` 11.10.

**Choices** (Gain / Lose / Pick)
1. The check holds both doors, Send and Download the File Instead. Gain: no path skips it. Lose: one more look per send. Pick: yes.
2. Flags sorted by dollars at risk, at most 10, with Was, New, Market, recent sales and copies. Gain: the costly slip is first. Lose: a wide row; at 820 it folds to three lines. Pick: yes.
3. Three choices per flag (Keep New, Use Old, Use Market). Gain: the fix is one press. Lose: Use Market is a third price source. Pick: keep, hideable.
4. Keep New for All. Gain: one press for flags you meant. Lose: the road to clicking through. The high-value cut is never in it. Pick: keep, hideable.
5. High-value cut: retype the price, at the existing $25 value line, always first. Gain: a slip needs two wrong acts. Lose: typing at 1 am. Pick: yes.
6. Mark Uploaded after a download. Gain: answers D273 hazard 3, Banchi cannot see a hand upload. Lose: a tap people forget; the list shows "Not marked uploaded". Pick: yes.
7. Past Sends reads the receipts ledger, not a new store. Each row: time, changes, flags kept, sold since, state. Gain: one home. Pick: yes.
8. The reverse is an ordinary send: same check, price only, Add to Quantity 0 (stale-listings 5, D54). Gain: reverse of a reverse comes free. Pick: yes.

**Departs from**
- Departs from: D277 Q7 and the `Pricing.tsx` comment at the send effect, "no press puts the old prices back" — Make Reverse is that press. Owner grant: yes.
- Departs from: DESIGN.md "Ask first, or undo after" (UX-099), no press does both — the send gets a check before and a reverse after. Argued: a sold card cannot be unsold (stale-listings 7), so the reverse is not a full undo. Owner grant: yes.
- Departs from: D273 Q2, one press sends and makes live — that press is now locked until each flag has a choice.
- Not drawn: the "wrong column" whole-file flag, slab and fee rules, the after-send alert, memory of kept flags (plan section 4 defers them).

**Owner questions (from the plan)**
1. Does a live price change outside these files? Banchi already reads what is live before each send; the "Compare With" toggle shows both bases.
2. A sale at a bad price: honor it or cancel the order? The "A Sale at a Bad Price" toggle lists the orders when you cancel.
3. The value line is $25 today. Does every slab get the confirm too, whatever its price? Toggle "Own Confirm For".

**Verdicts.** 1440 light, `#state=high-value` (`upload-reverse-1440-light.png`): pass, the confirm, flags and press fit one row each, no overflow. 820 dark, `#state=reverse` (`upload-reverse-820-dark.png`): pass, the sheet fills the column beside the rail and every row reads. Also looked at: outliers at 820 dark, pass, each flag folds to three lines.
