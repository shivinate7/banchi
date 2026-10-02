import { useState } from 'react'
import type { ReactNode } from 'react'

import {
  CardPicker,
  SettingsCensus,
  SettingsEditor,
  SettingsFigures,
  SettingsGroup,
  SettingsOp,
  SettingsTrouble,
  useSheetWrite,
  type PickGroup,
} from './settings'

/* The settings sheet's parts, drawn on the kit page with invented data. Nothing here reads the
 * store. The write below is a stand-in that waits a moment and then either answers or refuses,
 * so the row's own ring and the refusal panel are the real ones. */

function Specimen({ name, children }: { readonly name: string; readonly children: ReactNode }) {
  return (
    <div className="bn-stack" style={{ gap: 'var(--bn-2)', maxWidth: 420 }} data-specimen={name}>
      <p className="bn-label">{name}</p>
      {children}
    </div>
  )
}

const GROUPS: readonly PickGroup[] = [
  { key: 'a', title: 'Section 1', cards: [1, 2, 3].map((n) => ({ index: n, label: `Card ${n}` })) },
  { key: 'b', title: 'Section 2', cards: [4, 5].map((n) => ({ index: n, label: `Card ${n}` })) },
]

export function SettingsSpecimens() {
  const [picked, setPicked] = useState<readonly number[] | null>(null)
  const [editing, setEditing] = useState(false)
  const [running, setRunning] = useState<'ok' | 'refuse' | null>(null)
  const { busy, trouble, write } = useSheetWrite(() => undefined)

  const press = (kind: 'ok' | 'refuse') => {
    setRunning(kind)
    void write(
      () =>
        new Promise<string>((resolve, reject) =>
          window.setTimeout(() => (kind === 'ok' ? resolve('done') : reject(new Error('The write was refused.'))), 900),
        ),
    ).finally(() => setRunning(null))
  }

  return (
    <div className="bn-stack" style={{ gap: 'var(--bn-5)' }}>
      <Specimen name="SettingsFigures and SettingsCensus">
        <SettingsFigures title="Overview">
          <SettingsCensus label="Total" value={640} />
          <SettingsCensus label="Open" value={504} />
          <SettingsCensus label="Unknown" value={null} help="A missing figure is a dash, never a zero." />
          <SettingsCensus label="Held" value={12} note="Recent, 18 days" />
        </SettingsFigures>
      </Specimen>

      <Specimen name="SettingsGroup and SettingsOp">
        <SettingsGroup title="Group" note="A note beside the head">
          <SettingsOp icon="pencil" label="Rename" detail="Shelf A" busy={busy} onClick={() => setEditing(true)} />
          <SettingsOp icon="divider" label="Waiting on a step" detail="declare it first" busy={busy} disabled onClick={() => undefined} />
          <SettingsOp icon="moveTo" label="Write that works" detail="2 items" busy={busy} running={running === 'ok'} onClick={() => press('ok')} />
        </SettingsGroup>
        <SettingsGroup title="Danger" danger>
          <SettingsOp icon="x" label="Write that refuses" detail="2 items" busy={busy} running={running === 'refuse'} danger onClick={() => press('refuse')} />
        </SettingsGroup>
        <SettingsTrouble failure={trouble} />
      </Specimen>

      <Specimen name="SettingsEditor">
        {editing ? (
          <SettingsEditor title="Rename" onBack={() => setEditing(false)}>
            <p className="bn-lede">The screen's own editor goes here.</p>
          </SettingsEditor>
        ) : (
          <p className="bn-lede">Press Rename above to open one.</p>
        )}
      </Specimen>

      <Specimen name="CardPicker">
        <CardPicker whole="Whole shelf" sections={GROUPS} picked={picked} onChange={setPicked} />
      </Specimen>
    </div>
  )
}
