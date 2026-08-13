import { useEffect, useState } from 'react'
import type { Camera } from './useCamera'
import { PIPELINE_LONG_EDGE } from './useCamera'
import './CameraPicker.css'

/* The device picker — docs/specs/capture-app.md section 6.1, D13.
 *
 * A requirement rather than a nicety, and the reason is the hardware: the Cam Link presents
 * the rig's camera as a plain UVC webcam, so nothing but the label separates it from the
 * laptop's built-in one. There is no facing hint to select on and never was — v1 bug 3.
 *
 * Owner-side chrome, used once and then silent for the rest of the machine's life, so it is
 * small and quiet by design. Not a Fulfillment screen: none of docs/DESIGN.md's floors
 * (20px body, 32px positions, 44px targets) govern here, and applying them anyway would put
 * a control the owner touches monthly at the same weight as the card in front of him.
 */

type Signal = { width: number; height: number }

export function CameraPicker({ camera }: { camera: Camera }) {
  /* What the track actually negotiated, which is the one number that makes this whole
   * screen honest. useCamera asks for 4K with a 720p floor, but a constraint is a request:
   * showing the result is how the owner finds out that today's stream came up short before
   * a box has been shot through it rather than after. Read from the element rather than
   * from useCamera because the Camera type is pinned and shared with other work in flight;
   * the listeners below are the same ones the browser fires at the hook. */
  const [signal, setSignal] = useState<Signal | null>(null)

  useEffect(() => {
    const video = camera.videoRef.current
    if (video === null) {
      setSignal(null)
      return
    }

    const read = () => {
      /* Zero until the first frame is decoded, and zero again after a teardown. Reporting
       * "0 x 0" as a resolution would be worse than reporting nothing. */
      if (video.videoWidth === 0 || video.videoHeight === 0) {
        setSignal(null)
        return
      }
      setSignal({ width: video.videoWidth, height: video.videoHeight })
    }

    read()
    video.addEventListener('loadedmetadata', read)
    /* `resize` on a video element is an intrinsic-dimension change, not a layout one: it
     * fires when the HDMI source switches mode mid-session, which is exactly the case a
     * one-shot read at open would miss. */
    video.addEventListener('resize', read)
    return () => {
      video.removeEventListener('loadedmetadata', read)
      video.removeEventListener('resize', read)
    }
  }, [camera.videoRef, camera.deviceId, camera.ready])

  const underTarget = signal !== null && Math.max(signal.width, signal.height) < PIPELINE_LONG_EDGE

  return (
    <section className="camera-picker" aria-label="Camera">
      <label className="camera-picker-label" htmlFor="camera-picker-select">
        Camera
      </label>

      {/* A native select, not the list of rows the review queue uses. Rows are the right
          shape for a choice the owner makes hundreds of times with a photo to compare
          against; this is one choice, made once, between strings. The select also collapses
          to a single line, which matters because every pixel it takes is a pixel off the
          live preview beside it. */}
      <select
        id="camera-picker-select"
        className="camera-picker-select"
        value={camera.deviceId ?? ''}
        disabled={camera.devices.length === 0}
        onChange={(event) => {
          const chosen = event.target.value
          if (chosen !== '') camera.selectDevice(chosen)
        }}
      >
        <option value="" disabled>
          {camera.devices.length === 0 ? 'No cameras found' : 'Pick a camera'}
        </option>
        {camera.devices.map((device, position) => (
          <option key={device.deviceId} value={device.deviceId}>
            {/* Labels are blank until camera permission has been granted. useCamera asks
                for it before enumerating, so a blank here means permission was refused —
                the numbered fallback keeps the list usable rather than showing a row of
                64-character deviceIds. */}
            {device.label === '' ? `Camera ${position + 1}` : device.label}
          </option>
        ))}
      </select>

      {/* Accent as outline and text, never as fill. docs/DESIGN.md: the solid fill means
          there is exactly one thing to do, and a screen with two answers gets none. Both
          notices below leave the owner a choice — pick a different camera, or go fix the
          rig — so both are drawn at the light weight. */}
      {camera.missing ? (
        <p className="camera-picker-notice">
          The remembered camera is not connected. Check the Cam Link and that the camera is
          awake, or pick a camera above. Nothing is open until you do.
        </p>
      ) : null}

      {camera.error === null ? null : <p className="camera-picker-notice">{camera.error}</p>}

      {/* Mono carries every number in the product — docs/DESIGN.md, and a stream's
          dimensions are metadata by any reading of that rule. */}
      {signal === null ? null : (
        <p className="camera-picker-signal" data-under-target={underTarget ? '' : undefined}>
          {signal.width} &times; {signal.height}
        </p>
      )}

      {underTarget ? (
        <p className="camera-picker-notice">
          This stream is below the {PIPELINE_LONG_EDGE}px the pipeline works from, so every
          photo will be worse than the rig can produce. Check the camera is in its clean-HDMI
          output mode and that nothing else is holding the capture card.
        </p>
      ) : null}
    </section>
  )
}
