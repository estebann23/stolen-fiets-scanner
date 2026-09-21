"use client"

import * as React from "react"
import { ImagePlus, X } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const ACCEPT = "image/jpeg,image/jpg,image/png,image/webp"
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/jpg", "image/png", "image/webp"])
const ACCEPTED_EXT = /\.(jpe?g|png|webp)$/i

export function isAllowedImage(file: File): boolean {
  if (ACCEPTED_TYPES.has(file.type)) return true
  if (!file.type && ACCEPTED_EXT.test(file.name)) return true
  return ACCEPTED_EXT.test(file.name)
}

type PhotoDropzoneProps = {
  files: File[]
  onChange: (files: File[]) => void
  error?: boolean
  disabled?: boolean
  id?: string
}

export function PhotoDropzone({
  files,
  onChange,
  error,
  disabled,
  id,
}: PhotoDropzoneProps) {
  const inputRef = React.useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = React.useState(false)
  const previews = React.useMemo(
    () => files.map((file) => ({ file, url: URL.createObjectURL(file) })),
    [files]
  )

  React.useEffect(() => {
    return () => {
      for (const preview of previews) {
        URL.revokeObjectURL(preview.url)
      }
    }
  }, [previews])

  function addFiles(incoming: FileList | File[]) {
    const list = Array.from(incoming)
    const images = list.filter(isAllowedImage)
    const rejected = list.length - images.length
    const room = Math.max(0, 5 - files.length)
    const truncated = images.length > room
    const next = images.slice(0, room)
    if (rejected > 0) {
      toast.error("Photos must be JPEG, PNG, or WebP.")
    }
    if (truncated) {
      toast.error("Use at most five photos.")
    }
    if (next.length) {
      onChange([...files, ...next])
    }
  }

  return (
    <div className="grid gap-3">
      <div
        onDragOver={(event) => {
          event.preventDefault()
          if (!disabled) setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragOver(false)
          if (!disabled && event.dataTransfer.files.length) {
            addFiles(event.dataTransfer.files)
          }
        }}
        className={cn(
          "relative rounded-2xl border-2 border-dashed bg-card/60 px-4 py-8 text-center transition-colors",
          dragOver && "border-primary bg-primary/5",
          error && "border-destructive/60 bg-destructive/5",
          disabled && "pointer-events-none opacity-60"
        )}
      >
        <input
          ref={inputRef}
          id={id}
          type="file"
          accept={ACCEPT}
          multiple
          className="sr-only"
          disabled={disabled}
          onChange={(event) => {
            if (event.target.files) addFiles(event.target.files)
            event.target.value = ""
          }}
        />
        <ImagePlus
          className="mx-auto mb-3 size-8 text-primary/80"
          aria-hidden="true"
        />
        <p className="text-sm font-medium text-foreground">
          Drop 1–5 photos here, or{" "}
          <button
            type="button"
            className="text-primary underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            onClick={() => inputRef.current?.click()}
          >
            browse
          </button>
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          JPEG, PNG, or WebP. {files.length}/5 selected.
        </p>
      </div>

      {files.length > 0 && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
          {previews.map((preview, index) => (
            <li
              key={`${preview.file.name}-${index}`}
              className="group relative overflow-hidden rounded-xl border bg-card shadow-sm"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview.url}
                alt={`Uploaded photo ${index + 1}: ${preview.file.name}`}
                className="aspect-square w-full object-cover"
              />
              <Button
                type="button"
                size="icon-xs"
                variant="secondary"
                disabled={disabled}
                className="absolute top-1.5 right-1.5 shadow-sm"
                aria-label={`Remove ${preview.file.name}`}
                onClick={() =>
                  onChange(files.filter((_, fileIndex) => fileIndex !== index))
                }
              >
                <X />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
