# Geometry

Find the card in the frame; cut the crop-retry bands.

## Code files

- `geometry/__init__.py` — Makes `geometry` a package.
- `geometry/card_box.py` — The card finder for runs and the crop preview: a fine-tuned D-FINE-N on onnxruntime, detect_card behind it as the safety path.
  - Decisions: `D125`
- `geometry/crop.py` — Cut the crop-retry regions out of a registered card.
  - Decisions: `D22`, `D1`, `D75`
  - Tested by: `harness/tests/t6_geometry.py`
- `geometry/detect.py` — Card-boundary detection by tone, and by border when tone refuses, and the shape correction both crop paths share.
  - Decisions: `D1`, `D22`, `D23`, `D75`
  - Tested by: `harness/tests/t6_geometry.py`
- `geometry/model/labels.json` — Corner labels on the owner's rig photographs, the first batch, with rejected rows dropped at build.
  - Decisions: `D125`
- `geometry/model/labels_new.json` — Corner labels on the owner's rig photographs, the last batch.
  - Decisions: `D125`
- `geometry/model/rebuild.py` — Rebuild the ONNX: labels to COCO, then the export of a trained D-FINE-N checkpoint.
  - Decisions: `D125`
