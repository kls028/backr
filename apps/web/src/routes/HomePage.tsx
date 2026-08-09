import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api, type Campaign } from '@/lib/api'

export function HomePage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void api.campaigns().then(setCampaigns).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : 'Campaign request failed')
    })
  }, [])

  return (
    <div className="space-y-8">
      <section>
        <p className="text-sm font-medium text-muted-foreground">Campaigns</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Backr</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Support athlete campaigns with a monthly USDC subscription.
        </p>
      </section>

      {error && <Badge variant="destructive">{error}</Badge>}

      <section className="grid gap-4 md:grid-cols-2">
        {campaigns.map((campaign) => (
          <Link key={campaign.id} to={`/campaigns/${campaign.id}`} className="block">
            <Card className="h-full transition-colors hover:border-foreground/40">
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <CardTitle>{campaign.title}</CardTitle>
                  <Badge variant="secondary">{campaign.status}</Badge>
                </div>
                <CardDescription>{campaign.description}</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Unit price</p>
                  <p className="font-medium">{campaign.unit_price_usdc} USDC</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Success threshold</p>
                  <p className="font-medium">{campaign.minimum_success_threshold_usdc} USDC</p>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </section>

      {!error && campaigns.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No campaigns are available.
          </CardContent>
        </Card>
      )}
    </div>
  )
}
