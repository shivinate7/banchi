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
