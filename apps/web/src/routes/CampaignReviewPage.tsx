import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useWallet } from '@solana/wallet-adapter-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CampaignSummary } from '@/components/campaign/CampaignSummary'
import { api, type Campaign } from '@/lib/api'
import { signAndSend } from '@/lib/solana'

export function CampaignReviewPage() {
  const { id = '' } = useParams()
  const { signTransaction } = useWallet()
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [escrowTokenAccount, setEscrowTokenAccount] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    const campaigns = await api.myCampaigns()
    const nextCampaign = campaigns.find((item) => item.id === id) ?? null
    setCampaign(nextCampaign)
    if (nextCampaign?.escrow_token_account) setEscrowTokenAccount(nextCampaign.escrow_token_account)
  }, [id])

  useEffect(() => { void refresh().catch((cause: unknown) => setMessage(cause instanceof Error ? cause.message : 'Campaign request failed')) }, [refresh])

  const publish = async () => {
    if (!campaign || !signTransaction) { setMessage('Connect a wallet before publishing'); return }
    setBusy(true); setMessage(null)
    try {
      const intent = await api.publishCampaign(campaign.id, { escrow_token_account: escrowTokenAccount })
      const signature = await signAndSend(intent.transaction, intent.last_valid_block_height, intent.blockhash, signTransaction)
      const confirmation = await api.confirmCampaign(campaign.id, { signature, campaign_pda: intent.campaign_pda })
      setMessage(`Publication pending verification: ${confirmation.signature}`)
      await refresh()
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Publication failed') }
    finally { setBusy(false) }
  }

  if (!campaign) return <p className="text-sm text-muted-foreground">Loading campaign…</p>
  const pending = campaign.publish_confirmation_status === 'pending'
  return <div className="space-y-6"><div><Link className="text-sm text-muted-foreground hover:text-foreground" to="/athlete">← Athlete workspace</Link><h1 className="mt-3 text-2xl font-bold tracking-wide">Campaign review</h1></div><CampaignSummary campaign={campaign} /><Card><CardHeader><CardTitle>On-chain publication</CardTitle></CardHeader><CardContent className="space-y-4">{pending && <Badge variant="secondary">publish pending verification</Badge>}{campaign.chain_signature && <p className="break-all font-mono text-xs text-muted-foreground">Verified signature: {campaign.chain_signature}</p>}{!campaign.chain_signature && !pending && <label className="block text-sm">Escrow token account<input className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs" value={escrowTokenAccount} onChange={(event) => setEscrowTokenAccount(event.target.value)} /></label>}{!campaign.chain_signature && !pending && <Button onClick={() => void publish()} disabled={busy || !escrowTokenAccount}>{busy ? 'Waiting…' : 'Publish campaign'}</Button>}{message && <p className="break-words text-sm text-muted-foreground">{message}</p>}<Button variant="outline" onClick={() => void refresh()} disabled={busy}>Refresh status</Button></CardContent></Card></div>
}
