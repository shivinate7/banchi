/* WHERE `#/pricing`'s ROWS CAME FROM, AND WHAT MAY BE ASKED ABOUT THEM (D103).
 *
 * THE SCREEN USED TO HAVE ONE SOURCE AND ONE SENTINEL FOR IT. `run` is derived —
 * `loaded.length === 1 ? loaded[0] : null` — so a null meant "zero or two-plus runs", and four
 * separate capabilities were gated on that one value: the history press, the trends press, the
 * receipt's download links, and the single-run emit. That worked while a run was the only thing
 * a row could come out of. A markdown is a second thing, and it can take a reading while it can
 * never take an emit, so a single sentinel cannot express it.
 *
 * SO THE SCREEN ASKS ABOUT THE ROW, NEVER ABOUT THE DOOR. `source.history === null` reads "no
 * reading can be taken here"; `source.copies` reads "these rows are cards this store holds".
 * Both are questions with answers on either side, which is what keeps the body of `Pricing.tsx`
 * from filling up with `kind === 'run' ? … : …`. Exactly two places ask which door it was — the
 * landing deck and the ship bar — and those are the two places the modes genuinely are different
 * objects rather than one object with a field missing.
 *
 * NO JSX HERE, WHICH IS `runScope.ts`'s AND `readiness.ts`'s POSTURE. One type, the builders,
 * and the hash parsing. A source that rendered would be a second screen.
 *
 * `SECTIONS` AND `PRESETS` STAY IN `Pricing.tsx` AND ARE PASSED IN. `scripts/docs-audit.py`'s
 * `pricing presets` row reads `const PRESETS` out of that file by path, so moving the pricing
 * vocabulary out of the screen's front door would turn a passing mechanical check into a false
 * alarm — and the two constants belong together. The section list arrives as an argument for
 * that reason and not because a source cannot own one.
 */

import type { IconName } from './kit'
import type {
  MarkdownSku,
  MarkdownTable,
  MergedSku,
  PriceHistoryPayload,
  PricingSku,
  PricingWorklist,
  TrendsPayload,
} from './types'

/** One drawn band of the list. `Pricing.tsx` owns the values; this is the shape they take. */
export type SectionSpec = {
  bucket: PricingSku['bucket']
  title: string
  icon: IconName
  note: (cut: string) => string
}

export type PricingSource = {
  /** Which door. Legal at EXACTLY TWO call sites — the deck and the ship bar. */
  kind: 'run' | 'markdown'
  /** The run name, or the markdown stamp. An address, and never a capability. */
  id: string | null

  /** The list, in the shape the row draws. */
  rows: readonly MergedSku[]
  sections: readonly SectionSpec[]

  /** Whether a typed cut-off re-partitions the list.
   *
   *  TRUE ON BOTH DOORS SINCE 2026-09-07, and it was the last thing telling them apart on this
   *  axis. The cut-off is ONE variable (D99) — the line, and what everything under it lists at
   *  — so on a run the list moving under a new figure answers "how many cards does that make
   *  cheap", and on a lens it answers "how many live listings would that press move". Both are
   *  real; what differs is only WHEN the figure is spent, and that is `CutoffPanel`'s
   *  `applyCount` rather than this flag. Kept as a field because a future source may genuinely
   *  have nothing for the figure to decide. */
  repartition: boolean

  /** Whether these rows are copies this store physically holds — the thumb, the quantity cell,
   *  the photo drawer. False for a live listing, which this store may never have held at all. */
  copies: boolean

  /** Whether the rule's figure OPENS IN THE FIELD or only behind it as a placeholder.
   *
   *  TRUE FOR A RUN AND FALSE FOR A LENS, for the same reason `repartition` splits: what an
   *  untouched row MEANS is different. A run's rows are not listed yet, so the rule's price is
   *  the answer until the operator overrides it and a field full of it is the worklist working.
   *  A lens's rows are already live at a price somebody chose; on the owner's store a 7-day
   *  window has the rule speaking about 243 of 387 live SKUs, so a filled field turns one bulk
   *  press into 243 live price changes. The figure is still one keystroke or one preset away —
   *  it is drawn as a placeholder — but the default is that nothing moves. */
  proposes: boolean

  /** Why this SKU may not be priced AT ALL, as the operator's own sentence, or null.
   *
   *  THE SERVER DECIDES MEMBERSHIP AND THIS ONLY DRAWS IT. `pipeline/reprice.py:read_back` is
   *  what actually refuses the push, and `GET …/table` ships `unpriceable` so the row can
   *  refuse the field rather than let a price be typed that the apply will throw away. That
   *  field was declared on the wire and read by NOTHING until 2026-09-06: a locked row drew a
   *  live input, `pushable` counted it, the corpus write landed, and only the receipt named
   *  the refusal — D101's defect exactly, a screen offering a control it would not honour. */
  locked: (sku: string) => string | null

  /** The two readings, pre-bound to the document that holds the row. `null` means no reading
   *  can be taken from here, which is a run picker holding zero runs or more than one. */
  history: ((sku: string) => Promise<PriceHistoryPayload>) | null
  trends: ((skus: string[]) => Promise<TrendsPayload>) | null

  /** When the figures on a row were read, as epoch millis, or null. */
  readAtOf: (sku: MergedSku) => number | null
}

/** The runs source — today's behaviour, moved rather than rewritten.
 *
 *  EVERY BODY HERE IS THE ONE `Pricing.tsx` HELD, so the run path is byte-identical by
 *  construction rather than by care. `readAtOf` in particular is the same closure: the last leg
 *  of a merged row names the run whose write time dates its figures.
 */
export function runSource(
  work: PricingWorklist | null,
  run: string | null,
  sections: readonly SectionSpec[],
  fetchers: {
    history: (run: string, sku: string) => Promise<PriceHistoryPayload>
    trends: (run: string, skus: string[]) => Promise<TrendsPayload>
  },
): PricingSource {
  return {
    kind: 'run',
    id: run,
    rows: work?.skus ?? [],
    sections,
    repartition: true,
    copies: true,
    proposes: true,
    // A RUN HAS NO LOCKED ROWS. Its rows are cards in a drawer waiting for a price; there is
    // no live listing for a refusal to be about.
    locked: () => null,
    // BOUND ONLY WHERE THERE IS ONE RUN TO ADDRESS. Both routes are run-scoped, and a worklist
    // merged over three runs has no single document to read a history out of — which is what
    // the old `disabled={run === null}` said, in the one place it is now said.
    history: run === null ? null : (sku: string) => fetchers.history(run, sku),
    trends: run === null ? null : (skus: string[]) => fetchers.trends(run, skus),
    readAtOf: (sku: MergedSku) => {
      const from = sku.in[sku.in.length - 1]?.run ?? run
      const stamp = from === null ? undefined : work?.written_at?.[from]
      return typeof stamp === 'number' ? stamp : null
    },
  }
}

/** One live listing as the row draws it — the ONE place the two shapes meet.
 *
 *  THE WIRE TYPE IS HONEST AND THE ROW STILL WANTS `MergedSku`, so the projection lives here,
 *  documented, rather than being a server assertion that a live listing is a joined card. Every
 *  run-shaped field below takes the value that makes the row's OWN guards erase it: the row
 *  already tests `positions[0] ?? null`, `listing === null`, and `in.length < 2 && !over_cap`,
 *  so the cells simply do not draw. Only the thumb and the quantity cell were unguarded, and
 *  `source.copies` is what turns those two off.
 *
 *  `bucket` MUST BE A REAL BUCKET AND IS NOT COSMETIC. `write()` picks the corpus channel with
 *  `targetOf(bucket)`, so a row landing in `no_market_data` writes its answer into the table
 *  `pipeline/decisions.py:blocking` reads to refuse an emit. A live listing is a card the
 *  operator is already selling, which is `listable` — the cut-off decides which import FILE a
 *  row is bound for, and this row is bound for none.
 *
 *  `snap.now` IS THE OPERATOR'S OWN ASKING PRICE, which is what makes `N` work on this screen
 *  with no new key binding: the field's `n` command snaps to `snap.now`, and on a live listing
 *  the honest meaning of "now" is what TCGplayer is asking today.
 */
function asRow(entry: MarkdownSku): MergedSku {
  const cell = (column: string): string | null => {
    const raw = entry.row[column]
    return raw === undefined || raw.trim() === '' ? null : raw.trim()
  }
  return {
    sku: entry.sku,
    game: '',
    row: entry.row,
    bucket: 'listable',
    name: entry.name,
    condition: entry.condition,
    set_name: cell('Set Name') ?? '',
    snap: {
      now: entry.asking,
      market: entry.market,
      low: cell('TCG Low Price'),
      low_with_shipping: cell('TCG Low Price With Shipping'),
      direct_low: cell('TCG LowestSalePrice'),
    },
    // THE REAL FIGURES SINCE 2026-09-07. This was `{}`, so every preset button on the lens
    // filled nothing — and still wrote `policy.rule` to the store, silently repricing every
    // future joined run from a screen that could not act on the rule itself.
    presets: entry.presets ?? {},
    rule_price: entry.proposed,
    // TCGPLAYER'S OWN LIVE COUNT, which is an honest figure and the one the row's `LiveCount`
    // is for. `pushed` and `staged` are this pipeline's commitments and it has made none here.
    listing: { pushed: 0, staged: 0, live: entry.live },
    // EVERY FIELD BELOW IS A JOIN'S ARITHMETIC AND MEANS NOTHING FOR A LIVE LISTING. They are
    // the values the row's own guards read as "nothing to draw", never an invented figure.
    positions: [],
    copies: 0,
    add_to_quantity: 0,
    backstock: 0,
    live_before: entry.live,
    committed: 0,
    copies_out: 0,
    at_cap: false,
    nothing_to_add: null,
    in: [],
    claimed_add: 0,
    over_cap: false,
  } as unknown as MergedSku
}

/** SKU -> the sentence saying why no price may be pushed for it, for one table.
 *
 *  MEMOISED ON THE TABLE OBJECT because `markdownSource` is called on every render and this
 *  walks every live row — 759 of them on the owner's store. A `WeakMap` so a table that goes
 *  out of scope takes its index with it. */
const LOCKED = new WeakMap<MarkdownTable, Map<string, string>>()

function lockedOf(table: MarkdownTable | null): Map<string, string> {
  if (table === null) return new Map()
  const cached = LOCKED.get(table)
  if (cached !== undefined) return cached
  const bar = new Set(table.unpriceable ?? [])
  const out = new Map<string, string>()
  for (const entry of table.skus ?? []) {
    if (entry.skip !== null && bar.has(entry.skip)) {
      out.set(entry.sku, table.says?.[entry.skip] ?? entry.skip)
    }
  }
  LOCKED.set(table, out)
  return out
}

/** The markdown source — the operator's whole live inventory, staleness as a filter over it. */
export function markdownSource(
  stamp: string,
  table: MarkdownTable | null,
  sections: readonly SectionSpec[],
  fetchers: {
    history: (stamp: string, sku: string) => Promise<PriceHistoryPayload>
    trends: (stamp: string, skus: string[]) => Promise<TrendsPayload>
  },
): PricingSource {
  return {
    kind: 'markdown',
    id: stamp,
    rows: (table?.skus ?? []).map(asRow),
    sections,
    // TRUE SINCE 2026-09-07, AND FALSE BEFORE IT. The old reason was that "the cut-off decides
    // which import file a row is bound for, and a live listing is bound for none" — right about
    // the FILE and wrong about the FIGURE. D99 made the line and the cheap price ONE variable,
    // so the cut-off also says what everything under it is worth, and the operator asked for
    // exactly that here: price the cheap half of the live book in one press, the way a run
    // already does. Re-partitioning is no longer a distinction the pipeline will not act on —
    // it is the one the press acts on.
    repartition: true,
    // A LIVE LISTING IS NOT A COPY IN A DRAWER. This store may never have held it at all —
    // 28 of the owner's 387 live SKUs are exactly that — so there is no photograph, no slot
    // and no quantity going into a file. THEY ARE PRICEABLE NOW: never having held one used
    // to be a terminal refusal, and it refused 94.5% of that live book by asking value.
    copies: false,
    // THE FIELD OPENS EMPTY HERE. These rows are already live at a price somebody chose, and
    // the rule speaks about 243 of the owner's 387 at a 7-day window — a filled field would
    // make one bulk press 243 live price changes. The suggestion is drawn as a placeholder,
    // so it is one keystroke or one preset away and nothing moves by default.
    proposes: false,
    // THE SERVER'S OWN LIST, LOOKED UP PER ROW. Built once here rather than per render, and
    // read off `unpriceable` so the screen and `read_back` cannot disagree about which rows
    // refuse. `says` is `pipeline/reprice.py:SKIP_SENTENCE` — the sentence is never re-worded
    // on this side, so the row and the receipt say one string from one table.
    locked: (sku: string) => lockedOf(table).get(sku) ?? null,
    history: (sku: string) => fetchers.history(stamp, sku),
    trends: (skus: string[]) => fetchers.trends(stamp, skus),
    // THE WHOLE TABLE WAS READ AT ONE MOMENT, so every row's figures carry the same age —
    // unlike a run merge, where each leg has its own write time.
    readAtOf: () => {
      const at = table?.at ? Date.parse(table.at) : NaN
      return Number.isNaN(at) ? null : at
    },
  }
}

/** The runs named on the hash. `run` repeats rather than carrying a comma list. */
export function runsInHash(): string[] {
  return query().getAll('run').filter((name) => name !== '')
}

/** The markdown stamp on the hash, or null.
 *
 *  A QUERY ON AN EXISTING ROUTE RATHER THAN A ROUTE OF ITS OWN. `App.tsx`'s router strips `?…`
 *  before matching, and `#/pricing` already addressed itself this way for `?run=`, so the lens
 *  costs no `ROUTES` row — which matters because a row there moves three mechanical counts
 *  (`route census`, `route rosters`, and every spec's pinned roster) and is a deliberate edit
 *  rather than a side effect. D100's own ROUTES comment left that row available for the asking;
 *  this is a third answer it did not anticipate.
 *
 *  SHAPE-CHECKED HERE, because the stamp goes into a URL path. `YYYYMMDD-HHMMSS` and nothing
 *  else mints one, and the server checks it again — this is the client refusing to build a
 *  request it knows is malformed, not the guard.
 */
export function markdownInHash(): string | null {
  const stamp = query().get('markdown') ?? ''
  return /^\d{8}-\d{6}$/.test(stamp) ? stamp : null
}

function query(): URLSearchParams {
  return new URLSearchParams(window.location.hash.split('?')[1] ?? '')
}
