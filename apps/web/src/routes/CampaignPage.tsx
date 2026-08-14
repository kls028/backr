import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CampaignRewards } from '@/components/campaign/CampaignRewards'
import { CampaignStatusBadge } from '@/components/campaign/CampaignStatusBadge'
import { api, type Campaign } from '@/lib/api'

export function CampaignPage() {
  const { id = '' } = useParams()
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => { void api.campaign(id).then(setCampaign).catch((cause: unknown) => setMessage(cause instanceof Error ? cause.message : 'Campaign request failed')) }, [id])

  if (message) return <p className="text-sm text-destructive">{message}</p>
  if (!campaign) return <p className="text-sm text-muted-foreground">Loading campaign…</p>

  return <div className="space-y-6"><div className="flex flex-wrap items-start justify-between gap-4"><div><CampaignStatusBadge status={campaign.status} /><h1 className="mt-3 text-3xl font-semibold tracking-tight">{campaign.title}</h1><p className="mt-2 max-w-2xl text-muted-foreground">{campaign.description}</p></div><div className="text-right text-sm"><p className="text-muted-foreground">Unit price</p><p className="text-xl font-semibold">{campaign.unit_price_usdc} USDC</p></div></div><div className="grid gap-6 md:grid-cols-2"><Card><CardHeader><CardTitle>Schedule and goals</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><div className="flex justify-between"><span>Start</span><span>{new Date(campaign.start_at).toLocaleString()}</span></div><div className="flex justify-between"><span>End</span><span>{new Date(campaign.end_at).toLocaleString()}</span></div><div className="flex justify-between"><span>Success threshold</span><span>{campaign.minimum_success_threshold_usdc} USDC</span></div>{campaign.main_goal_usdc && <div className="flex justify-between"><span>Main goal</span><span>{campaign.main_goal_usdc} USDC</span></div>}{campaign.stretch_goals.map((goal) => <div key={goal.id} className="flex justify-between text-muted-foreground"><span>{goal.benefit}</span><span>{goal.amount_usdc} USDC</span></div>)}</CardContent></Card><CampaignRewards campaignId={campaign.id} /></div><Card><CardHeader><CardTitle>Publication</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">{campaign.chain_signature ? <p className="break-all font-mono text-xs text-muted-foreground">Chain signature: {campaign.chain_signature}</p> : <Badge variant="secondary">Publication not yet verified</Badge>}{campaign.campaign_pda && <p className="break-all font-mono text-xs text-muted-foreground">Campaign PDA: {campaign.campaign_pda}</p>}<Link className="text-sm underline" to="/campaigns">Back to campaigns</Link></CardContent></Card></div>
}
