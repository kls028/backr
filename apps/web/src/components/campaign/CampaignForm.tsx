import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { GoalEditor } from '@/components/campaign/GoalEditor'
import { RewardTierEditor } from '@/components/campaign/RewardTierEditor'
import type { Campaign, CampaignInput, CampaignGoalInput, CampaignTierInput } from '@/lib/api'

interface CampaignFormProps {
  planId: string
  initialCampaign?: Campaign | null
  busy?: boolean
  onSave: (input: CampaignInput) => Promise<void>
}

const localDate = (value: string | undefined) => value ? new Date(value).toISOString().slice(0, 16) : ''
const apiDate = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toISOString()
}

export function CampaignForm({ planId, initialCampaign, busy = false, onSave }: CampaignFormProps) {
  const [step, setStep] = useState(0)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [startAt, setStartAt] = useState('')
  const [endAt, setEndAt] = useState('')
  const [threshold, setThreshold] = useState('')
  const [mainGoal, setMainGoal] = useState('')
  const [metadataUri, setMetadataUri] = useState('')
  const [stretchGoals, setStretchGoals] = useState<CampaignGoalInput[]>([])
  const [rewardTiers, setRewardTiers] = useState<CampaignTierInput[]>([])

  useEffect(() => {
    if (!initialCampaign) return
    setTitle(initialCampaign.title)
    setDescription(initialCampaign.description)
    setStartAt(localDate(initialCampaign.start_at))
    setEndAt(localDate(initialCampaign.end_at))
    setThreshold(initialCampaign.minimum_success_threshold_usdc)
    setMainGoal(initialCampaign.main_goal_usdc ?? '')
    setMetadataUri(initialCampaign.metadata_uri ?? '')
    setStretchGoals(initialCampaign.stretch_goals.map((goal) => ({ amount_usdc: goal.amount_usdc, benefit: goal.benefit })))
    setRewardTiers(initialCampaign.reward_tiers.map((tier) => ({ required_units: tier.required_units, benefit: tier.benefit, is_cumulative: tier.is_cumulative, max_supply: tier.max_supply, max_per_supporter: tier.max_per_supporter, uri: tier.uri })))
  }, [initialCampaign])

  const input = (): CampaignInput => ({
    plan_id: planId,
    title,
    description,
    start_at: apiDate(startAt),
    end_at: apiDate(endAt),
    minimum_success_threshold_usdc: threshold,
    main_goal_usdc: mainGoal || null,
    stretch_goals: stretchGoals,
    reward_tiers: rewardTiers,
    metadata_uri: metadataUri || null,
  })

  const next = () => setStep((current) => Math.min(3, current + 1))
  const previous = () => setStep((current) => Math.max(0, current - 1))

  return (
    <Card>
      <CardHeader><CardTitle>Campaign editor · Step {step + 1} of 4</CardTitle><p className="text-sm text-muted-foreground">Save a draft after reviewing the campaign configuration.</p></CardHeader>
      <CardContent className="space-y-6">
        {step === 0 && <div className="space-y-4"><label className="block text-sm">Title<input className="mt-1 w-full rounded-md border bg-background px-3 py-2" value={title} onChange={(event) => setTitle(event.target.value)} /></label><label className="block text-sm">Description<textarea className="mt-1 min-h-32 w-full rounded-md border bg-background px-3 py-2" value={description} onChange={(event) => setDescription(event.target.value)} /></label></div>}
        {step === 1 && <div className="grid gap-4 md:grid-cols-2"><label className="text-sm">Start<input className="mt-1 w-full rounded-md border bg-background px-3 py-2" type="datetime-local" value={startAt} onChange={(event) => setStartAt(event.target.value)} /></label><label className="text-sm">End<input className="mt-1 w-full rounded-md border bg-background px-3 py-2" type="datetime-local" value={endAt} onChange={(event) => setEndAt(event.target.value)} /></label><label className="text-sm">Minimum success threshold USDC<input className="mt-1 w-full rounded-md border bg-background px-3 py-2" value={threshold} onChange={(event) => setThreshold(event.target.value)} /></label><label className="text-sm">Main goal USDC<input className="mt-1 w-full rounded-md border bg-background px-3 py-2" value={mainGoal} onChange={(event) => setMainGoal(event.target.value)} /></label><label className="text-sm md:col-span-2">Metadata URI<input className="mt-1 w-full rounded-md border bg-background px-3 py-2" maxLength={200} value={metadataUri} onChange={(event) => setMetadataUri(event.target.value)} /></label></div>}
        {step === 2 && <div className="space-y-8"><GoalEditor goals={stretchGoals} onChange={setStretchGoals} /><RewardTierEditor tiers={rewardTiers} onChange={setRewardTiers} /></div>}
        {step === 3 && <div className="space-y-4 rounded-md border p-4"><h2 className="font-medium">Review</h2><dl className="grid gap-3 text-sm md:grid-cols-2"><div><dt className="text-muted-foreground">Title</dt><dd>{title || 'Not set'}</dd></div><div><dt className="text-muted-foreground">Unit price</dt><dd>Loaded from published plan</dd></div><div><dt className="text-muted-foreground">Schedule</dt><dd>{startAt || 'Not set'} to {endAt || 'Not set'}</dd></div><div><dt className="text-muted-foreground">Threshold</dt><dd>{threshold || 'Not set'} USDC</dd></div><div><dt className="text-muted-foreground">Stretch goals</dt><dd>{stretchGoals.length}</dd></div><div><dt className="text-muted-foreground">Reward tiers</dt><dd>{rewardTiers.length}</dd></div></dl><p className="text-sm text-muted-foreground">The server validates all amounts, dates, ordering, and publication immutability when this draft is saved.</p></div>}
        <div className="flex flex-wrap justify-between gap-2"><Button type="button" variant="outline" onClick={previous} disabled={step === 0 || busy}>Back</Button><div className="flex gap-2">{step < 3 ? <Button type="button" onClick={next}>Next</Button> : <Button type="button" onClick={() => void onSave(input())} disabled={busy}>{busy ? 'Saving…' : 'Save draft'}</Button>}</div></div>
      </CardContent>
    </Card>
  )
}
