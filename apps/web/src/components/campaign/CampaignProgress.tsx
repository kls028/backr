import { cn } from '@/lib/utils'

/**
 * Funding progress against the success threshold (spec §39-40).
 *
 * The threshold is the number that matters — below it everyone gets refunded —
 * so the bar is scaled to it and the main goal is shown as a marker beyond it
 * rather than as the denominator. Scaling to the main goal instead would make a
 * fully-funded campaign look half-finished.
 */
export function CampaignProgress({
  raisedAtomic,
  thresholdAtomic,
  raisedUsdc,
  thresholdUsdc,
  className,
}: {
  raisedAtomic: number
  thresholdAtomic: number
  raisedUsdc: string
  thresholdUsdc: string
  className?: string
}) {
  const ratio = thresholdAtomic > 0 ? raisedAtomic / thresholdAtomic : 0
  const percent = Math.round(ratio * 100)
  const funded = raisedAtomic >= thresholdAtomic

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="tabular-nums">
          <span className={funded ? 'text-primary font-semibold' : 'font-semibold'}>
            {raisedUsdc}
          </span>
          <span className="text-muted-foreground"> / {thresholdUsdc} USDC</span>
        </span>
        <span
          className={cn('text-xs tabular-nums', funded ? 'text-primary' : 'text-muted-foreground')}
        >
          {funded ? 'Threshold met' : `${percent}%`}
        </span>
      </div>

      {/* Squared-off bar with a stepped fill, echoing the landing page's grid
          without any of its motion. */}
      <div
        className="bg-secondary h-2 w-full overflow-hidden"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Funding progress: ${raisedUsdc} of ${thresholdUsdc} USDC`}
      >
        <div
          className={cn('h-full', funded ? 'bg-primary' : 'bg-foreground')}
          // Width is inline because it is data, not a design decision, and
          // Tailwind cannot express an arbitrary runtime percentage.
          style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
        />
      </div>
    </div>
  )
}
