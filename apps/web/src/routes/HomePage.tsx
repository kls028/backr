import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { CampaignProgress } from '@/components/campaign/CampaignProgress'
import { api, type Campaign } from '@/lib/api'

export function HomePage() {
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void api
      .campaigns()
      .then(setCampaigns)
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : 'Campaign request failed')
      })
  }, [])

  return (
    <div className="space-y-8">
      <header>
        {/* The site header already says Backr; this is the page name. */}
        <h1 className="text-2xl font-bold tracking-wide">Campaigns</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          Buy an athlete&apos;s subscription months in USDC. One month starts immediately, the rest
          are held in escrow until the campaign settles.
        </p>
      </header>

      {error && (
        <Card>
          <CardContent className="space-y-3 py-8 text-center">
            <p className="text-destructive text-sm">{error}</p>
            <p className="text-muted-foreground text-sm">
              The API may not be running. Start it with{' '}
              <code className="text-foreground">pnpm dev:up</code>, then reload.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Card-shaped skeletons so the layout does not jump when data lands. */}
      {!campaigns && !error && (
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1].map((index) => (
            <Card key={index}>
              <CardHeader className="space-y-3">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-4 w-1/3" />
              </CardHeader>
              <CardContent className="space-y-3">
                <Skeleton className="h-2 w-full" />
                <Skeleton className="h-4 w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {campaigns && campaigns.length > 0 && (
        <ul className="grid gap-4 md:grid-cols-2">
          {campaigns.map((campaign) => (
            <li key={campaign.id}>
              <Link
                to={`/campaigns/${campaign.id}`}
                className="group focus-visible:ring-ring block focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none"
              >
                <Card className="hover:border-primary h-full border transition-colors duration-100 ease-out">
                  <CardHeader className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <CardTitle className="text-base leading-snug">{campaign.title}</CardTitle>
                      <Badge variant="secondary" className="shrink-0">
                        {campaign.status}
                      </Badge>
                    </div>
                    {campaign.athlete_display_name && (
                      <p className="text-muted-foreground text-xs tracking-wide uppercase">
                        {campaign.athlete_display_name}
                        {campaign.athlete_sport && ` · ${campaign.athlete_sport}`}
                      </p>
                    )}
                  </CardHeader>

                  <CardContent className="space-y-4">
                    <CampaignProgress
                      raisedAtomic={campaign.raised_amount_atomic}
                      thresholdAtomic={campaign.minimum_success_threshold_atomic}
                      raisedUsdc={campaign.raised_amount_usdc}
                      thresholdUsdc={campaign.minimum_success_threshold_usdc}
                    />
                    <div className="text-muted-foreground flex items-baseline justify-between text-xs">
                      <span>
                        <span className="text-foreground tabular-nums">
                          {campaign.unit_price_usdc}
                        </span>{' '}
                        USDC / month
                      </span>
                      <span>{daysLeft(campaign.end_at)}</span>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {campaigns && campaigns.length === 0 && (
        <Card>
          <CardContent className="space-y-3 py-12 text-center">
            <p className="text-sm font-medium">No campaigns yet</p>
            <p className="text-muted-foreground text-sm">
              Athletes publish campaigns from the athlete workspace.
            </p>
            <Link to="/athlete" className="text-primary inline-block text-sm underline">
              Go to athlete workspace
            </Link>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

/** Human-readable time remaining (spec §41). */
function daysLeft(endAt: string): string {
  const ms = new Date(endAt).getTime() - Date.now()
  if (Number.isNaN(ms)) return ''
  if (ms <= 0) return 'Ended'
  const days = Math.floor(ms / 86_400_000)
  if (days >= 1) return `${days} ${days === 1 ? 'day' : 'days'} left`
  const hours = Math.max(1, Math.floor(ms / 3_600_000))
  return `${hours} ${hours === 1 ? 'hour' : 'hours'} left`
}
