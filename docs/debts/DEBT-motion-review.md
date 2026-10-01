## DEBT-motion-review — no motion designer has reviewed the app's animation

The app's motion is built screen by screen, by the agent that builds each screen. The design
system sets the floors: motion is tokens, `prefers-reduced-motion` is honored, a press dips
with `translate`, and only loops that carry meaning keep turning. Nobody with motion-design
skill has reviewed the whole app for feel, timing and consistency.

**What it costs:** each animation passes its own spec, but the set is unreviewed as a whole.
Durations, easing and entry styles can drift from screen to screen. Only the owner finds a
motion defect that no spec names. The copy-row jiggle is an example: a row's entry slide
moved a snap list.

**Why it is not fixed:** a professional review is out of scope for now, by the owner's word.
The Mark sold button's sale animation (a drawn-bills burst, then a framed Undo) is the newest
motion. Review it first.

**Closes when:** a motion-design pass reviews every animated surface (the row entries, the
press and hover states, the sale burst, the sheets and the skeletons) and its findings land
as tokens, spec changes or new debts.
