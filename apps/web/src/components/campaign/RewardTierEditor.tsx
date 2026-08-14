import { Button } from '@/components/ui/button'
import type { CampaignTierInput } from '@/lib/api'

interface RewardTierEditorProps {
  tiers: CampaignTierInput[]
  onChange: (tiers: CampaignTierInput[]) => void
}

// max_per_supporter is fixed at 1: an entitlement is unique per supporter and
// tier, so any other value would be a limit the platform never applies.
const emptyTier = (): CampaignTierInput => ({
  required_units: 1,
  benefit: '',
  is_cumulative: true,
  reward_group: null,
  max_supply: null,
  max_per_supporter: 1,
  uri: null,
})

export function RewardTierEditor({ tiers, onChange }: RewardTierEditorProps) {
  const update = (index: number, field: keyof CampaignTierInput, value: string | number | boolean | null) => {
    onChange(tiers.map((tier, tierIndex) => tierIndex === index ? { ...tier, [field]: value } : tier))
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium">Reward tiers</p>
          <p className="text-xs text-muted-foreground">Thresholds must be strictly increasing.</p>
        </div>
        <Button type="button" size="sm" variant="outline" onClick={() => onChange([...tiers, emptyTier()])}>Add tier</Button>
      </div>
      {tiers.map((tier, index) => (
        <div key={index} className="space-y-3 rounded-md border p-3">
          <div className="grid gap-3 md:grid-cols-[150px_1fr_auto]">
            <label className="text-sm">
              Required units
              <input className="mt-1 w-full rounded-md border bg-background px-3 py-2" type="number" min="1" value={tier.required_units} onChange={(event) => update(index, 'required_units', Math.max(1, Number(event.target.value)))} />
            </label>
            <label className="text-sm">
              Benefit
              <input className="mt-1 w-full rounded-md border bg-background px-3 py-2" value={tier.benefit} onChange={(event) => update(index, 'benefit', event.target.value)} />
            </label>
            <Button type="button" size="sm" variant="ghost" className="self-end" onClick={() => onChange(tiers.filter((_, tierIndex) => tierIndex !== index))}>Remove</Button>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm">
              Reward group
              <input className="mt-1 w-full rounded-md border bg-background px-3 py-2" maxLength={40} placeholder="default" value={tier.reward_group ?? ''} onChange={(event) => update(index, 'reward_group', event.target.value.trim() || null)} />
              <span className="mt-1 block text-xs text-muted-foreground">Non-cumulative tiers in the same group compete; only the highest unlocks.</span>
            </label>
            <label className="text-sm">
              Maximum supply
              <input className="mt-1 w-full rounded-md border bg-background px-3 py-2" type="number" min="1" placeholder="Unlimited" value={tier.max_supply ?? ''} onChange={(event) => update(index, 'max_supply', event.target.value === '' ? null : Math.max(1, Number(event.target.value)))} />
              <span className="mt-1 block text-xs text-muted-foreground">Leave blank for an unlimited tier.</span>
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={tier.is_cumulative} onChange={(event) => update(index, 'is_cumulative', event.target.checked)} /> Cumulative</label>
        </div>
      ))}
    </div>
  )
}
