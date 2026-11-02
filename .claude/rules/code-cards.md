---
paths:
  - "codes/**"
  - "code-card-fork/**"
  - "docs/specs/code-cards.md"
  - "app/src/Codes.tsx"
  - "cli/cmd_scan.py"
  - "server/codes_routes.py"
---

# Code cards

The feature is DORMANT. Root `CLAUDE.md` marks it. `docs/specs/code-cards.md` is the spec. Read it before you build here.

- Never guess a code. No decode goes to the paid vision read, then a human.
- A QR that does not decode is a stop.
- Separate non-`BST` codes on sight. They are the scarce ones.
- No real code-card photo or code string in any tracked file. The pre-commit hook enforces it. The
  gitignored `inventory/` is the sanctioned place.
