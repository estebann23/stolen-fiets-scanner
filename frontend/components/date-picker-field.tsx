"use client"

import * as React from "react"
import { format } from "date-fns"
import { CalendarIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn } from "@/lib/utils"

type DatePickerFieldProps = {
  value?: Date
  onChange: (date: Date | undefined) => void
  disabled?: boolean
  invalid?: boolean
  id?: string
}

export function DatePickerField({
  value,
  onChange,
  disabled,
  invalid,
  id,
}: DatePickerFieldProps) {
  const [open, setOpen] = React.useState(false)
  const today = new Date()

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          disabled={disabled}
          aria-invalid={invalid}
          className={cn(
            "h-10 w-full justify-start rounded-lg px-3 font-normal",
            !value && "text-muted-foreground"
          )}
        >
          <CalendarIcon data-icon="inline-start" />
          {value ? format(value, "d MMMM yyyy") : "Select theft date"}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-2">
        <Calendar
          mode="single"
          selected={value}
          onSelect={(date) => {
            onChange(date)
            if (date) setOpen(false)
          }}
          disabled={{ after: today }}
          captionLayout="dropdown"
          defaultMonth={value ?? today}
        />
      </PopoverContent>
    </Popover>
  )
}
