import { CheckCircle2, FilePlus2, Hand, ScanBarcode } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

export function NextStepsBox() {
  return (
    <Alert className="plaque rounded-2xl border-primary/15 bg-primary/[0.035] px-5 py-4">
      <FilePlus2 className="text-primary" />
      <AlertTitle className="font-heading text-base font-semibold text-foreground">
        Next steps for police review
      </AlertTitle>
      <AlertDescription className="mt-2 text-[0.925rem] leading-relaxed text-foreground/80">
        <ul className="grid gap-2.5">
          <li className="flex gap-2.5">
            <FilePlus2 className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
            <span>Add this listing to your police report.</span>
          </li>
          <li className="flex gap-2.5">
            <ScanBarcode className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
            <span>
              Check the serial via the police{" "}
              <a
                href="https://www.stopheling.nl"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-primary underline-offset-4 hover:underline"
              >
                Stop Heling
              </a>{" "}
              service.
            </span>
          </li>
          <li className="flex gap-2.5">
            <Hand className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
            <span>
              <strong className="font-semibold text-foreground">
                Do not confront the seller.
              </strong>{" "}
              These are candidates for officers to review — not a finding of
              guilt.
            </span>
          </li>
        </ul>
        <p className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
          <CheckCircle2 className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          Keep contact with the marketplace listing through official channels
          only.
        </p>
      </AlertDescription>
    </Alert>
  )
}
