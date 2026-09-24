import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '../../src/tokens.css'
import '../../src/base.css'
import '../../src/kit.css'

import { DataSpecimens } from '../../src/kit/data.specimens'

/* THE TEST PAGE FOR THE KIT'S DATA PRIMITIVES. `?theme=dark` draws the dark theme. */
if (new URLSearchParams(window.location.search).get('theme') === 'dark') {
  document.documentElement.setAttribute('data-theme', 'dark')
}

const root = document.getElementById('root')
if (root === null) throw new Error('the test page has no #root to mount into')

createRoot(root).render(
  <StrictMode>
    <main style={{ padding: 'var(--bn-4)', background: 'var(--bn-bg)', minHeight: '100vh' }}>
      <DataSpecimens />
    </main>
  </StrictMode>,
)
