import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Eye, CheckCircle2, XCircle, Loader2, Sparkles, FileSearch, Maximize2, Download, X, AlertCircle, History, Trash2, Mail, Check, RefreshCw } from 'lucide-react'
import { getUploads, previewInvoice, fetchPreviewPdfBlobUrl, updateTemplateStatus, getSettings, updateSettings, getTemplateHistory, deleteTemplateHistoryLog, deleteAllTemplateHistoryLogs, getEnvelopeHistory, deleteEnvelopeHistoryLog, deleteAllEnvelopeHistoryLogs } from '../../lib/api'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { toast } from 'sonner'
import { cn, formatTemplateDisplayName } from '@/lib/utils'
import { motion, AnimatePresence } from 'framer-motion'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"

import { BASE_URL } from '@/lib/api'

const API_BASE = BASE_URL

async function fetchSubmittedEnvelopes() {
  const res = await fetch(`${API_BASE}/api/envelope/artworks?status=SUBMITTED`)
  if (!res.ok) return []
  return res.json()
}

export default function InvoicePreview() {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [selectedMode, setSelectedMode] = useState<'auto' | 'manual' | null>(null)
  const [activeSection, setActiveSection] = useState<'gmf' | 'envelopes'>('gmf')
  const [showHistory, setShowHistory] = useState(false)
  const [historyTab, setHistoryTab] = useState<'gmf' | 'envelope'>('gmf')
  const [rejectTemplateId, setRejectTemplateId] = useState<string | null>(null)
  const [rejectReason, setRejectReason] = useState<string>('')
  const [rejectEnvelopeId, setRejectEnvelopeId] = useState<number | null>(null)
  const [rejectEnvelopeReason, setRejectEnvelopeReason] = useState<string>('')
  const abortControllerRef = useRef<AbortController | null>(null)

  const { data: submittedEnvelopes, isLoading: loadingEnvelopes, refetch: refetchEnvelopes } = useQuery({
    queryKey: ['submittedEnvelopes'],
    queryFn: fetchSubmittedEnvelopes,
    refetchInterval: 5000,
  })

  const approveEnvelopeMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`${API_BASE}/api/envelope/artworks/${id}/approve`, { method: 'POST' })
      if (!res.ok) throw new Error('Failed to approve envelope artwork')
      return res.json()
    },
    onSuccess: () => {
      toast.success('Generated envelope campaign approved successfully!')
      queryClient.invalidateQueries({ queryKey: ['submittedEnvelopes'] })
      queryClient.invalidateQueries({ queryKey: ['envelopeHistory'] })
    },
  })

  const rejectEnvelopeMutation = useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason: string }) => {
      const res = await fetch(`${API_BASE}/api/envelope/artworks/${id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
      })
      if (!res.ok) throw new Error('Failed to reject envelope artwork')
      return res.json()
    },
    onSuccess: () => {
      toast.success('Generated envelope artwork rejected.')
      setRejectEnvelopeId(null)
      setRejectEnvelopeReason('')
      queryClient.invalidateQueries({ queryKey: ['submittedEnvelopes'] })
      queryClient.invalidateQueries({ queryKey: ['envelopeHistory'] })
    },
  })

  const { data: uploads, isLoading } = useQuery({
    queryKey: ['billing-uploads'],
    queryFn: () => getUploads(undefined, undefined),
    refetchInterval: 5000,
  })

  const { data: settingsData } = useQuery({
    queryKey: ['billing-settings'],
    queryFn: getSettings,
  })

  useEffect(() => {
    if (settingsData?.billing_mode) {
      setSelectedMode(settingsData.billing_mode as 'auto' | 'manual')
    }
  }, [settingsData])

  useEffect(() => {
    return () => {
      if (previewPdfUrl?.startsWith('blob:')) {
        URL.revokeObjectURL(previewPdfUrl)
      }
    }
  }, [previewPdfUrl])

  const { data: historyData } = useQuery({
    queryKey: ['template-history'],
    queryFn: getTemplateHistory,
    refetchInterval: 5000,
  })

  const testGmfs = (uploads || []).filter(u => u.folder_type === 'Test_GMFs')
  const selectedGmf = testGmfs.find(u => u.id === selectedId)

  const settingsMutation = useMutation({
    mutationFn: (mode: string) => updateSettings({ billing_mode: mode }),
    onSuccess: (resData) => {
      setSelectedMode(resData.billing_mode as 'auto' | 'manual')
      queryClient.invalidateQueries({ queryKey: ['billing-settings'] })
      toast.success(`Validation mode switched to ${resData.billing_mode.toUpperCase()}`)
    },
    onError: (err: any) => toast.error(err.detail || 'Failed to update billing mode')
  })

  const previewMutation = useMutation({
    mutationFn: async (id: number) => {
      const controller = new AbortController()
      abortControllerRef.current = controller
      const resData = await previewInvoice(id, controller.signal)
      const previewBlobUrl = await fetchPreviewPdfBlobUrl(resData.pdf_url, controller.signal)
      return { ...resData, pdf_url: previewBlobUrl }
    },
    onSuccess: (resData) => {
      toast.success(resData.message)
      if (previewPdfUrl?.startsWith('blob:')) {
        URL.revokeObjectURL(previewPdfUrl)
      }
      setPreviewPdfUrl(resData.pdf_url)
      queryClient.invalidateQueries({ queryKey: ['billing-uploads'] })
    },
    onError: (err: any) => {
      if (err.name === 'AbortError') {
        // Ignored since cancel button handles notification
        return
      }
      toast.error(err.detail || 'Failed to generate preview')
    }
  })

  const approveMutation = useMutation({
    mutationFn: (templateId: string) => updateTemplateStatus(templateId, 'APPROVED'),
    onSuccess: () => {
      toast.success(`Template APPROVED successfully`)
      queryClient.invalidateQueries({ queryKey: ['billing-templates'] })
      queryClient.invalidateQueries({ queryKey: ['billing-uploads'] })
      queryClient.invalidateQueries({ queryKey: ['billing-pending-batches'] })
      queryClient.invalidateQueries({ queryKey: ['template-history'] })
    },
    onError: (err: any) => toast.error(err.detail || 'Failed to approve template')
  })

  const rejectMutation = useMutation({
    mutationFn: ({ templateId, reason }: { templateId: string, reason: string }) =>
      updateTemplateStatus(templateId, 'REJECTED', reason),
    onSuccess: () => {
      toast.success(`Template REJECTED successfully`)
      setRejectTemplateId(null)
      setRejectReason('')
      queryClient.invalidateQueries({ queryKey: ['billing-templates'] })
      queryClient.invalidateQueries({ queryKey: ['billing-uploads'] })
      queryClient.invalidateQueries({ queryKey: ['billing-pending-batches'] })
      queryClient.invalidateQueries({ queryKey: ['template-history'] })
    },
    onError: (err: any) => toast.error(err.detail || 'Failed to reject template')
  })

  const deleteHistoryMutation = useMutation({
    mutationFn: (historyId: number) => deleteTemplateHistoryLog(historyId),
    onSuccess: () => {
      toast.success('Template history log deleted.')
      queryClient.invalidateQueries({ queryKey: ['template-history'] })
    },
    onError: (err: any) => toast.error(err.detail || 'Failed to delete history log')
  })

  const deleteAllHistoryMutation = useMutation({
    mutationFn: () => deleteAllTemplateHistoryLogs(),
    onSuccess: () => {
      toast.success('All template history logs deleted.')
      queryClient.invalidateQueries({ queryKey: ['template-history'] })
    },
    onError: (err: any) => toast.error(err.detail || 'Failed to delete history logs')
  })

  const { data: envelopeHistoryData } = useQuery({
    queryKey: ['envelopeHistory'],
    queryFn: getEnvelopeHistory,
    enabled: showHistory,
  })

  const deleteEnvelopeHistoryMutation = useMutation({
    mutationFn: (historyId: number) => deleteEnvelopeHistoryLog(historyId),
    onSuccess: () => {
      toast.success('Envelope history log deleted.')
      queryClient.invalidateQueries({ queryKey: ['envelopeHistory'] })
    },
    onError: (err: any) => toast.error(err.detail || 'Failed to delete history log')
  })

  const deleteAllEnvelopeHistoryMutation = useMutation({
    mutationFn: () => deleteAllEnvelopeHistoryLogs(),
    onSuccess: () => {
      toast.success('All envelope history logs deleted.')
      queryClient.invalidateQueries({ queryKey: ['envelopeHistory'] })
    },
    onError: (err: any) => toast.error(err.detail || 'Failed to delete history logs')
  })

  const checkMode = (action: () => void) => {
    if (selectedMode === null) {
      toast.error("First select the mode", {
        style: {
          backgroundColor: '#ef4444',
          color: '#ffffff',
          fontWeight: 'bold',
          border: '1px solid #dc2626'
        }
      })
      return
    }
    action()
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between shrink-0">
        <PageHeader
          title="Invoice Preview"
          description="Review test GMFs, generate preview invoices, and approve them for batch generation."
        />
        <Button
          variant="outline"
          onClick={() => setShowHistory(true)}
          className="flex items-center justify-center gap-2 font-bold shadow-sm h-10 border-border hover:bg-muted shrink-0"
        >
          <History size={16} className="text-muted-foreground" />
          View Logs
        </Button>
      </div>

      {/* Section Tabs */}
      <div className="flex border-b border-border gap-6 shrink-0">
        <button
          type="button"
          onClick={() => setActiveSection('gmf')}
          className={cn(
            "pb-3 text-sm font-bold border-b-2 transition-colors flex items-center gap-2",
            activeSection === 'gmf'
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
              : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
          )}
        >
          <FileText size={16} />
          Invoice GMF Previews
        </button>

        <button
          type="button"
          onClick={() => setActiveSection('envelopes')}
          className={cn(
            "pb-3 text-sm font-bold border-b-2 transition-colors flex items-center gap-2",
            activeSection === 'envelopes'
              ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
              : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
          )}
        >
          <Mail size={16} />
          Generated Envelope Approvals
          {submittedEnvelopes && submittedEnvelopes.length > 0 && (
            <Badge className="bg-indigo-600 text-white text-[10px] px-1.5 py-0.2">
              {submittedEnvelopes.length}
            </Badge>
          )}
        </button>
      </div>

      {activeSection === 'envelopes' ? (
        /* Generated Envelope Approvals Workspace */
        <div className="space-y-4 flex-1">
          <div className="flex justify-between items-center bg-card p-4 rounded-xl border border-border shadow-sm">
            <div>
              <h3 className="font-bold text-base text-foreground">Generated Envelope Submissions</h3>
              <p className="text-xs text-muted-foreground">Review promotional artwork campaign envelopes submitted by envelope handlers for Admin approval.</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => refetchEnvelopes()} className="gap-2 text-xs font-semibold">
              <RefreshCw size={14} className={loadingEnvelopes ? "animate-spin text-indigo-500" : ""} />
              Refresh Queue
            </Button>
          </div>

          {loadingEnvelopes ? (
            <div className="flex justify-center p-12">
              <Loader2 className="animate-spin text-muted-foreground size-8" />
            </div>
          ) : submittedEnvelopes && submittedEnvelopes.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {submittedEnvelopes.map((env: any) => {
                const pdfViewUrl = `${API_BASE}/api/envelope/artworks/${env.id}/view-pdf`
                const pngPreviewUrl = `${API_BASE}/api/envelope/artworks/${env.id}/preview`

                return (
                  <Card key={env.id} className="rounded-2xl overflow-hidden border border-border shadow-sm flex flex-col justify-between bg-card">
                    <div
                      className="h-56 bg-slate-950 relative cursor-pointer flex items-center justify-center p-3 border-b border-slate-800 group"
                      onClick={() => {
                        setPreviewPdfUrl(pdfViewUrl)
                        setIsFullscreen(true)
                      }}
                    >
                      <img src={pngPreviewUrl} alt={env.campaign_name} className="max-h-full max-w-full object-contain rounded-lg" />
                      <div className="absolute top-3 left-3">
                        <Badge className="bg-amber-600 text-white text-xs font-bold">SUBMITTED</Badge>
                      </div>
                      <div className="absolute top-3 right-3">
                        <Badge variant="outline" className="bg-slate-900 text-indigo-300 border-slate-700 text-xs font-mono font-bold">
                          {env.envelope_type}
                        </Badge>
                      </div>

                      <div className="absolute inset-0 bg-slate-950/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center z-20">
                        <span className="bg-white text-slate-900 px-3.5 py-2 rounded-full text-xs font-bold flex items-center gap-2 shadow-lg">
                          <Maximize2 size={14} className="text-indigo-600" /> Inspect Composite PDF
                        </span>
                      </div>
                    </div>

                    <div className="p-4 space-y-3">
                      <div>
                        <h4 className="font-bold text-sm text-foreground truncate">{env.campaign_name}</h4>
                        <p className="text-xs text-muted-foreground font-mono">{env.display_name} • {env.image_size}</p>
                      </div>

                      <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border">
                        <Button
                          size="sm"
                          className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs gap-1.5 h-8 shadow-xs"
                          onClick={() => approveEnvelopeMutation.mutate(env.id)}
                          disabled={approveEnvelopeMutation.isPending}
                        >
                          <Check size={14} /> Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          className="font-semibold text-xs gap-1.5 h-8"
                          onClick={() => {
                            setRejectEnvelopeId(env.id)
                            setRejectEnvelopeReason('')
                          }}
                          disabled={rejectEnvelopeMutation.isPending}
                        >
                          <XCircle size={14} /> Reject
                        </Button>
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          ) : (
            <div className="text-center p-12 border border-dashed rounded-2xl text-muted-foreground bg-muted/20">
              <Mail size={40} className="mx-auto mb-3 opacity-30 text-indigo-500" />
              <p className="font-medium text-sm">No envelope campaign submissions currently awaiting admin approval.</p>
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Mode Selector */}
      <div className="flex flex-col gap-3 p-4 rounded-xl border bg-card shadow-sm shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-sm font-bold">Template Validation Mode</span>
            <span className="text-xs text-muted-foreground">Select a mode before executing preview or approval actions.</span>
          </div>
          {selectedMode === null && (
            <span className="text-xs font-bold text-red-500 flex items-center gap-1 animate-pulse bg-red-50 dark:bg-red-950/30 px-2 py-1 rounded-md border border-red-200">
              <AlertCircle size={14} /> Mode selection required!
            </span>
          )}
        </div>
        <div className="flex gap-3">
          <Button
            type="button"
            className={cn(
              "flex-1 py-6 text-base font-bold shadow-sm transition-all border",
              selectedMode === 'auto'
                ? "bg-gradient-to-r from-slate-900 via-blue-900 to-indigo-800 hover:from-black hover:via-blue-950 hover:to-indigo-900 dark:from-slate-100 dark:via-blue-100 dark:to-indigo-300 dark:hover:from-white dark:hover:via-blue-50 dark:hover:to-indigo-200 text-white dark:text-slate-900 scale-[1.01] shadow-[0_8px_20px_rgba(30,58,138,0.3)] dark:shadow-[0_4px_15px_rgba(199,210,254,0.15)] font-extrabold border-transparent"
                : "bg-card border-border hover:bg-muted/50 hover:border-primary/20 text-muted-foreground hover:text-foreground font-semibold"
            )}
            onClick={() => settingsMutation.mutate('auto')}
            disabled={settingsMutation.isPending}
          >
            Auto Mode
            <span className="ml-2 text-xs font-normal opacity-85 block sm:inline">(Automated generation on approval)</span>
          </Button>
          <Button
            type="button"
            className={cn(
              "flex-1 py-6 text-base font-bold shadow-sm transition-all border",
              selectedMode === 'manual'
                ? "bg-gradient-to-r from-slate-900 via-blue-900 to-indigo-800 hover:from-black hover:via-blue-950 hover:to-indigo-900 dark:from-slate-100 dark:via-blue-100 dark:to-indigo-300 dark:hover:from-white dark:hover:via-blue-50 dark:hover:to-indigo-200 text-white dark:text-slate-900 scale-[1.01] shadow-[0_8px_20px_rgba(30,58,138,0.3)] dark:shadow-[0_4px_15px_rgba(199,210,254,0.15)] font-extrabold border-transparent"
                : "bg-card border-border hover:bg-muted/50 hover:border-primary/20 text-muted-foreground hover:text-foreground font-semibold"
            )}
            onClick={() => settingsMutation.mutate('manual')}
            disabled={settingsMutation.isPending}
          >
            Manual Mode
            <span className="ml-2 text-xs font-normal opacity-85 block sm:inline">(Manual run inside Generation Hub)</span>
          </Button>
        </div>
      </div>

      {/* Main Workspace (Responsive Height) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 flex-1 min-h-[400px]">

        {/* Left Panel: List of Test GMFs */}
        <div className="lg:col-span-2 rounded-xl border bg-card shadow-sm p-4 flex flex-col h-full max-h-[calc(100vh-270px)]">
          <div className="flex items-center justify-between border-b pb-3 shrink-0 mb-3">
            <h3 className="font-bold text-lg flex items-center gap-2 text-foreground">
              <FileText size={18} className="text-primary" />
              Test GMF Files
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto pr-1 custom-scrollbar">
            {isLoading ? (
              <div className="h-32 flex items-center justify-center">
                <Loader2 className="animate-spin text-muted-foreground" />
              </div>
            ) : testGmfs.length === 0 ? (
              <div className="text-sm text-muted-foreground p-6 text-center flex flex-col items-center justify-center border border-dashed rounded-lg bg-muted/20 h-full">
                <FileSearch size={28} className="mb-2 opacity-20" />
                No Test GMFs found.
              </div>
            ) : (
              <div className="flex flex-col">
                {testGmfs.map(gmf => {
                  const isSelected = gmf.id === selectedId
                  return (
                    <motion.div
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      key={gmf.id}
                      onClick={() => {
                        setSelectedId(gmf.id)
                        setPreviewPdfUrl(null)
                      }}
                      className={cn(
                        "flex flex-col p-3 rounded-lg cursor-pointer border transition-all duration-200 relative pl-4 mb-2 select-none",
                        isSelected
                          ? "border-primary/50 bg-primary/5 shadow-sm ring-1 ring-primary/20"
                          : "border-border/60 hover:bg-muted/60 hover:border-border"
                      )}
                    >
                      <div className={cn("absolute left-0 top-0 bottom-0 w-1 transition-all", isSelected ? "bg-primary" : "bg-transparent")} />

                      <div className="flex flex-col gap-2">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2 overflow-hidden w-full">
                            <FileText size={16} className={cn("shrink-0", isSelected ? "text-primary" : "text-muted-foreground")} />
                            <span className={cn("font-bold text-[14px] truncate leading-tight text-foreground", isSelected && "text-primary")} title={gmf.filename}>
                              {gmf.filename}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center justify-between gap-2">
                          <span className={cn(
                            "text-[10px] font-bold px-2 py-0.5 rounded-md transition-colors uppercase border tracking-wider shrink-0",
                            gmf.status === 'PENDING_APPROVAL' ? "bg-cyan-50 text-cyan-600 border-cyan-200/50 dark:bg-cyan-950/30" :
                              gmf.status === 'APPROVED' ? "bg-emerald-50 text-emerald-600 border-emerald-200/50 dark:bg-emerald-950/30" :
                                gmf.status === 'REJECTED' ? "bg-red-50 text-red-600 border-red-200/50 dark:bg-red-950/30" :
                                  "bg-muted text-muted-foreground border-border"
                          )}>
                            {gmf.status === 'PENDING_APPROVAL' ? 'Pending' : gmf.status}
                          </span>

                          <span className="font-bold bg-amber-100 dark:bg-amber-900/40 text-amber-900 dark:text-amber-300 border border-amber-300 dark:border-amber-700/60 px-2 py-0.5 rounded text-[11px] leading-tight break-all shadow-sm">
                            {formatTemplateDisplayName(gmf.template_detected)}
                          </span>
                        </div>

                        {gmf.rejection_reason && (
                          <div className="text-[11px] text-red-500 font-semibold bg-red-50/50 dark:bg-red-950/10 px-2 py-1 rounded truncate" title={gmf.rejection_reason}>
                            <span className="font-bold">Reason:</span> {gmf.rejection_reason}
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )
                })}
              </div>
            )}
          </div>

        </div>

        {/* Right Panel: PDF Viewer and Action Area */}
        <div className="lg:col-span-3 rounded-xl border bg-card shadow-sm overflow-hidden flex flex-col h-full max-h-[calc(100vh-270px)] relative bg-slate-50/50 dark:bg-slate-900/10">
          <AnimatePresence mode="wait">
            {!selectedGmf ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8"
              >
                <div className="bg-background p-6 rounded-full shadow-sm border mb-4">
                  <Eye size={32} className="text-slate-300 dark:text-slate-600" />
                </div>
                <h3 className="text-xl font-bold text-foreground mb-2">No Template Selected</h3>
                <p className="text-sm text-center max-w-md">Select a Test GMF from the sidebar to begin review, render a preview invoice, and validate the template layout.</p>
              </motion.div>
            ) : (
              <motion.div
                key="content"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex-1 flex flex-col h-full min-h-0"
              >
                {/* Header Actions */}
                <div className="p-4 border-b bg-background flex justify-between items-center shadow-sm z-10 shrink-0">
                  <div className="flex flex-col">
                    <span className="font-bold text-lg text-foreground truncate max-w-[280px]" title={selectedGmf.filename}>
                      {selectedGmf.filename}
                    </span>
                    <span className="text-sm text-muted-foreground font-medium flex items-center gap-1.5 mt-0.5">
                      Detected Template: <span className="text-primary font-bold bg-primary/10 px-2 py-0.5 rounded border border-primary/20">{formatTemplateDisplayName(selectedGmf.template_detected)}</span>
                    </span>
                  </div>

                  {selectedGmf.status === 'PENDING_APPROVAL' && previewPdfUrl && selectedGmf.template_detected && (
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/20 border-red-200 font-bold"
                        onClick={() => checkMode(() => setRejectTemplateId(selectedGmf.template_detected!))}
                        disabled={rejectMutation.isPending}
                      >
                        <XCircle size={16} className="mr-2" /> Reject Template
                      </Button>
                      <Button
                        className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white shadow-md font-bold border-none"
                        onClick={() => checkMode(() => approveMutation.mutate(selectedGmf.template_detected!))}
                        disabled={approveMutation.isPending}
                      >
                        <CheckCircle2 size={16} className="mr-2" /> Approve Template
                      </Button>
                    </div>
                  )}
                  {selectedGmf.status === 'APPROVED' && (
                    <div className="flex gap-2">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 dark:bg-emerald-950/30 px-3 py-1.5 text-sm font-bold text-emerald-700 dark:text-emerald-400 border border-emerald-200">
                        <CheckCircle2 size={18} className="text-emerald-600 dark:text-emerald-500" />
                        Template Approved
                      </span>
                    </div>
                  )}
                  {selectedGmf.status === 'REJECTED' && (
                    <div className="flex gap-2">
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 dark:bg-red-950/30 px-3 py-1.5 text-sm font-bold text-red-700 dark:text-red-400 border border-red-200">
                        <XCircle size={18} className="text-red-600 dark:text-red-500" />
                        Template Rejected
                      </span>
                    </div>
                  )}
                </div>

                {/* Preview Content Area */}
                <div className="flex-1 flex items-center justify-center p-4 sm:p-6 bg-slate-100/30 dark:bg-slate-900/40 min-h-0 overflow-hidden relative">
                  {previewMutation.isPending ? (
                    <motion.div
                      initial={{ scale: 0.9, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      className="flex flex-col items-center p-8 bg-background rounded-2xl shadow-lg border"
                    >
                      <Loader2 size={40} className="animate-spin text-primary mb-4" />
                      <h3 className="text-lg font-bold mb-2">Rendering Preview...</h3>
                      <p className="text-sm text-muted-foreground text-center max-w-[280px] mb-6">
                        The AI billing engine is parsing the GMF data and mapping it to the layout. This may take a moment.
                      </p>
                      <Button
                        variant="outline"
                        className="text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 dark:bg-red-950/20 dark:hover:bg-red-950/40 border-red-200 hover:border-red-300 font-extrabold px-6 h-10 transition-all shadow-sm flex items-center gap-2"
                        onClick={() => {
                          if (abortControllerRef.current) {
                            abortControllerRef.current.abort()
                          }
                          previewMutation.reset()
                          toast.error("Preview generation cancelled.")
                        }}
                      >
                        <X size={16} />
                        Cancel Generation
                      </Button>
                    </motion.div>
                  ) : previewPdfUrl ? (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="w-full h-full relative flex flex-col"
                    >
                      <div className="absolute top-2 right-4 flex gap-2 z-10">
                        <Button variant="secondary" size="sm" className="h-8 shadow-md font-bold bg-white/90 hover:bg-white text-slate-700 border-none backdrop-blur-sm" onClick={() => setIsFullscreen(true)}>
                          <Maximize2 size={14} className="mr-1.5" /> Maximize
                        </Button>
                        <Button variant="secondary" size="sm" className="h-8 shadow-md font-bold bg-white/90 hover:bg-white text-slate-700 border-none backdrop-blur-sm" onClick={() => window.open(previewPdfUrl, '_blank')}>
                          <Download size={14} className="mr-1.5" /> Download
                        </Button>
                      </div>
                      <iframe
                        src={`${previewPdfUrl}#toolbar=0`}
                        className="w-full h-full rounded-xl shadow-xl border border-border bg-white"
                        title="Invoice Preview"
                      />
                    </motion.div>
                  ) : (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className="flex flex-col items-center justify-center text-center p-10 max-w-md bg-background border rounded-2xl shadow-lg relative overflow-hidden"
                    >
                      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none" />
                      <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center mb-6 shadow-inner ring-1 ring-primary/20">
                        <Sparkles size={28} className="text-primary" />
                      </div>
                      <h3 className="text-2xl font-extrabold text-foreground mb-3">Ready to Render</h3>
                      <p className="text-muted-foreground mb-8 leading-relaxed">
                        Generate a high-fidelity PDF preview to verify the layout, calculations, and visual aesthetics before approving this batch for production.
                      </p>
                      <Button
                        size="lg"
                        className="w-full h-12 shadow-lg text-base font-extrabold bg-gradient-to-r from-slate-900 via-blue-900 to-indigo-800 hover:from-black hover:via-blue-950 hover:to-indigo-900 dark:from-slate-100 dark:via-blue-100 dark:to-indigo-300 dark:hover:from-white dark:hover:via-blue-50 dark:hover:to-indigo-200 text-white dark:text-slate-900 shadow-[0_8px_20px_rgba(30,58,138,0.3)] dark:shadow-[0_4px_15px_rgba(199,210,254,0.15)] border-none transition-all"
                        onClick={() => checkMode(() => previewMutation.mutate(selectedGmf.id))}
                        disabled={previewMutation.isPending}
                      >
                        <Eye size={20} className="mr-2" />
                        Generate PDF Preview
                      </Button>
                    </motion.div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      </>
      )}

      {/* Full Screen PDF Modal */}
      <AnimatePresence>
        {isFullscreen && previewPdfUrl && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 md:p-8"
            onClick={() => setIsFullscreen(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ type: "spring", bounce: 0, duration: 0.3 }}
              className="relative max-h-full max-w-5xl w-full h-[90vh] flex flex-col bg-slate-100 rounded-xl overflow-hidden shadow-2xl border border-white/10"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="absolute top-4 right-4 z-10 flex gap-2">
                <button
                  className="text-slate-600 hover:text-slate-900 bg-white/90 hover:bg-white rounded-full p-2.5 shadow-md transition-colors backdrop-blur-sm border"
                  onClick={() => setIsFullscreen(false)}
                >
                  <X size={20} />
                </button>
              </div>

              <iframe
                src={`${previewPdfUrl}#toolbar=0&navpanes=0`}
                title="Full Template Preview"
                className="w-full h-full bg-white"
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Rejection Reason Modal */}
      <AnimatePresence>
        {rejectTemplateId !== null && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
            onClick={() => setRejectTemplateId(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 10 }}
              className="relative w-full max-w-md bg-background border rounded-2xl overflow-hidden shadow-2xl p-6"
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className="text-xl font-extrabold text-foreground mb-3 flex items-center gap-2">
                <XCircle className="text-red-500" size={24} /> Reject Template
              </h3>
              <p className="text-sm text-muted-foreground mb-5 leading-relaxed">
                Please provide the reason for rejecting template <span className="font-bold text-foreground bg-muted px-1.5 py-0.5 rounded">{rejectTemplateId}</span>:
              </p>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Describe layout issues, mismatch, or errors..."
                rows={4}
                className="w-full rounded-xl border border-input bg-muted/50 px-4 py-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:border-primary mb-6 transition-all"
              />
              <div className="flex justify-end gap-3">
                <Button
                  variant="outline"
                  onClick={() => {
                    setRejectTemplateId(null)
                    setRejectReason('')
                  }}
                  className="font-bold"
                >
                  Cancel
                </Button>
                <Button
                  className="bg-red-600 hover:bg-red-700 text-white font-bold shadow-md"
                  onClick={() => rejectMutation.mutate({ templateId: rejectTemplateId, reason: rejectReason || 'No reason specified' })}
                  disabled={rejectMutation.isPending}
                >
                  Confirm Rejection
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Envelope Rejection Reason Modal */}
      <AnimatePresence>
        {rejectEnvelopeId !== null && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-card border border-border p-6 rounded-2xl shadow-2xl max-w-md w-full flex flex-col gap-4"
            >
              <div className="flex items-center gap-3 text-red-600">
                <AlertCircle size={24} />
                <h3 className="text-lg font-bold text-foreground">Reject Envelope Artwork</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                Please provide a reason for rejecting this promotional envelope artwork. The uploader will see this reason in their portal.
              </p>
              <textarea
                value={rejectEnvelopeReason}
                onChange={(e) => setRejectEnvelopeReason(e.target.value)}
                placeholder="Enter rejection reason (e.g. low image resolution, misaligned aspect ratio, incorrect promotional text)..."
                rows={4}
                className="w-full rounded-xl border border-input bg-muted/50 px-4 py-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:border-primary mb-6 transition-all"
              />
              <div className="flex justify-end gap-3">
                <Button
                  variant="outline"
                  onClick={() => {
                    setRejectEnvelopeId(null)
                    setRejectEnvelopeReason('')
                  }}
                  className="font-bold"
                >
                  Cancel
                </Button>
                <Button
                  className="bg-red-600 hover:bg-red-700 text-white font-bold shadow-md"
                  onClick={() => rejectEnvelopeMutation.mutate({ id: rejectEnvelopeId, reason: rejectEnvelopeReason || 'Rejected by admin' })}
                  disabled={rejectEnvelopeMutation.isPending}
                >
                  Confirm Rejection
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Validation Logs Drawer */}
      <Sheet open={showHistory} onOpenChange={setShowHistory}>
        <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto border-l shadow-2xl">
          <SheetHeader className="border-b pb-5">
            <div className="flex flex-col gap-3 pr-10">
              <SheetTitle className="flex items-center gap-2 text-xl font-extrabold">
                <History className="text-primary" />
                Audit Log History
              </SheetTitle>
              <SheetDescription className="text-sm">
                View separate activity log history for Test GMF templates and Envelope campaigns.
              </SheetDescription>

              {/* Log Switcher Tabs */}
              <div className="flex rounded-xl bg-muted p-1 gap-1 text-xs font-bold mt-1">
                <button
                  type="button"
                  onClick={() => setHistoryTab('gmf')}
                  className={cn(
                    "flex-1 py-1.5 rounded-lg transition-all text-center",
                    historyTab === 'gmf' ? "bg-background text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Test GMF Logs
                </button>
                <button
                  type="button"
                  onClick={() => setHistoryTab('envelope')}
                  className={cn(
                    "flex-1 py-1.5 rounded-lg transition-all text-center",
                    historyTab === 'envelope' ? "bg-background text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Envelope Logs
                </button>
              </div>

              {historyTab === 'gmf' && historyData && historyData.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (window.confirm('Are you sure you want to delete all Test GMF template history logs?')) {
                      deleteAllHistoryMutation.mutate()
                    }
                  }}
                  disabled={deleteAllHistoryMutation.isPending}
                  className="h-8 w-fit text-muted-foreground hover:text-destructive border-muted-foreground/25"
                >
                  <Trash2 size={13} className="mr-1.5" />
                  Delete All GMF Logs
                </Button>
              )}

              {historyTab === 'envelope' && envelopeHistoryData && envelopeHistoryData.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (window.confirm('Are you sure you want to delete all Envelope history logs?')) {
                      deleteAllEnvelopeHistoryMutation.mutate()
                    }
                  }}
                  disabled={deleteAllEnvelopeHistoryMutation.isPending}
                  className="h-8 w-fit text-muted-foreground hover:text-destructive border-muted-foreground/25"
                >
                  <Trash2 size={13} className="mr-1.5" />
                  Delete All Envelope Logs
                </Button>
              )}
            </div>
          </SheetHeader>

          <div className="mt-6 flex flex-col gap-4">
            {historyTab === 'gmf' ? (
              !historyData || historyData.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-8 border border-dashed rounded-xl bg-muted/20">
                  <History size={32} className="text-muted-foreground/30 mb-3" />
                  <span className="text-sm font-medium text-muted-foreground block text-center">No GMF template history logged yet.</span>
                </div>
              ) : (
                historyData.map(log => (
                  <div key={log.id} className="p-4 border rounded-xl bg-card shadow-sm text-sm flex flex-col gap-2 transition-all hover:shadow-md hover:border-border">
                    <div className="flex items-center justify-between font-bold">
                      <span className="text-foreground text-[15px] tracking-tight">{log.template_name}</span>
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          "px-2.5 py-1 rounded-md text-[11px] uppercase tracking-wider font-extrabold shadow-sm",
                          log.action === 'APPROVED' ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400" : "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-400"
                        )}>
                          {log.action}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Delete log"
                          onClick={() => {
                            if (window.confirm('Delete this template history log?')) {
                              deleteHistoryMutation.mutate(log.id)
                            }
                          }}
                          disabled={deleteHistoryMutation.isPending}
                          className="h-7 w-7 text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </div>
                    {log.filename && <div className="text-muted-foreground text-xs mt-1 font-medium flex items-center gap-1.5"><FileText size={12} /> {log.filename}</div>}
                    {log.reason && <div className="text-red-600 dark:text-red-400 font-semibold text-xs mt-1.5 bg-red-50 dark:bg-red-950/20 px-2.5 py-1.5 rounded flex gap-1.5 items-start"><AlertCircle size={14} className="shrink-0 mt-0.5" /> {log.reason}</div>}
                    <div className="text-[11px] text-muted-foreground mt-2 font-mono bg-muted/50 px-2 py-1 rounded w-fit">
                      {new Date(log.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))
              )
            ) : (
              !envelopeHistoryData || envelopeHistoryData.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-8 border border-dashed rounded-xl bg-muted/20">
                  <Mail size={32} className="text-muted-foreground/30 mb-3" />
                  <span className="text-sm font-medium text-muted-foreground block text-center">No envelope campaign history logged yet.</span>
                </div>
              ) : (
                envelopeHistoryData.map(log => (
                  <div key={log.id} className="p-4 border rounded-xl bg-card shadow-sm text-sm flex flex-col gap-2 transition-all hover:shadow-md hover:border-border">
                    <div className="flex items-center justify-between font-bold">
                      <span className="text-foreground text-[15px] tracking-tight">{log.template_name}</span>
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          "px-2.5 py-1 rounded-md text-[11px] uppercase tracking-wider font-extrabold shadow-sm",
                          log.action === 'APPROVED' ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400" : "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-400"
                        )}>
                          {log.action}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Delete log"
                          onClick={() => {
                            if (window.confirm('Delete this envelope history log?')) {
                              deleteEnvelopeHistoryMutation.mutate(log.id)
                            }
                          }}
                          disabled={deleteEnvelopeHistoryMutation.isPending}
                          className="h-7 w-7 text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </div>
                    {log.filename && <div className="text-muted-foreground text-xs mt-1 font-medium flex items-center gap-1.5"><FileText size={12} /> {log.filename}</div>}
                    {log.reason && <div className="text-red-600 dark:text-red-400 font-semibold text-xs mt-1.5 bg-red-50 dark:bg-red-950/20 px-2.5 py-1.5 rounded flex gap-1.5 items-start"><AlertCircle size={14} className="shrink-0 mt-0.5" /> {log.reason}</div>}
                    <div className="text-[11px] text-muted-foreground mt-2 font-mono bg-muted/50 px-2 py-1 rounded w-fit">
                      {new Date(log.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))
              )
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
