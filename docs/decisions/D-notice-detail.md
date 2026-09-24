## D-notice-detail — The machine's words go behind "What the server said"

**This amends D196's one exemption.** D196 exempted `Notice`'s `code` prop from the rule that no user-visible string names a mechanism. Its premise was that the raw string "stays available on hover and in the run log". The review found that premise false (UX-038, COPY-24). The code drew in plain view, under every refusal, on eight screens. Server text drew verbatim, so request paths and a repository command reached the owner.

**The owner's ruling, 2026-09-23:** codes go behind a details disclosure.

**What changes.** `Notice` keeps its `code` prop and gains `detail`, for server text that holds a path, a command or a code. Both draw inside a `<details>` element whose summary reads "What the server said". It is closed by default. The sentence above it is the person's sentence. Capture already drew its server text this way, and that is the shape the kit now uses everywhere.

**What D196 protected, and what protects it now.** D196 protected the owner from pipeline nouns on screen. The disclosure keeps the words one press away for a bug report and out of plain view. The machine-words browser check, in the text-checks lane, reads rendered `innerText`. A closed `<details>` contributes its summary only, so the check reads what the owner sees.

**Two shapes for a failure (UX-041).** `Refusal` says that the press cannot be done here, and it offers no retry. `Retry` offers "Try again", and the button shows that it is trying. `server.ts:describeFailure` now says which shape a failure is (`kind`), and `FailureNotice` picks the shape. `FailureNotice` never uses the server's message as its title. The title is a plain sentence, and the server's words go behind the disclosure.

**The demo says one sentence.** Every refusal in `app/src/demoServer.ts` now says "Not in this demo." (TXT-46). The code still names the refusal, behind the disclosure.
