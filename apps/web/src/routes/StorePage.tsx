import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api, type CosmeticItem, type RewardOffer } from '@/lib/api'

const message = (cause: unknown, fallback: string) =>
  cause instanceof Error ? cause.message : fallback

/** Why an item cannot be redeemed right now, or null when it can. */
function offerBlocker(offer: RewardOffer, available: number, now: number): string | null {
  if (offer.availability_start && now < Date.parse(offer.availability_start)) {
    return 'Not available yet'
  }
  if (offer.availability_end && now >= Date.parse(offer.availability_end)) {
    return 'No longer available'
  }
  if (offer.available_quantity !== null && offer.available_quantity <= 0) return 'Sold out'
  if (available < offer.support_points_price) {
    return `Need ${offer.support_points_price - available} more points`
  }
  return null
}

export function StorePage() {
  const queryClient = useQueryClient()
  const points = useQuery({ queryKey: ['points'], queryFn: api.points })
  const cosmetics = useQuery({ queryKey: ['cosmetics'], queryFn: api.cosmetics })
  const offers = useQuery({ queryKey: ['reward-offers'], queryFn: api.rewardOffers })
  const owned = useQuery({ queryKey: ['owned-cosmetics'], queryFn: api.ownedCosmetics })

  // The balance drives every disabled state, so a redemption has to invalidate
  // it alongside the catalog it just decremented.
  const invalidate = async (...keys: string[]) => {
    await Promise.all(
      [['points'], ...keys.map((key) => [key])].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey }),
      ),
    )
  }

  const redeemCosmetic = useMutation({
    mutationFn: (id: string) => api.redeemCosmetic(id),
    onSuccess: async (order) => {
      toast.success(
        order.points_spent === 0
          ? 'You already own this cosmetic'
          : `Redeemed for ${order.points_spent} points`,
      )
      await invalidate('cosmetics', 'owned-cosmetics')
    },
    onError: (cause: unknown) => toast.error(message(cause, 'Redemption failed')),
  })

  const redeemOffer = useMutation({
    mutationFn: (id: string) => api.redeemReward(id),
    onSuccess: async (order) => {
      toast.success(
        order.status === 'awaiting_details'
          ? 'Reserved. Add your delivery details on the Points page.'
          : 'Reward reserved',
      )
      await invalidate('reward-offers', 'my-reward-orders')
    },
    onError: (cause: unknown) => toast.error(message(cause, 'Redemption failed')),
  })

  const available = points.data?.available_points ?? 0
  const ownedIds = new Set((owned.data ?? []).map((item) => item.cosmetic_item_id))
  const now = Date.now()
  const loadError = cosmetics.error ?? offers.error

  const cosmeticBlocker = (item: CosmeticItem): string | null => {
    if (ownedIds.has(item.id)) return 'Owned'
    if (item.available_quantity !== null && item.available_quantity <= 0) return 'Sold out'
    if (available < item.support_points_price) {
      return `Need ${item.support_points_price - available} more points`
    }
    return null
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Store</h1>
          <p className="mt-2 text-muted-foreground">Redeem Support Points.</p>
        </div>
        <div className="text-right text-sm">
          <p className="text-muted-foreground">Available</p>
          <p className="text-2xl font-semibold">{points.data?.available_points ?? '—'} points</p>
          {(points.data?.pending_points ?? 0) > 0 && (
            <p className="text-xs text-muted-foreground">
              {points.data?.pending_points} pending, not yet spendable
            </p>
          )}
        </div>
      </div>

      {loadError && (
        <p className="text-sm text-destructive">{message(loadError, 'Store request failed')}</p>
      )}

      <section>
        <h2 className="mb-3 text-xl font-semibold">Platform cosmetics</h2>
        {cosmetics.isPending && <p className="text-sm text-muted-foreground">Loading cosmetics…</p>}
        {cosmetics.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">No cosmetics are available yet.</p>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          {(cosmetics.data ?? []).map((item) => {
            const blocker = cosmeticBlocker(item)
            const busy = redeemCosmetic.isPending && redeemCosmetic.variables === item.id
            return (
              <Card key={item.id}>
                <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
                  <CardTitle>{item.name}</CardTitle>
                  {ownedIds.has(item.id) && <Badge variant="secondary">Owned</Badge>}
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-sm text-muted-foreground">{item.description}</p>
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <div>
                      <span>{item.support_points_price} points</span>
                      {item.available_quantity !== null && (
                        <span className="ml-2 text-muted-foreground">
                          {item.available_quantity} left
                        </span>
                      )}
                    </div>
                    <Button
                      size="sm"
                      disabled={blocker !== null || busy}
                      onClick={() => redeemCosmetic.mutate(item.id)}
                    >
                      {busy ? 'Redeeming…' : (blocker ?? 'Redeem')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xl font-semibold">Athlete rewards</h2>
        {offers.isPending && <p className="text-sm text-muted-foreground">Loading rewards…</p>}
        {offers.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">No athlete rewards are on offer yet.</p>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          {(offers.data ?? []).map((offer) => {
            const blocker = offerBlocker(offer, available, now)
            const busy = redeemOffer.isPending && redeemOffer.variables === offer.id
            return (
              <Card key={offer.id}>
                <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
                  <CardTitle>{offer.reward_name}</CardTitle>
                  <Badge variant="outline">{offer.fulfillment_type}</Badge>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-sm text-muted-foreground">{offer.description}</p>
                  <div className="space-y-1 text-xs text-muted-foreground">
                    {offer.available_quantity !== null && <p>{offer.available_quantity} remaining</p>}
                    {offer.maximum_per_user !== null && (
                      <p>Limit {offer.maximum_per_user} per supporter</p>
                    )}
                    {offer.availability_end && (
                      <p>Closes {new Date(offer.availability_end).toLocaleString()}</p>
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span>{offer.support_points_price} points</span>
                    <Button
                      size="sm"
                      disabled={blocker !== null || busy}
                      onClick={() => redeemOffer.mutate(offer.id)}
                    >
                      {busy ? 'Reserving…' : (blocker ?? 'Redeem')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </section>
    </div>
  )
}
