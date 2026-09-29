6. ~~Design tokens locked and one component built against them~~ — done 2026-08-12.
   Tokens locked by interview against rendered alternatives rather than by inference; the
   pull-confirm built against them at `app/src/PullConfirm.tsx`, in all three states, on a
   gallery route `make screenshot` renders and `make design-check` asserts.
   **Building it earned its place**: it caught two points where
   the static palette sheet contradicted `docs/DESIGN.md`. One was an 18px button label under
   the view's own 20px floor. The other was a keyboard chip on a control only the Fulfiller
   touches. `docs/DESIGN.md` now holds both findings. Neither was visible in prose.