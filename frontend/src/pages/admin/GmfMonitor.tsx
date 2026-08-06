import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, CheckCircle2, AlertTriangle, Loader2, XCircle, Trash2, Eye } from 'lucide-react'
import { getUploads, deleteUpload, clearAllUploads, type GmfUploadOut } from '../../lib/api'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { DataTable, type ColumnDef } from '../../components/ui-kit/DataTable'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { toast } from 'sonner'
import { useAuth } from '../../auth/AuthProvider'

function StatusBadge({ status }: { status: string }) {
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

export default function GmfMonitor() {
  const queryClient = useQueryClient()
  const { session } = useAuth()
  const [showCompleted, setShowCompleted] = useState(false)
  const [selectedUpload, setSelectedUpload] = useState<GmfUploadOut | null>(null)
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
      header: 'Filename',
      cell: (upload) => (
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-muted-foreground shrink-0" />
            <span className="font-semibold text-foreground hover:text-indigo-600 transition-colors">{upload.filename}</span>
          </div>
          {upload.error_message && (
            <span className="text-xs text-red-500 mt-1 flex items-center gap-1">
              <AlertTriangle size={10} />
              {upload.error_message}
            </span>
          )}
        </div>
      ),
    },
    {
      header: 'Cycle',
      cell: (upload) => {
        let label = 'Test GMF'
        if (upload.folder_type === 'LOD') label = 'LOD'
        else if (upload.folder_type === 'VAT_Confirmation') label = 'VAT Confirmation'
        else if (upload.folder_type === 'Final_Notice') label = 'Final Notice'
        else if (upload.folder_type === 'Customer_Letter' || upload.folder_type === 'Customer_Letter_Logo_V1Print') label = 'Customer Letter'
        else if (upload.cycle_number) label = `Cycle ${upload.cycle_number}`
        return (
          <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-slate-800 dark:bg-slate-800 dark:text-slate-200 border border-slate-200/50 dark:border-slate-700/30">
            {label}
          </span>
        )
      },
    },
    {
      header: 'Detected Templates & Customer Breakdown',
      cell: (upload) => {
        const breakdown = upload.template_breakdown
        const total = upload.total_records_count || 0
        const processed = upload.processed_records_count || 0

        const hasBreakdown = breakdown && Object.keys(breakdown).length > 0

        return (
          <div className="flex flex-col gap-1.5 py-0.5">
            <div className="flex items-center gap-2">
              <span className="text-sm font-extrabold text-foreground tracking-tight">
                {total > 0 ? total.toLocaleString() : '-'} <span className="text-xs font-normal text-muted-foreground">total records</span>
              </span>
              {processed > 0 && (
                <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                  {processed.toLocaleString()} processed
                </span>
              )}
            </div>

            {/* Template Breakdown Pill List */}
            <div className="flex flex-wrap gap-1.5 max-w-md">
              {hasBreakdown ? (
                Object.entries(breakdown).map(([tid, count]) => {
                  const formattedName = tid.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
                  return (
                    <span 
                      key={tid} 
                      className="inline-flex items-center gap-1.5 rounded-md bg-indigo-50/80 px-2 py-0.5 text-xs font-semibold text-indigo-800 dark:bg-indigo-950/50 dark:text-indigo-200 border border-indigo-200/60 dark:border-indigo-800/40 shadow-xs"
                    >
                      <span>{formattedName}</span>
                      <span className="inline-flex items-center justify-center rounded-full bg-indigo-600 px-1.5 py-0.2 text-[10px] font-black text-white dark:bg-indigo-400 dark:text-slate-950">
                        {count.toLocaleString()}
                      </span>
                    </span>
                  )
                })
              ) : upload.template_detected ? (
                <span className="inline-flex items-center gap-1.5 rounded-md bg-indigo-50 px-2.5 py-0.5 text-xs font-bold text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300 border border-indigo-200/60 dark:border-indigo-800/40">
                  {upload.template_detected.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}: {total > 0 ? total.toLocaleString() : 1}
                </span>
              ) : (
                <span className="text-xs text-muted-foreground italic">Template Unknown</span>
              )}
            </div>
          </div>
        )
      },
    },
    {
      header: 'Detected At',
      cell: (upload) => new Date(upload.detected_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }),
    },
    {
      header: 'Status',
      cell: (upload) => <StatusBadge status={upload.status} />,
    },
    {
      header: 'Actions',
      cell: (upload: GmfUploadOut) => {
        const isLocked = upload.template_status === 'APPROVED' || upload.template_status === 'REJECTED'
        return (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={(e) => {
                e.stopPropagation()
                setSelectedUpload(upload)
              }}
              title="View File Summary"
              className="rounded-full size-8 text-muted-foreground hover:text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-950/50"
            >
              <Eye size={15} />
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
        description="Monitor detected GMF files and click any row to view full file breakdown and metrics."
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
            emptyLabel="No GMF uploads detected yet."
            onRowClick={(upload) => setSelectedUpload(upload)}
          />
        )}
      </div>

      {/* GMF File Summary Drawer */}
      <Sheet open={!!selectedUpload} onOpenChange={(open) => !open && setSelectedUpload(null)}>
        <SheetContent className="sm:max-w-md md:max-w-lg overflow-y-auto p-6 space-y-6">
          {selectedUpload && (
            <div className="space-y-6">
              <SheetHeader className="space-y-1 text-left border-b pb-4">
                <div className="flex items-center gap-2">
                  <FileText className="text-indigo-600 shrink-0" size={20} />
                  <SheetTitle className="text-lg font-bold truncate">
                    {selectedUpload.filename}
                  </SheetTitle>
                </div>
                <div className="flex items-center gap-2 pt-1">
                  <StatusBadge status={selectedUpload.status} />
                  <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    {selectedUpload.folder_type === 'LOD' ? 'LOD' : selectedUpload.folder_type === 'VAT_Confirmation' ? 'VAT Confirmation' : selectedUpload.folder_type === 'Final_Notice' ? 'Final Notice' : selectedUpload.folder_type === 'Customer_Letter' || selectedUpload.folder_type === 'Customer_Letter_Logo_V1Print' ? 'Customer Letter' : `Cycle ${selectedUpload.cycle_number || 1}`}
                  </span>
                </div>
              </SheetHeader>

              {/* 3 Cards Stats Grid */}
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-xl border bg-card p-3 text-center shadow-xs">
                  <span className="text-xl font-extrabold text-foreground">
                    {(selectedUpload.total_records_count || 0).toLocaleString()}
                  </span>
                  <span className="block text-[11px] font-bold text-muted-foreground uppercase mt-0.5">
                    Total Records
                  </span>
                </div>
                <div className="rounded-xl border bg-emerald-50/60 dark:bg-emerald-950/20 p-3 text-center border-emerald-200/50 shadow-xs">
                  <span className="text-xl font-extrabold text-emerald-700 dark:text-emerald-400">
                    {(selectedUpload.processed_records_count || 0).toLocaleString()}
                  </span>
                  <span className="block text-[11px] font-bold text-emerald-800/80 dark:text-emerald-300 uppercase mt-0.5">
                    Processed
                  </span>
                </div>
                <div className="rounded-xl border bg-amber-50/60 dark:bg-amber-950/20 p-3 text-center border-amber-200/50 shadow-xs">
                  <span className="text-xl font-extrabold text-amber-700 dark:text-amber-400">
                    {Math.max(0, (selectedUpload.total_records_count || 0) - (selectedUpload.processed_records_count || 0)).toLocaleString()}
                  </span>
                  <span className="block text-[11px] font-bold text-amber-800/80 dark:text-amber-300 uppercase mt-0.5">
                    Remaining
                  </span>
                </div>
              </div>

              {/* Progress Bar */}
              {(selectedUpload.total_records_count || 0) > 0 && (
                <div className="space-y-1.5 bg-muted/40 p-3.5 rounded-xl border border-border/50">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="text-muted-foreground">Generation Progress</span>
                    <span className="text-indigo-600 dark:text-indigo-400">
                      {Math.round(((selectedUpload.processed_records_count || 0) / (selectedUpload.total_records_count || 1)) * 100)}%
                    </span>
                  </div>
                  <Progress 
                    value={Math.round(((selectedUpload.processed_records_count || 0) / (selectedUpload.total_records_count || 1)) * 100)} 
                    className="h-2"
                  />
                </div>
              )}

              {/* Template Breakdown */}
              <div className="space-y-2.5">
                <h4 className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
                  Detected Templates & Customer Breakdown
                </h4>
                <div className="flex flex-col gap-2">
                  {selectedUpload.template_breakdown && Object.keys(selectedUpload.template_breakdown).length > 0 ? (
                    Object.entries(selectedUpload.template_breakdown).map(([tid, count]) => {
                      const formattedName = tid.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
                      const percent = selectedUpload.total_records_count 
                        ? Math.round((count / selectedUpload.total_records_count) * 100)
                        : 100
                      return (
                        <div key={tid} className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent/40 transition-colors">
                          <div className="flex items-center gap-2">
                            <div className="size-2 rounded-full bg-indigo-500" />
                            <span className="font-bold text-sm text-foreground">{formattedName}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-muted-foreground">{percent}%</span>
                            <span className="px-2.5 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-black text-xs">
                              {count.toLocaleString()} customers
                            </span>
                          </div>
                        </div>
                      )
                    })
                  ) : selectedUpload.template_detected ? (
                    <div className="flex items-center justify-between p-3 rounded-lg border bg-card">
                      <span className="font-bold text-sm text-foreground">
                        {selectedUpload.template_detected.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                      </span>
                      <span className="px-2.5 py-0.5 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-black text-xs">
                        {(selectedUpload.total_records_count || 1).toLocaleString()} customers
                      </span>
                    </div>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">No breakdown available.</p>
                  )}
                </div>
              </div>

              {/* Detailed File Properties */}
              <div className="space-y-2.5">
                <h4 className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
                  File Metadata & Location
                </h4>
                <div className="space-y-2 rounded-xl border bg-muted/20 p-3.5 text-xs">
                  <div className="flex justify-between py-1 border-b border-border/40">
                    <span className="font-medium text-muted-foreground">Upload ID</span>
                    <span className="font-bold font-mono text-foreground">#{selectedUpload.id}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/40">
                    <span className="font-medium text-muted-foreground">Detected Date</span>
                    <span className="font-bold text-foreground">
                      {new Date(selectedUpload.detected_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border/40">
                    <span className="font-medium text-muted-foreground">File Path</span>
                    <span className="font-mono text-[11px] text-muted-foreground truncate max-w-[220px]" title={selectedUpload.file_path}>
                      {selectedUpload.file_path}
                    </span>
                  </div>
                  {selectedUpload.billing_run_id && (
                    <div className="flex justify-between py-1 border-b border-border/40">
                      <span className="font-medium text-muted-foreground">Active Billing Run</span>
                      <span className="font-bold text-indigo-600">Run #{selectedUpload.billing_run_id}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Error / Rejection Info */}
              {(selectedUpload.error_message || selectedUpload.rejection_reason) && (
                <div className="rounded-xl border border-red-200 bg-red-50/50 p-3.5 dark:border-red-900/50 dark:bg-red-950/20 text-xs">
                  <div className="flex items-center gap-2 font-bold text-red-700 dark:text-red-400">
                    <AlertTriangle size={14} />
                    <span>Issue Details</span>
                  </div>
                  <p className="mt-1 text-red-600 dark:text-red-300 font-medium">
                    {selectedUpload.error_message || selectedUpload.rejection_reason}
                  </p>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}
