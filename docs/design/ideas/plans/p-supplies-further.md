# p-supplies-further

The pack recipe turns each order into one fixed packing build. In the first version, the Fulfiller makes no judgment calls about weight, rigidity or tracking. "Learn where tracking actually pays" then changes only one row of the rules table. All numbers below are made up.

**1. The core loop, from order to sealed envelope**
1. The order export arrives. Each order already knows its cards, each card's value, its box, section and position, and whether it is a slab.
2. The rules table works out the recipe: the protection for each card, how many cards share a toploader, the mailer, the estimated weight, and the postage (stamp count or a tracked label).
3. The pull slip shows the recipe as icons next to the pull list, so the Fulfiller sees the build before they walk to the boxes.
4. The Fulfiller pulls the cards and packs them in the order shown: sleeve, toploader, team bag, then the mailer.
5. They apply the stamps or the tracked label shown, then tap "Sealed". If they used something different, they tap "Packed differently" and pick what they used.
6. The order keeps its method, its weight estimate and any change the Fulfiller made. Stage 2 later adds the outcome: arrived, missing or refunded.

**2. States**
- **One-card order (most orders):** "1 sleeve, 1 toploader, plain envelope, 1 stamp." One line, nothing to decide.
- **Ten-card order near a weight step:** "Two toploaders of 5 cards, team bag, plain envelope, 2 stamps," with a small note: "0.2 oz under the 3-stamp step." If the order is over the step, it moves up to the next stamp count or to a flat mailer, with no question to anyone.
- **Slab:** "Slab sleeve, bubble wrap, rigid mailer, tracked label." The tracked rule applies whatever the order's value.
- **Two orders from one buyer:** The two slips are joined under the banner "Ship together." The screen shows one combined recipe, and one "Sealed" tap closes both orders.
- **Order breaking a rule:** An amber bar names the rule ("Over the plain-envelope weight limit" or "Tracking needed, but the order paid for a stamp"). The screen offers the fix ("Use a flat mailer with a tracked label") and shows the extra cost. The Fulfiller can apply the fix, or hold the order for the owner.
- **Rules table (owner only):** One screen, one row per rule. It shows how many orders each row changed in the last 30 days, so a row nobody uses is easy to spot.

**3. Rules table rows (sample values)**
| Row | Sample value |
|---|---|
| Card weight, sleeved | 0.07 oz |
| Toploader weight | 0.20 oz |
| Most cards per toploader | 5 |
| Team bag weight | 0.02 oz |
| Plain envelope weight | 0.20 oz |
| Ounces the first stamp covers | 1.0 |
| Ounces each extra stamp covers | 1.0 |
| Heaviest plain envelope allowed | 3.0 oz |
| Extra postage for a rigid or lumpy envelope | 1 extra stamp |
| Order value at which tracking starts | $20 (stage 2 changes this row) |
| Item value that needs a rigid mailer | $50 |
| Slab is always tracked | yes |
| Merge orders from one buyer within | 24 hours |
| Cost per item: sleeve / toploader / team bag / envelope / rigid mailer | $0.01 / $0.08 / $0.02 / $0.05 / $0.40 |
| Cost: stamp / tracked label | $0.73 / $4.50 |

**4. Smallest first version**
- A recipe line on each pull slip for orders without slabs: protection, envelope and stamp count, from the first nine rows only.
- One amber flag for "over the weight limit" or "over the tracking value". It offers no fix yet.
- A "Sealed" tap that records the method used.
- Merging, slab builds and the rule-row counts come later. Stage 2 has nothing to learn from until about 300 sealed orders carry a method.

**5. Measure**
Postage problems per 100 shipped orders: mail returned for postage, postage due, or a buyer complaint about damage. Take a baseline from the month before the first version, then compare each later month.

**6. Questions for the owner**
1. When an order has 2 to 5 cards, do they share one toploader or get one each? This decides the default for "Most cards per toploader".
2. Does TCGplayer require tracking above a value the owner cannot go below? If so, stage 2 can only raise the tracking cut-off, never lower it below that value.
3. When two orders from one buyer ship together, does the owner refund the second shipping charge? If they do, the merge needs a refund step, and the "Ship together" state stays out of the first version.
