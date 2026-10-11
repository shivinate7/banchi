6. ~~Design tokens locked and one component built against them~~ — done.
   Tokens locked by interview against rendered alternatives, not by inference. The
   pull-confirm was built against them at `app/src/PullConfirm.tsx`, in all three states, on a
   gallery route that `make screenshot` renders and `make design-check` asserts.
   Building it caught two points where the static palette sheet contradicted
   `docs/DESIGN.md`: an 18px button label under the view's 20px floor, and a keyboard chip on
   a control only the Fulfiller touches. `docs/DESIGN.md` now holds both findings. Neither
   was visible in prose.
