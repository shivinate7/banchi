const fs = require('fs');
const path = require('path');
const palettes = require('./palettes');

function tint(hex, alpha) {
  const n = parseInt(hex.replace('#',''), 16);
  const r = (n>>16)&255, g=(n>>8)&255, b=n&255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function cssFor(key, p) {
  return `/* ${p.name} — ${p.mood} */
:root[data-theme='dark'] {
  color-scheme: dark;

  --bn-bg: ${p.bg};
  --bn-surface: ${p.surface};
  --bn-surface-2: ${p.surface2};
  --bn-surface-3: ${p.surface3};
  --bn-surface-glass: ${tint(p.surface, 0.72)};
  --bn-hover: ${tint(p.ink, 0.05)};

  --bn-ink: ${p.ink};
  --bn-ink-2: ${p.ink2};
  --bn-ink-3: ${p.ink3};
  --bn-ink-4: ${p.ink4};

  --bn-line: ${p.line};
  --bn-line-strong: ${p.lineStrong};
  --bn-line-focus: ${tint(p.accent, 0.6)};

  --bn-accent: ${p.accent};
  --bn-accent-hover: ${p.accentHover};
  --bn-accent-press: ${p.accentPress};
  --bn-accent-tint: ${tint(p.accent, 0.16)};
  --bn-accent-tint-2: ${tint(p.accent, 0.26)};
  --bn-on-accent: ${p.onAccent};

  --bn-live: ${p.live};
  --bn-live-tint: ${tint(p.live, 0.18)};

  --bn-ok: ${p.ok};
  --bn-ok-tint: ${tint(p.ok, 0.16)};
  --bn-warn: ${p.warn};
  --bn-warn-tint: ${tint(p.warn, 0.16)};
  --bn-danger: ${p.danger};
  --bn-danger-tint: ${tint(p.danger, 0.16)};
  --bn-money: ${p.money};

  --bn-pill-ink-accent: ${p.accentHover};
  --bn-pill-ink-ok: ${p.ok};
  --bn-pill-ink-warn: ${p.warn};
  --bn-pill-ink-danger: ${p.danger};
  --bn-pill-ink-live: ${p.live};

  --bn-shadow-1: 0 1px 2px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.06);
  --bn-shadow-2: 0 1px 2px rgba(0, 0, 0, 0.5), 0 8px 24px -8px ${tint(p.accent, 0.35)},
    0 0 0 1px rgba(255, 255, 255, 0.07);
  --bn-shadow-3: 0 2px 4px rgba(0, 0, 0, 0.5), 0 24px 56px -16px ${tint(p.live, 0.4)},
    0 0 0 1px rgba(255, 255, 255, 0.08);
  --bn-shadow-accent: 0 8px 28px -8px ${tint(p.accent, 0.65)};

  --bn-btn-bg: var(--bn-surface-3);
  --bn-btn-bg-hover: ${p.surface3};
  --bn-btn-shadow: 0 0 0 1px var(--bn-line-strong), 0 1px 2px rgba(0, 0, 0, 0.4);

  /* the camera/photo stage keeps its own accent apart from the UI's, so the
     capture screen clashes on purpose against the shell around it */
  --bn-stage-accent: ${p.stageAccent};
  --bn-stage-accent-hover: ${tint(p.stageAccent, 1)};
  --bn-stage-ok: ${p.stageOk};
  --bn-stage-warn: ${p.stageWarn};
  --bn-stage-danger: ${p.stageDanger};
  --bn-stage-live: ${p.stageLive};

  /* text glow, cyberpunk sign-off */
  text-shadow: none;
}

/* ---- nav groups: each rail section takes its own hue (D-less, color only) ---- */
:root[data-theme='dark'] .bn-nav-group:nth-of-type(2) .bn-nav-group-label { color: ${p.navWorkflow}; }
:root[data-theme='dark'] .bn-nav-group:nth-of-type(2) .bn-nav-link[aria-current='page'] {
  color: ${p.navWorkflow};
  background: ${tint(p.navWorkflow, 0.14)};
  box-shadow: inset 2px 0 0 ${p.navWorkflow};
}
:root[data-theme='dark'] .bn-nav-group:nth-of-type(2) .bn-nav-link:hover { color: ${p.navWorkflow}; }

:root[data-theme='dark'] .bn-nav-group:nth-of-type(3) .bn-nav-group-label { color: ${p.navSell}; }
:root[data-theme='dark'] .bn-nav-group:nth-of-type(3) .bn-nav-link[aria-current='page'] {
  color: ${p.navSell};
  background: ${tint(p.navSell, 0.14)};
  box-shadow: inset 2px 0 0 ${p.navSell};
}
:root[data-theme='dark'] .bn-nav-group:nth-of-type(3) .bn-nav-link:hover { color: ${p.navSell}; }

:root[data-theme='dark'] .bn-nav-group:nth-of-type(4) .bn-nav-group-label { color: ${p.navLibrary}; }
:root[data-theme='dark'] .bn-nav-group:nth-of-type(4) .bn-nav-link[aria-current='page'] {
  color: ${p.navLibrary};
  background: ${tint(p.navLibrary, 0.14)};
  box-shadow: inset 2px 0 0 ${p.navLibrary};
}
:root[data-theme='dark'] .bn-nav-group:nth-of-type(4) .bn-nav-link:hover { color: ${p.navLibrary}; }

/* Home link (ungrouped, index 1) keeps the primary accent as its own job */
:root[data-theme='dark'] .bn-nav-group:nth-of-type(1) .bn-nav-link[aria-current='page'] {
  color: ${p.accent};
  background: var(--bn-accent-tint);
  box-shadow: inset 2px 0 0 ${p.accent};
}

/* segmented tabs (Pricing's To send / Live, etc.) alternate two clashing hues */
:root[data-theme='dark'] .bn-seg-item[aria-selected='true'],
:root[data-theme='dark'] .bn-seg-item.active {
  color: ${p.onAccent};
  background: ${p.accent};
}
:root[data-theme='dark'] .bn-seg-item:nth-of-type(2)[aria-selected='true'],
:root[data-theme='dark'] .bn-seg-item:nth-of-type(2).active {
  background: ${p.navSell};
}

/* the "Live" / server-online dot and any live badge reads the live hue already via
   --bn-live; the "Server online" status dot picks up bn-ok already through tokens */
`;
}

const OUT = __dirname;
for (const [key, p] of Object.entries(palettes)) {
  const file = path.join(OUT, `${key}.css`);
  fs.writeFileSync(file, cssFor(key, p));
  console.log('wrote', file);
}
