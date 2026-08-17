import { Link, useLocation } from 'react-router-dom'
import { WalletAuthButton } from '@/components/WalletAuthButton'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/campaigns', label: 'Campaigns' },
  { to: '/points', label: 'Points' },
  { to: '/store', label: 'Store' },
  { to: '/athlete', label: 'Athlete' },
]

function isActive(pathname: string, to: string) {
  // /athlete has child routes (setup, plan, campaigns/*) that should keep the
  // parent tab marked current.
  return pathname === to || pathname.startsWith(`${to}/`)
}

export function SiteHeader() {
  const { pathname } = useLocation()

  return (
    <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-5xl items-center gap-4 px-4 sm:gap-6">
        {/* Back to the landing page, and the only non-uppercase mark in the app. */}
        <Link
          to="/"
          className="text-base font-bold tracking-widest uppercase focus-visible:outline-none"
        >
          <span className="text-primary">▮</span> Backr
        </Link>

        <nav
          className="-mx-1 flex flex-1 items-center gap-0.5 overflow-x-auto sm:gap-1"
          aria-label="Main"
        >
          {NAV.map((item) => {
            const active = isActive(pathname, item.to)
            return (
              <Link
                key={item.to}
                to={item.to}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  // 40px min height keeps the touch target legal while the row
                  // stays visually compact.
                  'flex min-h-10 shrink-0 items-center px-3 text-xs font-medium tracking-widest uppercase',
                  'transition-colors duration-100 ease-out',
                  active
                    ? 'text-foreground border-primary border-b-2'
                    : 'text-muted-foreground hover:text-foreground border-b-2 border-transparent',
                )}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>

        <WalletAuthButton />
      </div>
    </header>
  )
}
