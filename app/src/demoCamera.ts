/**
 * A camera for a page that has none — the viewfinder, frozen, for the published demo.
 *
 * WHY A REAL `MediaStream` AND NOT A PLACEHOLDER `<img>`. `CaptureScreen.tsx` is 3,255 lines
 * and gates on `camera.ready` in about ten places — the trigger arming, the capture button,
 * the device notice, the stage's own `data-live`. Swapping the `<video>` for a picture would
 * mean patching every one of those and would leave the screen drawing a state the real app
 * never has. A canvas can produce an actual `MediaStream`, so instead the demo hands the hook
 * a stream and NOTHING above it changes: `ready` becomes true the ordinary way, every gate
 * opens the ordinary way, and the screen is the screen.
 *
 * WHAT IT SHOWS IS ONE OF THE DEMO'S OWN PHOTOGRAPHS, which is the same picture the review
 * queue and the inventory walk draw. A viewer who presses *Start the camera* sees the rig's
 * own framing — a card on the stand under the lamp — rather than a grey rectangle.
 *
 * IT DELIBERATELY NEVER MOVES. The motion trigger fires on the difference between frames
 * (D81, D84), so a stream of identical frames arms, watches and never captures — which is
 * the honest outcome, because a capture would need a disk to write a photograph to. The
 * trigger's tuning panel, its thresholds and its arming are all live and inspectable; only
 * the thing that would write is absent, and the demo already refuses `POST /capture` by name.
 *
 * NOT IN THE PRODUCTION BUNDLE: `useCamera.ts` reaches this through a dynamic `import()`
 * inside `if (IS_DEMO)`, which folds to `false` at build time in every ordinary build.
 */

/* Landscape, because that is what the rig hands the browser. D13: the Cam Link presents the
 * camera as a plain UVC webcam and delivers a LANDSCAPE frame however the camera is
 * physically mounted, which is exactly why `useCamera` carries a rotation at all. Drawing a
 * portrait card into a landscape frame and letting the app's own rotation stand it back up
 * reproduces the real path rather than short-circuiting it. */
const FRAME_W = 1280
const FRAME_H = 720

/* Enough to keep a `<video>` fed and its `readyState` past HAVE_METADATA. The frames are
 * identical, so this costs nothing to encode and produces no motion. */
const FPS = 8

/** The fake device the picker offers. One, named for what it is. */
export function demoDevices(): MediaDeviceInfo[] {
  const device = {
    deviceId: 'demo-camera',
    groupId: 'demo',
    kind: 'videoinput' as const,
    label: 'Demo camera (frozen frame)',
    toJSON() {
      return this
    },
  }
  return [device as MediaDeviceInfo]
}

function loadFrame(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => resolve(null)
    image.src = src
  })
}

/**
 * A stream carrying one of the demo's photographs, forever.
 *
 * The canvas is redrawn on a timer rather than captured once: `captureStream` emits a frame
 * when the surface changes, and a canvas painted a single time can leave a `<video>` waiting
 * on metadata that never arrives. Redrawing the same pixels is the cheapest way to keep the
 * track live, and it still produces no motion for the trigger to see.
 */
export async function demoStream(): Promise<MediaStream> {
  const canvas = document.createElement('canvas')
  canvas.width = FRAME_W
  canvas.height = FRAME_H
  const paint = canvas.getContext('2d')
  if (paint === null) throw new Error('demo camera: no 2d context')

  const frame = await loadFrame(`${import.meta.env.BASE_URL}demo/photos/1/1.jpg`)

  const draw = () => {
    paint.fillStyle = '#141418'
    paint.fillRect(0, 0, FRAME_W, FRAME_H)
    if (frame === null) return
    /* Rotated a quarter turn so the portrait photograph sits in the landscape frame the way
       a card sits in front of a side-mounted camera. The screen's own rotation stands it
       back up, which is the path a real frame takes. */
    const scale = FRAME_W / frame.height
    const w = frame.height * scale
    const h = frame.width * scale
    paint.save()
    paint.translate(FRAME_W / 2, FRAME_H / 2)
    paint.rotate(-Math.PI / 2)
    paint.drawImage(frame, -h / 2, -w / 2, h, w)
    paint.restore()
  }

  draw()
  const stream = canvas.captureStream(FPS)
  const timer = window.setInterval(draw, 1000 / FPS)
  /* Cleared when the track is stopped, which is what `useCamera`'s teardown does — otherwise
     the interval outlives the screen and paints for the rest of the session. */
  for (const track of stream.getVideoTracks()) {
    const stop = track.stop.bind(track)
    track.stop = () => {
      window.clearInterval(timer)
      stop()
    }
  }
  return stream
}
