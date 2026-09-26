import { useEffect, useRef, useState } from 'react'
import { Icon, IconButton } from './kit'
import './Runs.css'

/* A COMMAND'S STDOUT, VERBATIM, in a well: a mono log that follows its tail, counts its
 * lines, folds, and copies. Nothing here summarises what a command said — the log is the
 * receipt, and being able to grep what you saw is the point of showing it. */
export function LogWell({
  text,
  label,
  className,
  defaultOpen = true,
  maxHeight,
}: {
  readonly text: string
  readonly label: string
  readonly className?: string
  readonly defaultOpen?: boolean
  readonly maxHeight?: number
}) {
  const box = useRef<HTMLPreElement | null>(null)
  const [open, setOpen] = useState(defaultOpen)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (box.current !== null) box.current.scrollTop = box.current.scrollHeight
  }, [text, open])

  if (text.trim() === '') return null
  const lines = text.replace(/\n$/, '').split('\n').length

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable — the text is selectable in the well */
    }
  }

  return (
    <div className={`runslog${open ? '' : ' runslog-closed'}`}>
      <div className="runslog-head">
        <button type="button" className="runslog-toggle" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          <Icon name="chevronDown" size={14} className="runslog-chev" />
          <span className="runslog-label">{label}</span>
          <span className="runslog-lines">
            {lines} line{lines === 1 ? '' : 's'}
          </span>
        </button>
        <IconButton size="sm" icon={copied ? 'check' : 'copy'} label="Copy" name={`Copy ${label.toLowerCase()}`} onClick={() => void copy()} />
        <span className="bn-sr" role="status">
          {copied ? 'Copied' : ''}
        </span>
      </div>
      {open ? (
        <pre
          className={['run-console', className ?? ''].filter(Boolean).join(' ')}
          ref={box}
          aria-label={label}
          tabIndex={0}
          style={maxHeight === undefined ? undefined : { maxHeight }}
        >
          {text}
        </pre>
      ) : null}
    </div>
  )
}
