/* Whatever fires a capture, behind one interface — docs/specs/capture-app.md section 6.
 *
 * The seam was the deliverable before either implementation mattered, and on 2026-08-22 it
 * paid out: Gate B ran on the key press below, and the motion state machine
 * (src/motion.ts, Gate C's trigger) dropped into the same slot as a second Trigger with no
 * change to the capture screen's caller — which was the whole promise. The screen still
 * never learns which one is behind it, except through `name`.
 *
 * A Trigger fires. It never decides whether the app is in a state to capture. That split
 * held up exactly as hoped when the second implementation arrived: a cooldown between
 * frames is the trigger's own business, while "a request is already in flight" and "no box
 * is selected" belong to the screen — and motion mode adds one obligation on the screen's
 * side of that line, counting the fires it declines (docs/specs/motion-trigger.md §3),
 * because under a feeder a silently swallowed fire is a card with no record.
 */

export type Trigger = {
  /** Which implementation is behind the seam, as a greppable machine string —
   *  `manual:Space` today, `motion` at Gate C. docs/DESIGN.md's idiom for exactly this:
   *  a machine string shown small beside a human label, so that what you saw on screen
   *  can be found in the source. */
  readonly name: string

  /** Arms the trigger and returns its teardown.
   *
   *  Deliberately the shape of a React effect's return value, because that is the only
   *  caller: `useEffect(() => trigger.start(onFire), [trigger, onFire])`. A trigger that
   *  needed a separate `stop()` would leak a listener the first time someone forgot, and
   *  StrictMode's double mount would leave two of them armed — one key press, two
   *  captures, two positions burned. */
  start(onFire: () => void): () => void
}

/** Key names as a human reads them. Only `name` uses this; the on-screen hint is the
 *  capture screen's, built from the key it passed in. */
function keyLabel(key: string): string {
  if (key === ' ') return 'Space'
  if (key === 'Enter') return 'Enter'
  return key
}

/* Focus that swallows the key. INPUT and TEXTAREA are the obvious pair — the set hint is
 * free text (docs/specs/capture-app.md section 5.3) and typing a set name must not
 * photograph five cards.
 *
 * SELECT is in the list for a less obvious reason: a native select does letter typeahead,
 * so with the box or camera list focused, a single-letter trigger key would both jump the
 * list and fire a capture. The camera picker on this same screen is a select, which makes
 * that a real collision rather than a hypothetical one. contentEditable is here for
 * completeness and costs one clause.
 */
function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

/** Gate B's trigger: one key, pressed by the owner. */
export function manualTrigger(key: string): Trigger {
  return {
    name: `manual:${keyLabel(key)}`,

    start(onFire) {
      const onKeyDown = (event: KeyboardEvent) => {
        if (event.key !== key) return

        /* Auto-repeat is a held key, and a held key is a stack of captures of one card
         * sitting in the lens. Undo walks backwards one call at a time
         * (docs/specs/capture-app.md section 3), so the cleanup is linear in a mistake
         * that takes one second to make. */
        if (event.repeat) return

        /* Modifiers belong to the browser and the OS. A capture fired by Cmd-Space is a
         * capture nobody asked for, and worse, it is one taken while the owner was
         * looking at Spotlight rather than at the card. Shift is deliberately not in this
         * list: `event.key` already carries the shifted character for letter keys, so a
         * shifted Space is still the key that was asked for. */
        if (event.metaKey || event.ctrlKey || event.altKey) return

        if (isEditableTarget(event.target)) return

        /* Space scrolls the page by default, which would walk the live preview off screen
         * on the one screen where it is the whole point. Only prevented on the path that
         * actually fires, so every ignored press above keeps its normal behaviour. */
        event.preventDefault()
        onFire()
      }

      window.addEventListener('keydown', onKeyDown)
      return () => window.removeEventListener('keydown', onKeyDown)
    },
  }
}
