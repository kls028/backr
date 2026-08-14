import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  FULFILLMENT_TYPES,
  api,
  type AthleteRewardOrderRow,
  type Entitlement,
  type FulfillmentType,
  type OrderStatus,
  type RewardOfferInput,
} from '@/lib/api'

const message = (cause: unknown, fallback: string) =>
  cause instanceof Error ? cause.message : fallback

// Shared with CampaignForm: a datetime-local value is wall-clock, so it has to
// be widened to an ISO instant before it crosses the API boundary.
const apiDate = (value: string) => {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

const emptyOffer = (): RewardOfferInput => ({
  reward_name: '',
  description: '',
  support_points_price: 100,
  available_quantity: null,
  maximum_per_user: null,
  availability_start: null,
  availability_end: null,
  fulfillment_type: 'digital',
  metadata_uri: null,
})

const fieldClass = 'mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm'

function OfferComposer() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<RewardOfferInput>(emptyOffer)
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')

  const set = <K extends keyof RewardOfferInput>(key: K, value: RewardOfferInput[K]) =>
    setDraft((current) => ({ ...current, [key]: value }))

  const create = useMutation({
    mutationFn: () =>
      api.createRewardOffer({
        ...draft,
        availability_start: apiDate(start),
        availability_end: apiDate(end),
      }),
    onSuccess: async () => {
      toast.success('Reward offer published')
      setDraft(emptyOffer())
      setStart('')
      setEnd('')
      await queryClient.invalidateQueries({ queryKey: ['my-reward-offers'] })
    },
    onError: (cause: unknown) => toast.error(message(cause, 'Could not create the offer')),
  })

  const incomplete = draft.reward_name.trim() === '' || draft.description.trim() === ''

  return (
    <Card>
      <CardHeader><CardTitle>New reward offer</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">
            Reward name
            <input className={fieldClass} maxLength={120} value={draft.reward_name} onChange={(event) => set('reward_name', event.target.value)} />
          </label>
          <label className="text-sm">
            Fulfillment type
            <select className={fieldClass} value={draft.fulfillment_type} onChange={(event) => set('fulfillment_type', event.target.value as FulfillmentType)}>
              {FULFILLMENT_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </label>
        </div>
        <label className="block text-sm">
          Description
          <textarea className={`${fieldClass} min-h-24`} maxLength={2000} value={draft.description} onChange={(event) => set('description', event.target.value)} />
        </label>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="text-sm">
            Points price
            <input className={fieldClass} type="number" min="1" value={draft.support_points_price} onChange={(event) => set('support_points_price', Math.max(1, Number(event.target.value)))} />
          </label>
          <label className="text-sm">
            Quantity
            <input className={fieldClass} type="number" min="0" placeholder="Unlimited" value={draft.available_quantity ?? ''} onChange={(event) => set('available_quantity', event.target.value === '' ? null : Math.max(0, Number(event.target.value)))} />
          </label>
          <label className="text-sm">
            Limit per supporter
            <input className={fieldClass} type="number" min="1" placeholder="No limit" value={draft.maximum_per_user ?? ''} onChange={(event) => set('maximum_per_user', event.target.value === '' ? null : Math.max(1, Number(event.target.value)))} />
          </label>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">
            Opens (optional)
            <input className={fieldClass} type="datetime-local" value={start} onChange={(event) => setStart(event.target.value)} />
          </label>
          <label className="text-sm">
            Closes (optional)
            <input className={fieldClass} type="datetime-local" value={end} onChange={(event) => setEnd(event.target.value)} />
          </label>
        </div>
        <Button disabled={incomplete || create.isPending} onClick={() => create.mutate()}>
          {create.isPending ? 'Publishing…' : 'Publish offer'}
        </Button>
      </CardContent>
    </Card>
  )
}

function OfferList() {
  const queryClient = useQueryClient()
  const offers = useQuery({ queryKey: ['my-reward-offers'], queryFn: api.myRewardOffers })

  const archive = useMutation({
    mutationFn: (id: string) => api.updateRewardOffer(id, { status: 'archived' }),
    onSuccess: async () => {
      toast.success('Offer archived')
      await queryClient.invalidateQueries({ queryKey: ['my-reward-offers'] })
    },
    onError: (cause: unknown) => toast.error(message(cause, 'Could not archive the offer')),
  })

  const restock = useMutation({
    mutationFn: (input: { id: string; quantity: number }) =>
      api.updateRewardOffer(input.id, { available_quantity: input.quantity }),
    onSuccess: async () => {
      toast.success('Inventory updated')
      await queryClient.invalidateQueries({ queryKey: ['my-reward-offers'] })
    },
    onError: (cause: unknown) => toast.error(message(cause, 'Could not update inventory')),
  })

  return (
    <Card>
      <CardHeader><CardTitle>My offers</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        {offers.isPending && <p className="text-muted-foreground">Loading offers…</p>}
        {offers.error && (
          <p className="text-destructive">{message(offers.error, 'Offer request failed')}</p>
        )}
        {(offers.data ?? []).map((offer) => (
          <div key={offer.id} className="flex flex-wrap items-center justify-between gap-3 border-b pb-3 last:border-0">
            <div className="min-w-0">
              <p>{offer.reward_name}</p>
              <p className="text-xs text-muted-foreground">
                {offer.support_points_price} points · {offer.fulfillment_type}
                {offer.available_quantity !== null && ` · ${offer.available_quantity} left`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={offer.status === 'active' ? 'default' : 'secondary'}>{offer.status}</Badge>
              {offer.available_quantity !== null && (
                <Button size="sm" variant="outline" disabled={restock.isPending} onClick={() => restock.mutate({ id: offer.id, quantity: offer.available_quantity! + 10 })}>
                  +10 stock
                </Button>
              )}
              {offer.status === 'active' && (
                <Button size="sm" variant="ghost" disabled={archive.isPending} onClick={() => archive.mutate(offer.id)}>
                  Archive
                </Button>
              )}
            </div>
          </div>
        ))}
        {offers.data?.length === 0 && (
          <p className="text-muted-foreground">No offers published yet.</p>
        )}
      </CardContent>
    </Card>
  )
}

function OrderRow({ order }: { order: AthleteRewardOrderRow }) {
  const queryClient = useQueryClient()
  const [target, setTarget] = useState('')
  const [reference, setReference] = useState('')

  const move = useMutation({
    mutationFn: () =>
      api.transitionRewardOrder(order.id, {
        status: target as OrderStatus,
        fulfillment_reference: reference.trim() || null,
      }),
    onSuccess: async () => {
      toast.success(`Order moved to ${target}`)
      setTarget('')
      setReference('')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['athlete-reward-orders'] }),
        queryClient.invalidateQueries({ queryKey: ['my-reward-offers'] }),
      ])
    },
    onError: (cause: unknown) => toast.error(message(cause, 'Transition rejected')),
  })

  return (
    <div className="space-y-2 border-b pb-3 last:border-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm">{order.offer_name}</p>
          <p className="text-xs text-muted-foreground">
            {order.supporter_display_name ?? 'Supporter'} · {order.points_spent} points ·{' '}
            {order.fulfillment_type}
          </p>
        </div>
        <Badge variant={order.status === 'fulfilled' ? 'default' : 'secondary'}>{order.status}</Badge>
      </div>

      {order.fulfillment_details && (
        <dl className="rounded-md border p-2 text-xs">
          {Object.entries(order.fulfillment_details).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-3">
              <dt className="text-muted-foreground">{key.replaceAll('_', ' ')}</dt>
              <dd className="text-right">{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}

      {order.allowed_transitions.length > 0 ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs">
            Move to
            {/* Options come from the server so the state machine lives in one place. */}
            <select className={`${fieldClass} w-44`} value={target} onChange={(event) => setTarget(event.target.value)}>
              <option value="">Select…</option>
              {order.allowed_transitions.map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </label>
          <label className="flex-1 text-xs">
            Reference (optional)
            <input className={fieldClass} maxLength={200} placeholder="Tracking or booking reference" value={reference} onChange={(event) => setReference(event.target.value)} />
          </label>
          <Button size="sm" disabled={target === '' || move.isPending} onClick={() => move.mutate()}>
            {move.isPending ? 'Saving…' : 'Apply'}
          </Button>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">This order is closed.</p>
      )}
    </div>
  )
}

function EntitlementRow({ entitlement }: { entitlement: Entitlement }) {
  const queryClient = useQueryClient()
  const move = useMutation({
    mutationFn: (status: string) =>
      api.transitionEntitlement(entitlement.id, {
        status: status as Entitlement['status'],
      }),
    onSuccess: async () => {
      toast.success('Entitlement updated')
      await queryClient.invalidateQueries({ queryKey: ['athlete-entitlements'] })
    },
    onError: (cause: unknown) => toast.error(message(cause, 'Transition rejected')),
  })

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-3 last:border-0">
      <div className="min-w-0">
        <p className="text-sm">{entitlement.benefit}</p>
        <p className="text-xs text-muted-foreground">
          {entitlement.supporter_display_name ?? 'Supporter'} · {entitlement.campaign_title} ·{' '}
          {entitlement.required_units} units
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant={entitlement.status === 'fulfilled' ? 'default' : 'secondary'}>
          {entitlement.status}
        </Badge>
        {entitlement.allowed_transitions.map((status) => (
          <Button key={status} size="sm" variant="outline" disabled={move.isPending} onClick={() => move.mutate(status)}>
            {status.replaceAll('_', ' ')}
          </Button>
        ))}
      </div>
    </div>
  )
}

export function AthleteRewardsPage() {
  const [statusFilter, setStatusFilter] = useState('')
  const orders = useQuery({
    queryKey: ['athlete-reward-orders', statusFilter],
    queryFn: () => api.athleteRewardOrders(statusFilter === '' ? undefined : (statusFilter as OrderStatus)),
  })
  const entitlements = useQuery({
    queryKey: ['athlete-entitlements'],
    queryFn: () => api.athleteEntitlements(),
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Rewards</h1>
        <p className="mt-2 text-muted-foreground">
          Publish Support Point offers and work through fulfillment.
        </p>
        <Link className="mt-2 inline-block text-sm underline" to="/athlete">Back to athlete hub</Link>
      </div>

      <OfferComposer />
      <OfferList />

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0">
          <CardTitle>Fulfillment queue</CardTitle>
          <select className="rounded-md border bg-background px-3 py-2 text-sm" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">All statuses</option>
            <option value="reserved">reserved</option>
            <option value="awaiting_details">awaiting_details</option>
            <option value="in_progress">in_progress</option>
            <option value="shipped">shipped</option>
            <option value="scheduled">scheduled</option>
            <option value="fulfilled">fulfilled</option>
          </select>
        </CardHeader>
        <CardContent className="space-y-3">
          {orders.isPending && <p className="text-sm text-muted-foreground">Loading orders…</p>}
          {orders.error && (
            <p className="text-sm text-destructive">{message(orders.error, 'Order request failed')}</p>
          )}
          {(orders.data ?? []).map((order) => <OrderRow key={order.id} order={order} />)}
          {orders.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">Nothing in the queue.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Campaign tier entitlements</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {entitlements.isPending && (
            <p className="text-sm text-muted-foreground">Loading entitlements…</p>
          )}
          {(entitlements.data ?? []).map((entitlement) => (
            <EntitlementRow key={entitlement.id} entitlement={entitlement} />
          ))}
          {entitlements.data?.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No supporter has unlocked a campaign tier yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
