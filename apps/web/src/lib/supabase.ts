import { createClient } from '@supabase/supabase-js'

const configuredUrl = import.meta.env.VITE_SUPABASE_URL
const configuredAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY
export const supabaseConfigured = Boolean(configuredUrl && configuredAnonKey)

// Keep the application shell renderable before local Supabase or hosted
// credentials exist. Authenticated requests still fail closed in the API; this
// fallback only prevents a module-level exception from blanking the UI.
const url = configuredUrl ?? 'http://127.0.0.1:54421'
const anonKey = configuredAnonKey ?? 'local-placeholder-anon-key'

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
