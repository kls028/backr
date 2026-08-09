import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useWallet } from '@solana/wallet-adapter-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api, type Campaign } from '@/lib/api'
import { signAndSend } from '@/lib/solana'

export function CampaignPage() {
  const { id = '' } = useParams()
  const { signTransaction } = useWallet()
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [units, setUnits] = useState(1)
  const [sourceTokenAccount, setSourceTokenAccount] = useState('')
  const [escrowTokenAccount, setEscrowTokenAccount] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void api.campaign(id).then((nextCampaign) => {
      setCampaign(nextCampaign)
      setEscrowTokenAccount(nextCampaign.escrow_token_account ?? '')
    }).catch((cause: unknown) => {
      setMessage(cause instanceof Error ? cause.message : 'Campaign request failed')
    })
  }, [id])

  const purchase = useCallback(async () => {
    if (!signTransaction) {
      setMessage('Connect a wallet to purchase')
      return
    }
    setBusy(true)
    setMessage(null)
    try {
      const intent = await api.purchase(id, {
        purchased_units: units,
        source_token_account: sourceTokenAccount,
        escrow_token_account: escrowTokenAccount,
      })
      const signature = await signAndSend(
        intent.transaction,
        intent.last_valid_block_height,
        intent.blockhash,
        signTransaction,
      )
      setMessage(`Confirmed ${signature}`)
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : 'Purchase failed')
    } finally {
      setBusy(false)
    }
  }, [id, units, sourceTokenAccount, escrowTokenAccount, signTransaction])

  if (!campaign) return <p className="text-sm text-muted-foreground">Loading campaign…</p>

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Badge variant="secondary">{campaign.status}</Badge>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">{campaign.title}</h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">{campaign.description}</p>
        </div>
        <div className="text-right text-sm">
          <p className="text-muted-foreground">Unit price</p>
          <p className="text-xl font-semibold">{campaign.unit_price_usdc} USDC</p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle>Goals</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between"><span>Success threshold</span><span>{campaign.minimum_success_threshold_usdc} USDC</span></div>
              {campaign.main_goal_usdc && <div className="flex justify-between"><span>Main goal</span><span>{campaign.main_goal_usdc} USDC</span></div>}
              {campaign.stretch_goals.map((goal) => <div key={goal.id} className="flex justify-between text-muted-foreground"><span>{goal.benefit}</span><span>{goal.amount_usdc} USDC</span></div>)}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Reward tiers</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              {campaign.reward_tiers.map((tier) => <div key={tier.id} className="flex justify-between gap-4"><span>{tier.benefit}</span><span className="shrink-0 text-muted-foreground">{tier.required_units} units</span></div>)}
              {campaign.reward_tiers.length === 0 && <p className="text-muted-foreground">No reward tiers configured.</p>}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader><CardTitle>Purchase</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <label className="block text-sm">Units<input className="mt-1 w-full rounded-md border bg-background px-3 py-2" type="number" min="1" value={units} onChange={(event) => setUnits(Math.max(1, Number(event.target.value)))} /></label>
            <label className="block text-sm">Source token account<input className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs" value={sourceTokenAccount} onChange={(event) => setSourceTokenAccount(event.target.value)} /></label>
            <label className="block text-sm">Escrow token account<input className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs" value={escrowTokenAccount} onChange={(event) => setEscrowTokenAccount(event.target.value)} /></label>
            <Button className="w-full" onClick={() => void purchase()} disabled={busy || !sourceTokenAccount || !escrowTokenAccount}>{busy ? 'Waiting…' : 'Purchase units'}</Button>
            {message && <p className="break-words text-xs text-muted-foreground">{message}</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
