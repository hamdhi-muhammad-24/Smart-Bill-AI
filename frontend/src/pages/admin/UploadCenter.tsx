import { useState, useRef, useSyncExternalStore } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Upload, File, Archive, X, Trash2, CheckCircle2, Loader2, AlertTriangle, Clock, Timer, Calendar, FolderCheck } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { clearCompletedUploadJobs, getUploadJobsSnapshot, startUploadJob, subscribeUploadJobs, type UploadJob } from '../../lib/uploadQueue'

function formatDateTime(value: string | null): string {
  if (!value) return '-'
  return new Date(value).toLocaleString([], {
    dateStyle: 'short',
    timeStyle: 'medium',
  })
}

function formatDuration(startedAt: string, finishedAt: string | null): string {
  if (!startedAt) return '-'
  const start = new Date(startedAt).getTime()
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now()
  const diffMs = Math.max(0, end - start)

  if (diffMs < 1000) {
    return `${diffMs} ms`
  }
  const seconds = (diffMs / 1000).toFixed(1)
  if (Number(seconds) < 60) {
    return `${seconds}s`
  }
  const mins = Math.floor(diffMs / 60000)
  const remSecs = Math.round((diffMs % 60000) / 1000)
  return `${mins}m ${remSecs}s`
}

function UploadJobBadge({ job }: { job: UploadJob }) {
  if (job.status === 'uploading') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200/60 bg-amber-50 px-2.5 py-0.5 text-xs font-bold text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300">
        <Loader2 size={12} className="animate-spin" />
        Uploading
      </span>
    )
  }
  if (job.status === 'completed') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200/60 bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-300">
        <CheckCircle2 size={12} />
        Completed
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-red-200/60 bg-red-50 px-2.5 py-0.5 text-xs font-bold text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300">
      <AlertTriangle size={12} />
      Failed
    </span>
  )
}

export default function UploadCenter() {
  const queryClient = useQueryClient()
  const [folderType, setFolderType] = useState<string>('Cycle')
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState<boolean>(false)
  const [success, setSuccess] = useState<boolean>(false)
  const uploadJobs = useSyncExternalStore(subscribeUploadJobs, getUploadJobsSnapshot, getUploadJobsSnapshot)
  
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(true)
  }

  const handleDragLeave = () => {
    setDragging(false)
  }

  const isValidGmfFile = (file: File): boolean => {
    const name = file.name
    const lastDot = name.lastIndexOf('.')
    if (lastDot === -1) return true // no extension is valid GMF
    const ext = name.substring(lastDot).toLowerCase()
    const extClean = ext.startsWith('.') ? ext.substring(1) : ext
    const isNumeric = /^\d+$/.test(extClean)
    return ext === '.zip' || ext === '.gmf' || ext === '.xlsx' || ext === '.xls' || ext === '.csv' || isNumeric
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files) {
      const droppedFiles = Array.from(e.dataTransfer.files)
      const valid = droppedFiles.filter(isValidGmfFile)
      if (valid.length !== droppedFiles.length) {
        toast.error("Invalid file format. Please upload valid GMF formats (no extension, numeric suffixes like .1, .6, or .gmf, or .zip).")
      }
      if (valid.length > 0) {
        setFiles(prev => [...prev, ...valid])
        setSuccess(false)
      }
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files)
      const valid = selectedFiles.filter(isValidGmfFile)
      if (valid.length !== selectedFiles.length) {
        toast.error("Invalid file format. Please upload valid GMF formats (no extension, numeric suffixes like .1, .6, or .gmf, or .zip).")
      }
      if (valid.length > 0) {
        setFiles(prev => [...prev, ...valid])
        setSuccess(false)
      }
    }
  }

  const removeFile = (idx: number) => {
    setFiles(prev => prev.filter((_, i) => i !== idx))
  }

  const clearAll = () => {
    setFiles([])
    setSuccess(false)
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error("Please add files to upload first.")
      return
    }

    const total = files.length
    const selectedFiles = files

    const { done } = startUploadJob(selectedFiles, folderType)
    toast.success(`Upload started for ${total} file(s). You can safely open another tab.`)
    setFiles([])
    setSuccess(true)

    done.then((job) => {
      queryClient.invalidateQueries({ queryKey: ['billing-uploads'] })
      if (job.status === 'completed') {
        toast.success(`Uploaded ${job.uploadedCount} file(s) in ${formatDuration(job.startedAt, job.finishedAt)}.`)
      } else {
        toast.error(job.message || `Upload failed for ${job.failedCount} file(s).`)
      }
    })
  }

  return (
    <div className="space-y-6">
      <PageHeader 
        title="Upload Center" 
        description="Upload GMF folders, ZIP files, or GMF files without size limitations." 
      />

      <Card className="glass-card shadow-lg">
        <CardContent className="space-y-6 p-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center justify-between">
            <div className="flex flex-col gap-1">
              <span className="text-sm font-semibold">Select Destination Folder / Cycle</span>
              <span className="text-xs text-muted-foreground">Select where these uploads will be archived</span>
            </div>
            
            <select
              value={folderType}
              onChange={(e) => setFolderType(e.target.value)}
              className="w-full sm:w-64 rounded-md border-none bg-gradient-to-r from-slate-900 via-blue-900 to-indigo-800 text-white dark:from-slate-100 dark:via-blue-50 dark:to-indigo-200 dark:text-slate-900 font-extrabold px-4 py-2.5 text-sm shadow-[0_4px_12px_rgba(0,0,0,0.15)] hover:scale-[1.01] transition-all cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 text-center"
            >
              <option value="Cycle" className="bg-background text-foreground font-bold">Cycle (auto-detect)</option>
              <option value="Test_GMFs" className="bg-background text-foreground font-bold">Test GMFs</option>
              <option value="LOD" className="bg-background text-foreground font-bold">LOD</option>
              <option value="VAT_Confirmation" className="bg-background text-foreground font-bold">VAT Confirmation</option>
              <option value="Final_Notice" className="bg-background text-foreground font-bold">Final Notice</option>
              <option value="Customer_Letter" className="bg-background text-foreground font-bold">Customer Migration Letter</option>
            </select>
          </div>

          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              "flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-12 cursor-pointer transition-all min-h-64 shadow-[inset_0_2px_4px_rgba(0,0,0,0.02)]",
              dragging 
                ? "border-primary bg-primary/5 scale-[1.01] shadow-md" 
                : "border-border/60 bg-gradient-to-b from-card to-slate-50/10 dark:to-slate-900/5 hover:border-primary/50 hover:bg-muted/40"
            )}
          >
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleFileSelect} 
              multiple 
              className="hidden" 
            />
            <div className="flex size-16 items-center justify-center rounded-full bg-primary/10 text-primary mb-4 shadow-sm">
              <Upload size={32} />
            </div>
            <span className="text-lg font-bold bg-gradient-to-r from-slate-900 via-blue-900 to-indigo-700 dark:from-slate-100 dark:via-blue-100 dark:to-indigo-300 bg-clip-text text-transparent">Drag & Drop files here</span>
            <span className="text-sm text-muted-foreground mt-2 text-center">
              Supports GMF files (no extension, .1, .6, .gmf), Excel spreadsheets (.xlsx, .xls), CSV files (.csv), or ZIP archives.<br/>
              Or click to browse from your device.
            </span>
          </div>

          {files.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b pb-2">
                <span className="text-sm font-semibold">Queue ({files.length} items)</span>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={clearAll} 
                  className="text-muted-foreground hover:text-destructive flex items-center gap-1.5"
                >
                  <Trash2 size={14} />
                  Clear All
                </Button>
              </div>

              <div className="max-h-64 overflow-y-auto divide-y">
                {files.length > 100 ? (
                  <div className="py-4 text-center text-sm text-muted-foreground">
                    {files.length} files selected. Ready for chunked upload.
                  </div>
                ) : (
                  files.map((file, idx) => {
                    const isZip = file.name.endsWith('.zip')
                    return (
                      <div key={idx} className="flex items-center justify-between py-2 text-sm">
                        <div className="flex items-center gap-2.5 truncate">
                          {isZip ? (
                            <Archive size={16} className="text-amber-500 shrink-0" />
                          ) : (
                            <File size={16} className="text-blue-500 shrink-0" />
                          )}
                          <span className="font-medium truncate">{file.name}</span>
                          <span className="text-xs text-muted-foreground font-mono">
                            ({(file.size / 1024).toFixed(1)} KB)
                          </span>
                        </div>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          onClick={() => removeFile(idx)} 
                          className="rounded-full size-8 text-muted-foreground hover:text-destructive"
                        >
                          <X size={14} />
                        </Button>
                      </div>
                    )
                  })
                )}
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t">
                <Button 
                  variant="outline" 
                  onClick={clearAll}
                >
                  Cancel
                </Button>
                <Button 
                  onClick={handleUpload}
                  className="flex items-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 font-extrabold shadow-[0_4px_12px_rgba(16,185,129,0.25)] text-white hover:scale-[1.01] border-transparent transition-all"
                >
                  <Upload size={16} />
                  Upload Now
                </Button>
              </div>
            </div>
          )}

          {success && (
            <div className="flex items-center gap-3 rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-4 text-emerald-800 dark:text-emerald-300">
              <CheckCircle2 className="size-5 shrink-0 text-emerald-500" />
              <div className="flex flex-col">
                <span className="font-semibold text-sm">Batch upload successfully queued</span>
                <span className="text-xs text-muted-foreground mt-0.5">
                  Upload continues in the background and will reflect in the history below shortly.
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="glass-card shadow-lg">
        <CardContent className="space-y-4 p-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-base font-extrabold">Upload Sessions</h3>
              <p className="text-xs text-muted-foreground">Current and recent Upload Center transfers with live timing and status breakdown.</p>
            </div>
            {uploadJobs.some(job => job.status !== 'uploading') && (
              <Button variant="outline" size="sm" onClick={clearCompletedUploadJobs} className="w-fit">
                Clear Completed
              </Button>
            )}
          </div>

          {uploadJobs.length === 0 ? (
            <div className="rounded-lg border border-dashed p-5 text-center text-sm text-muted-foreground">
              No Upload Center sessions yet.
            </div>
          ) : (
            <div className="max-h-96 overflow-y-auto space-y-3 pr-1">
              {uploadJobs.map(job => {
                const doneCount = job.uploadedCount + job.failedCount
                const progress = Math.round((doneCount / job.fileCount) * 100)
                return (
                  <div key={job.id} className="rounded-xl border bg-card/60 p-4 space-y-3 shadow-xs hover:border-border transition-colors">
                    {/* Header: Title & Status */}
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className="size-9 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shrink-0 font-bold border border-indigo-200/50 dark:border-indigo-800/30">
                          <FolderCheck size={18} />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-extrabold text-foreground">
                              {job.fileCount} file(s) to {job.folderType.replace('_', ' ')}
                            </span>
                          </div>
                          <span className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                            <Calendar size={12} className="text-muted-foreground/70" />
                            {formatDateTime(job.startedAt)}
                          </span>
                        </div>
                      </div>
                      <UploadJobBadge job={job} />
                    </div>

                    {/* Progress Bar */}
                    <div className="space-y-1">
                      <div className="h-2 overflow-hidden rounded-full bg-muted">
                        <div 
                          className={cn(
                            "h-full rounded-full transition-all duration-300",
                            job.status === 'completed' ? "bg-emerald-500" : job.status === 'failed' ? "bg-red-500" : "bg-amber-500"
                          )} 
                          style={{ width: `${progress}%` }} 
                        />
                      </div>
                      <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
                        <span>{job.uploadedCount} uploaded / {job.failedCount} failed</span>
                        <span className="font-bold text-foreground">{progress}%</span>
                      </div>
                    </div>

                    {/* Timings & Summary Grid (Start Time, End Time, Total Time Taken) */}
                    <div className="grid grid-cols-3 gap-2 pt-1 border-t border-border/40 text-xs">
                      {/* Start Time */}
                      <div className="rounded-lg bg-muted/30 p-2 border border-border/30">
                        <div className="flex items-center gap-1 text-muted-foreground font-semibold text-[11px]">
                          <Clock size={12} className="text-blue-500 shrink-0" />
                          <span>Start Time</span>
                        </div>
                        <div className="font-mono font-bold text-foreground text-xs mt-0.5 truncate" title={job.startedAt}>
                          {new Date(job.startedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </div>
                      </div>

                      {/* End Time */}
                      <div className="rounded-lg bg-muted/30 p-2 border border-border/30">
                        <div className="flex items-center gap-1 text-muted-foreground font-semibold text-[11px]">
                          <Clock size={12} className={job.finishedAt ? "text-emerald-500 shrink-0" : "text-amber-500 shrink-0"} />
                          <span>End Time</span>
                        </div>
                        <div className="font-mono font-bold text-foreground text-xs mt-0.5 truncate" title={job.finishedAt || 'In progress'}>
                          {job.finishedAt ? (
                            new Date(job.finishedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                          ) : (
                            <span className="text-amber-600 dark:text-amber-400 italic text-[11px] flex items-center gap-1 font-sans font-medium">
                              <Loader2 size={10} className="animate-spin shrink-0" /> In progress
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Total Time Taken (Duration) */}
                      <div className="rounded-lg bg-indigo-50/50 dark:bg-indigo-950/20 p-2 border border-indigo-200/40 dark:border-indigo-800/30">
                        <div className="flex items-center gap-1 text-indigo-700 dark:text-indigo-300 font-semibold text-[11px]">
                          <Timer size={12} className="text-indigo-600 dark:text-indigo-400 shrink-0" />
                          <span>Total Time</span>
                        </div>
                        <div className="font-mono font-extrabold text-indigo-900 dark:text-indigo-200 text-xs mt-0.5">
                          {formatDuration(job.startedAt, job.finishedAt)}
                        </div>
                      </div>
                    </div>

                    {job.message && job.status === 'failed' && (
                      <div className="rounded-md bg-red-50 px-2.5 py-1.5 text-xs font-semibold text-red-700 dark:bg-red-950/20 dark:text-red-300 border border-red-200/60">
                        {job.message}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

