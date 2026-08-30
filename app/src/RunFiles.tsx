import { runFileUrl } from './server'
import type { RunFile } from './types'
import './RunFiles.css'

/* A RUN'S FILES, AS DOWNLOADS. Extracted from `RunPanel.tsx` on 2026-08-30 (D50) so two
 * screens can draw them, because the import CSVs moved to `#/pricing` with the button that
 * writes them and everything else stayed on `#/runs` with the commands that wrote IT.
 *
 * THE SPLIT IS BY `only`, AND IT IS THE WHOLE REASON THIS TAKES A PROP:
 *
 *   `import`  the two import CSVs. Their entire job is an errand that begins the moment
 *             `emit` is pressed — download, Import to Staged, Export From Staged — and that
 *             press is on `#/pricing` now. `docs/GATES.md`'s recorded gap was never "the file
 *             must be at address X"; it was that the press and the receipt were in different
 *             places, one of them a terminal the owner never saw.
 *   `run`     everything else: `report.txt` and `pricing.json` (join), `reconcile.txt`
 *             (reconcile), `console.log`. Each sits one screen-inch from the button that
 *             produced it, which is the same argument pointing the other way.
 *
 * `is_import` IS COMPUTED SERVER-SIDE BY FILENAME (`_artefacts`), so the split is a field
 * rather than a rule this file re-derives.
 *
 * THE `manifest.json` FILTER TRAVELS WITH THE COMPONENT rather than sitting at each call
 * site. Two callers each remembering it is two places it can drift, and the manifest is the
 * one file here that is bookkeeping rather than output.
 *
 * RENDERS `null` ON AN EMPTY LIST, which is what lets a caller drop it in unguarded.
 */
export function RunFiles({
  run,
  files,
  only,
}: {
  run: string
  files: readonly RunFile[]
  only?: 'import' | 'run'
}) {
  const shown = files
    .filter((file) => file.name !== 'manifest.json')
    .filter((file) =>
      only === undefined ? true : only === 'import' ? file.is_import : !file.is_import,
    )
  if (shown.length === 0) return null

  /* DERIVED FROM `only`, NEVER PASSED IN. A `head` prop is two callers free to disagree about
     what a filtered list is called. */
  const head = only === 'import' ? 'The files to import' : 'Files'

  return (
    <div className="run-files">
      <p className="run-files-head">{head}</p>
      {shown.map((file) => (
        <a
          key={file.name}
          className={`run-file${file.is_import ? ' run-file-import' : ''}`}
          href={runFileUrl(run, file.name)}
          download={file.name}
        >
          <span className="run-file-name">{file.name}</span>
          <span className="run-file-size">{(file.bytes / 1000).toFixed(1)} kB</span>
        </a>
      ))}
    </div>
  )
}
