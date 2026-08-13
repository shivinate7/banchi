import './PullConfirm.css'

/* The pull-confirm button. Build-order step 6 requires one component built against the
 * locked tokens and looked at before any screen, and docs/DESIGN.md names this one.
 *
 * It is the confirmation in D6's pull modal: the Fulfiller sees the card's own capture
 * photo beside its location, and this is what he presses. Per docs/DESIGN.md's copy
 * rules the label is what happens, and it keeps its name through the flow — the button
 * that says "Pull" produces a confirmation that says "Pulled".
 */

export type PullConfirmProps = {
  /** What happens when it is pressed. Active voice, and the same word the confirmation
   *  will use. Not "OK", not "Confirm". */
  label: string

  onConfirm: () => void

  /** Never true in the Fulfillment view — docs/DESIGN.md gives that view no disabled
   *  state at all. Owner-side screens may disable it. */
  disabled?: boolean

  /** Owner-side only. Omitted renders no chip, which is the Fulfillment case: those
   *  screens are touch and show no keys. */
  keyHint?: string
}

export function PullConfirm({ label, onConfirm, disabled, keyHint }: PullConfirmProps) {
  return (
    <button className="pull-confirm" type="button" onClick={onConfirm} disabled={disabled}>
      <span className="pull-confirm-label">{label}</span>
      {keyHint === undefined ? null : <kbd className="pull-confirm-key">{keyHint}</kbd>}
    </button>
  )
}
