import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { CampaignStatusBadge } from '@/components/campaign/CampaignStatusBadge'
import { CampaignProgress } from '@/components/campaign/CampaignProgress'
import { PurchaseCard } from '@/components/campaign/PurchaseCard'
import { api, type Campaign } from '@/lib/api'

export function CampaignPage() {
  const { id = '' } = useParams()
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setCampaign(null)
    setError(null)
    void api
      .campaign(id)
      .then(setCampaign)
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : 'Campaign request failed'),
      )
  }, [id])

  if (error) {
    return (
      <Card>
        <CardContent className="space-y-3 py-12 text-center">
          <p className="text-destructive text-sm">{error}</p>
          <Link to="/campaigns" className="text-primary inline-block text-sm underline">
            Back to campaigns
          </Link>
        </CardContent>
      </Card>
    )
  }

  if (!campaign) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-7 w-2/3" />
        <Skeleton className="h-4 w-full max-w-xl" />
        <div className="grid gap-6 md:grid-cols-2">
          <Skeleton className="h-52 w-full" />
          <Skeleton className="h-52 w-full" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <nav aria-label="Breadcrumb">
        <Link to="/campaigns" className="text-muted-foreground hover:text-foreground text-xs">
          ← Campaigns
        </Link>
      </nav>

      <header className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <CampaignStatusBadge status={campaign.status} />
            <h1 className="mt-3 text-2xl font-bold tracking-wide">{campaign.title}</h1>
            {campaign.athlete_display_name && (
              <p className="text-muted-foreground mt-2 text-xs tracking-widest uppercase">
                {campaign.athlete_display_name}
                {campaign.athlete_sport && ` · ${campaign.athlete_sport}`}
              </p>
            )}
          </div>
          <div className="text-right">
            <p className="text-muted-foreground text-xs tracking-wide uppercase">Per month</p>
            <p className="text-xl font-bold tabular-nums">{campaign.unit_price_usdc} USDC</p>
          </div>
        </div>

        <p className="text-muted-foreground max-w-2xl text-sm leading-relaxed">
          {campaign.description}
        </p>

        <CampaignProgress
          className="max-w-xl"
          raisedAtomic={campaign.raised_amount_atomic}
          thresholdAtomic={campaign.minimum_success_threshold_atomic}
          raisedUsdc={campaign.raised_amount_usdc}
          thresholdUsdc={campaign.minimum_success_threshold_usdc}
        />
      </header>

      {/* Purchase first — it is what the page is for. Detail follows. */}
      <PurchaseCard campaign={campaign} />

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Goals</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Success threshold" value={`${campaign.minimum_success_threshold_usdc} USDC`} />
            {campaign.main_goal_usdc && (
              <Row label="Main goal" value={`${campaign.main_goal_usdc} USDC`} />
            )}
            {campaign.stretch_goals.map((goal) => (
              <Row key={goal.id} label={goal.benefit} value={`${goal.amount_usdc} USDC`} muted />
            ))}
            <Row label="Ends" value={new Date(campaign.end_at).toLocaleDateString()} muted />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Reward tiers</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {campaign.reward_tiers.length === 0 && (
              <p className="text-muted-foreground">No reward tiers on this campaign.</p>
            )}
            {campaign.reward_tiers.map((tier) => (
              <div key={tier.id} className="flex items-start justify-between gap-4">
                <span>
                  {tier.benefit}
                  {!tier.is_cumulative && (
                    <Badge variant="secondary" className="ml-2 align-middle text-[10px]">
                      not cumulative
                    </Badge>
                  )}
                </span>
                <span className="text-muted-foreground shrink-0 tabular-nums">
                  {tier.required_units}+ months
                </span>
              </div>
            ))}
            {campaign.reward_tiers.length > 0 && (
              <p className="text-muted-foreground border-t pt-3 text-xs">
                Tiers unlock only if the campaign meets its threshold.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* On-chain provenance is useful but secondary, so it sits last and quiet. */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">On-chain</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-xs">
          {campaign.campaign_pda ? (
            <Row label="Campaign account" value={campaign.campaign_pda} mono muted />
          ) : (
            <p className="text-muted-foreground">Not published on-chain yet.</p>
          )}
          {campaign.chain_signature ? (
            <Row label="Publish signature" value={campaign.chain_signature} mono muted />
          ) : (
            <p className="text-muted-foreground">Publication not verified.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function Row({
  label,
  value,
  muted = false,
  mono = false,
}: {
  label: string
  value: string
  muted?: boolean
  mono?: boolean
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className={muted ? 'text-muted-foreground' : ''}>{label}</span>
      <span className={`shrink-0 text-right tabular-nums ${mono ? 'text-[11px] break-all' : ''}`}>
        {value}
      </span>
    </div>
  )
}
