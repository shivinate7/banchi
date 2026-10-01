## D-loading-holds-loaded-size — A loading area holds its loaded size

**Every area that fills from a read reserves its final box from the first paint.** Nothing on
the page moves when data lands. The owner's rule: reserve space so loading elements cause no
layout shift.

**The box comes from construction, never from a tuned pixel.** Three ways are allowed, in this
order:

- The loading state is drawn in the loaded state's own elements and classes. Each box takes its
  size from its own rule. A skeleton bar over a transparent sentence in the loaded grammar
  wraps where the loaded sentence wraps.
- The kit's `Skeleton` or `Loading`, sized by the loaded content's own rule.
- Space reserved from what the screen already knows, such as counts from `/status`.

A pixel height typed to fit the Mac's fonts is refused. CI renders on Linux, and a number tuned
to one font is wrong on the other.

**The measure is the browser's.** `app/tests/load-shift.spec.ts` reads `ROUTES` at run time.
It opens every nav screen at 1440 and 820 with each read held 800ms. It sums `layout-shift`
entries over the first 3s with no recent-input exclusion. A sum of 0.01 or more fails. A new
screen is covered with no edit to the spec.

**An exception is a shrinking list.** `app/tests/load-shift-allow.json` names a screen and its
reason. The list only shrinks (D280, lists of offenders).

**What a loading frame cannot know stays a named residue.** A frame cannot know whether a loaded
line wraps once a count lands. It cannot know which variant of a status line a store earns.
The frame takes the common variant. The spec's budget bounds the rest.

**Enforced** by `app/tests/load-shift.spec.ts`.

**NOT MECHANIZED:** the rule that a fix leaves the loaded screen unchanged. A machine cannot tell
a loaded frame that changed from one that only loads differently.
