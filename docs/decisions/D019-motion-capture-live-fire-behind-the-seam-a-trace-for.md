## D19 — Auto-capture fires live, never from video

**The motion trigger fires per card through the same `POST /capture` a key press uses.** Never record video and extract frames. Cutting a tape into per-card frames is the motion state machine run offline. It avoids none of the tuning and gives up the position-to-photo binding `allocate_capture` makes inside the store lock, undo's safety argument (the deleted photo is of a card still in hand) and the halt at the moment of failure. The 64x36 luma trace gives re-runnable tuning at a thousandth of the bytes.

The presence gate reads a bright quantile (`CARD_QUANTILE` 0.9), never the mean. A mean describes the whole watch region and matches the card only when the card fills it. On a second rig, empty stand read mean 27-30 and bright quantile 62-69, a settled card mean 62-86 and quantile 125-236, and the floor of 90 sat above both means. A constant can be right while its statistic is wrong, and only a second rig shows it.

Every parameter derives from a measurement named where the constant lives (`docs/specs/motion-trigger.md`). Built is not tuned.

- Arming is an act. The mode is session-only and never persisted, because a remembered motion mode is an automatic shutter armed by a page load.
- A declined fire is counted on screen by reason. A halt with the feeder running says how many cards to re-feed.
- A jam surfaces and does not fire. Motion past the stall window reports `stalled`, because a hand in frame would capture-spam.
- Undo stays manual. No automatic action reaches a control that hard-deletes a record, a sidecar and a photo.
