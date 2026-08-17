import { Outlet, Route, Routes } from 'react-router-dom'
import { Toaster } from '@/components/ui/sonner'
import { SiteHeader } from '@/components/SiteHeader'
import { LandingPage } from '@/routes/LandingPage'
import { HomePage } from '@/routes/HomePage'
import { NotFoundPage } from '@/routes/NotFoundPage'
import { CampaignPage } from '@/routes/CampaignPage'
import { PointsPage } from '@/routes/PointsPage'
import { StorePage } from '@/routes/StorePage'
import { AthletePage } from '@/routes/AthletePage'
import { AthleteSetupPage } from '@/routes/AthleteSetupPage'
import { SubscriptionPlanPage } from '@/routes/SubscriptionPlanPage'
import { CampaignEditorPage } from '@/routes/CampaignEditorPage'
import { CampaignReviewPage } from '@/routes/CampaignReviewPage'

/**
 * The landing page owns its full viewport — it is always dark, brings its own
 * header and footer, and must not sit inside the app's light chrome or its
 * max-width container. Every other route keeps the shared shell.
 */
export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route element={<AppShell />}>
          <Route path="/campaigns" element={<HomePage />} />
          <Route path="/campaigns/:id" element={<CampaignPage />} />
          <Route path="/points" element={<PointsPage />} />
          <Route path="/store" element={<StorePage />} />
          <Route path="/athlete" element={<AthletePage />} />
          <Route path="/athlete/setup" element={<AthleteSetupPage />} />
          <Route path="/athlete/plan" element={<SubscriptionPlanPage />} />
          <Route path="/athlete/campaigns/new" element={<CampaignEditorPage />} />
          <Route path="/athlete/campaigns/:id" element={<CampaignReviewPage />} />
          <Route path="/athlete/campaigns/:id/edit" element={<CampaignEditorPage />} />
          <Route path="/athlete/campaigns/:id/review" element={<CampaignReviewPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
      <Toaster richColors position="bottom-right" />
    </>
  )
}

function AppShell() {
  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <main className="mx-auto max-w-5xl px-4 py-10">
        <Outlet />
      </main>
    </div>
  )
}
