# Sets view, master set: design notes

Lane kind: informed. Mockup: `inventory-sets.html`. Spec: `docs/specs/master-set.md`, sections 4
and 3. Component: `InventorySets.InventorySets`, drawn when `#/inventory?view=sets`. The frame
draws the spec as written. The Options panel under the frame draws each alternative, and each has
a control that hides it.

Deep links: `#s=off`, `#s=on`, `#s=all`, `#s=none`. Add `&w=820` for the iPad width and
`&t=dark`, `&t=abyssal-bloom` or `&t=carnival-midway` for a theme. With no `t`, the page follows
`prefers-color-scheme`. `&h=O1,O3` hides options.

The CSS is the repo's own sheets, inlined at the time of drawing: `tokens.css`, `base.css`,
`kit.css`, `kit/data.css`, `kit/filters.css`, `InventorySets.css`. The proposed rules are at the
end, under "PROPOSED". Stock photos are flat placeholders at 63 by 88, so the page loads nothing.

1. **The filter is the kit's `HideToggle`, under the set picker.** Gain: one filter shape on every
   screen, and it carries its count. Loss: none. Pick: yes. Its state is `?master=open` (D285,
   filter, sort and search live in the URL).
2. **The filter's words (option O1).** The spec says "Not in my master set". `HideToggle` draws the
   count of rows it hides, so the control reads "Not in my master set 38" while 38 rows are IN
   the master set. "Hide my master set 38" reads true. Gain: the count and the words agree. Loss:
   the spec's words change. Pick: O1. **Owner grant: yes.**
3. **The filter beside the picker (option O2).** Gain: one row less above the grid. Loss: the spec
   says "under". Pick: under, as the spec says.
4. **The mark has its own line, the height of a pill, on every tile.** A tile with no mark keeps
   the empty line. Gain: a tile's height never depends on its mark (D313, nothing moves unless the
   person moved it). Loss: one pill line on each tile. Pick: yes.
5. **The mark on the image corner (option O3).** Gain: no extra line. Loss: a pill over a photo
   needs a solid ground, and it covers the card's art. Pick: no.
6. **The mark as a shape, named once in a key (option O4).** The house rule ux-label-once says a
   status word shows once per screen. The spec says each mark is "named in words" on the tile.
   Gain: the grid reads by colour; the key names it once. Loss: the colour alone carries meaning
   on the tile, so a reader must learn the key. Pick: the words, as the spec says. Taking O4 is
   **Owner grant: yes.**
7. **Tones.** In master set is `ok` (green). Last copy is `warn` (amber). Never `live`: vermilion
   means "happening now" only. Option O5 draws Last copy in the accent. Loss of O5: the accent means
   "press this". Pick: amber.
8. **A collected row wins over a single copy.** Toedscruel holds two copies and Charizard ex holds
   one; both say In master set. Gain: one mark per tile. Pick: yes.
9. **Last copy beside "1 copy" (option O6).** The two say the same thing. O6 drops the "1 copy"
   pill on a Last copy tile. Loss: the count is not in the same place on every tile. Pick: keep
   both.
10. **A collected row with no copy on hand (Wugtrio, Klefki).** Today's `count` helper draws
    "0 copies". Option O7 draws "None on hand" and dims the image. Loss of the dim: a dimmed tile
    looks disabled, but it still opens the walk. Pick: "0 copies", no dim.
11. **The header count.** "38 of 190 in your master set" joins the header as its last part. The
    part before it, "247 cards", counts copies, and "190" counts rows, so two numbers on one line
    count different things. Option O8 says "247 copies". Pick: O8. It changes today's words only,
    not the spec.
12. **The header and the toggle hold still.** The count does not change when the filter turns on.
    The picker, the toggle and the header keep their boxes between `#s=off` and `#s=on`; the
    headless check measured them.
13. **A filter that empties the grid (`#s=all`).** One sentence, "Every card of this set is in
    your master set.", and one control, "Show every card", that turns the filter off
    (ux-empty-one-action).
14. **A set with nothing collected (`#s=none`).** The toggle stays and reads 0. The house rule
    ux-control-earns-place says a control that changes nothing is absent, but then the header
    moves when the person changes the set. Pick: the toggle stays, with its zero.
15. **Order holds.** The filter hides rows and never re-sorts them (spec section 4).
16. **At 820** the frame states the coarse-pointer control heights (42 px field, 40 px segment),
    because a desktop browser never matches that query. Every control there measured 40 px or more.
