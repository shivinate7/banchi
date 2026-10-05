import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Plugin } from 'vite'
import { DECK_POOL, DEMO_DATA_DIR, canonical, historyCards, recentCards } from './src/demoShared'

/**
 * THE DEMO'S RECORDING, SPLIT AT BUILD TIME (DEBT84). `scripts/demo-mirror.py --install` puts the
 * recorder's chunks in `demo/bundle/` unchanged; this plugin turns their `responses` into static
 * JSON files under `demo-data/` and one index of canonical key to file, so `app/src/demoServer.ts`
 * fetches a screen's data when the screen asks and Home never waits on the whole recording.
 *
 * A file holds a whole route family (`/boxes`, `/pipeline/price-now`) when the family is small, and
 * one response when it is large (`/pipeline/pricing`, `/inventory`), so a first ask costs one request
 * and no file is a megabyte nobody wanted. Each file is `{canonicalKey: {status, body}}`.
 *
 * Two keys are DERIVED here with the functions the runtime uses: `/inventory/history` and
 * `/inventory/recent` (the newest DECK_POOL cards), so Home need not fetch the whole-store read.
 *
 * ponytail: one threshold, no per-route tuning. Tune FAMILY_BYTES if a screen's first ask is too slow or too many requests.
 */
const FAMILY_BYTES = 1024 * 1024

type Entry = { status: number; body: unknown }

export function demoSplit(): Plugin {
  const dir = join(dirname(fileURLToPath(import.meta.url)), 'demo', 'bundle')
  return {
    name: 'demo-split',
    apply: 'build',
    generateBundle() {
      const responses = new Map<string, Entry>()
      const names = existsSync(dir) ? readdirSync(dir).filter((name) => /^chunk-\d+\.json$/.test(name)) : []
      for (const name of names.sort((a, b) => parseInt(a.slice(6), 10) - parseInt(b.slice(6), 10))) {
        const chunk = JSON.parse(readFileSync(join(dir, name), 'utf8')) as { responses?: Record<string, Entry> }
        for (const [key, entry] of Object.entries(chunk.responses ?? {})) responses.set(canonical(key), entry)
      }

      const inventory = responses.get('/inventory')?.body as { cards?: Record<string, Record<string, unknown>> } | undefined
      if (inventory?.cards !== undefined) {
        responses.set('/inventory/history', { status: 200, body: historyCards(inventory.cards) })
        responses.set('/inventory/recent', { status: 200, body: recentCards(inventory.cards, DECK_POOL) })
      }

      const families = new Map<string, Array<[string, string]>>()
      for (const [key, entry] of responses) {
        const family = key.startsWith('POST ') ? key.replace(/^(POST \S+).*$/s, '$1') : key.split('?')[0]!
        const text = JSON.stringify(entry)
        families.set(family, [...(families.get(family) ?? []), [key, text]])
      }

      const index: Record<string, string> = {}
      let count = 0
      const emit = (rows: Array<[string, string]>): void => {
        const file = `${count++}.json`
        this.emitFile({
          type: 'asset',
          fileName: `${DEMO_DATA_DIR}/${file}`,
          source: `{${rows.map(([key, text]) => `${JSON.stringify(key)}:${text}`).join(',')}}`,
        })
        for (const [key] of rows) index[key] = file
      }
      for (const rows of families.values()) {
        if (rows.reduce((sum, [, text]) => sum + text.length, 0) <= FAMILY_BYTES) emit(rows)
        else for (const row of rows) emit([row])
      }
      this.emitFile({ type: 'asset', fileName: `${DEMO_DATA_DIR}/index.json`, source: JSON.stringify(index) })
    },
  }
}
