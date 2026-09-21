import { format } from "date-fns"

/** Convert a 0–1 (or 0–100) score to a 0–100 percentage. */
export function scoreToPercent(score: number | null | undefined): number | null {
  if (score === null || score === undefined || Number.isNaN(score)) return null
  const pct = score <= 1 ? score * 100 : score
  return Math.round(Math.min(100, Math.max(0, pct)))
}

export function formatPercent(score: number | null | undefined): string {
  const pct = scoreToPercent(score)
  if (pct === null) return "—"
  return `${pct}%`
}

export function formatDateLabel(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return format(date, "d MMM yyyy")
}
