import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { RefObject } from 'react'

/* The camera behind the rig — docs/specs/capture-app.md section 6.1, D13.
 *
 * The hardware is a Sony RX100 VII or A7C over HDMI into an Elgato Cam Link 4K, and the
 * one consequence that shapes every line below is that the Cam Link presents it to the
 * browser as a plain UVC webcam. It is not distinguishable by kind from the laptop's
 * built-in camera — only by its label and its deviceId. That is why there is a picker at
 * all, and it is why `facingMode` appears nowhere in this file: selecting by facing was
 * v1 bug 3, it is banned by name in CLAUDE.md, and against a capture card it does not even
 * have a wrong answer to give.
 */

/* ---- what we ask the track for ----
 *
 * THE MOST CONSEQUENTIAL LINES IN THIS FILE. A browser video track negotiates its own mode
 * and will happily settle on 640x480, which is *below* identify/images.py's 1568px target:
 * every photo would then be worse than the rig can produce, and nothing downstream could
 * tell, because a low-resolution photo of a card is still a photo of a card.
 *
 * The `ideal` is the Cam Link's native 4K mode. The `min` is a hard floor and it is
 * deliberately hard: a device that cannot clear 720p makes the run pointless, so
 * getUserMedia should refuse loudly (OverconstrainedError, surfaced verbatim below) rather
 * than hand back a stream that quietly wastes an afternoon of capture. Rejected: `ideal`
 * alone plus a warning after the fact, which is the same silent-downgrade failure with a
 * label on it.
 *
 * Resolution matters here through the crop, not through the whole card — D13 and
 * docs/specs/capture-app.md section 6.2 correct the simpler argument. geometry/crop.py
 * upscales the collector number to at least 600px and can only enlarge pixels that were
 * really captured, and T1's recorded misses are numerator misreads. Framing the card tight
 * in this field is the other half, and that half is rig setup rather than code.
 */
const IDEAL_WIDTH = 3840
const IDEAL_HEIGHT = 2160
const MIN_WIDTH = 1280
const MIN_HEIGHT = 720

/* identify/images.py's MAX_EDGE. Not imported — nothing crosses the Python/TS boundary —
 * so it is stated once here and read by the picker, which shows the owner when the live
 * signal is under it. A second literal in the picker would be the drift this repo audits
 * its docs for. */
export const PIPELINE_LONG_EDGE = 1568

/* The pipeline re-encodes this frame later, so a cheap first pass compounds two lossy
 * steps on the one image identification depends on. 0.95 rather than the 0.92 default:
 * the difference is a few hundred KB against a 24 MB server ceiling, and the thing being
 * preserved is the JPEG ringing around the collector number's digits. */
const JPEG_QUALITY = 0.95

/* Device-local, and that is the whole justification for storing it here rather than in the
 * one truth D13 names. CLAUDE.md bans localStorage — for *inventory*, whose entire point is
 * that the owner's and Fulfiller's devices agree, and which the capture server owns. A
 * deviceId is the opposite kind of fact: it is meaningless on any other machine and would
 * be actively wrong if shared, since the Fulfiller's laptop has different hardware. Nothing
 * about a card is stored here, and docs/specs/capture-app.md section 9's "no second store
 * in the browser" is about captures, which still go straight to the Mac. */
const REMEMBERED_DEVICE_KEY = 'pkmnscan.capture.deviceId'

export type Camera = {
  /** Attach to a `<video>` that is rendered unconditionally. Gating the element on
   *  `ready` deadlocks: the frames that set `ready` cannot arrive until there is an
   *  element to decode into. */
  videoRef: RefObject<HTMLVideoElement | null>

  devices: MediaDeviceInfo[]

  /** null means nothing is open: a first run with no remembered choice, or a remembered
   *  choice that is not connected. Never a silent stand-in for another camera. */
  deviceId: string | null

  selectDevice(id: string): void

  /** Re-run acquisition for whatever is currently chosen. The only way back from a stream
   *  error: re-picking the same camera in the select is a no-op twice over — a `<select>`
   *  fires no change event for the value it already holds, and the effect that opens the
   *  device is keyed on `deviceId`, which did not change. */
  retry(): void

  /** The remembered camera is not in the device list. Distinct from `error`, because it
   *  is answerable: the owner picks, or plugs the rig back in. */
  missing: boolean

  /** The server's own copy rules applied to the browser's errors: what happened, and what
   *  to do next. */
  error: string | null

  /** A live track is attached and the element has reported its dimensions. Goes false
   *  again when the track ends or mutes — a dead signal leaves the element holding its
   *  last decoded frame, so nothing about the `<video>` says the picture is stale. */
  ready: boolean

  /** JPEG bytes as bare base64 — no `data:` prefix, because the server b64decodes the
   *  string it is handed. */
  grabFrameJpeg(): Promise<string>
}

function videoConstraints(deviceId: string): MediaStreamConstraints {
  return {
    audio: false,
    video: {
      /* `exact`, never a bare string. A bare deviceId is a *preference*: the browser is
       * free to open a different camera when it cannot honour it, which is precisely the
       * silent wrong-lens failure the picker exists to prevent. `exact` turns that into an
       * OverconstrainedError the owner can see. */
      deviceId: { exact: deviceId },
      width: { ideal: IDEAL_WIDTH, min: MIN_WIDTH },
      height: { ideal: IDEAL_HEIGHT, min: MIN_HEIGHT },
    },
  }
}

function stopTracks(stream: MediaStream): void {
  for (const track of stream.getTracks()) track.stop()
}

/* DOMException is the usual carrier, but OverconstrainedError is its own interface in some
 * engines and not a DOMException at all — reading `.name` structurally catches both. */
function errorName(cause: unknown): string {
  if (typeof cause !== 'object' || cause === null) return ''
  const named: { name?: unknown } = cause
  return typeof named.name === 'string' ? named.name : ''
}

function describeCameraError(cause: unknown): string {
  switch (errorName(cause)) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'Camera permission was refused. Allow the camera for this site in the browser settings, then reload.'
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return 'That camera is not connected. Check the Cam Link cable and that the camera is awake, then reopen the camera below.'
    case 'NotReadableError':
    case 'TrackStartError':
      return 'Another application is holding the camera. Quit it — OBS and the Elgato utilities both take exclusive use — then reopen the camera below.'
    case 'OverconstrainedError':
    case 'ConstraintNotSatisfiedError':
      return `That camera cannot deliver ${MIN_WIDTH}x${MIN_HEIGHT} or better, which is below what the pipeline needs. Check the camera is in its clean-HDMI output mode, then reopen the camera below.`
    case 'AbortError':
      return 'The camera stopped responding. Unplug the Cam Link, plug it back in, then reopen the camera below.'
    default:
      return cause instanceof Error
        ? `The camera did not open: ${cause.message}`
        : 'The camera did not open. Unplug the Cam Link, plug it back in, then reopen the camera below.'
  }
}

/* ---- the signal dying under a camera that is still there ----
 *
 * docs/specs/capture-app.md section 6.2's last rig setting: a body that sleeps mid-box drops
 * the HDMI signal. The Cam Link stays plugged in and stays enumerated, so `devicechange`
 * never fires and nothing above notices. What does change is the track — it mutes when the
 * source stops delivering and ends when it goes away — and until those were listened for,
 * `ready` had exactly one thing that cleared it, which was choosing a different device.
 *
 * The cost of not listening is the reason these three messages exist at all. The `<video>`
 * keeps its last decoded frame with `videoWidth` intact, so every subsequent capture
 * succeeds against a photograph of the previous card: the feeder keeps feeding, the server
 * keeps allocating positions, and a box fills with one image at twenty real positions. It
 * surfaces at identification, in a paid Batch request, after the cards are boxed. That is
 * precisely the quiet failure section 5.5 stops the run to prevent, so it stops the run.
 *
 * Same what-happened / what-to-do-next shape as describeCameraError, and separate strings
 * for mute and end because the remedies differ: a muted track is a sleeping camera, an ended
 * one is a source that went away.
 *
 * Honest limit, recorded so a later session does not read this as total coverage: it catches
 * what the platform reports. A capture card that answers a dead HDMI input with black frames
 * rather than by muting its track raises no event at all, and nothing here would fire. That
 * is a Gate B rig finding — check what the Cam Link does with the camera switched off — and
 * the answer is a frame-content check, not another listener.
 */
const SIGNAL_MUTED_MESSAGE =
  'The camera stopped sending video. The capture card is still connected, so the camera itself has slept or lost its HDMI output — wake it and disable auto power off, then reopen the camera below.'

const SIGNAL_ENDED_MESSAGE =
  'The camera closed while it was open. Check the Cam Link cable and that the camera is awake, then reopen the camera below.'

/* Thrown on the capture path rather than shown on the preview, so it names the one fact the
 * operator needs first: nothing was recorded. CaptureScreen turns it into the halt. */
const SIGNAL_DEAD_CAPTURE_MESSAGE =
  'The camera has stopped sending frames, so no photo was taken. Wake the camera, then reopen it below before capturing again.'

/* getUserMedia lives on an insecure origin's navigator as undefined, not as a function
 * that throws. The DOM types do not model that, and it is not hypothetical here:
 * docs/specs/capture-app.md section 4 leaves the base URL configurable so the Fulfiller's
 * device can reach the Mac by address later, and http://192.168.x.x is not a secure
 * context while http://localhost is. */
const INSECURE_CONTEXT_MESSAGE =
  'This browser exposes no camera. The camera API needs a secure context — open the app at http://localhost, not at an IP address.'

function mediaDevices(): MediaDevices | undefined {
  const media: MediaDevices | undefined = navigator.mediaDevices
  return media
}

async function listVideoInputs(media: MediaDevices): Promise<MediaDeviceInfo[]> {
  const all = await media.enumerateDevices()
  return all.filter((device) => device.kind === 'videoinput')
}

/* Labels are empty strings until camera permission has been granted once, and a list of
 * indistinguishable blanks is not a picker — against a Cam Link the label is the *only*
 * thing that separates the rig from the built-in camera.
 *
 * This opens whatever camera the browser picks, for as long as it takes to be granted, and
 * stops it before a frame is read. It does not violate the no-fallback rule above: that
 * rule is about which lens a photograph comes through, and no photograph comes from this
 * stream. Rejected: enumerating without labels and showing the raw deviceIds, which asks
 * the owner to choose between two 64-character hashes. */
async function revealLabels(media: MediaDevices): Promise<void> {
  const probe = await media.getUserMedia({ video: true })
  stopTracks(probe)
}

/* Storage can throw outright — Safari private browsing, a profile with site data disabled.
 * Losing the remembered camera costs one click per session; letting the exception out
 * would white-screen the one view the owner spends hours in. */
function readRememberedDeviceId(): string | null {
  try {
    const stored = window.localStorage.getItem(REMEMBERED_DEVICE_KEY)
    return stored === null || stored === '' ? null : stored
  } catch {
    return null
  }
}

function writeRememberedDeviceId(id: string): void {
  try {
    window.localStorage.setItem(REMEMBERED_DEVICE_KEY, id)
  } catch {
    /* Ignored on purpose. See readRememberedDeviceId. */
  }
}

async function blobToBase64(blob: Blob): Promise<string> {
  const encoded = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('The captured frame could not be read.'))
    reader.onload = () => {
      const result = reader.result
      if (typeof result !== 'string') {
        reject(new Error('The captured frame did not encode.'))
        return
      }
      resolve(result)
    }
    reader.readAsDataURL(blob)
  })

  /* The server decodes with `validate=True`, which rejects anything outside the base64
   * alphabet — so the payload must be the bare string with no prefix and no line breaks.
   * readAsDataURL emits exactly one comma, between the media type and the data, and wraps
   * nothing. Slicing at the first one is the whole of the contract. */
  const comma = encoded.indexOf(',')
  if (comma === -1) throw new Error('The captured frame did not encode as base64.')
  return encoded.slice(comma + 1)
}

export function useCamera(): Camera {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])
  const [deviceId, setDeviceId] = useState<string | null>(null)
  const [missing, setMissing] = useState(false)
  const [ready, setReady] = useState(false)

  /* Bumped by `retry`, and in the acquisition effect's dependencies purely so that bumping
   * it re-runs acquisition. A counter rather than a boolean, because a boolean has to be
   * cleared again and the clear is another render that re-runs the effect a second time.
   *
   * This is what makes a stream error answerable at all: every other input to that effect
   * is unchanged when the owner wants to try the same camera again. */
  const [attempt, setAttempt] = useState(0)

  /* The live video track, for the capture path. A ref rather than state because
   * `grabFrameJpeg` must stay identity-stable — it is in CaptureScreen's `doCapture`
   * dependencies, and behind that sits the trigger seam, which at Gate C holds phase across
   * a motion state machine. Rebuilding the callback on every track change would tear that
   * down mid-card. */
  const trackRef = useRef<MediaStreamTrack | null>(null)

  /* ONE canvas, reused for every capture this session — never one per press.
   *
   * A fresh 4K canvas holds ~33 MB of raster backing store the JS collector cannot see:
   * to it the element is a few bytes, so nothing reclaims the real memory until the
   * browser is forced to, synchronously, mid-capture. Measured on this rig's own Mac,
   * 2026-08-21: a burst of captures runs at ~100 ms each until the canvas budget fills,
   * then every press costs 1–3 s while the browser digs itself out — a fast-then-crawl
   * rhythm the operator reads as a slow button — and a long enough run wedges the
   * image-decode service for every page in the browser. Reusing one canvas measured
   * stable across the same run. Same failure shape as v1 bug 4, Web Audio contexts
   * created per sound and never closed: a per-use resource that nothing releases.
   *
   * Fallback-only as of 2026-08-22: the real capture path encodes in the worker below
   * and touches no main-thread canvas at all. This ref serves the arm for an engine
   * with no OffscreenCanvas or no Worker. */
  const captureCanvasRef = useRef<HTMLCanvasElement | null>(null)

  /* The JPEG encoder lives on a worker thread, and the reason is a scheduler, not a CPU.
   *
   * `toBlob` — and, it turned out, main-thread `convertToBlob` — schedule their encode as
   * main-thread IDLE work, and a capture burst is precisely a main thread with no idle:
   * key events, a live 4K preview and React renders every few hundred ms. A Performance
   * trace of a real burst (2026-08-22) showed 1.0 s, 2.3 s and once 6.9 s inside single
   * encodes while every thread in the process sat empty — the 1.0/2.3 clusters are
   * Chromium's own idle-task start and completion timeouts, which is as close to a
   * signed confession as a scheduler gives. Switching to convertToBlob on a main-thread
   * OffscreenCanvas was tried first and reproduced the identical clusters, which is how
   * the scheduler was convicted rather than the API. On a worker there is no idle
   * scheduler; the encode starts when asked. See encode-worker.ts for the other half.
   *
   * Created lazily on the first capture — StrictMode's double mount therefore never
   * builds one — and terminated on unmount below. */
  const encodeWorkerRef = useRef<Worker | null>(null)

  useEffect(
    () => () => {
      encodeWorkerRef.current?.terminate()
      encodeWorkerRef.current = null
    },
    [],
  )

  /* Two error sources, kept apart internally and combined on the way out. Enumeration
   * failures survive a devicechange; a stream failure belongs to one acquisition and is
   * cleared by the next one, whether that is a different device or `retry` re-opening the
   * same one. Writing both into one slot meant a replugged Cam Link
   * wiping a real "another application is holding the camera" message, or the reverse. */
  const [listError, setListError] = useState<string | null>(null)
  const [streamError, setStreamError] = useState<string | null>(null)

  /* Enumerate, then reconcile against what is remembered.
   *
   * localStorage is the single source of the chosen id and `deviceId` mirrors it, which is
   * what lets this run from a devicechange event with no dependency on current state and
   * therefore no stale closure. The alternative — a ref shadowing deviceId — is one more
   * thing to keep in step for no gain. */
  const reconcile = useCallback(async () => {
    const media = mediaDevices()
    if (media === undefined) {
      setListError(INSECURE_CONTEXT_MESSAGE)
      return
    }

    let found: MediaDeviceInfo[]
    try {
      found = await listVideoInputs(media)
      if (found.length > 0 && found.every((device) => device.label === '')) {
        await revealLabels(media)
        found = await listVideoInputs(media)
      }
    } catch (cause) {
      setListError(describeCameraError(cause))
      return
    }

    setDevices(found)
    setListError(
      found.length === 0
        ? 'No camera is connected. Plug in the Cam Link and switch the camera on — the list refreshes on its own.'
        : null,
    )

    const remembered = readRememberedDeviceId()
    if (remembered === null) {
      /* First run on this machine. Nothing is opened and nothing is guessed: picking once
       * is the price of never photographing a box through the laptop's lens because it
       * happened to enumerate first. Silent re-selection starts from the next session. */
      setMissing(false)
      return
    }

    if (found.some((device) => device.deviceId === remembered)) {
      setMissing(false)
      setDeviceId(remembered)
      return
    }

    /* The remembered camera is gone. Say so and open nothing — docs/specs/capture-app.md
     * section 6.1: silently grabbing a different input is how a box gets photographed
     * through the wrong lens. */
    setMissing(true)
    setDeviceId(null)
  }, [])

  useEffect(() => {
    void reconcile()

    const media = mediaDevices()
    if (media === undefined) return

    /* The rig is USB, so the device list is not static: unplug the Cam Link and this flips
     * `missing` rather than leaving a frozen preview that still looks live.
     *
     * It covers the unplug and nothing else, which is worth stating because the wording here
     * used to claim the sleeping-camera case too and that claim is what made the frozen
     * preview invisible. A body that auto-powers-off mid-box — docs/specs/capture-app.md
     * section 6.2 — drops the HDMI signal behind a Cam Link that stays plugged in and stays
     * enumerated, so `devicechange` never fires. That failure is caught one level down, on
     * the track's own events; see SIGNAL_MUTED_MESSAGE. */
    const onDeviceChange = () => {
      void reconcile()
    }
    media.addEventListener('devicechange', onDeviceChange)
    return () => media.removeEventListener('devicechange', onDeviceChange)
  }, [reconcile])

  /* Open the chosen device, attach it, and tear it down again on every change of mind — and
   * on every `retry`, which is what `attempt` is doing in the dependencies below.
   *
   * The `cancelled` flag is not defensive programming: StrictMode mounts, unmounts and
   * remounts, so a stream that resolves after the cleanup has run must stop itself. Left
   * out, the first stream stays live with no element and no reference — the camera's tally
   * light stays on and the device stays busy for the next getUserMedia. */
  useEffect(() => {
    setStreamError(null)
    setReady(false)
    if (deviceId === null) return

    const media = mediaDevices()
    if (media === undefined) {
      setStreamError(INSECURE_CONTEXT_MESSAGE)
      return
    }

    let cancelled = false
    let opened: MediaStream | null = null
    let attached: HTMLVideoElement | null = null
    let watched: MediaStreamTrack | null = null
    const onMetadata = () => {
      if (!cancelled) setReady(true)
    }

    /* The three track events, and the only things besides a device change that move `ready`.
     *
     * `ended` and `mute` both clear it, because both mean the next frame drawn from this
     * element is the previous card. `unmute` restores rather than staying dead: a camera
     * that wakes up is the common case after the owner acts on the message, and demanding a
     * reload to recover from a recoverable state is how an operator learns to ignore the
     * message. `ready` is recomputed from the element on the way back rather than assumed
     * true — the track can unmute before the element has metadata again. */
    const onTrackEnded = () => {
      if (cancelled) return
      setReady(false)
      setStreamError(SIGNAL_ENDED_MESSAGE)
    }
    const onTrackMuted = () => {
      if (cancelled) return
      setReady(false)
      setStreamError(SIGNAL_MUTED_MESSAGE)
    }
    const onTrackUnmuted = () => {
      if (cancelled) return
      setStreamError(null)
      const video = videoRef.current
      setReady(video !== null && video.readyState >= HTMLMediaElement.HAVE_METADATA)
    }

    void (async () => {
      let stream: MediaStream
      try {
        stream = await media.getUserMedia(videoConstraints(deviceId))
      } catch (cause) {
        if (!cancelled) setStreamError(describeCameraError(cause))
        return
      }
      if (cancelled) {
        stopTracks(stream)
        return
      }
      const video = videoRef.current
      if (video === null) {
        /* Only reachable if the `<video>` is rendered conditionally, which the Camera type
         * tells its consumer not to do. Loud rather than a preview that never arrives —
         * and the track is stopped on the way out rather than left to the cleanup, because
         * this path stays mounted: the camera would otherwise hold its tally light on and
         * the device busy for as long as the owner reads the message. */
        stopTracks(stream)
        setStreamError('The camera opened with nowhere to show it. Reload the page.')
        return
      }
      opened = stream
      attached = video
      video.srcObject = stream
      video.addEventListener('loadedmetadata', onMetadata)
      if (video.readyState >= HTMLMediaElement.HAVE_METADATA) onMetadata()

      /* One video track, always — `videoConstraints` asks for one device and no audio. The
       * `?? null` is for the shape of the array type rather than for a case that happens. */
      watched = stream.getVideoTracks()[0] ?? null
      trackRef.current = watched
      if (watched !== null) {
        watched.addEventListener('ended', onTrackEnded)
        watched.addEventListener('mute', onTrackMuted)
        watched.addEventListener('unmute', onTrackUnmuted)
        /* Already muted at the moment it opened: the camera was asleep before the app was.
         * Checked because the event fired before this line and will not fire again, and the
         * alternative is a preview that waits forever with nothing on screen saying why. If
         * an engine reports a momentary mute at open, `unmute` clears this within a frame —
         * a message that self-corrects, against a wait that does not. */
        if (watched.muted) onTrackMuted()
      }

      /* A rejected play() is normal here — swapping srcObject aborts the pending one — and
       * an unhandled rejection in the console is noise on the screen where real errors
       * need to be visible. The element carries `autoPlay`; this is the belt. */
      void video.play().catch(() => {})
    })()

    return () => {
      cancelled = true
      if (attached !== null) {
        attached.removeEventListener('loadedmetadata', onMetadata)
        attached.srcObject = null
      }
      if (watched !== null) {
        watched.removeEventListener('ended', onTrackEnded)
        watched.removeEventListener('mute', onTrackMuted)
        watched.removeEventListener('unmute', onTrackUnmuted)
      }
      /* Cleared unconditionally, not only when it still points at this track. The next
       * acquisition assigns it after `getUserMedia` resolves, and until then there is no
       * camera open — so a capture fired in that window has to be refused rather than drawn
       * from whatever was attached last. */
      trackRef.current = null
      if (opened !== null) stopTracks(opened)
    }
  }, [deviceId, attempt])

  const selectDevice = useCallback((id: string) => {
    /* Storage first: it is what `reconcile` reads back, so writing state first would leave
     * a devicechange one tick later reverting the choice to the previous camera. */
    writeRememberedDeviceId(id)
    setMissing(false)
    setDeviceId(id)
  }, [])

  /* The way back from a stream error, and the reason it cannot be "pick the camera again".
   *
   * That is a no-op twice over: a `<select>` fires no change event for the value it already
   * holds, so `selectDevice` is never called, and even called it would set `deviceId` to
   * what it already is, which re-runs nothing. Until this existed, every message ending in
   * "then pick a camera" was instructing the owner to press a button that does nothing, and
   * a reload was the only real remedy.
   *
   * Both halves are needed, and they answer different states. `reconcile` re-enumerates, so
   * a Cam Link that came back is seen and `missing` clears; bumping `attempt` re-opens the
   * device that is already chosen, which is the case reconcile cannot help with because
   * nothing about the device list changed. Ordering does not matter — reconcile is async and
   * settles on the same `deviceId`, which React bails out of, leaving exactly one
   * re-acquisition from the bump. */
  const retry = useCallback(() => {
    setAttempt((count) => count + 1)
    void reconcile()
  }, [reconcile])

  const grabFrameJpeg = useCallback(async (): Promise<string> => {
    const video = videoRef.current
    if (video === null) throw new Error('There is no camera preview to capture from.')

    /* Belt and braces with the `ready` gate above, and the duplication is deliberate: the
     * cost of getting this wrong is a box of cards recorded against a photograph of the
     * first one. `ready` guards the button, this guards the frame, and the trigger seam
     * means the two are not the same thing — at Gate C a motion state machine fires captures
     * without a button to disable.
     *
     * The zero-dimension check below cannot do this job. A dead track leaves the element
     * holding its last decoded frame with `videoWidth` intact, which is exactly why the
     * check passed and `drawImage` copied a stale card. */
    const track = trackRef.current
    if (track === null) {
      throw new Error('No camera is open, so no photo was taken. Pick a camera, then capture.')
    }
    if (track.readyState !== 'live' || track.muted) {
      throw new Error(SIGNAL_DEAD_CAPTURE_MESSAGE)
    }

    /* The track's own dimensions, never the element's CSS box. Drawing at the displayed
     * size would throw away exactly the resolution the constraints above fought for, and
     * the loss would be invisible — a correctly framed, correctly exposed, quietly
     * useless photograph of a collector number. */
    /* The readyState clause is what makes canvas reuse safe, so it may not be removed
     * while the reuse below stands. Dimensions are populated at HAVE_METADATA, but the
     * spec makes drawImage a silent no-op until a frame has actually decoded — and a
     * no-op draw over a reused canvas would encode the PREVIOUS card's pixels as this
     * card's photo, the exact silent failure the SIGNAL_MUTED machinery above exists to
     * prevent. The window is real and self-made: `onTrackUnmuted` sets `ready` at
     * HAVE_METADATA by its own admission, and a camera waking from the halt is the one
     * moment the operator is pressing C on instruction. Before reuse this window
     * produced an all-black JPEG — loud in the Last-capture panel; the guard upgrades
     * both cases to a refusal that names the remedy. */
    const width = video.videoWidth
    const height = video.videoHeight
    if (
      width === 0 ||
      height === 0 ||
      video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA
    ) {
      throw new Error('The camera has not delivered a frame yet. Wait for the preview, then capture.')
    }

    /* Two arms, the same JPEG bytes at the same quality; what differs is which thread
     * runs the encoder, and that difference is the whole story on encodeWorkerRef. The
     * worker arm is the real path: the frame crosses as a transferred ImageBitmap and
     * comes back as a Blob, and no main-thread canvas exists at all. The element-canvas
     * arm is the fallback for an engine with no OffscreenCanvas or no Worker, and it
     * keeps the old idle-scheduled toBlob cost: slow under a busy main thread, correct
     * always. toDataURL remains rejected in both arms — it encodes synchronously on the
     * main thread, a visible stall in the live preview at the moment the next card is
     * being placed. ImageCapture.takePhoto remains rejected too: not implemented across
     * browsers, and against a UVC capture card it returns the same video frame anyway. */
    let blob: Blob | null
    if (typeof OffscreenCanvas !== 'undefined' && typeof Worker !== 'undefined') {
      const worker =
        encodeWorkerRef.current ??
        new Worker(new URL('./encode-worker.ts', import.meta.url), { type: 'module' })
      encodeWorkerRef.current = worker
      /* The element holds a decoded frame — the readyState guard above proved it — so
       * createImageBitmap resolves against exactly that frame, and the transfer list
       * hands it across without a copy. One job in flight at a time is CaptureScreen's
       * busyRef guarantee, which is what makes reassigning onmessage per call safe. */
      const bitmap = await createImageBitmap(video)
      blob = await new Promise<Blob>((resolve, reject) => {
        worker.onmessage = (
          event: MessageEvent<{ ok: true; blob: Blob } | { ok: false; message: string }>,
        ) => {
          if (event.data.ok) resolve(event.data.blob)
          else reject(new Error(event.data.message))
        }
        worker.onerror = () => {
          reject(new Error('The frame could not be encoded. Reload the page, then capture again.'))
        }
        worker.postMessage({ bitmap, quality: JPEG_QUALITY }, [bitmap])
      })
    } else {
      /* See captureCanvasRef above for why this is one canvas and never a fresh one per
       * press. Dimensions are assigned only when they differ: assigning a canvas
       * dimension clears the bitmap and resets context state even to an equal value, and
       * may reallocate the one thing the ref exists to keep. Stale pixels from the
       * previous card need no clearing — the frame is opaque, so drawImage overwrites
       * every pixel at these exact dimensions — but only because a frame is guaranteed
       * decoded: that is the readyState guard above, without which drawImage no-ops and
       * the previous card is re-encoded. */
      const canvas = captureCanvasRef.current ?? document.createElement('canvas')
      captureCanvasRef.current = canvas
      if (canvas.width !== width) canvas.width = width
      if (canvas.height !== height) canvas.height = height
      const context = canvas.getContext('2d')
      if (context === null) throw new Error('This browser gave no canvas to capture into.')
      context.drawImage(video, 0, 0, width, height)
      blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY)
      })
    }
    if (blob === null) throw new Error('The frame did not encode as JPEG.')

    return await blobToBase64(blob)
  }, [])

  /* Memoised because a consumer will reasonably put `camera` in a dependency array, and an
   * object rebuilt every render turns that into an effect that re-runs on every render. */
  return useMemo(
    () => ({
      videoRef,
      devices,
      deviceId,
      selectDevice,
      retry,
      missing,
      error: streamError ?? listError,
      ready,
      grabFrameJpeg,
    }),
    [
      devices,
      deviceId,
      selectDevice,
      retry,
      missing,
      streamError,
      listError,
      ready,
      grabFrameJpeg,
    ],
  )
}
