import { ImageOff } from "lucide-react"

import { cn } from "@/lib/utils"

type RemotePhotoProps = {
  src: string | null
  alt: string
  label: string
  className?: string
  framed?: boolean
}

export function RemotePhoto({
  src,
  alt,
  label,
  className,
  framed = false,
}: RemotePhotoProps) {
  return (
    <figure className={cn("flex min-w-0 flex-1 flex-col gap-2", className)}>
      <div
        className={cn(
          "relative aspect-[4/3] overflow-hidden rounded-xl bg-muted ring-1 ring-foreground/10",
          framed && "photo-frame"
        )}
      >
        {src ? (
          // FastAPI-hosted files; skip the Next optimizer so localhost /data works.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={alt}
            className="size-full object-cover"
          />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-2 text-muted-foreground">
            <ImageOff className="size-6" aria-hidden="true" />
            <span className="text-xs">No photo available</span>
          </div>
        )}
      </div>
      <figcaption className="text-center text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {label}
      </figcaption>
    </figure>
  )
}
