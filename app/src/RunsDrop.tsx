import { useState, type ChangeEvent, type DragEvent } from 'react'
import { Icon, type IconName } from './kit'
import './Runs.css'

/* FILE CONTROLS THAT LOOK LIKE THE PRODUCT. A native file input cannot be styled to sit
 * beside a kit button, so the input is visually hidden and its label is the control — a
 * label IS the accessible name of the input it wraps, so this costs nothing in reachability.
 * Both take a drop as well as a click. */

type Common = {
  readonly accept?: string
  readonly disabled?: boolean
  readonly onFiles: (files: File[]) => void
}

function useDrop(onFiles: (files: File[]) => void, disabled: boolean | undefined) {
  const [over, setOver] = useState(false)
  return {
    over,
    onDragOver: (event: DragEvent) => {
      if (disabled) return
      event.preventDefault()
      setOver(true)
    },
    onDragLeave: () => setOver(false),
    onDrop: (event: DragEvent) => {
      event.preventDefault()
      setOver(false)
      if (disabled) return
      const files = Array.from(event.dataTransfer.files)
      if (files.length > 0) onFiles(files)
    },
  }
}

function fromInput(event: ChangeEvent<HTMLInputElement>, onFiles: (files: File[]) => void): void {
  const files = Array.from(event.currentTarget.files ?? [])
  /* Cleared before the async work so the same file can be picked twice in a row. */
  event.currentTarget.value = ''
  if (files.length > 0) onFiles(files)
}

/** A file picker that measures like a kit button. */
export function FileButton({
  label,
  icon = 'upload',
  accept = '.csv,text/csv',
  multiple,
  disabled,
  busy,
  onFiles,
  className,
}: Common & {
  readonly label: string
  readonly icon?: IconName
  readonly multiple?: boolean
  readonly busy?: boolean
  readonly className?: string
}) {
  const drop = useDrop(onFiles, disabled)
  return (
    <label
      className={['bn-btn', 'runs-filebtn', className ?? ''].filter(Boolean).join(' ')}
      data-over={drop.over ? 'true' : undefined}
      data-busy={busy ? 'true' : undefined}
      aria-disabled={disabled ? 'true' : undefined}
      onDragOver={drop.onDragOver}
      onDragLeave={drop.onDragLeave}
      onDrop={drop.onDrop}
    >
      <input
        type="file"
        className="runs-file-input"
        accept={accept}
        multiple={multiple === true}
        disabled={disabled === true}
        onChange={(event) => fromInput(event, onFiles)}
      />
      <Icon name={icon} size={16} />
      {label}
    </label>
  )
}

/** A drop zone for the one file a screen is waiting for. */
export function DropZone({
  title,
  hint,
  fileName,
  accept = '.csv,text/csv',
  disabled,
  onFiles,
  className,
}: Common & {
  readonly title: string
  readonly hint: string
  readonly fileName?: string | null
  readonly className?: string
}) {
  const drop = useDrop(onFiles, disabled)
  const filled = typeof fileName === 'string' && fileName !== ''
  return (
    <label
      className={['runs-drop', drop.over ? 'runs-drop-over' : '', filled ? 'runs-drop-filled' : '', className ?? '']
        .filter(Boolean)
        .join(' ')}
      onDragOver={drop.onDragOver}
      onDragLeave={drop.onDragLeave}
      onDrop={drop.onDrop}
    >
      <input
        type="file"
        className="runs-file-input"
        accept={accept}
        disabled={disabled === true}
        onChange={(event) => fromInput(event, onFiles)}
      />
      <span className="runs-drop-art">
        <Icon name={filled ? 'check' : 'upload'} size={20} />
      </span>
      <span className="runs-drop-text">
        <span className="runs-drop-title">{filled ? fileName : title}</span>
        <span className="runs-drop-hint">{filled ? 'Drop another file to replace it' : hint}</span>
      </span>
    </label>
  )
}
