"use client"

import * as React from "react"

import { usePrefersReducedMotion } from "@/hooks/use-prefers-reduced-motion"

const BIKE_LAYERS = [0, 1, 2, 3, 4, 5, 6, 7] as const

function BikeGlyph() {
  return (
    <svg
      viewBox="0 0 240 140"
      className="hero-bike-glyph"
      fill="none"
      aria-hidden="true"
    >
      <g
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="50" cy="102" r="26" fill="currentColor" opacity="0.08" stroke="none" />
        <circle cx="188" cy="102" r="26" fill="currentColor" opacity="0.08" stroke="none" />
        <circle cx="50" cy="102" r="26" strokeWidth="4.2" />
        <circle cx="50" cy="102" r="20.5" strokeWidth="1" opacity="0.45" />
        <circle cx="188" cy="102" r="26" strokeWidth="4.2" />
        <circle cx="188" cy="102" r="20.5" strokeWidth="1" opacity="0.45" />
        <g strokeWidth="0.55" opacity="0.42">
          <path d="M50 102 L50 76 M50 102 L76 102 M50 102 L50 128 M50 102 L24 102" />
          <path d="M50 102 L68.4 83.6 M50 102 L31.6 120.4 M50 102 L68.4 120.4 M50 102 L31.6 83.6" />
          <path d="M188 102 L188 76 M188 102 L214 102 M188 102 L188 128 M188 102 L162 102" />
          <path d="M188 102 L206.4 83.6 M188 102 L169.6 120.4 M188 102 L206.4 120.4 M188 102 L169.6 83.6" />
        </g>
        <circle cx="50" cy="102" r="5" fill="currentColor" stroke="none" />
        <circle cx="188" cy="102" r="5" fill="currentColor" stroke="none" />
        <circle cx="98" cy="102" r="8" strokeWidth="2.6" />
        <path d="M50 102 H98" strokeWidth="3.4" />
        <path d="M50 102 L116 48" strokeWidth="3.1" />
        <path d="M98 102 L116 48" strokeWidth="3.5" />
        <path d="M98 102 C122 86 142 68 160 52" strokeWidth="3.3" />
        <path d="M160 52 L188 102" strokeWidth="3.3" />
        <path d="M42 76 H80" strokeWidth="2.8" />
        <path d="M42 76 L50 102 M80 76 L72 100" strokeWidth="2" />
        <path d="M42 76 V70 H80 V76" strokeWidth="2.2" />
        <path d="M104 46 L130 44" strokeWidth="4.2" />
        <path d="M160 52 V29" strokeWidth="3" />
        <path d="M160 29 C168 20 182 20 188 28" strokeWidth="3.2" />
        <path d="M98 102 L86 118" strokeWidth="2.4" />
        <path d="M86 118 H78" strokeWidth="2.6" />
      </g>
    </svg>
  )
}

function GlassCard({
  kicker,
  title,
  className,
}: {
  kicker: string
  title: string
  className: string
}) {
  return (
    <div className={`hero-glass ${className}`}>
      <p className="hero-glass-kicker">{kicker}</p>
      <p className="hero-glass-title">{title}</p>
    </div>
  )
}

export function HeroScene() {
  const reduced = usePrefersReducedMotion()
  const stageRef = React.useRef<HTMLDivElement>(null)
  const [visible, setVisible] = React.useState(true)
  const [pointer, setPointer] = React.useState({ x: 0, y: 0 })

  React.useEffect(() => {
    const node = stageRef.current
    if (!node) return
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.12 }
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  React.useEffect(() => {
    if (reduced) return
    let frame = 0
    const onMove = (event: PointerEvent) => {
      if (!visible) return
      if (event.pointerType === "touch") return
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const width = window.innerWidth || 1
        const height = window.innerHeight || 1
        setPointer({
          x: (event.clientX / width) * 2 - 1,
          y: (event.clientY / height) * 2 - 1,
        })
      })
    }
    window.addEventListener("pointermove", onMove, { passive: true })
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener("pointermove", onMove)
    }
  }, [reduced, visible])

  const tilt = reduced
    ? undefined
    : ({
        "--hero-px": pointer.x.toFixed(3),
        "--hero-py": pointer.y.toFixed(3),
      } as React.CSSProperties)

  return (
    <div
      ref={stageRef}
      className="hero-stage"
      aria-hidden="true"
      data-reduced={reduced ? "true" : "false"}
      data-paused={visible ? "false" : "true"}
      style={tilt}
    >
      <div className="hero-rig">
        <div className="hero-plate" />
        <div className="hero-shadow" />
        <div className="hero-bike">
          {BIKE_LAYERS.map((layer) => (
            <div
              key={layer}
              className={
                layer === BIKE_LAYERS.length - 1
                  ? "hero-bike-layer hero-bike-layer-front"
                  : "hero-bike-layer"
              }
              style={{ transform: `translateZ(${layer * 3.25}px)` }}
            >
              <BikeGlyph />
            </div>
          ))}
        </div>
        <GlassCard
          className="hero-glass-report"
          kicker="Report"
          title="Filed for review"
        />
        <GlassCard
          className="hero-glass-listing"
          kicker="Listing"
          title="Limburg marketplaces"
        />
        <GlassCard
          className="hero-glass-review"
          kicker="Candidate"
          title="Officer review"
        />
      </div>
      <p className="hero-caption">Limburg listing set · for police review</p>
    </div>
  )
}
