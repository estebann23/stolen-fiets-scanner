"use client"

import { OrbitSpinner } from "@/components/orbit-spinner"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

type MatchLoadingProps = {
  open: boolean
  phase: "submitting" | "matching"
}

export function MatchLoading({ open, phase }: MatchLoadingProps) {
  const matching = phase === "matching"

  return (
    <Dialog open={open}>
      <DialogContent
        showCloseButton={false}
        onPointerDownOutside={(event) => event.preventDefault()}
        onEscapeKeyDown={(event) => event.preventDefault()}
        className="sm:max-w-md"
        aria-describedby="match-loading-desc"
      >
        <DialogHeader className="items-center sm:text-center">
          <OrbitSpinner
            className="mx-auto"
            label={matching ? "Comparing against listings" : "Saving your report"}
          />
          <DialogTitle className="pt-1">
            {matching ? "Comparing against listings…" : "Saving your report…"}
          </DialogTitle>
          <DialogDescription id="match-loading-desc">
            {matching
              ? "The review service is ranking possible matches. This may take a moment."
              : "Uploading photos and creating a report for police review."}
          </DialogDescription>
        </DialogHeader>
        <p className="text-center text-xs text-muted-foreground">
          Results are candidates for police review — not accusations.
        </p>
      </DialogContent>
    </Dialog>
  )
}
