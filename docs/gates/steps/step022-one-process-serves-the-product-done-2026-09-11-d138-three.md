22. ~~**One process serves the product**~~ — **done 2026-09-11.** D138, three PRs the same
    day. The capture server serves `app/dist/` beside the API, narrowly — the root and the
    build's own files, never a catch-all, because a hash router has no deep links and a
    catch-all turned `GET /boxes/abc` into 200 HTML and would have retired a dozen named
    refusals with nothing failing. The supervisor dropped its Vite child and builds into a
    sibling directory it renames in, on its own watch set over `app/src` and `app/public`: a
    Python edit restarts the capture child and never builds, and a screen edit does the
    reverse. `make dev` runs beside it now on its own port, which is the loop the owner
    alternates into. Covered by T7's `check_app_serve` and the new `serve-selftest`; seven
    mutations were observed failing the two. **What this step did NOT do**: the dock app is
    still installed at `:5173` and `make lan-check` has not been run from the phone. Both are
    presses on the owner's own machine, and the first resets the camera grant and the six
    device-local keys once, because a port is part of an origin (D108, amended).
