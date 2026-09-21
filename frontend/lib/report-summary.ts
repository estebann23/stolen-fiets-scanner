export type ReportSummary = {
  reportId: string
  brand?: string
  color?: string
  serial?: string
  stolenAt: string
  location: string
  policeReportNr?: string
}

const storageKey = (reportId: string) => `sfs:report:${reportId}`

export function saveReportSummary(summary: ReportSummary) {
  if (typeof window === "undefined") return
  sessionStorage.setItem(storageKey(summary.reportId), JSON.stringify(summary))
}

export function loadReportSummary(reportId: string): ReportSummary | null {
  if (typeof window === "undefined") return null
  try {
    const raw = sessionStorage.getItem(storageKey(reportId))
    if (!raw) return null
    return JSON.parse(raw) as ReportSummary
  } catch {
    return null
  }
}
