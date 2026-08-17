import type { Campaign, CampaignTier, PlatformConfig } from '@/lib/api'

/**
 * Checkout arithmetic, kept pure so it can be tested without a wallet or a
 * network. The backend is authoritative — `POST /campaigns/:id/purchase` returns
 * the real split — but the supporter has to see what they are buying *before*
 * they approve a signature (spec §60), so the same rules are mirrored here.
 */

export interface PurchaseEstimate {
  units: number
  totalAtomic: number
  totalUsdc: string
  /** Spec §73: at most one unit per supporter per campaign activates now. */
  immediateUnits: number
  pendingUnits: number
  confirmedPoints: number
  pendingPoints: number
  basePoints: number
  /** Only awarded if the campaign succeeds (spec §136-143). */
  successBonusPoints: number
  tier: CampaignTier | null
}

/** Format an atomic USDC amount for display. Integer maths only — a float here
 *  turns 0.1 + 0.2 into a support ticket. */
export function formatUsdc(atomic: number, decimals = 6): string {
  const sign = atomic < 0 ? '-' : ''
  const abs = Math.abs(atomic)
  const scale = 10 ** decimals
  const whole = Math.floor(abs / scale)
  const fraction = String(abs % scale).padStart(decimals, '0').replace(/0+$/, '')
  return fraction ? `${sign}${whole}.${fraction}` : `${sign}${whole}`
}

/** Highest tier the supporter reaches, counting units already bought in this
 *  campaign (spec §91-95: cumulative totals, highest tier only). */
export function highestTier(tiers: CampaignTier[], totalUnits: number): CampaignTier | null {
  return tiers
    .filter((tier) => tier.required_units <= totalUnits)
    .reduce<CampaignTier | null>(
      (best, tier) => (best === null || tier.required_units > best.required_units ? tier : best),
      null,
    )
}

export function estimatePurchase(
  units: number,
  campaign: Campaign,
  config: Pick<PlatformConfig, 'base_points_per_unit' | 'success_bonus_rate_bps'>,
  priorUnits = 0,
): PurchaseEstimate {
  const safeUnits = Number.isFinite(units) ? Math.max(0, Math.floor(units)) : 0

  // One immediate unit only, and none at all if the supporter already holds one
  // in this campaign.
  const immediateUnits = safeUnits > 0 && priorUnits === 0 ? 1 : 0
  const pendingUnits = safeUnits - immediateUnits

  const basePoints = safeUnits * config.base_points_per_unit
  // Floor division, matching calculate_success_bonus() in the backend.
  const successBonusPoints = Math.floor((basePoints * config.success_bonus_rate_bps) / 10_000)
  const totalAtomic = campaign.unit_price_usdc_atomic * safeUnits

  return {
    units: safeUnits,
    totalAtomic,
    totalUsdc: formatUsdc(totalAtomic),
    immediateUnits,
    pendingUnits,
    confirmedPoints: immediateUnits * config.base_points_per_unit,
    pendingPoints: pendingUnits * config.base_points_per_unit,
    basePoints,
    successBonusPoints,
    tier: highestTier(campaign.reward_tiers, priorUnits + safeUnits),
  }
}
