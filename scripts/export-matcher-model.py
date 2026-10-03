#!/usr/bin/env python3
"""Export the free reader's model: Marqo ecommerce-B's IMAGE tower, fp32, to ONNX.

A DEVELOPER STEP, RUN ONCE PER MODEL. The app never runs it and never installs what it needs.
`requirements.txt` holds onnxruntime and nothing else (the owner's one-runtime ruling), so this
needs a THROWAWAY venv that has torch, torchvision and open_clip_torch, and the original
weights from Hugging Face (about 775 MB, text tower included).

    python3 -m venv /tmp/export-venv
    /tmp/export-venv/bin/pip install torch torchvision open_clip_torch onnx numpy pillow
    /tmp/export-venv/bin/python scripts/export-matcher-model.py OUT.onnx

It writes OUT.onnx and `scripts/matcher-parity-reference.npz`, then prints the file's size and
SHA-256. Publish OUT.onnx as the release asset named `identify/match.py:MODEL_FILENAME` under
`MODEL_RELEASE_TAG`, and pin the printed size and hash in `MODEL_BYTES` and `MODEL_SHA256`.
`scripts/match-parity.py` then proves the file against the reference with onnxruntime alone.
A RE-EXPORT IS NOT BYTE-IDENTICAL (measured: same weights, a different file and hash), so the pinned
hash is the PUBLISHED asset's, and a re-export is a new model file that rebuilds every fingerprint.

THE REFERENCE IS TORCH'S OWN ANSWER for fixed synthetic images, through torchvision's own
transform (resize 224 bicubic, to tensor, normalize 0.5/0.5). The shipped path is Pillow and
numpy (`identify/match.py:preprocess`), so a match between the two proves the preprocessing
as well as the graph. No stock photo or card photograph is ever stored.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

HF_ID = "hf-hub:Marqo/marqo-ecommerce-embeddings-B"
REFERENCE = REPO / "scripts" / "matcher-parity-reference.npz"


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 64
    out = Path(argv[1])
    import numpy as np
    import open_clip
    import torch
    import torchvision.transforms as T

    from identify import match

    model, _, pre = open_clip.create_model_and_transforms(HF_ID)
    model.eval()
    norm = [t for t in pre.transforms if t.__class__.__name__ == "Normalize"][0]
    if tuple(norm.mean) != (match.NORM_MEAN,) * 3 or tuple(norm.std) != (match.NORM_STD,) * 3:
        print(f"refused: the model normalises with {norm.mean}/{norm.std}, not {match.NORM_MEAN}/{match.NORM_STD}")
        return 1

    class Image(torch.nn.Module):
        def __init__(self, visual):
            super().__init__()
            self.visual = visual

        def forward(self, pixels):
            return torch.nn.functional.normalize(self.visual(pixels), dim=-1)

    net = Image(model.visual).eval()
    torch.onnx.export(
        net, torch.randn(2, 3, match.INPUT_SIZE, match.INPUT_SIZE), str(out),
        input_names=["pixels"], output_names=["embedding"],
        dynamic_axes={"pixels": {0: "n"}, "embedding": {0: "n"}}, opset_version=17, dynamo=False,
    )

    transform = T.Compose([
        T.Resize((match.INPUT_SIZE, match.INPUT_SIZE), interpolation=T.InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(norm.mean, norm.std),
    ])
    images = match.parity_images()
    with torch.no_grad():
        vectors = net(torch.stack([transform(image.convert("RGB")) for image in images])).numpy()
    np.savez_compressed(REFERENCE, vectors=vectors.astype(np.float32))

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"wrote {out}: {out.stat().st_size} bytes, sha256 {digest}")
    print(f"wrote {REFERENCE}: {len(vectors)} reference vectors")
    print("pin MODEL_BYTES and MODEL_SHA256 in identify/match.py to the two figures above, then run scripts/match-parity.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
