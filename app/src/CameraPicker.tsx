import { useEffect, useState } from 'react'
import type { Camera } from './useCamera'
import { PIPELINE_LONG_EDGE, ROTATIONS } from './useCamera'
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

      {/* Which way the stored photo is turned, in degrees clockwise. The rig's camera is
          mounted on its side so a portrait card fills the field — D13's frame-tight rule
          done properly — and the Cam Link reports the sensor's landscape frame regardless,
          so without this every stored photo holds a sideways card, which is what sent 45
          of the first real run's 53 cards to the review queue misread. The live preview is
          deliberately left as the camera sends it; the Last-capture panel shows the stored
          photo, so one capture confirms the choice. Chips rather than a second select:
          four values, one glance, and the active one reads without opening anything. */}
      <p className="camera-picker-label" id="camera-picker-rotation-label">
        Photo rotation
      </p>
      <div
        className="camera-picker-rotation"
        role="group"
        aria-labelledby="camera-picker-rotation-label"
      >
        {ROTATIONS.map((value) => (
          <button
            key={value}
            type="button"
            className="camera-picker-rotation-chip"
            aria-pressed={value === camera.rotation}
            onClick={() => camera.setRotation(value)}
          >
            {value}°
          </button>
        ))}
      </div>

      {/* Accent as outline and text, never as fill. docs/DESIGN.md: the solid fill means
          there is exactly one thing to do, and a screen with two answers gets none. Every
          notice below leaves the owner a choice — pick a different camera, reopen this one,
          or go fix the rig — so all of them are drawn at the light weight, and so is the
          control at the bottom. */}
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

      {/* Every message above ends by telling the owner to act on the rig and come back, and
          until this control existed there was nothing to come back to: the select fires no
          change event for the value it already holds, and re-picking the same camera changed
          no state, so a sleeping camera or a busy capture card could only be answered with a
          page reload. `retry` re-enumerates and re-opens.

          Shown only when something is wrong. A permanently visible control to reopen a
          working camera is an invitation to drop the stream mid-box, and it would sit at the
          same weight as the choice the owner actually came here to make.

          A plain button rather than PullConfirm: that component carries the solid accent
          fill, which docs/DESIGN.md reserves for a screen with exactly one thing to do. This
          screen offers at least two — reopen this camera, or pick a different one from the
          select above — so it takes the same outline weight as the notices it answers. */}
      {camera.missing || camera.error !== null || underTarget ? (
        <button className="camera-picker-retry" type="button" onClick={camera.retry}>
          Reopen the camera
        </button>
      ) : null}
    </section>
  )
}
