/* THE STRING VALUES OF ONE NAMED OBJECT LITERAL IN A SOURCE FILE, READ BY THE LANGUAGE'S OWN PARSER.
 *
 * `ReviewQueue.tsx`'s `QUESTIONS` is a `const` that is not exported, and this change does not export
 * it (a product edit, outside this lane). So the unit tier reads its text from the source. A regex
 * over source text would be wrong at the first comment opener inside a string, so the TypeScript
 * parser does the reading. The cases in `unit/copy-rules.unit.ts` pin that: `//` and `/*` inside a
 * string, a multi-line template literal, and a lone quote in JSX text.
 *
 * It throws, rather than skipping, on anything that is not a plain string value. A label computed at
 * runtime cannot be checked here, and a silent skip would make the unit check pass over it. */
import ts from 'typescript'

/** Strips `as X`, `satisfies X` and parentheses, which a typed `const` wraps its literal in. */
function unwrap(expression: ts.Expression): ts.Expression {
  let node = expression
  while (ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isParenthesizedExpression(node)) {
    node = node.expression
  }
  return node
}

/** The first object literal bound to `name` by a `const` declaration, found by walking the tree. */
function findObjectLiteral(node: ts.Node, name: string): ts.ObjectLiteralExpression | undefined {
  if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === name && node.initializer) {
    const value = unwrap(node.initializer)
    if (ts.isObjectLiteralExpression(value)) return value
  }
  return ts.forEachChild(node, (child) => findObjectLiteral(child, name))
}

/** Props whose string value is drawn as text or read as a name (R4a): the JSX attributes and the
 *  object keys a screen passes its copy through. A string under any other key is not checked. */
const RENDERED_PROPS: ReadonlySet<string> = new Set([
  'label', 'title', 'placeholder', 'aria-label', 'hint', 'caption', 'heading', 'alt', 'text', 'detail', 'says',
])

/** The string pieces an expression can draw as text: a literal, a template's fixed parts, and each
 *  branch of a conditional or a logical operator. Anything else (a call, a variable) draws nothing this
 *  reader can see, and it is left unread rather than guessed. */
function renderedPieces(expression: ts.Expression, out: string[]): void {
  const node = unwrap(expression)
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
    out.push(node.text)
  } else if (ts.isTemplateExpression(node)) {
    out.push(node.head.text, ...node.templateSpans.map((span) => span.literal.text))
  } else if (ts.isConditionalExpression(node)) {
    renderedPieces(node.whenTrue, out)
    renderedPieces(node.whenFalse, out)
  } else if (ts.isBinaryExpression(node) && [ts.SyntaxKind.AmpersandAmpersandToken, ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken].includes(node.operatorToken.kind)) {
    renderedPieces(node.right, out)
  }
}

/** A first-person word: "I", "my", "me" or "mine" as a whole word, in any case (R4, R4a). */
const FIRST_PERSON = /(?<![\p{L}\p{N}_])(?:i|my|me|mine)(?![\p{L}\p{N}_])/giu

/** Quoted names that carry a first-person word and are not the app's own voice. `"My Pricing"` is the name
 *  of TCGplayer's page, a proper name the owner ruled to keep (wave 2, copy map row 10). The quotation marks
 *  mark it as a name, so only this exact quoted phrase is exempt. An unquoted `My Pricing` still counts. */
const NAMED_EXEMPT: readonly string[] = ['"My Pricing"']

/** One rendered string that carries a first-person word. `line` is 1-based. */
export interface VoiceFinding {
  readonly file: string
  readonly line: number
  readonly where: string
  readonly text: string
  readonly words: readonly string[]
}

/** Every rendered string in one `.tsx` source that carries "I", "my", "me" or "mine" as a whole word.
 *  Rendered means: a JSX text node, a string or template under a JSX expression child, a value of a
 *  `RENDERED_PROPS` JSX attribute, or a value of a `RENDERED_PROPS` object key. Comments are not
 *  strings and are never read. */
export function firstPersonInSource(source: string, file: string): VoiceFinding[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const found: VoiceFinding[] = []
  const at = (node: ts.Node): number => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
  const report = (node: ts.Node, where: string, text: string): void => {
    let scrubbed = text
    for (const quoted of NAMED_EXEMPT) scrubbed = scrubbed.split(quoted).join(' ')
    const words = Array.from(scrubbed.matchAll(FIRST_PERSON), (match) => match[0])
    if (words.length > 0) found.push({ file, line: at(node), where, text: text.replace(/\s+/g, ' ').trim(), words })
  }

  const visit = (node: ts.Node): void => {
    if (ts.isJsxText(node)) {
      report(node, 'JSX text', node.text)
    } else if (ts.isJsxExpression(node) && node.expression && node.parent && (ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent))) {
      const pieces: string[] = []
      renderedPieces(node.expression, pieces)
      for (const piece of pieces) report(node, 'JSX expression', piece)
    } else if (ts.isJsxAttribute(node) && ts.isIdentifier(node.name) && RENDERED_PROPS.has(node.name.text) && node.initializer) {
      const pieces: string[] = []
      if (ts.isStringLiteral(node.initializer)) pieces.push(node.initializer.text)
      else if (ts.isJsxExpression(node.initializer) && node.initializer.expression) renderedPieces(node.initializer.expression, pieces)
      for (const piece of pieces) report(node, `attribute ${node.name.text}`, piece)
    } else if (ts.isPropertyAssignment(node) && (ts.isIdentifier(node.name) || ts.isStringLiteral(node.name)) && RENDERED_PROPS.has(node.name.text)) {
      const pieces: string[] = []
      renderedPieces(node.initializer, pieces)
      for (const piece of pieces) report(node, `key ${node.name.text}`, piece)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return found
}

/** Every `key: 'value'` of the object literal named `name` in `source`, as a map. */
export function recordFromSource(source: string, name: string): Record<string, string> {
  const file = ts.createSourceFile('source.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const literal = findObjectLiteral(file, name)
  if (literal === undefined) throw new Error(`no object literal named ${name} in the source`)

  const out: Record<string, string> = {}
  for (const property of literal.properties) {
    if (!ts.isPropertyAssignment(property)) throw new Error(`${name} has an entry that is not "key: value"`)
    const key = property.name
    if (!ts.isIdentifier(key) && !ts.isStringLiteral(key)) throw new Error(`${name} has a computed key`)
    const value = unwrap(property.initializer)
    if (!ts.isStringLiteral(value) && !ts.isNoSubstitutionTemplateLiteral(value)) {
      throw new Error(`${name}.${key.text} is not a plain string, so it cannot be checked from source`)
    }
    out[key.text] = value.text
  }
  return out
}

/** One JSX opening or self-closing element of a `.tsx` source. `attrs` holds the named attributes;
 *  `spread` is true when the element also takes `{...props}`, which can supply any attribute, so a
 *  check that needs an attribute reads that element as unknown rather than as a finding. */
export interface JsxOpening {
  readonly tag: string
  readonly line: number
  readonly attrs: ReadonlyMap<string, ts.JsxAttribute>
  readonly spread: boolean
}

/** Every JSX opening element in `source`, read by the TypeScript parser (comments and strings are never
 *  elements). */
export function jsxOpeningsIn(source: string, file: string): JsxOpening[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const out: JsxOpening[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const attrs = new Map<string, ts.JsxAttribute>()
      let spread = false
      for (const property of node.attributes.properties) {
        if (ts.isJsxSpreadAttribute(property)) spread = true
        else attrs.set(property.name.getText(sf), property)
      }
      out.push({
        tag: node.tagName.getText(sf),
        line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1,
        attrs,
        spread,
      })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

/** The text an attribute carries: '' for a bare attribute, the value for a string, or the fixed text of
 *  a plain template or a string under `{...}`. `null` when the value is computed and this reader cannot
 *  see it, so a check skips it rather than guessing. */
export function attrText(attr: ts.JsxAttribute): string | null {
  const init = attr.initializer
  if (init === undefined) return ''
  if (ts.isStringLiteral(init)) return init.text
  if (ts.isJsxExpression(init) && init.expression) {
    const value = unwrap(init.expression)
    if (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) return value.text
  }
  return null
}
