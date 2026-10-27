import { useEffect, useState, type ReactNode } from 'react'
import { Icon, type IconName } from './Icon'
import { IconButton } from './index'

/* One toast stack for the whole product. Any screen may call toast(); the shell renders
   <Toaster/> once. Receipts carry an undo; status toasts expire; refusals stay until dismissed. */

export type ToastKind = 'receipt' | 'status' | 'ok' | 'refusal'
export type Toast = {
  readonly id: number
  readonly kind: ToastKind
  readonly title: ReactNode
  readonly body?: string
  readonly icon?: IconName
  /** A refusal toast is amber; `danger` makes it red for a real fault (`server.ts:failureTone`). */
  readonly tone?: 'warn' | 'danger'
  readonly ttlMs: number
  readonly action?: { readonly label: string; readonly kbd?: string; readonly onPress: () => void }
  /** Dismissed and folding away; gone from the list one beat later. */
  readonly leaving?: boolean
  /** Under the body, inside the text column: a `ToastLine`, with presses of its own that do not
   *  dismiss the toast (`ToastPress`). */
  readonly extra?: ReactNode
  /** A press inside `extra` is running: the fade waits (`holdToast`). */
  readonly held?: boolean
  /** Counts the clock's restarts, so the drain bar starts over with it. */
  readonly run?: number
}
type ToastInput = Omit<Toast, 'id' | 'ttlMs' | 'leaving' | 'held' | 'run'> & { readonly ttlMs?: number }
/** How long a dismissed toast takes to fade — kit.css's `bn-toast-out` (--bn-t). */
const LEAVE_MS = 220

type Listener = (toasts: readonly Toast[]) => void
const listeners = new Set<Listener>()
let toasts: readonly Toast[] = []
let nextId = 1
/** Each standing toast's fade timer, by id. */
const clocks = new Map<number, number>()

function startClock(id: number, ttlMs: number): void {
  window.clearTimeout(clocks.get(id))
  clocks.delete(id)
  if (ttlMs > 0) clocks.set(id, window.setTimeout(() => dismissToast(id), ttlMs))
}

function emit(): void {
  for (const listener of listeners) listener(toasts)
}

/** A dismissed toast fades and keeps its box, so no toast someone can see moves. The boxes go
 *  together, once every toast in the stack has faded. */
export function dismissToast(id: number): void {
  const hit = toasts.find((t) => t.id === id)
  if (hit === undefined || hit.leaving) return
  window.clearTimeout(clocks.get(id))
  clocks.delete(id)
  toasts = toasts.map((t) => (t.id === id ? { ...t, leaving: true } : t))
  emit()
  window.setTimeout(() => {
    if (toasts.every((t) => t.leaving)) {
      toasts = []
      emit()
    }
  }, LEAVE_MS)
}

export function toast(input: ToastInput): number {
  const id = nextId++
  const ttlMs = input.ttlMs ?? (input.kind === 'receipt' ? 20000 : input.kind === 'refusal' ? 0 : 5000)
  const next: Toast = { ...input, id, ttlMs }
  toasts = [...toasts, next]
  emit()
  /* Past five standing toasts the oldest fades, like a dismissed one: it never leaves the stack under the others. */
  const standing = toasts.filter((t) => !t.leaving)
  if (standing.length > 5 && standing[0] !== undefined) dismissToast(standing[0].id)
  startClock(id, ttlMs)
  return id
}

/** A press inside the toast is running: its fade waits, and starts over in full once the press
 *  is let go, so the answer is read for as long as a receipt is. */
export function holdToast(id: number, held: boolean): void {
  const hit = toasts.find((t) => t.id === id)
  if (hit === undefined || hit.leaving || (hit.held ?? false) === held) return
  toasts = toasts.map((t) => (t.id === id ? { ...t, held, run: held ? t.run : (t.run ?? 0) + 1 } : t))
  emit()
  if (held) {
    window.clearTimeout(clocks.get(id))
    clocks.delete(id)
  } else startClock(id, hit.ttlMs)
}

export function useToasts(): readonly Toast[] {
  const [list, setList] = useState<readonly Toast[]>(toasts)
  useEffect(() => {
    listeners.add(setList)
    return () => {
      listeners.delete(setList)
    }
  }, [])
  return list
}

/** A press inside a toast's text. It never dismisses the toast; while `busy` its words go clear
 *  and a ring turns in its place, so the button keeps its box (D313). */
export function ToastPress({ busy = false, onPress, children }: { readonly busy?: boolean; readonly onPress: () => void; readonly children: ReactNode }) {
  return (
    <button type="button" className="bn-toast-action" data-busy={busy ? 'true' : undefined} aria-busy={busy || undefined} onClick={busy ? undefined : onPress}>
      {children}
    </button>
  )
}

export type ToastLineState = {
  readonly tone?: 'ok' | 'warn' | 'danger' | 'info'
  readonly icon?: IconName
  readonly text: ReactNode
  readonly press?: ReactNode
}

/** A line inside a toast that changes in place. Every state sits in one grid cell and only
 *  `current` shows, so the toast has its tallest state's box from the first paint and nothing
 *  under it moves when the words change (D313). */
export function ToastLine({ current, states }: { readonly current: string; readonly states: Readonly<Record<string, ToastLineState>> }) {
  return (
    <div className="bn-toast-line">
      {Object.entries(states).map(([key, state]) => (
        <div key={key} className="bn-toast-line-state" data-tone={state.tone} data-off={key === current ? undefined : 'true'} aria-hidden={key === current ? undefined : true}>
          <span className="bn-toast-line-text">
            {state.icon ? <Icon name={state.icon} size={14} /> : null}
            <span>{state.text}</span>
          </span>
          {state.press}
        </div>
      ))}
    </div>
  )
}

const ICONS: Record<ToastKind, IconName> = { receipt: 'undo', status: 'info', ok: 'check', refusal: 'alert' }

export function Toaster() {
  const list = useToasts()
  if (list.length === 0) return null
  return (
    <div className="bn-toasts" aria-live="polite">
      {list.map((t) => (
        <div key={t.id} className={`bn-toast bn-toast-${t.kind}${t.tone === 'danger' ? ' bn-toast-fault' : ''}`} role={t.kind === 'refusal' ? 'alert' : 'status'} data-leaving={t.leaving ? 'true' : undefined} aria-hidden={t.leaving ? true : undefined}>
          <Icon name={t.icon ?? ICONS[t.kind]} size={16} className="bn-toast-icon" />
          <div className="bn-toast-text">
            <div className="bn-toast-title">{t.title}</div>
            {t.body ? <div className="bn-toast-body">{t.body}</div> : null}
            {t.extra}
          </div>
          {t.action ? (
            <button
              type="button"
              className="bn-toast-action"
              onClick={() => {
                t.action?.onPress()
                dismissToast(t.id)
              }}
            >
              {t.action.label}
              {t.action.kbd ? <kbd className="bn-kbd">{t.action.kbd}</kbd> : null}
            </button>
          ) : null}
          <IconButton icon="x" label="Dismiss" size="sm" className="bn-toast-close" onClick={() => dismissToast(t.id)} />
          {t.ttlMs > 0 ? <span key={t.run ?? 0} className="bn-toast-drain" style={{ animationDuration: `${t.ttlMs}ms`, animationPlayState: t.held ? 'paused' : undefined }} /> : null}
        </div>
      ))}
    </div>
  )
}
