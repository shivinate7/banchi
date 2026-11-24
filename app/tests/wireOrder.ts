/* THE ORDER OF A PAGE'S REQUESTS. A write's read-back is a request that leaves after the write, so a case asserts that
   order, never a bare count: a timer's read can land anywhere, and a read from before the press proves nothing. One home
   for both specs that assert it (`pricing.spec.ts`, `run-panel.spec.ts`). */
import type { Page } from '@playwright/test'

export type Sent = { method: string; path: string }

/** Records each request the page sends, in the order it leaves. Register it before the press. */
export function recordSent(page: Page): Sent[] {
  const sent: Sent[] = []
  page.on('request', (request) => sent.push({ method: request.method(), path: new URL(request.url()).pathname }))
  return sent
}

/** True when a GET of `readPath` was sent after the first `method` request to `writePath`. Works on any list of requests in send order. */
export function readAfterWrite(sent: readonly Sent[], method: string, writePath: string, readPath: string): boolean {
  const at = sent.findIndex((r) => r.method === method && r.path === writePath)
  return at >= 0 && sent.slice(at + 1).some((r) => r.method === 'GET' && r.path === readPath)
}

/** `readAfterWrite` for a POST, with the read defaulting to the same path. */
export function readAfterPost(sent: readonly Sent[], postPath: string, readPath: string = postPath): boolean {
  return readAfterWrite(sent, 'POST', postPath, readPath)
}
