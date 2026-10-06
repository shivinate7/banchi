import { useMemo, useState } from 'react'
import type { MatchSweepCard, MatchSweepDetail } from './types'
import { previewUrl } from './server'
import { NO_REASON, NO_REASON_OFF, unreadGroup } from './reasons'
import { Button, EmptyState, Loading, Sheet, Slot } from './kit'
import './ReviewBandSheet.css'

/* THE REVIEW BAND'S SHEETS (`docs/specs/identify-engine-pick.md`, section 10). One sheet per count: waiting for a paid look
 * (grouped by why the free reader stopped), not yet looked at (by box), matched free (by set) and the cards that need a set
 * named (by box). A sheet is a SNAPSHOT taken at open (D313, D181): when the band's count later differs it says so in a held
 * line and offers "Show it again", and never rewrites itself. It builds no fix. It points at the free fix the app already has,
 * and a row press goes to the card's own place on Inventory, where the claim and the set hint are corrected.
 *
 * A GROUP SHOWS ITS FIRST 50 ROWS, then "Show 50 more", so a 2,000-card group paints 50 photographs. */

export type BandSheetData = {
  readonly kind: MatchSweepDetail
  /** null while the one read is out. */
  readonly cards: readonly MatchSweepCard[] | null
  readonly failed: boolean
}

const PAGE = 50
const SETTLED_BY_CLAIM = new Set(['printing_settled_by_claim', 'narrowed_by_claim'])

export const SHEET_LABELS: Record<MatchSweepDetail, string> = {
  matched: 'matched free',
  paid: 'waiting for a paid look',
  unread: 'not yet looked at',
  unhinted: 'need a set named',
}

/** The sheet's title and the count button's name: the count's own words with the number. */
export function sheetTitle(kind: MatchSweepDetail, n: number): string {
  return kind === 'unhinted' && n === 1 ? '1 needs a set named' : `${n} ${SHEET_LABELS[kind]}`
}

const EMPTY: Record<'paid' | 'unread' | 'matched', string> = {
  paid: 'No card is waiting for a paid look.',
  unread: 'The free reader has looked at every card.',
  matched: 'The free reader has not matched a card yet.',
}

type Group = {
  readonly key: string
  readonly title: string
  readonly codes: readonly string[]
  readonly cards: readonly MatchSweepCard[]
  readonly fix: string | null
  readonly note: string | null
}

/* Largest first, ties in the order they first appear (the server sorts by box, then slot). */
function bySize(groups: Group[]): Group[] {
  return groups
    .map((group, at) => ({ group, at }))
    .sort((a, b) => b.group.cards.length - a.group.cards.length || a.at - b.at)
    .map((x) => x.group)
}

function gather(cards: readonly MatchSweepCard[], name: (card: MatchSweepCard) => { key: string; title: string; code?: string }): Group[] {
  const found = new Map<string, { title: string; codes: Set<string>; cards: MatchSweepCard[] }>()
  for (const card of cards) {
    const { key, title, code } = name(card)
    const group = found.get(key) ?? { title, codes: new Set<string>(), cards: [] }
    if (code !== undefined) group.codes.add(code)
    group.cards.push(card)
    found.set(key, group)
  }
  return [...found.entries()].map(([key, group]) => {
    const codes = [...group.codes]
    const said = codes.length > 0 ? unreadGroup(codes[0] === '' ? null : (codes[0] ?? null)) : null
    return { key, title: group.title, codes, cards: group.cards, fix: said?.fix ?? null, note: said?.note ?? null }
  })
}

function groupsOf(kind: MatchSweepDetail, cards: readonly MatchSweepCard[]): Group[] {
  if (kind === 'paid') {
    return bySize(
      gather(cards, (card) => {
        const said = unreadGroup(card.code ?? null)
        return { key: said.title, title: said.title, code: card.code ?? '' }
      }),
    )
  }
  if (kind === 'matched') return bySize(gather(cards, (card) => ({ key: card.set || 'No set', title: card.set || 'No set' })))
  return gather(cards, (card) => ({ key: String(card.box), title: card.box_name }))
}

/* The pattern is read from the rows and never guessed: most rows of a rarity group in one box, none naming a rarity. */
function pattern(group: Group): { box: number; name: string; n: number } | null {
  if (!group.codes.includes('margin_too_small') || group.cards.length < 3) return null
  const here = new Map<number, { name: string; n: number }>()
  for (const card of group.cards) {
    if ((card.rarity_claim ?? []).length > 0) continue
    const seen = here.get(card.box) ?? { name: card.box_name, n: 0 }
    seen.n += 1
    here.set(card.box, seen)
  }
  const top = [...here.entries()].sort((a, b) => b[1].n - a[1].n)[0]
  return top !== undefined && top[1].n * 2 > group.cards.length ? { box: top[0], name: top[1].name, n: top[1].n } : null
}

function Row({ card, kind }: { readonly card: MatchSweepCard; readonly kind: MatchSweepDetail }) {
  const href = `#/inventory?box=${card.box}${card.cid === '' ? '' : `&card=${encodeURIComponent(card.cid)}`}`
  const place = `${card.box_name}, slot ${card.index}`
  return (
    <li className="rbs-row">
      <a className="rbs-row-link" href={href}>
        <span className="rbs-photo">
          <img loading="lazy" alt="" src={previewUrl(card.box, card.index, { cid: card.cid }) ?? undefined} />
        </span>
        <span className="rbs-row-body">
          {kind === 'matched' ? (
            <>
              <span className="rbs-line">
                <span className="rbs-name">{card.name}</span> <span className="rbs-set">{card.set}</span> <span className="bn-mono">{card.number}</span>
              </span>
              <span className="rbs-place">{place}</span>{' '}
              {SETTLED_BY_CLAIM.has(card.accept ?? '') ? <span className="rbs-thin">Chosen by your rarity claim</span> : null}
            </>
          ) : (
            <>
              <span className="rbs-place rbs-place-lead">{place}</span>{' '}
              {(card.candidates ?? []).map((cand, at) => (
                <span key={at} className="rbs-line">
                  <span className="rbs-name">{cand.name}</span> <span className="rbs-set">{cand.set}</span> <span className="bn-mono">{cand.number}</span>{' '}
                </span>
              ))}
            </>
          )}
        </span>
      </a>
    </li>
  )
}

function GroupView({ group, kind, readerOn }: { readonly group: Group; readonly kind: MatchSweepDetail; readonly readerOn: boolean }) {
  const [shown, setShown] = useState(PAGE)
  const seen = group.cards.slice(0, shown)
  const found = pattern(group)
  /* "A free read will fill it in" is true only while the reader is on. */
  const line = group.title === NO_REASON.title && !readerOn ? NO_REASON_OFF : (group.fix ?? group.note)
  return (
    <section className="rbs-group" role="group" aria-label={group.title}>
      <div className="rbs-group-head">
        <h3 className="rbs-group-title">{group.title}</h3>
        <span className="rbs-group-count bn-mono">{group.cards.length}</span>
      </div>
      {line === null ? null : (
        <p className="rbs-pointer">
          {line}
          {found === null ? null : (
            <>
              {' '}
              {found.n} of {group.cards.length} are in <a href={`#/inventory?box=${found.box}`}>{found.name}</a> and name no rarity.
            </>
          )}
        </p>
      )}
      <ul className="rbs-list">
        {seen.map((card) => (
          <Row key={card.key} card={card} kind={kind} />
        ))}
      </ul>
      {seen.length < group.cards.length ? (
        <Button variant="ghost" size="sm" onClick={() => setShown(shown + PAGE)} className="rbs-more">
          Show {PAGE} more
        </Button>
      ) : null}
    </section>
  )
}

export function BandSheet({
  open,
  onClose,
  data,
  figure,
  moved,
  busy,
  readerOn,
  onAgain,
}: {
  readonly open: boolean
  readonly onClose: () => void
  /** null before the first press: nothing to draw while the leave beat runs. */
  readonly data: BandSheetData | null
  /** The band's own figure for this count, titling the sheet until its rows arrive. */
  readonly figure: number
  /** The band's count differs from the snapshot. */
  readonly moved: boolean
  /** "Show it again" is reading. */
  readonly busy: boolean
  /** The background reader is switched on. */
  readonly readerOn: boolean
  readonly onAgain: () => void
}) {
  const kind = data?.kind ?? 'paid'
  const cards = data?.cards ?? null
  const groups = useMemo(() => (cards === null ? [] : groupsOf(kind, cards)), [kind, cards])
  const back = () => {
    onClose()
    window.location.hash = '#/capture'
  }
  const again = (
    <Button variant="ghost" size="sm" onClick={onAgain} disabled={busy}>
      Show it again
    </Button>
  )
  const line = (
    <>
      <span>The count has moved</span>
      {again}
    </>
  )
  return (
    <Sheet open={open} onClose={onClose} title={sheetTitle(kind, cards === null ? figure : cards.length)} icon="list" className="review-band-sheet">
      <div className="rbs-moved" aria-live="polite">
        <Slot show={moved} ghost={again} className="rbs-moved-slot">
          {line}
        </Slot>
      </div>
      {data?.failed === true && cards === null ? (
        <EmptyState icon="alert" title="The cards did not load." actions={<Button onClick={onAgain}>Try again</Button>} />
      ) : cards === null ? (
        <Loading rows={4} label="Loading the cards" />
      ) : cards.length === 0 ? (
        kind === 'unhinted' ? null : (
          <EmptyState icon="inbox" title={EMPTY[kind]} actions={<Button onClick={back}>Back to Capture</Button>} />
        )
      ) : (
        <>
          {kind === 'unhinted' ? <p className="rbs-pointer">Name the set on the card.</p> : null}
          {groups.map((group) => (
            <GroupView key={group.key} group={group} kind={kind} readerOn={readerOn} />
          ))}
        </>
      )}
    </Sheet>
  )
}
