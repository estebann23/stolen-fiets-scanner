import { Badge } from "@/components/ui/badge"
import type { Verdict } from "@/lib/api"
import { cn } from "@/lib/utils"

const VERDICT_COPY: Record<
  Verdict,
  { label: string; className: string }
> = {
  likely_same: {
    label: "Likely same",
    className:
      "border-emerald-700/20 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100",
  },
  possibly_same: {
    label: "Possibly same",
    className:
      "border-amber-700/20 bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-100",
  },
  different: {
    label: "Different",
    className:
      "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200",
  },
}

export function VerdictBadge({ verdict }: { verdict: Verdict | null }) {
  if (!verdict) {
    return (
      <Badge variant="outline" className="h-6 rounded-full px-2.5">
        Awaiting verdict
      </Badge>
    )
  }

  const copy = VERDICT_COPY[verdict]
  return (
    <Badge
      variant="outline"
      className={cn("h-6 rounded-full px-2.5", copy.className)}
    >
      {copy.label}
    </Badge>
  )
}
