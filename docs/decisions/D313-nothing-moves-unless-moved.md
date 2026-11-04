# D313 — Nothing on screen moves unless the person moved it

**No element changes place or size unless the person moved it.** A late read, a press, a re-read
and a changed string are not the person. The owner's rule: reserve space so loading elements
cause no layout shift. It is the first case of this rule. Later cases join the same table.

**One exception, by the owner's word: the Review band sheet's title count.** The sheet titled "N Waiting for a Paid Look" (and its three siblings) shows the band's live count in its title, so the count updates when a run ends. The sheet's rows stay a snapshot, and the held line "The count has moved" with "Show it again" stays for them. The exception covers the title's number and nothing else on that sheet. `docs/specs/identify-engine-pick.md`, section 10.1, holds the behavior.

**The cases are rows of one table.** `app/tests/stability.spec.ts` holds the table. A case is a
name, the widths it runs at, and the way it provokes motion. A new class of shift adds a row.
It adds no file. The measure is the browser's `layout-shift` entry with no recent-input
exclusion (`app/tests/layoutShift.ts`). A sum of 0.01 or more fails a loading case. A press case
allows 0.0005 in the 500 ms after the press.

**Case: loading.** Every area that fills from a read reserves its final box from the first
paint. The spec reads `ROUTES` at run time and opens every nav screen, plus the Fulfiller's, at 1440 and 820 with each
read held 800 ms. A new screen is covered with no edit to the spec.

**Case: a sale press.** The press that sells a copy moves nothing. A line that the sale rewrites
holds a fixed line box, so a different string cannot change a height.

**Case: the Capture rail's far tiles.** A capture adds a tile at the top and moves every older tile one cell. Every tile
of the sitting stays a real row (D164): in the tab order, counted by a screen reader, never blank. A tile outside the
rail's own view keeps its row button and nothing under it (`capture-undo-far`, set by the rail's `IntersectionObserver`),
at the thumbnail's own 9:16 box, so it holds its size when it comes near. A scroll wakes the tiles one list-size ahead
before they paint. A capture, an undo or a resize wakes the tiles that came into view, and focus wakes its tile. All of
them read where a tile sits now, never an observer's answer from a frame ago. A rail that holds still for 150 ms sends the
tiles out of view back. `content-visibility: auto` cannot do it,
because Chrome judges it against the page viewport plus a margin of several screens and never the rail's scroller.
`app/tests/capture-freeze.spec.ts` measures it: each added tile costs at most 3 layout objects.

**The box comes from construction, never from a tuned pixel.** Three ways are allowed, in this
order:

- The loading state is drawn in the loaded state's own elements and classes. Each box takes its
  size from its own rule. A skeleton bar over a transparent sentence in the loaded grammar
  wraps where the loaded sentence wraps.
- The kit's `Skeleton` or `Loading`, sized by the loaded content's own rule.
- Space reserved from what the screen already knows, such as counts from `/status`.

A pixel height typed to fit the Mac's fonts is refused. CI renders on Linux, and a number tuned
to one font is wrong on the other.

**An exception is a shrinking list.** `app/tests/stability-allow.json` maps `<case>:<screen>`
to a reason. A listed screen is measured and not failed. An entry that now passes fails the
spec. The list only shrinks (D280, lists of offenders).

**What a frame cannot know stays a named residue.** A frame cannot know whether a loaded line
wraps once a count lands. It cannot know which variant of a status line a store earns. The frame
takes the common variant. The budget bounds the rest.

**Enforced** by `app/tests/stability.spec.ts`, and for the rail by `app/tests/capture-freeze.spec.ts`.

**NOT MECHANIZED:** the rule that a fix leaves the loaded screen unchanged. A machine cannot tell
a loaded frame that changed from one that only loads differently.
