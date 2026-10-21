## DEBT-fulfil-stock-art — Fulfillment still shows the owner's photo first

**The owner ruled that Fulfillment shows the catalog image first, with the owner's own photo one press away** (lean-server spec, section 6, Q2 and Q6). `#/fulfillment` still shows the capture photo (`previewUrl`) first.

- **Ruled change.** Stock image first. One press, 40px or more and labeled in a sentence, loads the real photo. A card with no stock image shows the real photo. The image box holds its size across the swap (D313, nothing moves unless the person moved it). Which cards and orders a pull holds does not change.
- **Where.** `app/src/Fulfillment.tsx` and `Fulfillment.css`. The stock URL comes from `pipeline/stockimages.StockImages`, the same path the Orders walk reads (`image_url ?? photoUrl` in `OrdersWalkPane`). If the Fulfillment wire lacks `image_url`, add it in the existing route and `app/src/types.ts`.
- **Proof.** A Playwright spec shown red on main first: stock first, the press loads the real photo, a no-stock card shows the real photo. Screens checked at 1440 and 820, both themes. `make design-check` green.
- **Decisions it weakens.** D38 (the photo is sized to confirm a slot) and D6 (the pull modal shows the card's own capture photo). Cite them and do not repeal them.
- **Not fixed because** the owner parked the lane.
- **Closes when** the change above ships.

**Outcome at risk.** The Fulfiller keeps loading full capture photos, which the owner ruled against.
