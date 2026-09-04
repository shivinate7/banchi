import { Icon, type IconName } from './kit'
import { runFileUrl } from './server'
import type { RunFile } from './types'
import './RunFiles.css'

/* A RUN'S FILES, AS DOWNLOAD CARDS. Shared by `#/runs` (everything but the import CSVs) and
 * `#/pricing` (the import CSVs, beside the press that writes them) — `only` is the split,
 * and `is_import` is the server's own answer to which side a file is on. `manifest.json` is
 * bookkeeping rather than output and is never listed. Renders nothing on an empty list. */

function kindOf(file: RunFile): { readonly icon: IconName; readonly label: string } {
  if (file.is_import) return { icon: 'upload', label: 'Import to Staged' }
  const name = file.name.toLowerCase()
  if (name.endsWith('.csv')) return { icon: 'columns', label: 'CSV export' }
  if (name.endsWith('.txt')) return { icon: 'list', label: 'Report' }
  if (name.endsWith('.log')) return { icon: 'history', label: 'Console log' }
  if (name.endsWith('.json')) return { icon: 'layers', label: 'JSON' }
  return { icon: 'download', label: 'File' }
}

function sizeOf(bytes: number): string {
  if (bytes < 1000) return `${bytes} B`
  if (bytes < 1_000_000) return `${(bytes / 1000).toFixed(1)} kB`
  return `${(bytes / 1_000_000).toFixed(1)} MB`
}

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
    .filter((file) => (only === undefined ? true : only === 'import' ? file.is_import : !file.is_import))
  if (shown.length === 0) return null

  const head = only === 'import' ? 'The files to import' : 'Files'

  return (
    <div className="run-files">
      <p className="run-files-head">{head}</p>
      <div className="run-files-grid">
        {shown.map((file, i) => {
          const kind = kindOf(file)
          return (
            <a
              key={file.name}
              className={`run-file${file.is_import ? ' run-file-import' : ''}`}
              href={runFileUrl(run, file.name)}
              download={file.name}
              style={{ animationDelay: `${i * 30}ms` }}
            >
              <span className="run-file-icon">
                <Icon name={kind.icon} size={16} />
              </span>
              <span className="run-file-text">
                <span className="run-file-name" title={file.name}>
                  {file.name}
                </span>
                <span className="run-file-meta">
                  {kind.label} · <span className="run-file-size">{sizeOf(file.bytes)}</span>
                </span>
              </span>
              <Icon name="download" size={16} className="run-file-arrow" />
            </a>
          )
        })}
      </div>
    </div>
  )
}
