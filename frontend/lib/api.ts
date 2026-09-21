export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "")

export type Verdict = "likely_same" | "possibly_same" | "different"

export type Candidate = {
  listing_id: string
  url: string | null
  score: number
  serial_match: boolean
  verdict: Verdict | null
  reasons: string[]
  suspicion_score: number | null
  listing_image: string | null
  report_image: string | null
}

export type MatchResponse = {
  report_id: string
  candidates: Candidate[]
}

export type ReportCreated = {
  report_id: string
}

export type ReportPayload = {
  photos: File[]
  stolen_at: string
  location?: string
  stolen_lat?: number
  stolen_lon?: number
  serial?: string
  brand?: string
  color?: string
  police_report_nr?: string
  notes?: string
}

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = "ApiError"
    this.status = status
    this.detail = detail
  }
}

/** Turn a backend image path (`data/images/…`) into a browser URL. */
export function imgUrl(path: string | null | undefined): string | null {
  if (!path) return null
  const trimmed = path.trim()
  if (!trimmed) return null
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  const cleaned = trimmed.replace(/^\/+/, "")
  return `${API_URL}/${cleaned}`
}

function parseDetail(body: unknown, status: number): string {
  if (status === 501) {
    return "This step is not available yet on the review service (HTTP 501)."
  }
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === "string" && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (typeof item === "string") return item
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg)
          }
          return null
        })
        .filter((msg): msg is string => Boolean(msg))
      if (messages.length) return messages.join(" ")
    }
  }
  if (status === 422) {
    return "Some fields could not be accepted. Check photos, date, and location."
  }
  return `The review service returned an error (HTTP ${status}).`
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, init)
  } catch {
    throw new ApiError(
      0,
      "Cannot reach the review service. Is the API running on the configured URL?"
    )
  }

  let body: unknown = null
  const contentType = response.headers.get("content-type") ?? ""
  if (contentType.includes("application/json")) {
    try {
      body = await response.json()
    } catch {
      body = null
    }
  } else {
    try {
      const text = await response.text()
      body = text ? { detail: text } : null
    } catch {
      body = null
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, parseDetail(body, response.status))
  }

  return body as T
}

function appendOptional(
  form: FormData,
  key: string,
  value: string | number | undefined
) {
  if (value === undefined) return
  if (typeof value === "string" && !value.trim()) return
  form.append(key, String(value))
}

export async function createReport(payload: ReportPayload): Promise<ReportCreated> {
  const form = new FormData()
  for (const photo of payload.photos) {
    form.append("photos", photo)
  }
  form.append("stolen_at", payload.stolen_at)
  appendOptional(form, "location", payload.location)
  appendOptional(form, "stolen_lat", payload.stolen_lat)
  appendOptional(form, "stolen_lon", payload.stolen_lon)
  appendOptional(form, "serial", payload.serial)
  appendOptional(form, "brand", payload.brand)
  appendOptional(form, "color", payload.color)
  appendOptional(form, "police_report_nr", payload.police_report_nr)
  appendOptional(form, "notes", payload.notes)

  return apiFetch<ReportCreated>("/reports", {
    method: "POST",
    body: form,
  })
}

export async function runMatch(reportId: string): Promise<MatchResponse> {
  return apiFetch<MatchResponse>(
    `/reports/${encodeURIComponent(reportId)}/match`,
    { method: "POST" }
  )
}

export async function getMatches(reportId: string): Promise<MatchResponse> {
  return apiFetch<MatchResponse>(
    `/reports/${encodeURIComponent(reportId)}/matches`
  )
}

export async function getHealth(): Promise<{ status: string; listings: number }> {
  return apiFetch("/health")
}
