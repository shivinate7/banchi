# Flow deliberation: from captured cards to live listings

**Status: reasoning, not a spec.** The final answers to every question below live in
`RULINGS.md`'s "Flow interview" section (Q1 through Q8). This file holds the measured evidence
against the built screen, the hazards found in the code, and the options the owner weighed.
`docs/specs/order-flow.md` covers a different subject, the box, search and position
architecture, so nothing here duplicates it.

## The verdict

The flow is a four-command pipeline drawn as a screen. The owner walks nine steps, about 33
presses, two trips into TCGplayer's own portal, two file downloads and two file pickers. Only
five of those steps are a real choice. The other four are work the app can already do, or
almost do, with parts it already has.

The product changed under the screen. Pricing became store-wide. Identify became a selection.
A transport exists that can push a file to TCGplayer and publish it. The live export can be
fetched. The Runs stepper still draws the old box-at-a-time pipeline anyway, and so does the
Pricing receipt, which sends the owner back into a shell command.

The recommendation: five presses from capture to live. Identify takes two (open, spend). Price
and send happen on Pricing. Send and Put live are two presses on one card. Matching, the staged
check and the live check all run by themselves.

## The flow today, measured

On the happy path, one box, nothing to review, the standing rule pricing every row, the nine
steps cost about 33 presses. They carry about 910 words of flow text, across seven screen
changes, two downloads and two file pickers.
Five steps hold a real choice. They are: spending money to identify, answering a price the
rule cannot set, uploading to Staged, moving to Live, and reviewing a card in doubt. The other
four (join, the staged compare, the live check) ask the owner to press a button. Each button
only starts work the machine already knows how to do on its own.

What the owner reads along the way names its own machinery in plain sight: "Identify, join,
emit and reconcile a box." A receipt ends with a shell instruction: "In TCGplayer, Import to
Staged, then Export From Staged. Come back with that export and reconcile on Runs." A toast
reuses the word "reconcile" for a different step than the header press of the same name. A
mark-down sheet tells the owner to run a shell command by hand.

## Three hazards found in the code, not only in the words

1. **A file written and never uploaded strands its copies.** Writing the import file marks
   those copies "pushed" in the store, and the send cap then holds them out of the next file.
   Only the staged compare clears that mark, and it only reports a row that did not land.
   Nothing names a file that never left the Mac at all. Its size on the owner's own store is
   unmeasured.
2. **A hand "Move to Live" has no lag guard.** The export the app reads after a publish serves
   stale figures for a while. A listing published by hand in the portal, then reconciled at
   once, reads off that stale export. Its effect on the store is unmeasured.
3. **The one measured doubling happened on the hand path.** Nine SKUs were found sent twice by
   a file uploaded twice by hand. The app cannot see a hand upload, so it cannot refuse a
   second one. A push the app itself makes can, because it keeps its own receipt.

## What the owner really decides, against where it sits today

| Decision | Where it sits now | Where it should sit |
|---|---|---|
| Spend money to identify these cards | The Identify sheet's third stage | The Identify sheet, its only screen |
| Which cards | The Identify sheet's first stage | Carried from whichever press opened the sheet |
| How cards are read | The Identify sheet's second stage | Behind a settings door, since one preset already measures best |
| What a doubtful card is | Review | Review, unchanged |
| A price the rule cannot set, or a hold | Pricing | Pricing, unchanged |
| Send these copies to TCGplayer | Pricing's write bar, then a portal upload | One press on Pricing |
| Let buyers see them | The portal only | One separate press on the same card |

Everything else the owner presses today is ceremony the machine can already do on its own.
That covers the cost check, the join, and the file download and portal upload clicks. It also
covers the staged export download and its compare, and the live fetch and its preview.

## What the app already has

The cost check is already free to run, and can fire the moment the sheet opens. The join needs
no answer from the owner at all, since its scope is already a rule. The only human part is a
refusal with its own sentence already written. A transport already exists that can push a
file to Staged and publish it. It cannot reach the listing file only because of this repo's own
rule, which refuses any row that adds a quantity through that door. The push already answers
with what TCGplayer took. The live export is already fetched, with a lag guard already built
for any upload the app itself published. Pricing is already the one worklist, and already
writes the one file.

## The proposed flow

Five presses on the happy path, three steps run by themselves:

```
Capture -> Identify sheet -> (reading, then matching: automatic)
   press 1: open
   press 2: Spend
                          -> Review, only if a card is in doubt
Home or the run card "Ready to send" -> Pricing
   press 3: open, price what the rule cannot
   press 4: Send N copies to TCGplayer (write, push, staged check: automatic)
   press 5: Put N copies live (live check after the lag: automatic)
                          -> Live, confirmed
```

The Identify sheet opens already running its cost check, with the box or "every waiting card"
already carried in from the press that opened it. A settings door holds how cards are read,
closed by default. Matching runs the moment the reading finishes, and a refusal becomes the
run's own next step rather than a dead end. Review is unchanged, and its done state points on
to Pricing or back to more identifying.

Pricing's own send press writes the file, pushes it to Staged, and checks what TCGplayer took,
in one server call. A failed push rolls back at TCGplayer, so a copy is never marked sent when
it was not. The card that follows names what TCGplayer took, and offers "Put N copies live" or
"Take them back". A hand download stays available too, named "17 copies written, not confirmed
at TCGplayer" until a check finds them, closing hazard 1 either way.

The publish press stands apart and stays scoped to that one upload. After the wait, the next
visit to Pricing or Home runs the live check once. There is no preview at all when nothing
needs a decision, and a plain row with a door whenever something does.

Runs itself becomes a history of reads. Each row shows one spend: its cost, its card count, its
box, and its real next step. The stepper, the six-segment bar, the files list and the header
shell command all leave the screen. The route keeps its name. Home's ranked line learns two new
states in place of today's pipeline-shaped one, and its spine gains a Send stage.

Measured against today: identify drops from 8 presses and about 363 words to 2 presses and
about 35 words. Matching drops from 2 presses to 0. Writing and uploading drops from about 8
presses across the app and the portal to 1. The staged check and the live check both drop from
several presses plus a console read to zero. The whole path drops from about 33 presses and
910 words to about 5 presses and 100 words. It also drops both portal trips, both downloads,
and both file pickers. Every pipeline word along the way goes too: join, emit, parked,
sub-threshold, reconcile, Staged.

## Decisions this touches

Every decision below keeps the outcome it protects. Only the screen's own shape changes.

| Decision | What it protects | What changes |
|---|---|---|
| The pipeline-on-a-screen rule, one route spends | The owner sees the figure before the spend | The cost check starts when the sheet opens. Still two presses, never one. |
| The pipeline gets a route | The selection is handed to the screen | The box or every waiting card is carried in already. The stepper goes. |
| A press names its cards | A press states its own scope | "Box" on screen, a live count, carried from the press that opened it |
| One file for the store | One press, one file, across every run | Kept. The write now joins the send. |
| The markdown lives where prices are decided | Prices are decided and sent in one place | Kept, and extended to listing files too |
| Push and publish are two presses, a re-upload is a no-op | Buyers see nothing until a separate press, and a file sent twice never doubles a quantity | Push and publish now reach the listing file too. A receipt guard replaces the old zero-quantity rule for it. |
| The store-wide reconcile | Both directions are reported, and nothing is marked sold by it | Moves off Runs onto the send card and the mark-down sheet, and runs after the lag with no needless preview |
| One worklist, and a run stays open | No unsent copy is forgotten | Its status now names the real next step |
| The export fetch's scope rule | A fetch always names its scope | Unchanged. It just runs without a press. |
| A press claims its cards | No card is paid for twice | Unchanged |
| No mechanism named on screen | Owner words only | The whole path now carries no pipeline word |

A send made from the app itself is new surface area, and needs its own decision entry once it
is built.

## Alternatives the owner did not pick

**A store-wide pipeline board on Runs**, five columns with counts, and the send and publish
presses living there instead of on Pricing. This was not preferred. It would split price from
send again, after two earlier decisions fixed that exact split once already. It also repeats
Home's own spine as a second board.

**A single-box wizard from Capture**, walking identify, review, price, send and live for just
the box in hand. Not preferred. Identifying takes minutes to hours, so a wizard cannot hold the
owner's attention that long. Pricing and sending were also made store-wide on purpose, rather
than per box.

**Words only, no structural change.** Rename the two reconciles, and fix the wrong status
text. Link the steps from the receipt, and cut the machine words, with everything else left as
built. Not preferred, and the owner said as much. It still leaves about 25 presses standing,
both portal trips, and all three hazards. It remains the right first cut if the fuller reshape
were ever declined.

## Measure before building

Each of these is a read, or a reversible act. None ran as part of this deliberation.
1. Push one real listing row through the app's own transport, then roll it back. This proves
   TCGplayer accepts an added quantity through that door. It touches the real account, so it
   waits on the owner's own word first.
2. Fetch Export From Staged, by the endpoint the code already names. This confirms the staged
   check can be a plain fetch, rather than a manual compare.
3. Time the cost check on the owner's own store, to decide whether the sheet shows its figure
   at once or after a short wait.
4. Count how many copies sit "pushed" and never "staged" on the owner's store today, to size
   hazard 1.
5. Measure how long the live export actually takes to reflect a publish, to replace the
   guessed fifteen-minute wait with a real one.

## Options each question weighed

Every answer here is now a ruling in `RULINGS.md`'s "Flow interview" section. This file keeps
only what each question weighed before the owner picked.

- **Does Banchi send the listing file itself?** Yes, with a hand-download door kept alongside
  it (chosen). Or yes, with the download door removed entirely. Or no, keep the hand upload and
  only add the staged check.
- **Is "Put live" its own press after Send?** Yes, a separate press scoped to that one upload
  (chosen, since Staged is the one margin that already caught a real mistake). Or no, one press
  does both. Or Banchi sends, and the owner always moves to live by hand in the portal.
- **How does Banchi check what went live?** By itself, on the next visit to Pricing or Home
  once the wait has passed, with no preview unless something needs a decision (chosen). Or a
  background timer that fires with no screen open. Or one manual press with no preview step. Or
  today's fetch-then-preview-then-press shape kept as is.
- **Does matching run by itself?** Yes, with a problem becoming the run's own next step
  (chosen). Or no, keep a press for it.
- **Does the cost check run the moment the sheet opens?** Yes (chosen). Or no, keep "Check
  cost" as its own separate press.
- **What does the Runs screen become?** A history of reads, each with its own next step, with
  send and live both moving onto Pricing (chosen, pending a final decision on Runs' own nav
  label). Or the five-stage store-wide board from the alternatives above. Or gone entirely,
  with identify opening from Capture, Home and Pricing, and its history folded into Home.
- **Where does "Check what is live" live?** On Pricing's send card and in the mark-down sheet,
  the two places that actually need it (chosen). Or on Runs, renamed. Or on Home alone.
- **What happens to a written file that was never sent?** Pricing names the unconfirmed copies
  and offers "Take them back", until a check finds them (chosen, since a guess by elapsed time
  alone could put a copy on TCGplayer twice). Or the copies quietly return to the list after a
  fixed wait. Or nothing at all, as built today.
