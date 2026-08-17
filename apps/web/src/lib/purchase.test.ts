import { describe, expect, it } from 'vitest'

import { estimatePurchase, formatUsdc, highestTier } from '@/lib/purchase'
import type { Campaign, CampaignTier } from '@/lib/api'

const CONFIG = { base_points_per_unit: 100, success_bonus_rate_bps: 2_000 }

function tier(id: string, requiredUnits: number, benefit: string): CampaignTier {
  return {
    id,
    required_units: requiredUnits,
    benefit,
    is_cumulative: true,
    max_supply: null,
    max_per_supporter: null,
    uri: null,
  }
}

function campaign(overrides: Partial<Campaign> = {}): Campaign {
  return {
    id: 'c1',
    athlete_profile_id: 'a1',
    plan_id: 'p1',
    title: 'Road to nationals',
    description: '',
    unit_price_usdc: '25',
    unit_price_usdc_atomic: 25_000_000,
    minimum_success_threshold_usdc: '800',
    minimum_success_threshold_atomic: 800_000_000,
    main_goal_usdc: null,
    main_goal_atomic: null,
    start_at: new Date().toISOString(),
    end_at: new Date(Date.now() + 86_400_000).toISOString(),
    metadata_uri: null,
    metadata_hash: null,
    status: 'active',
    campaign_pda: null,
    escrow_token_account: null,
    chain_signature: null,
    publish_confirmation_status: null,
    stretch_goals: [],
    reward_tiers: [tier('t1', 1, 'one-on-one session'), tier('t2', 5, 'autograph'), tier('t3', 10, 'tennis racket')],
    created_at: '',
    updated_at: '',
    ...overrides,
  }
}

describe('formatUsdc', () => {
  it('renders whole and fractional amounts without floating point drift', () => {
    expect(formatUsdc(25_000_000)).toBe('25')
    expect(formatUsdc(275_000_000)).toBe('275')
    expect(formatUsdc(1)).toBe('0.000001')
    expect(formatUsdc(1_500_000)).toBe('1.5')
    expect(formatUsdc(0)).toBe('0')
  })
})

describe('highestTier', () => {
  it('returns only the highest tier reached, not every tier below it', () => {
    const tiers = campaign().reward_tiers
    expect(highestTier(tiers, 11)?.required_units).toBe(10)
    expect(highestTier(tiers, 7)?.required_units).toBe(5)
    expect(highestTier(tiers, 1)?.required_units).toBe(1)
  })

  it('returns null below the lowest tier', () => {
    expect(highestTier(campaign().reward_tiers, 0)).toBeNull()
  })
})

describe('estimatePurchase', () => {
  it('splits three units into one immediate and two pending', () => {
    // Mirrors the Part 2 acceptance criterion and the on-chain allocate_units().
    const estimate = estimatePurchase(3, campaign(), CONFIG)
    expect(estimate.immediateUnits).toBe(1)
    expect(estimate.pendingUnits).toBe(2)
  })

  it('never activates more than one unit however many are bought', () => {
    expect(estimatePurchase(10, campaign(), CONFIG).immediateUnits).toBe(1)
    expect(estimatePurchase(100, campaign(), CONFIG).immediateUnits).toBe(1)
    expect(estimatePurchase(100, campaign(), CONFIG).pendingUnits).toBe(99)
  })

  it('activates nothing when the supporter already holds a unit in this campaign', () => {
    const estimate = estimatePurchase(5, campaign(), CONFIG, 1)
    expect(estimate.immediateUnits).toBe(0)
    expect(estimate.pendingUnits).toBe(5)
    expect(estimate.confirmedPoints).toBe(0)
    expect(estimate.pendingPoints).toBe(500)
  })

  it('awards 100 points per unit, split by confirmation state', () => {
    const estimate = estimatePurchase(11, campaign(), CONFIG)
    expect(estimate.basePoints).toBe(1_100)
    expect(estimate.confirmedPoints).toBe(100)
    expect(estimate.pendingPoints).toBe(1_000)
  })

  it('floors the success bonus like the backend does', () => {
    // 100 base * 2000bps = 20 exactly; 300 base gives 60. Use a rate that would
    // produce a fraction to prove flooring rather than rounding.
    expect(estimatePurchase(1, campaign(), { ...CONFIG, success_bonus_rate_bps: 1_550 }).successBonusPoints).toBe(15)
    expect(estimatePurchase(5, campaign(), CONFIG).successBonusPoints).toBe(100)
  })

  it('prices the purchase from the campaign unit price', () => {
    const estimate = estimatePurchase(11, campaign(), CONFIG)
    expect(estimate.totalAtomic).toBe(275_000_000)
    expect(estimate.totalUsdc).toBe('275')
  })

  it('counts prior units when resolving the tier', () => {
    // 4 already bought + 7 now = 11 total, which reaches the 10+ tier.
    expect(estimatePurchase(7, campaign(), CONFIG, 4).tier?.required_units).toBe(10)
  })

  it('treats junk input as zero rather than producing NaN', () => {
    const estimate = estimatePurchase(Number.NaN, campaign(), CONFIG)
    expect(estimate.units).toBe(0)
    expect(estimate.totalAtomic).toBe(0)
    expect(estimate.immediateUnits).toBe(0)
  })
})
