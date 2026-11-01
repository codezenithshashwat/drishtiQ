// @ts-expect-error -- @types/node is not installed; this config runs under Node, where the module exists
import { execSync } from 'node:child_process'
// @ts-expect-error -- as above
import { existsSync, readFileSync } from 'node:fs'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

// The build records the commit it was built from; the app compares it with the backend's commit (/api/version).
const commit = (() => {
  try {
    return execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    // A copy without git history (project zip) carries its stamp in BUILD_COMMIT.
    return existsSync('../BUILD_COMMIT') ? readFileSync('../BUILD_COMMIT', 'utf8').trim() : 'unknown'
  }
})()

// The dev server proxies API calls to the FastAPI backend on :8000.
// build-info.json lets preflight check that the built page matches the code it is about to start.
const buildInfo: Plugin = { name: 'build-info', generateBundle() { this.emitFile({ type: 'asset', fileName: 'build-info.json', source: JSON.stringify({ commit }) }) } }

export default defineConfig({
  plugins: [react(), buildInfo],
  define: { __BUILD_COMMIT__: JSON.stringify(commit) },
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000', '/report-fonts': 'http://127.0.0.1:8000' } },
})
