import { supabase, supabaseConfigured } from '@/lib/supabase'

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
  const token = supabaseConfigured
    ? (await supabase.auth.getSession()).data.session?.access_token
    : undefined

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

export interface CampaignGoal {
  id: string
  amount_atomic: number
  amount_usdc: string
  benefit: string
}

export interface CampaignTier {
  id: string
  required_units: number
  benefit: string
  is_cumulative: boolean
  max_supply: number | null
  max_per_supporter: number | null
  uri: string | null
}

export interface Campaign {
  id: string
  athlete_profile_id: string
  plan_id: string
  title: string
  description: string
  unit_price_usdc: string
  unit_price_usdc_atomic: number
  minimum_success_threshold_usdc: string
  minimum_success_threshold_atomic: number
  main_goal_usdc: string | null
  main_goal_atomic: number | null
  start_at: string
  end_at: string
  metadata_uri: string | null
  metadata_hash: string | null
  status: string
  campaign_pda: string | null
  escrow_token_account: string | null
  chain_signature: string | null
  publish_confirmation_status: 'pending' | 'verified' | 'rejected' | null
  stretch_goals: CampaignGoal[]
  reward_tiers: CampaignTier[]
  created_at: string
  updated_at: string
}

export interface PlatformConfig {
  program_id: string
  usdc_mint: string
  usdc_decimals: number
  base_points_per_unit: number
  success_bonus_rate_bps: number
  max_active_units: number
  /** False when the deployment has no USDC mint, i.e. purchases cannot be built. */
  configured: boolean
}

export interface PurchaseIntent extends UnsignedTransaction {
  campaign_id: string
  purchased_units: number
  amount_atomic: number
  immediate_units: number
  pending_units: number
  confirmed_points: number
  pending_points: number
}

export interface PointsAccount {
  profile_id: string
  available_points: number
  pending_points: number
  updated_at: string
}

export interface PointLedgerEntry {
  id: string
  operation_type: string
  delta_points: number
  available_balance_after: number
  pending_balance_after: number
  campaign_id: string | null
  contribution_id: string | null
  transaction_reference: string | null
  created_at: string
}

export interface CosmeticItem {
  id: string
  name: string
  description: string
  support_points_price: number
  metadata_uri: string | null
  available_quantity: number | null
}

export interface RewardOffer {
  id: string
  athlete_profile_id: string
  reward_name: string
  description: string
  support_points_price: number
  available_quantity: number | null
  maximum_per_user: number | null
  availability_start: string | null
  availability_end: string | null
  fulfillment_type: string
  metadata_uri: string | null
  status: string
}

export interface SubscriptionPlan {
  id: string
  athlete_profile_id: string
  unit_price_usdc: string
  unit_price_usdc_atomic: number
  benefits: string
  status: string
  created_at?: string
  updated_at?: string
}

export interface AthleteProfile {
  id: string
  profile_id: string
  display_name: string
  sport: string | null
  bio: string | null
  avatar_uri: string | null
}

export interface CampaignGoalInput {
  amount_usdc: string
  benefit: string
}

export interface CampaignTierInput {
  required_units: number
  benefit: string
  is_cumulative: boolean
  max_supply: number | null
  max_per_supporter: number | null
  uri: string | null
}

export interface CampaignInput {
  plan_id: string
  title: string
  description: string
  start_at: string
  end_at: string
  minimum_success_threshold_usdc: string
  main_goal_usdc: string | null
  stretch_goals: CampaignGoalInput[]
  reward_tiers: CampaignTierInput[]
  metadata_uri?: string | null
}

export interface CampaignPublishIntent extends UnsignedTransaction {
  campaign_id: string
  publish_intent_id: string
  campaign_pda: string
  snapshot_hash: string
}

export interface CampaignPublishConfirmation {
  campaign_id: string
  publish_intent_id: string
  signature: string
  status: 'pending' | 'verified' | 'rejected'
  confirmed_at: string
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
  campaign: (id: string) => request<Campaign>(`/campaigns/${id}`),
  purchase: (id: string, body: {
    purchased_units: number
    source_token_account: string
    escrow_token_account: string
  }) => request<PurchaseIntent>(`/campaigns/${id}/purchase`, {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  points: () => request<PointsAccount>('/supporter/points'),
  pointLedger: (limit = 50) => request<PointLedgerEntry[]>(`/supporter/points/ledger?limit=${limit}`),
  cosmetics: () => request<CosmeticItem[]>('/store/cosmetics'),
  redeemCosmetic: (id: string) => request<unknown>(`/store/cosmetics/${id}/redeem`, { method: 'POST' }),
  rewardOffers: () => request<RewardOffer[]>('/reward-offers'),
  redeemReward: (id: string) => request<unknown>(`/reward-offers/${id}/redeem`, { method: 'POST' }),
  activateAthleteProfile: (body: { display_name: string; sport?: string; bio?: string; avatar_uri?: string }) =>
    request<AthleteProfile>('/profiles/me/athlete', { method: 'POST', body: JSON.stringify(body) }),
  athleteProfile: (body: { display_name: string; sport?: string; bio?: string; avatar_uri?: string }) =>
    request<AthleteProfile>('/profiles/me/athlete', { method: 'POST', body: JSON.stringify(body) }),
  myPlan: () => request<SubscriptionPlan | null>('/subscription-plans/me'),
  createPlan: (body: { unit_price_usdc: string; benefits: string }) =>
    request<SubscriptionPlan>('/subscription-plans', { method: 'POST', body: JSON.stringify(body) }),
  updatePlan: (id: string, body: { unit_price_usdc?: string; benefits?: string }) =>
    request<SubscriptionPlan>(`/subscription-plans/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  publishPlan: (id: string) => request<SubscriptionPlan>(`/subscription-plans/${id}/publish`, { method: 'POST' }),
  archivePlan: (id: string) => request<SubscriptionPlan>(`/subscription-plans/${id}/archive`, { method: 'POST' }),
  campaigns: (limit = 50) => request<Campaign[]>(`/campaigns?limit=${limit}`),
  myCampaigns: () => request<Campaign[]>('/athlete/campaigns'),
  createCampaign: (body: CampaignInput) =>
    request<Campaign>('/athlete/campaigns', { method: 'POST', body: JSON.stringify(body) }),
  updateCampaign: (id: string, body: Omit<CampaignInput, 'plan_id'>) =>
    request<Campaign>(`/athlete/campaigns/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  cancelCampaign: (id: string) =>
    request<Campaign>(`/athlete/campaigns/${id}/cancel`, { method: 'POST' }),
  publishCampaign: (id: string, body: { escrow_token_account: string }) => request<CampaignPublishIntent>(
    `/athlete/campaigns/${id}/publish`, { method: 'POST', body: JSON.stringify(body) }),
  confirmCampaign: (id: string, body: { signature: string; campaign_pda: string }) =>
    request<CampaignPublishConfirmation>(`/athlete/campaigns/${id}/publish/confirm`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  config: () => request<PlatformConfig>('/config'),
}
