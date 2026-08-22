/* The JPEG encode, on a thread the idle scheduler cannot starve — the second half of the
 * capture-latency fix recorded on `encodeWorkerRef` in useCamera.ts.
 *
 * Why a worker at all, when OffscreenCanvas.convertToBlob exists on the main thread:
 * Chromium routes toBlob AND main-thread convertToBlob through the same encoder, and that
 * encoder is scheduled as main-thread IDLE work — a capture burst never yields an idle
 * moment, so the encode sits parked until a scheduler timeout forces it through at 1.0 or
 * 2.3 s. Both were measured on this rig on 2026-08-22: a Performance trace of a real burst
 * showed 1.0/2.3/6.9 s inside single encodes while every thread in the process sat idle,
 * and the main-thread convertToBlob variant reproduced the identical timeout clusters. On
 * a worker there is no such scheduler; the encode starts when asked.
 *
 * One canvas, module-level and resized only on change — the same reuse rule as
 * `captureCanvasRef` in useCamera.ts, for the same reason: a fresh ~33 MB backing store
 * per press is the leak that was the first half of this fix.
 */

/* `rotation` is degrees clockwise the frame is turned before encoding — the rig's camera
 * is mounted on its side (useCamera's ROTATION_KEY has the whole story), and rotating
 * here costs nothing extra: the frame is already being drawn once. */
type EncodeJob = { bitmap: ImageBitmap; quality: number; rotation: number }
type EncodeAnswer = { ok: true; blob: Blob } | { ok: false; message: string }

/* `self` typed locally to the two members this file uses. The DOM lib types `self` as
 * Window, and pulling the webworker lib into the program would give every other file a
 * conflicting global scope — a whole-program cost for one module's two calls. */
const scope = self as unknown as {
  onmessage: ((event: MessageEvent<EncodeJob>) => void) | null
  postMessage(message: EncodeAnswer): void
}

let canvas: OffscreenCanvas | null = null

scope.onmessage = (event) => {
  void (async () => {
    const { bitmap, quality, rotation } = event.data
    try {
      /* The 0|90|180|270 invariant lives in useCamera's Rotation type, and this message
       * seam is the one place it is not stated — so it is restated here as a refusal,
       * matching the repo's refuse-rather-than-guess rule. An off-menu value would
       * otherwise draw a diagonal frame into swapped dims: corners clipped, background
       * bands exposed, delivered as a normal-looking JPEG. */
      if (rotation % 90 !== 0) {
        throw new Error(`rotation must be a quarter turn in degrees, not ${rotation}.`)
      }
      /* A quarter turn swaps the output dimensions; the transform turns the frame about
       * the output's centre. Reset-first rather than save/restore, because the canvas is
       * reused across jobs and reset-first is exception-safe by construction: a throw
       * mid-job cannot leak a transform into the next job when the next job never trusts
       * the state it inherits. */
      const swap = rotation % 180 !== 0
      const outWidth = swap ? bitmap.height : bitmap.width
      const outHeight = swap ? bitmap.width : bitmap.height
      if (canvas === null) canvas = new OffscreenCanvas(outWidth, outHeight)
      if (canvas.width !== outWidth) canvas.width = outWidth
      if (canvas.height !== outHeight) canvas.height = outHeight
      const context = canvas.getContext('2d')
      if (context === null) throw new Error('The encode worker got no canvas context.')
      context.setTransform(1, 0, 0, 1, 0, 0)
      context.translate(outWidth / 2, outHeight / 2)
      context.rotate((rotation * Math.PI) / 180)
      context.drawImage(bitmap, -bitmap.width / 2, -bitmap.height / 2)
      const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality })
      scope.postMessage({ ok: true, blob })
    } catch (err) {
      scope.postMessage({
        ok: false,
        message: err instanceof Error ? err.message : String(err),
      })
    } finally {
      /* The bitmap was transferred in, so this side owns it — and a closed bitmap is the
       * difference between a worker that holds one frame and one that accumulates a run's
       * worth of 33 MB frames nothing can reach. */
      bitmap.close()
    }
  })()
}
