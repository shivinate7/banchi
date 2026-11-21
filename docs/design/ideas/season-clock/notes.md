# Season Clock: notes on the mockup

A forward calendar of releases, holidays and tournaments, lined up against your own past orders. Each busy
stretch arrives with a prep card (orders a day as a range, supplies, Fulfiller days) and is scored afterwards.

**Click through.** Open `season-clock.html` from disk. The amber bar is mockup-only: View (Owner, Fulfiller),
Theme, State, and Hide an option. Deep links: `#state=quiet`, `week-out` (default), `first-kind`, `spike`,
`after`, `overlap`; add `&view=fulfiller`, `&t=dark` or `&t=light`, `&hide=rig,learn`. The no-guess answer is
`#state=first-kind&guess=none`. Press an event on the strip or in On the Clock to open its card.

**Where it lives.** Reached from Sales (`#/revenue`), as a third tab on `Revenue.LensSwitch`: `?lens=season`.
Nearest: the Mix lens (`docs/specs/sales-screen.md`, Mix). The Fulfiller's part sits on Cards to Pull (`Fulfillment.Fulfillment`).
Departs from: Sales, a retrospective only (sales-screen "What it answers") — Season adds a forward guess, in order counts, never money (D214, sales shows gross, never profit, holds).
Departs from: Cards to Pull, which shows only cards — it gains a This Week panel of plain sentences.

**Design choices** (each option has a Hide press; Pick is the designer's, not a ruling)
1. Lens inside Sales, not a new route. Gain: no `ROUTES` row, the Mix precedent. Lose: stretches Sales'
   retrospective job. Pick: lens. Owner grant: yes.
2. One capsule per day for the range, your order bar drawn inside it. Gain: every day reads alone; past days
   show the score at a glance. Lose: busier than one smooth band. Pick: capsules.
3. Fulfiller reads "Be ready for up to 24 orders a day", the top of the range. The plan wrote "about 20" and
   "no ranges"; the brief forbids a single forecast. Gain: no point guess, no range to read. Lose: can
   overstate. Pick: top of range. Owner grant: yes.
4. Spike line reads "14 so far, against 1–5 expected", not "about 5". Gain: keeps the range rule. Pick.
5. Supply counts sized to the top of the range for the busiest 3 days (`supplies`). The plan's first version
   leaves them out. Gain: one less sum to do. Lose: a guess times a guess. Pick: keep, cull if noisy.
6. First of its kind: a borrowed range in hatched amber, or "No guess. Watch this one", chosen per event.
   Gain: never a confident number on no history. Lose: one more choice. Pick: borrow by default.
7. Two at once: the ranges add, the card says it cannot tell them apart, and they are scored as one stretch.
   Gain: honest. Lose: the history cannot split them later. Owner grant: yes.
8. "Today" is an accent tint; vermilion stays for a live capture. Also hidable: `rig`, `learn`, `extra`, `boxes`,
   `preview`, `weekends`.

**Owner questions** (from the plan, section 6; nothing waits on them)
- How far back do the saved order files go, and do they hold one past release season? If not, v1 starts empty.
- Will you enter one or two events a month by hand, or must events arrive on their own?
- Are the Fulfiller's hours fixed? If so, `extra` goes and the view only says what to prepare.
**Checked** in headless Chrome, at the brief's sizes (the device list is unknown). System fonts; no font loads.
- 1440 light, `season-clock-1440-light.png`: PASS. Strip, prep card and side column read in one screen.
- 820 dark, `season-clock-820-dark.png`: PASS. Rail shell; the card stacks under the strip; marker names wrap to lanes.
