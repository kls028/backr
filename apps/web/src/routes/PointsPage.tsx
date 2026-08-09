import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api, type PointLedgerEntry, type PointsAccount } from '@/lib/api'

export function PointsPage() {
  const [account, setAccount] = useState<PointsAccount | null>(null)
  const [ledger, setLedger] = useState<PointLedgerEntry[]>([])
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    void Promise.all([api.points(), api.pointLedger()]).then(([nextAccount, nextLedger]) => {
      setAccount(nextAccount)
      setLedger(nextLedger)
    }).catch((cause: unknown) => setMessage(cause instanceof Error ? cause.message : 'Points request failed'))
  }, [])

  return (
    <div className="space-y-6">
      <div><h1 className="text-3xl font-semibold tracking-tight">Support Points</h1><p className="mt-2 text-muted-foreground">Available and pending points.</p></div>
      {message && <p className="text-sm text-destructive">{message}</p>}
      <div className="grid gap-4 md:grid-cols-2">
        <Card><CardHeader><CardTitle>Available</CardTitle></CardHeader><CardContent className="text-3xl font-semibold">{account?.available_points ?? '—'}</CardContent></Card>
        <Card><CardHeader><CardTitle>Pending</CardTitle></CardHeader><CardContent className="text-3xl font-semibold">{account?.pending_points ?? '—'}</CardContent></Card>
      </div>
      <Card><CardHeader><CardTitle>Ledger</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
        {ledger.map((entry) => <div key={entry.id} className="flex justify-between border-b pb-3 last:border-0"><span>{entry.operation_type}</span><span>{entry.delta_points > 0 ? '+' : ''}{entry.delta_points}</span></div>)}
        {ledger.length === 0 && <p className="text-muted-foreground">No Support Point activity.</p>}
      </CardContent></Card>
    </div>
  )
}
