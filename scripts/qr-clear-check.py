#!/usr/bin/env python3
"""Decode every STAGED image under the demo's two tracked photo directories.

THE ONE CHECK THAT LOOKS AT THE IMAGE, run at commit time. `scripts/demo-photos.py` and
`scripts/demo-extra-real.py` already run this exact decode before either one ever writes a
photograph — but that only proves the CURATOR is honest. It says nothing about a photograph
staged by any other path: an edit made outside either curator, a reviewer's own `git add`, a
mutation applied by hand. The commit is the one place every route into `demo-assets/photos/`
and `demo-assets/extra/photos/` converges, so this is where a bearer instrument is stopped
regardless of how it got staged.

Reads the STAGED BLOB (`git show :<path>`), never the working-tree file — a partially staged
edit must be judged by what would actually be committed, not by whatever sits on disk.

Exit 0: every staged image in scope decoded to no QR.
Exit 1: at least one staged image carries a decodable QR. Prints the file name, never the
        payload — naming the file is enough to go and look.
Exit 2: the decoder itself could not load. UNAVAILABLE IS NOT ABSENT — a decoder that could
        not run is not a clean scan, and letting the commit through on that basis is exactly
        the failure this check exists to prevent.

    python3 scripts/qr-clear-check.py <staged-path> [<staged-path> ...]
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def staged_bytes(path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f":{path}"], cwd=REPO_ROOT, check=True, capture_output=True,
    ).stdout


def main(argv: list) -> int:
    if not argv:
        return 0

    from codes import qr
    from PIL import Image

    refused = []
    for path in argv:
        try:
            blob = staged_bytes(path)
        except subprocess.CalledProcessError:
            continue  # deleted or renamed out of the index — nothing to decode
        try:
            with Image.open(io.BytesIO(blob)) as image:
                image.load()
                read = qr.decode_image(image)
        except qr.QrUnavailable:
            print(
                "REFUSING: the QR decoder is unavailable, so %s cannot be cleared of "
                "carrying a live code. Install requirements.txt (zxing-cpp) and retry."
                % path,
                file=sys.stderr,
            )
            return 2
        except Exception as exc:  # not a decodable image at all — treat as a real failure
            print(
                "REFUSING: %s could not be opened to check for a QR (%s). "
                "Unavailable is not absent." % (path, exc),
                file=sys.stderr,
            )
            return 2
        if read is not None:
            refused.append(path)

    if refused:
        print("staged image(s) carrying a decodable QR:", file=sys.stderr)
        for path in refused:
            print("  %s" % path, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
