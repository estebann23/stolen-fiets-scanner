import { ResultsView } from "@/components/results-view"

export default async function ReportResultsPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  return <ResultsView reportId={id} />
}
