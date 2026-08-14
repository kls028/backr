import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api, type Campaign, type SubscriptionPlan } from '@/lib/api'

export function AthletePage() {
  const [plan, setPlan] = useState<SubscriptionPlan | null>(null)
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    void Promise.all([api.myPlan(), api.myCampaigns()]).then(([nextPlan, nextCampaigns]) => {
      setPlan(nextPlan)
      setCampaigns(nextCampaigns)
    }).catch((cause: unknown) => setMessage(cause instanceof Error ? cause.message : 'Athlete workspace request failed'))
  }, [])

  const planPublished = plan?.status === 'published'

  return (
    <div className="space-y-6">
      <div><p className="text-sm font-medium text-muted-foreground">Athlete</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Athlete workspace</h1><p className="mt-2 text-muted-foreground">Profile, subscription plan, and campaign setup.</p></div>
      {message && <Badge variant="destructive">{message}</Badge>}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card><CardHeader><CardTitle>Athlete profile</CardTitle></CardHeader><CardContent className="space-y-3"><p className="text-sm text-muted-foreground">Set the public profile fields used by campaigns.</p><Button asChild><Link to="/athlete/setup">Open setup</Link></Button></CardContent></Card>
        <Card><CardHeader><CardTitle>Subscription plan</CardTitle></CardHeader><CardContent className="space-y-3"><p className="text-sm text-muted-foreground">{plan ? `${plan.unit_price_usdc} USDC · ${plan.status}` : 'No plan configured'}</p><Button asChild><Link to="/athlete/plan">{plan ? 'Edit plan' : 'Create plan'}</Link></Button></CardContent></Card>
        {/* `disabled` on a Slot-rendered anchor is inert, so gate by rendering a
            plain button instead of an asChild link. */}
        <Card><CardHeader><CardTitle>Campaign</CardTitle></CardHeader><CardContent className="space-y-3"><p className="text-sm text-muted-foreground">Create or resume a campaign draft.</p>{planPublished ? <Button asChild><Link to="/athlete/campaigns/new">New campaign</Link></Button> : <Button disabled>New campaign</Button>}{!planPublished && <p className="text-xs text-muted-foreground">Publish a plan before creating a campaign.</p>}</CardContent></Card>
        <Card><CardHeader><CardTitle>Rewards</CardTitle></CardHeader><CardContent className="space-y-3"><p className="text-sm text-muted-foreground">Publish Support Point offers and work the fulfillment queue.</p><Button asChild><Link to="/athlete/rewards">Open rewards</Link></Button></CardContent></Card>
      </div>
      <Card><CardHeader><CardTitle>Your campaigns</CardTitle></CardHeader><CardContent className="space-y-3">{campaigns.map((campaign) => <div key={campaign.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3"><div><p className="font-medium">{campaign.title}</p><p className="text-xs text-muted-foreground">{campaign.id}</p></div><div className="flex items-center gap-2"><Badge variant="secondary">{campaign.publish_confirmation_status ?? campaign.status}</Badge>{campaign.status === 'draft' ? <Button asChild size="sm" variant="outline"><Link to={`/athlete/campaigns/${campaign.id}/edit`}>Edit</Link></Button> : <Button asChild size="sm" variant="outline"><Link to={`/athlete/campaigns/${campaign.id}/review`}>Review</Link></Button>}</div></div>)}{campaigns.length === 0 && <p className="text-sm text-muted-foreground">No campaigns configured.</p>}</CardContent></Card>
    </div>
  )
}
