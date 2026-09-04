import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Order matters: tokens define the custom properties base.css and every component read.
import './tokens.css'
import './base.css'
import './kit.css'

import { App } from './App'

// Step 7a's shell. The gallery was the whole app at step 6 and is now the /gallery route —
// it stays in the build because a component sheet that is rendered by the build is a
// component sheet that cannot go stale. App owns which of the three screens is showing;
// this file owns only the mount and the stylesheet order.
const root = document.getElementById('root')
if (root === null) throw new Error('index.html has no #root to mount into')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
