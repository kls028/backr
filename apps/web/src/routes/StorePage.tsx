import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api, type CosmeticItem, type RewardOffer } from '@/lib/api'

export function StorePage() {
  const [cosmetics, setCosmetics] = useState<CosmeticItem[]>([])
  const [offers, setOffers] = useState<RewardOffer[]>([])
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    void Promise.all([api.cosmetics(), api.rewardOffers()]).then(([nextCosmetics, nextOffers]) => {
      setCosmetics(nextCosmetics)
      setOffers(nextOffers)
    }).catch((cause: unknown) => setMessage(cause instanceof Error ? cause.message : 'Store request failed'))
  }, [])

  const redeem = async (kind: 'cosmetic' | 'offer', id: string) => {
    try {
      if (kind === 'cosmetic') await api.redeemCosmetic(id)
      else await api.redeemReward(id)
      setMessage('Redemption reserved')
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : 'Redemption failed')
    }
  }

  return (
    <div className="space-y-8">
      <div><h1 className="text-3xl font-semibold tracking-tight">Store</h1><p className="mt-2 text-muted-foreground">Redeem Support Points.</p></div>
      {message && <p className="text-sm text-muted-foreground">{message}</p>}
      <section><h2 className="mb-3 text-xl font-semibold">Platform cosmetics</h2><div className="grid gap-4 md:grid-cols-2">{cosmetics.map((item) => <Card key={item.id}><CardHeader><CardTitle>{item.name}</CardTitle></CardHeader><CardContent className="space-y-4"><p className="text-sm text-muted-foreground">{item.description}</p><div className="flex items-center justify-between text-sm"><span>{item.support_points_price} points</span><Button size="sm" onClick={() => void redeem('cosmetic', item.id)}>Redeem</Button></div></CardContent></Card>)}</div></section>
      <section><h2 className="mb-3 text-xl font-semibold">Athlete rewards</h2><div className="grid gap-4 md:grid-cols-2">{offers.map((offer) => <Card key={offer.id}><CardHeader><CardTitle>{offer.reward_name}</CardTitle></CardHeader><CardContent className="space-y-4"><p className="text-sm text-muted-foreground">{offer.description}</p><div className="flex items-center justify-between text-sm"><span>{offer.support_points_price} points</span><Button size="sm" onClick={() => void redeem('offer', offer.id)}>Redeem</Button></div></CardContent></Card>)}</div></section>
    </div>
  )
}
