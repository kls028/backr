import { useQuery } from '@tanstack/react-query'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api, type CampaignRewardTierView } from '@/lib/api'

/** The label a tier carries for this viewer, or null when nothing applies. */
function tierState(tier: CampaignRewardTierView, signedIn: boolean) {
  if (tier.unlocked_but_unavailable) return { label: 'Sold out', variant: 'outline' as const }
  if (tier.unlocked_for_viewer) return { label: 'Unlocked', variant: 'default' as const }
  if (tier.superseded_for_viewer) return { label: 'Superseded', variant: 'outline' as const }
  return signedIn ? { label: 'Locked', variant: 'secondary' as const } : null
}

function TierRow({ tier, signedIn }: { tier: CampaignRewardTierView; signedIn: boolean }) {
  const state = tierState(tier, signedIn)
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b pb-3 last:border-0">
      <div className="min-w-0">
        <p className={tier.superseded_for_viewer ? 'text-muted-foreground' : undefined}>
          {tier.benefit}
        </p>
        <p className="text-xs text-muted-foreground">
          {tier.required_units} units
          {tier.supply_remaining !== null && ` · ${tier.supply_remaining} of ${tier.max_supply} left`}
        </p>
      </div>
      {state && <Badge variant={state.variant}>{state.label}</Badge>}
    </div>
  )
}

export function CampaignRewards({ campaignId }: { campaignId: string }) {
  const rewards = useQuery({
    queryKey: ['campaign-rewards', campaignId],
    queryFn: () => api.campaignRewards(campaignId),
  })

  if (rewards.isPending) {
    return (
      <Card>
        <CardHeader><CardTitle>Reward tiers</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground">Loading reward tiers…</CardContent>
      </Card>
    )
  }
  if (rewards.error || !rewards.data) {
    return (
      <Card>
        <CardHeader><CardTitle>Reward tiers</CardTitle></CardHeader>
        <CardContent className="text-sm text-destructive">
          {rewards.error instanceof Error ? rewards.error.message : 'Reward request failed'}
        </CardContent>
      </Card>
    )
  }

  const { tiers, viewer } = rewards.data
  const signedIn = viewer !== null
  const cumulative = tiers.filter((tier) => tier.is_cumulative)
  const grouped = new Map<string, CampaignRewardTierView[]>()
  for (const tier of tiers) {
    if (tier.is_cumulative) continue
    const key = tier.reward_group ?? ''
    grouped.set(key, [...(grouped.get(key) ?? []), tier])
  }

  return (
    <Card>
      <CardHeader><CardTitle>Reward tiers</CardTitle></CardHeader>
      <CardContent className="space-y-4 text-sm">
        {viewer && (
          <p className="text-xs text-muted-foreground">
            You hold {viewer.confirmed_units} confirmed{' '}
            {viewer.confirmed_units === 1 ? 'unit' : 'units'}
            {viewer.pending_units > 0 && ` and ${viewer.pending_units} pending`}. Only confirmed
            units unlock rewards.
          </p>
        )}

        {cumulative.length > 0 && (
          <div className="space-y-3">
            {cumulative.map((tier) => (
              <TierRow key={tier.id} tier={tier} signedIn={signedIn} />
            ))}
          </div>
        )}

        {[...grouped.entries()].map(([group, groupTiers]) => (
          <div key={group || 'default'} className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {group || 'Choose one'} · highest tier only
            </p>
            {groupTiers.map((tier) => (
              <TierRow key={tier.id} tier={tier} signedIn={signedIn} />
            ))}
          </div>
        ))}

        {tiers.length === 0 && <p className="text-muted-foreground">No reward tiers configured.</p>}
      </CardContent>
    </Card>
  )
}
