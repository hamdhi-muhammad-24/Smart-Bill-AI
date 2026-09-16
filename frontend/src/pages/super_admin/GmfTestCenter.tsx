import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Play,
  Download,
  FileCheck2,
  CheckCircle2,
  XCircle,
  Clock,
  Layers,
  Search,
  ChevronRight,
  Info,
  RotateCw,
  Check,
  AlertCircle,
  X,
  Eye,
  Trash2,
} from 'lucide-react'
import {
  getSuperAdminOverview,
  startGmfTestRun,
  listGmfTestRuns,
  getGmfTestRunDetails,
  downloadGmfTestReportPdf,
  getInvoicePdfUrl,
  downloadInvoicePdf,
  resetSystemData,
} from '../../lib/api'
import type { GmfTestRunSummary, GmfTestInvoiceResult } from '../../lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

export default function GmfTestCenter() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'all' | 'pass' | 'fail'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedResult, setSelectedResult] = useState<GmfTestInvoiceResult | null>(null)
  const [activeRunId, setActiveRunId] = useState<number | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const [isResetDialogOpen, setIsResetDialogOpen] = useState(false)

  // 1. Fetch overview metrics
  const { data: overview, refetch: refetchOverview } = useQuery({
    queryKey: ['super-admin-overview'],
    queryFn: getSuperAdminOverview,
    refetchInterval: isPolling ? 3000 : 30000,
  })

  // 2. Fetch runs history
  const { data: runsList, refetch: refetchRuns } = useQuery({
    queryKey: ['super-admin-runs'],
    queryFn: listGmfTestRuns,
  })

  // Set activeRunId from overview or most recent run if not set
  useEffect(() => {
    if (!activeRunId && overview?.latest_run) {
      setActiveRunId(overview.latest_run.id)
    } else if (!activeRunId && runsList && runsList.length > 0) {
      setActiveRunId(runsList[0].id)
    }
  }, [overview, runsList, activeRunId])

  // 3. Fetch details of the selected run
  const { data: currentRun } = useQuery({
    queryKey: ['super-admin-run-details', activeRunId],
    queryFn: () => (activeRunId ? getGmfTestRunDetails(activeRunId) : null),
    enabled: !!activeRunId,
    refetchInterval: isPolling ? 2000 : false,
  })

  // Check if current run is in progress and update polling state
  useEffect(() => {
    if (currentRun && (currentRun.status === 'RUNNING' || currentRun.status === 'PENDING')) {
      setIsPolling(true)
    } else if (currentRun && (currentRun.status === 'COMPLETED' || currentRun.status === 'FAILED')) {
      if (isPolling) {
        setIsPolling(false)
        queryClient.invalidateQueries({ queryKey: ['super-admin-overview'] })
        queryClient.invalidateQueries({ queryKey: ['super-admin-runs'] })
        if (currentRun.status === 'COMPLETED') {
          toast.success(
            `Test Run #${currentRun.id} completed: ${currentRun.passed_count}/${currentRun.total_invoices_tested} invoices verified successfully.`,
          )
        } else {
          toast.error(`Test Run #${currentRun.id} failed: ${currentRun.error_message}`)
        }
      }
    }
  }, [currentRun, isPolling, queryClient])

  // Mutation to start new test run
  const startMutation = useMutation({
    mutationFn: (sampleSize: number) => startGmfTestRun(sampleSize),
    onSuccess: (data) => {
      toast.info(`Started test run #${data.id} with up to 100 GMF files.`)
      setActiveRunId(data.id)
      setIsPolling(true)
      queryClient.invalidateQueries({ queryKey: ['super-admin-overview'] })
      queryClient.invalidateQueries({ queryKey: ['super-admin-runs'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to start test run.')
    },
  })

  // Mutation to reset system data
  const resetMutation = useMutation({
    mutationFn: resetSystemData,
    onSuccess: (data) => {
      toast.success(data.message || 'System wiped clean. Ready for fresh test.')
      setIsResetDialogOpen(false)
      setActiveRunId(null)
      queryClient.invalidateQueries({ queryKey: ['super-admin-overview'] })
      queryClient.invalidateQueries({ queryKey: ['super-admin-runs'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to reset system data.')
    },
  })

  // Filtered results list
  const results = useMemo(() => {
    const list = currentRun?.results || []
    return list.filter((item: GmfTestInvoiceResult) => {
      // Tab filter
      if (activeTab === 'pass' && item.status !== 'PASS') return false
      if (activeTab === 'fail' && item.status !== 'FAIL') return false

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchFile = (item.filename || '').toLowerCase().includes(q)
        const matchAcc = (item.account_number || '').toLowerCase().includes(q)
        const matchInv = (item.invoice_number || '').toLowerCase().includes(q)
        const matchTpl = (item.template_id || '').toLowerCase().includes(q)
        return matchFile || matchAcc || matchInv || matchTpl
      }
      return true
    })
  }, [currentRun, activeTab, searchQuery])

  // Compute pass rates
  const currentPassRate = useMemo(() => {
    if (!currentRun || currentRun.total_invoices_tested === 0) return 0
    return Math.round((currentRun.passed_count / currentRun.total_invoices_tested) * 100)
  }, [currentRun])

  const latestOverviewPassRate = useMemo(() => {
    const lr = overview?.latest_run
    if (!lr || lr.total_invoices_tested === 0) return 'N/A'
    return `${Math.round((lr.passed_count / lr.total_invoices_tested) * 100)}%`
  }, [overview])

  const handleDownloadPdf = (runId: number) => {
    toast.info('Downloading verification report PDF...')
    downloadGmfTestReportPdf(runId).catch(() => {
      toast.error('Failed to download report.')
    })
  }

  return (
    <div className="space-y-6 pb-12 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            GMF Test Center
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Sample up to 100 uploaded GMF invoices and verify line calculations against rendered statement totals.
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              refetchOverview()
              refetchRuns()
              if (activeRunId) queryClient.invalidateQueries({ queryKey: ['super-admin-run-details', activeRunId] })
            }}
            className="gap-2 text-xs font-semibold"
          >
            <RotateCw size={13} className={isPolling ? 'animate-spin' : ''} />
            Refresh
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsResetDialogOpen(true)}
            disabled={isPolling || resetMutation.isPending}
            className="gap-2 text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 border-rose-200 dark:border-rose-900/50 dark:hover:bg-rose-950/30"
          >
            <Trash2 size={13} />
            Reset All Test Data
          </Button>

          <Button
            size="sm"
            onClick={() => startMutation.mutate(100)}
            disabled={isPolling || startMutation.isPending}
            className="gap-2 bg-[#0066b3] hover:bg-[#005292] text-white font-semibold shadow-xs text-xs px-4"
          >
            {isPolling || startMutation.isPending ? (
              <>
                <RotateCw size={14} className="animate-spin" />
                Testing In Progress...
              </>
            ) : (
              <>
                <Play size={13} fill="currentColor" />
                Run 100 GMF Test
              </>
            )}
          </Button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Pool Total */}
        <div className="rounded-xl border border-border/70 bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold whitespace-nowrap">Total Uploads</span>
            <div className="flex size-7 items-center justify-center rounded-md bg-blue-500/10 text-[#0066b3] dark:text-[#00b2e3]">
              <Layers size={14} />
            </div>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {overview?.total_uploads_in_system ?? 0}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5 whitespace-nowrap">
            Raw GMF files stored in system
          </p>
        </div>

        {/* Eligible Invoices */}
        <div className="rounded-xl border border-border/70 bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold whitespace-nowrap">Eligible Invoices</span>
            <div className="flex size-7 items-center justify-center rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <FileCheck2 size={14} />
            </div>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {overview?.eligible_invoice_gmfs_count ?? 0}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5 whitespace-nowrap">
            Standard billing statements
          </p>
        </div>

        {/* Latest Pass Rate */}
        <div className="rounded-xl border border-border/70 bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold whitespace-nowrap">Latest Pass Rate</span>
            <div className="flex size-7 items-center justify-center rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <Check size={14} />
            </div>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {latestOverviewPassRate}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5 whitespace-nowrap">
            Line items and total match
          </p>
        </div>

        {/* Total Runs Executed */}
        <div className="rounded-xl border border-border/70 bg-card p-4 shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-2">
            <span className="text-xs font-semibold whitespace-nowrap">Test Runs</span>
            <div className="flex size-7 items-center justify-center rounded-md bg-purple-500/10 text-purple-600 dark:text-purple-400">
              <Clock size={14} />
            </div>
          </div>
          <div className="text-2xl font-bold text-foreground">
            {runsList?.length ?? 0}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5 whitespace-nowrap">
            Completed verification batches
          </p>
        </div>
      </div>

      {/* Live Run Banner */}
      {isPolling && (
        <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-4 shadow-xs">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="size-8 rounded-lg bg-blue-500/10 text-[#0066b3] dark:text-[#00b2e3] flex items-center justify-center">
                <RotateCw size={16} className="animate-spin" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-foreground whitespace-nowrap">
                  Verification in progress for Run #{currentRun?.id}
                </h3>
                <p className="text-xs text-muted-foreground whitespace-nowrap">
                  Verifying invoice line items and totals against generated PDFs...
                </p>
              </div>
            </div>
            <span className="text-xs font-semibold text-[#0066b3] dark:text-[#00b2e3] whitespace-nowrap">Processing</span>
          </div>
        </div>
      )}

      {/* Selected Run Overview Bar */}
      {currentRun && (
        <div className="rounded-xl border border-border/80 bg-card p-4 shadow-xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="text-base font-bold text-foreground whitespace-nowrap">
                  Test Run #{currentRun.id}
                </h2>
                <Badge
                  variant="outline"
                  className={cn(
                    "text-xs font-semibold whitespace-nowrap",
                    currentRun.status === 'COMPLETED'
                      ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30'
                      : currentRun.status === 'FAILED'
                      ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30'
                      : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30'
                  )}
                >
                  {currentRun.status}
                </Badge>
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  {currentRun.started_at ? new Date(currentRun.started_at).toLocaleString() : ''}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5 whitespace-nowrap">
                Sampled {currentRun.total_files_sampled} files &bull; {currentRun.total_invoices_tested} invoices verified
              </p>
            </div>

            {/* Micro Stats & Download */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 whitespace-nowrap">
                <CheckCircle2 size={14} className="text-emerald-500" />
                <div className="text-xs">
                  <span className="text-muted-foreground mr-1">Passed:</span>
                  <span className="font-bold text-emerald-600 dark:text-emerald-400">{currentRun.passed_count}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 rounded-lg bg-rose-500/10 border border-rose-500/20 px-3 py-1.5 whitespace-nowrap">
                <XCircle size={14} className="text-rose-500" />
                <div className="text-xs">
                  <span className="text-muted-foreground mr-1">Failed:</span>
                  <span className="font-bold text-rose-600 dark:text-rose-400">{currentRun.failed_count}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 rounded-lg bg-card border border-border px-3 py-1.5 whitespace-nowrap">
                <div className="text-xs">
                  <span className="text-muted-foreground mr-1">Rate:</span>
                  <span className="font-bold text-foreground">{currentPassRate}%</span>
                </div>
              </div>

              <Button
                size="sm"
                variant="outline"
                onClick={() => handleDownloadPdf(currentRun.id)}
                disabled={currentRun.status !== 'COMPLETED'}
                className="gap-1.5 text-xs font-semibold whitespace-nowrap"
              >
                <Download size={13} />
                Download Report PDF
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Main Validation Table Card */}
      <div className="rounded-xl border border-border/80 bg-card shadow-xs overflow-hidden">
        {/* Table Filters & Search Header */}
        <div className="p-3.5 border-b border-border/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-muted/20">
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer whitespace-nowrap ${
                activeTab === 'all'
                  ? 'bg-primary text-primary-foreground shadow-xs'
                  : 'text-muted-foreground hover:bg-muted'
              }`}
            >
              All Invoices ({currentRun?.results?.length || 0})
            </button>
            <button
              onClick={() => setActiveTab('pass')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer whitespace-nowrap ${
                activeTab === 'pass'
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'text-muted-foreground hover:bg-emerald-500/10 hover:text-emerald-600'
              }`}
            >
              Passed ({currentRun?.passed_count || 0})
            </button>
            <button
              onClick={() => setActiveTab('fail')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer whitespace-nowrap ${
                activeTab === 'fail'
                  ? 'bg-rose-600 text-white shadow-xs'
                  : 'text-muted-foreground hover:bg-rose-500/10 hover:text-rose-600'
              }`}
            >
              Failed ({currentRun?.failed_count || 0})
            </button>
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search file, account, invoice..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-xs rounded-lg"
            />
          </div>
        </div>

        {/* Table Content */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-muted/40 text-muted-foreground uppercase font-bold text-[10px] border-b border-border/70">
              <tr>
                <th className="px-4 py-2.5 whitespace-nowrap">Doc #</th>
                <th className="px-4 py-2.5 whitespace-nowrap">Source File</th>
                <th className="px-4 py-2.5 whitespace-nowrap">Account / Invoice</th>
                <th className="px-4 py-2.5 whitespace-nowrap">Template</th>
                <th className="px-4 py-2.5 text-right whitespace-nowrap">GMF Line Sum</th>
                <th className="px-4 py-2.5 text-right whitespace-nowrap">GMF Tag</th>
                <th className="px-4 py-2.5 text-right whitespace-nowrap">PDF Line Sum</th>
                <th className="px-4 py-2.5 text-right whitespace-nowrap">PDF Total</th>
                <th className="px-4 py-2.5 text-center whitespace-nowrap">Status</th>
                <th className="px-4 py-2.5 text-center whitespace-nowrap">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {results.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-10 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-1.5">
                      <Info size={18} />
                      <p className="font-semibold text-xs whitespace-nowrap">No verification results match current filters.</p>
                      <p className="text-[11px] whitespace-nowrap">Run a 100 GMF test or select an existing test run.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                results.map((row: GmfTestInvoiceResult, idx: number) => {
                  const isFail = row.status === 'FAIL'
                  const gmfCalc = Number(row.gmf_calculated_total || 0)
                  const gmfTag = row.gmf_charges_tag !== null ? Number(row.gmf_charges_tag) : null
                  const pdfLineSum = Number(row.pdf_details_total || 0)
                  const pdfTot = row.pdf_total_charges !== null ? Number(row.pdf_total_charges) : null

                  return (
                    <tr
                      key={`${row.filename}_${row.doc_index}_${idx}`}
                      className={`hover:bg-muted/30 transition-colors ${
                        isFail ? 'bg-rose-500/[0.04]' : ''
                      }`}
                    >
                      <td className="px-4 py-3 font-semibold text-muted-foreground whitespace-nowrap">
                        #{row.doc_index}
                      </td>
                      <td className="px-4 py-3 font-medium text-foreground max-w-[220px] truncate whitespace-nowrap" title={row.filename}>
                        {row.filename}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="font-semibold text-foreground whitespace-nowrap">{row.account_number}</div>
                        <div className="text-[11px] text-muted-foreground whitespace-nowrap">{row.invoice_number}</div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <Badge variant="outline" className="font-mono text-[10px] uppercase whitespace-nowrap">
                          {row.template_id}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-semibold text-foreground whitespace-nowrap">
                        Rs {gmfCalc.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-semibold text-foreground whitespace-nowrap">
                        {gmfTag !== null
                          ? `Rs ${gmfTag.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                          : <span className="text-rose-500 font-semibold whitespace-nowrap">Missing</span>}
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-semibold text-foreground whitespace-nowrap">
                        Rs {pdfLineSum.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3 text-right font-mono font-semibold text-foreground whitespace-nowrap">
                        {pdfTot !== null
                          ? `Rs ${pdfTot.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                          : <span className="text-rose-500 font-semibold whitespace-nowrap">Missing</span>}
                      </td>
                      <td className="px-4 py-3 text-center whitespace-nowrap">
                        {isFail ? (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-rose-600 dark:text-rose-400 bg-rose-500/15 border border-rose-500/30 px-2 py-0.5 rounded-md whitespace-nowrap">
                            <XCircle size={11} />
                            Failed
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 rounded-md whitespace-nowrap">
                            <CheckCircle2 size={11} />
                            Passed
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center whitespace-nowrap">
                        <div className="flex items-center justify-center gap-1 whitespace-nowrap">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedResult(row)}
                            className="h-6 text-xs font-semibold gap-0.5 text-[#0066b3] dark:text-[#00b2e3] hover:underline px-2 whitespace-nowrap"
                          >
                            Inspect
                            <ChevronRight size={12} />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => window.open(getInvoicePdfUrl(row.filename, row.doc_index), '_blank')}
                            title="View generated invoice PDF in new tab"
                            className="h-6 text-xs font-semibold gap-1 text-muted-foreground hover:text-foreground px-2 whitespace-nowrap"
                          >
                            <Eye size={12} />
                            PDF
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Historical Test Runs Section */}
      <div className="rounded-xl border border-border/80 bg-card p-4 shadow-xs">
        <h3 className="text-sm font-bold text-foreground mb-0.5 whitespace-nowrap">
          Past Test Runs
        </h3>
        <p className="text-xs text-muted-foreground mb-3 whitespace-nowrap">
          Review previous verification batches or download historical reports.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-muted/40 text-muted-foreground uppercase font-bold text-[10px] border-b border-border/70">
              <tr>
                <th className="px-3.5 py-2 whitespace-nowrap">Run ID</th>
                <th className="px-3.5 py-2 whitespace-nowrap">Date & Time</th>
                <th className="px-3.5 py-2 whitespace-nowrap">Files Sampled</th>
                <th className="px-3.5 py-2 whitespace-nowrap">Invoices Tested</th>
                <th className="px-3.5 py-2 whitespace-nowrap">Passed / Failed</th>
                <th className="px-3.5 py-2 whitespace-nowrap">Pass Rate</th>
                <th className="px-3.5 py-2 whitespace-nowrap">Status</th>
                <th className="px-3.5 py-2 text-right whitespace-nowrap">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {(runsList || []).map((run: GmfTestRunSummary) => {
                const runPassRate = run.total_invoices_tested > 0
                  ? Math.round((run.passed_count / run.total_invoices_tested) * 100)
                  : 0

                return (
                  <tr key={run.id} className="hover:bg-muted/20">
                    <td className="px-3.5 py-2.5 font-semibold text-foreground whitespace-nowrap">
                      #{run.id}
                    </td>
                    <td className="px-3.5 py-2.5 text-muted-foreground whitespace-nowrap">
                      {new Date(run.started_at).toLocaleString()}
                    </td>
                    <td className="px-3.5 py-2.5 font-medium whitespace-nowrap">
                      {run.total_files_sampled}
                    </td>
                    <td className="px-3.5 py-2.5 font-medium whitespace-nowrap">
                      {run.total_invoices_tested}
                    </td>
                    <td className="px-3.5 py-2.5 whitespace-nowrap">
                      <span className="text-emerald-600 font-semibold">{run.passed_count}</span>
                      <span className="text-muted-foreground"> / </span>
                      <span className="text-rose-600 font-semibold">{run.failed_count}</span>
                    </td>
                    <td className="px-3.5 py-2.5 font-semibold text-foreground whitespace-nowrap">
                      {runPassRate}%
                    </td>
                    <td className="px-3.5 py-2.5 whitespace-nowrap">
                      <Badge variant="outline" className="text-[10px] whitespace-nowrap">
                        {run.status}
                      </Badge>
                    </td>
                    <td className="px-3.5 py-2.5 text-right space-x-1.5 whitespace-nowrap">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setActiveRunId(run.id)}
                        className="h-6 text-xs px-2 font-semibold whitespace-nowrap"
                      >
                        View
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDownloadPdf(run.id)}
                        disabled={run.status !== 'COMPLETED'}
                        className="h-6 text-xs px-2 font-semibold text-[#0066b3] dark:text-[#00b2e3] whitespace-nowrap"
                      >
                        <Download size={12} className="mr-1" />
                        PDF
                      </Button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Inspect Item Modal */}
      {selectedResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="relative w-full max-w-3xl max-h-[85vh] rounded-xl border border-border/80 bg-background shadow-xl overflow-hidden flex flex-col">
            {/* Header */}
            <div className="p-4 sm:p-5 border-b border-border/70 flex items-start justify-between bg-muted/20">
              <div className="min-w-0 flex-1 pr-4">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground whitespace-nowrap">
                    Invoice Details
                  </span>
                  <Badge
                    variant="outline"
                    className={cn(
                      "text-[10px] font-semibold whitespace-nowrap",
                      selectedResult.status === 'PASS'
                        ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30'
                        : 'bg-rose-500/10 text-rose-600 border-rose-500/30'
                    )}
                  >
                    {selectedResult.status === 'PASS' ? 'Passed' : 'Failed'}
                  </Badge>
                  <Badge variant="outline" className="font-mono text-[10px] uppercase whitespace-nowrap">
                    {selectedResult.template_id}
                  </Badge>
                </div>
                <h3 className="text-base font-bold text-foreground truncate" title={`${selectedResult.filename} (Doc #${selectedResult.doc_index})`}>
                  {selectedResult.filename} <span className="text-muted-foreground font-semibold text-xs ml-1">(Doc #{selectedResult.doc_index})</span>
                </h3>
                <p className="text-xs text-muted-foreground mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="whitespace-nowrap">Account: <strong className="text-foreground font-mono">{selectedResult.account_number}</strong></span>
                  <span className="text-muted-foreground/40 hidden sm:inline">•</span>
                  <span className="whitespace-nowrap">Invoice: <strong className="text-foreground font-mono">{selectedResult.invoice_number}</strong></span>
                  <span className="text-muted-foreground/40 hidden sm:inline">•</span>
                  <span className="whitespace-nowrap">Template: <strong className="text-foreground">{selectedResult.template_id}</strong></span>
                </p>
              </div>

              <button
                onClick={() => setSelectedResult(null)}
                className="text-muted-foreground hover:text-foreground p-1.5 rounded-lg hover:bg-muted transition-colors cursor-pointer shrink-0 ml-2"
                title="Close"
              >
                <X size={18} />
              </button>
            </div>

            {/* Content Body */}
            <div className="p-5 overflow-y-auto space-y-4">
              {/* Status Message */}
              {selectedResult.status === 'FAIL' ? (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs">
                  <div className="flex items-center gap-2 font-semibold text-rose-600 dark:text-rose-400 mb-1">
                    <AlertCircle size={14} />
                    Discrepancy Details
                  </div>
                  <p className="text-rose-700 dark:text-rose-300 leading-relaxed">
                    {selectedResult.mismatch_details}
                  </p>
                </div>
              ) : (
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs">
                  <div className="flex items-center gap-2 font-semibold text-emerald-600 dark:text-emerald-400 mb-1">
                    <CheckCircle2 size={14} />
                    Verification Successful
                  </div>
                  <p className="text-emerald-700 dark:text-emerald-300 leading-relaxed">
                    All line items, tags, and rendered PDF totals match exactly.
                  </p>
                </div>
              )}

              {/* 4-Way Reconciliation Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <div className="rounded-lg border border-border p-3 bg-muted/20">
                  <div className="text-[10px] font-semibold text-muted-foreground uppercase whitespace-nowrap">GMF Line Sum</div>
                  <div className="text-xs font-bold font-mono mt-1 text-foreground whitespace-nowrap">
                    Rs {Number(selectedResult.gmf_calculated_total || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                </div>
                <div className="rounded-lg border border-border p-3 bg-muted/20">
                  <div className="text-[10px] font-semibold text-muted-foreground uppercase whitespace-nowrap">GMF Tag</div>
                  <div className="text-xs font-bold font-mono mt-1 text-foreground whitespace-nowrap">
                    {selectedResult.gmf_charges_tag !== null
                      ? `Rs ${Number(selectedResult.gmf_charges_tag).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                      : 'N/A'}
                  </div>
                </div>
                <div className="rounded-lg border border-border p-3 bg-muted/20">
                  <div className="text-[10px] font-semibold text-muted-foreground uppercase whitespace-nowrap">PDF Line Sum</div>
                  <div className="text-xs font-bold font-mono mt-1 text-foreground whitespace-nowrap">
                    Rs {Number(selectedResult.pdf_details_total || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                </div>
                <div className="rounded-lg border border-border p-3 bg-muted/20">
                  <div className="text-[10px] font-semibold text-muted-foreground uppercase whitespace-nowrap">PDF Total</div>
                  <div className="text-xs font-bold font-mono mt-1 text-foreground whitespace-nowrap">
                    {selectedResult.pdf_total_charges !== null
                      ? `Rs ${Number(selectedResult.pdf_total_charges).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                      : 'N/A'}
                  </div>
                </div>
              </div>

              {/* Extracted GMF Line Items Breakdown */}
              <div>
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                  Line Items Extracted from GMF ({selectedResult.gmf_line_items_count || 0})
                </h4>
                <div className="rounded-lg border border-border overflow-hidden">
                  <table className="w-full text-xs">
                    <thead className="bg-muted/40 text-muted-foreground text-[10px] font-semibold uppercase">
                      <tr>
                        <th className="px-3 py-1.5 text-left whitespace-nowrap">Description</th>
                        <th className="px-3 py-1.5 text-right whitespace-nowrap">Amount (LKR)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {(selectedResult.details_summary || []).map((item: any, i: number) => (
                        <tr key={i} className="hover:bg-muted/20">
                          <td className="px-3 py-1.5 text-foreground font-medium">{item.desc}</td>
                          <td className="px-3 py-1.5 text-right font-mono font-semibold text-foreground whitespace-nowrap">
                            Rs {Number(item.amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                        </tr>
                      ))}
                      {(selectedResult.details_summary || []).length === 0 && (
                        <tr>
                          <td colSpan={2} className="px-3 py-3 text-center text-muted-foreground">
                            No individual charge items extracted.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Footer with View/Download on left and Close on right */}
            <div className="p-3.5 sm:p-4 border-t border-border/70 flex items-center justify-between bg-muted/10">
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => window.open(getInvoicePdfUrl(selectedResult.filename, selectedResult.doc_index), '_blank')}
                  className="h-8 text-xs font-semibold gap-1.5 whitespace-nowrap"
                >
                  <Eye size={13} />
                  View PDF
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => downloadInvoicePdf(selectedResult.filename, selectedResult.doc_index)}
                  className="h-8 text-xs font-semibold gap-1.5 whitespace-nowrap"
                >
                  <Download size={13} />
                  Download PDF
                </Button>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedResult(null)}
                className="h-8 text-xs font-semibold px-4 whitespace-nowrap"
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Confirmation Modal */}
      {isResetDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="relative w-full max-w-md rounded-2xl bg-card p-6 shadow-2xl border border-border/80">
            <div className="flex items-start gap-4">
              <div className="size-10 rounded-xl bg-rose-500/10 text-rose-600 flex items-center justify-center shrink-0">
                <AlertCircle size={20} />
              </div>
              <div className="space-y-1.5 flex-1">
                <h3 className="text-base font-semibold text-foreground">
                  Reset All Test Data & Storage?
                </h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  This will completely wipe all uploaded GMFs, generated PDFs, billing runs, and test history from the database and physical storage.
                </p>
                <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-2.5 text-[11px] text-amber-700 dark:text-amber-400 mt-2">
                  <strong>Safe Wipe:</strong> User accounts, base templates, and system configuration will remain intact.
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-border/60">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsResetDialogOpen(false)}
                disabled={resetMutation.isPending}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => resetMutation.mutate()}
                disabled={resetMutation.isPending}
                className="text-xs font-semibold gap-2 bg-rose-600 hover:bg-rose-700 text-white"
              >
                {resetMutation.isPending ? (
                  <>
                    <RotateCw size={13} className="animate-spin" />
                    Resetting System...
                  </>
                ) : (
                  <>
                    <Trash2 size={13} />
                    Yes, Wipe & Reset All
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

