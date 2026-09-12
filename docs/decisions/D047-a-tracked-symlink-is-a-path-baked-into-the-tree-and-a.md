## D47 — A tracked symlink is a path baked into the tree, and a checkout will spend a directory to place one

**A symlink that leaves the repository may not be committed, because checking it out elsewhere destroys whatever stands in its way.** Built 2026-08-30, after a `git merge --ff-only origin/main` in the main working tree replaced the 133 MB eval-image mirror with a link pointing at itself. No file was written by hand and no script misbehaved: the checkout did exactly what it was told, and what it was told was wrong.

**The data came back, and the entry is written as though it had not.** iCloud Drive restored the directory from its own copy about ten minutes later — 150 images and the manifest, intact — and removed the empty conflict copy it had made in the meantime. That is luck wearing the clothes of a backup: the same sync layer D44 exists to defend against is what happened to be holding the only other copy. On a machine without it the loss is permanent, and the remedy would have been a 151-file re-download rather than nothing at all only because D15 makes this data derived. **The first draft said the mirror was deleted, because that was true of every observation available for ten minutes.** Corrected rather than quietly softened, because the mechanism is unchanged by the recovery and is the reason the rules below exist.

### The mechanism

`scripts/worktree-guard.sh` provisions a linked worktree by symlinking two gitignored things to the main tree — `app/node_modules` and `harness/images`. Correct there, and necessarily an **absolute path**. Then:

1. `.gitignore` said `node_modules/` and `harness/images/`. **A pattern ending in `/` matches directories only**, and git does not count a symlink as a directory — so neither link was ignored in a worktree, and both were invisible to a reader who had just read the ignore file and concluded they were covered.
2. A session ran `git add -A` and committed both, as mode `120000` blobs whose contents are an **absolute path on one Mac** — the main working tree's own location, followed by the same two names.
3. In the **main** working tree those paths name the links' own locations. Checking the commit out there makes each one a symlink to itself, and **git removes an ignored file or directory that stands in the way of a checkout without asking**. The real directories were ignored, so they were removed.

**What it cost, measured.** `harness/images` — 133 MB, 150 eval images and the manifest that labels them — was replaced by a self-referential link at 20:13 on 2026-08-29, with an empty iCloud conflict copy (`harness/images 2`) beside it. Every worktree linking to that path went dangling with it. T1 failed with a `FileExistsError` from `IMAGES_DIR.mkdir(exist_ok=True)`, which is what `mkdir` does when the path exists and is not a directory: **the error names the symptom and says nothing about the cause**, which is why this took a full investigation rather than a glance.

**`app/node_modules` was in the same trap and survived by accident.** The pull that detonated the images also carried a commit that had removed the node_modules entry from the index — for an unrelated reason, while cleaning a merge — so the add and the delete cancelled and git left the real directory alone. An accident is not a guard, and this entry is what replaces it.

### The fix is three things, and only the third is new machinery

- **`harness/images` is untracked.** It was the only tracked symlink left in the tree.
- **Both ignore patterns lose the trailing slash** — `node_modules` and `harness/images` — so they match a link as well as a directory. That is the one-character fault at the root of it, now stated in the file with the reason attached.
- **The pre-commit hook refuses a staged symlink that leaves the repository.** It reads mode `120000` out of the index rather than guessing from a name; an absolute target is refused outright, and a relative one is refused when it climbs out of the tree. **A relative link that stays inside is allowed**, because that is the only kind that survives a clone on another machine — which is the property actually being enforced. `PKMNSCAN_LINKS=off` bypasses, in the shape the iCloud-duplicate rule beside it already uses.

### The mirror left iCloud and came back

**Moving it out was the owner's call and not a consequence of the bug.** `PKMNSCAN_IMAGE_MIRROR` had been documented since build-order step 9 and read by nothing; `harness/eval/fixtures.py` honors it now, and the allowlist entry that carried it as a documented-but-unbuilt name is retired the moment it came true, exactly as D16 requires. The default is unchanged, so a tree that sets nothing behaves as it always did and every banked score stays comparable. The reason for moving it was D44's: this repository sat in iCloud Drive, and 133 MB of derived binaries syncing there is what produced the conflict copies that entry refuses.

**And moving it gives up the thing that just saved the mirror**, which is the honest way to record the trade. iCloud's copy is what restored the directory. Outside it there is no second copy and no version history — the recovery path becomes the re-download, which is exactly what D15 says this data is for: derived, reproducible, and never the artifact worth keeping. A safety net that costs conflict copies, against a clean tree whose worst case is one download. The owner took the second.

**The mirror came home on 2026-08-29, hours after it left, because the repo left iCloud and took the whole reason with it.** `PKMNSCAN_IMAGE_MIRROR` is unset, `harness/eval/fixtures.py` falls back to its own default, and the 152 files sit at `harness/images` where every version of this project before 2026-08-30 expected them. Measured after the move: `IMAGES_DIR` resolves in-repo, 152 entries with the manifest, `make harness` all 7 passed, `make ignore-check` green.

**Both paragraphs above are void as dispositions and kept as reasoning, and the second is why this was cheap to reverse.** The trade it records had exactly one term on each side, and leaving iCloud zeroed both at once. There are no conflict copies to pay because nothing syncs the directory, and there is no safety net to give up because there was none left to lose. A decision whose two arguments both evaporate is not one that has to be re-argued; it is one whose premise is gone, and the honest move is to put the data back where the default already pointed.

**What survives, named so nothing is unpicked with it.** Three things landed under this heading and only one was about iCloud:

- **The knob stays and is still honored.** D15 authored `PKMNSCAN_IMAGE_MIRROR` for the mirror's SIZE, not its sync status, and ~16.7 GB at full catalog is still the reason which disk it lands on is a choice worth having. Unset is not unbuilt: the code reads it, the allowlist entry stays retired, and a tree that wants the mirror elsewhere sets one line.
- **The provisioner still ASKS rather than assumes.** `scripts/worktree-guard.sh` running the main checkout's `fixtures.py` to learn where the mirror is was written because the move broke it, and it is correct whatever the answer — including today's, which is the in-repo default it used to hardcode. Reverting it would restore the silent skip, not the old code.
- **`harness/images` keeps its type-agnostic ignore pattern.** That is this entry's own subject and has nothing to do with where the bytes live: the pattern exists so a worktree's SYMLINK at that name is ignored, which is the fault this entry opens with. A directory there now makes the pattern matter more, not less.

**What would reopen this: the repo going back into a synced folder.** Then D44's hazard returns and the mirror is the largest thing in the tree that would sync, so moving it out is the first remedy to reach for — and it is one line in `.env`, which is the whole point of leaving the knob alone.

**What this does not do.** It does not stop `worktree-guard.sh` making the links — they are right, and they are what keep T1 from re-downloading 151 files per worktree. It does not make symlinks a bad idea. It stops one of them being **committed**, which is the only step in the chain where a local convenience becomes every checkout's problem.

### It broke the audit on its way in, and that defect was older than this entry

Writing the paragraphs above put the string `app/node_modules` into a doc, which made it a path candidate — and `scripts/docs-audit.py:ignored_paths` probes missing candidates through `git check-ignore --stdin`, which **exits 128 and stops** on a pathspec it refuses. A provisioning symlink is exactly such a pathspec, so the batch aborted and every candidate after it lost its answer. The audit then blocked the commit over `harness/.cache/` in `docs/GATES.md` — a reference that was correct, unchanged, and in a different file.

**A batch that did not run cleanly is not evidence about anything.** check-ignore's contract is 0 when something matched and 1 when nothing did; any other code means it gave up. It now falls back to asking one candidate at a time so a refusal is contained. The failure mode this replaces is the worse kind: not a check that misses something, but one that **reports a defect in a file nobody touched**, which sends a session investigating the wrong doc.

### Moving the mirror broke the provisioner, and the provisioner said nothing

Found 2026-08-30 by a Stop hook that failed T1 in a worktree whose main checkout was healthy. This entry moved the mirror behind `PKMNSCAN_IMAGE_MIRROR` and did not look at the one script whose job is to give a worktree that mirror. `scripts/worktree-guard.sh` and `make worktree-setup` both read `[ -d "$main/harness/images" ]` and linked THAT path — and after the move the main checkout has no `harness/images` at all, so the precondition went false and both blocks were skipped whole. **Neither printed anything**: the only failure message sat on the `ln`, and the `ln` was never reached. A fresh worktree then downloaded 151 images at its first `make harness`, which is the exact cost the guard's own header says that line exists to avoid.

**The fix is to ask rather than to assume, and the thing asked is the one resolution.** Both call sites now run the MAIN checkout's own `harness/eval/fixtures.py` and link to whatever `IMAGES_DIR` answers — env var, then that checkout's `.env`, then its in-repo default. Re-deriving that precedence in shell is how the two drift apart a second time, and `fixtures.py` is stdlib-only at module scope so a bare `python3` can answer it. The script never reads `.env` itself; `envfile` does, and the only thing crossing the pipe is a path. Where there is no mirror to link, it now SAYS so — the silent skip was the defect, not the missing link.

**That resolution answers `harness/images` again as of 2026-08-29**, the mirror having come home. The fix is untouched by that and must stay: what it replaced was a hardcoded path that happened to be right, and it is exactly as wrong to hardcode a path that happens to be right today.

**And the path belongs in `.env`, not in a shell profile.** Tried and reverted the same day: an export in `~/.zshenv` fixes an interactive session and does nothing for the Stop hook, which runs `scripts/stop-gate.sh` under **bash** — a shell that reads no zsh profile and, spawned from an app started before the export existed, inherits nothing either. `.env` is what every reader of this repo already consults regardless of shell, and `envfile.get` still lets a real environment variable win. Two records of one path is also drift this file dislikes: a stale export would outrank a corrected `.env` and point at a mirror that had moved.

### The reverse direction, closed the same day

**What would reopen this: a third provisioned path.** The guard is general — it refuses by mode and by target, not by name — so a new link is covered the day it is added. What was not covered is the reverse: a path that ought to be ignored and is not, which is what let the first one through. `git check-ignore` over the provisioned set, run off the commit path, would close that half.

**It reopened the same day, by exactly that direction.** Two of the four provisioned paths kept their directory-only patterns — `harness/.cache/` and `.venv/` — on the reasoning that `scripts/worktree-guard.sh` COPIES the first and BUILDS the second, so neither is ever a link. That reasoning is sound about the script and says nothing about the path. A session that provisioned a worktree by hand linked both, and got this entry's own state straight back: **untracked rather than ignored**, one `git add -A` from committing an absolute path into one Mac.

**It also broke something this entry did not predict.** `scripts/docs-audit.py`'s ignore filter exists so a gitignored path is not reported as a dangling reference — and it had nothing to match, so every doc reference to `harness/.cache/` read as a broken path and the pre-commit hook blocked a commit over two of them. That is the audit being right for the wrong reason: the reference was fine and the ignore was not.

**So the rule is about the PATH and not about today's provisioning.** All four patterns are type-agnostic now. The precision a trailing slash buys is worth nothing on a name nothing else in the tree bears, and it is worth less than nothing when it silently depends on a script's current behavior staying what it is.

**And `make ignore-check` is the guard this entry asked for**, doing exactly what the paragraph above specified: `git check-ignore` over the provisioned set, asserting each is ignored **as a file, as a directory and as a symlink**. It is in `make check` and deliberately NOT in the git hook — D18's rule, and a second reason of its own: what it checks is a property of the local worktree's provisioning, so a fresh clone with none of these paths present would fail a commit over something that is not wrong. Off the commit path is where a check about local state belongs.

---
