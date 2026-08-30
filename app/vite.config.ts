import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { CAPTURE_PORT, CAPTURE_URL, DEV_PORT } from './devPort'

// Port 5173 is not Vite's default acting by accident — CLAUDE.md and the Makefile's `dev`
// target both promise :5173, and scripts/views.txt points the screenshot runner there.
// strictPort so a busy port fails loudly instead of serving on 5174, where every one of
// those three would be quietly wrong.
// THE CLIENT LEARNS ITS OWN TREE'S CAPTURE SERVER FROM HERE (D43). `app/src/server.ts` asked
// for `http://localhost:8000` no matter which checkout served it, while `store/files.py:home()`
// already gave every checkout its own inventory — so tree A's UI was answered by whichever
// server won the bind, over THAT tree's store. Injected rather than read from a `.env` file
// because there is nothing for a human to keep in step: the value is derived from where the
// checkout is, by the same slot that decides the port Vite is listening on two lines up.
//
// VITE_CAPTURE_SERVER still wins over this. That is the operator's explicit override and the
// case docs/specs/capture-app.md §11 leaves open — the Fulfiller's device pointed at this Mac
// by address. A derived default is a better default; it is not a reason to take the knob away.
// THE PORT IS INJECTED BESIDE THE URL, AND app/src/server.ts PREFERS IT. The URL's host is
// `localhost`, which is right at the desk and wrong from anywhere else — on a phone
// `localhost` is the phone. Composing the base from `location.hostname` plus this port keeps
// the per-checkout guarantee above (the port still comes from this tree's slot, so a
// worktree's UI still cannot be answered by another tree's server) while letting the page be
// opened by any name that reaches this Mac. The URL stays for callers that have no `location`
// — `tsc`, the specs' module imports — where there is no address bar to follow.
//
// `server.host` so Vite answers on the LAN at all. The capture server has bound 0.0.0.0 since
// it was written; Vite was the half still listening only on the loopback, so the app could not
// be opened from the phone even though its server could be reached.
export default defineConfig({
  plugins: [react()],
  server: { port: DEV_PORT, strictPort: true, host: true },
  define: {
    'import.meta.env.VITE_CAPTURE_DEFAULT': JSON.stringify(CAPTURE_URL),
    'import.meta.env.VITE_CAPTURE_PORT': JSON.stringify(CAPTURE_PORT),
  },
})
