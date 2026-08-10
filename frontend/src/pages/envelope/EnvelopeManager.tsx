import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  Upload, ZoomIn, ZoomOut, RotateCcw, CheckCircle2,
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
  const [viewMode, setViewMode] = useState<'image' | 'pdf'>('image')

  // Full screen PDF modal state
  const [selectedPdf, setSelectedPdf] = useState<{ url: string; pngUrl: string; title: string; downloadUrl: string } | null>(null)

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

  const [selectedArtworkId, setSelectedArtworkId] = useState<number | null>(null)

  const basePdfUrl = `${API_BASE}/api/envelope/templates/${selectedTemplateId}/base-pdf`
  const basePdfDownloadUrl = `${API_BASE}/api/envelope/templates/${selectedTemplateId}/download-base-pdf`

  const activeArtwork = templateDetail?.artworks.find(a =>
    selectedArtworkId ? a.id === selectedArtworkId : ['ACTIVE', 'SUBMITTED', 'APPROVED', 'DRAFT'].includes(a.status)
  ) || templateDetail?.artworks[0]

  const activeOutputPdfUrl = activeArtwork ? `${API_BASE}/api/envelope/artworks/${activeArtwork.id}/view-pdf` : basePdfUrl
  const activeOutputPdfDownloadUrl = activeArtwork ? `${API_BASE}/api/envelope/artworks/${activeArtwork.id}/download` : basePdfDownloadUrl

  // Upload Mutation
  const uploadMutation = useMutation({
    mutationFn: async ({ file, targetStatus }: { file: File; targetStatus: 'DRAFT' | 'SUBMITTED' }) => {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch(`${API_BASE}/api/envelope/templates/${selectedTemplateId}/upload-artwork?target_status=${targetStatus}`, {
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
      toast.success(data.message || 'Promotional artwork processed successfully!')
      setUploadError(null)
      setIsUploading(false)
      queryClient.invalidateQueries({ queryKey: ['envelopeTemplateDetail', selectedTemplateId] })
      queryClient.invalidateQueries({ queryKey: ['envelopeTemplates'] })
      queryClient.invalidateQueries({ queryKey: ['savedArtworks'] })
    },
    onError: (error: any) => {
      const msg = error.message || 'Image upload failed'
      setUploadError(msg)
      toast.error(msg)
      setIsUploading(false)
    },
  })

  const handleFileSelect = (file: File, targetStatus: 'DRAFT' | 'SUBMITTED' = 'DRAFT') => {
    setUploadError(null)
    setIsUploading(true)
    uploadMutation.mutate({ file, targetStatus })
  }

  // Remove Artwork Mutation
  const removeMutation = useMutation({
    mutationFn: async (artworkId: number) => {
      const res = await fetch(`${API_BASE}/api/envelope/artworks/${artworkId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to remove artwork')
      return res.json()
    },
    onSuccess: () => {
      toast.success('Artwork removed. Template reverted to base layout.')
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
      toast.success('Artwork submitted for review!')
      queryClient.invalidateQueries({ queryKey: ['envelopeTemplateDetail', selectedTemplateId] })
      queryClient.invalidateQueries({ queryKey: ['envelopeTemplates'] })
    },
  })



  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0])
    }
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-10">
      <PageHeader
        title="Envelope Manager"
        description="Select an envelope template to view the layout, upload campaign images, or review composite outputs."
        breadcrumbs={[
          { label: 'Envelope Portal', to: '/envelope-handler' },
          { label: 'Manager' },
        ]}
        actions={
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm" onClick={() => setShowHistoryModal(true)} className="gap-2 text-xs font-semibold h-9">
              <History size={14} className="text-indigo-500" />
              Artwork History ({templateDetail?.artworks.length || 0})
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowExampleModal(true)} className="gap-2 text-xs font-semibold h-9 text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-900">
              <HelpCircle size={14} />
              Size Guide
            </Button>
          </div>
        }
      />

      {/* Template Navigation Pills */}
      <div className="flex p-1.5 bg-slate-100 dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 w-full max-w-2xl">
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
              }}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-4 text-xs font-bold rounded-xl transition-all ${
                isSelected
                  ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-sm border border-slate-200 dark:border-slate-700'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              <Layers size={14} className={isSelected ? "text-indigo-600 dark:text-indigo-400" : ""} />
              <span>{t.display_name}</span>
              {t.has_active_artwork && (
                <span className="size-2 rounded-full bg-indigo-600 animate-pulse ml-0.5" />
              )}
            </button>
          )
        })}
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="h-96 flex items-center justify-center border border-slate-200 dark:border-slate-800 rounded-2xl bg-card">
            <div className="flex items-center gap-3 text-slate-500">
              <RefreshCw size={20} className="animate-spin text-indigo-600" />
              <span className="font-medium text-sm">Loading template layout...</span>
            </div>
          </div>
        ) : templateDetail ? (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Viewers (7 cols) */}
            <div className="lg:col-span-7 space-y-6">
              {/* Base Template Viewer */}
              <Card className="overflow-hidden border-slate-200 dark:border-slate-800 shadow-sm rounded-2xl">
                <CardHeader className="py-3.5 px-5 bg-slate-50/50 dark:bg-slate-900/40 border-b border-slate-200 dark:border-slate-800 flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-bold flex items-center gap-2 text-slate-900 dark:text-slate-100">
                      <span>Base Envelope Layout</span>
                      <Badge variant="outline" className="text-xs font-mono uppercase text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-900">
                        {templateDetail.envelope_type}
                      </Badge>
                    </CardTitle>
                  </div>

                  {/* Controls */}
                  <div className="flex items-center gap-1.5">
                    <div className="flex bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-0.5 text-xs font-semibold">
                      <button
                        type="button"
                        onClick={() => setViewMode('image')}
                        className={`px-2.5 py-1 rounded-md transition-colors ${viewMode === 'image' ? 'bg-indigo-600 text-white font-bold' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'}`}
                      >
                        Image
                      </button>
                      <button
                        type="button"
                        onClick={() => setViewMode('pdf')}
                        className={`px-2.5 py-1 rounded-md transition-colors ${viewMode === 'pdf' ? 'bg-indigo-600 text-white font-bold' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'}`}
                      >
                        PDF
                      </button>
                    </div>

                    <div className="h-4 w-px bg-slate-200 dark:bg-slate-800 mx-1" />

                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 text-slate-600 dark:text-slate-400"
                      title="Zoom In"
                      onClick={() => setZoomLevel((z) => Math.min(z + 0.25, 2.5))}
                    >
                      <ZoomIn size={15} />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 text-slate-600 dark:text-slate-400"
                      title="Zoom Out"
                      onClick={() => setZoomLevel((z) => Math.max(z - 0.25, 0.5))}
                    >
                      <ZoomOut size={15} />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 text-slate-600 dark:text-slate-400"
                      title="Reset Zoom"
                      onClick={() => setZoomLevel(1)}
                    >
                      <RotateCcw size={15} />
                    </Button>

                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-8 text-slate-600 dark:text-slate-400"
                      title="Inspect Full PDF Layout"
                      onClick={() => setSelectedPdf({
                        url: basePdfUrl,
                        pngUrl: `${API_BASE}/api/envelope/templates/${templateDetail.id}/preview-base`,
                        title: `${templateDetail.display_name} (Base Template)`,
                        downloadUrl: basePdfDownloadUrl
                      })}
                    >
                      <Maximize2 size={15} />
                    </Button>

                    <div className="h-4 w-px bg-slate-200 dark:bg-slate-800 mx-1" />

                    <Button
                      size="sm"
                      className="h-8 text-xs font-semibold gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <Upload size={13} />
                      Upload Image
                    </Button>
                  </div>
                </CardHeader>

                <CardContent className="p-4 bg-slate-950 min-h-[360px] flex items-center justify-center overflow-auto">
                  {viewMode === 'pdf' ? (
                    <div className="w-full h-[360px]">
                      <iframe
                        src={`${basePdfUrl}#toolbar=0&navpanes=0&view=Fit`}
                        title={templateDetail.display_name}
                        className="w-full h-full rounded-xl bg-white border border-slate-800"
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
                        className="max-h-[340px] object-contain rounded-lg shadow-2xl border border-slate-800"
                      />
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Composited Output Preview */}
              {activeArtwork && (
                <Card className="overflow-hidden border-indigo-200 dark:border-indigo-900/50 bg-indigo-50/40 dark:bg-indigo-950/20 shadow-sm rounded-2xl">
                  <CardHeader className="py-3.5 px-5 bg-indigo-100/50 dark:bg-indigo-900/30 border-b border-indigo-200 dark:border-indigo-900/50 flex flex-row items-center justify-between">
                    <div>
                      <CardTitle className="text-sm font-bold text-indigo-900 dark:text-indigo-200 flex items-center gap-2">
                        <CheckCircle2 size={16} className="text-indigo-600 dark:text-indigo-400" />
                        Composited Output Preview
                      </CardTitle>
                      <CardDescription className="text-xs text-indigo-700/80 dark:text-indigo-300/80 mt-0.5">
                        Base Template + Uploaded Artwork composite output
                      </CardDescription>
                    </div>

                    <div className="flex items-center gap-2">
                      <Badge className="bg-indigo-600 text-white uppercase text-xs font-bold px-2.5 py-0.5">
                        {activeArtwork.status}
                      </Badge>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 text-xs font-semibold gap-1.5 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-200/50 dark:hover:bg-indigo-900/50"
                        onClick={() => setSelectedPdf({
                          url: activeOutputPdfUrl,
                          pngUrl: `${API_BASE}/api/envelope/artworks/${activeArtwork.id}/preview`,
                          title: `${templateDetail.display_name} (Composited Output)`,
                          downloadUrl: activeOutputPdfDownloadUrl
                        })}
                      >
                        <Maximize2 size={14} />
                        Inspect PDF
                      </Button>
                      <a
                        href={activeOutputPdfDownloadUrl}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <Button size="sm" variant="outline" className="h-8 text-xs font-semibold gap-1.5 border-indigo-300 dark:border-indigo-800 text-indigo-800 dark:text-indigo-200">
                          <Download size={14} />
                          Download PDF
                        </Button>
                      </a>
                    </div>
                  </CardHeader>

                  <CardContent className="p-4 bg-slate-950 min-h-[320px] flex items-center justify-center">
                    <img
                      src={`${API_BASE}/api/envelope/artworks/${activeArtwork.id}/preview`}
                      alt="Composited Envelope Output"
                      className="max-h-[340px] object-contain rounded-lg shadow-2xl border border-slate-800"
                    />
                  </CardContent>
                </Card>
              )}
            </div>

            {/* Right Column: Settings (5 cols) */}
            <div className="lg:col-span-5 space-y-6">
              <Card className="border-slate-200 dark:border-slate-800 shadow-sm rounded-2xl">
                <CardHeader className="pb-3 border-b border-slate-100 dark:border-slate-800">
                  <CardTitle className="text-base font-bold flex items-center justify-between text-slate-900 dark:text-slate-100">
                    <span>Artwork Placement Settings</span>
                    <Badge variant="outline" className="text-xs font-mono">
                      {templateDetail.display_name}
                    </Badge>
                  </CardTitle>
                </CardHeader>

                <CardContent className="space-y-4 pt-4">
                  {/* Specification Box */}
                  <div className="rounded-xl border border-indigo-100 dark:border-indigo-900/50 bg-indigo-50/50 dark:bg-indigo-950/30 p-4 text-xs space-y-2">
                    <div className="font-bold text-indigo-900 dark:text-indigo-200 flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <Sparkles size={14} className="text-indigo-600 dark:text-indigo-400" />
                        Artwork Requirements
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-5 text-xs text-indigo-600 dark:text-indigo-400 p-0 font-semibold underline hover:bg-transparent"
                        onClick={() => setShowExampleModal(true)}
                      >
                        View Guide
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-slate-600 dark:text-slate-400 pt-1">
                      <div>Recommended Size: <strong className="text-indigo-600 dark:text-indigo-400 font-mono">{templateDetail.sample_img_size}</strong></div>
                      <div>Min Width: <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold">{templateDetail.min_width}px</span></div>
                      <div>Aspect Ratio: <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold">{templateDetail.aspect_min/100} - {templateDetail.aspect_max/100}</span></div>
                      <div>Fit Mode: <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold uppercase">{templateDetail.fit_mode}</span></div>
                    </div>
                  </div>

                  {/* Drag & Drop Upload Zone (ALWAYS VISIBLE FOR MULTIPLE UPLOADS) */}
                  <div
                    className={`border-2 border-dashed rounded-xl p-5 text-center transition-all cursor-pointer ${
                      dragActive
                        ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/30'
                        : 'border-slate-200 dark:border-slate-800 hover:border-indigo-500/50 hover:bg-slate-50/50'
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
                          handleFileSelect(e.target.files[0], 'DRAFT')
                        }
                      }}
                    />

                    {isUploading ? (
                      <div className="space-y-2 py-3">
                        <RefreshCw size={24} className="animate-spin text-indigo-600 mx-auto" />
                        <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">Processing promotional image...</p>
                      </div>
                    ) : (
                      <div className="space-y-3 py-1">
                        <div className="size-10 rounded-xl bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mx-auto">
                          <Upload size={20} />
                        </div>
                        <div>
                          <p className="text-sm font-bold text-slate-900 dark:text-slate-100">Upload Promotional Image</p>
                          <p className="text-xs text-slate-500 mt-0.5">Drag & drop or browse image files for {templateDetail.display_name}</p>
                        </div>
                        <div className="flex gap-2 justify-center pt-1" onClick={(e) => e.stopPropagation()}>
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-xs font-semibold gap-1.5 h-8"
                            onClick={() => fileInputRef.current?.click()}
                          >
                            <Upload size={13} />
                            Save as Draft
                          </Button>
                          <Button
                            size="sm"
                            className="text-xs font-semibold gap-1.5 h-8 bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm"
                            onClick={() => fileInputRef.current?.click()}
                          >
                            <Send size={13} />
                            Submit for Approval
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Artwork Campaign Variations List */}
                  {templateDetail.artworks && templateDetail.artworks.length > 0 && (
                    <div className="space-y-3 pt-2">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
                          Saved Campaign Variations ({templateDetail.artworks.length})
                        </h4>
                      </div>

                      <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                        {templateDetail.artworks.map((art) => {
                          const isSelected = (activeArtwork?.id === art.id)
                          return (
                            <div
                              key={art.id}
                              className={`p-3 rounded-xl border transition-all cursor-pointer ${
                                isSelected
                                  ? 'border-indigo-500 bg-indigo-50/40 dark:bg-indigo-950/40 shadow-xs'
                                  : 'border-slate-200 dark:border-slate-800 bg-card hover:bg-slate-50 dark:hover:bg-slate-900/40'
                              }`}
                              onClick={() => setSelectedArtworkId(art.id)}
                            >
                              <div className="flex items-center justify-between mb-1.5">
                                <span className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate max-w-[180px]">
                                  {art.filename}
                                </span>
                                <Badge className={`text-[10px] font-bold px-2 py-0.2 ${
                                  art.status === 'APPROVED' ? 'bg-indigo-600 text-white' :
                                  art.status === 'SUBMITTED' ? 'bg-amber-600 text-white' :
                                  art.status === 'REJECTED' ? 'bg-rose-600 text-white' :
                                  'bg-slate-700 text-slate-200'
                                }`}>
                                  {art.status}
                                </Badge>
                              </div>

                              <div className="flex items-center justify-between text-xs text-slate-500 font-mono">
                                <span>{art.image_size}</span>
                                <div className="flex items-center gap-1">
                                  {art.status === 'DRAFT' && (
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      className="h-6 px-2 text-[11px] font-bold text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50"
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        submitMutation.mutate(art.id)
                                      }}
                                    >
                                      Submit
                                    </Button>
                                  )}
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-6 px-1.5 text-rose-500 hover:text-rose-700 hover:bg-rose-50"
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      if (window.confirm(`Delete "${art.filename}"?`)) {
                                        removeMutation.mutate(art.id)
                                      }
                                    }}
                                  >
                                    <Trash2 size={12} />
                                  </Button>
                                </div>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Upload Error Alert */}
                  {uploadError && (
                    <div className="rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-950/30 p-3.5 text-xs text-rose-900 dark:text-rose-200 space-y-1.5">
                      <div className="font-bold flex items-center gap-1.5 text-rose-600 dark:text-rose-400">
                        <AlertCircle size={14} />
                        Uploaded Image Unsuitable
                      </div>
                      <p className="leading-relaxed">{uploadError}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        ) : null}
      </div>

      {/* PDF Inspection Modal */}
      <AnimatePresence>
        {selectedPdf && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 md:p-8"
            onClick={() => setSelectedPdf(null)}
          >
            <motion.div
              initial={{ scale: 0.96, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.96, opacity: 0 }}
              className="relative max-h-full max-w-5xl w-full h-[90vh] flex flex-col bg-slate-900 rounded-2xl overflow-hidden shadow-2xl border border-slate-800"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="px-6 py-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                  <h3 className="font-bold text-sm text-white">{selectedPdf.title}</h3>
                </div>

                <div className="flex items-center gap-3">
                  <a href={selectedPdf.downloadUrl} download target="_blank" rel="noreferrer">
                    <Button size="sm" variant="secondary" className="h-8 text-xs font-semibold gap-1.5">
                      <Download size={14} /> Download PDF
                    </Button>
                  </a>
                  <button
                    className="text-slate-400 hover:text-white bg-slate-800 rounded-full p-1.5 transition-colors"
                    onClick={() => setSelectedPdf(null)}
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>

              <div className="flex-1 bg-slate-950 p-2 overflow-hidden">
                <iframe
                  src={`${selectedPdf.url}#toolbar=1&navpanes=0`}
                  title={selectedPdf.title}
                  className="w-full h-full bg-white rounded-xl border border-slate-800"
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Size Guide Modal */}
      {showExampleModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-slate-200 dark:border-slate-800 rounded-2xl p-6 max-w-xl w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-base flex items-center gap-2 text-slate-900 dark:text-slate-100">
                <HelpCircle className="text-indigo-600" size={18} />
                Artwork Specifications
              </h3>
              <Button variant="ghost" size="icon" onClick={() => setShowExampleModal(false)}>
                <X size={16} />
              </Button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="border rounded-xl p-3.5 bg-slate-50 dark:bg-slate-900/40 space-y-1">
                <div className="font-bold text-slate-900 dark:text-slate-100 flex justify-between">
                  <span>1. Large Envelope</span>
                  <span className="font-mono text-indigo-600 dark:text-indigo-400">833 × 817 px</span>
                </div>
                <p className="text-slate-500">Square promo banners. Placed on top-right panel.</p>
              </div>

              <div className="border rounded-xl p-3.5 bg-slate-50 dark:bg-slate-900/40 space-y-1">
                <div className="font-bold text-slate-900 dark:text-slate-100 flex justify-between">
                  <span>2. Medium Envelope</span>
                  <span className="font-mono text-indigo-600 dark:text-indigo-400">1179 × 618 px</span>
                </div>
                <p className="text-slate-500">Wide landscape promo images. Placed on bottom panel.</p>
              </div>

              <div className="border rounded-xl p-3.5 bg-slate-50 dark:bg-slate-900/40 space-y-1">
                <div className="font-bold text-slate-900 dark:text-slate-100 flex justify-between">
                  <span>3. Self-Seal A4</span>
                  <span className="font-mono text-indigo-600 dark:text-indigo-400">1070 × 361 px</span>
                </div>
                <p className="text-slate-500">Horizontal campaign banners. Placed on bottom strip.</p>
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <Button size="sm" className="font-semibold" onClick={() => setShowExampleModal(false)}>
                Close Guide
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* History Modal */}
      {showHistoryModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-card border border-slate-200 dark:border-slate-800 rounded-2xl p-6 max-w-2xl w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-base flex items-center gap-2 text-slate-900 dark:text-slate-100">
                <History size={18} className="text-indigo-600" />
                Artwork Upload History — {templateDetail?.display_name}
              </h3>
              <Button variant="ghost" size="icon" onClick={() => setShowHistoryModal(false)}>
                <X size={16} />
              </Button>
            </div>

            <div className="max-h-[360px] overflow-y-auto space-y-2.5 pr-1">
              {templateDetail?.artworks.length === 0 ? (
                <p className="text-xs text-slate-500 text-center py-6">No history records found.</p>
              ) : (
                templateDetail?.artworks.map((art) => (
                  <div key={art.id} className="flex items-center justify-between border border-slate-200 dark:border-slate-800 rounded-xl p-3 text-xs bg-slate-50/50 dark:bg-slate-900/40">
                    <div className="space-y-0.5">
                      <div className="font-bold flex items-center gap-2 text-slate-900 dark:text-slate-100">
                        <span>{art.filename}</span>
                        <Badge variant="outline" className="text-xs uppercase font-mono">
                          {art.status}
                        </Badge>
                      </div>
                      <div className="text-slate-500 text-xs flex gap-3">
                        <span>Size: {art.image_size}</span>
                        <span>Date: {new Date(art.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>

                    <div>
                      {art.output_pdf_path && (
                        <a href={`${API_BASE}/api/envelope/artworks/${art.id}/download`} target="_blank" rel="noreferrer">
                          <Button size="sm" variant="ghost" className="h-7 text-xs font-semibold gap-1">
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
              <Button size="sm" className="font-semibold" onClick={() => setShowHistoryModal(false)}>
                Close History
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
