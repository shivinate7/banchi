"""Rebuild `dfine_card_640.onnx` from the committed corner labels (D125).

    python geometry/model/rebuild.py data <workdir>        # stretched PNGs + COCO json
    # then train D-FINE-N (Apache-2.0, github.com/Peterande/D-FINE) from its COCO-pretrained
    # `dfine_hgnetv2_n_coco` checkpoint: 1 class, 40 epochs, batch 8, AdamW lr 2e-4 (backbone
    # 1e-4), no EMA, no AMP, with `dfine_hgnetv2_n_custom.yml` pointing at <workdir>.
    python geometry/model/rebuild.py export <dfine-repo> <config.yml> <checkpoint.pth> <out.onnx>

The labels hold 243 corner sets on the owner's rig photos. Each holds a `path` to a photograph
that is NOT in this repo; a label whose file is missing is skipped. `verdict: REJECT` labels in
`labels.json` are dropped. Boxes 1 and 5 are the holdout. Needs numpy, Pillow, and for `export`
torch plus the D-FINE checkout. The ONNX takes `images` and `orig_target_sizes`.
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOLDOUT_BOXES = (1, 5)


def labels():
    a = [o for o in json.load(open(HERE / "labels.json")) if o["verdict"] != "REJECT"]
    return a + json.load(open(HERE / "labels_new.json"))


def make_data(work):
    import numpy as np
    from PIL import Image

    sys.path.insert(0, str(HERE.parent.parent))
    from geometry.card_box import resize_linear

    coco = {sp: dict(images=[], annotations=[], categories=[dict(id=0, name="card")]) for sp in ("train", "val")}
    for sp in coco:
        os.makedirs(f"{work}/{sp}", exist_ok=True)
    for o in labels():
        if not os.path.exists(o["path"]):
            continue
        sp = "val" if o["box"] in HOLDOUT_BOXES else "train"
        im = np.asarray(Image.open(o["path"]).convert("RGB"))
        H, W = im.shape[:2]
        c = np.array(o["corners"])
        x0, x1 = np.clip([c[:, 0].min(), c[:, 0].max()], 0, W)
        y0, y1 = np.clip([c[:, 1].min(), c[:, 1].max()], 0, H)
        Image.fromarray(resize_linear(im, 640, 640)).save(f"{work}/{sp}/{o['i']}.png")
        sx, sy = 640 / W, 640 / H
        d = coco[sp]
        d["images"].append(dict(id=o["i"], file_name=f"{o['i']}.png", width=640, height=640))
        d["annotations"].append(dict(id=o["i"], image_id=o["i"], category_id=0, iscrowd=0,
                                     bbox=[x0 * sx, y0 * sy, (x1 - x0) * sx, (y1 - y0) * sy],
                                     area=(x1 - x0) * (y1 - y0) * sx * sy))
    for sp, d in coco.items():
        json.dump(d, open(f"{work}/{sp}.json", "w"))
        print(sp, len(d["images"]))


def export(repo, config, ckpt, out):
    import torch
    import torch.nn as nn

    sys.path.insert(0, repo)
    from src.core import YAMLConfig

    cfg = YAMLConfig(config, resume=ckpt)
    cfg.yaml_cfg["HGNetv2"]["pretrained"] = False
    st = torch.load(ckpt, map_location="cpu")
    cfg.model.load_state_dict(st["ema"]["module"] if "ema" in st else st["model"])

    class M(nn.Module):
        def __init__(self):
            super().__init__()
            self.model, self.post = cfg.model.deploy(), cfg.postprocessor.deploy()

        def forward(self, images, sizes):
            return self.post(self.model(images), sizes)

    m = M().eval()
    d, sz = torch.rand(1, 3, 640, 640), torch.tensor([[640, 640]])
    m(d, sz)
    torch.onnx.export(m, (d, sz), out, input_names=["images", "orig_target_sizes"],
                      output_names=["labels", "boxes", "scores"], opset_version=16,
                      do_constant_folding=True, dynamo=False)


if __name__ == "__main__":
    if sys.argv[1:2] == ["data"] and len(sys.argv) == 3:
        make_data(sys.argv[2])
    elif sys.argv[1:2] == ["export"] and len(sys.argv) == 6:
        export(*sys.argv[2:])
    else:
        sys.exit(__doc__)
