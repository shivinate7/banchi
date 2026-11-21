# p-space

**1. Name:** Find a card by its neighbours
**The idea:** A position number like "slot 214" goes stale once cards ahead of it sell, because every pull shifts the count. So each card's location becomes "behind this divider, between these two cards," shown with their photos. A depth bar shows roughly how far back from the divider to reach, worked out from card thickness. Slabs count as thick cards.
**Who it helps:** The Fulfiller, who matches pictures more easily than counting cards.
**Why now:** At 3 orders a day the position numbers drift a little every day. The fix stays cheap while the boxes are few and the photos already exist.
**Rough shape:**
- The pull screen shows a side view of the section, with the target card lit at its depth.
- The two neighbour cards are shown above and below the target.
- "Not here" opens the photos of the next five cards on either side, so the Fulfiller can search nearby.
- After the pull, the gap closes in the map with no step from the Fulfiller.
**Risk:** If a neighbour has itself been misfiled, the clue points to the wrong place.

**2. Name:** Box census by re-feed
**The idea:** Once in a while, feed a whole box back through the rig and compare what passes the camera with what the map expects. The check compares new photos against the store's own photos on the Mac, so it calls no paid identify step. The result is a picture of the box showing missing cards, extra cards and cards out of order.
**Who it helps:** The owner, who must be sure every card on the map is really there.
**Why now:** The rig takes about 30 minutes per box, so a full count of all 6 boxes is an afternoon. Misfiles from returns and hurried pulls build up without anyone seeing them, and a listed card that is not in the box costs a cancelled order.
**Rough shape:**
- Pick a box, feed it, and get a strip map of its sections, each coloured by how well it matches.
- Each mismatch shows two photos: the card that was expected and the card that came past the camera.
- One tap accepts the box as it now stands, or marks a card as lost so its listing comes down.
- Each box shows the date of its last count.
**Risk:** Matching against old photos may fail on reflective foils or slabs, and false alarms teach the owner to ignore the check.

**3. Name:** Fill, gaps and heat planner
**The idea:** Draw each box as sections whose width is the number of cards held, coloured by how often that section is pulled and how much its cards are worth. From that the planner suggests two moves. The first squeezes thinned-out sections together to free a box. The second sets aside a small front section for the cards pulled most often and the valuable ones, and the map tracks that they moved.
**Who it helps:** The owner, when planning new intake and room space. The Fulfiller, because busy-day pulls stay near the front.
**Why now:** Boxes hold anywhere from 545 to 732 cards, so some are already uneven. On a 39-order day the walk across 6 boxes adds up. New intake needs to know where each set has free space before the cards are photographed.
**Rough shape:**
- A top-down view of the shelf, with each box's fill level and a heat colour per section.
- "New batch of set X" shows which section has room, or where a new divider goes.
- The re-pack plan is a checklist of moves, each a section, never a single card, and the map updates as each is ticked.
- A monthly note such as: "Box 4 is 38% empty. Merge it into Box 3 to free a box."
**Risk:** A front section for popular cards breaks the strict set-and-number order that makes cards easy to find without the map.

**Bet:** Build "Find a card by its neighbours" first. The Fulfiller uses it every day, it keeps working as the boxes change, and it needs no new hardware and no paid step. The census can come next, since it needs a matching step that compares photos.
