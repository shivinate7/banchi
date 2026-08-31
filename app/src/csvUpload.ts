import type { CsvUpload } from './types'

/** Read one picked file as text, into the {name, content} shape every CSV upload in this
 *  app uses on the wire (`app/src/types.ts:CsvUpload`, and the server's `_store_upload`).
 *  Lifted out of RunPanel.tsx so the shipping screen shares this reader rather than
 *  carrying a second FileReader — two copies is two encodings to disagree about.
 *
 *  TEXT AND NOT BYTES, because a TCGplayer export is a CSV and the route takes it as a string —
 *  and because reading it here means the app can refuse an obviously-wrong file before it costs
 *  a round trip. The encoding is the browser's default UTF-8, which is what the export is;
 *  `pipeline/tcgcsv.py` is the only thing in this repo allowed to have an opinion about the
 *  bytes beyond that. */
export function readUpload(file: File): Promise<CsvUpload> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`))
    reader.onload = () => resolve({ name: file.name, content: String(reader.result ?? '') })
    reader.readAsText(file)
  })
}
