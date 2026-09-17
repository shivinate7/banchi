17. ~~**The order pipeline: the ledger, the order screen, the shipping lane**~~ — **done
    2026-08-30.** D48, D61, D63, D64, D65, D66, D69, D71 — steps 8 to 12 of
    `docs/specs/order-pipeline.md`. D63's two-map ledger, D64/D65's fetched Filtered Export
    with completeness as a delta rather than a claim, `#/orders` saying which copies a buyer
    gets and where they are, and `#/shipping` routing a real export into D61's three lanes,
    the third of which is *"I cannot tell"*. `server/order_transport.py` fetches this
    account's own orders over the cookie session D69 measured before it was written.
    **What this step did NOT do** is step 20 below — the shipped status and the tracking
    write-back. Both endpoints were seen on the wire and deliberately left alone.
