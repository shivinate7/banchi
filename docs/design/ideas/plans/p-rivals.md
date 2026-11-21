# p-rivals

**Thin Shelf Finder**
**The idea:** Many sellers list the same card, but not evenly. Near Mint copies of recent sets are crowded, while played copies, older sets, odd variants and graded slabs often have only a few sellers. A per-set crowd map shows where this store is one of a handful of sellers and where it is one of hundreds. The owner then puts their price attention where it can change the outcome.
**Who it helps:** The owner, who sets prices and picks which cards to photograph and identify next.
**Why now:** The paid identify step costs money per card. Knowing which sets have few sellers tells the owner which batch to pay for first.
**Rough shape:**
- A set list colored crowded, mixed or thin, with each condition shown as its own column.
- Opening a set shows each card's competing listing count beside the store's own copy.
- A "fights worth picking" queue lists thin-shelf cards where this store's copy is a strong offer.
- A flag on crowded cards says "match market, spend no attention".
**Risk:** Listing counts must come from views a seller may legitimately use, by hand or from marketplace data, never from scraping that breaks the terms.

**Set Depth Cart Magnet**
**The idea:** Buyers often want one shipment, and the marketplace's cart tools favor a seller who can fill more of a cart. Cards arrive in set-and-number runs, so this store often holds deep runs of a set that a typical seller holds only in part. Find those sets, keep them fully listed, and price the run as a whole. The store wins the multi-card order rather than the one-card race.
**Who it helps:** Buyers finishing a set. The Fulfiller, because many cards from one section are faster to pull than scattered singles. The owner, whose cheap cards only earn money in bundles.
**Why now:** The order exports already show which orders had several cards from one set. Knowing each card's box, section and position makes a deep order cheap to pull, a cost edge other sellers lack.
**Rough shape:**
- A depth score per set: how much of the set is listed, and whether there are gaps.
- A "gap" list of missing numbers in deep sets, to fill from unlisted stock first.
- After each order import, a tally of multi-card orders by set shows which sets draw bundles.
- A pull estimate for a bundle order: cards, sections and boxes.
**Risk:** How the cart tool chooses sellers is not published, so the gain can only be measured by watching orders change.

**Photo-Proof Condition Honesty**
**The idea:** On a valuable card, a buyer distrusts a "Near Mint" claim from a tiny seller with few ratings. Every card already has a capture photo. For the top value tier and the slabs, grade condition conservatively from that photo, and where the marketplace allows it, show the real card. Honesty becomes the reason a buyer picks this store over a cheaper copy from an unknown seller.
**Who it helps:** The owner, through fewer returns and disputes and better ratings. Buyers of expensive cards.
**Why now:** The photos already exist at no added cost. On a few valuable cards, one dispute costs more than a week of cheap sales.
**Rough shape:**
- A short queue of high-value cards, each shown with its capture photo at full size.
- The owner confirms or lowers the condition with one press. The default is the lower grade.
- A record of condition disputes and returns, broken down by condition and value tier.
- A "photo available" mark on listings where the marketplace supports photos.
**Risk:** Whether a seller of this size can attach photos to listings is unknown, so the gain may shrink to conservative grading alone.

**Bet:** Set Depth Cart Magnet first. It rests on things only this store has: deep sorted runs, and a known box, section and position for every card. It can start from the store's own order exports, with no outside data. It also serves the most cards, the cheap ones.

Note: the brief said not to read the repository, so none of these ideas was checked against existing features or records.
