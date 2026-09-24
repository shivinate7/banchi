import { mkdirSync, renameSync, writeFileSync } from 'node:fs'
import { dirname, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import type {
  FullConfig,
  FullResult,
  Reporter,
  Suite,
  TestCase,
  TestResult,
} from '@playwright/test/reporter'

// THE VERDICT, AS ONE SMALL FILE A SESSION CAN READ ONCE.
//
// `make design-check` takes ~2 minutes clean and longer under load, against the 120s tool
// timeout an agent session runs under, so every invocation from one is backgrounded
// mid-run. What the session then needs is not the 450-line progress stream — it needs
// pass/fail, the counts, and the failing titles. Reading that out of `--reporter=line`
// cost a session about a dozen turns of sleep-and-poll on 2026-09-07, and three separate
// traps did the costing:
//
//   1. `playwright test | tail -N > file` writes NOTHING until the process exits, because
//      `tail` buffers its whole input. The obvious "run it and read the tail" therefore
//      produces an empty file for the entire run, and an empty file cannot be told apart
//      from a run that died.
//   2. Polling with an `until` loop is either refused by the harness or produces one
//      completion notification per poll, none of which carry the result.
//   3. The output that finally lands is ANSI-laden, contains NUL bytes (so `grep` needs
//      `-a`), and interleaves the failure list with the per-test progress.
//
// So this reporter writes RESULT_FILE and nothing else has to be parsed. The contract:
//
//   * It is written at `onBegin` with `"verdict": "running"` — so a reader mid-run can
//     tell "still going" from "died", which was trap 1's real cost.
//   * It is rewritten at `onEnd` with the verdict, the counts and the failures. `onEnd`
//     runs for an interrupted or timed-out run too, so a Ctrl-C still lands a verdict.
//   * A file still saying `running` AFTER the process has exited means the run died
//     between the two writes — a crashed worker, an OOM, a kill. That is a real signal,
//     not an ambiguity.
//   * NO FILE AT ALL means the run died before Playwright loaded its config, so no
//     reporter was ever constructed. `make design-check` deletes the file before it
//     invokes anything precisely so that case cannot show a previous run's `pass`.
//   * A `--list` run writes NOTHING, at either moment, and prints no block. It runs no test,
//     so it has no verdict to give. Until 2026-09-24 it overwrote the file with `pass` and
//     0 passed. The signal is the `_mode` option Playwright hands every reporter's
//     constructor — `'list'` exactly when `config.cliListOnly` — the same one its own html
//     reporter reads. It is private, so a bump may move it. `make verdict-selftest`'s list
//     case goes red if it does.
//   * `"verdict": "empty"` means Playwright said `passed` and no test was counted — not
//     passed, failed, flaky nor skipped. An empty shard is the real case. It is never a
//     `pass`. A run where every test was skipped is still a `pass`, since its tests ran
//     through the filter and were each counted.
//
// MEASURED, because the first draft of this comment guessed and guessed wrong. It claimed
// a `webServer` that never came up would leave `running`; it does not — Playwright still
// calls `onBegin` and `onEnd`, so that case lands a real `"verdict": "fail"` with 0/0
// counts, and so does a spec that will not parse. The only case with no write at all is an
// unloadable config, which is what the `rm` in the Makefile answers.
//
// NO ANSI, NO NUL BYTES, NO BUFFERING: `writeFileSync` at two known moments, renamed into
// place so a reader never sees a half-written file.
//
// IT IS ADDITIVE AND REPLACES NOTHING. `playwright.config.ts` keeps `list` for the human
// watching live; `make design-check-quiet` is the same run with `list` dropped, for the
// case where the progress stream is only noise.
//
// THIS FILE HAS TWO READERS, AND THEY ANSWER DIFFERENT QUESTIONS.
//
// `make docs-audit`'s `verdict file` row is the NAMES: RESULT_FILE below against the
// config's reporter list, both Makefile recipes' `rm -f`, and the path CLAUDE.md publishes,
// failing a commit on any disagreement. It exists because three of the four ways this comes
// apart are SILENT — drop this reporter from the config and the suite goes green writing
// nothing, move RESULT_FILE and the prose points at a file nobody writes, drop the `rm` and
// a run that never started leaves the last run's `pass` behind.
//
// `make verdict-selftest` is the BEHAVIOUR: it runs this file, copied into a throwaway tree,
// against one passing and one failing spec and asserts the verdict, the counts, the failing
// title, and that the error text carries no ANSI and no NUL bytes. It catches what no amount
// of name-checking can — a `@playwright/test` bump moving the Reporter API, where every name
// stays right and every count goes wrong.
//
// THAT SECOND ONE WAS ALMOST NOT BUILT, on the reasoning that a behavioural check needs a
// browser and therefore belongs with `design-check`, off `make check`. That reasoning was
// asserted rather than measured and it is wrong twice: a test that never touches the `page`
// fixture launches no browser, and a config with no `webServer` starts no Vite. The pair
// costs ~1s. It found a real defect on its first execution — the reporter depends on
// `"type": "module"` in app/package.json, which is why that file is COPIED into the
// throwaway tree rather than faked.

const HERE = dirname(fileURLToPath(import.meta.url))
const APP_DIR = HERE
const REPO_ROOT = resolve(HERE, '..')

// `.serve/` and not `captures/`: this is derived per-run process state, which is exactly
// what `.serve/` already holds (`make up`'s pidfiles and logs), and .gitignore covers it
// with a bare `.serve` — no trailing slash, per the rule at the top of that file. It is
// per-checkout by construction, since it lives inside the checkout, which is the same
// property that makes the ports safe (D43). `captures/` is the opposite: photographs and
// UI renders, kept out of git under the opsec rule rather than the derived one.
export const RESULT_FILE = resolve(REPO_ROOT, '.serve', 'design-check.json')

// Enough to name every failure in a normal run without letting a total collapse write a
// megabyte. The count is reported either way, so a truncated list still tells the truth
// about how bad it is.
const MAX_FAILURES = 60
const MAX_ERROR_CHARS = 400

type Failure = {
  title: string
  location: string
  status: string
  retries: number
  error: string
}

// Playwright's error messages carry ANSI colour and a code frame; the terminal render also
// carries NUL bytes, which is why grepping the raw log needs `-a`. Both are for a human
// reading a terminal — a session reading JSON wants the sentence. Spelled as unicode
// escapes so this file itself holds no control characters.
const ANSI = /\u001b\[[0-9;]*m/g
const NULS = /\u0000/g

function firstLines(text: string, limit: number): string {
  const plain = text.replace(ANSI, '').replace(NULS, '')
  const lines = plain.split('\n').map((line) => line.trimEnd()).filter(Boolean)
  const joined = lines.slice(0, 4).join('\n')
  return joined.length > limit ? `${joined.slice(0, limit)}...` : joined
}

function writeAtomically(payload: unknown): void {
  const body = `${JSON.stringify(payload, null, 2)}\n`
  mkdirSync(dirname(RESULT_FILE), { recursive: true })
  // Write beside the target and rename, so a reader looking at the path mid-run never
  // catches a half-written object. A rename within one directory is atomic.
  const staging = `${RESULT_FILE}.partial`
  writeFileSync(staging, body, 'utf8')
  renameSync(staging, RESULT_FILE)
}

export default class DesignCheckVerdict implements Reporter {
  private startedAt = 0
  private failures: Failure[] = []
  private failureCount = 0
  private counts = { total: 0, passed: 0, failed: 0, flaky: 0, skipped: 0 }
  private readonly listOnly: boolean

  constructor(options: { _mode?: string } = {}) {
    this.listOnly = options._mode === 'list'
  }

  // Playwright suppresses a reporter's stdout unless it declares that it writes there. The
  // final block below is deliberate: a session that ran this in the foreground and got the
  // tail anyway should see the verdict without having to open a file.
  printsToStdio(): boolean {
    return true
  }

  onBegin(_config: FullConfig, suite: Suite): void {
    if (this.listOnly) return
    this.startedAt = Date.now()
    this.counts.total = suite.allTests().length
    writeAtomically({
      target: 'design-check',
      verdict: 'running',
      startedAt: new Date(this.startedAt).toISOString(),
      pid: process.pid,
      planned: this.counts.total,
      note: 'Still `running` after the process has exited means the run died between the '
        + 'two writes. No file at all means it died before Playwright loaded its config.',
    })
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    const outcome = test.outcome()
    if (outcome === 'skipped') this.counts.skipped += 1
    else if (outcome === 'flaky') this.counts.flaky += 1
    else if (outcome === 'expected') this.counts.passed += 1
    else this.counts.failed += 1

    // A retried test reports several results and only the last one is its verdict, so the
    // TEST is counted above off `outcome()` and the failure is recorded once, here.
    if (outcome !== 'unexpected' || result.retry < test.retries) return
    this.failureCount += 1
    if (this.failures.length >= MAX_FAILURES) return
    const error = result.error?.message ?? result.error?.stack ?? result.status
    this.failures.push({
      title: test.titlePath().filter(Boolean).join(' > '),
      location: `${relative(APP_DIR, test.location.file)}:${test.location.line}`,
      status: result.status,
      retries: result.retry,
      error: firstLines(String(error), MAX_ERROR_CHARS),
    })
  }

  onEnd(result: FullResult): void {
    if (this.listOnly) return
    const finished = Date.now()
    const { passed, failed, flaky, skipped } = this.counts
    const ran = passed + failed + flaky + skipped
    const verdict = result.status !== 'passed' ? 'fail' : ran === 0 ? 'empty' : 'pass'
    const omitted = Math.max(0, this.failureCount - this.failures.length)
    writeAtomically({
      target: 'design-check',
      verdict,
      // Playwright's own word: 'passed' | 'failed' | 'timedout' | 'interrupted'. Kept
      // beside the verdict because "the suite was interrupted" and "an assertion
      // is false" are different things to do next about.
      status: result.status,
      startedAt: new Date(this.startedAt).toISOString(),
      finishedAt: new Date(finished).toISOString(),
      durationMs: finished - this.startedAt,
      counts: { ...this.counts },
      failures: this.failures,
      failuresOmitted: omitted,
    })

    const { total } = this.counts
    const seconds = ((finished - this.startedAt) / 1000).toFixed(1)
    const lines = [
      '',
      `design-check ${verdict.toUpperCase()} (${result.status}) in ${seconds}s`,
      `  ${passed}/${total} passed, ${failed} failed, ${flaky} flaky, ${skipped} skipped`,
      ...(verdict === 'empty' ? ['  no test ran, so this is not a pass'] : []),
      ...this.failures.map((f) => `  FAIL  ${f.location}  ${f.title}`),
      ...(omitted ? [`  ... and ${omitted} more`] : []),
      `  verdict: ${relative(REPO_ROOT, RESULT_FILE)}`,
      '',
    ]
    console.log(lines.join('\n'))
  }
}
