"use client"

import * as React from "react"

import { usePrefersReducedMotion } from "@/hooks/use-prefers-reduced-motion"
import { cn } from "@/lib/utils"

type TiltSurfaceProps = {
  children: React.ReactNode
  className?: string
  intensity?: number
  glare?: boolean
}

export function TiltSurface({
  children,
  className,
  intensity = 7,
  glare = true,
}: TiltSurfaceProps) {
  const reduced = usePrefersReducedMotion()
  const ref = React.useRef<HTMLDivElement>(null)

  const reset = React.useCallback(() => {
    const node = ref.current
    if (!node) return
    node.style.setProperty("--tilt-x", "0deg")
    node.style.setProperty("--tilt-y", "0deg")
    node.style.setProperty("--glare-x", "50%")
    node.style.setProperty("--glare-y", "0%")
    node.dataset.tilting = "false"
  }, [])

  function onPointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (reduced) return
    if (event.pointerType === "touch") return
    const node = ref.current
    if (!node) return
    const rect = node.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return
    const x = (event.clientX - rect.left) / rect.width
    const y = (event.clientY - rect.top) / rect.height
    const rotateX = (0.5 - y) * intensity
    const rotateY = (x - 0.5) * intensity
    node.style.setProperty("--tilt-x", `${rotateX.toFixed(2)}deg`)
    node.style.setProperty("--tilt-y", `${rotateY.toFixed(2)}deg`)
    node.style.setProperty("--glare-x", `${(x * 100).toFixed(1)}%`)
    node.style.setProperty("--glare-y", `${(y * 100).toFixed(1)}%`)
    node.dataset.tilting = "true"
  }

  return (
    <div
      ref={ref}
      className={cn("tilt-surface", className)}
      onPointerMove={onPointerMove}
      onPointerLeave={reset}
      onPointerCancel={reset}
      onBlur={reset}
    >
      {children}
      {glare ? <span className="tilt-glare" aria-hidden="true" /> : null}
    </div>
  )
}
