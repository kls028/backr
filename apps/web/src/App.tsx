import { Route, Routes } from 'react-router-dom'
import { Toaster } from '@/components/ui/sonner'
import { SiteHeader } from '@/components/SiteHeader'
import { HomePage } from '@/routes/HomePage'
import { NotFoundPage } from '@/routes/NotFoundPage'
import { CampaignPage } from '@/routes/CampaignPage'
import { PointsPage } from '@/routes/PointsPage'
import { StorePage } from '@/routes/StorePage'
import { AthletePage } from '@/routes/AthletePage'

export default function App() {
  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <main className="mx-auto max-w-5xl px-4 py-10">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/campaigns/:id" element={<CampaignPage />} />
          <Route path="/points" element={<PointsPage />} />
          <Route path="/store" element={<StorePage />} />
          <Route path="/athlete" element={<AthletePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <Toaster richColors position="bottom-right" />
    </div>
  )
}
