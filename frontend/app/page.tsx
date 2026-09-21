import { HeroScene } from "@/components/hero-scene"
import { ReportIntakeForm } from "@/components/report-intake-form"

export default function HomePage() {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-10 sm:px-6 lg:py-14">
      <section className="grid items-center gap-8 lg:grid-cols-[minmax(0,1.05fr)_minmax(260px,0.95fr)] lg:gap-4">
        <div className="max-w-2xl">
          <p className="mb-3 text-xs font-semibold tracking-[0.16em] text-primary uppercase">
            Civic review tool
          </p>
          <h1 className="font-heading text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
            Stolen Bike Matcher
          </h1>
          <p className="mt-4 max-w-prose text-lg leading-relaxed text-muted-foreground">
            Compare a stolen-bike report with second-hand listings and surface
            candidates for officers to review.
          </p>
          <p className="mt-3 max-w-prose text-sm leading-relaxed text-foreground/80">
            Results are candidates for police review — not accusations.
          </p>
        </div>
        <HeroScene />
      </section>
      <ReportIntakeForm />
    </div>
  )
}
