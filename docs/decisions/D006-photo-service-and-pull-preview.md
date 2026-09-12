## D6 — Photo service and pull preview

**One photo route serves the review queue and the pull preview alike.**

The capture server serves stored photos at `GET /photo/<box>/<position>`. The review queue requires it; the pull modal reuses it, showing the card's own capture photo beside its location before pulling. Photos are position-keyed on disk — this is display, not new storage.
