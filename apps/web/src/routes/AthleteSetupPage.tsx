import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { api } from '@/lib/api'

export function AthleteSetupPage() {
  const [displayName, setDisplayName] = useState('')
  const [sport, setSport] = useState('')
  const [bio, setBio] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void api.me().then((profile) => { setDisplayName(profile.display_name ?? '') }).catch(() => undefined)
  }, [])

  const save = async () => {
    setBusy(true)
    setMessage(null)
    try { await api.activateAthleteProfile({ display_name: displayName, sport, bio }); setMessage('Athlete profile saved') }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Profile request failed') }
    finally { setBusy(false) }
  }

  return <div className="mx-auto max-w-2xl space-y-6"><div><Link className="text-sm text-muted-foreground hover:text-foreground" to="/athlete">← Athlete workspace</Link><h1 className="mt-3 text-3xl font-semibold tracking-tight">Athlete setup</h1></div><Card><CardHeader><CardTitle>Profile</CardTitle></CardHeader><CardContent className="space-y-4"><label className="block text-sm">Display name<input className="mt-1 w-full rounded-md border bg-background px-3 py-2" value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label><label className="block text-sm">Sport<input className="mt-1 w-full rounded-md border bg-background px-3 py-2" value={sport} onChange={(event) => setSport(event.target.value)} /></label><label className="block text-sm">Bio<textarea className="mt-1 min-h-32 w-full rounded-md border bg-background px-3 py-2" value={bio} onChange={(event) => setBio(event.target.value)} /></label><Button onClick={() => void save()} disabled={busy || !displayName.trim()}>{busy ? 'Saving…' : 'Save profile'}</Button>{message && <p className="text-sm text-muted-foreground">{message}</p>}</CardContent></Card></div>
}
