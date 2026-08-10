import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { FileText, CheckCircle2, AlertTriangle, Loader2, XCircle, Trash2, Info, ArrowRight, Layers, X } from 'lucide-react'
import { getUploads, deleteUpload, clearAllUploads, getUploadSummary, type GmfUploadOut } from '../../lib/api'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { DataTable, type ColumnDef } from '../../components/ui-kit/DataTable'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'
import { useAuth } from '../../auth/AuthProvider'

function StatusBadge({ status, processed, total }: { status: string; processed?: number; total?: number }) {
  if (status === 'PENDING_APPROVAL') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold bg-cyan-50 text-cyan-700 dark:bg-cyan-950/20 dark:text-cyan-400 border border-cyan-200/50">
        <div className="size-1.5 rounded-full bg-cyan-500" />
        Pending Review
      </span>
    )
  }
  if (status === 'APPROVED') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400 border border-emerald-200/50">
        <CheckCircle2 size={12} className="text-emerald-500" />
        Approved
      </span>
    )
  }
  if (status === 'GENERATING') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold bg-amber-50 text-amber-700 dark:bg-amber-950/20 dark:text-amber-400 border border-amber-200/50">
        <Loader2 size={12} className="animate-spin text-amber-500" />
        Generating
      </span>
    )
  }
  if (status === 'PARTIALLY_PROCESSED') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-300/60">
        <Loader2 size={12} className="text-amber-600 animate-pulse" />
        Partial ({processed && total ? `${processed}/${total}` : 'In Progress'})
      </span>
    )
  }
  if (status === 'COMPLETED') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold bg-blue-50 text-blue-700 dark:bg-blue-950/20 dark:text-blue-400 border border-blue-200/50">
        <CheckCircle2 size={12} className="text-blue-500" />
        Completed
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold bg-red-50 text-red-700 dark:bg-red-950/20 dark:text-red-400 border border-red-200/50">
      <XCircle size={12} className="text-red-500" />
      {status}
    </span>
  )
}

function GmfSummaryModal({ uploadId, onClose }: { uploadId: number | null; onClose: () => void }) {
  const navigate = useNavigate()
  const { data: summary, isLoading } = useQuery({
    queryKey: ['gmf-summary', uploadId],
    queryFn: () => (uploadId ? getUploadSummary(uploadId) : null),
    enabled: !!uploadId,
  })

  if (!uploadId) return null

  const pct = summary && summary.total_documents > 0
    ? Math.round((summary.processed_documents / summary.total_documents) * 100)
    : 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl bg-background text-foreground border border-border/80 shadow-2xl rounded-2xl p-6 space-y-5 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between gap-3 border-b border-border/40 pb-4">
          <div className="flex items-center gap-2">
            <FileText className="text-primary" size={22} />
            <h3 className="text-lg font-bold">GMF Processing Summary</h3>
          </div>
          <div className="flex items-center gap-2">
            {summary && (
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-extrabold uppercase tracking-wider ${summary.is_red_notice ? 'bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-300 border border-red-200' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200'
                }`}>
                {summary.is_red_notice ? 'RED Notice' : 'NON-RED'}
              </span>
            )}
            <button
              onClick={onClose}
              className="rounded-full p-1.5 hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {isLoading || !summary ? (
          <div className="h-48 flex items-center justify-center">
            <Loader2 className="animate-spin text-primary size-8" />
          </div>
        ) : (
          <div className="space-y-5">
            {/* File Info & Status */}
            <div className="rounded-xl bg-muted/40 border border-border/60 p-4 space-y-3">
              <div className="flex justify-between items-start">
                <div>
                  <div className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">GMF File</div>
                  <div className="text-sm font-bold text-foreground break-all">{summary.filename}</div>
                </div>
                <StatusBadge
                  status={summary.status}
                  processed={summary.processed_documents}
                  total={summary.total_documents}
                />
              </div>

              {/* 3 Stat Cards Grid */}
              <div className="grid grid-cols-3 gap-3 pt-2">
                <div className="flex flex-col items-center justify-center bg-card p-3 rounded-lg border border-border/50 shadow-sm">
                  <span className="text-xl font-bold text-foreground">{summary.total_documents}</span>
                  <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Total Invoices</span>
                </div>
                <div className="flex flex-col items-center justify-center bg-emerald-50/50 dark:bg-emerald-950/20 p-3 rounded-lg border border-emerald-200/50 dark:border-emerald-800/30 shadow-sm">
                  <span className="text-xl font-bold text-emerald-600 dark:text-emerald-400">{summary.processed_documents}</span>
                  <span className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-300 uppercase tracking-wider">Generated</span>
                </div>
                <div className="flex flex-col items-center justify-center bg-amber-50/50 dark:bg-amber-950/20 p-3 rounded-lg border border-amber-200/50 dark:border-amber-800/30 shadow-sm">
                  <span className="text-xl font-bold text-amber-600 dark:text-amber-400">{summary.remaining_documents}</span>
                  <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wider">Remaining</span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="space-y-1.5 pt-2">
                <div className="flex justify-between text-xs font-semibold">
                  <span className="text-muted-foreground">Overall Progress</span>
                  <span className="text-foreground">{summary.processed_documents} / {summary.total_documents} ({pct}%)</span>
                </div>
                <div className="w-full bg-slate-200 dark:bg-slate-800 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="bg-primary h-2.5 rounded-full transition-all duration-500"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Template Breakdown List */}
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                <Layers size={14} />
                Detected Template Types Breakdown
              </div>

              {summary.template_breakdown.length === 0 ? (
                <div className="text-xs text-muted-foreground italic p-3 border rounded-lg">
                  Single invoice template detected: <span className="font-bold text-foreground">{summary.template_detected}</span>
                </div>
              ) : (
                <div className="border border-border/60 rounded-xl overflow-hidden divide-y divide-border/40">
                  {summary.template_breakdown.map((item) => (
                    <div key={item.template_id} className="flex items-center justify-between p-3 text-xs hover:bg-muted/30 transition-colors">
                      <div className="flex flex-col">
                        <span className="font-bold text-foreground">{item.template_name}</span>
                        <span className="text-[11px] text-muted-foreground font-mono">{item.template_id}</span>
                      </div>

                      <div className="flex items-center gap-3">
                        <span className="font-semibold text-foreground bg-muted px-2 py-0.5 rounded-md">
                          {item.count} invoice{item.count > 1 ? 's' : ''}
                        </span>

                        {item.is_approved ? (
                          <span className="inline-flex items-center gap-1 font-bold text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200/50 px-2 py-0.5 rounded-full text-[11px]">
                            <CheckCircle2 size={11} /> Approved
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 font-bold text-amber-600 bg-amber-50 dark:bg-amber-950/30 border border-amber-200/50 px-2 py-0.5 rounded-full text-[11px]">
                            <AlertTriangle size={11} /> Waiting Approval (Unapproved)
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Standby Output Archive Link */}
            {summary.processed_documents > 0 && (
              <div className="pt-2 flex justify-end">
                <Button
                  size="sm"
                  onClick={() => {
                    onClose()
                    navigate('/archive')
                  }}
                  className="flex items-center gap-2 font-bold shadow-md"
                >
                  View Generated Invoices in Output Archive
                  <ArrowRight size={14} />
                </Button>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  )
}

export default function GmfMonitor() {
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const [showCompleted, setShowCompleted] = useState(false)
  const [selectedSummaryId, setSelectedSummaryId] = useState<number | null>(null)
  const canManageUploads = session?.role === 'gmf_handler' || (session?.role as string) === 'admin1'

  const { data: uploads, isLoading } = useQuery({
    queryKey: ['billing-uploads'],
    queryFn: () => getUploads(),
    refetchInterval: 1000,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteUpload(id),
    onSuccess: (data) => {
      toast.success(data.message || "GMF file deleted successfully.")
      queryClient.invalidateQueries({ queryKey: ['billing-uploads'] })
    },
    onError: (err: any) => {
      toast.error(err?.message || "Failed to delete GMF file.")
    }
  })

  const clearAllMutation = useMutation({
    mutationFn: () => clearAllUploads(),
    onSuccess: (data: any) => {
      toast.success(data.message || "GMF uploads cleared.")
      queryClient.invalidateQueries({ queryKey: ['billing-uploads'] })
    },
    onError: (err: any) => {
      toast.error(err?.message || "Failed to clear GMF uploads.")
    }
  })

  const handleDelete = (id: number) => {
    if (confirm("Are you sure you want to delete this GMF file?")) {
      deleteMutation.mutate(id)
    }
  }

  const handleClearAll = () => {
    if (confirm("Are you sure you want to clear all GMF uploads that are not associated with approved or rejected templates?")) {
      clearAllMutation.mutate()
    }
  }

  const COLS: ColumnDef<GmfUploadOut>[] = [
    {
      header: 'Filename & Notice Type',
      cell: (upload) => {
        const fn = upload.filename.toUpperCase()
        const isRed = fn.includes('BILL-RED') || fn.includes('-RED_') || fn.includes('_RED.')
        return (
          <div className="flex flex-col gap-1 cursor-pointer" onClick={() => setSelectedSummaryId(upload.id)}>
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-muted-foreground" />
              <span className="font-semibold text-foreground hover:underline">{upload.filename}</span>
              <span className={`px-2 py-0.2 rounded-full text-[10px] font-extrabold uppercase tracking-wider ${isRed ? 'bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-300 border border-red-200' : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200'
                }`}>
                {isRed ? 'RED NOTICE' : 'NON-RED'}
              </span>
            </div>
            {upload.error_message && (
              <span className="text-xs text-red-500 flex items-center gap-1">
                <AlertTriangle size={10} />
                {upload.error_message}
              </span>
            )}
          </div>
        )
      },
    },
    {
      header: 'Cycle',
      cell: (upload) => {
        let label = 'Test GMF'
        if (upload.folder_type === 'LOD') label = 'LOD'
        else if (upload.folder_type === 'VAT_Confirmation') label = 'VAT Confirmation'
        else if (upload.cycle_number) label = `Cycle ${upload.cycle_number}`
        return (
          <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-slate-800 dark:bg-slate-800 dark:text-slate-200 border border-slate-200/50 dark:border-slate-700/30">
            {label}
          </span>
        )
      },
    },
    {
      header: 'Detected Templates',
      cell: (upload) => (
        <span className="text-xs font-bold text-foreground">
          {upload.template_detected ? upload.template_detected.replace(/_/g, ' ') : <span className="text-muted-foreground font-medium">Unknown</span>}
        </span>
      ),
    },
    {
      header: 'Detected At',
      cell: (upload) => new Date(upload.detected_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }),
    },
    {
      header: 'Status',
      cell: (upload) => (
        <div className="cursor-pointer" onClick={() => setSelectedSummaryId(upload.id)}>
          <StatusBadge
            status={upload.status}
            processed={upload.processed_records_count}
            total={upload.total_records_count}
          />
        </div>
      ),
    },
    {
      header: 'Summary & Actions',
      cell: (upload: GmfUploadOut) => {
        const isLocked = upload.template_status === 'APPROVED' || upload.template_status === 'REJECTED'
        return (
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedSummaryId(upload.id)}
              className="h-8 text-xs font-bold gap-1 rounded-lg"
            >
              <Info size={13} />
              Summary
            </Button>
            {canManageUploads && (
              <Button
                variant="ghost"
                size="icon"
                onClick={(e) => {
                  e.stopPropagation()
                  handleDelete(upload.id)
                }}
                disabled={isLocked || deleteMutation.isPending}
                title={isLocked ? "Cannot delete: Associated template has been approved/rejected" : "Delete GMF"}
                className="rounded-full size-8 text-muted-foreground hover:text-destructive disabled:opacity-40"
              >
                <Trash2 size={14} />
              </Button>
            )}
          </div>
        )
      }
    }
  ]

  const allUploads = uploads || []
  const filteredUploads = allUploads.filter(u => u.folder_type !== 'Test_GMFs')

  const displayedUploads = allUploads.filter((u) => {
    if (!showCompleted && u.status === 'COMPLETED') {
      return false
    }
    return true
  })

  const summary = {
    total: allUploads.length,
    pending: allUploads.filter(u => u.status === 'PENDING_APPROVAL').length,
    completed: filteredUploads.filter(u => u.status === 'COMPLETED').length,
    failed: filteredUploads.filter(u => u.status === 'FAILED').length,
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="GMF Monitor"
        description="Monitor detected GMF files, partial generation progress, and template approval statuses."
        actions={
          canManageUploads && allUploads.length > 0 ? (
            <Button
              variant="destructive"
              size="sm"
              onClick={handleClearAll}
              disabled={clearAllMutation.isPending}
              className="flex items-center gap-1.5 font-bold shadow-sm"
            >
              <Trash2 size={14} />
              {clearAllMutation.isPending ? "Clearing..." : "Clear All Uploads"}
            </Button>
          ) : undefined
        }
      />

      <div className="grid grid-cols-4 gap-4 glass-card p-5 shadow-lg">
        <div className="flex flex-col items-center justify-center border-r border-border/40">
          <span className="text-2xl font-bold">{summary.total}</span>
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Total Detected</span>
        </div>
        <div className="flex flex-col items-center justify-center border-r">
          <span className="text-2xl font-bold text-cyan-600">{summary.pending}</span>
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Pending Review</span>
        </div>
        <div className="flex flex-col items-center justify-center border-r">
          <span className="text-2xl font-bold text-emerald-600">{summary.completed}</span>
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Completed</span>
        </div>
        <div className="flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-rose-600">{summary.failed}</span>
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Failed</span>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between px-1">
          <span className="text-sm font-bold text-muted-foreground uppercase tracking-wider">Queue Files</span>
          <div className="flex items-center gap-3">
            <Label htmlFor="show-completed" className="text-xs font-semibold text-muted-foreground cursor-pointer select-none">
              Show Completed Files
            </Label>
            <Switch
              id="show-completed"
              checked={showCompleted}
              onCheckedChange={setShowCompleted}
            />
          </div>
        </div>

        {isLoading ? (
          <div className="h-64 animate-pulse rounded-lg bg-muted" />
        ) : (
          <DataTable
            columns={COLS}
            data={displayedUploads}
            keyExtractor={(upload) => upload.id}
            onRowClick={(upload) => setSelectedSummaryId(upload.id)}
            emptyLabel="No GMF uploads detected yet."
          />

        )}
      </div>

      <GmfSummaryModal
        uploadId={selectedSummaryId}
        onClose={() => setSelectedSummaryId(null)}
      />
    </div>
  )
}
