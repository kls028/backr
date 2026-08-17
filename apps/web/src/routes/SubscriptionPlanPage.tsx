import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api, type SubscriptionPlan } from '@/lib/api'

export function SubscriptionPlanPage() {
  const [plan, setPlan] = useState<SubscriptionPlan | null>(null)
  const [price, setPrice] = useState('')
  const [benefits, setBenefits] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { void api.myPlan().then((nextPlan) => { setPlan(nextPlan); setPrice(nextPlan?.unit_price_usdc ?? ''); setBenefits(nextPlan?.benefits ?? '') }).catch((cause: unknown) => setMessage(cause instanceof Error ? cause.message : 'Plan request failed')) }, [])

  const save = async (publish: boolean) => {
    setBusy(true); setMessage(null)
    try {
      const nextPlan = plan ? await api.updatePlan(plan.id, { unit_price_usdc: price, benefits }) : await api.createPlan({ unit_price_usdc: price, benefits })
      const finalPlan = publish ? await api.publishPlan(nextPlan.id) : nextPlan
      setPlan(finalPlan); setMessage(publish ? 'Subscription plan published' : 'Subscription plan draft saved')
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Plan request failed') }
    finally { setBusy(false) }
  }

  const published = plan?.status === 'published'
  return <div className="mx-auto max-w-2xl space-y-6"><div><Link className="text-sm text-muted-foreground hover:text-foreground" to="/athlete">← Athlete workspace</Link><h1 className="mt-3 text-2xl font-bold tracking-wide">Subscription plan</h1></div><Card><CardHeader><CardTitle>{published ? 'Published plan' : 'Plan details'}</CardTitle></CardHeader><CardContent className="space-y-4"><label className="block text-sm">Unit price USDC<input className="mt-1 w-full rounded-md border bg-background px-3 py-2" readOnly={published} value={price} onChange={(event) => setPrice(event.target.value)} /></label><label className="block text-sm">Benefits<textarea className="mt-1 min-h-32 w-full rounded-md border bg-background px-3 py-2" readOnly={published} value={benefits} onChange={(event) => setBenefits(event.target.value)} /></label>{!published && <div className="flex flex-wrap gap-2"><Button onClick={() => void save(false)} disabled={busy}>{busy ? 'Saving…' : 'Save draft'}</Button><Button variant="outline" onClick={() => void save(true)} disabled={busy}>Publish plan</Button></div>}{message && <p className="text-sm text-muted-foreground">{message}</p>}</CardContent></Card></div>
}
