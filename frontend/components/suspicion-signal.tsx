import { Separator } from "@/components/ui/separator"
import { formatPercent, scoreToPercent } from "@/lib/format"
import { cn } from "@/lib/utils"

type SuspicionSignalProps = {
  score: number | null
}

export function SuspicionSignal({ score }: SuspicionSignalProps) {
  const percent = scoreToPercent(score)

  return (
    <section
      className="rounded-xl border border-amber-800/25 bg-amber-50/70 p-4 dark:border-amber-500/25 dark:bg-amber-950/20"
      aria-label="Independent risk signal"
    >
      <p className="text-[0.7rem] font-semibold tracking-wider text-amber-900/80 uppercase dark:text-amber-200/80">
        Independent risk signal
      </p>
      <p className="mt-1 text-xs leading-relaxed text-amber-950/75 dark:text-amber-100/70">
        Derived from the asking price, listing wording, and seller activity. It
        does not indicate that this is the reported bike.
      </p>
      <Separator className="my-3 bg-amber-800/15 dark:bg-amber-200/15" />
      {percent === null ? (
        <p className="text-sm text-amber-950/80 dark:text-amber-50/80">
          No risk signal available for this listing.
        </p>
      ) : (
        <div className="grid gap-2">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm font-medium text-amber-950 dark:text-amber-50">
              Signal strength
            </span>
            <span className="font-heading text-lg font-semibold tabular-nums text-amber-950 dark:text-amber-50">
              {formatPercent(score)}
            </span>
          </div>
          <div
            className="h-1.5 overflow-hidden rounded-full bg-amber-200/80 dark:bg-amber-900/60"
            role="meter"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            aria-label="Independent risk signal"
          >
            <div
              className={cn(
                "h-full rounded-full bg-amber-700/80 dark:bg-amber-400/80 transition-[width] duration-500"
              )}
              style={{ width: `${percent}%` }}
            />
          </div>
        </div>
      )}
    </section>
  )
}
