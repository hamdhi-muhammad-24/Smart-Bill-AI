import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  Upload, Image as ImageIcon, ZoomIn, ZoomOut, RotateCcw, Edit3, CheckCircle2,
  AlertCircle, Trash2, Download, Send, HelpCircle, History, Sparkles, Layers, RefreshCw, X, Maximize2
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { toast } from 'sonner'
import { motion, AnimatePresence } from 'framer-motion'

interface ArtworkRecord {
  id: number
  filename: string
  status: string
  image_size: string
  output_pdf_path?: string
  rejection_reason?: string
  uploaded_by?: string
  created_at: string
  replaced_at?: string
}

interface EnvelopeTemplateDetail {
  id: number
  envelope_type: string
  display_name: string
  base_pdf_path: string
  box: { x0: number; y0: number; x1: number; y1: number }
  rotation_deg: number
  fit_mode: string
  min_width: number
  min_height: number
  aspect_min: number
  aspect_max: number
  sample_img_size: string
  artworks: ArtworkRecord[]
}

const API_BASE = 'http://localhost:8090'

async function fetchTemplateDetail(id: number): Promise<EnvelopeTemplateDetail> {
  const res = await fetch(`${API_BASE}/api/envelope/templates/${id}`)
  if (!res.ok) throw new Error('Failed to fetch template detail')
  return res.json()
}

async function fetchTemplatesSummary() {
  const res = await fetch(`${API_BASE}/api/envelope/templates`)
  if (!res.ok) throw new Error('Failed to fetch templates summary')
  return res.json()
}

export default function EnvelopeManager() {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  
  const templateIdFromUrl = parseInt(searchParams.get('template') || '1', 10)
  const [selectedTemplateId, setSelectedTemplateId] = useState<number>(templateIdFromUrl || 1)

  // Viewer mode & zoom state
  const [zoomLevel, setZoomLevel] = useState<number>(1)
  const [showUploadZone, setShowUploadZone] = useState<boolean>(false)
  const [viewMode, setViewMode] = useState<'image' | 'pdf'>('image')

  // Full screen PDF modal state
  const [selectedPdf, setSelectedPdf] = useState<{ url: string; title: string; downloadUrl: string } | null>(null)

  // Upload modal & drag state
  const [isUploading, setIsUploading] = useState<boolean>(false)
  const [dragActive, setDragActive] = useState<boolean>(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  // Reference example output modal
  const [showExampleModal, setShowExampleModal] = useState<boolean>(false)

  // History drawer/tab state
  const [showHistoryModal, setShowHistoryModal] = useState<boolean>(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  // Fetch list of templates to populate tabs
  const { data: templatesList } = useQuery({
    queryKey: ['envelopeTemplates'],
    queryFn: fetchTemplatesSummary,
  })

  // Fetch current selected template details
  const { data: templateDetail, isLoading } = useQuery({
    queryKey: ['envelopeTemplateDetail', selectedTemplateId],
    queryFn: () => fetchTemplateDetail(selectedTemplateId),
    enabled: !!selectedTemplateId,
  })

  useEffect(() => {
    if (searchParams.get('template')) {
      const id = parseInt(searchParams.get('template')!, 10)
      if (id && id !== selectedTemplateId) {
        setSelectedTemplateId(id)
      }
    }
  }, [searchParams])

  const activeArtwork = templateDetail?.artworks.find(a =>
    ['ACTIVE', 'SUBMITTED', 'APPROVED'].includes(a.status)
  )

  const basePdfUrl = `${API_BASE}/api/envelope/templates/${selectedTemplateId}/base-pdf`
  const activeOutputPdfUrl = activeArtwork ? `${API_BASE}/api/envelope/artworks/${activeArtwork.id}/download` : basePdfUrl

  // Upload Mutation
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch(`${API_BASE}/api/envelope/templates/${selectedTemplateId}/upload-artwork`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail?.message || data.message || 'Upload failed')
      }
      return data
    },
    onSuccess: (data) => {
      toast.success(data.message || 'Artwork uploaded and composited successfully!')
      setUploadError(null)
      setIsUploading(false)
      setShowUploadZone(false)
      queryClient.invalidateQueries({ queryKey: ['envelopeTemplateDetail', selectedTemplateId] })
      queryClient.invalidateQueries({ queryKey: ['envelopeTemplates'] })
    },
    onError: (error: any) => {
      const msg = error.message || 'Image upload failed'
      setUploadError(msg)
      toast.error(msg)
      setIsUploading(false)
    },
  })

  // Remove Artwork Mutation
  const removeMutation = useMutation({
    mutationFn: async (artworkId: number) => {
      const res = await fetch(`${API_BASE}/api/envelope/artworks/${artworkId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to remove artwork')
      return res.json()
    },
    onSuccess: () => {
      toast.success('Artwork removed. Reverted to empty base template.')
      queryClient.invalidateQueries({ queryKey: ['envelopeTemplateDetail', selectedTemplateId] })
      queryClient.invalidateQueries({ queryKey: ['envelopeTemplates'] })
    },
  })

  // Submit Artwork Mutation
  const submitMutation = useMutation({
    mutationFn: async (artworkId: number) => {
      const res = await fetch(`${API_BASE}/api/envelope/artworks/${artworkId}/submit`, { method: 'POST' })
      if (!res.ok) throw new Error('Failed to submit artwork for approval')
      return res.json()
    },
    onSuccess: () => {
      toast.success('Artwork submitted for Admin review and approval!')
      queryClient.invalidateQueries({ queryKey: ['envelopeTemplateDetail', selectedTemplateId] })
      queryClient.invalidateQueries({ queryKey: ['envelopeTemplates'] })
    },
  })

  const handleFileSelect = (file: File) => {
    setUploadError(null)
    setIsUploading(true)
    uploadMutation.mutate(file)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0])
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <PageHeader
        title="Envelope Base Template & Artwork Manager"
        description="Select an envelope type below to preview base PDF layout, upload campaign artwork, or review generated output."
        breadcrumbs={[
          { label: 'Envelope Portal', to: '/envelope-handler' },
          { label: 'Envelope Manager' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowHistoryModal(true)} className="gap-2 text-xs">
              <History size={13} />
              Artwork History ({templateDetail?.artworks.length || 0})
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowExampleModal(true)} className="gap-2 text-xs text-blue-400 border-blue-500/30 bg-blue-500/5">
              <HelpCircle size={13} />
              Size Guide & Examples
            </Button>
          </div>
        }
      />

      {/* Custom Template Navigation Tabs */}
      <div className="flex p-1 bg-muted/40 rounded-xl border border-border/80 w-full max-w-2xl">
        {templatesList?.map((t: any) => {
          const isSelected = t.id === selectedTemplateId
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setSelectedTemplateId(t.id)
                setSearchParams({ template: t.id.toString() })
                setZoomLevel(1)
                setUploadError(null)
                setShowUploadZone(false)
              }}
              className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 text-xs font-bold rounded-lg transition-all ${
                isSelected
                  ? 'bg-background text-foreground shadow-sm border border-border'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              }`}
            >
              <Layers size={13} />
              {t.display_name}
            </button>
          )
        })}
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="h-96 flex items-center justify-center border rounded-2xl bg-muted/20">
            <div className="flex items-center gap-3 text-muted-foreground">
              <RefreshCw size={20} className="animate-spin text-blue-500" />
              <span>Loading envelope template configuration...</span>
            </div>
          </div>
        ) : templateDetail ? (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Interactive Base Template & PDF Viewer (7 cols) */}
            <div className="lg:col-span-7 space-y-6">
              <Card className="overflow-hidden border-border/80 shadow-md">
                <CardHeader className="py-3 px-4 bg-muted/40 border-b flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-bold flex items-center gap-2">
                      <span>Base Template Viewer</span>
                      <Badge variant="outline" className="text-[10px] font-mono uppercase bg-blue-500/10 text-blue-400 border-blue-500/20">
                        {templateDetail.envelope_type}
                      </Badge>
                    </CardTitle>
                    <CardDescription className="text-[11px]">
                      Placeholder Box: <strong className="text-foreground">{templateDetail.box.x1 - templateDetail.box.x0}x{templateDetail.box.y1 - templateDetail.box.y0} pts</strong>
                    </CardDescription>
                  </div>

                  {/* Viewer Toolbar Controls */}
                  <div className="flex items-center gap-1.5">
                    {/* View Mode Toggle: Image vs PDF */}
                    <div className="flex bg-background border rounded-md p-0.5 text-[11px] font-semibold">
                      <button
                        type="button"
                        onClick={() => setViewMode('image')}
                        className={`px-2 py-0.5 rounded ${viewMode === 'image' ? 'bg-muted text-foreground font-bold' : 'text-muted-foreground'}`}
                      >
                        PNG
                      </button>
                      <button
                        type="button"
                        onClick={() => setViewMode('pdf')}
                        className={`px-2 py-0.5 rounded ${viewMode === 'pdf' ? 'bg-muted text-foreground font-bold' : 'text-muted-foreground'}`}
                      >
                        PDF
                      </button>
                    </div>

                    <div className="h-4 w-px bg-border mx-0.5" />

                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 text-muted-foreground hover:text-foreground"
                      title="Zoom In"
                      onClick={() => setZoomLevel((z) => Math.min(z + 0.25, 2.5))}
                    >
                      <ZoomIn size={14} />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 text-muted-foreground hover:text-foreground"
                      title="Zoom Out"
                      onClick={() => setZoomLevel((z) => Math.max(z - 0.25, 0.5))}
                    >
                      <ZoomOut size={14} />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 text-muted-foreground hover:text-foreground"
                      title="Reset Zoom"
                      onClick={() => setZoomLevel(1)}
                    >
                      <RotateCcw size={14} />
                    </Button>

                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 text-muted-foreground hover:text-foreground"
                      title="Inspect Full PDF Layout"
                      onClick={() => setSelectedPdf({ url: basePdfUrl, title: `${templateDetail.display_name} (Base Empty Template)`, downloadUrl: basePdfUrl })}
                    >
                      <Maximize2 size={14} />
                    </Button>

                    <div className="h-4 w-px bg-border mx-0.5" />

                    <Button
                      variant="default"
                      size="sm"
                      className="h-7 text-xs font-bold gap-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow"
                      onClick={() => setShowUploadZone(true)}
                    >
                      <Edit3 size={12} />
                      Edit / Upload Artwork
                    </Button>
                  </div>
                </CardHeader>

                <CardContent className="p-4 bg-slate-950/70 min-h-[360px] flex items-center justify-center overflow-auto relative">
                  {viewMode === 'pdf' ? (
                    <div className="w-full h-[360px]">
                      <iframe
                        src={`${basePdfUrl}#toolbar=0&navpanes=0`}
                        title={templateDetail.display_name}
                        className="w-full h-full rounded-lg bg-white border border-white/10"
                      />
                    </div>
                  ) : (
                    <div
                      className="transition-transform duration-200 ease-out origin-center flex items-center justify-center max-w-full"
                      style={{ transform: `scale(${zoomLevel})` }}
                    >
                      <img
                        src={`${API_BASE}/api/envelope/templates/${templateDetail.id}/preview-base`}
                        alt={templateDetail.display_name}
                        className="max-h-[340px] object-contain rounded shadow-2xl border border-white/10"
                      />
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Composited Output Preview (if artwork uploaded) */}
              {activeArtwork && (
                <Card className="overflow-hidden border-emerald-500/30 bg-emerald-500/5 shadow-md">
                  <CardHeader className="py-3 px-4 bg-emerald-500/10 border-b border-emerald-500/20 flex flex-row items-center justify-between">
                    <div>
                      <CardTitle className="text-sm font-bold text-emerald-400 flex items-center gap-2">
                        <CheckCircle2 size={16} />
                        Composited Output Preview
                      </CardTitle>
                      <CardDescription className="text-[11px] text-emerald-300/80">
                        Base Template + Uploaded Artwork composite result
                      </CardDescription>
                    </div>

                    <div className="flex items-center gap-2">
                      <Badge className="bg-emerald-500 text-white uppercase text-[10px]">
                        {activeArtwork.status}
                      </Badge>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs gap-1.5 text-emerald-300 hover:bg-emerald-500/20"
                        onClick={() => setSelectedPdf({ url: activeOutputPdfUrl, title: `${templateDetail.display_name} (Composited PDF)`, downloadUrl: activeOutputPdfUrl })}
                      >
                        <Maximize2 size={12} />
                        View Full PDF
                      </Button>
                      <a
                        href={activeOutputPdfUrl}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5 border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/20">
                          <Download size={12} />
                          Download PDF
                        </Button>
                      </a>
                    </div>
                  </CardHeader>

                  <CardContent className="p-4 bg-slate-950/60 min-h-[320px] flex items-center justify-center">
                    <img
                      src={`${API_BASE}/api/envelope/artworks/${activeArtwork.id}/preview`}
                      alt="Composited Envelope Output"
                      className="max-h-[340px] object-contain rounded shadow-2xl border border-white/15"
                    />
                  </CardContent>
                </Card>
              )}
            </div>

            {/* Right Column: Upload & Actions Workspace (5 cols) */}
            <div className="lg:col-span-5 space-y-6">
              <Card className="border-border/80 shadow-md">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base font-bold flex items-center justify-between">
                    <span>Promotional Image Settings</span>
                    <Badge variant="outline" className="text-[10px]">
                      {templateDetail.display_name}
                    </Badge>
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Upload promotional campaign artwork to place into the base envelope template.
                  </CardDescription>
                </CardHeader>

                <CardContent className="space-y-4">
                  {/* Size & Specification Box */}
                  <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-3 text-xs space-y-1.5">
                    <div className="font-bold text-blue-400 flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <Sparkles size={14} />
                        Required Artwork Specs
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-5 text-[11px] text-blue-400 p-0 underline hover:bg-transparent"
                        onClick={() => setShowExampleModal(true)}
                      >
                        View Reference Example
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-muted-foreground">
                      <div>Sample Size: <strong className="text-foreground font-mono">{templateDetail.sample_img_size}</strong></div>
                      <div>Min Width: <span className="font-mono text-foreground">{templateDetail.min_width}px</span></div>
                      <div>Aspect Ratio: <span className="font-mono text-foreground">{templateDetail.aspect_min/100} - {templateDetail.aspect_max/100}</span></div>
                      <div>Fit Mode: <span className="font-mono text-foreground uppercase">{templateDetail.fit_mode}</span></div>
                    </div>
                  </div>

                  {/* Active Upload Card */}
                  {activeArtwork ? (
                    <div className="rounded-xl border border-border p-4 bg-muted/30 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-muted-foreground uppercase">Current Active Artwork</span>
                        <Badge variant="secondary" className="text-[10px] font-mono">
                          {activeArtwork.image_size}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="size-12 rounded-lg bg-background border flex items-center justify-center shrink-0 overflow-hidden">
                          <ImageIcon size={20} className="text-muted-foreground" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold truncate">{activeArtwork.filename}</p>
                          <p className="text-[11px] text-muted-foreground">
                            Uploaded: {new Date(activeArtwork.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="grid grid-cols-2 gap-2 pt-2 border-t">
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-xs gap-1.5 font-bold"
                          onClick={() => fileInputRef.current?.click()}
                          disabled={isUploading}
                        >
                          <Edit3 size={13} />
                          Replace Image
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          className="text-xs gap-1.5 font-bold"
                          onClick={() => removeMutation.mutate(activeArtwork.id)}
                          disabled={removeMutation.isPending}
                        >
                          <Trash2 size={13} />
                          Remove Image
                        </Button>
                      </div>

                      {activeArtwork.status === 'ACTIVE' && (
                        <Button
                          size="sm"
                          className="w-full text-xs font-bold gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md mt-2"
                          onClick={() => submitMutation.mutate(activeArtwork.id)}
                          disabled={submitMutation.isPending}
                        >
                          <Send size={13} />
                          Submit to Admin for Approval
                        </Button>
                      )}
                    </div>
                  ) : null}

                  {/* Drag & Drop Upload Zone */}
                  {(!activeArtwork || showUploadZone) && (
                    <div
                      className={`border-2 border-dashed rounded-2xl p-6 text-center transition-all cursor-pointer ${
                        dragActive
                          ? 'border-blue-500 bg-blue-500/10'
                          : 'border-border/80 hover:border-blue-500/50 hover:bg-muted/30'
                      }`}
                      onDragOver={(e) => { e.preventDefault(); setDragActive(true) }}
                      onDragLeave={() => setDragActive(false)}
                      onDrop={handleDrop}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".jpg,.jpeg,.png"
                        className="hidden"
                        onChange={(e) => {
                          if (e.target.files && e.target.files[0]) {
                            handleFileSelect(e.target.files[0])
                          }
                        }}
                      />

                      {isUploading ? (
                        <div className="space-y-3 py-4">
                          <RefreshCw size={28} className="animate-spin text-blue-500 mx-auto" />
                          <p className="text-xs font-semibold">Validating and compositing promotional image...</p>
                        </div>
                      ) : (
                        <div className="space-y-3 py-2">
                          <div className="size-12 rounded-full bg-blue-500/10 text-blue-400 flex items-center justify-center mx-auto">
                            <Upload size={20} />
                          </div>
                          <div>
                            <p className="text-sm font-bold">Click or drag promotional image here</p>
                            <p className="text-xs text-muted-foreground mt-1">Accepted Formats: .JPG, .JPEG, .PNG</p>
                          </div>
                          <Button size="sm" variant="secondary" className="text-xs font-bold gap-1">
                            Browse Computer
                          </Button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Upload Error Alert */}
                  {uploadError && (
                    <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive space-y-1.5">
                      <div className="font-bold flex items-center gap-1.5">
                        <AlertCircle size={14} />
                        Uploaded Image Unsuitable
                      </div>
                      <p className="leading-relaxed">{uploadError}</p>
                      <div className="pt-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-[11px] h-6 text-destructive underline p-0 hover:bg-transparent"
                          onClick={() => setShowExampleModal(true)}
                        >
                          View Example Output Reference & Size Guide
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        ) : null}
      </div>

      {/* Full Screen PDF Modal (Matches InvoiceTemplates.tsx) */}
      <AnimatePresence>
        {selectedPdf && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 md:p-8"
            onClick={() => setSelectedPdf(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ type: "spring", bounce: 0, duration: 0.3 }}
              className="relative max-h-full max-w-5xl w-full h-[90vh] flex flex-col bg-slate-900 rounded-2xl overflow-hidden shadow-2xl border border-white/10"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="px-6 py-4 bg-slate-950 border-b border-white/10 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                  <h3 className="font-extrabold text-base text-white">{selectedPdf.title}</h3>
                  <Badge variant="outline" className="text-[10px] font-mono text-blue-400 border-blue-500/30">
                    PDF Layout Viewer
                  </Badge>
                </div>

                <div className="flex items-center gap-3">
                  <a href={selectedPdf.downloadUrl} target="_blank" rel="noreferrer">
                    <Button size="sm" variant="secondary" className="h-8 text-xs font-bold gap-1.5">
                      <Download size={14} /> Download PDF
                    </Button>
                  </a>
                  <button
                    className="text-slate-400 hover:text-white bg-white/10 hover:bg-white/20 rounded-full p-2 transition-colors"
                    onClick={() => setSelectedPdf(null)}
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>

              {/* iframe */}
              <div className="flex-1 bg-slate-950 p-2 overflow-hidden">
                <iframe
                  src={`${selectedPdf.url}#toolbar=1&navpanes=0`}
                  title={selectedPdf.title}
                  className="w-full h-full bg-white rounded-xl border border-white/10"
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Example Size Guide Modal */}
      {showExampleModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border rounded-2xl p-6 max-w-2xl w-full shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-base flex items-center gap-2 text-foreground">
                <HelpCircle className="text-blue-400" size={18} />
                Envelope Promotional Image Size Guide & Reference
              </h3>
              <Button variant="ghost" size="icon" onClick={() => setShowExampleModal(false)}>
                <X size={16} />
              </Button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="border rounded-xl p-3.5 bg-muted/30 space-y-2">
                <div className="font-bold text-foreground flex justify-between">
                  <span>1. Large Envelope</span>
                  <span className="font-mono text-blue-400">Sample: 833x817 px</span>
                </div>
                <p className="text-muted-foreground leading-relaxed">
                  Suitable for square or near-square promotional banners (aspect ratio 0.70 - 1.40). Placed on top-right of Large Envelope.
                </p>
              </div>

              <div className="border rounded-xl p-3.5 bg-muted/30 space-y-2">
                <div className="font-bold text-foreground flex justify-between">
                  <span>2. Medium Envelope</span>
                  <span className="font-mono text-blue-400">Sample: 1179x618 px</span>
                </div>
                <p className="text-muted-foreground leading-relaxed">
                  Suitable for wide landscape promotional images (aspect ratio 1.50 - 2.50). Placed on bottom area of Medium Envelope.
                </p>
              </div>

              <div className="border rounded-xl p-3.5 bg-muted/30 space-y-2">
                <div className="font-bold text-foreground flex justify-between">
                  <span>3. Self-Seal A4 Envelope</span>
                  <span className="font-mono text-blue-400">Sample: 1070x361 px</span>
                </div>
                <p className="text-muted-foreground leading-relaxed">
                  Suitable for horizontal campaign banners (aspect ratio 2.50 - 4.50). Placed on bottom strip of Self-Seal A4 Envelope.
                </p>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <Button size="sm" onClick={() => setShowExampleModal(false)}>
                Close Reference Guide
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Artwork History Modal */}
      {showHistoryModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border rounded-2xl p-6 max-w-3xl w-full shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-base flex items-center gap-2 text-foreground">
                <History size={18} className="text-indigo-400" />
                Artwork Upload History — {templateDetail?.display_name}
              </h3>
              <Button variant="ghost" size="icon" onClick={() => setShowHistoryModal(false)}>
                <X size={16} />
              </Button>
            </div>

            <div className="max-h-[400px] overflow-y-auto space-y-3 pr-2">
              {templateDetail?.artworks.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-6">No history records found.</p>
              ) : (
                templateDetail?.artworks.map((art) => (
                  <div key={art.id} className="flex items-center justify-between border rounded-xl p-3 text-xs bg-muted/20">
                    <div className="space-y-1">
                      <div className="font-bold flex items-center gap-2">
                        <span>{art.filename}</span>
                        <Badge variant="outline" className="text-[10px] uppercase font-mono">
                          {art.status}
                        </Badge>
                      </div>
                      <div className="text-muted-foreground text-[11px] flex gap-3">
                        <span>Size: {art.image_size}</span>
                        <span>Uploaded: {new Date(art.created_at).toLocaleString()}</span>
                      </div>
                      {art.rejection_reason && (
                        <p className="text-destructive text-[11px]">Rejection Reason: {art.rejection_reason}</p>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {art.output_pdf_path && (
                        <a href={`${API_BASE}/api/envelope/artworks/${art.id}/download`} target="_blank" rel="noreferrer">
                          <Button size="sm" variant="ghost" className="h-7 text-xs gap-1">
                            <Download size={12} />
                            Download
                          </Button>
                        </a>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <Button size="sm" onClick={() => setShowHistoryModal(false)}>
                Close History
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
