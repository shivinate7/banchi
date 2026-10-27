import { useState } from 'react'

import { count } from './kit/dataRules'
import { holdToast, ToastLine, ToastPress } from './kit/toast'
import { pressTakeOff, viewOf, type TakeOffView } from './takeOff'
import type { MasterTakeOff } from './types'

/* THE TAKE-OFF LINE ON A MASTER-SET RETIRE RECEIPT (`docs/specs/master-set.md`, section 5): "Take
 * It Off TCGplayer" at the pull, and the answer in the same place. Whatever is left undone waits
 * on Pricing's send card, and the line says so. The toast fades 20 seconds after the pull; while
 * the press runs it waits (`holdToast`), and the answer then stands for a full receipt's time. */

/** The card the receipt is for, and where its take-off stood when the card was retired. */
export function TakeOffLine({
  box,
  index,
  name,
  start,
  toastId,
}: {
  readonly box: number
  readonly index: number
  readonly name: string
  readonly start: MasterTakeOff
  /** The receipt's toast id, set once the toast exists: a press happens later than the toast. */
  readonly toastId: { current: number }
}) {
  const [view, setView] = useState<TakeOffView>(viewOf(start.state))
  const [busy, setBusy] = useState(false)
  const [taken, setTaken] = useState(start.taken_off)
  /* The copies TCGplayer lists above what is on hand: what the store reckoned at the pull. */
  const listed = Math.max(1, start.excess)
  const off = taken > 0 ? taken : listed

  const press = async () => {
    setBusy(true)
    holdToast(toastId.current, true)
    const outcome = await pressTakeOff(box, index)
    setView(outcome.view)
    setTaken(outcome.taken)
    setBusy(false)
    holdToast(toastId.current, false)
  }
  const pressWith = (label: string) => (
    <ToastPress busy={busy} onPress={() => void press()}>
      {label}
    </ToastPress>
  )

  return (
    <ToastLine
      current={view}
      states={{
        offer: {
          text: `TCGplayer still lists ${count(listed, 'copy', 'copies')} you no longer hold. Leave it, and Pricing keeps it on a list.`,
          press: pressWith('Take It Off TCGplayer'),
        },
        sent: {
          tone: 'ok',
          icon: 'check',
          text: `TCGplayer accepted: ${count(off, 'copy', 'copies')} of ${name} ${off === 1 ? 'is' : 'are'} off. Undo lists ${off === 1 ? 'it' : 'them'} again at your next send.`,
        },
        failed: {
          tone: 'danger',
          icon: 'alert',
          text: 'TCGplayer did not take it, so nothing went live. It waits on Pricing, and the card stays in your master set.',
          press: pressWith('Try again'),
        },
        matches: { tone: 'ok', icon: 'check', text: 'TCGplayer already lists only what you hold. Nothing was sent.' },
        onway: { tone: 'info', icon: 'info', text: 'The take-off is on its way to TCGplayer. Pricing shows it until it is done.' },
        nosession: {
          tone: 'warn',
          icon: 'alert',
          text: `TCGplayer is not signed in, so ${count(listed, 'copy', 'copies')} ${listed === 1 ? 'stays' : 'stay'} listed. It waits on Pricing until you sign in.`,
        },
      }}
    />
  )
}
