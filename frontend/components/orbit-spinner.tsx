import { cn } from "@/lib/utils"

type OrbitSpinnerProps = {
  className?: string
  label?: string
  size?: "sm" | "md"
}

export function OrbitSpinner({
  className,
  label,
  size = "md",
}: OrbitSpinnerProps) {
  return (
    <div
      className={cn("orbit-spinner", className)}
      data-size={size}
      role="img"
      aria-label={label ?? "Working"}
    >
      <span className="orbit-ring orbit-ring-a" />
      <span className="orbit-ring orbit-ring-b" />
      <span className="orbit-ring orbit-ring-c" />
      <span className="orbit-core" />
    </div>
  )
}
