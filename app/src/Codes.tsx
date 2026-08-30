import { useCallback, useEffect, useMemo, useState } from 'react'

import { describeFailure, exportCodes, getCodes, photoUrl, scanCodes, type Failure } from './server'
import type { CodeEntry, CodeExportResult, CodeLedger, CodeScanResult } from './types'
import './Codes.css'

/* THE CODE-CARD TRACK, ON A ROUTE OF ITS OWN — C9, C10 and C11.
 *
 * WHY IT IS NOT A PANEL ON `#/runs`. `#/runs` is the four commands of the SINGLES pipeline,
 * and every one of them is about resolving a card against a TCGplayer export and pricing it.
 * A code card is joined against nothing, priced against nothing, and identified by arithmetic
 * rather than by a paid model call — D14's "shares the rig, shares nothing downstream", which
 * is a track boundary rather than a screen-size problem. Putting it there would also put the
 * one control in this product that hands over a bearer instrument next to the one that spends
 * money, and those two want different confirmations for different reasons.
 *
 * THE SCREEN'S WHOLE JOB IS C11's TIER. A Pokemon Center ETB code lists at roughly 46x a
 * booster code, and boosters are the overwhelming majority of any pile — so the pile is a long
 * flat floor with a few tall spikes in it, and the one mistake that actually costs money is
 * sweeping a spike into the floor's wholesale lot. Hence the two lanes are the first thing
 * drawn, hence an unclaimed code enters NEITHER lane, and hence the premium lane is drawn
 * first even though it is always the smaller number.
 *
 * NOTHING HERE SPENDS. There is no money gate because the code-card primary path makes no
 * model call at all. What it has instead is a commit gate, on the export: a code handed to a
 * buyer cannot be un-handed and double-selling one is unrecoverable (C3), so the export is a
 * preview until it is confirmed against a named order, and confirming reserves permanently.
 *
 * THE CODES ARE DRAWN IN THE CLEAR. That is the point of the screen — the owner reads a code
 * and pastes it to a buyer. The opsec rules govern what reaches a tracked file, and this
 * screen is deliberately absent from `scripts/views.txt` so `make screenshot` never renders
 * one to `captures/ui/`.
 */

type Lane = 'bulk' | 'premium'

/** A number the operator is about to act on, drawn big. */
function Tally({ n, label, tone }: { n: number; label: string; tone?: string }) {
  return (
    <div className={`codes-tally${tone ? ` is-${tone}` : ''}`}>
      <span className="codes-tally-n">{n}</span>
      <span className="codes-tally-label">{label}</span>
    </div>
  )
}

export function Codes() {
  const [ledger, setLedger] = useState<CodeLedger | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [busy, setBusy] = useState(false)

  const [box, setBox] = useState('')
  const [scan, setScan] = useState<CodeScanResult | null>(null)

  const [lane, setLane] = useState<Lane>('premium')
  const [preview, setPreview] = useState<CodeExportResult | null>(null)
  const [orderId, setOrderId] = useState('')
  const [committed, setCommitted] = useState<CodeExportResult | null>(null)

  const [filter, setFilter] = useState('')

  const load = useCallback(async () => {
    try {
      setLedger(await getCodes())
      setFailure(null)
    } catch (err) {
      setFailure(describeFailure(err))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const runScan = useCallback(
    async (dryRun: boolean) => {
      const n = Number(box)
      if (!Number.isSafeInteger(n) || n < 1) {
        setFailure({ code: 'box_required', message: 'Type the box number whose photographs should be scanned.' })
        return
      }
      setBusy(true)
      try {
        setScan(await scanCodes({ box: n, preview: dryRun }))
        setFailure(null)
        if (!dryRun) await load()
      } catch (err) {
        setFailure(describeFailure(err))
      } finally {
        setBusy(false)
      }
    },
    [box, load],
  )

  const runPreview = useCallback(async () => {
    setBusy(true)
    setCommitted(null)
    try {
      setPreview(await exportCodes({ lane }))
      setFailure(null)
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }, [lane])

  const runCommit = useCallback(async () => {
    if (!orderId.trim()) {
      setFailure({
        code: 'order_id_required',
        message: 'A confirmed export assigns codes to an order, so it needs a name.',
      })
      return
    }
    setBusy(true)
    try {
      const done = await exportCodes({ lane, confirm: true, orderId: orderId.trim() })
      setCommitted(done)
      setPreview(null)
      setOrderId('')
      setFailure(null)
      await load()
    } catch (err) {
      setFailure(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }, [lane, orderId, load])

  const rows = useMemo(() => {
    if (ledger === null) return []
    const needle = filter.trim().toLowerCase()
    if (!needle) return ledger.entries
    return ledger.entries.filter(
      (e) =>
        e.code.toLowerCase().includes(needle) ||
        (e.product_display ?? '').toLowerCase().includes(needle) ||
        (e.set_hint ?? '').toLowerCase().includes(needle) ||
        (e.order_id ?? '').toLowerCase().includes(needle) ||
        e.state.includes(needle),
    )
  }, [ledger, filter])

  return (
    <div className="codes">
      <header className="codes-head">
        <h1>Code cards</h1>
        <p className="codes-quiet">
          The QR carries the redemption code, so reading one costs nothing and calls nothing.
          What this screen decides is which of two populations a code belongs to — and the
          only mistake that costs real money is letting a premium code leave in a bulk lot.
        </p>
      </header>

      {failure === null ? null : (
        <p className="codes-fail" role="alert">
          {failure.message}
          {failure.code ? <code> {failure.code}</code> : null}
        </p>
      )}

      {/* ---------------------------------------------------------------- scan */}
      <section className="codes-panel">
        <h2>Read a box</h2>
        <p className="codes-quiet">
          Decodes every code-card photograph in one box. Free — no model call, no network.
        </p>
        <div className="codes-row">
          <label className="codes-field">
            <span>Box</span>
            <input
              inputMode="numeric"
              value={box}
              onChange={(e) => setBox(e.target.value.replace(/[^0-9]/g, ''))}
              placeholder="9"
            />
          </label>
          <button type="button" onClick={() => void runScan(true)} disabled={busy}>
            Preview
          </button>
          <button type="button" className="codes-go" onClick={() => void runScan(false)} disabled={busy}>
            Read the box
          </button>
        </div>
        {scan === null ? null : (
          <div className="codes-result">
            <p>
              <strong>
                {scan.decoded} of {scan.code_cards}
              </strong>{' '}
              code card{scan.code_cards === 1 ? '' : 's'} decoded
              {scan.preview ? ' (preview — nothing written)' : ''}.
              {scan.photographs !== scan.code_cards
                ? ` ${scan.photographs - scan.code_cards} photo(s) of other games were left alone.`
                : ''}
            </p>
            {scan.unread.length === 0 ? null : (
              <>
                <p className="codes-warn">
                  {scan.unread.length} card{scan.unread.length === 1 ? '' : 's'} did not read.
                  None is lost — each keeps its photograph and its position, and the remedy is
                  the next reader: the paid vision transcription, then a human.
                </p>
                <ul className="codes-unread">
                  {scan.unread.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
      </section>

      {/* ---------------------------------------------------------------- lanes */}
      {ledger === null ? (
        <p className="codes-quiet">Reading the ledger…</p>
      ) : (
        <>
          <section className="codes-panel">
            <h2>What is on hand</h2>
            <div className="codes-tallies">
              <Tally n={ledger.lanes.premium} label="premium — list individually" tone="premium" />
              <Tally n={ledger.lanes.bulk} label="bulk — sells by the lot" />
              <Tally n={ledger.lanes.unclaimed} label="no product claim" tone={ledger.lanes.unclaimed ? 'warn' : undefined} />
              <Tally n={ledger.counts.reserved ?? 0} label="reserved to an order" />
              <Tally n={ledger.counts.delivered ?? 0} label="delivered" />
              <Tally n={ledger.counts.dead ?? 0} label="dead" />
            </div>
            {ledger.lanes.unclaimed === 0 ? null : (
              <p className="codes-warn">
                {ledger.lanes.unclaimed} held code{ledger.lanes.unclaimed === 1 ? '' : 's'}{' '}
                {ledger.lanes.unclaimed === 1 ? 'carries' : 'carry'} no product claim, so{' '}
                <strong>neither lane will take {ledger.lanes.unclaimed === 1 ? 'it' : 'them'}</strong>. That is
                deliberate: treating an unclaimed code as a booster would be right most of the
                time, and the times it is wrong a $1.50 code leaves in a penny lot and nobody
                finds out. Set the Product field on the capture screen, or correct these cards
                on the inventory screen.
              </p>
            )}
            {ledger.by_product.length === 0 ? null : (
              <table className="codes-tiers">
                <tbody>
                  {ledger.by_product.map((row) => (
                    <tr key={row.product}>
                      <td className={row.premium ? 'is-premium' : ''}>
                        {/* THE LANE, NOT A GUESS AT IT. This cell drew `premium ? … : 'bulk'`
                            and so labelled an UNCLAIMED code `bulk` while the export lane was
                            correctly refusing to take it — the table and the lane disagreeing
                            about one code, on the screen built to keep them apart. */}
                        {row.lane === 'none' ? '—' : row.lane}
                      </td>
                      <td>{row.display}</td>
                      <td className="codes-num">{row.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {/* ------------------------------------------------------------ duplicates */}
          {ledger.duplicates.length === 0 ? null : (
            <section className="codes-panel is-alarm">
              <h2>{ledger.duplicates.length} duplicate code(s)</h2>
              <p>
                One code was read at two different positions. That is either one card
                photographed twice, or <strong>two cards bearing one code — in which case one
                of them is worth nothing.</strong> Look at both photographs before selling
                either. Nothing here guesses which is which, because a rule would be wrong
                about half the time.
              </p>
              <ul className="codes-unread">
                {ledger.duplicates.map((e) => (
                  <li key={e.code}>
                    <code>{e.code}</code> — box {e.box}/{e.index}
                    {e.duplicate_positions.map((p) => ` and ${p.box}/${p.index}`).join('')}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* ------------------------------------------------------------ export */}
          <section className="codes-panel">
            <h2>Hand codes to a buyer</h2>
            <p className="codes-quiet">
              Confirming reserves every code it returns, permanently. A reserved code is never
              offered again — which is the only thing standing between this pile and selling
              one code twice.
            </p>
            <div className="codes-row">
              <div className="codes-lanes" role="group" aria-label="lane">
                {(['premium', 'bulk'] as Lane[]).map((l) => (
                  <button
                    key={l}
                    type="button"
                    className={lane === l ? 'is-on' : ''}
                    onClick={() => {
                      setLane(l)
                      setPreview(null)
                      setCommitted(null)
                    }}
                  >
                    {l} ({ledger.lanes[l]})
                  </button>
                ))}
              </div>
              <button type="button" onClick={() => void runPreview()} disabled={busy}>
                Preview
              </button>
            </div>

            {preview === null ? null : (
              <div className="codes-result">
                <p>
                  <strong>{preview.available}</strong> code(s) in the {preview.lane} lane.{' '}
                  {preview.note}
                </p>
                {preview.available === 0 ? null : (
                  <div className="codes-row">
                    <label className="codes-field">
                      <span>Order name</span>
                      <input
                        value={orderId}
                        onChange={(e) => setOrderId(e.target.value)}
                        placeholder="wholesale-2026-08-30"
                      />
                    </label>
                    <button
                      type="button"
                      className="codes-commit"
                      onClick={() => void runCommit()}
                      disabled={busy || !orderId.trim()}
                    >
                      Reserve {preview.available} code(s)
                    </button>
                  </div>
                )}
              </div>
            )}

            {committed === null ? null : (
              <div className="codes-result is-done">
                <p>{committed.note}</p>
                <textarea
                  className="codes-codes"
                  readOnly
                  rows={Math.min(12, (committed.codes ?? []).length + 1)}
                  value={(committed.codes ?? []).join('\n')}
                />
                <p className="codes-quiet">
                  Copy these to the buyer. Nothing here sends anything anywhere — there is no
                  channel integration, on purpose: no channel has been executed even once, and
                  building delivery automation against an unproven one is the mistake
                  docs/specs/code-cards.md §6.3 names.
                </p>
              </div>
            )}
          </section>

          {/* ------------------------------------------------------------ the ledger */}
          <section className="codes-panel">
            <h2>The ledger ({ledger.total})</h2>
            <label className="codes-field codes-filter">
              <span>Find</span>
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="a code, a product, a set, an order"
              />
            </label>
            <table className="codes-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>State</th>
                  <th>Product</th>
                  <th>Set</th>
                  <th>Photo</th>
                  <th>Order</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e: CodeEntry) => (
                  <tr key={e.code} className={`is-${e.state}`}>
                    <td>
                      <code className={e.well_formed ? '' : 'is-odd'}>{e.code}</code>
                    </td>
                    <td>{e.state}</td>
                    <td>
                      {e.premium ? <span className="is-premium">premium </span> : null}
                      {e.product_display ?? '—'}
                    </td>
                    <td>{e.set_hint ?? '—'}</td>
                    <td>
                      {e.box === null || e.index === null ? (
                        '—'
                      ) : (
                        <a href={photoUrl(e.box, e.index)} target="_blank" rel="noreferrer">
                          {e.box}/{e.index}
                        </a>
                      )}
                    </td>
                    <td>{e.order_id ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 ? (
              <p className="codes-quiet">
                {ledger.total === 0
                  ? 'No codes yet. Capture code cards with the Game field set to Pokémon code cards, then read the box above.'
                  : 'Nothing matches that.'}
              </p>
            ) : null}
          </section>
        </>
      )}
    </div>
  )
}
