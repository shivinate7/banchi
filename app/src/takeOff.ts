import { describeFailure, masterTakeOff, type Failure } from './server'
import type { MasterTakeOff, OwedTakeOffResult } from './types'

/* THE MASTER-SET TAKE-OFF'S ONE VOCABULARY (`docs/specs/master-set.md`, section 5), read by the
 * retire receipt (`TakeOffLine.tsx`) and the owed list on the send card (`SendCard.tsx`). A
 * press has one answer in the same six words wherever it was pressed. */

/** Where a take-off stands, as the screens say it. `offer` is the press, before it is pressed. */
export type TakeOffView = 'offer' | 'sent' | 'failed' | 'matches' | 'onway' | 'nosession'

/** What one press came to. `taken` is the copies the take-off row removes; `checkAfter` is when
 *  the live check can settle it, known only for a press made through the card's own route. */
export type TakeOffOutcome = {
  readonly view: Exclude<TakeOffView, 'offer'>
  readonly taken: number
  readonly checkAfter: string | null
  readonly failure: Failure | null
}

/** The server's state word as a view. `failed` and `offered` both carry a press. */
export function viewOf(state: MasterTakeOff['state']): TakeOffView {
  switch (state) {
    case 'offered':
      return 'offer'
    case 'on_its_way':
      return 'onway'
    case 'no_session':
      return 'nosession'
    default:
      return state
  }
}

/** A press that reached TCGplayer and was accepted reads `on_its_way` until a live check settles
 *  it, so on an answer to a press it is `sent`: the push went through. */
function afterPress(take: MasterTakeOff, checkAfter: string | null): TakeOffOutcome {
  const view = take.state === 'on_its_way' || take.state === 'sent' ? 'sent' : viewOf(take.state)
  return { view: view === 'offer' ? 'failed' : view, taken: take.taken_off, checkAfter, failure: null }
}

/** A refusal or a failed push, as a view. A take-off already on its way and a missing sign-in
 *  are states of their own; any other refusal leaves the take-off owed, with the press again. */
export function refused(failure: Failure): TakeOffOutcome {
  if (failure.code === 'take_off_outstanding') return { view: 'onway', taken: 0, checkAfter: null, failure }
  if (failure.code === 'take_off_no_session') return { view: 'nosession', taken: 0, checkAfter: null, failure }
  return { view: 'failed', taken: 0, checkAfter: null, failure }
}

/** One card's press: `POST /inventory/<box>/<index>/take-off`, whatever it answers or refuses. */
export async function pressTakeOff(box: number, index: number): Promise<TakeOffOutcome> {
  try {
    const answer = await masterTakeOff(box, index)
    return afterPress(answer.take_off, answer.send?.check_after ?? null)
  } catch (err) {
    return refused(describeFailure(err))
  }
}

/** One entry of `POST /pipeline/sends/owed`, answered. */
export function outcomeOfOwed(result: OwedTakeOffResult): TakeOffOutcome {
  if (result.take_off !== null) return afterPress(result.take_off, null)
  return refused({ code: result.refused ?? 'unknown', message: result.message ?? '', kind: 'refusal' })
}
