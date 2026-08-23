/* The motion trace — D19's Tier-1 tuning instrument, built the day the rig session asked.
 *
 * One feeder pass with this recording answers every question the thresholds in motion.ts
 * were derived without: the feeder's true period and jitter, how much of each cycle the
 * card is MOVING versus SITTING STILL (the one number nobody has ever measured), and
 * whether the gates decided correctly at each settle. The file downloads from the HUD and
 * is small enough to hand to a session (~3 MB for a ten-minute run), which is the whole
 * point — tuning happens offline against the trace instead of costing another rig trip.
 *
 * WHAT IS RECORDED, AND WHY EXACTLY THIS:
 *
 *   frames     [t, d, luma] for every frame the machine saw. The full timing signal —
 *              period, jitter, t_move/t_still all fall out of it — at ~20 bytes a frame
 *              instead of the ~2 KB the grid itself would cost.
 *   events     every fire/suppression/stall, WITH the quantised watch-region pixels of
 *              the frame that triggered it. The novelty and luma gates decided on those
 *              exact pixels, so an offline re-run of the gates against different
 *              thresholds needs precisely these frames and no others.
 *   keyframes  the watch region roughly once a second, so background drift and a
 *              mis-aimed region are visible offline too.
 *
 * NOT recorded: continuous frames. That is Tier-2 video territory, and D19 keeps it a
 * rig-day debugging instrument at most. This file is a signal, not a tape.
 *
 * Lives beside motion.ts rather than inside it because the trigger must not grow a
 * recorder the seam never asked for: motion.ts exposes one optional per-frame callback,
 * and everything here is what the SCREEN chooses to do with it.
 */

import type { MotionEvent, MotionParams } from './motion'
import { GRID_H, GRID_W, ROI_X0, ROI_X1, ROI_Y0, ROI_Y1 } from './motion'

/* A forgotten armed session must not eat the tab. 200k frames is ~110 minutes at 30fps
 * and ~20 MB of rows; past it the trace marks itself truncated and stops growing. */
const MAX_FRAMES = 200_000

/* Base64 in chunks: String.fromCharCode(...whole) overflows the argument limit on a
 * frame worth of bytes, and byte-at-a-time concatenation is quadratic. */
function toBase64(bytes: Uint8Array): string {
  let binary = ''
  const CHUNK = 8192
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK))
  }
  return btoa(binary)
}

function quantise(cells: Float32Array): Uint8Array {
  const out = new Uint8Array(cells.length)
  for (let i = 0; i < cells.length; i += 1) {
    const v = cells[i] as number
    out[i] = v < 0 ? 0 : v > 255 ? 255 : Math.round(v)
  }
  return out
}

type TraceEvent = { t: number; event: MotionEvent; frame: string }
type TraceKeyframe = { t: number; frame: string }

export class MotionTrace {
  private readonly params: MotionParams
  private frames: Array<[number, number, number]> = []
  private events: TraceEvent[] = []
  private keyframes: TraceKeyframe[] = []
  private firstAt: number | null = null
  private lastKeyframeAt = -Infinity
  private truncated = false

  constructor(params: MotionParams) {
    this.params = params
  }

  get frameCount(): number {
    return this.frames.length
  }

  /** One frame, as the trigger's onFrame callback delivers it. `cells` is the sampler's
   *  REUSED buffer — anything kept is quantised into a fresh array here, the same copy
   *  rule the machine itself lives by. */
  record(
    tMs: number,
    d: number,
    luma: number,
    event: MotionEvent | null,
    cells: Float32Array,
  ): void {
    if (this.truncated) return
    if (this.frames.length >= MAX_FRAMES) {
      this.truncated = true
      return
    }
    if (this.firstAt === null) this.firstAt = tMs
    const t = Math.round((tMs - this.firstAt) * 10) / 10
    this.frames.push([t, Math.round(d * 100) / 100, Math.round(luma * 10) / 10])
    if (event !== null) {
      this.events.push({ t, event, frame: toBase64(quantise(cells)) })
    } else if (t - this.lastKeyframeAt >= 1000) {
      this.lastKeyframeAt = t
      this.keyframes.push({ t, frame: toBase64(quantise(cells)) })
    }
  }

  /** The file, self-describing: the thresholds that produced these events travel with
   *  the evidence, so a trace can never be scored against the wrong parameters. */
  toJSON(): string {
    return JSON.stringify({
      version: 1,
      kind: 'pkmnscan-motion-trace',
      recorded_at: new Date().toISOString(),
      params: this.params,
      grid: { w: GRID_W, h: GRID_H, roi: [ROI_X0, ROI_Y0, ROI_X1, ROI_Y1] },
      truncated: this.truncated,
      frames: this.frames,
      events: this.events,
      keyframes: this.keyframes,
    })
  }

  /** Hand the operator the file. A plain <a download> in the owner's own browser —
   *  nothing goes near the capture server, because the trace is a tuning artifact and
   *  the store holds inventory, not diagnostics. */
  download(): void {
    const blob = new Blob([this.toJSON()], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `motion-trace-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }
}
