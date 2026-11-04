## DEBT-stale-cache-fault-looks-like-id — a stale list makes a network fault look like an unknown set

**What.** After a failed refetch, `pipeline/pricehistory.Market`'s `get` and `group_id` serve the stale catalog list, so a set missing from that list raises `NotResolvable`, which `readings_for_rows` returns as an identification refusal without checking `serving_stale`.

**Harm.** A person reviews a card whose identification is fine. The fault was the network, not the card. D238 (archive refusals go to review) promises that a network refusal never reaches the queue, and this gap breaks that promise.

**Where.** `pipeline/pricehistory.Market`'s `readings_for_rows`. `pipeline/stockimages.py` already checks `serving_stale` on the same list, so the check has a precedent.

**Fix, when taken.** Check `serving_stale` before a `NotResolvable` becomes an identification refusal. While the list is stale, tag the refusal as network.

**Measured.** Unmeasured: how often a failed refetch leaves a set missing from the stale list, and how many queue entries that produced.
