/* SCRATCH harness: the neighbour-row mark alone, scaled up, replaying its one-shot glint. */
import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'

import './tokens.css'
import './base.css'
import './kit.css'
import './PlaceNeighbors.css'
import { Logo } from './kit'

const q = new URLSearchParams(window.location.search)
if (q.get('t') === 'dark') document.documentElement.setAttribute('data-theme', 'dark')
const part = q.get('part') === 'card-small' ? 'card-small' : 'both'

function Harness() {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (n >= 3) return
    const t = setTimeout(() => setN(n + 1), n === 0 ? 1200 : 2200)
    return () => clearTimeout(t)
  }, [n])
  return (
    <div style={{ display: 'grid', placeItems: 'center', height: '100vh', background: 'var(--bn-bg)' }}>
      <span className="nb-here" style={{ zoom: 16 }}>
        <Logo part={part} size={18} glint key={n} />
      </span>
    </div>
  )
}
createRoot(document.getElementById('root')!).render(<Harness />)
