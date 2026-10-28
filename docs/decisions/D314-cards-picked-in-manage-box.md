# D314 — Cards for a bulk box action are picked inside Manage box

**The Inventory list carries no ticks.** Cards for a bulk box action are picked inside Manage box, in the sheet of the act that uses them. Move and Claims each open on the whole box. "Some cards" in the sheet narrows them. The sheet lists the box's on-hand cards by section, with a check per card and per section (partial while some are picked), and All and None. All cards picked is the whole box, so the write sends no index list. None picked refuses the press.

**Outcome protected.** The list never changes shape on a tick (D313: nothing on screen moves unless the person moved it). The selection sits beside the act that uses it, with that act's receipt and way back. A tick count in a toolbar was rejected: it built one argument of two writes and changed the toolbar's size.

**What stays.** `moveCards` and `applyBoxClaims` take the same indices as before. Nothing about a card is stored on the device. Move lists on-hand cards only. Claims also lists departed records, in their own group "Sold or moved out", so one can be claimed alone. A departed record can be claimed, not moved.
