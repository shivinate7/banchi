#!/usr/bin/env python3
"""Prove a matcher model file against torch's own answer, with onnxruntime alone.

    python3 scripts/match-parity.py [MODEL.onnx]        # default: the file the app would load

The file must be the pinned size and SHA-256 (`identify/match.py:MODEL_BYTES`, `MODEL_SHA256`),
and every one of the reference vectors in `scripts/matcher-parity-reference.npz` must come back
at a cosine of at least `MIN_COSINE`. The reference is torch's output for fixed synthetic images
(`identify.match.parity_images`) through torchvision's transform; this runs the SHIPPED path
(Pillow, numpy, onnxruntime), so passing proves the preprocessing as well as the graph.

A changed model file fails until someone re-exports it (`scripts/export-matcher-model.py`) and
pins the new figures on purpose. Exit 0 is a pass, 1 a failure, 2 a file or dependency that
could not be read (never reported as a pass or a failure).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

MIN_COSINE = 0.9999
REFERENCE = REPO / "scripts" / "matcher-parity-reference.npz"


def main(argv) -> int:
    from identify import match

    target = Path(argv[1]) if len(argv) > 1 else match.model_path()
    try:
        import numpy as np

        reference = np.load(REFERENCE)["vectors"]
    except Exception as exc:
        print(f"unknown: the reference could not be read ({exc})")
        return 2
    if not target.exists():
        print(f"unknown: no model file at {target}")
        return 2
    size = target.stat().st_size
    digest = match.sha256_of_file(target)
    failures = []
    if size != match.MODEL_BYTES:
        failures.append(f"size {size} is not the pinned {match.MODEL_BYTES}")
    if digest != match.MODEL_SHA256:
        failures.append(f"sha256 {digest} is not the pinned {match.MODEL_SHA256}")
    try:
        vectors = match.embed(match.parity_images(), target)
    except Exception as exc:
        print(f"unknown: the model could not run ({type(exc).__name__}: {exc})")
        return 2
    if vectors.shape != reference.shape:
        failures.append(f"shape {vectors.shape} is not the reference's {reference.shape}")
    else:
        cosines = (vectors * reference).sum(axis=1)
        worst = float(cosines.min())
        if worst < MIN_COSINE:
            failures.append(f"the worst cosine {worst:.6f} is under {MIN_COSINE} ({int((cosines < MIN_COSINE).sum())} of {len(cosines)})")
        print(f"cosine to torch: worst {worst:.8f}, mean {float(cosines.mean()):.8f} over {len(cosines)} vectors")
    for line in failures:
        print("FAIL", line)
    print("model parity:", "FAIL" if failures else "ok")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
