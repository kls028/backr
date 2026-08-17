import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import '@/styles/landing.css'

/**
 * Landing page.
 *
 * Always dark, deliberately — it does not follow the app theme. Every ambient
 * layer is aria-hidden and motion-gated; a screen reader gets the copy in
 * document order with none of the scenery, and `prefers-reduced-motion` gets a
 * completely still page rather than a faster one.
 */

export function LandingPage() {
  return (
    <div className="landing">
      <Sky />
      <LandingHeader />
      <main>
        <Hero />
        <HowItWorks />
        <MoneyModel />
        <Points />
        <FinalCta />
      </main>
      <LandingFooter />
    </div>
  )
}

/* --------------------------------------------------------------------------- */

function Sky() {
  return (
    <div className="landing-sky" aria-hidden="true">
      <div className="landing-stars landing-stars--far" />
      <div className="landing-stars landing-stars--mid" />
      <div className="landing-stars landing-stars--near" />
      <div className="landing-sweep" />
      <div className="landing-vignette" />
      <div className="landing-scanlines" />
    </div>
  )
}

function LandingHeader() {
  return (
    <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-5 py-6">
      <span className="flex items-center gap-3">
        <TrophySprite size={28} />
        <span className="landing-display text-lg">Backr</span>
      </span>
      <nav className="flex items-center gap-2" aria-label="Primary">
        <Link to="/campaigns" className="landing-btn landing-btn--ghost">
          Campaigns
        </Link>
        <Link to="/athlete" className="landing-btn">
          For athletes
        </Link>
      </nav>
    </header>
  )
}

function Hero() {
  return (
    <section className="relative z-10 mx-auto max-w-6xl px-5 pt-16 pb-24 sm:pt-24">
      <p className="landing-eyebrow">Solana · USDC · escrow-backed</p>

      <h1 className="landing-display mt-6 text-[clamp(2.5rem,9vw,6rem)]">
        {/* data-text feeds the two clipped pseudo-element copies that make the
            glitch. Keep it identical to the visible text. */}
        <span className="landing-glitch" data-text="Back athletes">
          Back athletes
        </span>
        <br />
        <span className="text-[var(--accent)]">block by block</span>
        <span className="landing-cursor ml-2 inline-block align-baseline" aria-hidden="true">
          _
        </span>
      </h1>

      <p className="mt-8 max-w-xl text-base leading-relaxed text-[var(--paper-dim)] sm:text-lg">
        Buy an athlete&apos;s subscription months in USDC. One month starts today. The rest sit in
        an on-chain escrow until the campaign hits its threshold — funded, or refunded.
      </p>

      <div className="mt-10 flex flex-wrap items-center gap-4">
        <Link to="/campaigns" className="landing-btn">
          Browse campaigns
        </Link>
        <Link to="/athlete" className="landing-btn landing-btn--ghost">
          Start a campaign
        </Link>
      </div>

      <dl className="mt-16 grid max-w-2xl grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-4">
        <Stat value="1" label="month starts now" />
        <Stat value="100" label="points per month" />
        <Stat value="12" label="month forward cap" />
        <Stat value="0%" label="platform custody" />
      </dl>
    </section>
  )
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      {/* tabular-nums so a value swap never shifts the label beneath it. */}
      <dt className="landing-display text-3xl tabular-nums">{value}</dt>
      <dd className="mt-2 text-xs leading-snug tracking-wide text-[var(--paper-dim)] uppercase">
        {label}
      </dd>
    </div>
  )
}

/* --------------------------------------------------------------------------- */

const STEPS = [
  {
    sprite: <RunnerSprite />,
    title: 'Pick a campaign',
    body: 'An athlete sets a monthly price, a success threshold and reward tiers. You choose how many months to buy.',
  },
  {
    sprite: <CoinSprite />,
    title: 'Pay in USDC',
    body: 'Your wallet signs a transaction the backend built and simulated. No key ever leaves your browser.',
  },
  {
    sprite: <TrophySprite size={48} />,
    title: 'Settle on-chain',
    body: 'Hit the threshold and pending months activate with your reward tier. Miss it and escrow refunds you automatically.',
  },
]

function HowItWorks() {
  return (
    <Section id="how" eyebrow="How it works" title="Three steps, one signature">
      <ol className="grid gap-5 md:grid-cols-3">
        {STEPS.map((step, index) => (
          <li key={step.title}>
            <Reveal delay={index * 60}>
              <article className="landing-panel landing-card h-full p-6">
                <div className="flex items-start justify-between">
                  <span aria-hidden="true">{step.sprite}</span>
                  <span className="landing-display text-sm text-[var(--paper-dim)] tabular-nums">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                </div>
                <h3 className="landing-display mt-6 text-lg">{step.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-[var(--paper-dim)]">{step.body}</p>
              </article>
            </Reveal>
          </li>
        ))}
      </ol>
    </Section>
  )
}

/* --------------------------------------------------------------------------- */

function MoneyModel() {
  const [units, setUnits] = useState(6)

  return (
    <Section
      id="escrow"
      eyebrow="The money model"
      title="One month now. The rest in escrow."
    >
      <div className="grid gap-8 md:grid-cols-[1fr_auto] md:items-start">
        <div>
          <p className="max-w-xl text-sm leading-relaxed text-[var(--paper-dim)]">
            Buying ten months does not hand an athlete ten months of money. Exactly one month
            activates immediately and is non-refundable. The other nine are held by the program
            until the campaign closes, then released or returned — never held by us.
          </p>

          <label
            htmlFor="landing-units"
            className="landing-eyebrow mt-10 block text-[var(--paper-dim)]"
          >
            Drag to see the split
          </label>
          <input
            id="landing-units"
            type="range"
            min={1}
            max={12}
            value={units}
            onChange={(event) => setUnits(Number(event.target.value))}
            className="mt-4 w-full max-w-sm accent-[var(--accent)]"
          />

          <div className="landing-bar mt-6" aria-hidden="true">
            {Array.from({ length: units }, (_, index) => (
              <span
                key={index}
                className="landing-bar-cell"
                data-kind={index === 0 ? 'immediate' : 'pending'}
              />
            ))}
          </div>

          {/* The bar is decorative; this sentence is the accessible equivalent. */}
          <p className="mt-5 text-sm text-[var(--paper-dim)]">
            <strong className="text-[var(--paper)]">{units}</strong>{' '}
            {units === 1 ? 'month' : 'months'} —{' '}
            <span className="text-[var(--accent)]">1 active today</span>, {units - 1} in escrow,{' '}
            <strong className="text-[var(--paper)] tabular-nums">{units * 100}</strong> points
            pending.
          </p>
        </div>

        <Reveal>
          <div className="landing-panel p-6 md:w-72">
            <p className="landing-eyebrow">If the campaign fails</p>
            <div className="landing-bar mt-5" aria-hidden="true">
              {Array.from({ length: units }, (_, index) => (
                <span
                  key={index}
                  className="landing-bar-cell"
                  data-kind={index === 0 ? 'immediate' : 'refunded'}
                />
              ))}
            </div>
            <p className="mt-5 text-sm leading-relaxed text-[var(--paper-dim)]">
              You keep the active month and its 100 confirmed points. Escrow returns the other{' '}
              <strong className="text-[var(--paper)] tabular-nums">{units - 1}</strong> months to
              your wallet.
            </p>
          </div>
        </Reveal>
      </div>
    </Section>
  )
}

/* --------------------------------------------------------------------------- */

function Points() {
  return (
    <Section id="points" eyebrow="Support Points" title="Earn them. Spend them. Never trade them.">
      <div className="grid gap-5 sm:grid-cols-3">
        <Reveal>
          <div className="landing-panel landing-card h-full p-6">
            <p className="landing-display text-4xl tabular-nums">
              <CountUp to={100} /> <span className="text-base">/ month</span>
            </p>
            <p className="mt-3 text-sm text-[var(--paper-dim)]">
              Confirmed for the active month, pending for the rest until settlement.
            </p>
          </div>
        </Reveal>
        <Reveal delay={60}>
          <div className="landing-panel landing-card h-full p-6">
            <p className="landing-display text-4xl tabular-nums">
              +<CountUp to={20} />%
            </p>
            <p className="mt-3 text-sm text-[var(--paper-dim)]">
              Success bonus on everything you earned in a campaign that funds.
            </p>
          </div>
        </Reveal>
        <Reveal delay={120}>
          <div className="landing-panel landing-card h-full p-6">
            <p className="landing-display text-4xl">Burned</p>
            <p className="mt-3 text-sm text-[var(--paper-dim)]">
              Redeem for cosmetics or athlete rewards. Points are destroyed on spend, never resold.
            </p>
          </div>
        </Reveal>
      </div>
    </Section>
  )
}

function FinalCta() {
  return (
    <section className="relative z-10 mx-auto max-w-6xl px-5 py-28">
      <Reveal>
        <div className="landing-panel p-8 text-center sm:p-14">
          <p className="landing-eyebrow">Ready when you are</p>
          <h2 className="landing-display mx-auto mt-6 max-w-2xl text-[clamp(1.75rem,5vw,3rem)]">
            Fund a season, not a subscription
          </h2>
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <Link to="/campaigns" className="landing-btn">
              Browse campaigns
            </Link>
            <Link to="/athlete" className="landing-btn landing-btn--ghost">
              I&apos;m an athlete
            </Link>
          </div>
        </div>
      </Reveal>
    </section>
  )
}

function LandingFooter() {
  return (
    <footer className="relative z-10 border-t-2 border-[var(--ink-line)]">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-8 text-xs text-[var(--paper-dim)]">
        <span className="flex items-center gap-3">
          <TrophySprite size={16} />
          Backr — athlete crowdfunding on Solana
        </span>
        <Link to="/campaigns" className="landing-link">
          Browse campaigns
        </Link>
      </div>
    </footer>
  )
}

/* --------------------------------------------------------------------------- */

function Section({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string
  eyebrow: string
  title: string
  children: ReactNode
}) {
  return (
    <section id={id} className="relative z-10 mx-auto max-w-6xl px-5 py-20">
      <Reveal>
        <header className="mb-12">
          <p className="landing-eyebrow">{eyebrow}</p>
          <h2 className="landing-display mt-5 max-w-2xl text-[clamp(1.5rem,4vw,2.5rem)]">
            {title}
          </h2>
        </header>
      </Reveal>
      {children}
    </section>
  )
}

/**
 * Reveals children once when scrolled into view, then disconnects.
 *
 * Deliberately one-shot: re-animating on every scroll-back is the classic
 * landing-page annoyance. Under reduced motion the CSS leaves content fully
 * visible, so this becomes a no-op rather than a hidden-content trap.
 */
function Reveal({ children, delay = 0 }: { children: ReactNode; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    const node = ref.current
    if (!node) return

    // Without IntersectionObserver (or with it stubbed in tests) show at once
    // rather than leaving the page blank.
    if (typeof IntersectionObserver === 'undefined') {
      setShown(true)
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setShown(true)
            observer.disconnect()
          }
        }
      },
      { rootMargin: '0px 0px -12% 0px' },
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      className="landing-reveal"
      data-shown={shown}
      style={{ transitionDelay: shown ? `${delay}ms` : undefined }}
    >
      {children}
    </div>
  )
}

/** Counts up in whole steps when first visible. Reduced motion jumps to the end. */
function CountUp({ to }: { to: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const [value, setValue] = useState(0)

  useEffect(() => {
    const node = ref.current
    if (!node) return

    const reduced =
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced || typeof IntersectionObserver === 'undefined') {
      setValue(to)
      return
    }

    let frame = 0
    let raf = 0
    const steps = 24
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return
      observer.disconnect()

      const tick = () => {
        frame += 1
        // Quantised to 24 frames rather than eased per-millisecond: the number
        // ratchets like a scoreboard instead of sliding.
        setValue(Math.round((to * frame) / steps))
        if (frame < steps) raf = requestAnimationFrame(tick)
      }
      raf = requestAnimationFrame(tick)
    })

    observer.observe(node)
    return () => {
      observer.disconnect()
      cancelAnimationFrame(raf)
    }
  }, [to])

  return (
    <span ref={ref} className="tabular-nums">
      {value}
    </span>
  )
}

/* ---------------------------------------------------------------------------
   Sprites — integer viewBoxes with crispEdges, so they scale as pixel art
   instead of blurring. Decorative: the markup marks them aria-hidden.
   --------------------------------------------------------------------------- */

function TrophySprite({ size = 32 }: { size?: number }) {
  return (
    <svg
      className="landing-sprite"
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <path d="M3 2h10v2H3z" fill="#4ff0d2" />
      <path d="M3 4h2v4H3zM11 4h2v4h-2z" fill="#0f7f6c" />
      <path d="M5 4h6v5H5z" fill="#ffffff" />
      <path d="M7 9h2v3H7z" fill="#0f7f6c" />
      <path d="M5 12h6v2H5z" fill="#4ff0d2" />
    </svg>
  )
}

function CoinSprite({ size = 48 }: { size?: number }) {
  return (
    <svg
      className="landing-sprite"
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <path d="M5 2h6v1H5zM3 3h2v1H3zM11 3h2v1h-2z" fill="#4ff0d2" />
      <path d="M2 4h1v8H2zM13 4h1v8h-1z" fill="#4ff0d2" />
      <path d="M3 12h2v1H3zM11 12h2v1h-2zM5 13h6v1H5z" fill="#4ff0d2" />
      <path d="M4 4h8v8H4z" fill="#ffffff" />
      <path d="M7 5h2v6H7z" fill="#0f7f6c" />
      <path d="M6 6h4v1H6zM6 9h4v1H6z" fill="#0f7f6c" />
    </svg>
  )
}

function RunnerSprite({ size = 48 }: { size?: number }) {
  return (
    <svg
      className="landing-sprite"
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <path d="M7 1h3v3H7z" fill="#ffffff" />
      <path d="M6 4h5v4H6z" fill="#4ff0d2" />
      <path d="M3 5h3v1H3zM11 6h3v1h-3z" fill="#ffffff" />
      <path d="M6 8h2v4H6zM9 8h2v3H9z" fill="#ffffff" />
      <path d="M4 12h3v1H4zM10 11h3v1h-3z" fill="#0f7f6c" />
      <path d="M2 14h12v1H2z" fill="#0f7f6c" />
    </svg>
  )
}
