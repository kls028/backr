import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api, type FulfillmentDetails, type SupporterRewardOrder } from '@/lib/api'

const message = (cause: unknown, fallback: string) =>
  cause instanceof Error ? cause.message : fallback

// Mirrors the discriminated detail models the API accepts. Sending a field the
// server does not expect for this fulfillment type is a 422.
const DETAIL_FIELDS: Record<string, { name: string; label: string }[]> = {
  digital: [{ name: 'delivery_handle', label: 'Delivery handle' }],
  session: [
    { name: 'preferred_times', label: 'Preferred times' },
    { name: 'contact_handle', label: 'Contact handle' },
  ],
  physical: [
    { name: 'recipient_name', label: 'Recipient name' },
    { name: 'address_line1', label: 'Address line 1' },
    { name: 'address_line2', label: 'Address line 2 (optional)' },
    { name: 'city', label: 'City' },
    { name: 'region', label: 'Region (optional)' },
    { name: 'postal_code', label: 'Postal code' },
    { name: 'country', label: 'Country' },
  ],
}

function FulfillmentDetailsForm({ order }: { order: SupporterRewardOrder }) {
  const queryClient = useQueryClient()
  const [values, setValues] = useState<FulfillmentDetails>({})
  const fields = DETAIL_FIELDS[order.fulfillment_type] ?? []

  const submit = useMutation({
    mutationFn: () => {
      const filled = Object.fromEntries(
        Object.entries(values).filter(([, value]) => value.trim() !== ''),
      )
      return api.submitFulfillmentDetails(order.id, filled)
    },
    onSuccess: async () => {
      toast.success('Details sent to the athlete')
      await queryClient.invalidateQueries({ queryKey: ['my-reward-orders'] })
    },
    onError: (cause: unknown) => toast.error(message(cause, 'Could not send details')),
  })

  return (
    <div className="mt-3 space-y-2 rounded-md border p-3">
      <p className="text-xs text-muted-foreground">
        This reward needs delivery details before the athlete can start work.
      </p>
      <div className="grid gap-2 md:grid-cols-2">
        {fields.map((field) => (
          <label key={field.name} className="text-xs">
            {field.label}
            <input
              className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={values[field.name] ?? ''}
              onChange={(event) =>
                setValues((current) => ({ ...current, [field.name]: event.target.value }))
              }
            />
          </label>
        ))}
      </div>
      <Button size="sm" disabled={submit.isPending} onClick={() => submit.mutate()}>
        {submit.isPending ? 'Sending…' : 'Send details'}
      </Button>
    </div>
  )
}

export function PointsPage() {
  const account = useQuery({ queryKey: ['points'], queryFn: api.points })
  const ledger = useQuery({ queryKey: ['point-ledger'], queryFn: () => api.pointLedger() })
  const orders = useQuery({ queryKey: ['my-reward-orders'], queryFn: api.myRewardOrders })
  const cosmetics = useQuery({ queryKey: ['owned-cosmetics'], queryFn: api.ownedCosmetics })
  const entitlements = useQuery({ queryKey: ['my-entitlements'], queryFn: api.myEntitlements })

  const loadError = account.error ?? ledger.error

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Support Points</h1>
        <p className="mt-2 text-muted-foreground">Balances, history, and everything you unlocked.</p>
      </div>
      {loadError && (
        <p className="text-sm text-destructive">{message(loadError, 'Points request failed')}</p>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Available</CardTitle></CardHeader>
          <CardContent className="text-3xl font-semibold">
            {account.data?.available_points ?? '—'}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Pending</CardTitle></CardHeader>
          <CardContent className="space-y-1">
            <p className="text-3xl font-semibold">{account.data?.pending_points ?? '—'}</p>
            <p className="text-xs text-muted-foreground">
              Released when the campaign settles successfully.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Reward tiers unlocked</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm">
          {(entitlements.data ?? []).map((entitlement) => (
            <div key={entitlement.id} className="flex flex-wrap items-center justify-between gap-3 border-b pb-3 last:border-0">
              <div>
                <p>{entitlement.benefit}</p>
                <p className="text-xs text-muted-foreground">
                  {entitlement.campaign_title} · {entitlement.required_units} units
                </p>
              </div>
              <Badge variant={entitlement.status === 'fulfilled' ? 'default' : 'secondary'}>
                {entitlement.status}
              </Badge>
            </div>
          ))}
          {entitlements.data?.length === 0 && (
            <p className="text-muted-foreground">
              No tiers unlocked yet. Confirmed units unlock campaign rewards.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Reward orders</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm">
          {(orders.data ?? []).map((order) => (
            <div key={order.id} className="border-b pb-3 last:border-0">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p>{order.offer_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {order.athlete_display_name ?? 'Athlete'} · {order.points_spent} points ·{' '}
                    {new Date(order.created_at).toLocaleDateString()}
                  </p>
                </div>
                <Badge variant={order.status === 'fulfilled' ? 'default' : 'secondary'}>
                  {order.status}
                </Badge>
              </div>
              {order.status === 'awaiting_details' && <FulfillmentDetailsForm order={order} />}
            </div>
          ))}
          {orders.data?.length === 0 && (
            <p className="text-muted-foreground">No reward orders yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Cosmetics</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm">
          {(cosmetics.data ?? []).map((item) => (
            <div key={item.id} className="flex justify-between gap-4 border-b pb-3 last:border-0">
              <span>{item.name}</span>
              <span className="shrink-0 text-muted-foreground">
                {new Date(item.acquired_at).toLocaleDateString()}
              </span>
            </div>
          ))}
          {cosmetics.data?.length === 0 && (
            <p className="text-muted-foreground">No cosmetics owned yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Ledger</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm">
          {(ledger.data ?? []).map((entry) => (
            <div key={entry.id} className="flex flex-wrap items-baseline justify-between gap-3 border-b pb-3 last:border-0">
              <div>
                <span>{entry.operation_type}</span>
                <span className="ml-2 text-xs text-muted-foreground">
                  {new Date(entry.created_at).toLocaleString()}
                </span>
              </div>
              <div className="text-right">
                <span className={entry.delta_points > 0 ? 'text-emerald-600' : 'text-destructive'}>
                  {entry.delta_points > 0 ? '+' : ''}{entry.delta_points}
                </span>
                <span className="ml-3 text-xs text-muted-foreground">
                  {entry.available_balance_after} available
                </span>
              </div>
            </div>
          ))}
          {ledger.data?.length === 0 && (
            <p className="text-muted-foreground">No Support Point activity.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
