## DEBT62 — the demo photos are about 180 MB of plain git, and the owner left them there

**Symptom.** `demo-assets/` holds thousands of tracked files, about 180 MB in all. The weekly mirror moves the figure.
The demo photos are most of the repo's bytes. Every clone, and every CI job that clones,
downloads them.

**Owner's ruling.** Leave it as it is. No Git LFS, and no history rewrite.

**If reopened.** The outline is `git lfs track "demo-assets/**"` with the `.gitattributes` it writes,
and CI checkout with `lfs: true` only in the jobs that read the photos. GitHub's LFS storage and
bandwidth quota is UNCHECKED: no number is stated here, because none was verified. Count runs per
month times the pulled bytes against that quota first. Without a history rewrite
(`git lfs migrate import`) the 180 MB stays in every clone's history, and only new commits shrink.
A rewrite changes every open branch and needs the owner's word on its own.
