"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { zodResolver } from "@hookform/resolvers/zod"
import { format } from "date-fns"
import { Search } from "lucide-react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"

import { DatePickerField } from "@/components/date-picker-field"
import { MatchLoading } from "@/components/match-loading"
import { isAllowedImage, PhotoDropzone } from "@/components/photo-dropzone"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { ApiError, createReport, runMatch } from "@/lib/api"
import { DEMO_CITIES, OTHER_CITY_VALUE } from "@/lib/cities"
import { saveReportSummary } from "@/lib/report-summary"

const reportSchema = z
  .object({
    photos: z
      .array(z.custom<File>((value) => value instanceof File))
      .min(1, "Add at least one photo.")
      .max(5, "Use at most five photos."),
    serial: z.string(),
    brand: z.string(),
    color: z.string(),
    stolenAt: z.date("Theft date is required."),
    city: z.string().min(1, "Location is required."),
    locationOther: z.string(),
    policeReportNr: z.string(),
    notes: z.string(),
  })
  .superRefine((data, ctx) => {
    if (data.photos.some((file) => !isAllowedImage(file))) {
      ctx.addIssue({
        code: "custom",
        path: ["photos"],
        message: "Photos must be JPEG, PNG, or WebP.",
      })
    }
    if (data.city === OTHER_CITY_VALUE && !data.locationOther.trim()) {
      ctx.addIssue({
        code: "custom",
        path: ["locationOther"],
        message: "Type a city or place name.",
      })
    }
  })

type ReportFormValues = z.infer<typeof reportSchema>

function resolveLocation(values: ReportFormValues): string {
  if (values.city === OTHER_CITY_VALUE) return values.locationOther.trim()
  return values.city.trim()
}

export function ReportIntakeForm() {
  const router = useRouter()
  const [flowPhase, setFlowPhase] = React.useState<"idle" | "submitting" | "matching">(
    "idle"
  )
  const form = useForm<ReportFormValues>({
    resolver: zodResolver(reportSchema),
    defaultValues: {
      photos: [],
      serial: "",
      brand: "",
      color: "",
      stolenAt: undefined,
      city: "",
      locationOther: "",
      policeReportNr: "",
      notes: "",
    },
  })

  const city = form.watch("city")
  const submitting = flowPhase !== "idle"

  async function onSubmit(values: ReportFormValues) {
    const location = resolveLocation(values)
    if (!location) {
      form.setError("city", { message: "Location is required." })
      return
    }

    try {
      setFlowPhase("submitting")
      const created = await createReport({
        photos: values.photos,
        stolen_at: format(values.stolenAt, "yyyy-MM-dd"),
        location,
        serial: values.serial.trim() || undefined,
        brand: values.brand.trim() || undefined,
        color: values.color.trim() || undefined,
        police_report_nr: values.policeReportNr.trim() || undefined,
        notes: values.notes.trim() || undefined,
      })

      saveReportSummary({
        reportId: created.report_id,
        brand: values.brand.trim() || undefined,
        color: values.color.trim() || undefined,
        serial: values.serial.trim() || undefined,
        stolenAt: format(values.stolenAt, "yyyy-MM-dd"),
        location,
        policeReportNr: values.policeReportNr.trim() || undefined,
      })

      setFlowPhase("matching")
      await runMatch(created.report_id)
      router.push(`/reports/${created.report_id}`)
    } catch (error) {
      setFlowPhase("idle")
      const message =
        error instanceof ApiError
          ? error.detail
          : "Something went wrong. Please try again."
      toast.error(message)
    }
  }

  return (
    <>
      <div className="vitrine">
        <div className="vitrine-stack" aria-hidden="true">
          <span />
          <span />
        </div>
      <Card className="vitrine-face rounded-2xl py-6 shadow-sm ring-foreground/8">
        <CardHeader className="gap-1.5">
          <CardTitle className="font-heading text-xl font-semibold tracking-tight">
            Report a stolen bike
          </CardTitle>
          <CardDescription className="max-w-prose text-[0.95rem] leading-relaxed">
            Photos and a theft date help the matcher surface listings for
            officers to review. Nothing here accuses a seller.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form
              noValidate
              onSubmit={form.handleSubmit(onSubmit, (errors) => {
                if (errors.photos) toast.error(String(errors.photos.message))
                else if (errors.stolenAt) {
                  toast.error(String(errors.stolenAt.message))
                } else if (errors.city || errors.locationOther) {
                  toast.error("Location is required.")
                }
              })}
              className="grid gap-6"
            >
              <FormField
                control={form.control}
                name="photos"
                render={({ field, fieldState }) => (
                  <FormItem>
                    <FormLabel>Photos</FormLabel>
                    <FormDescription>
                      1–5 photos of the bike. Clear frame and distinguishing
                      marks work best.
                    </FormDescription>
                    <FormControl>
                      <PhotoDropzone
                        files={field.value}
                        onChange={field.onChange}
                        error={fieldState.invalid}
                        disabled={submitting}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid gap-6 md:grid-cols-2">
                <FormField
                  control={form.control}
                  name="serial"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Serial / frame number{" "}
                        <span className="font-normal text-muted-foreground">
                          (strongly encouraged)
                        </span>
                      </FormLabel>
                      <FormControl>
                        <Input
                          className="h-10"
                          autoComplete="off"
                          placeholder="e.g. WMK123456"
                          disabled={submitting}
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>
                        An exact serial match is flagged first for police
                        review.
                      </FormDescription>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="policeReportNr"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Police report number{" "}
                        <span className="font-normal text-muted-foreground">
                          (optional)
                        </span>
                      </FormLabel>
                      <FormControl>
                        <Input
                          className="h-10"
                          autoComplete="off"
                          placeholder="If you already filed a report"
                          disabled={submitting}
                          {...field}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="brand"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Brand{" "}
                        <span className="font-normal text-muted-foreground">
                          (optional)
                        </span>
                      </FormLabel>
                      <FormControl>
                        <Input
                          className="h-10"
                          autoComplete="off"
                          placeholder="Gazelle, Batavus, …"
                          disabled={submitting}
                          {...field}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="color"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Colour{" "}
                        <span className="font-normal text-muted-foreground">
                          (optional)
                        </span>
                      </FormLabel>
                      <FormControl>
                        <Input
                          className="h-10"
                          autoComplete="off"
                          placeholder="Black, blue, …"
                          disabled={submitting}
                          {...field}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="stolenAt"
                  render={({ field, fieldState }) => (
                    <FormItem>
                      <FormLabel>Theft date</FormLabel>
                      <FormControl>
                        <DatePickerField
                          value={field.value}
                          onChange={field.onChange}
                          disabled={submitting}
                          invalid={fieldState.invalid}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="city"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Location</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        value={field.value}
                        disabled={submitting}
                      >
                        <FormControl>
                          <SelectTrigger className="h-10 w-full">
                            <SelectValue placeholder="Select a city" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent position="popper">
                          {DEMO_CITIES.map((name) => (
                            <SelectItem key={name} value={name}>
                              {name}
                            </SelectItem>
                          ))}
                          <SelectItem value={OTHER_CITY_VALUE}>
                            Type a different city
                          </SelectItem>
                        </SelectContent>
                      </Select>
                      <FormDescription>
                        City or area where the bike was stolen.
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {city === OTHER_CITY_VALUE && (
                <FormField
                  control={form.control}
                  name="locationOther"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>City or place name</FormLabel>
                      <FormControl>
                        <Input
                          className="h-10"
                          autoComplete="off"
                          placeholder="e.g. Meerssen"
                          disabled={submitting}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              <FormField
                control={form.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Notes{" "}
                      <span className="font-normal text-muted-foreground">
                        (optional)
                      </span>
                    </FormLabel>
                    <FormControl>
                      <Textarea
                        rows={4}
                        placeholder="Distinctive stickers, accessories, or other details for reviewers."
                        disabled={submitting}
                        {...field}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="max-w-md text-xs leading-relaxed text-muted-foreground">
                  Submitting compares this report with the local listing set.
                  Officers remain the decision-makers.
                </p>
                <Button
                  type="submit"
                  size="lg"
                  className="h-10 min-w-48 rounded-xl px-5"
                  disabled={submitting}
                >
                  <Search data-icon="inline-start" />
                  Find candidate listings
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
      </div>
      <MatchLoading
        open={flowPhase !== "idle"}
        phase={flowPhase === "matching" ? "matching" : "submitting"}
      />
    </>
  )
}
