import { Link, useLocation } from 'react-router-dom'
import { WalletAuthButton } from '@/components/WalletAuthButton'
import { cn } from '@/lib/utils'

const NAV = [{ to: '/', label: 'Home' }]

export function SiteHeader() {
  const { pathname } = useLocation()

  return (
    <header className="border-b">
      <div className="mx-auto flex h-16 max-w-5xl items-center gap-6 px-4">
        <Link
          to="/"
          className="rounded-md font-semibold tracking-tight focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          sss-project
        </Link>

        <nav className="flex items-center gap-1" aria-label="Main">
          {NAV.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              aria-current={pathname === item.to ? 'page' : undefined}
              className={cn(
                'rounded-md px-3 py-1.5 text-sm transition-colors',
                'focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                pathname === item.to
                  ? 'bg-secondary text-secondary-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto">
          <WalletAuthButton />
        </div>
      </div>
    </header>
  )
}
