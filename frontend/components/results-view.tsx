"use client"

import * as React from "react"
import Link from "next/link"
import { ArrowLeft, Inbox } from "lucide-react"
import { toast } from "sonner"

import { CandidateCard } from "@/components/candidate-card"
import { NextStepsBox } from "@/components/next-steps"
import { OrbitSpinner } from "@/components/orbit-spinner"
import { ReportSummaryStrip } from "@/components/report-summary-strip"
import { SerialMatchBanner } from "@/components/serial-match-banner"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ApiError,
  getMatches,
  imgUrl,
  type Candidate,
  type MatchResponse,
} from "@/lib/api"
import { loadReportSummary } from "@/lib/report-summary"

/** The risk signal is the deciding factor; listings without one rank last. */
function orderCandidates(candidates: Candidate[]): Candidate[] {
  return [...candidates]
    .sort((a, b) => {
      const left = a.suspicion_score ?? -1
      const right = b.suspicion_score ?? -1
      if (left !== right) return right - left
      return a.listing_id.localeCompare(b.listing_id)
    })
    .slice(0, 5)
}

export function ResultsView({ reportId }: { reportId: string }) {
  const [data, setData] = React.useState<MatchResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)
  const summary = React.useMemo(() => loadReportSummary(reportId), [reportId])

  React.useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    getMatches(reportId)
      .then((response) => {
        if (!cancelled) setData(response)
      })
      .catch((caught) => {
        if (cancelled) return
        const message =
          caught instanceof ApiError
            ? caught.detail
            : "Could not load candidates for this report."
        setError(message)
        toast.error(message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [reportId])

  const candidates = data ? orderCandidates(data.candidates) : []
  const hasSerialMatch = candidates.some((candidate) => candidate.serial_match)
  const photoSrc = imgUrl(candidates[0]?.report_image ?? null)

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6 lg:py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="ghost" className="-ml-2 rounded-xl">
          <Link href="/">
            <ArrowLeft data-icon="inline-start" />
            New report
          </Link>
        </Button>
        <p className="text-sm text-muted-foreground">
          Cached results for this report
        </p>
      </div>

      {loading ? (
        <div className="grid gap-6" aria-busy="true" aria-live="polite">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <OrbitSpinner
              size="sm"
              label="Loading candidates for police review"
            />
            Loading candidates for police review…
          </div>
          <Skeleton className="h-40 rounded-2xl" />
          <Skeleton className="h-72 rounded-2xl" />
        </div>
      ) : error ? (
        <Alert className="rounded-2xl">
          <AlertTitle>Could not load results</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : (
        <>
          <ReportSummaryStrip
            summary={summary}
            photoSrc={photoSrc}
            reportId={reportId}
          />

          {hasSerialMatch ? <SerialMatchBanner /> : null}

          {candidates.length === 0 ? (
            <div className="plaque flex flex-col items-center gap-3 rounded-2xl border bg-card px-6 py-16 text-center">
              <Inbox className="size-8 text-primary/70" aria-hidden="true" />
              <h2 className="font-heading text-lg font-semibold">
                No strong candidates yet
              </h2>
              <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
                Nothing in the current listing set rose to a reviewable match.
                You can file a new report with extra photos or a serial number.
              </p>
              <Button asChild className="mt-2 rounded-xl">
                <Link href="/">Submit another report</Link>
              </Button>
            </div>
          ) : (
            <ol className="grid gap-6">
              {candidates.map((candidate, index) => (
                <li key={candidate.listing_id}>
                  <CandidateCard candidate={candidate} rank={index + 1} />
                </li>
              ))}
            </ol>
          )}
        </>
      )}

      <NextStepsBox />
    </div>
  )
}
