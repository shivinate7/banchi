## D13 — Mac holds the one truth

**Photos and the store (SQLite, D88) live on one Mac and are read and written through the capture server, so the owner's and the Fulfiller's devices cannot disagree.** Single operator is a choice with a known exit, not an unexamined assumption. What would move: this entry, D5 (two personas on two devices) and D24's opsec rules, which assume one person controls the machine. Hosting elsewhere is a different product (backups, secrets, uptime). Remote access is a tunnel to this Mac and needs no code change.

**The camera path fixes three rules.** The rig is a Sony RX100 VII or A7C over HDMI into an Elgato Cam Link 4K.
- The Cam Link presents a plain UVC webcam, distinguishable only by label and id. So the device picker is required and `facingMode: "environment"` is never used.
- The Cam Link sends a landscape frame however the camera is mounted, and the rig mounts it on its side. The stored photo is upright only after a quarter turn, so rotation has two choices, 90 and 270, and the default is 90. A stored 0 or 180 migrates to it. Leaving 0 as the fallback misread 45 of 53 cards.
- Rotation is applied at capture time (`app/src/useCamera.ts`, `app/src/encode-worker.ts`), so the model, the crop bands and the review photo all see one upright photo. The live preview stays as the camera sends it.

The camera is not driven over USB: tethered capture costs one to three seconds a frame, a native dependency and a refocus per shot. Frame the card tight in the 4K field. The number-corner crop can only enlarge pixels that were captured, and glare on the number is unrecoverable at any resolution.
