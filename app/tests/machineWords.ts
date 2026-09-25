/* THE ONE MEASUREMENT `machine-words.spec.ts` READS, kept in its own module for the same
 * reason `textShape.ts` is: `page.evaluate` serialises a function by `toString()`, so it may
 * not close over anything from this file's outer scope — the word list and the repo-top-dirs
 * list are passed IN as its argument instead, both read once from `scripts/machine-words.json`
 * by the spec, so the dictionary itself still lives in exactly one file (see D196,
 * `D284`).
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
 * `D269`'s own argument for why "the machine-words browser check reads what the
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

  // `scripts/docs-audit.py:_word_pattern`'s RULE, WITH A LETTER BOUNDARY IN PLACE OF `\b`: a
  // bare identifier-shaped word may not touch a LETTER on either side, so `emit` does not
  // match inside `emitted` and `Staged` does not match inside `unstaged`. A letter boundary,
  // not `\b`, because rendered `innerText` joins two adjacent inline spans with no space:
  // `#/orders` draws "Pushed 0Staged 0", and `\bStaged` never matches after the digit. A
  // phrase with a space or a path-shaped entry with a `/` is matched as a plain literal.
  function wordPattern(word: string): string {
    const literal = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    if (/^[\w-]+$/.test(word)) return `(?<![A-Za-z])${literal}(?![A-Za-z])`
    return literal
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

/* THE MUTATION HOOK for `machine-words.spec.ts` (`MACHINE_WORDS_MUTATE=<hash>`): one sentence
 * naming a word on the list, appended inside that route's `.bn-view` through
 * `page.evaluate`, never an edit under `app/src`. "the resolver" is on the list and on no
 * screen, so the finding it makes is always a NEW one. */
export function injectMachineWord(): void {
  const root = document.querySelector('.bn-view')
  if (!root) return
  const p = document.createElement('p')
  p.textContent = 'This mutation line names the resolver on purpose.'
  root.appendChild(p)
}
