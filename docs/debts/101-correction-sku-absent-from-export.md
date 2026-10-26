## DEBT101 — a sent copy whose SKU left the live export is refused every time

**A sent copy whose SKU is missing from the live export keeps `live` at 1 or more, and the correction refuses it every time. The refusal's way out does not clear it.** This happens when the listing was deleted on TCGplayer and not zeroed.

- **Result:** `old_sku_still_live` (D252) answers each correction of that copy. The sentence says to take the listing down, then Refresh, then Match the store. The listing is already down, and Match the store has no row to read for that SKU, so `live` stays where it was.
- **Unmeasured:** whether TCGplayer drops a deleted listing's row from the live export, or exports it with a quantity of zero. Nothing has been measured.
- **Not fixed because** the gap is not measured. Fixing it blind would let a correction through while a copy may still be live, which breaks the owner's word that one physical copy is never listed under two SKUs.
- **Closes when** a real export shows what a deleted listing looks like, and either Match the store zeroes a SKU that has left the export or the refusal names another way out.
- **Points to** D252 (a wrong answer gets a correct route) and `docs/specs/identity-follows-sku.md`.

**Outcome at risk.** The owner cannot correct a sent card whose listing is gone, and the screen gives no working step.
