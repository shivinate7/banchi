# Geometry

Find the card in the frame; cut the crop-retry bands.

## Code files

- `geometry/__init__.py` — Makes `geometry` a package.
- `geometry/card_box.py` — The card finder for runs and the crop preview: a fine-tuned D-FINE-N on onnxruntime, detect_card behind it as the safety path.
- `geometry/crop.py` — Cut the crop-retry regions out of a registered card.
- `geometry/detect.py` — Card-boundary detection by tone, and by border when tone refuses, and the shape correction both crop paths share.
- `geometry/model/rebuild.py` — Rebuild the ONNX: labels to COCO, then the export of a trained D-FINE-N checkpoint.
