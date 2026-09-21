import { Fingerprint } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

export function SerialMatchBanner() {
  return (
    <Alert className="rounded-2xl border-emerald-700/20 bg-emerald-50/80 px-5 py-4 text-emerald-950 shadow-sm dark:bg-emerald-950/30 dark:text-emerald-50">
      <Fingerprint className="text-emerald-800 dark:text-emerald-200" />
      <AlertTitle className="font-heading text-base font-semibold">
        Exact serial match
      </AlertTitle>
      <AlertDescription className="text-[0.925rem] leading-relaxed">
        A listing shares this serial or frame number. It is pinned first as a{" "}
        <strong className="font-medium">candidate for police review</strong> —
        not a determination that the seller stole the bike.
      </AlertDescription>
    </Alert>
  )
}
