import { ExternalLink } from "lucide-react"

import { PhotoDiptych } from "@/components/photo-diptych"
import { SuspicionSignal } from "@/components/suspicion-signal"
import { TiltSurface } from "@/components/tilt-surface"
import { VerdictBadge } from "@/components/verdict-badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import type { Candidate } from "@/lib/api"
import { imgUrl } from "@/lib/api"
import { formatPercent, scoreToPercent } from "@/lib/format"

type CandidateCardProps = {
  candidate: Candidate
  rank: number
}

export function CandidateCard({ candidate, rank }: CandidateCardProps) {
  const matchPercent = scoreToPercent(candidate.score) ?? 0
  const reportSrc = imgUrl(candidate.report_image)
  const listingSrc = imgUrl(candidate.listing_image)

  return (
    <TiltSurface className="rounded-2xl">
      <Card className="overflow-visible rounded-2xl py-0 shadow-sm ring-foreground/8">
      <CardHeader className="flex flex-row items-start justify-between gap-4 pt-5 pb-0">
        <div className="grid gap-1">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Candidate {rank} for police review
          </p>
          <CardTitle className="font-heading text-lg font-semibold tracking-tight">
            Listing {candidate.listing_id}
          </CardTitle>
        </div>
        <VerdictBadge verdict={candidate.verdict} />
      </CardHeader>
      <CardContent className="grid gap-5 pt-4 pb-5">
        <PhotoDiptych
          reportSrc={reportSrc}
          listingSrc={listingSrc}
          listingId={candidate.listing_id}
        />

        <div className="grid gap-2">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm font-medium">Match score</span>
            <span className="font-heading text-sm font-semibold tabular-nums text-primary">
              {formatPercent(candidate.score)}
            </span>
          </div>
          <Progress
            value={matchPercent}
            className="h-2 bg-primary/10"
            aria-label="Match score"
          />
          <p className="text-xs text-muted-foreground">
            Visual and attribute agreement only. Not a finding of theft.
          </p>
        </div>

        {candidate.reasons.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-medium">Why this is a candidate</p>
            <ul className="grid list-disc gap-1.5 pl-5 text-sm leading-relaxed text-muted-foreground">
              {candidate.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
        )}

        <Separator />
        <SuspicionSignal score={candidate.suspicion_score} />
      </CardContent>
      {candidate.url ? (
        <CardFooter className="justify-end">
          <Button asChild variant="outline" className="rounded-xl">
            <a href={candidate.url} target="_blank" rel="noopener noreferrer">
              View listing
              <ExternalLink data-icon="inline-end" />
            </a>
          </Button>
        </CardFooter>
      ) : null}
      </Card>
    </TiltSurface>
  )
}
