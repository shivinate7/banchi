/**
 * The build-time demo flag, as a BARE IDENTIFIER a bundler can fold.
 *
 * `vite.config.ts` substitutes this with the literal `true` or `false` before Rollup sees the
 * source, so every `if (__BN_DEMO__)` in an ordinary build reads `if (false)` and is
 * eliminated along with the dynamic `import()` inside it.
 *
 * WHY NOT `import.meta.env.VITE_DEMO`, AND WHY NOT AN EXPORTED CONST — both were tried and
 * both leaked a production build, which is why this exists at all:
 *
 *   an exported `IS_DEMO` const     stays a live binding across the module boundary, so the
 *                                   branch survives. Shipped `demoCamera-*.js`.
 *   `import.meta.env.VITE_DEMO`     is only text-substituted for variables that are SET; an
 *                                   unset one stays a property read. Shipped it too.
 *   a module-local const from a
 *   defined `import.meta.env.*`     folds the simple guards but left the dynamic imports —
 *                                   `"" === '1'` at a declaration is not reliably folded
 *                                   into the binding.
 *
 * A bare identifier replaced by a boolean literal is the one form that removes all of it.
 * Declared here rather than in each consumer so there is one place saying what it is.
 *
 * THE STATEMENT FORM MATTERS TOO, which is the part no amount of defining fixes: the same
 * folded constant in `if (__BN_DEMO__) { … }` disappears completely, and in a TERNARY it
 * does not — the branch survived minification and pulled its dynamic import's chunk in with
 * it. Write these guards as `if`.
 *
 * WHAT A PRODUCTION BUILD ACTUALLY CONTAINS, measured rather than claimed: zero references
 * to any demo symbol — no `demoRequest`, no `demoStream`, no `demoDevices` — and no
 * `demoServer` chunk, which is the one that matters at 1.3 MB of recorded fixtures. Rollup
 * still EMITS a ~0.9 kB `demoCamera-*.js` orphan that nothing imports and no page ever
 * loads. That is dead weight in the output directory, not code in the app.
 */
declare const __BN_DEMO__: boolean
