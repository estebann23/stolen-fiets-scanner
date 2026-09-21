import { RemotePhoto } from "@/components/remote-photo"
import { cn } from "@/lib/utils"

type PhotoDiptychProps = {
  reportSrc: string | null
  listingSrc: string | null
  listingId: string
  className?: string
}

export function PhotoDiptych({
  reportSrc,
  listingSrc,
  listingId,
  className,
}: PhotoDiptychProps) {
  return (
    <div className={cn("photo-diptych", className)}>
      <div className="photo-diptych-panel photo-diptych-panel-left">
        <RemotePhoto
          src={reportSrc}
          alt={`Submitted report photo compared with listing ${listingId}`}
          label="Report photo"
          framed
        />
      </div>
      <div className="photo-diptych-panel photo-diptych-panel-right">
        <RemotePhoto
          src={listingSrc}
          alt={`Listing ${listingId} photo shown as a possible match candidate`}
          label="Listing photo"
          framed
        />
      </div>
    </div>
  )
}
