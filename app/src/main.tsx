import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Order matters: tokens define the custom properties base.css and every component read.
import './tokens.css'
import './base.css'

import { Gallery } from './Gallery'

// The gallery is the whole app at step 6. Step 7 mounts the real capture app here and
// moves the gallery to its own route — it is worth keeping, because a component sheet
// that is rendered by the build is a component sheet that cannot go stale.
const root = document.getElementById('root')
if (root === null) throw new Error('index.html has no #root to mount into')

createRoot(root).render(
  <StrictMode>
    <Gallery />
  </StrictMode>,
)
