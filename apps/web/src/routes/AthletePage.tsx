import { useState } from 'react'
import { useWallet } from '@solana/wallet-adapter-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api } from '@/lib/api'
import { signAndSend } from '@/lib/solana'

export function AthletePage() {
  const { signTransaction } = useWallet()
  const [displayName, setDisplayName] = useState('')
  const [sport, setSport] = useState('')
  const [bio, setBio] = useState('')
  const [price, setPrice] = useState('')
  const [benefits, setBenefits] = useState('')
  const [planId, setPlanId] = useState('')
  const [campaignTitle, setCampaignTitle] = useState('')
  const [campaignDescription, setCampaignDescription] = useState('')
  const [threshold, setThreshold] = useState('')
  const [mainGoal, setMainGoal] = useState('')
  const [startAt, setStartAt] = useState('')
  const [endAt, setEndAt] = useState('')
  const [campaignId, setCampaignId] = useState('')
  const [escrowTokenAccount, setEscrowTokenAccount] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const activate = async () => {
    setMessage(null)
    try {
      await api.athleteProfile({ display_name: displayName, sport, bio })
      setMessage('Athlete profile saved')
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Profile request failed') }
  }

  const createPlan = async () => {
    setMessage(null)
    try {
      const plan = await api.createPlan({ unit_price_usdc: price, benefits })
      await api.publishPlan(plan.id)
      setPlanId(plan.id)
      setMessage('Subscription plan published')
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Plan request failed') }
  }

  const createCampaign = async () => {
    setBusy(true)
    setMessage(null)
    try {
      const campaign = await api.createCampaign({
        plan_id: planId,
        title: campaignTitle,
        description: campaignDescription,
        start_at: new Date(startAt).toISOString(),
        end_at: new Date(endAt).toISOString(),
        minimum_success_threshold_usdc: threshold,
        main_goal_usdc: mainGoal || null,
        stretch_goals: [],
        reward_tiers: [],
      })
      setCampaignId(campaign.id)
      setMessage('Campaign draft created')
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Campaign request failed') }
    finally { setBusy(false) }
  }

  const publishCampaign = async () => {
    if (!signTransaction || !campaignId) { setMessage('Connect a wallet and create a campaign first'); return }
    setBusy(true)
    try {
      const intent = await api.publishCampaign(campaignId, { escrow_token_account: escrowTokenAccount })
      const signature = await signAndSend(intent.transaction, intent.last_valid_block_height, intent.blockhash, signTransaction)
      await api.confirmCampaign(campaignId, { signature, campaign_pda: intent.campaign_pda })
      setMessage(`Campaign published: ${signature}`)
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Publication failed') }
    finally { setBusy(false) }
  }

  const field = (label: string, value: string, setValue: (value: string) => void, type = 'text') => (
    <label className="block text-sm">{label}<input className="mt-1 w-full rounded-md border bg-background px-3 py-2" type={type} value={value} onChange={(event) => setValue(event.target.value)} /></label>
  )

  return (
    <div className="space-y-6">
      <div><h1 className="text-3xl font-semibold tracking-tight">Athlete workspace</h1><p className="mt-2 text-muted-foreground">Profile, subscription plan, and campaign setup.</p></div>
      {message && <p className="text-sm text-muted-foreground">{message}</p>}
      <Card><CardHeader><CardTitle>Athlete profile</CardTitle></CardHeader><CardContent className="grid gap-4 md:grid-cols-2">{field('Display name', displayName, setDisplayName)}{field('Sport', sport, setSport)}<label className="block text-sm md:col-span-2">Bio<textarea className="mt-1 min-h-24 w-full rounded-md border bg-background px-3 py-2" value={bio} onChange={(event) => setBio(event.target.value)} /></label><Button onClick={() => void activate()}>Save profile</Button></CardContent></Card>
      <Card><CardHeader><CardTitle>Subscription plan</CardTitle></CardHeader><CardContent className="space-y-4">{field('Unit price USDC', price, setPrice)}<label className="block text-sm">Benefits<textarea className="mt-1 min-h-24 w-full rounded-md border bg-background px-3 py-2" value={benefits} onChange={(event) => setBenefits(event.target.value)} /></label><Button onClick={() => void createPlan()}>Publish plan</Button>{planId && <p className="font-mono text-xs text-muted-foreground">{planId}</p>}</CardContent></Card>
      <Card><CardHeader><CardTitle>Campaign</CardTitle></CardHeader><CardContent className="grid gap-4 md:grid-cols-2">{field('Title', campaignTitle, setCampaignTitle)}{field('Minimum success threshold USDC', threshold, setThreshold)}{field('Main goal USDC', mainGoal, setMainGoal)}{field('Start', startAt, setStartAt, 'datetime-local')}{field('End', endAt, setEndAt, 'datetime-local')}{field('Escrow token account', escrowTokenAccount, setEscrowTokenAccount)}<label className="block text-sm md:col-span-2">Description<textarea className="mt-1 min-h-24 w-full rounded-md border bg-background px-3 py-2" value={campaignDescription} onChange={(event) => setCampaignDescription(event.target.value)} /></label><div className="flex flex-wrap gap-2 md:col-span-2"><Button onClick={() => void createCampaign()} disabled={busy || !planId}>Create draft</Button><Button variant="outline" onClick={() => void publishCampaign()} disabled={busy || !campaignId || !escrowTokenAccount}>Publish on chain</Button></div>{campaignId && <p className="font-mono text-xs text-muted-foreground md:col-span-2">{campaignId}</p>}</CardContent></Card>
    </div>
  )
}
