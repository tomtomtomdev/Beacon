import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// vitest runs without injected globals, so testing-library's automatic
// per-test cleanup never registers — do it explicitly.
afterEach(() => {
  cleanup()
})
