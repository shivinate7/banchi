## DEBT62 — the demo photos are about 180 MB of plain git, and the owner wants them in Git LFS

**Symptom.** `demo-assets/` holds thousands of tracked files, about 180 MB in all. The daily mirror moves the figure.
The demo photos are most of the repo's bytes. Every clone, and every CI job that clones,
downloads them.

**Owner's word.** Move them to Git LFS soon.

**Open question.** GitHub's LFS storage and bandwidth quota, against `demo.yml` and
`check.yml` checking the tree out on every run. The quota is UNCHECKED: no number is stated
here, because none was verified. Read GitHub's current LFS limits for this account and plan
first. Then count runs per month times the pulled bytes. `check.yml` needs the photos only if
a check reads them, so also find which jobs can skip the LFS pull.

**Remedy, in outline.**

1. `git lfs track "demo-assets/**"`, and commit the `.gitattributes` it writes.
2. CI checkout with `lfs: true` in the jobs that need the photos, and `lfs: false` in the
   rest.
3. Decide whether to rewrite history (`git lfs migrate import`). Without a rewrite the about 180 MB
   stays in every clone's history, and only new commits shrink. With a rewrite every open
   branch changes, and it needs the owner's word on its own.

**Why not fixed now.** The quota answer decides whether LFS is cheaper than the current cost,
and nobody has read it. A history rewrite is the owner's call.
