"""The card's box from a fine-tuned D-FINE-N model on onnxruntime (D125). `locate_card` is the one call.

THE MODEL ANSWERS FIRST, `detect_card` ANSWERS WHEN IT CANNOT. The crop preview asks
`locate_card`. A missing model file, a missing onnxruntime, a score under `MIN_SCORE` or any
error at all returns `detect_card`'s answer instead. That fallback is the SAFETY PATH and it
is today's behaviour, so a machine without the model is exactly one that never had it.

The model is one class. Its ONNX includes the post-processing. The photo is STRETCHED to
640x640 RGB 0..1 with no letterbox, and the best score of 300 wins. The box is the card
itself, axis aligned and unpadded: `identify.images.crop_rect` pads it by `PAD_BY_METHOD`.
`method` is "dfine". `geometry/model/rebuild.py` rebuilds the file from the labels.
"""

import sys
import threading
import time
from pathlib import Path
from typing import Optional

from geometry.detect import CARD_ASPECT, CardBox, detect_card, open_image

MODEL = Path(__file__).resolve().parent / "model" / "dfine_card_640.onnx"
SIZE = 640
MIN_SCORE = 0.25
# A CHEAP PRE-FILTER, NOT THE GUARD. The guard is `identify.images.crop_refusal`, and the crop
# preview falls back to `detect_card` when it refuses. This only spares that round trip for a
# box nobody believes (0.70 on a dark strip, aspect 0.25). The thinnest of the 243 labeled cards
# is 0.603, so 0.5 loses none of them.
MIN_BOX_ASPECT = 0.5

# THE MARGIN FOLLOWS THE FINDER. The model's box is measured at a 4% pad (0 loose crops in 74;
# 6 at 8%). A method not listed here takes the caller's default, `identify.images.CROP_PAD`.
PAD_BY_METHOD = {"dfine": 0.04}


def pad_for(box, default: float) -> float:
    return PAD_BY_METHOD.get(box.method, default)


_lock = threading.Lock()
_session = None  # None: not loaded. False: the last load failed.
_failed_at = 0.0
RETRY_AFTER = 60.0  # seconds before a failed load is tried again


def _load():
    global _session, _failed_at
    with _lock:
        if _session is False and time.monotonic() - _failed_at >= RETRY_AFTER:
            _session = None
        if _session is None:
            try:
                import onnxruntime as ort

                _session = ort.InferenceSession(str(MODEL), providers=["CPUExecutionProvider"])
            except Exception as exc:
                _session, _failed_at = False, time.monotonic()
                # Once per failure, not per photo: the cooldown is what keeps this one line.
                print(f"card_box: model not loaded ({exc!r}); using detect_card, retry in {RETRY_AFTER:.0f}s",
                      file=sys.stderr)
    return _session or None


def model_failed() -> bool:
    """True while the model's last load failed, so `locate_card` is answering with `detect_card`."""
    return _session is False


def resize_linear(array, nw, nh):
    """Pixel-centre bilinear with no antialiasing (cv2.INTER_LINEAR), which is what training saw."""
    import numpy as np

    h, w = array.shape[:2]
    ys = np.clip((np.arange(nh) + 0.5) * h / nh - 0.5, 0, h - 1)
    xs = np.clip((np.arange(nw) + 0.5) * w / nw - 0.5, 0, w - 1)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    y1, x1 = np.minimum(y0 + 1, h - 1), np.minimum(x0 + 1, w - 1)
    fy, fx = (ys - y0)[:, None, None], (xs - x0)[None, :, None]
    # GATHER ROWS AND COLUMNS WHILE STILL uint8 and convert only the 640x640 result: a float32
    # copy of a 12 MP frame is about 192 MB, times the preview's concurrent requests.
    def f(yy, xx):
        return array[yy][:, xx].astype(np.float32)

    top = f(y0, x0) * (1 - fx) + f(y0, x1) * fx
    bottom = f(y1, x0) * (1 - fx) + f(y1, x1) * fx
    return np.rint(top * (1 - fy) + bottom * fy).astype(np.uint8)


def model_card(source) -> Optional[CardBox]:
    """The model's box, or None when it is unavailable or not sure. Never raises."""
    try:
        import numpy as np

        session = _load()
        if session is None:
            return None
        image = open_image(source)  # upright, like the detector; an open frame passes through
        width, height = image.size
        pixels = resize_linear(np.asarray(image), SIZE, SIZE)
        inputs = {
            "images": pixels.transpose(2, 0, 1)[None].astype(np.float32) / 255.0,
            "orig_target_sizes": np.array([[SIZE, SIZE]], np.int64),
        }
        _, boxes, scores = session.run(None, inputs)
        best = int(np.argmax(scores[0]))
        score = float(scores[0, best])
        if score < MIN_SCORE:
            return None
        x0, y0, x1, y1 = (min(max(float(v) / SIZE, 0.0), 1.0) for v in boxes[0, best])
        if x1 <= x0 or y1 <= y0:
            return None
        w, h = (x1 - x0) * width, (y1 - y0) * height
        if min(w, h) / max(w, h) < MIN_BOX_ASPECT:
            return None
        return CardBox(
            angle=0.0, left=x0, top=y0, right=x1, bottom=y1,
            fill=score, aspect=min(w, h) / max(w, h), method="dfine",
        )
    except Exception:
        return None


def locate_card(source, aspect: Optional[float] = CARD_ASPECT) -> Optional[CardBox]:
    """The model's box, else `detect_card`'s (the safety path). None means a human should look."""
    return model_card(source) or detect_card(source, aspect)
