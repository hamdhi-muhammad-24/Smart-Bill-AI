import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, CheckCircle2, AlertTriangle, Loader2, XCircle, Trash2 } from 'lucide-react'
import { getUploads, deleteUpload, clearAllUploads, type GmfUploadOut } from '../../lib/api'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { DataTable, type ColumnDef } from '../../components/ui-kit/DataTable'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
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
            <FileText size={16} className="text-muted-foreground" />
            <span className="font-semibold text-foreground">{upload.filename}</span>
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
        else if (upload.cycle_number) label = `Cycle ${upload.cycle_number}`
        return (
          <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-slate-800 dark:bg-slate-800 dark:text-slate-200 border border-slate-200/50 dark:border-slate-700/30">
            {label}
          </span>
        )
      },
    },
    {
      header: 'Detected Template',
      cell: (upload) => (
        <span className="text-sm font-semibold text-foreground">
          {upload.template_detected ? upload.template_detected.replace('_', ' ') : <span className="text-muted-foreground font-medium">Unknown</span>}
        </span>
      ),
    },
    {
      header: 'Detected At',
      cell: (upload) => new Date(upload.detected_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }),
    },
    {
      header: 'Status',
      cell: (upload) => <StatusBadge status={upload.status} />,
    },
    ...(canManageUploads
      ? [{
          header: 'Actions',
          cell: (upload: GmfUploadOut) => {
            const isLocked = upload.template_status === 'APPROVED' || upload.template_status === 'REJECTED'
            return (
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
            )
          }
        } satisfies ColumnDef<GmfUploadOut>]
      : [])
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
        description="Monitor detected GMF files and their generation status."
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
          />
        )}
      </div>
    </div>
  )
}
