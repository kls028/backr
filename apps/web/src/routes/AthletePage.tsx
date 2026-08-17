import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader } from '@/components/PageHeader'
import { api, ApiError, type Campaign, type SubscriptionPlan } from '@/lib/api'
import { useAuth } from '@/providers/AuthProvider'

export function AthletePage() {
  const { session, loading } = useAuth()
  const [plan, setPlan] = useState<SubscriptionPlan | null>(null)
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Both endpoints are athlete-scoped. Calling them without a session returned
    // a 401 and printed "Missing bearer token" at the user — a transport detail
    // where a plain instruction belongs.
    if (loading) return
    if (!session) {
      setPlan(null)
      setCampaigns([])
      setError(null)
      return
    }

    void Promise.all([api.myPlan(), api.myCampaigns()])
      .then(([nextPlan, nextCampaigns]) => {
        setPlan(nextPlan)
        setCampaigns(nextCampaigns)
        setError(null)
      })
      .catch((cause: unknown) => {
        // 403 is the expected answer for a wallet that is not an athlete yet, so
        // point at the fix instead of reporting a failure.
        if (cause instanceof ApiError && cause.status === 403) {
          setError(null)
          return
        }
        setError(cause instanceof Error ? cause.message : 'Athlete workspace request failed')
      })
  }, [session, loading])

  const signedOut = !loading && !session
  const planPublished = plan?.status === 'published'

  return (
    <div className="space-y-6">
      <PageHeader
        title="Athlete workspace"
        description="Set up your profile, publish a subscription plan, then create a campaign."
      />

      {signedOut && (
        <p className="text-muted-foreground text-sm">
          Connect your wallet and sign in to manage your athlete profile.
        </p>
      )}

      {error && (
        <p className="text-destructive text-sm" role="alert">
          {error}
        </p>
      )}

      {/* Numbered because the order is a real dependency chain: no campaign
          without a published plan, no plan without a profile. */}
      <ol className="grid gap-4 md:grid-cols-3">
        <li>
          <Step
            index={1}
            title="Athlete profile"
            status={session ? undefined : 'Sign in first'}
            body="Your public name, sport and bio. Campaigns display these."
            action={<StepAction to="/athlete/setup" label="Open setup" disabled={signedOut} />}
          />
        </li>
        <li>
          <Step
            index={2}
            title="Subscription plan"
            status={plan ? `${plan.unit_price_usdc} USDC · ${plan.status}` : 'Not created'}
            body="The monthly price supporters pay. Publish it to lock the price in."
            action={
              <StepAction
                to="/athlete/plan"
                label={plan ? 'Edit plan' : 'Create plan'}
                disabled={signedOut}
              />
            }
          />
        </li>
        <li>
          <Step
            index={3}
            title="Campaign"
            status={planPublished ? 'Ready' : 'Needs a published plan'}
            body="Set a threshold, goals and reward tiers, then publish on-chain."
            action={
              <StepAction
                to="/athlete/campaigns/new"
                label="New campaign"
                disabled={signedOut || !planPublished}
              />
            }
          />
        </li>
      </ol>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Your campaigns</CardTitle>
        </CardHeader>
        <CardContent>
          {campaigns.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              {signedOut
                ? 'Sign in to see your campaigns.'
                : planPublished
                  ? 'No campaigns yet. Create one above.'
                  : 'Publish a subscription plan first, then create a campaign.'}
            </p>
          ) : (
            <ul className="space-y-3">
              {campaigns.map((campaign) => (
                <li
                  key={campaign.id}
                  className="flex flex-wrap items-center justify-between gap-3 border p-3"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium">{campaign.title}</p>
                    <p className="text-muted-foreground text-xs tabular-nums">
                      {campaign.raised_amount_usdc} / {campaign.minimum_success_threshold_usdc} USDC
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge variant="secondary">
                      {campaign.publish_confirmation_status ?? campaign.status}
                    </Badge>
                    <Button asChild size="sm" variant="outline">
                      <Link
                        to={
                          campaign.status === 'draft'
                            ? `/athlete/campaigns/${campaign.id}/edit`
                            : `/athlete/campaigns/${campaign.id}/review`
                        }
                      >
                        {campaign.status === 'draft' ? 'Edit' : 'Review'}
                      </Link>
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

/**
 * A disabled link is not a thing.
 *
 * `<Button asChild disabled>` renders an anchor, and anchors ignore `disabled` —
 * so the control looked enabled and still navigated. When the step is not
 * available we render a real disabled <button> instead of a link, which both
 * looks right and cannot be activated by mouse, keyboard or screen reader.
 */
function StepAction({ to, label, disabled }: { to: string; label: string; disabled: boolean }) {
  if (disabled) {
    return (
      <Button disabled aria-disabled="true">
        {label}
      </Button>
    )
  }
  return (
    <Button asChild>
      <Link to={to}>{label}</Link>
    </Button>
  )
}

function Step({
  index,
  title,
  status,
  body,
  action,
}: {
  index: number
  title: string
  status?: string
  body: string
  action: React.ReactNode
}) {
  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-baseline justify-between gap-3">
          <CardTitle className="text-base">{title}</CardTitle>
          <span className="text-muted-foreground text-xs tabular-nums">
            {String(index).padStart(2, '0')}
          </span>
        </div>
        {status && <p className="text-muted-foreground text-xs">{status}</p>}
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-muted-foreground text-sm">{body}</p>
        {action}
      </CardContent>
    </Card>
  )
}
