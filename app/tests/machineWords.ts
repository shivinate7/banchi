/* THE ONE MEASUREMENT `machine-words.spec.ts` READS, kept in its own module for the same
 * reason `textShape.ts` is: `page.evaluate` serialises a function by `toString()`, so it may
 * not close over anything from this file's outer scope — the word list and the repo-top-dirs
 * list are passed IN as its argument instead, both read once from `scripts/machine-words.json`
 * by the spec, so the dictionary itself still lives in exactly one file (see D196,
 * `D-text-shape-checks`).
 *
 * D196's OWN GAP, closed here. `scripts/docs-audit.py`'s `no mechanism on screen` row reads
 * `app/src`'s JSX literals through an AST walk — real, but blind to anything COMPOSED at
 * runtime: a server response relayed verbatim, the demo's own fixture text, a string built
 * from `${var}` interpolation the AST walk cannot trace. This check reads what the browser
 * actually PAINTS — `.bn-view`'s `innerText`, after fonts settle — so a request path or a
 * pipeline noun arriving through data rather than a literal is caught the same way a human
 * reading the screen would catch it.
 *
 * A CLOSED `<details>` CONTRIBUTES NOTHING, and it needs no special-casing: `innerText`
 * (unlike `textContent`) only reads what is actually RENDERED, and the UA stylesheet sets
 * `display: none` on everything under a closed `<details>` but its `<summary>`. That is
 * `D-notice-detail`'s own argument for why "the machine-words browser check reads what the
 * owner sees" is literally true once codes and server text move behind "What the server
 * said" — read `innerText`, never `textContent`, or this reads the hidden disclosure body too.
 */

export interface MachineWordsResult {
  words: Array<{ word: string; sample: string }>
  paths: Array<{ path: string; sample: string }>
}

/** Runs INSIDE the page via `page.evaluate(scanMachineWords, { words, repoTopDirs })`. */
export function scanMachineWords(args: {
  words: Record<string, string>
  repoTopDirs: string[]
}): MachineWordsResult {
  const empty: MachineWordsResult = { words: [], paths: [] }
  const view = document.querySelector('.bn-view')
  if (!view) return empty

  const text = (view as HTMLElement).innerText || ''
  if (!text.trim()) return empty

  // THE SAME \b-WRAPPING RULE `scripts/docs-audit.py:_word_pattern` USES: a bare
  // identifier-shaped word gets `\b` on both sides so `emit` does not match inside
  // `emitted`; a phrase with a space or a path-shaped entry with a `/` is matched as a
  // plain literal, because `\b` either side of a `/` checks the wrong transition.
  function wordPattern(word: string): string {
    if (/^[\w-]+$/.test(word)) {
      return `\\b${word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`
    }
    return word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  }

  const words = Object.keys(args.words)
  const wordsHit: MachineWordsResult['words'] = []
  if (words.length > 0) {
    const re = new RegExp(words.map(wordPattern).join('|'), 'gi')
    const seen = new Set<string>()
    let m: RegExpExecArray | null
    while ((m = re.exec(text))) {
      const canon = m[0].toLowerCase()
      if (seen.has(canon)) continue
      seen.add(canon)
      const start = Math.max(0, m.index - 40)
      const end = Math.min(text.length, m.index + m[0].length + 40)
      wordsHit.push({ word: m[0], sample: text.slice(start, end).replace(/\s+/g, ' ').trim() })
      if (re.lastIndex === m.index) re.lastIndex++
    }
  }

  // A REQUEST-PATH SHAPE: one of the repo's own top-level directories, followed by `/` and
  // more path-shaped characters — the exact pattern `scripts/docs-audit.py:_REPO_PATH_RE`
  // matches over JSX literals, applied here to what the page actually drew.
  const pathsHit: MachineWordsResult['paths'] = []
  if (args.repoTopDirs.length > 0) {
    const dirs = args.repoTopDirs.map((d) => d.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')
    const pathRe = new RegExp(`\\b(?:${dirs})/[\\w./<>-]+`, 'g')
    const seenPaths = new Set<string>()
    let pm: RegExpExecArray | null
    while ((pm = pathRe.exec(text))) {
      if (seenPaths.has(pm[0])) continue
      seenPaths.add(pm[0])
      const start = Math.max(0, pm.index - 40)
      const end = Math.min(text.length, pm.index + pm[0].length + 40)
      pathsHit.push({ path: pm[0], sample: text.slice(start, end).replace(/\s+/g, ' ').trim() })
    }
  }

  return { words: wordsHit, paths: pathsHit }
}
