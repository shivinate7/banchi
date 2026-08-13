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

  /** The remembered camera is not in the device list. Distinct from `error`, because it
   *  is answerable: the owner picks, or plugs the rig back in. */
  missing: boolean

  /** The server's own copy rules applied to the browser's errors: what happened, and what
   *  to do next. */
  error: string | null

  /** A live track is attached and the element has reported its dimensions. */
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
      return 'That camera is not connected. Check the Cam Link cable and that the camera is awake, then pick a camera.'
    case 'NotReadableError':
    case 'TrackStartError':
      return 'Another application is holding the camera. Quit it — OBS and the Elgato utilities both take exclusive use — then pick the camera again.'
    case 'OverconstrainedError':
    case 'ConstraintNotSatisfiedError':
      return `That camera cannot deliver ${MIN_WIDTH}x${MIN_HEIGHT} or better, which is below what the pipeline needs. Check the camera is in its clean-HDMI output mode, then pick a camera.`
    case 'AbortError':
      return 'The camera stopped responding. Unplug the Cam Link, plug it back in, then pick a camera.'
    default:
      return cause instanceof Error
        ? `The camera did not open: ${cause.message}`
        : 'The camera did not open. Unplug the Cam Link, plug it back in, then pick a camera.'
  }
}

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

  /* Two error sources, kept apart internally and combined on the way out. Enumeration
   * failures survive a devicechange; a stream failure belongs to one deviceId and is
   * cleared when that changes. Writing both into one slot meant a replugged Cam Link
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

    /* The rig is USB and HDMI, so the device list is not static: the Cam Link is unplugged,
     * and a camera body that auto-powers-off mid-box drops the HDMI signal — the failure
     * docs/specs/capture-app.md section 6.2 says to disable in the camera. When it happens
     * anyway this flips `missing` rather than leaving a frozen preview that still looks
     * live. */
    const onDeviceChange = () => {
      void reconcile()
    }
    media.addEventListener('devicechange', onDeviceChange)
    return () => media.removeEventListener('devicechange', onDeviceChange)
  }, [reconcile])

  /* Open the chosen device, attach it, and tear it down again on every change of mind.
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
    const onMetadata = () => {
      if (!cancelled) setReady(true)
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
      if (opened !== null) stopTracks(opened)
    }
  }, [deviceId])

  const selectDevice = useCallback((id: string) => {
    /* Storage first: it is what `reconcile` reads back, so writing state first would leave
     * a devicechange one tick later reverting the choice to the previous camera. */
    writeRememberedDeviceId(id)
    setMissing(false)
    setDeviceId(id)
  }, [])

  const grabFrameJpeg = useCallback(async (): Promise<string> => {
    const video = videoRef.current
    if (video === null) throw new Error('There is no camera preview to capture from.')

    /* The track's own dimensions, never the element's CSS box. Drawing at the displayed
     * size would throw away exactly the resolution the constraints above fought for, and
     * the loss would be invisible — a correctly framed, correctly exposed, quietly
     * useless photograph of a collector number. */
    const width = video.videoWidth
    const height = video.videoHeight
    if (width === 0 || height === 0) {
      throw new Error('The camera has not delivered a frame yet. Wait for the preview, then capture.')
    }

    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (context === null) throw new Error('This browser gave no canvas to capture into.')
    context.drawImage(video, 0, 0, width, height)

    /* toBlob rather than toDataURL. Both produce the same bytes, but toDataURL encodes a
     * 4K frame synchronously on the main thread — a visible stall in the live preview at
     * the moment the next card is being placed, which is the moment the owner is watching
     * it. ImageCapture.takePhoto was the other candidate and was rejected: it is not
     * implemented across browsers, and against a UVC capture card it returns the same
     * video frame anyway. */
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY)
    })
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
      missing,
      error: streamError ?? listError,
      ready,
      grabFrameJpeg,
    }),
    [devices, deviceId, selectDevice, missing, streamError, listError, ready, grabFrameJpeg],
  )
}
