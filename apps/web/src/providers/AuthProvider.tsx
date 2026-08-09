import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type { Session } from '@supabase/supabase-js'
import { useWallet } from '@solana/wallet-adapter-react'
import { supabase } from '@/lib/supabase'

interface AuthState {
  session: Session | null
  /** True until the initial session lookup resolves — avoids a signed-out flash. */
  loading: boolean
  signingIn: boolean
  /** The user dismissed the signature prompt. Surfaces a retry instead of nagging. */
  declined: boolean
  error: string | null
  signIn: () => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [signingIn, setSigningIn] = useState(false)
  const [declined, setDeclined] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const wallet = useWallet()
  // Which pubkey we have already auto-prompted for. Without this, every render
  // that briefly clears the session would fire another signature request.
  const promptedFor = useRef<string | null>(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next)
    })

    return () => subscription.subscription.unsubscribe()
  }, [])

  const signIn = useCallback(async () => {
    setError(null)

    if (!wallet.publicKey || !wallet.signMessage) {
      setError('Connect a wallet first')
      return
    }

    setSigningIn(true)
    try {
      // Sign-In-With-Solana. Supabase builds the SIWS message, the wallet signs
      // it, and Supabase verifies the signature and issues a JWT. No nonce
      // store, no custom session handling on our side.
      //
      // The message URI is window.location.href, which must appear in Supabase's
      // additional_redirect_urls — hence the /** globs in config.toml. Without
      // them this fails with "message was signed for another app".
      const { error: signInError } = await supabase.auth.signInWithWeb3({
        chain: 'solana',
        statement: 'Sign in to Backr.',
        wallet: {
          publicKey: wallet.publicKey,
          signMessage: wallet.signMessage,
        },
      } as Parameters<typeof supabase.auth.signInWithWeb3>[0])

      if (signInError) {
        setDeclined(true)
        setError(signInError.message)
      }
    } catch (cause) {
      // Wallets throw when the user rejects the signature. That is a choice,
      // not a failure, so stop prompting and let them retry deliberately.
      setDeclined(true)
      setError(cause instanceof Error ? cause.message : 'Sign-in failed')
    } finally {
      setSigningIn(false)
    }
  }, [wallet])

  const signOut = useCallback(async () => {
    promptedFor.current = null
    setDeclined(false)
    await supabase.auth.signOut()
    setSession(null)
  }, [])

  // Connecting a wallet and proving you own it are one intent, so the signature
  // prompt follows connection automatically. Exactly once per pubkey, and never
  // again after a rejection until the user asks.
  useEffect(() => {
    if (!wallet.connected || !wallet.publicKey) {
      promptedFor.current = null
      setDeclined(false)
      return
    }

    if (session || signingIn || declined || loading) return

    const address = wallet.publicKey.toBase58()
    if (promptedFor.current === address) return

    promptedFor.current = address
    void signIn()
  }, [wallet.connected, wallet.publicKey, session, signingIn, declined, loading, signIn])

  // A session tied to a wallet you are no longer holding is a confusing state,
  // so disconnecting ends it.
  useEffect(() => {
    if (!wallet.connected && session) {
      void supabase.auth.signOut()
    }
  }, [wallet.connected, session])

  const value = useMemo<AuthState>(
    () => ({ session, loading, signingIn, declined, error, signIn, signOut }),
    [session, loading, signingIn, declined, error, signIn, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
