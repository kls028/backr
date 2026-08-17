import { useEffect, useMemo, useState } from 'react'
import { useWallet } from '@solana/wallet-adapter-react'
import { PublicKey } from '@solana/web3.js'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { api, ApiError, type Campaign, type PlatformConfig } from '@/lib/api'
import { estimatePurchase } from '@/lib/purchase'
import { associatedTokenAddress, shortAddress, signAndSend } from '@/lib/solana'
import { useAuth } from '@/providers/AuthProvider'

/**
 * Buy subscription units in a campaign.
 *
 * The money path the user is agreeing to (spec F): exactly one unit activates
 * immediately and is non-refundable, every other unit sits in escrow until the
 * campaign settles. That is surprising enough that the summary states it plainly
 * before the wallet prompt rather than after.
 *
 * The backend builds and simulates the transaction; the browser only signs and
 * submits. No key material passes through the API.
 */

type Phase = 'idle' | 'building' | 'signing' | 'confirming' | 'done'

export function PurchaseCard({ campaign }: { campaign: Campaign }) {
  const { publicKey, connected, signTransaction } = useWallet()
  const { session } = useAuth()

  const [units, setUnits] = useState(1)
  const [config, setConfig] = useState<PlatformConfig | null>(null)
  const [configError, setConfigError] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [signature, setSignature] = useState<string | null>(null)

  useEffect(() => {
    void api
      .config()
      .then(setConfig)
      .catch((cause: unknown) =>
        setConfigError(cause instanceof Error ? cause.message : 'Could not load platform config'),
      )
  }, [])

  const estimate = useMemo(
    () => (config ? estimatePurchase(units, campaign, config) : null),
    [units, campaign, config],
  )

  const openForPurchase =
    ['scheduled', 'active', 'funded'].includes(campaign.status) &&
    new Date(campaign.end_at).getTime() > Date.now()

  const busy = phase === 'building' || phase === 'signing' || phase === 'confirming'

  // One reason at a time, in the order the user can act on them.
  const blocker = !openForPurchase
    ? 'This campaign is not accepting purchases.'
    : configError
      ? configError
      : config && !config.configured
        ? 'Purchases are unavailable: the deployment has no USDC mint configured.'
        : !campaign.escrow_token_account
          ? 'This campaign has no escrow account yet, so it cannot accept payment.'
          : !connected
            ? 'Connect your wallet to buy subscription months.'
            : !session
              ? 'Sign in with your wallet to continue.'
              : !signTransaction
                ? 'This wallet cannot sign transactions.'
                : null

  async function buy() {
    if (!publicKey || !signTransaction || !config || !campaign.escrow_token_account) return

    setError(null)
    setSignature(null)
    setPhase('building')

    try {
      const source = associatedTokenAddress(publicKey, new PublicKey(config.usdc_mint))

      const intent = await api.purchase(campaign.id, {
        purchased_units: units,
        source_token_account: source.toBase58(),
        escrow_token_account: campaign.escrow_token_account,
      })

      setPhase('signing')
      const sig = await signAndSend(
        intent.transaction,
        intent.last_valid_block_height,
        intent.blockhash,
        signTransaction,
      )

      setPhase('confirming')
      setSignature(sig)
      setPhase('done')
      toast.success('Purchase confirmed', {
        description: `${intent.immediate_units} month active now, ${intent.pending_units} pending until settlement.`,
      })
    } catch (cause) {
      setPhase('idle')
      const message =
        cause instanceof ApiError && typeof cause.detail === 'object' && cause.detail !== null
          ? JSON.stringify(cause.detail)
          : cause instanceof Error
            ? cause.message
            : 'Purchase failed'
      setError(message)
      toast.error('Purchase failed', { description: message })
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Buy subscription months</CardTitle>
        <CardDescription>
          {campaign.unit_price_usdc} USDC per month. One month activates immediately and is
          non-refundable; the rest stay in escrow until the campaign settles.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="space-y-2">
          <label htmlFor="units" className="text-sm font-medium">
            Months
          </label>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Decrease months"
              disabled={units <= 1 || busy}
              onClick={() => setUnits((value) => Math.max(1, value - 1))}
            >
              −
            </Button>
            <input
              id="units"
              type="number"
              inputMode="numeric"
              min={1}
              max={1000}
              value={units}
              disabled={busy}
              onChange={(event) => {
                const next = Number.parseInt(event.target.value, 10)
                setUnits(Number.isNaN(next) ? 1 : Math.min(1000, Math.max(1, next)))
              }}
              className="h-10 w-24 rounded-md border border-input bg-background px-3 text-center tabular-nums focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Increase months"
              disabled={units >= 1000 || busy}
              onClick={() => setUnits((value) => Math.min(1000, value + 1))}
            >
              +
            </Button>
          </div>
        </div>

        {estimate && (
          <dl className="space-y-2 rounded-md border p-4 text-sm">
            <Row label="Total" value={`${estimate.totalUsdc} USDC`} emphasis />
            <Row label="Active immediately" value={`${estimate.immediateUnits} month`} />
            <Row label="Pending until settlement" value={`${estimate.pendingUnits} months`} />
            <Row label="Support Points confirmed now" value={String(estimate.confirmedPoints)} />
            <Row label="Support Points pending" value={String(estimate.pendingPoints)} />
            <Row
              label="Bonus if the campaign succeeds"
              value={`+${estimate.successBonusPoints}`}
            />
            <Row
              label="Reward tier reached"
              value={estimate.tier ? estimate.tier.benefit : 'None yet'}
            />
          </dl>
        )}

        {!estimate && !configError && (
          <p className="text-sm text-muted-foreground">Loading platform configuration…</p>
        )}

        {blocker && <p className="text-sm text-muted-foreground">{blocker}</p>}

        {error && (
          <p className="text-sm break-words text-destructive" role="alert">
            {error}
          </p>
        )}

        {signature && (
          <div className="space-y-1 rounded-md border border-emerald-600/40 p-3 text-sm dark:border-emerald-400/40">
            <p className="font-medium">Purchase confirmed</p>
            <p className="font-mono text-xs break-all text-muted-foreground">
              {shortAddress(signature, 10)}
            </p>
          </div>
        )}

        <div className="flex items-center gap-3">
          <Button onClick={() => void buy()} disabled={Boolean(blocker) || busy || !estimate}>
            {phase === 'building' && 'Preparing…'}
            {phase === 'signing' && 'Check your wallet…'}
            {phase === 'confirming' && 'Confirming…'}
            {(phase === 'idle' || phase === 'done') &&
              (estimate ? `Buy for ${estimate.totalUsdc} USDC` : 'Buy')}
          </Button>
          {campaign.status && <Badge variant="secondary">{campaign.status}</Badge>}
        </div>
      </CardContent>
    </Card>
  )
}

function Row({
  label,
  value,
  emphasis = false,
}: {
  label: string
  value: string
  emphasis?: boolean
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={emphasis ? 'font-semibold tabular-nums' : 'tabular-nums'}>{value}</dd>
    </div>
  )
}
