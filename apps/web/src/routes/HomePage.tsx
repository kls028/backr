import { useWallet } from '@solana/wallet-adapter-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useAuth } from '@/providers/AuthProvider'
import { shortAddress, RPC_URL } from '@/lib/solana'

export function HomePage() {
  const { publicKey, connected } = useWallet()
  const { session, error } = useAuth()

  const rows = [
    { label: 'Wallet', value: connected && publicKey ? shortAddress(publicKey.toBase58()) : 'not connected' },
    { label: 'Supabase session', value: session ? 'active' : 'none' },
    { label: 'RPC endpoint', value: RPC_URL },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">sss-project</h1>
        <p className="mt-2 text-muted-foreground">
          Anchor program for on-chain truth, Supabase for the derived read model, FastAPI in
          between building transactions your wallet signs.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Connection status</CardTitle>
          <CardDescription>
            Connecting a wallet and signing in happen as one step. Connecting proves you hold a
            key; the signature that follows exchanges it for a Supabase session.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {rows.map((row) => (
            <div key={row.label} className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{row.label}</span>
              <span className="font-mono">{row.value}</span>
            </div>
          ))}
          {error && (
            <Badge variant="destructive" className="mt-2">
              {error}
            </Badge>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
