// Protects: a press the app has taken and queued reads as queued on the kit Button, and a second press does not reach the caller.
// Governs: D329 (a taken press answers at once); docs/specs/undo.md section 10
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { createElement, Fragment, type ReactElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { expect, test } from './unit'
import { lifted } from './lifted'

/* THE KIT'S OWN `Button`, RUN HERE WITHOUT A BROWSER. The kit index imports `overlay.tsx`, which imports
 * `dialog.css`, and the unit tier cannot load CSS. So the case lifts `Button` from the kit source, strips
 * its types and runs it, with `Icon` and `Kbd` stubbed (neither sets a Button attribute). `Button` has no
 * hooks, so calling it returns the element a DOM would receive: `renderToStaticMarkup` gives its markup,
 * and the element's props give `disabled` and the click handler a press calls. */
const KIT = readFileSync(new URL('../../src/kit/index.tsx', import.meta.url), 'utf8')
type Props = Record<string, unknown>
type Rendered = ReactElement<Props>
const Button = runInNewContext(`${lifted(KIT, 'Button', 'function')}\nButton`, {
  React: { createElement },
  Icon: () => null,
  Kbd: () => null,
}) as (props: Props) => Rendered

const markup = (props: Props): string => renderToStaticMarkup(createElement(Button, props))
const rendered = (props: Props): Rendered => Button(props)

/* THE KIT'S OWN `IconButton`, LIFTED THE SAME WAY, WITH ITS HOOKS STUBBED. `IconButton` keeps `useState`, `useRef` and
 * `useId`, and portals its tip: only a DOM render supports those. The case calls it once, outside a render, so each hook
 * is a plain stub that returns its first value, and `createPortal` returns its node. The element it returns is the
 * `<button>` a DOM would receive, and its `onClick` is the handler a press calls. `import.meta.env.DEV` reads as `false`,
 * since a vm script cannot parse `import.meta`. Its text is read here, never copied. */
const KIT_FOR_VM = KIT.replaceAll('import.meta.env.DEV', 'false')
const IconButton = runInNewContext(
  `${lifted(KIT_FOR_VM, 'FACE_PX', 'const')}\n${lifted(KIT_FOR_VM, 'GLYPH_PX', 'const')}\n${lifted(KIT_FOR_VM, 'IconButton', 'function')}\nIconButton`,
  {
    React: { createElement, Fragment },
    Icon: () => null,
    Kbd: () => null,
    createPortal: (node: unknown) => node,
    document: { body: null },
    useId: () => ':t:',
    useRef: (initial: unknown) => ({ current: initial }),
    useState: (initial: unknown) => [initial, () => undefined],
  },
) as (props: Props) => Rendered

const QUEUED = 'queued'

test('a queued press draws data-busy queued, not the busy ring, and keeps its label', () => {
  const html = markup({ busy: QUEUED, children: 'Send' })
  expect(html, 'the queued face is its own state, so it must not draw the busy ring').toContain('data-busy="queued"')
  expect(html, 'the label stays on the face while the press waits its turn').toContain('>Send</button>')
})

test('a queued press is announced busy and refused to assistive tech, and never sets the disabled attribute', () => {
  const html = markup({ busy: QUEUED, children: 'Send' })
  expect(html, 'assistive tech must hear that the press is busy').toContain('aria-busy="true"')
  expect(html, 'assistive tech must hear that the press is refused').toContain('aria-disabled="true"')
  expect(rendered({ busy: QUEUED, children: 'Send' }).props.disabled, 'disabled paints the refused look (0.45), so a queued press must not set it').toBeUndefined()
})

test('a queued press ignores a click: the caller onClick is not called', () => {
  let clicks = 0
  const element = rendered({ busy: QUEUED, children: 'Send', onClick: () => { clicks += 1 } })
  const onClick = element.props.onClick as ((event: unknown) => void) | undefined
  onClick?.({})
  expect(clicks, 'a second press while queued must not reach the caller, so it queues nothing').toBe(0)
})

test('control: busy true still draws the busy ring, not the queued mark', () => {
  const html = markup({ busy: true, children: 'Send' })
  expect(html, 'the busy ring keeps its own mark').toContain('data-busy="true"')
  expect(html, 'busy true is not the queued state').not.toContain('data-busy="queued"')
})

test('control: a button with no busy prop draws no busy mark', () => {
  expect(markup({ children: 'Send' })).not.toContain('data-busy')
})

test('a queued IconButton ignores a click: the caller onClick is not called', () => {
  let clicks = 0
  const element = IconButton({ icon: 'undo', label: 'Undo sale', busy: QUEUED, onClick: () => { clicks += 1 } })
  const onClick = element.props.onClick as ((event: { preventDefault: () => void }) => void) | undefined
  onClick?.({ preventDefault: () => undefined })
  expect(clicks, 'a second press while queued must not reach the caller, so it queues nothing').toBe(0)
})

test('control: an IconButton with no busy prop passes its click to the caller', () => {
  let clicks = 0
  const element = IconButton({ icon: 'undo', label: 'Undo sale', onClick: () => { clicks += 1 } })
  const onClick = element.props.onClick as ((event: { preventDefault: () => void }) => void) | undefined
  onClick?.({ preventDefault: () => undefined })
  expect(clicks, 'a press that is not queued reaches the caller').toBe(1)
})
