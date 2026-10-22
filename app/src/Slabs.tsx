import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { Button, Count, EmptyState, FailureNotice, Icon, Money, Page, ReloadButton, Section, Select, Sheet, Skeleton, SkeletonText } from './kit'
import { toast } from './kit/toast'
import { dayDate } from './dates'
import { count } from './kit/dataRules'
import { addSlab, describeFailure, failureTone, getSlabDetail, getSlabs, removeSlab, type Failure } from './server'
import { SLAB_GRADERS } from './slabGraders'
import type { SlabDetail, SlabReceipt, SlabRow, SlabSnapshot } from './types'
import './Slabs.css'

/* SLABS (D320, `docs/specs/my-slabs.md` 4.1, 4.7, 4.8, 4.9).
 *
 * One ledger of the owner's graded slabs, read from the four slab routes and no others. The
 * browser computes no trust verdict: it shows Card Ladder's estimate and the grade-ladder value, each
 * with its source. A cert is never drawn, and the settings key is never named. A column no route
 * fills holds a typed dash, so all 18 headers show (4.1). */

const GRADER_NAME: Record<string, string> = { psa: 'PSA', beckett: 'Beckett', bgs: 'BGS', bvg: 'BVG', sgc: 'SGC', cgc: 'CGC' }
const CONF_WORD: Record<number, string> = { 1: 'Very low', 2: 'Low', 3: 'Fair', 4: 'Good', 5: 'High' }
const NO_NAME = 'Unnamed slab'
const DASH = '—'

/** Sales windows in the order Card Ladder's speed block lists them, with the words for each. */
const WINDOWS: ReadonlyArray<readonly [string, string]> = [
  ['twoWeekData', 'Two weeks'],
  ['oneMonthData', 'One month'],
  ['oneQuarterData', 'Three months'],
  ['sixMonthData', 'Six months'],
  ['oneYearData', 'One year'],
]

type Column = { readonly name: string; readonly width: number; readonly num?: boolean }
/* The owner's order (4.1). Widths are fixed, so a column keeps its width empty or full (D313). */
const COLUMNS: readonly Column[] = [
  { name: 'Pop', width: 48, num: true },
  { name: 'Graded', width: 56, num: true },
  { name: 'Rate', width: 44, num: true },
  { name: 'Top %', width: 58, num: true },
  { name: 'Best %', width: 58, num: true },
  { name: 'Grade', width: 80 },
  { name: 'Set', width: 40 },
  { name: 'Card', width: 172 },
  { name: 'Var', width: 40 },
  { name: 'Ask', width: 48, num: true },
  { name: 'Card Ladder', width: 96, num: true },
  { name: 'Conf', width: 68 },
  { name: 'Last sale', width: 80, num: true },
  { name: 'PSA 10', width: 60, num: true },
  { name: 'Raw NM', width: 64, num: true },
  { name: 'Slab vs raw', width: 64, num: true },
  { name: '×', width: 32, num: true },
  { name: 'Do', width: 36 },
]
const TABLE_MIN = COLUMNS.reduce((sum, column) => sum + column.width, 0)
/* The cells no route fills yet. Rate, Top % and Best % need the pop report, which the routes do not store. */
const DASH_COLUMNS: ReadonlySet<string> = new Set(['Graded', 'Rate', 'Top %', 'Best %', 'Set', 'Var', 'Ask', 'PSA 10', 'Raw NM', 'Slab vs raw', '×', 'Do'])

/* ----------------------------------------------------------------------------- words */

const rowKey = (row: Pick<SlabRow, 'grader' | 'cert'>): string => `${row.grader}/${row.cert}`
const nameOf = (row: Pick<SlabRow, 'label'>): string => (row.label ?? '').trim() === '' ? NO_NAME : (row.label as string)

/** Card Ladder's money text as a number; null where it gave none. */
function amount(text: string | null | undefined): number | null {
  if (text === null || text === undefined) return null
  const value = Number(text)
  return Number.isFinite(value) ? value : null
}

/** `g10` is 10, `g9_5` is 9.5. */
function gradeNumber(grade: string | null): string | null {
  if (grade === null) return null
  const found = /^g(\d+)(?:_(\d+))?$/.exec(grade)
  if (found === null) return grade.replace(/_/g, ' ')
  return found[2] === undefined ? found[1] ?? grade : `${found[1]}.${found[2]}`
}

function gradeText(row: Pick<SlabRow, 'grader' | 'grade'>): string | null {
  const grade = gradeNumber(row.grade)
  return grade === null ? null : `${GRADER_NAME[row.grader] ?? row.grader.toUpperCase()} ${grade}`
}

const dash = (): ReactNode => <span className="slabs-dash">{DASH}</span>

function Conf({ value }: { readonly value: number | null }) {
  if (value === null) return dash()
  return (
    <span className="slabs-conf" data-low={value <= 2 ? 'true' : undefined}>
      {CONF_WORD[value] ?? DASH}
    </span>
  )
}

/** Highest Card Ladder value first. A slab that never sold, or has no read yet, comes last. The sort on × comes
 *  first in the spec and no row has one in this build, so it falls through to this (4.1). */
function sorted(rows: readonly SlabRow[]): SlabRow[] {
  const value = (row: SlabRow): number | null => (row.note === 'no sales' ? null : amount(row.snapshot?.estimated_value))
  return rows
    .map((row, at) => ({ row, at, value: value(row) }))
    .sort((a, b) => (a.value === null ? 1 : 0) - (b.value === null ? 1 : 0) || (b.value ?? 0) - (a.value ?? 0) || a.at - b.at)
    .map((one) => one.row)
}

/* ----------------------------------------------------------------------------- refusals */

const LOGIN_SENTENCE = 'Card Ladder needs you to sign in again.'
const SAID: Readonly<Record<string, string>> = {
  cardladder_rate_limited: 'Card Ladder asked us to slow down. Nothing was saved. Try again tomorrow.',
  cardladder_token_missing: LOGIN_SENTENCE,
  cardladder_token_rejected: LOGIN_SENTENCE,
  cert_not_found: 'Card Ladder has no slab with that cert number for that grader.',
  cert_required: 'Type a cert number first.',
  grader_unknown: 'Pick a grader from the list.',
  slab_add_busy: 'Another slab is being added. Wait for it to finish.',
  slab_unknown: 'That slab is not in the list.',
}

/** The sentence a refusal gets on screen: the screen's own for the codes it words, else the refusal's own message (the
 *  server's, or the client's from `describeFailure`). The login codes also lose the server's text, which names the settings key. */
function said(failure: Failure, fallback: string): { title: string; failure: Failure } {
  const own = SAID[failure.code]
  return { title: own ?? (failure.message === '' ? fallback : failure.message), failure: own !== undefined && failure.code.startsWith('cardladder_token') ? { ...failure, message: own } : failure }
}

function Refused({ failure, fallback, onRetry, busy, compact }: { readonly failure: Failure; readonly fallback: string; readonly onRetry?: () => void; readonly busy?: boolean; readonly compact?: boolean }) {
  const one = said(failure, fallback)
  return <FailureNotice failure={one.failure} title={one.title} onRetry={onRetry} busy={busy} compact={compact} />
}

/** A receipt sentence that never carries a cert: a slab with no label comes back from the route as "slab <cert>". */
function receiptSentence(message: string, cert: string, verb: string): string {
  return message.includes(cert) ? `${verb} a slab with no name.` : message
}

function addVerb(receipt: SlabReceipt): string {
  return receipt.added ? 'Added' : receipt.restored ? 'Restored' : 'Updated'
}

/* ----------------------------------------------------------------------------- the screen */

export default function Slabs() {
  const [rows, setRows] = useState<SlabRow[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [reloading, setReloading] = useState(false)
  const read = useRef(0)

  const load = useCallback(async () => {
    const mine = ++read.current
    setReloading(true)
    try {
      const list = await getSlabs()
      if (mine !== read.current) return
      setRows(list.slabs)
      setFailure(null)
    } catch (err) {
      if (mine !== read.current) return
      setFailure(describeFailure(err))
    } finally {
      if (mine === read.current) setReloading(false)
    }
  }, [])
  useEffect(() => {
    void load()
  }, [load])

  const ordered = useMemo(() => (rows === null ? [] : sorted(rows)), [rows])
  const [detail, setDetail] = useState<SlabRow | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  /* ---- add. One request at a time, from the sheet or from an Undo. */
  const [addOpen, setAddOpen] = useState(false)
  const addOpenNow = useRef(false)
  const [cert, setCert] = useState('')
  const [grader, setGrader] = useState<string>(SLAB_GRADERS[0])
  const [adding, setAdding] = useState(false)
  const [addFailure, setAddFailure] = useState<Failure | null>(null)
  const addBusy = useRef(false)

  const openAdd = () => {
    setCert('')
    setAddFailure(null)
    addOpenNow.current = true
    setAddOpen(true)
  }
  const closeAdd = () => {
    addOpenNow.current = false
    setAddOpen(false)
  }

  /** Reads one slab and files it. `fromSheet` is true for the Add sheet, which shows a refusal in place while it is open. */
  const add = async (input: { cert: string; grader: string }, fromSheet: boolean): Promise<void> => {
    if (addBusy.current) return
    addBusy.current = true
    setAdding(true)
    if (fromSheet) setAddFailure(null)
    try {
      const receipt = await addSlab(input)
      toast({ kind: 'receipt', title: receiptSentence(receipt.message, receipt.cert, addVerb(receipt)) })
      if (fromSheet) {
        setCert('')
        closeAdd()
      }
      await load()
    } catch (err) {
      const f = describeFailure(err)
      if (fromSheet && addOpenNow.current) setAddFailure(f)
      else toast({ kind: 'refusal', tone: failureTone(f), title: said(f, 'That slab could not be added.').title })
    } finally {
      addBusy.current = false
      setAdding(false)
    }
  }

  /* ---- remove. Acts at once; the receipt carries Undo. */
  const [removing, setRemoving] = useState(false)
  const [removeFailure, setRemoveFailure] = useState<Failure | null>(null)
  const removeBusy = useRef(false)

  /* Where focus goes once the removed row has left the list: the next row's Card button, else the add button. */
  const [handover, setHandover] = useState<{ readonly gone: string; readonly next: string | null } | null>(null)
  useEffect(() => {
    if (handover === null || rows === null || rows.some((one) => rowKey(one) === handover.gone)) return
    setHandover(null)
    const active = document.activeElement
    if (active !== null && active !== document.body && active.isConnected) return
    const target = [...document.querySelectorAll<HTMLElement>('[data-slab]')].find((el) => el.dataset.slab === handover.next) ?? document.querySelector<HTMLElement>('[data-slabs-add]')
    target?.focus()
  }, [rows, handover])

  const remove = async (row: SlabRow): Promise<void> => {
    if (removeBusy.current || addBusy.current) return
    removeBusy.current = true
    setRemoving(true)
    setRemoveFailure(null)
    try {
      const gone = await removeSlab(row.grader, row.cert)
      const at = ordered.findIndex((one) => rowKey(one) === rowKey(row))
      const next = ordered[at + 1] ?? ordered[at - 1]
      setHandover({ gone: rowKey(row), next: next === undefined ? null : rowKey(next) })
      setDetailOpen(false)
      toast({
        kind: 'receipt',
        title: receiptSentence(gone.message, gone.cert, 'Removed'),
        action: { label: 'Undo', onPress: () => void add({ cert: row.cert, grader: row.grader }, false) },
      })
      await load()
    } catch (err) {
      setRemoveFailure(describeFailure(err))
    } finally {
      removeBusy.current = false
      setRemoving(false)
    }
  }

  const loading = rows === null && failure === null
  const never = ordered.filter((row) => row.note === 'no sales').length
  const addButton = (
    <Button variant="primary" icon="plus" onClick={openAdd} data-slabs-add="">
      Add a Slab
    </Button>
  )

  const verdict = loading ? (
    <SkeletonText>12 slabs. 3 have never sold at their grade.</SkeletonText>
  ) : rows === null || rows.length === 0 ? undefined : (
    <>
      {count(rows.length, 'slab')}. {never === 0 ? 'Every slab has sold at its grade.' : `${never === 1 ? '1 has' : `${never} have`} never sold at ${never === 1 ? 'its' : 'their'} grade.`}
    </>
  )

  return (
    <>
      <Page
        title="Slabs"
        verdict={verdict}
        actions={
          <>
            <ReloadButton onReload={() => void load()} busy={reloading} />
            {rows !== null && rows.length === 0 ? null : addButton}
          </>
        }
        status={failure === null ? undefined : <Refused failure={failure} fallback="The slabs could not be read." onRetry={() => void load()} busy={reloading} />}
        empty={
          rows !== null && rows.length === 0 ? (
            <EmptyState icon="layers" title="No slabs yet" body="Add a slab by its cert number." actions={addButton} />
          ) : null
        }
      >
        {rows === null && failure !== null ? null : (
          <div className="bn-panel slabs-panel">
            <div className="slabs-frame">
              <table className="bn-table slabs-table" style={{ minWidth: TABLE_MIN }} aria-busy={loading ? 'true' : undefined}>
                <colgroup>
                  {COLUMNS.map((column) => (
                    <col key={column.name} style={{ width: column.width }} />
                  ))}
                </colgroup>
                <thead>
                  <tr>
                    {COLUMNS.map((column) => (
                      <th key={column.name} scope="col" className={column.num ? 'num' : undefined}>
                        {column.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading
                    ? Array.from({ length: 8 }, (_, at) => (
                        <tr key={at} className="slabs-loading-row">
                          {COLUMNS.map((column) => (
                            <td key={column.name}>
                              <Skeleton className="slabs-skeleton" />
                            </td>
                          ))}
                        </tr>
                      ))
                    : ordered.map((row) => (
                        <LedgerRow
                          key={rowKey(row)}
                          row={row}
                          onOpen={() => {
                            setDetail(row)
                            setRemoveFailure(null)
                            setDetailOpen(true)
                          }}
                        />
                      ))}
                </tbody>
              </table>
              {loading ? <span className="bn-sr" role="status">Loading</span> : null}
            </div>
          </div>
        )}
      </Page>

      <SlabSheet
        row={detail}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        removing={removing}
        removeOff={adding}
        failure={removeFailure}
        onRemove={(row) => void remove(row)}
      />

      <Sheet
        open={addOpen}
        title="Add a Slab"
        icon="plus"
        onClose={closeAdd}
        footer={
          <>
            <Button variant="ghost" onClick={closeAdd}>
              Cancel
            </Button>
            <Button type="submit" form="slabs-add-form" variant="primary" busy={adding} disabled={adding || cert.trim() === ''}>
              Add
            </Button>
          </>
        }
      >
        <form
          id="slabs-add-form"
          className="slabs-add"
          onSubmit={(event) => {
            event.preventDefault()
            if (cert.trim() !== '') void add({ cert: cert.trim(), grader }, true)
          }}
        >
          <label className="bn-field">
            <span className="bn-field-label">Cert</span>
            <input className="bn-input bn-input-mono" name="cert" value={cert} onChange={(event) => setCert(event.target.value)} autoComplete="off" spellCheck={false} />
          </label>
          <Select<string>
            label="Grader"
            value={grader}
            options={SLAB_GRADERS.map((one) => ({ value: one, label: GRADER_NAME[one] ?? one }))}
            onChange={setGrader}
          />
          <div className="slabs-add-status" aria-live="polite">
            {adding ? (
              <p className="slabs-reading">Reading Card Ladder. This takes a little while.</p>
            ) : addFailure === null ? null : (
              <Refused failure={addFailure} fallback="That slab could not be added." compact />
            )}
          </div>
        </form>
      </Sheet>
    </>
  )
}

/* ----------------------------------------------------------------------------- the ledger */

function LedgerRow({ row, onOpen }: { readonly row: SlabRow; readonly onOpen: () => void }) {
  const snapshot = row.snapshot
  const noSales = row.note === 'no sales'
  const cell = (name: string): ReactNode => {
    if (DASH_COLUMNS.has(name)) return dash()
    switch (name) {
      case 'Pop':
        return snapshot === null || snapshot.population === null ? dash() : <Count value={snapshot.population} />
      case 'Grade': {
        const text = gradeText(row)
        return text === null ? dash() : text
      }
      case 'Card':
        return (
          <button type="button" className="slabs-card-btn" data-slab={rowKey(row)} onClick={onOpen}>
            {nameOf(row)}
          </button>
        )
      case 'Card Ladder':
        return noSales ? <span className="slabs-no-sales">No sales</span> : snapshot === null ? dash() : <Money value={amount(snapshot.estimated_value)} />
      case 'Conf':
        return noSales ? null : <Conf value={snapshot?.estimated_confidence ?? null} />
      case 'Last sale':
        return noSales ? null : <Money value={amount(snapshot?.last_sale_price)} />
      default:
        return dash()
    }
  }
  return (
    <tr>
      {COLUMNS.map((column) => (
        <td key={column.name} className={column.num ? 'num' : undefined}>
          {cell(column.name)}
        </td>
      ))}
    </tr>
  )
}

/* ----------------------------------------------------------------------------- the detail sheet */

type Read = { readonly key: string; readonly detail: SlabDetail | null; readonly failure: Failure | null }

function SlabSheet({
  row,
  open,
  onClose,
  removing,
  removeOff,
  failure,
  onRemove,
}: {
  readonly row: SlabRow | null
  readonly open: boolean
  readonly onClose: () => void
  readonly removing: boolean
  readonly removeOff: boolean
  readonly failure: Failure | null
  readonly onRemove: (row: SlabRow) => void
}) {
  const [read, setRead] = useState<Read | null>(null)
  const [again, setAgain] = useState(0)
  const key = row === null ? '' : rowKey(row)

  useEffect(() => {
    if (!open || row === null) return
    let live = true
    setRead(null)
    getSlabDetail(row.grader, row.cert)
      .then((detail) => live && setRead({ key, detail, failure: null }))
      .catch((err) => live && setRead({ key, detail: null, failure: describeFailure(err) }))
    return () => {
      live = false
    }
    // `row` is read once per open: its key names it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, key, again])

  const mine = read !== null && read.key === key ? read : null
  return (
    <Sheet
      open={open}
      title={row === null ? NO_NAME : nameOf(row)}
      onClose={onClose}
      className="slabs-sheet"
      footer={
        row === null ? undefined : (
          <>
            {failure === null ? null : <Refused failure={failure} fallback="That slab could not be removed." compact />}
            <Button variant="danger" icon="trash" busy={removing} disabled={removing || removeOff} onClick={() => onRemove(row)}>
              Remove
            </Button>
          </>
        )
      }
    >
      {row === null ? null : mine !== null && mine.failure !== null ? (
        <Refused failure={mine.failure} fallback="The slab could not be read." onRetry={() => setAgain((n) => n + 1)} />
      ) : (
        <SlabBody row={row} detail={mine?.detail ?? null} />
      )}
    </Sheet>
  )
}

function Rows({ children, loading }: { readonly children?: ReactNode; readonly loading?: boolean }) {
  return (
    <ul className="slabs-rows" aria-busy={loading ? 'true' : undefined}>
      {children}
    </ul>
  )
}

function SkeletonRows({ n }: { readonly n: number }) {
  return (
    <Rows loading>
      {Array.from({ length: n }, (_, at) => (
        <li key={at} className="slabs-row">
          <Skeleton className="slabs-skeleton" />
        </li>
      ))}
    </Rows>
  )
}

/** Fixed sections first, the two of unknown length last and drawn only once the detail is here, so arrival only grows downward (D313). */
function SlabBody({ row, detail }: { readonly row: SlabRow; readonly detail: SlabDetail | null }) {
  const loading = detail === null
  const newest: SlabSnapshot | null = detail === null ? row.snapshot : (detail.snapshots[detail.snapshots.length - 1] ?? row.snapshot)
  const noSales = (detail?.note ?? row.note) === 'no sales'
  const grade = gradeText(row)
  const speed = newest?.speed ?? null
  const sales = detail?.sales.slice(0, 5) ?? []
  /* Rows the sales list holds a place for, from the list row, which is there from the first paint: one for "no sales", else five (D313). */
  const held = row.note === 'no sales' ? 1 : 5
  return (
    <div className="slabs-body">
      <p className="bn-facts slabs-facts">
        <span>{grade ?? GRADER_NAME[row.grader] ?? row.grader}</span> <span>On the list since {dayDate(row.added)}</span>
      </p>

      <Section title="Worth">
        {noSales ? (
          <p className="slabs-no-sales">No sales at this grade.</p>
        ) : (
          <dl className="slabs-worth">
            <div>
              <dt>Card Ladder estimate</dt>
              <dd>
                <Money value={amount(newest?.estimated_value)} /> <Conf value={newest?.estimated_confidence ?? null} />
              </dd>
              <dd className="slabs-source">Card Ladder's estimate.</dd>
            </div>
            <div>
              <dt>Grade ladder value</dt>
              <dd>
                <Money value={amount(newest?.cl_value)} /> <Conf value={newest?.cl_confidence ?? null} />
              </dd>
              <dd className="slabs-source">Card Ladder's ladder value.</dd>
            </div>
          </dl>
        )}
      </Section>

      <Section title="Sales at the grade">
        {loading ? (
          <SkeletonRows n={held} />
        ) : (
          <Rows>
            {sales.length === 0 ? <li className="slabs-row slabs-no-sales">No sales at this grade yet.</li> : null}
            {sales.map((sale) => (
              <li key={sale.id} className="slabs-row slabs-sale">
                <Money value={amount(sale.price)} />
                <span className="slabs-sale-when">
                  {dayDate(sale.date)}
                  {typeof sale.platform === 'string' && sale.platform !== '' ? ` on ${sale.platform}` : ''}
                </span>
                {typeof sale.url === 'string' && sale.url !== '' ? (
                  <a className="slabs-link" href={sale.url} target="_blank" rel="noopener noreferrer">
                    <span>View listing</span>
                    <span className="bn-sr"> of the {dayDate(sale.date)} sale</span>
                    <Icon name="external" size={14} />
                  </a>
                ) : null}
              </li>
            ))}
            {Array.from({ length: Math.max(0, held - Math.max(1, sales.length)) }, (_, at) => (
              <li key={`held-${at}`} className="slabs-row" aria-hidden="true" />
            ))}
          </Rows>
        )}
      </Section>

      <Section title="Sales speed">
        <Rows loading={loading}>
          <li className="slabs-row slabs-speed slabs-head" aria-hidden="true">
            <span>Window</span>
            <span className="slabs-fig">Velocity</span>
            <span className="slabs-fig">Average price</span>
          </li>
          {WINDOWS.map(([id, words]) => {
            const one = speed?.[id]
            return loading ? (
              <li key={id} className="slabs-row">
                <Skeleton className="slabs-skeleton" />
              </li>
            ) : (
              <li key={id} className="slabs-row slabs-speed">
                <span>{words}</span>
                <span className="slabs-fig">{one?.velocity == null ? DASH : one.velocity.toLocaleString('en-US')}</span>
                <Money value={amount(one?.averagePrice)} />
              </li>
            )
          })}
        </Rows>
      </Section>

      <Section title="Population at the grade">
        <p className="slabs-pop">{newest?.population == null ? dash() : <Count value={newest.population} />} at this grade</p>
      </Section>

      {detail === null ? null : (
        <>
          <Section title="Grade ladder">
            <Rows>
              <li className="slabs-row slabs-step slabs-head" aria-hidden="true">
                <span>Grade</span>
                <span className="slabs-fig">Value</span>
                <span>Confidence</span>
              </li>
              {detail.ladder.map((step) => (
                <li key={step.grade} className="slabs-row slabs-step" data-here={step.grade === row.grade ? 'true' : undefined} aria-current={step.grade === row.grade ? 'true' : undefined}>
                  <span>{step.label}</span>
                  <Money value={amount(step.cl_value)} />
                  <Conf value={step.cl_confidence} />
                </li>
              ))}
            </Rows>
          </Section>

          <Section title="Snapshots">
            <Rows>
              <li className="slabs-row slabs-snap slabs-head" aria-hidden="true">
                <span>Day</span>
                <span className="slabs-fig">Estimate</span>
                <span>Confidence</span>
                <span className="slabs-fig">Last sale</span>
              </li>
              {[...detail.snapshots].reverse().map((snap) => (
                <li key={snap.day} className="slabs-row slabs-snap">
                  <span>{dayDate(snap.day)}</span>
                  <Money value={amount(snap.estimated_value)} />
                  <Conf value={snap.estimated_confidence} />
                  <Money value={amount(snap.last_sale_price)} />
                </li>
              ))}
            </Rows>
          </Section>
        </>
      )}
    </div>
  )
}
