import { CalendarDays, MapPin, Palette, Tag } from "lucide-react"

import { RemotePhoto } from "@/components/remote-photo"
import { Badge } from "@/components/ui/badge"
import type { ReportSummary } from "@/lib/report-summary"
import { formatDateLabel } from "@/lib/format"

type ReportSummaryStripProps = {
  summary: ReportSummary | null
  photoSrc: string | null
  reportId: string
}

function Meta({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Tag
  label: string
  value?: string
}) {
  if (!value) return null
  return (
    <div className="flex min-w-0 items-start gap-2">
      <Icon className="mt-0.5 size-3.5 shrink-0 text-primary/80" aria-hidden="true" />
      <div className="min-w-0">
        <p className="text-[0.65rem] font-medium tracking-wide text-muted-foreground uppercase">
          {label}
        </p>
        <p className="truncate text-sm font-medium">{value}</p>
      </div>
    </div>
  )
}

export function ReportSummaryStrip({
  summary,
  photoSrc,
  reportId,
}: ReportSummaryStripProps) {
  return (
    <section className="flex flex-col gap-4 rounded-2xl border bg-card p-4 shadow-sm ring-1 ring-foreground/8 sm:flex-row sm:items-center">
      <div className="w-full max-w-[11rem] shrink-0 [perspective:900px]">
        <div className="photo-diptych-panel photo-diptych-panel-left">
          <RemotePhoto
            src={photoSrc}
            alt="Submitted report photo thumbnail"
            label="Submitted photo"
            framed
          />
        </div>
      </div>
      <div className="grid min-w-0 flex-1 gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-heading text-lg font-semibold tracking-tight">
            Report summary
          </h2>
          <Badge variant="outline" className="rounded-full font-mono text-[0.7rem]">
            {reportId}
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <Meta icon={Tag} label="Brand" value={summary?.brand} />
          <Meta icon={Palette} label="Colour" value={summary?.color} />
          <Meta
            icon={Tag}
            label="Serial"
            value={summary?.serial ?? "Not provided"}
          />
          <Meta
            icon={CalendarDays}
            label="Theft date"
            value={summary?.stolenAt ? formatDateLabel(summary.stolenAt) : undefined}
          />
          <Meta icon={MapPin} label="Location" value={summary?.location} />
        </div>
        <p className="text-xs text-muted-foreground">
          Candidates below are for police review. They are not accusations.
        </p>
      </div>
    </section>
  )
}
