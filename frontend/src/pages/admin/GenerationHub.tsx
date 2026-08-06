import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Play, CheckCircle2, Zap, Loader2, XCircle, AlertTriangle, Download, Eye, Trash2 } from 'lucide-react'
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
import { cn } from '@/lib/utils'
import { Progress } from '@/components/ui/progress'
import { useState } from 'react'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"

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
  
  let total = run.total_accounts || 1
  if (total === 0) total = 1
  const progress = Math.round(((run.succeeded + run.failed) / total) * 100)

  return (
    <div 
      className={cn(
        "flex flex-col gap-3 rounded-lg border bg-card p-4 shadow-sm relative overflow-hidden pl-5 transition-all duration-200 hover:shadow-md hover:scale-[1.005] shrink-0", 
        isComplete && "border-l-4 border-l-emerald-500 bg-gradient-to-br from-card to-emerald-50/5 dark:to-emerald-950/2",
        isFailed && "border-l-4 border-l-red-500 bg-gradient-to-br from-card to-red-50/5 dark:to-red-950/2",
        isPartial && "border-l-4 border-l-amber-500 bg-gradient-to-br from-card to-amber-50/5 dark:to-amber-950/2",
        isRunning && "border-l-4 border-l-blue-500 bg-gradient-to-br from-card to-blue-50/5 dark:to-blue-950/2",
        onClick && "cursor-pointer"
      )}
      onClick={() => onClick && onClick(run.id)}
    >
      <div className="flex items-center justify-between border-b pb-3">
        <div className="flex items-center gap-2">
          <Zap className={cn("size-5", isRunning ? "text-amber-500 fill-amber-500 animate-pulse" : isComplete ? "text-emerald-500" : isFailed ? "text-red-500" : "text-blue-500")} />
          <span className="font-semibold">{run.batch_name}</span>
          <span className="text-xs text-muted-foreground ml-2 px-2 py-0.5 bg-slate-100 rounded-full font-bold">
            Cycle {run.cycle_number}
          </span>
        </div>
        <div className="flex items-center gap-2 text-sm font-medium">
          {isRunning && <span className="text-amber-600 flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> {run.status}</span>}
          {isComplete && <span className="text-emerald-600 flex items-center gap-1"><CheckCircle2 size={12} /> {run.status}</span>}
          {isFailed && <span className="text-red-600 flex items-center gap-1"><XCircle size={12} /> {run.status}</span>}
          {isPartial && <span className="text-orange-600 flex items-center gap-1"><AlertTriangle size={12} /> {run.status}</span>}
          
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
              <Trash2 size={14} />
            </Button>
          )}
        </div>
      </div>
      
      <div className="flex flex-col gap-1.5 mt-1">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{run.succeeded + run.failed} / {run.total_accounts} accounts processed</span>
          <span>{progress}%</span>
        </div>
        <Progress value={progress} className="h-2" />
        <div className="flex justify-between mt-2 text-xs">
          <span className="text-emerald-600 font-medium">{run.succeeded} Success</span>
          {run.failed > 0 && <span className="text-red-600 font-medium">{run.failed} Failed</span>}
        </div>
        
        {onRetry && run.failed > 0 && (
          <Button
            variant="outline"
            size="sm"
            className="mt-2 w-full h-8 text-xs bg-red-50 text-red-700 hover:bg-red-100 hover:text-red-800 border-red-200"
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
        
        <div className="flex justify-end gap-2 mt-3 pt-2 border-t border-slate-100">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 text-xs font-semibold"
            onClick={(e) => {
              e.stopPropagation()
              onClick && onClick(run.id)
            }}
          >
            <Eye size={12} className="mr-1.5" />
            View Details
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
  
  const { data: pendingBatches, isLoading: loadingBatches } = useQuery({
    queryKey: ['billing-pending-batches'],
    queryFn: () => getPendingBatches(),
    refetchInterval: 1000,
  })

  const { data: runs, isLoading: loadingRuns } = useQuery({
    queryKey: ['billing-runs'],
    queryFn: () => getRuns(),
    refetchInterval: 1000,
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

  const activeCyclesStr = batchesList.map(b => 'Cycle ' + b.cycle_number).join(', ')

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
            {loadingBatches ? (
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
                  const cycleTitle = typeof batch.cycle_number === 'number' || String(batch.cycle_number).startsWith('Cycle')
                    ? `Cycle ${String(batch.cycle_number).replace('Cycle_', '')}`
                    : String(batch.cycle_number).replace('_', ' ')

                  const hasRecordCounts = (batch.total_records || 0) > 0
                  
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
                          disabled={batchMutation.isPending}
                          className="h-8.5 text-xs font-bold px-1.5 whitespace-nowrap hover:bg-indigo-50 hover:text-indigo-700 dark:hover:bg-indigo-950/50 border-indigo-200/80 dark:border-indigo-800/60"
                          title="Generate next 10 customer records"
                        >
                          Generate 10
                        </Button>
                        <Button 
                          variant="outline"
                          size="sm"
                          onClick={() => batchMutation.mutate({ uploadIds: batch.upload_ids, recordLimit: 50 })}
                          disabled={batchMutation.isPending}
                          className="h-8.5 text-xs font-bold px-1.5 whitespace-nowrap hover:bg-indigo-50 hover:text-indigo-700 dark:hover:bg-indigo-950/50 border-indigo-200/80 dark:border-indigo-800/60"
                          title="Generate next 50 customer records"
                        >
                          Generate 50
                        </Button>
                        <Button 
                          onClick={() => batchMutation.mutate({ uploadIds: batch.upload_ids, recordLimit: null })}
                          disabled={batchMutation.isPending}
                          className="bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-700 hover:to-blue-700 font-extrabold shadow-[0_2px_8px_rgba(79,70,229,0.25)] text-white hover:scale-[1.01] border-transparent transition-all h-8.5 text-xs px-1.5 whitespace-nowrap"
                          title="Generate all remaining customer records"
                        >
                          {batchMutation.isPending ? (
                            <Loader2 size={12} className="animate-spin shrink-0" />
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
                  <div className="flex flex-col col-span-2 border-t pt-2.5">
                    <span className="text-xs text-muted-foreground font-bold">Started At</span>
                    <span className="font-medium text-foreground mt-0.5">
                      {run.started_at ? new Date(run.started_at).toLocaleString() : 'N/A'}
                    </span>
                  </div>
                  {run.finished_at && (
                    <div className="flex flex-col col-span-2 border-t pt-2.5">
                      <span className="text-xs text-muted-foreground font-bold">Finished At</span>
                      <span className="font-medium text-foreground mt-0.5">
                        {new Date(run.finished_at).toLocaleString()}
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
