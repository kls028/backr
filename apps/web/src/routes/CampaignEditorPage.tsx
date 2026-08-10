import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { CampaignForm } from '@/components/campaign/CampaignForm'
import { api, type Campaign, type CampaignInput, type SubscriptionPlan } from '@/lib/api'

export function CampaignEditorPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [plan, setPlan] = useState<SubscriptionPlan | null>(null)
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void Promise.all([api.myPlan(), api.myCampaigns()]).then(([nextPlan, campaigns]) => {
      setPlan(nextPlan)
      setCampaign(campaigns.find((item) => item.id === id) ?? null)
    }).catch((cause: unknown) => setMessage(cause instanceof Error ? cause.message : 'Campaign request failed')).finally(() => setLoading(false))
  }, [id])

  const save = async (input: CampaignInput) => {
    setBusy(true); setMessage(null)
    try {
      const nextCampaign = campaign
        ? await api.updateCampaign(campaign.id, { ...input, plan_id: undefined } as Omit<CampaignInput, 'plan_id'>)
        : await api.createCampaign(input)
      setCampaign(nextCampaign)
      navigate(`/athlete/campaigns/${nextCampaign.id}/review`)
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Campaign save failed') }
    finally { setBusy(false) }
  }

  if (loading) return <p className="text-sm text-muted-foreground">Loading campaign editor…</p>
  if (plan?.status !== 'published') return <div className="space-y-4"><Link className="text-sm text-muted-foreground hover:text-foreground" to="/athlete">← Athlete workspace</Link><p className="text-sm">Publish a subscription plan before authoring a campaign.</p><Button asChild><Link to="/athlete/plan">Open plan</Link></Button></div>
  if (id && !campaign && !message) return <p className="text-sm text-muted-foreground">Loading campaign…</p>

  return <div className="mx-auto max-w-3xl space-y-6"><div><Link className="text-sm text-muted-foreground hover:text-foreground" to="/athlete">← Athlete workspace</Link><h1 className="mt-3 text-3xl font-semibold tracking-tight">{campaign ? 'Edit campaign draft' : 'New campaign'}</h1>{message && <p className="mt-2 text-sm text-destructive">{message}</p>}</div><CampaignForm planId={plan.id} initialCampaign={campaign} busy={busy} onSave={save} /></div>
}
