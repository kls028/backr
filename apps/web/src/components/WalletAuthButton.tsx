import { useCallback, useState } from 'react'
import { useWallet } from '@solana/wallet-adapter-react'
import { useWalletModal } from '@solana/wallet-adapter-react-ui'
import { Check, ChevronDown, Copy, LogOut, Wallet } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuth } from '@/providers/AuthProvider'
import { shortAddress } from '@/lib/solana'

/**
 * One button for the whole identity flow.
 *
 * Connecting a wallet and signing in are two protocol steps but one user
 * intent, so they are presented as one: pick a wallet, approve the signature,
 * done. AuthProvider fires the signature request automatically once a wallet
 * connects, so there is no second button to hunt for.
 *
 * The one case that still needs a button is a rejected signature — then we show
 * an explicit retry rather than re-prompting, because re-prompting someone who
 * just said no is how you get uninstalled.
 */
export function WalletAuthButton() {
  const { publicKey, connected, connecting, disconnect } = useWallet()
  const { setVisible } = useWalletModal()
  const { session, signingIn, declined, signIn, signOut } = useAuth()
  const [copied, setCopied] = useState(false)

  const address = publicKey?.toBase58()

  const handleSignOut = useCallback(async () => {
    await signOut()
    await disconnect()
  }, [signOut, disconnect])

  const handleCopy = useCallback(async () => {
    if (!address) return
    await navigator.clipboard.writeText(address)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [address])

  // --- Signed in: address chip with a menu -------------------------------
  if (session && address) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" className="font-mono">
            <Wallet className="size-4" aria-hidden="true" />
            {shortAddress(address)}
            <ChevronDown className="size-4 opacity-60" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuItem onSelect={(event) => event.preventDefault()} onClick={handleCopy}>
            {copied ? (
              <Check className="size-4" aria-hidden="true" />
            ) : (
              <Copy className="size-4" aria-hidden="true" />
            )}
            {copied ? 'Copied' : 'Copy address'}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => void handleSignOut()}>
            <LogOut className="size-4" aria-hidden="true" />
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    )
  }

  // --- Connected, signature pending or rejected --------------------------
  if (connected) {
    if (signingIn) {
      return (
        <Button disabled>
          <Wallet className="size-4" aria-hidden="true" />
          Check your wallet…
        </Button>
      )
    }

    if (declined) {
      return (
        <Button onClick={() => void signIn()}>
          <Wallet className="size-4" aria-hidden="true" />
          Sign in to continue
        </Button>
      )
    }
  }

  // --- Not connected ------------------------------------------------------
  return (
    <Button onClick={() => setVisible(true)} disabled={connecting}>
      <Wallet className="size-4" aria-hidden="true" />
      {connecting ? 'Connecting…' : 'Connect wallet'}
    </Button>
  )
}
