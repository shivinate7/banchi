import { useCallback, useRef, useState } from 'react'

import { describeFailure, reconcileLive, type Failure } from './server'
import { readUpload } from './csvUpload'
import './LiveReconcile.css'

/* THE FOURTH COMMAND, OVER THE WHOLE STORE (D87).
 *
 * WHY IT IS ON `#/runs` AND NOT ON `#/inventory`. This screen's own lede names the four
 * commands — *"identify · join · emit · reconcile"* — and this is the fourth one, in the only
 * shape that can answer the question it is for. `#/inventory` is where a card's state is
 * changed, and this changes no card's state: it moves QUANTITIES held against a SKU (D7), and
 * deliberately marks nothing sold.
 *
 * IT IS NOT RUN-SCOPED AND THE PANEL SAYS SO, because everything else on this screen is. The
 * per-run reconcile lives in `RunPanel` and stays: it answers one import against one Export
 * From Staged. This answers the store against a full live export, which is the only document
 * that can report the other direction — SKUs TCGplayer holds that this pipeline never sent.
 *
 * TWO PRESSES, AND THE FIRST ONE WRITES NOTHING. The same shape D33 gave the money gate and
 * `pkmnscan prices adopt` gave the migration, for the reason both give: this settles the
 * quantities `pipeline/join.py`'s cap arithmetic reads, over every SKU at once, and a
 * settlement nobody read is how a wrong number becomes the new floor. Measured on the owner's
 * store the first time it ran: 1,125 copies drawn down, and 55 it could not explain.
 */
export function LiveReconcile() {
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<string | null>(null)
  const [wrote, setWrote] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  /* THE FILE IS HELD SO THE SECOND PRESS SENDS THE SAME BYTES. Re-picking it for the write
     would let the preview and the settlement describe two different exports, which is the
     straddle `do_pipeline_pricing` already argues about one level down. */
  const held = useRef<Awaited<ReturnType<typeof readUpload>> | null>(null)

  const send = useCallback(async (write: boolean) => {
    const file = held.current
    if (file === null) return
    setBusy(true)
    setFailure(null)
    try {
      const answer = await reconcileLive(file, { write })
      setReport(answer.console)
      setWrote(answer.wrote)
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }, [])

  return (
    <section className="livecheck" aria-labelledby="livecheck-head">
      <h2 className="livecheck-head" id="livecheck-head">
        Reconcile the whole store
      </h2>
      <p className="livecheck-says">
        One live export — TCGplayer&rsquo;s <strong>My Pricing</strong>, all printings —
        against every SKU in the store, whatever run or box it came from. Reports both
        directions: copies this pipeline sent that TCGplayer no longer holds, and SKUs it holds
        that were never sent from here. It moves quantities and marks no card sold.
      </p>

      <div className="livecheck-row">
        <label className="livecheck-pick">
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              const file = event.currentTarget.files?.[0]
              if (file === undefined) return
              setReport(null)
              setWrote(false)
              setFailure(null)
              void readUpload(file)
                .then((upload) => {
                  held.current = upload
                  return send(false)
                })
                .catch((err) => setFailure(describeFailure(err)))
            }}
          />
        </label>
        {report === null || wrote ? null : (
          /* ABSENT UNTIL THE PREVIEW HAS ANSWERED, which is D33's rule for the control that
             spends applied to the one that settles: a button that exists before there is
             anything to read is a button pressed before anything was read. */
          <button
            type="button"
            className="livecheck-settle"
            disabled={busy}
            onClick={() => void send(true)}
          >
            {busy ? 'Settling…' : 'Settle the ledger'}
          </button>
        )}
      </div>

      {failure === null ? null : (
        <div className="livecheck-note">
          <p className="livecheck-note-text">{failure.message}</p>
          <p className="livecheck-machine">{failure.code}</p>
        </div>
      )}

      {report === null ? null : (
        /* THE COMMAND'S OWN STDOUT, VERBATIM (D33). Summarising it here would be a second
           opinion about which of the four answers mattered, taken on the operator's behalf at
           the one moment the ledger changes. */
        <pre className="livecheck-console">{report}</pre>
      )}
    </section>
  )
}
