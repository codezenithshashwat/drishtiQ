// Use the installed TypeScript compiler and Node's local module hooks. No browser,
// downloads, bundled test framework or backend requests are needed for these checks.
import { registerHooks } from 'node:module'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
const project = new URL('../../', import.meta.url).href
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('.') && context.parentURL?.startsWith(project)) {
      const url = new URL(specifier, context.parentURL)
      if (!/\.[a-z]+$/i.test(url.pathname)) {
        for (const extension of ['.ts', '.tsx', '.js']) {
          const candidate = new URL(url.href + extension)
          if (existsSync(candidate)) return { url: candidate.href, shortCircuit: true }
        }
      }
    }
    return nextResolve(specifier, context)
  },
  load(url, context, nextLoad) {
    if (url.startsWith(project) && !url.includes('/node_modules/')) {
      if (/\.tsx?$/.test(url)) return { format: 'module', shortCircuit: true, source: ts.transpileModule(readFileSync(new URL(url), 'utf8'), {
        fileName: fileURLToPath(url), compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
      }).outputText }
      if (url.endsWith('.json')) return { format: 'module', shortCircuit: true, source: 'export default ' + readFileSync(new URL(url), 'utf8') }
    }
    return nextLoad(url, context)
  },
})
