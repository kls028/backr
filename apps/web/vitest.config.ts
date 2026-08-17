import path from 'node:path'
import { defineConfig } from 'vitest/config'

// Separate from vite.config.ts so dev-server concerns (proxy, host binding,
// envDir) stay out of the test run. Only the `@/` alias is shared.
export default defineConfig({
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
})
