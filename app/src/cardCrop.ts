/* THE FETCHING POLICY BEHIND `cropStyle` (kit/index.tsx), WHICH DELIBERATELY HOLDS ONLY THE
 * GEOMETRY. Its own comment says why: *"WHAT IS NOT HERE is the fetching: the hero asks once for
 * one card, the worklist asks for the rows a scroll brings into view, and those are policies, not
 * geometry."* Those two policies are both here now, because a third, fourth and fifth screen
 * wanted them (D125) and the machine below was already written once, in `Pricing.tsx`, at fifty
 * lines with four findings in it that nothing would have carried to the next copy.
 *
 * A rig photograph is mostly stand. On box 6 the card sits at [240, 1051, 1649, 3020] inside a
 * 2160x3840 frame; on box 3 at [126, 741, 1770, 3038]. `POST /pipeline/crop-preview` is the SAME
 * detector the batch reading uses (`geometry/detect.py`), it is FREE, it calls no model, and it
 * returns that rectangle — so every screen frames the card on what the pipeline itself thinks the
 * card is, rather than on a second guess written per screen.
 *
 * THE FOUR FINDINGS THE POLICY IS MADE OF, none of them optional:
 *
 *   - ONE CARD PER CALL, ALWAYS. `indices` is a scope, not a batch — the route answers with one
 *     `sample`, picked out of the scope by `offset`. So a card is a request, and the only levers
 *     left are how many ask and when.
 *   - STRICTLY SERIAL, and this one is not a preference. The route builds a scope directory named
 *     `box<n>-<count>-<unix seconds>` and deletes any directory already at that name; every
 *     single-index request for one box inside the same second therefore collides on the SAME name
 *     and rmtree's its neighbour mid-read. Measured against this server: 12 concurrent requests,
 *     11 failed with a FileNotFoundError out of the symlink. One in flight at a time.
 *   - ANSWERED ONCE PER SESSION. The reading is a property of a photograph, and a photograph at
 *     `box/index` does not change under a sitting, so the cache outlives the mount and every
 *     screen shares it: a card priced on `#/pricing` is already answered when the box walk
 *     reaches it.
 *   - `max_edge: 256` because the response carries the prepared JPEG as a data URI and nothing
 *     here draws it: 523KB a card at the default, 20KB at the floor. The rectangle is computed
 *     against the ORIGINAL size and is identical either way.
 *
 * A refusal, a missing rect, or a server that is not there leaves the element's own framing in
 * place. Every screen here was legible before this and must never be worse for it.
 */
import { useEffect, useRef, useState, type RefObject } from 'react'

import type { Crop } from './kit'
import { cropPreview } from './server'

export type CropRead = Crop | null

/** Answered readings, `box/index` -> crop or null. Module scope: it survives the mount, and it is
 *  ONE map for the whole app rather than one per screen. */
const CROPS = new Map<string, CropRead>()
/** Asked for, not yet answered. Drained one at a time by `pumpCrops`. */
const WANTED: string[] = []
const WATCH = new Map<string, Set<() => void>>()
let pumping = false

function cropKey(box: number, index: number): string {
  return `${box}/${index}`
}

/* URGENT JUMPS THE LINE, AND THE BOX WALK IS WHY (D125).
 *
 * `#/inventory` steps card by card under an arrow key, and auto-repeat is faster than the ~115ms
 * a reading costs — so a walk through a hundred unanswered cards queues a hundred requests, and
 * FIFO answers the card the operator is LOOKING AT last, about eleven seconds after they stopped
 * moving. Every screen that draws ONE photograph asks urgently, and a list's observer-driven rows
 * keep the plain end of the queue.
 *
 * Only the newest urgent want is kept. A walk supersedes its own previous card rather than
 * stacking, so the backlog cannot grow with the length of the walk. Rows already asked for stay
 * asked for: they are cheap and the answer is cached for the whole session either way. */
let urgent: string | null = null

function wantCrop(key: string, now: boolean): void {
  if (CROPS.has(key)) return
  if (now) {
    if (urgent === key) return
    const already = WANTED.indexOf(key)
    if (already >= 0) WANTED.splice(already, 1)
    /* The previous urgent card has been walked past. Drop it to the back rather than dropping it
       altogether — a step back up the box is the commonest next move there is. */
    if (urgent !== null && !CROPS.has(urgent) && !WANTED.includes(urgent)) WANTED.push(urgent)
    urgent = key
    WANTED.unshift(key)
  } else {
    if (WANTED.includes(key)) return
    WANTED.push(key)
  }
  void pumpCrops()
}

async function pumpCrops(): Promise<void> {
  if (pumping) return
  pumping = true
  try {
    for (;;) {
      const key = WANTED.shift()
      if (key === undefined) return
      if (CROPS.has(key)) continue
      const [box, index] = key.split('/').map(Number)
      let read: CropRead = null
      try {
        const { sample } = await cropPreview({
          // ONE CARD, NAMED AS A POSITION KEY — the selection's own vocabulary, and the same
          // string this cache is keyed by. It was `{box, indices: [index]}`, which was the one
          // idea spelled twice: `keys` is what the cache, the queues and the join use.
          selection: { keys: [`${box!}/${index!}`] },
          crop: true,
          maxEdge: 256,
        })
        if (sample.rect != null && sample.frame != null && sample.crop_refused == null) {
          read = { frame: sample.frame, rect: sample.rect }
        }
        /* A REFUSAL IS AN ANSWER and is remembered: `crop_refused`, no rectangle, an unreadable
           frame. Asking again would get the same one out of the same photograph. */
        CROPS.set(key, read)
      } catch {
        /* A FAILURE IS NOT AN ANSWER, so nothing is written down. The card stays uncropped for
           this mount — its observer has already fired — and the next visit asks again, which is
           what a capture server that was restarting deserves. */
      }
      if (urgent === key) urgent = null
      const told = WATCH.get(key)
      if (told !== undefined) for (const tell of told) tell()
    }
  } finally {
    pumping = false
  }
}

type At = { readonly box: number; readonly index: number } | null

function subscribe(key: string, tell: () => void): () => void {
  let watching = WATCH.get(key)
  if (watching === undefined) {
    watching = new Set()
    WATCH.set(key, watching)
  }
  watching.add(tell)
  return () => {
    watching.delete(tell)
    if (watching.size === 0) WATCH.delete(key)
  }
}

/** THE ONE-PHOTOGRAPH POLICY: ask now, because it is already on screen. For a hero, a drawer, a
 *  preview panel, a confirmation thumbnail — anywhere the card being drawn is the card the
 *  operator is looking at. Asks urgently, so a box walk answers the card under the cursor rather
 *  than the hundred it was dragged past. */
export function useCardCrop(at: At): CropRead {
  const key = at === null ? null : cropKey(at.box, at.index)
  const [crop, setCrop] = useState<CropRead>(() => (key === null ? null : CROPS.get(key) ?? null))

  useEffect(() => {
    if (key === null) {
      setCrop(null)
      return
    }
    setCrop(CROPS.get(key) ?? null)
    if (CROPS.has(key)) return
    const drop = subscribe(key, () => setCrop(CROPS.get(key) ?? null))
    wantCrop(key, true)
    return drop
  }, [key])

  return crop
}

/** THE LIST POLICY: ask when the row comes within 400px of the viewport, so an 11-row worklist
 *  costs 11 requests and a 109-row one costs the dozen that were actually looked at. Attach
 *  `hostRef` to the row's own element. Falls back to asking immediately where the browser has no
 *  `IntersectionObserver` — a render harness, mostly. */
export function useCardCropWhenSeen<T extends Element>(at: At, hostRef: RefObject<T | null>): CropRead {
  const key = at === null ? null : cropKey(at.box, at.index)
  const [crop, setCrop] = useState<CropRead>(() => (key === null ? null : CROPS.get(key) ?? null))

  useEffect(() => {
    if (key === null) {
      setCrop(null)
      return
    }
    setCrop(CROPS.get(key) ?? null)
    if (CROPS.has(key)) return
    const drop = subscribe(key, () => setCrop(CROPS.get(key) ?? null))
    const node = hostRef.current
    let eye: IntersectionObserver | null = null
    if (node !== null && typeof IntersectionObserver === 'function') {
      eye = new IntersectionObserver(
        (entries) => {
          if (!entries.some((entry) => entry.isIntersecting)) return
          eye?.disconnect()
          eye = null
          wantCrop(key, false)
        },
        { rootMargin: '400px 0px' },
      )
      eye.observe(node)
    } else {
      wantCrop(key, false)
    }
    return () => {
      drop()
      eye?.disconnect()
    }
  }, [key, hostRef])

  return crop
}

/** For a screen that owns its own host element and wants the list policy without threading a ref
 *  out of it. Returns the ref to attach and the reading. */
export function useSeenCardCrop<T extends Element>(at: At): { crop: CropRead; hostRef: RefObject<T | null> } {
  const hostRef = useRef<T | null>(null)
  const crop = useCardCropWhenSeen(at, hostRef)
  return { crop, hostRef }
}
