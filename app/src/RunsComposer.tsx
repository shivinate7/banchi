import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import { createPortal } from 'react-dom'

import { cropPreview, describeFailure, photoUrl, preflightRun, startRun, type Failure } from './server'
import type { BoxRecord, CropPreview, RunPreflight, RunStartFailure, RunStartedLeg } from './types'
import { Button, EmptyState, Icon, Kbd, Notice, Pill, Segmented } from './kit'
import { toast } from './kit/toast'
import { LogWell } from './RunsLog'
import { useOverlayFocus } from './runsOverlay'
import { boxLabel } from './runScope'
import { money } from './money'
import { storeKeyText } from './storeKey'
import './Runs.css'

/* THE IDENTIFY COMPOSER — the one press on this product that spends money, as a staged
 * dialog: which boxes, how each is read, what it costs, and a receipt.
 *
 * THE MONEY GATE IS TWO PRESSES AND NO TYPING (D33). `Check cost` runs the free preflight;
 * the confirm cannot be reached without it, and it carries the figure in its own label. The
 * estimate is void the moment the scope moves — a box added, a card ticked, a reading
 * changed — because a confirm whose first step described a different send is not a confirm.
 *
 * ONE PRESS, ONE REQUEST, N RUNS (D48). Each box in the cart is its own run with its own
 * reading, because which end of D32's cost-against-sharpness trade is right depends on what
 * is in the drawer. `Runs.tsx` owns which boxes are in the cart and where a ticked selection
 * came from; this dialog owns how each is read and everything after the press. */

export type CartBox = { box: number; name?: string | null; indices: readonly number[] }

/* D32's measured frontier over box 2, against a full-frame @1568 baseline of $0.72. */
const READINGS = [
  {
    key: 'measured',
    label: 'Measured best',
    crop: true,
    maxEdge: 1200,
    says: 'Crops to the card, sent at 1200px: $0.62 on box 2 and sharpest on the number. Photographs on disk are never touched.',
  },
  {
    key: 'cheapest',
    label: 'Cheapest',
    crop: true,
    maxEdge: 900,
    says: 'The same crop at 900px: $0.44 on box 2, about 13% fewer pixels on the number.',
  },
  {
    key: 'whole',
    label: 'Whole frame',
    crop: false,
    maxEdge: 1568,
    says: 'The whole photograph at 1568px: $0.72 on box 2, the command’s own default.',
  },
] as const

const CUSTOM_SAYS =
  'Crop and max edge are one decision: a crop at an unchanged 1568 cost 26% more when measured, and the rig’s useful range is 900 to 1400.'

type ReadingKey = (typeof READINGS)[number]['key'] | 'custom'

/** How a box is read until somebody says otherwise: D32's measured-best pair. */
const DEFAULT_READING = { crop: true, maxEdge: 1200, custom: false }
type Reading = typeof DEFAULT_READING

type StageKey = 'boxes' | 'read' | 'quote' | 'started'
const ORDER: readonly StageKey[] = ['boxes', 'read', 'quote', 'started']
const STAGE_LIST: readonly { readonly key: StageKey; readonly n: string; readonly label: string }[] = [
  { key: 'boxes', n: '1', label: 'Boxes' },
  { key: 'read', n: '2', label: 'Reading' },
  { key: 'quote', n: '3', label: 'Cost' },
]
const TITLES: Record<StageKey, string> = {
  boxes: 'Which boxes',
  read: 'How they are read',
  quote: 'What it costs',
  started: 'Started',
}

function count(value: number | null | undefined): string {
  return typeof value === 'number' ? String(value) : '—'
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

type Props = {
  readonly open: boolean
  readonly onClose: () => void
  readonly cart: readonly CartBox[]
  readonly boxes: readonly BoxRecord[] | null
  readonly boxesFailure: Failure | null
  readonly picked: ReadonlySet<number>
  readonly onToggleBox: (box: number) => void
  readonly carried: { readonly box: number; readonly indices: readonly number[] } | null
  readonly onDropCarried: () => void
  readonly onStarted: (run: string) => void
}

export function RunsComposer({
  open,
  onClose,
  cart,
  boxes,
  boxesFailure,
  picked,
  onToggleBox,
  carried,
  onDropCarried,
  onStarted,
}: Props) {
  const dialog = useRef<HTMLDivElement | null>(null)
  const [stage, setStage] = useState<StageKey>('boxes')

  /* The reading, per box: sparse, and `DEFAULT_READING` fills the gaps. A box that leaves the
     cart keeps its entry so re-ticking it does not silently reset a reading chosen on purpose. */
  const [readings, setReadings] = useState<Record<number, Reading>>({})
  const [previewBox, setPreviewBox] = useState<number | null>(null)
  const readingFor = useCallback((box: number): Reading => readings[box] ?? DEFAULT_READING, [readings])
  const setReading = useCallback((box: number, patch: Partial<Reading>) => {
    setReadings((held) => ({ ...held, [box]: { ...(held[box] ?? DEFAULT_READING), ...patch } }))
    /* The picture follows the reading that was just touched. */
    setPreviewBox(box)
  }, [])

  /* The preflight's answer — step one of the money gate — and the scope it was quoted for. */
  const [quote, setQuote] = useState<RunPreflight | null>(null)
  const [ticketScope, setTicketScope] = useState('')
  const [showPreflight, setShowPreflight] = useState(false)

  const [busy, setBusy] = useState<'quote' | 'start' | null>(null)
  const [trouble, setTrouble] = useState<Failure | null>(null)
  const [partial, setPartial] = useState<RunStartFailure[] | null>(null)
  const [started, setStarted] = useState<{
    readonly legs: RunStartedLeg[]
    readonly estimate: number | null
    readonly cards: number | null
  } | null>(null)

  /* The crop preview. */
  const [preview, setPreview] = useState<CropPreview | null>(null)
  const [previewFor, setPreviewFor] = useState('')
  const [previewOffset, setPreviewOffset] = useState(0)
  const [previewBusy, setPreviewBusy] = useState(false)
  const [previewTrouble, setPreviewTrouble] = useState<string | null>(null)
  const [aim, setAim] = useState<{ x: number; y: number } | null>(null)
  const detailRef = useRef<HTMLDivElement | null>(null)

  /* WHAT WOULD ACTUALLY BE SENT, box by box, in the shape `server.ts` puts on the wire. One
     derivation feeds the preflight, the confirm and the key below. */
  const legs = useMemo(
    () =>
      cart.map((row) => {
        const reading = readings[row.box] ?? DEFAULT_READING
        return {
          box: row.box,
          indices: row.indices.length > 0 ? [...row.indices] : undefined,
          crop: reading.crop,
          maxEdge: reading.maxEdge,
        }
      }),
    [cart, readings],
  )

  const sharedReading = useMemo(() => {
    if (cart.length === 0) return null
    const first = readings[cart[0]?.box ?? -1] ?? DEFAULT_READING
    const same = cart.every((row) => {
      const held = readings[row.box] ?? DEFAULT_READING
      return held.crop === first.crop && held.maxEdge === first.maxEdge && held.custom === first.custom
    })
    return same ? first : null
  }, [cart, readings])

  /* The whole send as one string — boxes, ticked cards and readings — so an effect can compare it. */
  const scopeKey = useMemo(
    () =>
      legs
        .map(
          (leg) =>
            `${leg.box}:${(leg.indices ?? []).slice().sort((a, b) => a - b).join(',')}` +
            `:${leg.crop ? 'crop' : 'whole'}:${leg.maxEdge}`,
        )
        .join('|'),
    [legs],
  )

  const scoped = cart.length > 0
  const cartName = useCallback((box: number) => cart.find((row) => row.box === box)?.name ?? null, [cart])

  /* THE QUOTE IS VOID THE MOMENT THE SCOPE MOVES. */
  useEffect(() => {
    if (ticketScope !== '' && ticketScope !== scopeKey) {
      setQuote(null)
      setTicketScope('')
    }
  }, [scopeKey, ticketScope])

  /* And the cost stage cannot stand without a quote under it. */
  useEffect(() => {
    if (stage === 'quote' && quote === null && busy !== 'quote') {
      setStage('read')
      toast({
        kind: 'status',
        title: 'Estimate retired',
        body: 'The scope changed. Check the cost again before spending.',
      })
    }
  }, [stage, quote, busy])

  /* Every way out goes through this one wrapper — the X, the scrim, "Watch the run" and
     Escape — so a spent receipt is reset however the dialog was left. */
  const close = useCallback(() => {
    onClose()
    if (stage === 'started') {
      setStage('boxes')
      setStarted(null)
      setPartial(null)
    }
  }, [onClose, stage])

  /* Dialog chrome: focus lands inside on open, stays inside under Tab, and goes back to the
     button that opened it on close. Escape closes. */
  useOverlayFocus(dialog, open, close)

  /* ------------------------------------------------------------------ the crop preview */
  const previewLeg = useMemo(() => legs.find((leg) => leg.box === previewBox) ?? legs[0] ?? null, [legs, previewBox])
  const previewArgs = useMemo(
    () =>
      previewLeg === null
        ? null
        : { box: previewLeg.box, indices: previewLeg.indices, crop: previewLeg.crop, maxEdge: previewLeg.maxEdge },
    [previewLeg],
  )
  const previewKey =
    previewArgs === null
      ? ''
      : `${previewArgs.box}:${(previewArgs.indices ?? []).join(',')}:${previewArgs.crop ? 'crop' : 'whole'}:${previewArgs.maxEdge}`
  const showing = open && stage === 'read'

  /* Debounced at 140ms: under a key repeat, over a human tap. The previous card stays up,
     dimmed, while the next is fetched. */
  useEffect(() => {
    if (!showing || !scoped || previewArgs === null) {
      setPreview(null)
      setPreviewFor('')
      return
    }
    const want = `${previewKey}:${previewOffset}`
    if (previewFor === want) return
    let live = true
    const timer = setTimeout(() => {
      setPreviewBusy(true)
      void (async () => {
        try {
          const answer = await cropPreview({ ...previewArgs, offset: previewOffset })
          if (!live) return
          setPreview(answer)
          setPreviewTrouble(null)
        } catch (err) {
          if (!live) return
          setPreview(null)
          setPreviewTrouble(describeFailure(err).message)
        } finally {
          if (live) {
            setPreviewFor(want)
            setPreviewBusy(false)
          }
        }
      })()
    }, 140)
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [showing, scoped, previewKey, previewOffset, previewFor, previewArgs])

  useEffect(() => {
    setAim(null)
  }, [previewFor])

  /* A new box starts at the front of its own walk — keyed on the resolved box, not the state. */
  useEffect(() => {
    setPreviewOffset(0)
  }, [previewLeg?.box])

  const stepPreview = useCallback(
    (by: number) =>
      setPreviewOffset((was) => {
        const total = preview?.total ?? 0
        return total > 0 ? (was + by + total) % total : Math.max(0, was + by)
      }),
    [preview],
  )

  /* Arrow keys walk the box while the preview is on screen — guarded on the target so a
     number input keeps its caret keys, and modifier chords are left to the shell. */
  useEffect(() => {
    if (!showing || !scoped) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target as HTMLElement | null
      const tag = target?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target?.isContentEditable) return
      event.preventDefault()
      stepPreview(event.key === 'ArrowRight' ? 1 : -1)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [showing, scoped, stepPreview])

  /* The 1:1 window's position in the sent image's own pixels, clamped into the image. */
  const detailPosition = useMemo(() => {
    const sample = preview?.sample
    if (sample?.sent == null) return undefined
    const [sentW, sentH] = sample.sent
    const node = detailRef.current
    const viewW = node?.offsetWidth ?? 300
    const viewH = node?.offsetHeight ?? 140
    let x: number
    let y: number
    if (aim !== null) {
      x = aim.x
      y = aim.y
    } else if (sample.band_rect != null) {
      x = sample.band_rect[0]
      y = sample.band_rect[1] + (sample.band_rect[3] - sample.band_rect[1] - viewH) / 2
    } else {
      x = (sentW - viewW) / 2
      y = (sentH - viewH) / 2
    }
    x = Math.max(0, Math.min(x, Math.max(0, sentW - viewW)))
    y = Math.max(0, Math.min(y, Math.max(0, sentH - viewH)))
    return `${-Math.round(x)}px ${-Math.round(y)}px`
  }, [preview, aim])

  const aimAt = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      const sample = preview?.sample
      if (sample?.frame == null || sample.sent == null) return
      const node = detailRef.current
      const box = event.currentTarget.getBoundingClientRect()
      if (box.width === 0 || box.height === 0) return
      const [frameW, frameH] = sample.frame
      const cut = sample.rect ?? [0, 0, frameW, frameH]
      const originalX = ((event.clientX - box.left) / box.width) * frameW
      const originalY = ((event.clientY - box.top) / box.height) * frameH
      const sentX = ((originalX - cut[0]) / (cut[2] - cut[0])) * sample.sent[0]
      const sentY = ((originalY - cut[1]) / (cut[3] - cut[1])) * sample.sent[1]
      setAim({ x: sentX - (node?.offsetWidth ?? 300) / 2, y: sentY - (node?.offsetHeight ?? 140) / 2 })
    },
    [preview],
  )

  /* ------------------------------------------------------------------- the two presses */
  const guard = useCallback(async (key: 'quote' | 'start', work: () => Promise<void>) => {
    setBusy(key)
    setTrouble(null)
    try {
      await work()
    } catch (err) {
      setTrouble(describeFailure(err))
    } finally {
      setBusy(null)
    }
  }, [])

  const doQuote = () =>
    guard('quote', async () => {
      const answer = await preflightRun(legs)
      setQuote(answer)
      setTicketScope(scopeKey)
      setShowPreflight(false)
      setStage('quote')
    })

  const doStart = () =>
    guard('start', async () => {
      const answer = await startRun(legs)
      setStarted({
        legs: answer.started,
        estimate: quote?.total.estimate_usd ?? null,
        cards: quote?.total.to_send ?? null,
      })
      /* The quote is spent: identifying more needs a fresh preflight. */
      setQuote(null)
      setTicketScope('')
      setPartial(answer.failed.length > 0 ? answer.failed : null)
      setStage('started')
      const first = answer.started[0]
      if (first !== undefined) {
        onStarted(first.run)
        toast({
          kind: 'ok',
          title: `Started · ${boxLabel(first.scope.box, cartName(first.scope.box))}`,
          body: `${money(quote?.total.estimate_usd)} · ${plural(quote?.total.to_send ?? 0, 'card')}${
            answer.started.length > 1 ? ` · ${plural(answer.started.length, 'run')}` : ''
          }`,
        })
      }
    })

  /* ---------------------------------------------------------------------------- render */
  const rows = useMemo(() => (boxes === null ? [] : [...boxes].sort((a, b) => a.box - b.box)), [boxes])
  const cardsPicked = useMemo(
    () =>
      cart.reduce(
        (sum, row) =>
          sum + (row.indices.length > 0 ? row.indices.length : (boxes?.find((b) => b.box === row.box)?.cards ?? 0)),
        0,
      ),
    [cart, boxes],
  )
  const only = cart.length === 1 ? cart[0] : undefined
  const scopeLine =
    only !== undefined
      ? `${boxLabel(only.box, only.name)} · ${
          only.indices.length > 0 ? `${plural(only.indices.length, 'ticked card')}` : 'the whole box'
        }`
      : cart.length === 0
        ? 'Pick a box. You can pick several.'
        : `${plural(cart.length, 'box').replace('boxs', 'boxes')} · ${plural(cardsPicked, 'card')}`

  const stageState = (key: StageKey): 'done' | 'current' | 'todo' =>
    stage === 'started' ? 'done' : ORDER.indexOf(key) < ORDER.indexOf(stage) ? 'done' : key === stage ? 'current' : 'todo'

  if (!open) return null

  const readingOptions = [
    ...READINGS.map((option) => ({
      value: option.key as ReadingKey,
      label: (
        <>
          <span>{option.label}</span>
          <span className="run-reading-edge">{option.maxEdge}</span>
        </>
      ),
    })),
    { value: 'custom' as ReadingKey, label: 'Custom' },
  ]

  /* Portalled to <body>: `.bn-page`'s enter animation leaves `main` with a filled transform,
     which makes it the containing block for anything fixed inside it — a dialog drawn there
     centres on the page column rather than the viewport and the scrim never reaches the nav. */
  return createPortal(
    <>
      <div className="bn-scrim" onClick={close} />
      <div
        ref={dialog}
        className="bn-dialog runs-composer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="runs-composer-title"
        tabIndex={-1}
      >
        <header className="runs-composer-head">
          <div className="runs-composer-heading">
            <span className="bn-eyebrow">Identify · costs money</span>
            <h2 className="runs-composer-title" id="runs-composer-title">
              {TITLES[stage]}
            </h2>
          </div>
          <ol className="runs-stages" aria-label="Stages">
            {STAGE_LIST.map((row) => {
              const state = stageState(row.key)
              const canGo = state === 'done' && stage !== 'started'
              return (
                <li key={row.key}>
                  {canGo ? (
                    <button type="button" className="runs-stage" data-state={state} onClick={() => setStage(row.key)}>
                      <span className="runs-stage-n">
                        <Icon name="check" size={11} />
                      </span>
                      <span className="runs-stage-label">{row.label}</span>
                    </button>
                  ) : (
                    <span className="runs-stage" data-state={state} aria-current={state === 'current' ? 'step' : undefined}>
                      <span className="runs-stage-n">{state === 'done' ? <Icon name="check" size={11} /> : row.n}</span>
                      <span className="runs-stage-label">{row.label}</span>
                    </span>
                  )}
                </li>
              )
            })}
          </ol>
          <Button variant="ghost" icon="x" iconOnly onClick={close}>
            Close
          </Button>
        </header>

        <div className="runs-composer-body">
          {trouble === null ? null : (
            <Notice tone="danger" code={trouble.code}>
              {trouble.message}
            </Notice>
          )}

          {/* ----------------------------------------------------------- 1 · which boxes */}
          {stage === 'boxes' ? (
            <div className="runs-composer-stage" key="boxes">
              {boxesFailure === null ? null : (
                <Notice tone="danger" code={boxesFailure.code}>
                  {boxesFailure.message}
                </Notice>
              )}
              {carried === null ? null : (
                <Notice tone="info" title={`${plural(carried.indices.length, 'card')} ticked in Box ${carried.box}`}>
                  <div className="runs-handoff">
                    <span>Only those cards are sent for that box.</span>
                    <Button size="sm" variant="quiet" onClick={onDropCarried}>
                      Identify all of box {carried.box} instead
                    </Button>
                  </div>
                </Notice>
              )}
              <div className="runs-boxes" role="group" aria-label="Which boxes to run">
                {boxes === null && boxesFailure === null ? (
                  Array.from({ length: 6 }, (_, i) => <div key={i} className="bn-skeleton runs-box-skel" />)
                ) : rows.length === 0 ? (
                  <EmptyState
                    icon="box"
                    title="No boxes yet"
                    body="Shoot one on the capture screen and it will be here to run."
                    actions={
                      <Button
                        icon="camera"
                        onClick={() => {
                          window.location.hash = '#/capture'
                        }}
                      >
                        Go to capture
                      </Button>
                    }
                  />
                ) : (
                  rows.map((record, i) => {
                    const on = picked.has(record.box)
                    const ticked = on && carried !== null && carried.box === record.box ? carried.indices.length : 0
                    return (
                      <button
                        key={record.box}
                        type="button"
                        className="runs-box"
                        aria-pressed={on}
                        onClick={() => onToggleBox(record.box)}
                        style={{ animationDelay: `${Math.min(i, 12) * 30}ms` }}
                      >
                        <span className="runs-box-num" aria-hidden="true">
                          {record.box}
                        </span>
                        <span className="runs-box-text">
                          <span className="runs-box-name" title={boxLabel(record.box, record.name)}>
                            {boxLabel(record.box, record.name)}
                          </span>
                          <span className="runs-box-cards">
                            {plural(record.cards, 'card')}
                            {ticked > 0 ? ` · ${ticked} ticked` : ''}
                          </span>
                        </span>
                        <span className="runs-box-check" aria-hidden="true">
                          <Icon name="check" size={12} />
                        </span>
                      </button>
                    )
                  })
                )}
              </div>
            </div>
          ) : null}

          {/* --------------------------------------------------------- 2 · the reading */}
          {stage === 'read' ? (
            <div className="runs-composer-stage runs-composer-read" key="read">
              <div className="runs-legs">
                {cart.map((row) => {
                  const held = readingFor(row.box)
                  const match = READINGS.find((r) => r.crop === held.crop && r.maxEdge === held.maxEdge) ?? null
                  const value: ReadingKey = held.custom ? 'custom' : (match?.key ?? 'custom')
                  return (
                    <div className="run-leg" key={row.box}>
                      <div className="run-leg-head">
                        <span className="run-leg-box">{boxLabel(row.box, row.name)}</span>
                        <span className="run-leg-scope">
                          {row.indices.length > 0 ? plural(row.indices.length, 'ticked card') : 'the whole box'}
                        </span>
                        {cart.length > 1 && previewLeg?.box === row.box ? (
                          <Pill tone="accent" icon="eye">
                            Previewing
                          </Pill>
                        ) : null}
                      </div>
                      <Segmented<ReadingKey>
                        className="run-readings"
                        label={`How box ${row.box} is read`}
                        value={value}
                        options={readingOptions}
                        onChange={(next) => {
                          if (next === 'custom') {
                            setReading(row.box, { custom: true })
                            return
                          }
                          const option = READINGS.find((r) => r.key === next)
                          if (option !== undefined) {
                            setReading(row.box, { custom: false, crop: option.crop, maxEdge: option.maxEdge })
                          }
                        }}
                      />
                      {held.custom ? (
                        <div className="run-controls">
                          <label className="bn-check">
                            <input
                              type="checkbox"
                              checked={held.crop}
                              onChange={(event) => setReading(row.box, { crop: event.target.checked })}
                            />
                            Crop to the card
                          </label>
                          <label className="runs-field-inline">
                            <span>Max edge</span>
                            <input
                              className="bn-input bn-input-mono runs-edge"
                              type="number"
                              min={256}
                              max={4096}
                              step={100}
                              value={held.maxEdge}
                              onChange={(event) => setReading(row.box, { maxEdge: Number(event.target.value) })}
                            />
                            <span className="bn-muted">px</span>
                          </label>
                        </div>
                      ) : null}
                      {sharedReading !== null ? null : (
                        <p className="run-step-fine">{held.custom || match === null ? CUSTOM_SAYS : match.says}</p>
                      )}
                    </div>
                  )
                })}
                {sharedReading === null ? null : (
                  <p className="run-step-fine runs-reading-says">
                    {sharedReading.custom
                      ? CUSTOM_SAYS
                      : (READINGS.find((r) => r.crop === sharedReading.crop && r.maxEdge === sharedReading.maxEdge)
                          ?.says ?? CUSTOM_SAYS)}
                  </p>
                )}
              </div>

              <aside className="run-preview" aria-label="What this reading sends">
                <div className="run-preview-head">
                  <span className="bn-label">What this reading sends</span>
                  {preview === null ? null : (
                    /* The walk lives up here, above the frame, so it is on screen at every
                       viewport height — the arrow keys are only discoverable from it. */
                    <span className="run-preview-walk" role="group" aria-label="Walk the box">
                      <Button size="sm" iconOnly icon="chevronLeft" onClick={() => setPreviewOffset((was) => was - 1)}>
                        The card before this one
                      </Button>
                      <span className="run-preview-count">
                        card {preview.offset + 1} of {count(preview.total)}
                      </span>
                      <Button size="sm" iconOnly icon="chevronRight" onClick={() => setPreviewOffset((was) => was + 1)}>
                        The card after this one
                      </Button>
                    </span>
                  )}
                </div>
                {previewTrouble !== null ? (
                  <Notice tone="warn">{previewTrouble}</Notice>
                ) : preview === null ? (
                  <div className="bn-skeleton runs-preview-skel" aria-busy="true" />
                ) : preview.sample.unreadable !== undefined || preview.sample.frame === undefined ? (
                  <p className="run-preview-fact">
                    {/* THE STORE KEY AND NOT A CARD NUMBER, on all four of this panel's figures.
                        `/pipeline/runs/<name>/crop` sends `{box, index}` and no slot, because what
                        it is describing is a PHOTOGRAPH — the same `(box, index)` `photoUrl` names
                        it by (D52) — and D58's countable number moves under that key every time a
                        card in front of this one leaves the box. Drawn as `Card 17` this panel
                        would name a different card than the one a hand counting into the drawer
                        reaches, so it draws what it actually has. */}
                    <span className="run-preview-slot">{storeKeyText(preview.sample.box, preview.sample.index)}</span>
                    <span>this photograph cannot be decoded, so nothing is sent for it.</span>
                  </p>
                ) : (
                  <div className="run-preview-card" aria-busy={previewBusy}>
                    <div className="run-preview-frame" onPointerMove={aimAt} onPointerLeave={() => setAim(null)}>
                      <img
                        className="run-preview-ghost"
                        /* THE SLOT ROUTE, BECAUSE THE PREVIEW HAS NO NAME TO OFFER (D172).
                           `POST /pipeline/runs/<name>/crop` answers with `{box, index}` and
                           nothing else — it describes a PHOTOGRAPH the detector just read off
                           disk, not a store record — so there is no `cid` on this payload to
                           address it by. */
                        src={photoUrl(preview.sample.box, preview.sample.index)}
                        alt=""
                        aria-hidden="true"
                        draggable={false}
                      />
                      {preview.sample.sent_image != null && (
                        <img
                          className="run-preview-sent"
                          src={preview.sample.sent_image}
                          alt={`${storeKeyText(preview.sample.box, preview.sample.index)}, as this reading sends it`}
                          draggable={false}
                          style={
                            preview.sample.rect != null && preview.sample.frame != null
                              ? {
                                  left: `${(preview.sample.rect[0] / preview.sample.frame[0]) * 100}%`,
                                  top: `${(preview.sample.rect[1] / preview.sample.frame[1]) * 100}%`,
                                  width: `${((preview.sample.rect[2] - preview.sample.rect[0]) / preview.sample.frame[0]) * 100}%`,
                                  height: `${((preview.sample.rect[3] - preview.sample.rect[1]) / preview.sample.frame[1]) * 100}%`,
                                }
                              : { left: 0, top: 0, width: '100%', height: '100%' }
                          }
                        />
                      )}
                      {preview.sample.rect != null && preview.sample.frame != null && (
                        <div
                          className="run-preview-cut"
                          style={{
                            left: `${(preview.sample.rect[0] / preview.sample.frame[0]) * 100}%`,
                            top: `${(preview.sample.rect[1] / preview.sample.frame[1]) * 100}%`,
                            width: `${((preview.sample.rect[2] - preview.sample.rect[0]) / preview.sample.frame[0]) * 100}%`,
                            height: `${((preview.sample.rect[3] - preview.sample.rect[1]) / preview.sample.frame[1]) * 100}%`,
                          }}
                        />
                      )}
                    </div>

                    <div
                      ref={detailRef}
                      className="run-preview-detail"
                      style={{
                        backgroundImage:
                          preview.sample.sent_image != null ? `url(${preview.sample.sent_image})` : undefined,
                        backgroundPosition: detailPosition,
                      }}
                      role="img"
                      aria-label={`${storeKeyText(preview.sample.box, preview.sample.index)} at full size, as this reading sends it`}
                    />
                    <p className="run-preview-fact">
                      <span>{aim === null ? 'Resting on the collector number' : 'Where you are pointing'} · 1:1</span>
                      {preview.sample.band_px != null && (
                        <span>
                          the number is {preview.sample.band_px[0]}×{preview.sample.band_px[1]} px as sent
                        </span>
                      )}
                    </p>
                    {preview.sample.band_absent != null && (
                      /* The server's own sentence names a module and a file; the fact it carries
                         is this one. */
                      <p className="run-step-fine">
                        No number band on this game&rsquo;s cards — point at the card above to read any part of it.
                      </p>
                    )}

                    <p className="run-preview-fact">
                      <span className="run-preview-slot">{storeKeyText(preview.sample.box, preview.sample.index)}</span>
                      {preview.sample.sent != null && (
                        <span>
                          sent at {preview.sample.sent[0]}×{preview.sample.sent[1]}, shown smaller here
                        </span>
                      )}
                      {preview.sample.method == null && <span>no card found, so the whole photograph goes</span>}
                      {preview.sample.crop_refused != null && (
                        <span>card found but the crop was refused, so the whole photograph goes</span>
                      )}
                    </p>
                    {preview.sample.crop_refused != null && (
                      <p className="run-step-fine">{preview.sample.crop_refused}</p>
                    )}

                    <p className="run-preview-hint">
                      <Kbd>←</Kbd>
                      <Kbd>→</Kbd> walk the box
                    </p>
                  </div>
                )}
              </aside>
            </div>
          ) : null}

          {/* ------------------------------------------------------ 3 · the money moment */}
          {stage === 'quote' && quote !== null ? (
            <div className="runs-composer-stage runs-quote run-quote" key="quote">
              <div className="runs-quote-figure">
                <span className="bn-label">Estimated cost</span>
                <span className="runs-quote-money">{money(quote.total.estimate_usd)}</span>
                <span className="runs-quote-line">
                  <strong>{plural(quote.total.to_send ?? 0, 'card')}</strong> to send ·{' '}
                  {count(quote.total.cache_hits)} already answered · {count(quote.total.photographs)} photographs
                  {quote.scopes.length > 1 ? ` · ${quote.scopes.length} boxes` : ''}
                </span>
              </div>

              {quote.scopes.length < 2 ? null : (
                <dl className="run-legs">
                  {quote.scopes.map((leg) => (
                    <div key={leg.scope.box}>
                      <dt>{boxLabel(leg.scope.box, cartName(leg.scope.box))}</dt>
                      <dd>
                        {count(leg.to_send)} to send · {money(leg.estimate_usd)}
                        {leg.scope.whole_box ? '' : ` · ${count(leg.scope.cards)} ticked`}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}

              {partial === null ? null : (
                <Notice tone="danger" title={`${plural(partial.length, 'box').replace('boxs', 'boxes')} did not start`}>
                  The rest started. Press again for {partial.length === 1 ? 'it' : 'them'}.
                  {partial.map((row) => (
                    <div className="bn-notice-code" key={row.box}>
                      box {row.box} · {row.code} · {row.message}
                    </div>
                  ))}
                </Notice>
              )}

              {quote.total.busy.length > 0 ? (
                <Notice tone="warn" title="Already running">
                  {quote.total.busy
                    .map((row) => `Box ${row.box} is already being identified by ${row.run}`)
                    .join('. ')}
                  . Watch that run instead; nothing here starts while it is running.
                </Notice>
              ) : quote.total.to_send === 0 ? (
                <Notice tone="ok" title="Nothing to send">
                  Every one of these cards is already answered and cached. There is nothing to spend.
                </Notice>
              ) : (
                <div className="runs-quote-confirm">
                  <Button
                    variant="primary"
                    size="xl"
                    icon="zap"
                    className="run-button-money"
                    busy={busy === 'start'}
                    disabled={busy !== null}
                    onClick={() => void doStart()}
                  >
                    {`Spend ${money(quote.total.estimate_usd)} and identify ${count(quote.total.to_send)} cards` +
                      (quote.scopes.length > 1 ? ` in ${quote.scopes.length} boxes` : '')}
                  </Button>
                  <span className="runs-quote-fine">
                    One run per box. Identification takes minutes to hours and keeps going if you close this tab.
                  </span>
                </div>
              )}

              {(quote.total.cache_hits ?? 0) > 0 && (
                <p className="run-step-fine runs-quote-cache">
                  Cards already answered keep the answer they were first read with. The reading above only
                  reaches the cards being sent.
                </p>
              )}

              <div className="runs-quote-consoles">
                <button
                  type="button"
                  className="runs-disclose"
                  aria-expanded={showPreflight}
                  onClick={() => setShowPreflight((v) => !v)}
                >
                  <Icon name="chevronDown" size={14} />
                  What the preflight printed
                </button>
                {showPreflight
                  ? quote.scopes.map((leg) => (
                      <LogWell
                        key={leg.scope.box}
                        text={leg.console}
                        label={`Preflight · ${boxLabel(leg.scope.box, cartName(leg.scope.box))}`}
                        maxHeight={220}
                      />
                    ))
                  : null}
              </div>
            </div>
          ) : null}

          {/* --------------------------------------------------------------- 4 · receipt */}
          {stage === 'started' && started !== null ? (
            <div className="runs-composer-stage runs-receipt" key="started">
              <span className="runs-receipt-art">
                <Icon name="check" size={28} strokeWidth={2.25} />
              </span>
              <h3 className="runs-receipt-title">
                {started.legs.length === 1 ? 'The run has started' : `${started.legs.length} runs have started`}
              </h3>
              <p className="runs-receipt-line">
                <strong>{money(started.estimate)}</strong> · {plural(started.cards ?? 0, 'card')} sent to be read
              </p>
              <ul className="runs-receipt-runs">
                {started.legs.map((leg) => (
                  <li key={leg.run}>
                    <span className="runs-receipt-box">{boxLabel(leg.scope.box, cartName(leg.scope.box))}</span>
                    <span className="bn-mono runs-receipt-run">{leg.run}</span>
                  </li>
                ))}
              </ul>
              {partial === null ? null : (
                <Notice tone="danger" title={`${plural(partial.length, 'box').replace('boxs', 'boxes')} did not start`}>
                  The rest started. Check the cost again to start {partial.length === 1 ? 'it' : 'them'}.
                  {partial.map((row) => (
                    <div className="bn-notice-code" key={row.box}>
                      box {row.box} · {row.code} · {row.message}
                    </div>
                  ))}
                </Notice>
              )}
              <p className="run-step-fine runs-receipt-fine">
                Identification takes minutes to hours and keeps running if you close this tab. The run is open
                beside the list and re-reads itself while it is live.
              </p>
            </div>
          ) : null}
        </div>

        <footer className="runs-composer-foot">
          {stage === 'boxes' ? (
            <>
              <span className="runs-composer-note">{scopeLine}</span>
              <Button variant="ghost" onClick={close}>
                Cancel
              </Button>
              <Button variant="primary" iconRight="arrowRight" disabled={!scoped} onClick={() => setStage('read')}>
                Next · how they are read
              </Button>
            </>
          ) : null}
          {stage === 'read' ? (
            <>
              <Button variant="ghost" icon="arrowLeft" onClick={() => setStage('boxes')}>
                Boxes
              </Button>
              <span className="runs-composer-note">{scopeLine}</span>
              <Button
                variant="primary"
                icon="dollar"
                busy={busy === 'quote'}
                disabled={!scoped || busy !== null}
                onClick={() => void doQuote()}
              >
                {cart.length > 1 ? `Check cost for ${cart.length} boxes` : 'Check cost'}
              </Button>
            </>
          ) : null}
          {stage === 'quote' ? (
            <>
              <Button variant="ghost" icon="arrowLeft" onClick={() => setStage('read')}>
                Reading
              </Button>
              <span className="runs-composer-note">{scopeLine} · quoted for exactly these boxes</span>
              <Button variant="ghost" onClick={close}>
                Not now
              </Button>
            </>
          ) : null}
          {stage === 'started' ? (
            <>
              <span className="runs-composer-note">
                The quote is spent; check the cost again before identifying more.
              </span>
              <Button variant="primary" icon="eye" onClick={close}>
                Watch the run
              </Button>
            </>
          ) : null}
        </footer>
      </div>
    </>,
    document.body,
  )
}
