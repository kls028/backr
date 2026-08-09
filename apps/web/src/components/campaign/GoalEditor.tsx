import { Button } from '@/components/ui/button'
import type { CampaignGoalInput } from '@/lib/api'

interface GoalEditorProps {
  goals: CampaignGoalInput[]
  onChange: (goals: CampaignGoalInput[]) => void
}

export function GoalEditor({ goals, onChange }: GoalEditorProps) {
  const update = (index: number, field: keyof CampaignGoalInput, value: string) => {
    onChange(goals.map((goal, goalIndex) => goalIndex === index ? { ...goal, [field]: value } : goal))
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium">Stretch goals</p>
          <p className="text-xs text-muted-foreground">Up to eight, strictly increasing by amount.</p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={goals.length >= 8}
          onClick={() => onChange([...goals, { amount_usdc: '', benefit: '' }])}
        >
          Add goal
        </Button>
      </div>
      {goals.map((goal, index) => (
        <div key={index} className="grid gap-3 rounded-md border p-3 md:grid-cols-[180px_1fr_auto]">
          <label className="text-sm">
            Amount USDC
            <input className="mt-1 w-full rounded-md border bg-background px-3 py-2" value={goal.amount_usdc} onChange={(event) => update(index, 'amount_usdc', event.target.value)} />
          </label>
          <label className="text-sm">
            Benefit
            <input className="mt-1 w-full rounded-md border bg-background px-3 py-2" value={goal.benefit} onChange={(event) => update(index, 'benefit', event.target.value)} />
          </label>
          <Button type="button" size="sm" variant="ghost" className="self-end" onClick={() => onChange(goals.filter((_, goalIndex) => goalIndex !== index))}>Remove</Button>
        </div>
      ))}
    </div>
  )
}
