import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Play, CheckCircle2, Zap, Loader2, XCircle, AlertTriangle, Download, Eye, Trash2, Clock, Timer } from 'lucide-react'
import { 
  getPendingBatches, 
  getRuns, 
  generateGroupBatch, 
  retryFailedRun, 
  getRunResults, 
  fetchPdfBlobUrl, 
  deleteRun, 
  deleteAllRuns,
  type BillingRunOut 
} from '../../lib/api'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { cn, formatCycleDisplayName } from '@/lib/utils'
import { Progress } from '@/components/ui/progress'
import { useState } from 'react'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"

function formatRunTitle(batchName: string): { title: string; subtitle?: string } {
  if (!batchName) return { title: 'Batch Run' }
  if (batchName.startsWith('Auto Gen ')) {
    const parts = batchName.replace('Auto Gen ', '').split(' ')
    const fileName = parts[0]
    const timeStr = parts.slice(1).join(' ')
    return {
      title: `Auto: ${fileName.replace(/_/g, ' ')}`,
      subtitle: timeStr ? `Generated at ${timeStr}` : undefined
    }
  }
  if (batchName.startsWith('Batch ')) {
    return {
      title: 'Manual Batch Run',
      subtitle: batchName.replace('Batch ', '')
    }
  }
  return { title: batchName }
}

function formatDateTime(isoStr?: string | null): string {
  if (!isoStr) return 'N/A'
  try {
    const d = new Date(isoStr)
    if (isNaN(d.getTime())) return 'N/A'
    return d.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return 'N/A'
  }
}

function formatTimeOnly(isoStr?: string | null): string {
  if (!isoStr) return 'N/A'
  try {
    const d = new Date(isoStr)
    if (isNaN(d.getTime())) return 'N/A'
    return d.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return 'N/A'
  }
}

function formatDuration(startedAt?: string | null, finishedAt?: string | null): string {
  if (!startedAt) return '—'
  const start = new Date(startedAt).getTime()
  if (isNaN(start)) return '—'
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now()
  if (isNaN(end)) return '—'
  const diffMs = Math.max(0, end - start)
  if (diffMs < 1000) {
    return `${diffMs} ms`
  }
  if (diffMs < 60000) {
    const seconds = (diffMs / 1000).toFixed(1)
    return `${seconds}s`
  }
  const mins = Math.floor(diffMs / 60000)
  const remSecs = Math.round((diffMs % 60000) / 1000)
  return `${mins}m ${remSecs}s`
}

function calculateSpeed(succeeded: number, startedAt?: string | null, finishedAt?: string | null): string | null {
  if (!startedAt || succeeded <= 0) return null
  const start = new Date(startedAt).getTime()
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now()
  const diffSec = (end - start) / 1000
  if (diffSec <= 0.05) return null
  const rate = succeeded / diffSec
  return `${rate.toFixed(1)} inv/s`
}

function RunCard({ 
  run, 
  onRetry, 
  onClick, 
  onDelete 
}: { 
  run: BillingRunOut, 
  onRetry?: (id: number) => void, 
  onClick?: (id: number) => void,
  onDelete?: (id: number) => void 
}) {
  const isRunning = run.status === 'RUNNING' || run.status === 'QUEUED' || run.status === 'PENDING'
  const isComplete = run.status === 'COMPLETED' || run.status === 'SUCCESS' || run.status === 'DONE'
  const isFailed = run.status === 'FAILED'
  const isPartial = run.status === 'COMPLETED_WITH_ERRORS' || run.status === 'PARTIAL'
  
  const processedCount = (run.succeeded || 0) + (run.failed || 0)
  const totalCount = Math.max(run.total_accounts || 1, processedCount, 1)
  
  const progress = isComplete 
    ? 100 
    : isFailed 
      ? 100 
      : Math.min(99, Math.round((processedCount / totalCount) * 100))

  const { title, subtitle } = formatRunTitle(run.batch_name)
  const cycleLabel = formatCycleDisplayName(run.cycle_number || run.batch_name)
  const speed = calculateSpeed(run.succeeded || 0, run.started_at, run.finished_at)

  return (
    <div 
      className={cn(
        "flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs relative overflow-hidden transition-all duration-200 hover:shadow-md hover:border-slate-300 dark:hover:border-slate-700 shrink-0", 
        isComplete && "border-l-4 border-l-emerald-500",
        isFailed && "border-l-4 border-l-red-500",
        isPartial && "border-l-4 border-l-amber-500",
        isRunning && "border-l-4 border-l-blue-500 animate-pulse-border",
        onClick && "cursor-pointer"
      )}
      onClick={() => onClick && onClick(run.id)}
    >
      <div className="flex items-start justify-between gap-2 border-b border-border/40 pb-3">
        <div className="flex items-start gap-2.5 min-w-0">
          <div className={cn(
            "p-2 rounded-lg shrink-0 mt-0.5",
            isRunning ? "bg-amber-100 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300" :
            isComplete ? "bg-emerald-100 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300" :
            isFailed ? "bg-red-100 dark:bg-red-950/50 text-red-700 dark:text-red-300" :
            "bg-blue-100 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300"
          )}>
            <Zap className={cn("size-4 shrink-0", isRunning && "animate-pulse")} />
          </div>
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold text-sm text-foreground truncate">{title}</span>
              {cycleLabel && (
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-md bg-muted text-muted-foreground whitespace-nowrap">
                  {cycleLabel}
                </span>
              )}
            </div>
            {subtitle && (
              <span className="text-xs text-muted-foreground mt-0.5 truncate">{subtitle}</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {isRunning && (
            <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-700 dark:text-amber-300 bg-amber-100 dark:bg-amber-950/40 px-2.5 py-0.5 rounded-full">
              <Loader2 size={12} className="animate-spin" /> In Progress
            </span>
          )}
          {isComplete && (
            <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-100 dark:bg-emerald-950/40 px-2.5 py-0.5 rounded-full">
              <CheckCircle2 size={12} /> Completed
            </span>
          )}
          {isFailed && (
            <span className="inline-flex items-center gap-1 text-xs font-bold text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-950/40 px-2.5 py-0.5 rounded-full">
              <XCircle size={12} /> Failed
            </span>
          )}
          {isPartial && (
            <span className="inline-flex items-center gap-1 text-xs font-bold text-orange-700 dark:text-orange-300 bg-orange-100 dark:bg-orange-950/40 px-2.5 py-0.5 rounded-full">
              <AlertTriangle size={12} /> Partial
            </span>
          )}
          
          {onDelete && !isRunning && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-destructive rounded-full"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(run.id)
              }}
              title="Delete run record"
            >
              <Trash2 size={13} />
            </Button>
          )}
        </div>
      </div>
      
      <div className="flex flex-col gap-2 pt-1">
        <div className="flex justify-between items-center text-xs font-semibold">
          <span className="text-muted-foreground">
            {processedCount} / {totalCount} account{totalCount !== 1 ? 's' : ''} processed
          </span>
          <span className={cn(
            "font-extrabold",
            isComplete ? "text-emerald-600 dark:text-emerald-400" :
            isFailed ? "text-red-600 dark:text-red-400" :
            "text-foreground"
          )}>
            {progress}%
          </span>
        </div>
        <Progress value={progress} className="h-2 rounded-full" />
        
        <div className="flex justify-between items-center text-xs pt-1">
          <span className="text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1">
            <CheckCircle2 size={12} /> {run.succeeded || 0} Succeeded
          </span>
          {run.failed > 0 && (
            <span className="text-red-600 dark:text-red-400 font-bold flex items-center gap-1">
              <XCircle size={12} /> {run.failed} Failed
            </span>
          )}
        </div>

        {/* Live Timing & Metrics Summary Grid */}
        <div className="grid grid-cols-3 gap-2 pt-2 border-t border-border/40 text-xs">
          {/* Start Time */}
          <div className="rounded-lg bg-muted/40 p-2 border border-border/40 flex flex-col justify-between">
            <div className="flex items-center gap-1 text-muted-foreground font-semibold text-[11px]">
              <Clock size={12} className="text-blue-500 shrink-0" />
              <span>Start Time</span>
            </div>
            <div className="font-mono font-bold text-foreground text-xs mt-1 truncate" title={formatDateTime(run.started_at)}>
              {formatTimeOnly(run.started_at)}
            </div>
          </div>

          {/* End Time */}
          <div className="rounded-lg bg-muted/40 p-2 border border-border/40 flex flex-col justify-between">
            <div className="flex items-center gap-1 text-muted-foreground font-semibold text-[11px]">
              <Clock size={12} className={run.finished_at ? "text-emerald-500 shrink-0" : "text-amber-500 shrink-0"} />
              <span>End Time</span>
            </div>
            <div className="font-mono font-bold text-foreground text-xs mt-1 truncate" title={run.finished_at ? formatDateTime(run.finished_at) : 'In progress'}>
              {run.finished_at ? (
                formatTimeOnly(run.finished_at)
              ) : (
                <span className="text-amber-600 dark:text-amber-400 italic text-[11px] flex items-center gap-1 font-sans font-medium">
                  <Loader2 size={10} className="animate-spin shrink-0" /> In progress
                </span>
              )}
            </div>
          </div>

          {/* Total Time / Duration & Speed */}
          <div className="rounded-lg bg-indigo-50/50 dark:bg-indigo-950/20 p-2 border border-indigo-200/40 dark:border-indigo-800/30 flex flex-col justify-between">
            <div className="flex items-center justify-between text-indigo-700 dark:text-indigo-300 font-semibold text-[11px]">
              <div className="flex items-center gap-1">
                <Timer size={12} className="text-indigo-600 dark:text-indigo-400 shrink-0" />
                <span>Total Time</span>
              </div>
              {speed && isComplete && (
                <span className="text-[10px] bg-indigo-100 dark:bg-indigo-900/60 px-1 py-0.2 rounded font-mono font-bold text-indigo-800 dark:text-indigo-200">
                  {speed}
                </span>
              )}
            </div>
            <div className="font-mono font-extrabold text-indigo-900 dark:text-indigo-200 text-xs mt-1">
              {formatDuration(run.started_at, run.finished_at)}
            </div>
          </div>
        </div>
        
        {onRetry && run.failed > 0 && (
          <Button
            variant="outline"
            size="sm"
            className="mt-2 w-full h-8 text-xs font-bold bg-red-50 text-red-700 hover:bg-red-100 hover:text-red-800 border-red-200"
            onClick={(e) => {
              e.stopPropagation()
              onRetry(run.id)
            }}
            disabled={isRunning}
          >
            {isRunning ? <Loader2 size={12} className="animate-spin mr-1.5" /> : <Play size={12} className="mr-1.5" />}
            Retry Failed Invoices
          </Button>
        )}
        
        <div className="flex justify-end gap-2 mt-1 pt-2 border-t border-border/30">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 text-xs font-semibold hover:bg-muted"
            onClick={(e) => {
              e.stopPropagation()
              onClick && onClick(run.id)
            }}
          >
            <Eye size={12} className="mr-1.5" />
            View Output Files
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function GenerationHub() {
  const queryClient = useQueryClient()
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null)

  const { data: runResults, isLoading: loadingResults } = useQuery({
    queryKey: ['run-results', selectedRunId],
    queryFn: () => getRunResults(selectedRunId!),
    enabled: !!selectedRunId
  })

  const handleViewPdf = async (success: any) => {
    try {
      const url = await fetchPdfBlobUrl(success.date, success.cycle, success.batch, success.filename)
      window.open(url, '_blank')
    } catch (e) {
      toast.error('Failed to open PDF')
    }
  }

  const handleDownloadPdf = async (success: any) => {
    try {
      const url = await fetchPdfBlobUrl(success.date, success.cycle, success.batch, success.filename)
      const a = document.createElement('a')
      a.href = url
      a.download = success.filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    } catch (e) {
      toast.error('Failed to download PDF')
    }
  }
  
  const { data: runs, isLoading: loadingRuns } = useQuery({
    queryKey: ['billing-runs'],
    queryFn: () => getRuns(),
    refetchInterval: (query) => {
      const data = query.state.data
      const isActive = data?.some((r: any) => r.status === 'RUNNING' || r.status === 'PENDING')
      return isActive ? 3000 : 8000
    },
    placeholderData: (prev) => prev,
  })

  const hasActiveRun = runs?.some(r => r.status === 'RUNNING' || r.status === 'PENDING')

  const { data: pendingBatches, isLoading: loadingBatches } = useQuery({
    queryKey: ['billing-pending-batches'],
    queryFn: () => getPendingBatches(),
    refetchInterval: hasActiveRun ? 3000 : 8000,
    placeholderData: (prev) => prev,
  })

  const batchMutation = useMutation({
    mutationFn: ({ uploadIds, recordLimit }: { uploadIds: number[]; recordLimit?: number | null }) => 
      generateGroupBatch(uploadIds, recordLimit),
    onSuccess: (data) => {
      toast.success(data.message)
      queryClient.invalidateQueries({ queryKey: ['billing-pending-batches'] })
      queryClient.invalidateQueries({ queryKey: ['billing-runs'] })
    },
    onError: (err: any) => toast.error(err.detail || 'Failed to start batch generation')
  })

  const retryMutation = useMutation({
    mutationFn: (runId: number) => retryFailedRun(runId),
    onSuccess: (data) => {
      toast.success(data.message)
      queryClient.invalidateQueries({ queryKey: ['billing-runs'] })
      queryClient.invalidateQueries({ queryKey: ['run-results', selectedRunId] })
    },
    onError: (err: any) => toast.error(err.detail || 'Failed to retry run')
  })

  const deleteRunMutation = useMutation({
    mutationFn: (runId: number) => deleteRun(runId),
    onSuccess: () => {
      toast.success("Billing run deleted successfully.")
      queryClient.invalidateQueries({ queryKey: ['billing-runs'] })
    },
    onError: (err: any) => toast.error(err.message || "Failed to delete run.")
  })

  const deleteAllRunsMutation = useMutation({
    mutationFn: () => deleteAllRuns(),
    onSuccess: () => {
      toast.success("All completed run history deleted.")
      queryClient.invalidateQueries({ queryKey: ['billing-runs'] })
    },
    onError: (err: any) => toast.error(err.message || "Failed to clear runs.")
  })

  const handleGenerateAll = async () => {
    if (!pendingBatches || pendingBatches.length === 0) return
    let i = 0;
    for (const batch of pendingBatches) {
      toast.success(`Queueing batch...`)
      await batchMutation.mutateAsync({ uploadIds: batch.upload_ids, recordLimit: null })
      i++
      await new Promise(r => setTimeout(r, 1000))
    }
    toast.success(`Queued ${i} batches successfully!`)
  }

  const activeRuns = runs?.filter(r => r.status === 'RUNNING' || r.status === 'QUEUED' || r.status === 'PENDING') || []
  const recentRuns = runs?.filter(r => r.status !== 'RUNNING' && r.status !== 'QUEUED' && r.status !== 'PENDING') || []
  const batchesList = pendingBatches || []
  const hasBatches = batchesList.length > 0

  const activeCyclesStr = batchesList.map(b => formatCycleDisplayName(String(b.cycle_number))).join(', ')

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <PageHeader 
          title="Generation Hub" 
          description="Monitor active batch jobs and trigger grouped invoice generation for real GMF cycles." 
        />
        {hasBatches && (
          <Button 
            onClick={handleGenerateAll} 
            disabled={batchMutation.isPending} 
            className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 font-extrabold shadow-[0_4px_12px_rgba(16,185,129,0.25)] text-white border-transparent transition-all"
          >
            <Play size={16} className="mr-2 fill-current" />
            Generate All Cycles ({activeCyclesStr})
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left Column: Live Runs and History (Wider Panel) */}
        <div className="flex flex-col gap-6 lg:col-span-3">
          {/* Live Runs Section */}
          <div className="flex flex-col gap-4">
            <h3 className="font-semibold text-lg flex items-center gap-2">
              Live Runs
              {activeRuns.length > 0 && (
                <span className="bg-amber-100 text-amber-700 text-xs px-2 py-0.5 rounded-full animate-pulse font-bold">
                  {activeRuns.length} Active
                </span>
              )}
            </h3>
            <div className="flex flex-col gap-4 p-1">
              {loadingRuns ? (
                <div className="h-32 animate-pulse rounded-lg bg-muted" />
              ) : activeRuns.length === 0 ? (
                <div className="rounded-xl border bg-card p-6 text-center text-sm text-muted-foreground shadow-sm">
                  No active billing runs at the moment.
                </div>
              ) : (
                activeRuns.map(run => (
                  <RunCard 
                    key={run.id} 
                    run={run} 
                    onClick={(id) => setSelectedRunId(id)} 
                  />
                ))
              )}
            </div>
          </div>

          {/* Recent Completed Runs Section */}
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-lg flex items-center gap-2">
                Recent Completed Runs
              </h3>
              {recentRuns.length > 0 && (
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => {
                    if (window.confirm("Are you sure you want to clear all completed history?")) {
                      deleteAllRunsMutation.mutate()
                    }
                  }}
                  disabled={deleteAllRunsMutation.isPending}
                  className="text-muted-foreground hover:text-destructive flex items-center gap-1.5 h-8 font-semibold border-muted-foreground/25"
                >
                  <Trash2 size={13} />
                  Delete All Runs
                </Button>
              )}
            </div>
            <div className="flex flex-col gap-4 max-h-[400px] overflow-y-auto p-1">
              {loadingRuns ? (
                <div className="h-32 animate-pulse rounded-lg bg-muted" />
              ) : recentRuns.length === 0 ? (
                <div className="rounded-xl border border-dashed bg-transparent p-6 text-center text-sm text-muted-foreground">
                  No recent run history.
                </div>
              ) : (
                recentRuns.map(run => (
                  <RunCard 
                    key={run.id} 
                    run={run} 
                    onRetry={(id) => retryMutation.mutate(id)} 
                    onClick={(id) => setSelectedRunId(id)}
                    onDelete={(id) => deleteRunMutation.mutate(id)}
                  />
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Approved GMFs ready to generate */}
        <div className="flex flex-col gap-4 lg:col-span-2">
          <h3 className="font-semibold text-lg">Ready for Generation</h3>
          <div className="rounded-xl border bg-card shadow-sm flex flex-col min-h-[400px]">
            {loadingBatches && !pendingBatches ? (
              <div className="flex-1 flex items-center justify-center">
                <Loader2 className="animate-spin text-muted-foreground" />
              </div>
            ) : !hasBatches ? (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-muted-foreground text-center">
                <CheckCircle2 size={48} className="mb-4 text-emerald-500/20" />
                <p>No pending grouped batches.</p>
                <p className="text-sm mt-1">All approved GMFs have been queued or processed.</p>
              </div>
            ) : (
              <div className="flex flex-col p-3 gap-3 max-h-[600px] overflow-y-auto">
                {batchesList.map(batch => {
                  const cycleTitle = formatCycleDisplayName(String(batch.cycle_number))
                  const hasRecordCounts = (batch.total_records || 0) > 0
                  
                  const isThisCardPending = 
                    batchMutation.isPending &&
                    batchMutation.variables?.uploadIds?.some(id => batch.upload_ids.includes(id))

                  const isLimit10Pending = isThisCardPending && batchMutation.variables?.recordLimit === 10
                  const isLimit50Pending = isThisCardPending && batchMutation.variables?.recordLimit === 50
                  const isLimitAllPending = isThisCardPending && batchMutation.variables?.recordLimit === null
                  
                  return (
                    <div key={`${batch.cycle_number}-${batch.date}`} className="flex flex-col gap-3 p-4 rounded-xl border bg-card hover:border-indigo-300 dark:hover:border-indigo-800 transition-all shadow-xs">
                      {/* Header Row: Title & Date */}
                      <div className="flex items-center justify-between gap-2 border-b border-border/40 pb-2.5">
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText size={18} className="text-indigo-600 dark:text-indigo-400 shrink-0" />
                          <span className="font-extrabold text-base text-foreground whitespace-nowrap truncate">{cycleTitle}</span>
                        </div>
                        <span className="text-xs font-semibold px-2.5 py-0.5 rounded-md bg-muted text-muted-foreground whitespace-nowrap shrink-0">
                          {batch.date}
                        </span>
                      </div>

                      {/* Progress Badge Row */}
                      <div>
                        {hasRecordCounts ? (
                          <div className="flex flex-wrap items-center justify-between gap-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 px-3 py-2 border border-emerald-200/60 dark:border-emerald-800/40 text-xs">
                            <span className="font-extrabold text-emerald-700 dark:text-emerald-300 whitespace-nowrap">
                              {(batch.remaining_records ?? 0).toLocaleString()} Remaining
                            </span>
                            <span className="text-emerald-800/70 dark:text-emerald-300/70 whitespace-nowrap text-[11px]">
                              ({(batch.processed_records ?? 0).toLocaleString()} / {(batch.total_records ?? 0).toLocaleString()} Done)
                            </span>
                          </div>
                        ) : (
                          <div className="rounded-lg bg-blue-50 dark:bg-blue-950/40 px-3 py-2 text-xs font-bold text-blue-700 dark:text-blue-300 whitespace-nowrap">
                            {batch.file_count} File(s)
                          </div>
                        )}
                      </div>

                      {/* Action Buttons Row */}
                      <div className="grid grid-cols-3 gap-2 pt-1">
                        <Button 
                          variant="outline"
                          size="sm"
                          onClick={() => batchMutation.mutate({ uploadIds: batch.upload_ids, recordLimit: 10 })}
                          disabled={isThisCardPending}
                          className="h-8.5 text-xs font-bold px-1.5 whitespace-nowrap hover:bg-indigo-50 hover:text-indigo-700 dark:hover:bg-indigo-950/50 border-indigo-200/80 dark:border-indigo-800/60"
                          title="Generate next 10 customer records"
                        >
                          {isLimit10Pending ? (
                            <Loader2 size={12} className="animate-spin mr-1 shrink-0" />
                          ) : null}
                          Generate 10
                        </Button>
                        <Button 
                          variant="outline"
                          size="sm"
                          onClick={() => batchMutation.mutate({ uploadIds: batch.upload_ids, recordLimit: 50 })}
                          disabled={isThisCardPending}
                          className="h-8.5 text-xs font-bold px-1.5 whitespace-nowrap hover:bg-indigo-50 hover:text-indigo-700 dark:hover:bg-indigo-950/50 border-indigo-200/80 dark:border-indigo-800/60"
                          title="Generate next 50 customer records"
                        >
                          {isLimit50Pending ? (
                            <Loader2 size={12} className="animate-spin mr-1 shrink-0" />
                          ) : null}
                          Generate 50
                        </Button>
                        <Button 
                          onClick={() => batchMutation.mutate({ uploadIds: batch.upload_ids, recordLimit: null })}
                          disabled={isThisCardPending}
                          className="bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-700 hover:to-blue-700 font-extrabold shadow-[0_2px_8px_rgba(79,70,229,0.25)] text-white hover:scale-[1.01] border-transparent transition-all h-8.5 text-xs px-1.5 whitespace-nowrap"
                          title="Generate all remaining customer records"
                        >
                          {isLimitAllPending ? (
                            <Loader2 size={12} className="animate-spin shrink-0 mr-1" />
                          ) : (
                            <Play size={12} className="mr-1 fill-current shrink-0" />
                          )}
                          <span className="truncate">Generate All</span>
                        </Button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      <Sheet open={!!selectedRunId} onOpenChange={(open) => !open && setSelectedRunId(null)}>
        <SheetContent side="right" className="w-full sm:max-w-xl overflow-y-auto dark:bg-slate-950">
          <SheetHeader className="border-b pb-4">
            <SheetTitle className="text-xl font-extrabold flex items-center gap-2">
              <Zap size={20} className="text-blue-500 fill-blue-500/20" />
              {runs?.find(r => r.id === selectedRunId)?.batch_name || "Run Details"}
            </SheetTitle>
            <SheetDescription className="text-sm">
              Detailed tracking of source GMF uploads and generated PDF invoices.
            </SheetDescription>
          </SheetHeader>
          
          {(() => {
            const run = runs?.find(r => r.id === selectedRunId)
            if (!run) return null
            const total = run.total_accounts || 1
            const progress = Math.round(((run.succeeded + run.failed) / total) * 100)
            return (
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3 my-5 p-4 rounded-xl border bg-muted/30 text-center">
                  <div className="flex flex-col">
                    <span className="text-lg font-extrabold text-foreground">{run.succeeded}</span>
                    <span className="text-[10px] uppercase font-bold text-emerald-600">Succeeded</span>
                  </div>
                  <div className="flex flex-col border-x">
                    <span className="text-lg font-extrabold text-foreground">{run.failed}</span>
                    <span className="text-[10px] uppercase font-bold text-rose-600">Failed</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-lg font-extrabold text-foreground">{progress}%</span>
                    <span className="text-[10px] uppercase font-bold text-blue-600">Progress</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 p-4 rounded-xl border bg-background text-sm">
                  <div className="flex flex-col">
                    <span className="text-xs text-muted-foreground font-bold">Total Accounts</span>
                    <span className="font-semibold text-foreground mt-0.5">{run.total_accounts}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xs text-muted-foreground font-bold">Status</span>
                    <span className="font-bold text-blue-600 dark:text-blue-400 mt-0.5 uppercase">{run.status}</span>
                  </div>
                  <div className="flex flex-col border-t pt-2.5">
                    <span className="text-xs text-muted-foreground font-bold flex items-center gap-1">
                      <Clock size={12} className="text-blue-500" /> Started At
                    </span>
                    <span className="font-medium text-foreground mt-0.5 text-xs">
                      {formatDateTime(run.started_at)}
                    </span>
                  </div>
                  <div className="flex flex-col border-t pt-2.5">
                    <span className="text-xs text-muted-foreground font-bold flex items-center gap-1">
                      <Clock size={12} className={run.finished_at ? "text-emerald-500" : "text-amber-500"} /> Finished At
                    </span>
                    <span className="font-medium text-foreground mt-0.5 text-xs">
                      {run.finished_at ? formatDateTime(run.finished_at) : (
                        <span className="text-amber-600 italic">In progress...</span>
                      )}
                    </span>
                  </div>
                  <div className="flex flex-col border-t pt-2.5">
                    <span className="text-xs text-muted-foreground font-bold flex items-center gap-1">
                      <Timer size={12} className="text-indigo-500" /> Total Duration
                    </span>
                    <span className="font-bold font-mono text-indigo-700 dark:text-indigo-300 mt-0.5 text-xs">
                      {formatDuration(run.started_at, run.finished_at)}
                    </span>
                  </div>
                  <div className="flex flex-col border-t pt-2.5">
                    <span className="text-xs text-muted-foreground font-bold flex items-center gap-1">
                      <Zap size={12} className="text-amber-500" /> Generation Speed
                    </span>
                    <span className="font-bold font-mono text-foreground mt-0.5 text-xs">
                      {calculateSpeed(run.succeeded || 0, run.started_at, run.finished_at) || '—'}
                    </span>
                  </div>
                  {run.output_path && (
                    <div className="flex flex-col col-span-2 border-t pt-2.5">
                      <span className="text-xs text-muted-foreground font-bold">Output Location</span>
                      <span className="font-mono text-xs text-muted-foreground mt-0.5 break-all">
                        {run.output_path}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )
          })()}
          
          <div className="mt-6 flex flex-col gap-6">
            {loadingResults ? (
              <div className="flex justify-center p-8"><Loader2 className="animate-spin text-muted-foreground" /></div>
            ) : runResults ? (
              <>
                {/* 1. Running GMF Files */}
                {runResults.gmf_running && runResults.gmf_running.length > 0 && (
                  <div className="flex flex-col gap-3 border-b pb-4">
                    <h4 className="font-bold text-sm flex items-center gap-2 text-blue-600 dark:text-blue-400">
                      <Loader2 size={15} className="animate-spin text-blue-500" />
                      Running GMF Files ({runResults.gmf_running.length})
                    </h4>
                    <div className="flex flex-col gap-2 max-h-[180px] overflow-y-auto pr-2">
                      {runResults.gmf_running.map((r: any) => (
                        <div key={r.id} className="flex items-center justify-between p-2.5 rounded border bg-blue-50/20 dark:bg-blue-950/10 text-xs">
                          <span className="font-semibold text-foreground truncate max-w-[320px]">{r.filename}</span>
                          <span className="bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300 text-[10px] px-2 py-0.5 rounded-full font-bold uppercase">
                            {r.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 2. Succeeded GMF Files */}
                {runResults.gmf_successes && runResults.gmf_successes.length > 0 && (
                  <div className="flex flex-col gap-3 border-b pb-4">
                    <h4 className="font-bold text-sm flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 size={15} className="text-emerald-500" />
                      Succeeded GMF Files ({runResults.gmf_successes.length})
                    </h4>
                    <div className="flex flex-col gap-2 max-h-[180px] overflow-y-auto pr-2">
                      {runResults.gmf_successes.map((s: any) => (
                        <div key={s.id} className="flex items-center justify-between p-2.5 rounded border bg-emerald-50/10 dark:bg-emerald-950/5 text-xs">
                          <span className="font-semibold text-foreground truncate max-w-[320px]">{s.filename}</span>
                          <span className="bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 text-[10px] px-2 py-0.5 rounded-full font-bold uppercase">
                            {s.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 3. Failed GMF Files */}
                {runResults.gmf_failures && runResults.gmf_failures.length > 0 && (
                  <div className="flex flex-col gap-3 border-b pb-4">
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-sm flex items-center gap-2 text-rose-600 dark:text-rose-400">
                        <XCircle size={15} className="text-rose-500" />
                        Failed GMF Files ({runResults.gmf_failures.length})
                      </h4>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 text-xs bg-red-50 text-red-700 hover:bg-red-100 border-red-200"
                        onClick={() => retryMutation.mutate(runResults.run_id)}
                        disabled={retryMutation.isPending}
                      >
                        <Play size={12} className="mr-1.5" />
                        Retry Failed
                      </Button>
                    </div>
                    <div className="flex flex-col gap-2 max-h-[180px] overflow-y-auto pr-2">
                      {runResults.gmf_failures.map((f: any) => (
                        <div key={f.id} className="flex flex-col p-2.5 rounded border border-red-100 dark:border-red-950/30 bg-red-50/20 dark:bg-red-950/10 text-xs">
                          <span className="font-semibold text-rose-700 dark:text-rose-400">{f.filename}</span>
                          {f.error_message && (
                            <span className="text-rose-600/80 dark:text-rose-400/80 mt-1 font-medium leading-relaxed">
                              {f.error_message}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 4. Generated PDF Invoices */}
                <div className="flex flex-col gap-3">
                  <h4 className="font-bold text-sm flex items-center gap-2">
                    <FileText size={15} className="text-blue-500" />
                    Generated PDF Invoices ({runResults.successes.length})
                  </h4>
                  {runResults.successes.length === 0 ? (
                    <p className="text-sm text-muted-foreground italic">No successful invoices.</p>
                  ) : (
                    <div className="flex flex-col gap-2 max-h-[220px] overflow-y-auto pr-2">
                      {runResults.successes.map((s: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between p-2.5 rounded border bg-slate-50 dark:bg-slate-900 text-xs">
                          <div className="flex items-center gap-2">
                            <FileText size={14} className="text-blue-400" />
                            <span className="font-semibold text-foreground">{s.account_number}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button variant="ghost" size="icon-sm" onClick={() => handleViewPdf(s)} title="View PDF">
                              <Eye size={13} />
                            </Button>
                            <Button variant="ghost" size="icon-sm" onClick={() => handleDownloadPdf(s)} title="Download PDF">
                              <Download size={13} />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : null}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
