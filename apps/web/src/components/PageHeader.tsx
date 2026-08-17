import type { ReactNode } from 'react'

/**
 * One page header for every app surface.
 *
 * Pages had drifted to three different title sizes and weights, which is the
 * kind of inconsistency that reads as unfinished even when nobody can name it.
 * The site header carries the product name, so the h1 here is always the page.
 */
export function PageHeader({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-wide">{title}</h1>
        {description && (
          <p className="text-muted-foreground mt-2 max-w-2xl text-sm leading-relaxed">
            {description}
          </p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  )
}
