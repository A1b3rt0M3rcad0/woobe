import { Outlet } from 'react-router-dom'
import { MarketingHeader } from '@/components/marketing/MarketingHeader'
import { Footer } from '@/components/marketing/Footer'

export function PublicLayout() {
  return (
    <div className="min-h-screen bg-background">
      <MarketingHeader />
      <main>
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
