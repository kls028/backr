import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!url || !anonKey) {
  throw new Error(
    'Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY. Copy .env.example to .env and fill them in — `supabase start` prints both.',
  )
}

/**
 * Browser-side Supabase client.
 *
 * This talks to Supabase directly for auth and for reads that RLS can protect.
 * Anything that needs to be trusted — building transactions, writing indexed
 * data — goes through the FastAPI backend instead. The anon key is public by
 * design; RLS is what actually protects the data.
 */
export const supabase = createClient(url, anonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: false,
  },
})
