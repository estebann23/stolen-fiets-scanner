import Link from "next/link"

import { HeaderMark } from "@/components/header-mark"
import { Badge } from "@/components/ui/badge"

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/80 bg-background/75 backdrop-blur-md">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2.5 rounded-lg outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <HeaderMark />
          <span className="font-heading text-[0.95rem] font-semibold tracking-tight text-foreground">
            Stolen Bike Matcher
          </span>
        </Link>
        <Badge
          variant="outline"
          className="h-auto max-w-[60%] rounded-full border-primary/20 bg-primary/5 px-2.5 py-1 text-[0.7rem] font-medium leading-tight text-primary sm:max-w-none sm:text-xs"
        >
          prototype — for police review
        </Badge>
      </div>
    </header>
  )
}
