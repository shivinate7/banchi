# Feature-idea planner briefs

Each planner was blind: it got the common context below and one lens, and no screens, code or specs.
Planners ran as Opus `Plan` agents. Their reports are in `plans/`, one file per lens.

## Common context (given to every planner)

You are inventing feature directions for a small software product. You have not seen it. Do not read
any file in the current folder or repository, and do not search the code. Work from this text alone.

**The business.** One person (the owner) sells single trading cards from collectible card games
(mostly one game today) on TCGplayer, a large online marketplace. Cards arrive already sorted by set
and card number. The goal: list cards in bulk with zero attention per card, and always know where
each card physically is.

**The people.**
- The owner: technical, runs the system, decides prices, does the photographing.
- The Fulfiller: a non-technical helper. When orders come in, the Fulfiller pulls the sold cards from
  about 6 long boxes (each holds 545 to 732 cards, split into 9 to 22 sections by dividers), packs
  them and ships them.

**The numbers.** About 3,600 cards on hand. Orders per day: median 3, busy days 11, peak 39. Most
cards sell for under a few dollars; a few are worth much more. Some cards are graded and sealed in
plastic cases ("slabs").

**The machinery.** A capture rig photographs cards as they feed past a camera, about 1,300 cards an
hour, and remembers each card's box, section and position. A paid identify step reads each photo
and names the card and its printing; it costs money per card, so it runs in batches. Prices come
from marketplace data (market price, recent sales). The marketplace takes listings as uploaded
spreadsheet files, and gives orders back as exported files. The whole store lives on one Mac on the
home network. People use it in a browser on that Mac, on an iPad, and maybe soon an iPhone app.

**Your job.** Invent directions the owner may not have thought of, seen through your lens. Skip the
obvious (a dashboard, a search box, barcode scanning). Short and thoughtful beats long and complete.
No implementation plans, no file lists, no code.

**Return exactly this, at most 45 lines:** three directions, each with:
- **Name** (at most 6 words)
- **The idea** (2 to 3 sentences)
- **Who it helps**
- **Why now** (why it matters at this size and stage)
- **Rough shape** (2 to 4 bullets: what a person sees and does)
- **Risk** (one line: the way it could be wrong or harmful)

End with one line: **Bet:** the one direction you would build first, and why.

## Lenses

| Planner | Lens |
|---|---|
| `p-fulfiller` | The Fulfiller's day, from the moment orders arrive to the last envelope sealed. |
| `p-rig` | The owner's hour at the capture rig: feeding, jams, sections, fatigue, what breaks flow. |
| `p-market` | Price and market timing: when to list, raise, hold or cut, and how the market moves. |
| `p-space` | Inventory as a map of physical space: boxes, sections, shelves, the room itself. |
| `p-buyers` | Buyers and repeat customers: who buys, what they come back for, what they would want. |
| `p-trust` | Trust and undo: mistakes, wrong cards shipped, wrong prices, and how to recover safely. |
| `p-automate` | Automation that removes a whole screen or a whole job, not one that speeds it up. |
| `p-iphone` | The iPhone in hand: what a phone in a pocket makes possible that a desk browser cannot. |
| `p-multigame` | Multi-game expansion: adding a second and third card game without doubling the work. |
| `p-slabs` | Slabs and high-value cards: the few cards where one mistake costs more than a month of bulk. |
| `p-product` | What would make this a product other sellers pay for. |
| `p-wild` | A deliberately wild lens: ideas that sound absurd today but might be right. |
| `p-seasons` | Time and seasons: new set releases, holidays, tournaments, spikes and slumps. |
| `p-condition` | Condition, damage and disputes: grading by eye, returns, "not as described" claims. |
| `p-learning` | A system that learns: every correction the owner makes teaches it something. |
| `p-money` | Money and books: cost basis, profit, taxes, cash tied up in slow cards. |

## Round 2 lenses

Same common context. Each was told the round-1 lenses already taken, and asked to avoid pick walks,
photo-match at packing, price rules, and sort-order identify checks, which round 1 covered.

| Planner | Lens |
|---|---|
| `p-handover` | A new or stand-in Fulfiller: the first week, a sick day, the owner away for two weeks. |
| `p-intake` | Where stock comes from: buying collections, lots and trade-ins before the rig ever sees them. |
| `p-ambient` | Interfaces that are not screens: lights on boxes, sounds, printed labels, the room itself. |
| `p-resilience` | The Mac dies, the network drops, the marketplace is down, the owner is away a week. |
| `p-local` | Life outside the marketplace: the local game store, friends, trade nights, a show table. |
| `p-attention` | The owner's attention budget: what deserves an interruption, and a weekly rhythm. |
| `p-pride` | Craft and pride: making careful work visible and satisfying for both people. |
| `p-photos` | The photo archive as an asset: thousands of square-on card photos, what else they can do. |
| `p-supplies` | Packaging, postage, supplies and waste: the physical consumables and their cost. |
| `p-rivals` | Other sellers of the same cards: positioning, undercutting, and where this seller wins. |
| `p-tenx` | The store at ten times its size: 36,000 cards and 30 to 400 orders a day. What breaks first. |
| `p-subtract` | Subtraction: which steps, screens or habits to delete because they add no value. |
