import { type ReactNode, useMemo } from 'react'
import { ConnectionProvider, WalletProvider } from '@solana/wallet-adapter-react'
import { WalletModalProvider } from '@solana/wallet-adapter-react-ui'
import { RPC_URL } from '@/lib/solana'

import '@solana/wallet-adapter-react-ui/styles.css'

/**
 * Wallet plumbing.
 *
 * The `wallets` array is intentionally empty: every current wallet implements
 * the Wallet Standard and registers itself with the browser, so the adapter
 * discovers them automatically. Adding entries from
 * @solana/wallet-adapter-wallets would pull in a large bundle to list wallets
 * that are already there.
 */
export function SolanaProvider({ children }: { children: ReactNode }) {
  const endpoint = useMemo(() => RPC_URL, [])

  return (
    <ConnectionProvider endpoint={endpoint}>
      <WalletProvider wallets={[]} autoConnect>
        <WalletModalProvider>{children}</WalletModalProvider>
      </WalletProvider>
    </ConnectionProvider>
  )
}
