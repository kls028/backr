import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { PageHeader } from '@/components/PageHeader'
import { api, ApiError, type CosmeticItem, type PointsAccount, type RewardOffer } from '@/lib/api'
import { useAuth } from '@/providers/AuthProvider'

type Kind = 'cosmetic' | 'offer'

export function StorePage() {
  const { session, loading } = useAuth()
  const [cosmetics, setCosmetics] = useState<CosmeticItem[] | null>(null)
  const [offers, setOffers] = useState<RewardOffer[] | null>(null)
  const [points, setPoints] = useState<PointsAccount | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [nextCosmetics, nextOffers] = await Promise.all([api.cosmetics(), api.rewardOffers()])
      setCosmetics(nextCosmetics)
      setOffers(nextOffers)
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Store request failed')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  // The balance is the thing that decides whether you can redeem, so it belongs
  // on this page — but only once there is a session to read it with.
  useEffect(() => {
    if (loading || !session) {
      setPoints(null)
      return
    }
    void api
      .points()
      .then(setPoints)
      .catch(() => setPoints(null))
  }, [session, loading])

  async function redeem(kind: Kind, id: string, price: number, name: string) {
    setPending(id)
    try {
      if (kind === 'cosmetic') await api.redeemCosmetic(id)
      else await api.redeemReward(id)
      toast.success('Redeemed', { description: `${name} — ${price} points spent.` })
      // Balance and stock both change on success.
      await load()
      if (session) await api.points().then(setPoints).catch(() => undefined)
    } catch (cause) {
      const message =
        cause instanceof ApiError && cause.status === 401
          ? 'Sign in to redeem.'
          : cause instanceof Error
            ? cause.message
            : 'Redemption failed'
      toast.error('Could not redeem', { description: message })
    } finally {
      setPending(null)
    }
  }

  const signedOut = !loading && !session
  const balance = points?.available_points ?? null

  return (
    <div className="space-y-8">
      <PageHeader
        title="Store"
        description="Spend Support Points on platform cosmetics or athlete rewards. Points are burned when you redeem."
        action={
          balance !== null ? (
            <div className="text-right">
              <p className="text-muted-foreground text-xs tracking-wide uppercase">Available</p>
              <p className="text-xl font-bold tabular-nums">{balance}</p>
            </div>
          ) : undefined
        }
      />

      {signedOut && (
        <p className="text-muted-foreground text-sm">
          Connect your wallet and sign in to redeem. You can browse either way.
        </p>
      )}

      {error && (
        <Card>
          <CardContent className="space-y-3 py-8 text-center">
            <p className="text-destructive text-sm">{error}</p>
            <Button variant="secondary" size="sm" onClick={() => void load()}>
              Try again
            </Button>
          </CardContent>
        </Card>
      )}

      <StoreSection
        title="Platform cosmetics"
        items={cosmetics}
        emptyTitle="No cosmetics yet"
        emptyBody="The platform catalog is empty. Check back once items are published."
        render={(item: CosmeticItem) => ({
          id: item.id,
          name: item.name,
          description: item.description,
          price: item.support_points_price,
          stock: item.available_quantity,
          kind: 'cosmetic' as Kind,
        })}
        onRedeem={redeem}
        disabled={signedOut}
        pending={pending}
        balance={balance}
      />

      <StoreSection
        title="Athlete rewards"
        items={offers}
        emptyTitle="No athlete rewards yet"
        emptyBody="Athletes create these from their workspace."
        render={(offer: RewardOffer) => ({
          id: offer.id,
          name: offer.reward_name,
          description: offer.description,
          price: offer.support_points_price,
          stock: offer.available_quantity,
          kind: 'offer' as Kind,
        })}
        onRedeem={redeem}
        disabled={signedOut}
        pending={pending}
        balance={balance}
      />
    </div>
  )
}

interface StoreItem {
  id: string
  name: string
  description: string
  price: number
  stock: number | null
  kind: Kind
}

function StoreSection<T>({
  title,
  items,
  emptyTitle,
  emptyBody,
  render,
  onRedeem,
  disabled,
  pending,
  balance,
}: {
  title: string
  items: T[] | null
  emptyTitle: string
  emptyBody: string
  render: (item: T) => StoreItem
  onRedeem: (kind: Kind, id: string, price: number, name: string) => Promise<void>
  disabled: boolean
  pending: string | null
  balance: number | null
}) {
  return (
    <section className="space-y-4">
      <h2 className="text-sm font-bold tracking-widest uppercase">{title}</h2>

      {!items && (
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1].map((index) => (
            <Card key={index}>
              <CardHeader>
                <Skeleton className="h-5 w-1/2" />
              </CardHeader>
              <CardContent className="space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-9 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {items && items.length === 0 && (
        <Card>
          <CardContent className="space-y-2 py-10 text-center">
            <p className="text-sm font-medium">{emptyTitle}</p>
            <p className="text-muted-foreground text-sm">{emptyBody}</p>
            {title === 'Athlete rewards' && (
              <Link to="/athlete" className="text-primary inline-block text-sm underline">
                Athlete workspace
              </Link>
            )}
          </CardContent>
        </Card>
      )}

      {items && items.length > 0 && (
        <ul className="grid gap-4 md:grid-cols-2">
          {items.map((raw) => {
            const item = render(raw)
            const soldOut = item.stock !== null && item.stock <= 0
            const tooExpensive = balance !== null && balance < item.price
            return (
              <li key={item.id}>
                <Card className="h-full">
                  <CardHeader>
                    <CardTitle className="text-base">{item.name}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-muted-foreground text-sm">{item.description}</p>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm tabular-nums">
                        {item.price} points
                        {item.stock !== null && (
                          <span className="text-muted-foreground"> · {item.stock} left</span>
                        )}
                      </span>
                      <Button
                        size="sm"
                        disabled={disabled || soldOut || tooExpensive || pending === item.id}
                        onClick={() => void onRedeem(item.kind, item.id, item.price, item.name)}
                      >
                        {pending === item.id
                          ? 'Redeeming…'
                          : soldOut
                            ? 'Sold out'
                            : tooExpensive
                              ? 'Not enough'
                              : 'Redeem'}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
