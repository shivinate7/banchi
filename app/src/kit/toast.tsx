import { useEffect, useState } from 'react'
import { Icon, type IconName } from './Icon'
import { IconButton } from './index'

/* One toast stack for the whole product. Any screen may call toast(); the shell renders
   <Toaster/> once. Receipts carry an undo; status toasts expire; refusals stay until dismissed. */

export type ToastKind = 'receipt' | 'status' | 'ok' | 'refusal'
export type Toast = {
  readonly id: number
  readonly kind: ToastKind
  readonly title: string
  readonly body?: string
  readonly icon?: IconName
  readonly ttlMs: number
  readonly action?: { readonly label: string; readonly kbd?: string; readonly onPress: () => void }
  /** Dismissed and folding away; gone from the list one beat later. */
  readonly leaving?: boolean
}
type ToastInput = Omit<Toast, 'id' | 'ttlMs' | 'leaving'> & { readonly ttlMs?: number }
/** How long a dismissed toast stays mounted to fold away — kit.css's `bn-toast-out` (--bn-t). */
const LEAVE_MS = 220

type Listener = (toasts: readonly Toast[]) => void
const listeners = new Set<Listener>()
let toasts: readonly Toast[] = []
let nextId = 1

function emit(): void {
  for (const listener of listeners) listener(toasts)
}

export function dismissToast(id: number): void {
  const hit = toasts.find((t) => t.id === id)
  if (hit === undefined || hit.leaving) return
  toasts = toasts.map((t) => (t.id === id ? { ...t, leaving: true } : t))
  emit()
  window.setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id)
    emit()
  }, LEAVE_MS)
}

export function toast(input: ToastInput): number {
  const id = nextId++
  const ttlMs = input.ttlMs ?? (input.kind === 'receipt' ? 20000 : input.kind === 'refusal' ? 0 : 5000)
  const next: Toast = { ...input, id, ttlMs }
  toasts = [...toasts.slice(-4), next]
  emit()
  if (ttlMs > 0) window.setTimeout(() => dismissToast(id), ttlMs)
  return id
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

const ICONS: Record<ToastKind, IconName> = { receipt: 'undo', status: 'info', ok: 'check', refusal: 'alert' }

export function Toaster() {
  const list = useToasts()
  if (list.length === 0) return null
  return (
    <div className="bn-toasts" aria-live="polite">
      {list.map((t) => (
        <div key={t.id} className={`bn-toast bn-toast-${t.kind}`} role={t.kind === 'refusal' ? 'alert' : 'status'} data-leaving={t.leaving ? 'true' : undefined}>
          <Icon name={t.icon ?? ICONS[t.kind]} size={16} className="bn-toast-icon" />
          <div className="bn-toast-text">
            <div className="bn-toast-title">{t.title}</div>
            {t.body ? <div className="bn-toast-body">{t.body}</div> : null}
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
          {t.ttlMs > 0 ? <span className="bn-toast-drain" style={{ animationDuration: `${t.ttlMs}ms` }} /> : null}
        </div>
      ))}
    </div>
  )
}
