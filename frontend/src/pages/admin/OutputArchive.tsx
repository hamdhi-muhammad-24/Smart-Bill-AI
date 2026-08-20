import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Folder, FolderOpen, FileText, ChevronRight, Download, Eye, Loader2 } from 'lucide-react'
import { getOutputDates, getOutputCycles, getOutputBatches, getOutputPdfs, fetchPdfBlobUrl } from '../../lib/api'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { Button } from '@/components/ui/button'
import { cn, formatCycleDisplayName } from '@/lib/utils'

export default function OutputArchive() {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedCycle, setSelectedCycle] = useState<string | null>(null)
  const [selectedBatch, setSelectedBatch] = useState<string | null>(null)
  const [selectedPdf, setSelectedPdf] = useState<string | null>(null)

  const { data: datesData, isLoading: loadingDates } = useQuery({
    queryKey: ['output-dates'],
    queryFn: getOutputDates
  })

  const { data: cyclesData, isLoading: loadingCycles } = useQuery({
    queryKey: ['output-cycles', selectedDate],
    queryFn: () => getOutputCycles(selectedDate!),
    enabled: !!selectedDate
  })

  const { data: batchesData, isLoading: loadingBatches } = useQuery({
    queryKey: ['output-batches', selectedDate, selectedCycle],
    queryFn: () => getOutputBatches(selectedDate!, selectedCycle!),
    enabled: !!selectedDate && !!selectedCycle
  })

  const { data: pdfsData, isLoading: loadingPdfs } = useQuery({
    queryKey: ['output-pdfs', selectedDate, selectedCycle, selectedBatch],
    queryFn: () => getOutputPdfs(selectedDate!, selectedCycle!, selectedBatch!),
    enabled: !!selectedDate && !!selectedCycle && !!selectedBatch
  })

  // Securely fetch PDF Blob URL
  const { data: pdfUrl, isLoading: loadingPdfBlob } = useQuery({
    queryKey: ['output-pdf-blob', selectedDate, selectedCycle, selectedBatch, selectedPdf],
    queryFn: () => fetchPdfBlobUrl(selectedDate!, selectedCycle!, selectedBatch!, selectedPdf!),
    enabled: !!selectedDate && !!selectedCycle && !!selectedBatch && !!selectedPdf
  })

  // Reset downstream selections when upstream changes
  useEffect(() => { setSelectedCycle(null); setSelectedBatch(null); setSelectedPdf(null); }, [selectedDate])
  useEffect(() => { setSelectedBatch(null); setSelectedPdf(null); }, [selectedCycle])
  useEffect(() => { setSelectedPdf(null); }, [selectedBatch])

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] gap-4">
      <PageHeader 
        title="Output Archive" 
        description="Browse and view all generated invoices organized by date, cycle, and batch." 
      />

      <div className="flex flex-1 min-h-0 gap-4 overflow-hidden">
        {/* Left Panel: File Browser */}
        <div className="w-1/3 flex flex-col glass-card shadow-lg overflow-hidden h-full min-h-0">
          <div className="bg-muted/30 border-b p-3 flex flex-wrap gap-1 items-center text-sm shrink-0">
            <span className="font-semibold text-foreground/80 cursor-pointer hover:text-foreground" onClick={() => setSelectedDate(null)}>
              Output
            </span>
            {selectedDate && (
              <>
                <ChevronRight size={14} className="text-muted-foreground" />
                <span className="cursor-pointer hover:text-foreground" onClick={() => setSelectedCycle(null)}>{selectedDate}</span>
              </>
            )}
            {selectedCycle && (
              <>
                <ChevronRight size={14} className="text-muted-foreground" />
                <span className="cursor-pointer hover:text-foreground" onClick={() => setSelectedBatch(null)}>{formatCycleDisplayName(selectedCycle)}</span>
              </>
            )}
            {selectedBatch && (
              <>
                <ChevronRight size={14} className="text-muted-foreground" />
                <span>{selectedBatch.replace('_', ' ')}</span>
              </>
            )}
          </div>
          
          <div className="flex-1 overflow-y-auto p-2.5 space-y-1 min-h-0">
            {!selectedDate ? (
              // Show Dates
              loadingDates ? <div className="flex justify-center p-4"><Loader2 className="animate-spin text-muted-foreground" /></div> :
              datesData?.dates.length === 0 ? <div className="text-center p-4 text-muted-foreground text-sm">No outputs found.</div> :
              datesData?.dates.map(date => (
                <div key={date} onClick={() => setSelectedDate(date)} className="flex items-center gap-2 p-2 rounded-lg cursor-pointer hover:bg-muted text-sm">
                  <Folder size={16} className="text-blue-400 fill-blue-400/20" />
                  <span className="font-medium">{date}</span>
                </div>
              ))
            ) : !selectedCycle ? (
              // Show Cycles
              loadingCycles ? <div className="flex justify-center p-4"><Loader2 className="animate-spin text-muted-foreground" /></div> :
              cyclesData?.cycles.length === 0 ? <div className="text-center p-4 text-muted-foreground text-sm">No cycles found.</div> :
              cyclesData?.cycles.map(cycle => (
                <div key={cycle} onClick={() => setSelectedCycle(cycle)} className="flex items-center gap-2 p-2 rounded-lg cursor-pointer hover:bg-muted text-sm">
                  <Folder size={16} className="text-amber-400 fill-amber-400/20" />
                  <span className="font-medium">{formatCycleDisplayName(cycle)}</span>
                </div>
              ))
            ) : !selectedBatch ? (
              // Show Batches
              loadingBatches ? <div className="flex justify-center p-4"><Loader2 className="animate-spin text-muted-foreground" /></div> :
              batchesData?.batches.length === 0 ? <div className="text-center p-4 text-muted-foreground text-sm">No batches found.</div> :
              batchesData?.batches.map(b => (
                <div key={b.batch} onClick={() => setSelectedBatch(b.batch)} className="flex items-center justify-between p-2 rounded-lg cursor-pointer hover:bg-muted text-sm">
                  <div className="flex items-center gap-2">
                    <FolderOpen size={16} className="text-emerald-400 fill-emerald-400/20" />
                    <span className="font-medium">{b.batch.replace('_', ' ')}</span>
                  </div>
                  <span className="text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 px-2 rounded-full">{b.pdf_count} PDFs</span>
                </div>
              ))
            ) : (
              // Show PDFs
              loadingPdfs ? <div className="flex justify-center p-4"><Loader2 className="animate-spin text-muted-foreground" /></div> :
              pdfsData?.files.length === 0 ? <div className="text-center p-4 text-muted-foreground text-sm">No PDFs found in this batch.</div> :
              pdfsData?.files.map(pdf => (
                <div 
                  key={pdf} 
                  onClick={() => setSelectedPdf(pdf)} 
                  className={cn("flex items-center gap-2 p-2 rounded-lg cursor-pointer text-sm", selectedPdf === pdf ? "bg-primary/10 text-primary font-medium" : "hover:bg-muted")}
                >
                  <FileText size={16} className={selectedPdf === pdf ? "text-primary" : "text-rose-500"} />
                  <span className="truncate">{pdf}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Panel: PDF Viewer */}
        <div className="w-2/3 flex flex-col glass-card shadow-lg overflow-hidden">
          {loadingPdfBlob ? (
            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground bg-slate-50/50 dark:bg-slate-900/50">
              <Loader2 size={48} className="mb-4 opacity-20 animate-spin" />
              <p>Loading secure PDF...</p>
            </div>
          ) : !pdfUrl ? (
            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground bg-slate-50/50 dark:bg-slate-900/50">
              <FileText size={48} className="mb-4 opacity-20" />
              <p>Select a PDF file from the browser to view it here.</p>
            </div>
          ) : (
            <>
              <div className="p-3 border-b bg-muted/20 flex justify-between items-center">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <FileText size={16} className="text-rose-500" />
                  {selectedPdf}
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => window.open(pdfUrl, '_blank')}>
                    <Eye size={14} className="mr-1.5" /> Open New Tab
                  </Button>
                  <Button size="sm" asChild>
                    <a href={pdfUrl} download>
                      <Download size={14} className="mr-1.5" /> Download
                    </a>
                  </Button>
                </div>
              </div>
              <div className="flex-1 bg-slate-200/50 dark:bg-slate-950/50 p-2">
                <iframe 
                  src={`${pdfUrl}#toolbar=0`} 
                  className="w-full h-full rounded border bg-white dark:bg-slate-900 shadow-sm"
                  title="PDF Viewer"
                />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
