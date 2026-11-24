// Lifts one top-level declaration out of a TS or TSX source, for a unit case that must run product code.
// A module that imports CSS or the browser cannot load in the unit tier, so the case reads the file and
// asks the language's own parser for the declaration. The parser reads past comment openers inside
// strings, a multi-line template literal and a lone quote in JSX text.
import ts from 'typescript'

export function lifted(source: string, name: string, kind: 'function' | 'const'): string {
  const file = ts.createSourceFile('source.tsx', source, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TSX)
  const found = file.statements.filter((s): s is ts.FunctionDeclaration | ts.VariableStatement => kind === 'function'
    ? ts.isFunctionDeclaration(s) && s.name?.text === name
    : ts.isVariableStatement(s) && s.declarationList.declarations.some((d) => ts.isIdentifier(d.name) && d.name.text === name))
  const [node] = found
  if (found.length !== 1 || node === undefined) throw new Error(`expected one top-level ${kind} ${name}, found ${found.length}`)
  const text = node.getText(file).replace(/^export\s+/, '')
  return ts.transpileModule(text, { compilerOptions: { target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React } }).outputText
}
