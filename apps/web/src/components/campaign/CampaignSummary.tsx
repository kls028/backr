import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CampaignStatusBadge } from '@/components/campaign/CampaignStatusBadge'
import type { Campaign } from '@/lib/api'

export function CampaignSummary({ campaign }: { campaign: Campaign }) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <CampaignStatusBadge status={campaign.status} />
          <h1 className="mt-3 text-2xl font-bold tracking-wide">{campaign.title}</h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">{campaign.description}</p>
        </div>
        <div className="text-right text-sm"><p className="text-muted-foreground">Unit price</p><p className="text-xl font-semibold">{campaign.unit_price_usdc} USDC</p></div>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <Card><CardHeader><CardTitle>Schedule and goals</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
          <div className="flex justify-between gap-4"><span>Start</span><span>{new Date(campaign.start_at).toLocaleString()}</span></div>
          <div className="flex justify-between gap-4"><span>End</span><span>{new Date(campaign.end_at).toLocaleString()}</span></div>
          <div className="flex justify-between gap-4"><span>Success threshold</span><span>{campaign.minimum_success_threshold_usdc} USDC</span></div>
          {campaign.main_goal_usdc && <div className="flex justify-between gap-4"><span>Main goal</span><span>{campaign.main_goal_usdc} USDC</span></div>}
          {campaign.stretch_goals.map((goal) => <div key={goal.id} className="flex justify-between gap-4 text-muted-foreground"><span>{goal.benefit}</span><span>{goal.amount_usdc} USDC</span></div>)}
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Reward tiers</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
          {campaign.reward_tiers.map((tier) => <div key={tier.id} className="flex justify-between gap-4"><span>{tier.benefit}</span><span className="shrink-0 text-muted-foreground">{tier.required_units} units</span></div>)}
          {campaign.reward_tiers.length === 0 && <p className="text-muted-foreground">No reward tiers configured.</p>}
        </CardContent></Card>
      </div>
    </div>
  )
}
