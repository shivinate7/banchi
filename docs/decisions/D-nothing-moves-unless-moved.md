## D-nothing-moves-unless-moved — Nothing on screen moves unless the person moved it

**No element changes place or size unless the person moved it.** A late read, a press, a re-read
and a changed string are not the person. The owner's rule: reserve space so loading elements
cause no layout shift. It is the first case of this rule. Later cases join the same table.

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

**Enforced** by `app/tests/stability.spec.ts`.

**NOT MECHANIZED:** the rule that a fix leaves the loaded screen unchanged. A machine cannot tell
a loaded frame that changed from one that only loads differently.
