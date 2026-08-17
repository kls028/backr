import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api, ApiError, type PointLedgerEntry, type PointsAccount } from '@/lib/api'
import { useAuth } from '@/providers/AuthProvider'

export function PointsPage() {
  const { session, loading } = useAuth()
  const [account, setAccount] = useState<PointsAccount | null>(null)
  const [ledger, setLedger] = useState<PointLedgerEntry[]>([])
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    // Points are per-supporter, so there is nothing to fetch until there is a
    // session. Requesting anyway produced a 401 and surfaced "Missing bearer
    // token" — a developer's error string in front of a user who simply is not
    // signed in yet.
    if (loading) return
    if (!session) {
      setAccount(null)
      setLedger([])
      setMessage(null)
      return
    }

    void Promise.all([api.points(), api.pointLedger()])
      .then(([nextAccount, nextLedger]) => {
        setAccount(nextAccount)
        setLedger(nextLedger)
        setMessage(null)
      })
      .catch((cause: unknown) => {
        // A 401 here means the session expired mid-session rather than never
        // existing, so say that instead of echoing the transport error.
        if (cause instanceof ApiError && cause.status === 401) {
          setMessage('Your session expired. Sign in again to see your points.')
          return
        }
        setMessage(cause instanceof Error ? cause.message : 'Points request failed')
      })
  }, [session, loading])

  const signedOut = !loading && !session

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Support Points</h1>
        <p className="mt-2 text-muted-foreground">
          100 points per subscription month. Points from pending months stay pending until the
          campaign settles.
        </p>
      </div>

      {signedOut && (
        <p className="text-sm text-muted-foreground">
          Connect your wallet and sign in to see your Support Points.
        </p>
      )}

      {message && (
        <p className="text-sm text-destructive" role="alert">
          {message}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Available</CardTitle>
          </CardHeader>
          <CardContent className="text-3xl font-semibold tabular-nums">
            {account?.available_points ?? '—'}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Pending</CardTitle>
          </CardHeader>
          <CardContent className="text-3xl font-semibold tabular-nums">
            {account?.pending_points ?? '—'}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Ledger</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {ledger.map((entry) => (
            <div key={entry.id} className="flex justify-between border-b pb-3 last:border-0">
              <span>{entry.operation_type}</span>
              <span className="tabular-nums">
                {entry.delta_points > 0 ? '+' : ''}
                {entry.delta_points}
              </span>
            </div>
          ))}
          {ledger.length === 0 && (
            <p className="text-muted-foreground">
              {signedOut ? 'Sign in to see your activity.' : 'No Support Point activity.'}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
