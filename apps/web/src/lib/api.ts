import { supabase } from '@/lib/supabase'

/**
 * Typed client for the FastAPI backend.
 *
 * In dev, requests go to /api and Vite proxies them (see vite.config.ts) so the
 * browser sees one origin. In production set VITE_API_BASE_URL to the deployed
 * API and make sure that origin is in the backend's CORS allow-list.
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export class ApiError extends Error {
  // Declared as fields rather than constructor parameter properties: the Vite
  // template enables `erasableSyntaxOnly`, which forbids the shorthand.
  readonly status: number
  readonly detail?: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  // Read the token per-request rather than caching it: supabase-js refreshes in
  // the background, and a stale copy means intermittent 401s that are miserable
  // to debug.
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token

  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers })

  if (!response.ok) {
    let detail: unknown
    try {
      detail = (await response.json())?.detail
    } catch {
      detail = await response.text().catch(() => undefined)
    }
    throw new ApiError(
      response.status,
      typeof detail === 'string' ? detail : `Request failed: ${response.status}`,
      detail,
    )
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export interface UnsignedTransaction {
  transaction: string
  blockhash: string
  last_valid_block_height: number
  simulation_logs: string[]
}

export interface Profile {
  id: string
  wallet: string | null
  display_name: string | null
  created_at: string
}

export interface CounterEvent {
  signature: string
  counter: string
  authority: string
  count: number
  slot: number
  block_time: string | null
}

export type CheckStatus = 'ok' | 'degraded' | 'error'

export interface Check {
  name: string
  status: CheckStatus
  target: string
  latency_ms: number | null
  detail: Record<string, unknown>
  error: string | null
}

export interface Diagnostics {
  status: CheckStatus
  environment: string
  checks: Check[]
}

export interface SimulatedIngest {
  signature: string
  derived: number
  counter: string
  authority: string
  count: number
}

export const api = {
  diagnostics: () => request<Diagnostics>('/diagnostics'),
  simulateIngest: () => request<SimulatedIngest>('/diagnostics/simulate-ingest', { method: 'POST' }),
  me: () => request<Profile>('/profiles/me'),
  updateMe: (displayName: string) =>
    request<Profile>('/profiles/me', {
      method: 'PATCH',
      body: JSON.stringify({ display_name: displayName }),
    }),
  counterEvents: (limit = 25) => request<CounterEvent[]>(`/events/counter?limit=${limit}`),
  buildInitialize: () => request<UnsignedTransaction>('/tx/initialize', { method: 'POST' }),
  buildIncrement: () => request<UnsignedTransaction>('/tx/increment', { method: 'POST' }),
  counterAddress: () => request<{ address: string; bump: string }>('/tx/counter-address'),
}
