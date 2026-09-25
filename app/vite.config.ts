import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { CAPTURE_PORT, CAPTURE_URL, DEV_PORT } from './devPort'
import { checkoutIdentityPlugin } from './checkoutIdentity'

// THE RECORDING WHEN THERE IS ONE, THE TYPE-ONLY STUB WHEN THERE IS NOT — the same ordered
// fallback `app/tsconfig.json` gives the `#demo-bundle` alias, spelled a second time because
// VITE DOES NOT READ tsconfig `paths`. Getting that wrong is not subtle: the alias typechecked
// and then failed the build with `Rollup failed to resolve "#demo-bundle"`.
//
// The stub is reachable at build time, not only at typecheck time, because `demoServer.ts`
// enters Rollup's graph even in an ordinary build — measured, not assumed. `make demo-static`
// seeds and records before it compiles, so the real file is what the demo ships.
const demoBundle = fileURLToPath(new URL('./demo/bundle.json', import.meta.url))
const demoBundleStub = fileURLToPath(new URL('./src/demoBundle.stub.ts', import.meta.url))

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
// `server.host` so Vite answers on the LAN at all. The capture server has bound every
// interface since it was written; Vite was the half still listening only on the loopback, so
// the app could not be opened from the phone even though its server could be reached.
export default defineConfig({
  // WHERE THE BUILD WILL BE SERVED FROM, and it is a build input because only the publisher
  // knows. GitHub Pages serves a project site under `/<repo>/`, not at the root, and a bundle
  // built for `/` 404s every asset there while working perfectly on localhost — a failure
  // that appears only once it is published, which is the worst moment to find it. Defaults to
  // `/` so every ordinary build and `make dev` are untouched; `make demo-static` passes the
  // subdirectory. `photoUrl` composes the demo's photographs against `import.meta.env.BASE_URL`
  // for the same reason.
  base: process.env.DEMO_BASE ?? '/',
  // `checkoutIdentityPlugin` answers `GET /__checkout` with this checkout's path, so a test
  // run that reuses a server can prove it is this tree's (checkoutIdentity.ts).
  plugins: [react(), checkoutIdentityPlugin()],
  server: {
    port: DEV_PORT,
    strictPort: true,
    host: true,
    // `host: true` makes Vite LISTEN on every interface; it does not make it ACCEPT every
    // name. Vite refuses a request whose Host header it does not recognise — DNS-rebinding
    // protection — so reaching this app at `pkmnscan.lan` returned "Blocked request. This
    // host is not allowed." while the bare IP worked fine. Found by opening the real
    // hostname rather than the address, which is the only test that could have caught it.
    //
    // TWO LOCAL SUFFIXES, NOT `true`. `true` switches the protection off for every name;
    // a leading dot allows a domain and its subdomains, so this admits `pkmnscan.lan` and
    // `MacBook-Pro-2.local` and still refuses an arbitrary public hostname pointed at this
    // machine. Both suffixes are non-routable on the public internet, which is what makes
    // the narrowing meaningful rather than decorative. Localhost and bare IPs are allowed
    // by Vite already and need no entry.
    allowedHosts: ['.lan', '.local'],
  },
  resolve: {
    alias: {
      '#demo-bundle': existsSync(demoBundle) ? demoBundle : demoBundleStub,
    },
  },
  define: {
    'import.meta.env.VITE_CAPTURE_DEFAULT': JSON.stringify(CAPTURE_URL),
    'import.meta.env.VITE_CAPTURE_PORT': JSON.stringify(CAPTURE_PORT),
    // DEFINED HERE OR IT DOES NOT FOLD, and this one is a correctness matter rather than a
    // size one. `make demo-static` builds with VITE_DEMO=1; every other build must eliminate
    // the demo branches entirely, including the dynamic `import()`s of `demoServer.ts` and
    // `demoCamera.ts` inside them.
    //
    // A BARE IDENTIFIER CARRYING A BOOLEAN, not an `import.meta.env` read, and the three
    // forms that did NOT work are recorded in `src/demoFlag.d.ts` beside the declaration.
    // The short version: only this form makes the guard read `if (false)` in the source
    // Rollup sees, which is what removes the branch AND the dynamic import inside it.
    __BN_DEMO__: JSON.stringify(process.env.VITE_DEMO === '1'),
  },
})
