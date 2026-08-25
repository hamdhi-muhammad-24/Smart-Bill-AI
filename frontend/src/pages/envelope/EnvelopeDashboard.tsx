import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle2, AlertCircle, RefreshCw, Upload, Sparkles, ImageIcon, Edit3, Maximize2, Download, X, Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { motion, AnimatePresence } from 'framer-motion'

interface EnvelopeTemplateInfo {
  id: number
  envelope_type: string
  display_name: string
  box_size: string
  fit_mode: string
  min_width: number
  min_height: number
  aspect_range: string
  sample_img_size: string
  has_active_artwork: boolean
  active_artwork: {
    id: number
    filename: string
    status: string
    image_size: string
    created_at: string
  } | null
}

import { BASE_URL } from '@/lib/api'

const API_BASE = BASE_URL

async function fetchEnvelopeTemplates(): Promise<EnvelopeTemplateInfo[]> {
  const res = await fetch(`${API_BASE}/api/envelope/templates`)
  if (!res.ok) throw new Error('Failed to fetch envelope templates')
  return res.json()
}

export default function EnvelopeDashboard() {
  const { data: templates, isLoading, refetch } = useQuery({
    queryKey: ['envelopeTemplates'],
    queryFn: fetchEnvelopeTemplates,
    refetchInterval: 15000,
  })

  // Full Screen PDF Modal State
  const [selectedPdf, setSelectedPdf] = useState<{
    url: string
    pngUrl: string
    title: string
    downloadUrl: string
  } | null>(null)

  const [modalViewMode, setModalViewMode] = useState<'image' | 'pdf'>('image')

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-10">
      {/* Clean Page Header */}
      <PageHeader
        title="Envelope Portal"
        description="Manage promotional campaign artwork across SLT's standardized envelope templates."
        breadcrumbs={[
          { label: 'SLT System' },
          { label: 'Envelope Portal' },
        ]}
        actions={
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              className="gap-2 text-xs font-semibold h-9"
            >
              <RefreshCw size={14} className={isLoading ? "animate-spin text-indigo-500" : ""} />
              Refresh
            </Button>
            <Link to="/envelope-handler/manager">
              <Button size="sm" className="gap-2 text-xs font-semibold h-9 bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm">
                <Upload size={14} />
                Open Envelope Manager
              </Button>
            </Link>
          </div>
        }
      />

      {/* 3 Envelope Template Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="animate-pulse rounded-2xl">
              <CardHeader className="h-28 bg-muted/30" />
              <CardContent className="h-48" />
            </Card>
          ))
        ) : (
          templates?.map((tmpl) => {
            const basePngPreviewUrl = `${API_BASE}/api/envelope/templates/${tmpl.id}/preview-base`
            const basePdfViewUrl = `${API_BASE}/api/envelope/templates/${tmpl.id}/base-pdf`
            const basePdfDownloadUrl = `${API_BASE}/api/envelope/templates/${tmpl.id}/download-base-pdf`

            const activeOutputPdfViewUrl = tmpl.active_artwork?.id
              ? `${API_BASE}/api/envelope/artworks/${tmpl.active_artwork.id}/view-pdf`
              : basePdfViewUrl

            const activeOutputPdfDownloadUrl = tmpl.active_artwork?.id
              ? `${API_BASE}/api/envelope/artworks/${tmpl.active_artwork.id}/download`
              : basePdfDownloadUrl

            const activeOutputPngUrl = tmpl.active_artwork?.id
              ? `${API_BASE}/api/envelope/artworks/${tmpl.active_artwork.id}/preview`
              : basePngPreviewUrl

            return (
              <motion.div
                whileHover={{ y: -4 }}
                transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                key={tmpl.id}
                className="flex flex-col rounded-2xl border border-slate-200 dark:border-slate-800 bg-card shadow-sm overflow-hidden transition-all hover:shadow-xl group"
              >
                {/* Image Preview Canvas */}
                <div
                  className="h-60 bg-slate-950 relative cursor-pointer overflow-hidden border-b border-slate-800 flex items-center justify-center p-4"
                  onClick={() => {
                    setSelectedPdf({
                      url: basePdfViewUrl,
                      pngUrl: basePngPreviewUrl,
                      title: `${tmpl.display_name} (Base Template)`,
                      downloadUrl: basePdfDownloadUrl,
                    })
                    setModalViewMode('image')
                  }}
                >
                  <img
                    src={basePngPreviewUrl}
                    alt={tmpl.display_name}
                    className="max-h-full max-w-full object-contain rounded-lg transition-transform duration-300 group-hover:scale-105"
                  />

                  {/* Status Badge */}
                  <div className="absolute top-3 left-3 z-10">
                    {tmpl.has_active_artwork ? (
                      <Badge className="bg-indigo-600 text-white font-semibold text-xs shadow-sm gap-1.5 px-2.5 py-1">
                        <CheckCircle2 size={13} />
                        Artwork Applied
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="bg-slate-900/80 text-slate-300 border border-slate-700 text-xs font-medium gap-1.5 px-2.5 py-1 backdrop-blur-md">
                        <AlertCircle size={13} className="text-slate-400" />
                        Base Template
                      </Badge>
                    )}
                  </div>

                  {/* Envelope Type Badge */}
                  <div className="absolute top-3 right-3 z-10">
                    <Badge variant="outline" className="bg-slate-900/80 text-indigo-300 border border-slate-700 text-xs font-mono uppercase font-bold px-2 py-0.5">
                      {tmpl.envelope_type}
                    </Badge>
                  </div>

                  {/* Hover Overlay Button */}
                  <div className="absolute inset-0 bg-slate-950/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center z-20">
                    <span className="bg-white text-slate-900 px-4 py-2 rounded-full text-xs font-bold flex items-center gap-2 shadow-lg">
                      <Maximize2 size={14} className="text-indigo-600" /> Inspect Base PDF
                    </span>
                  </div>
                </div>

                {/* Details Section */}
                <div className="p-5 flex flex-col justify-between flex-1 space-y-4">
                  <div className="space-y-3">
                    <h3 className="font-bold text-base text-slate-900 dark:text-slate-100">{tmpl.display_name}</h3>

                    {/* Specification Box */}
                    <div className="text-xs space-y-2 p-3 bg-slate-50 dark:bg-slate-900/60 rounded-xl border border-slate-200 dark:border-slate-800">
                      <div className="flex justify-between items-center">
                        <span className="text-slate-600 dark:text-slate-400 font-medium">Recommended Artwork:</span>
                        <span className="font-mono font-bold text-indigo-600 dark:text-indigo-400 text-xs">{tmpl.sample_img_size}</span>
                      </div>
                      <div className="flex justify-between items-center border-t border-slate-200/60 dark:border-slate-800/80 pt-2">
                        <span className="text-slate-600 dark:text-slate-400 font-medium">Placeholder Box:</span>
                        <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold text-xs">{tmpl.box_size}</span>
                      </div>
                    </div>

                    {/* Active Artwork Status */}
                    {tmpl.active_artwork && (
                      <div className="rounded-xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900/50 p-3 text-xs space-y-1.5">
                        <div className="font-semibold text-indigo-900 dark:text-indigo-200 truncate flex items-center gap-2">
                          <ImageIcon size={14} className="text-indigo-600 dark:text-indigo-400" />
                          <span>{tmpl.active_artwork.filename}</span>
                        </div>
                        <div className="flex justify-between text-slate-500 dark:text-slate-400 text-xs">
                          <span>Size: {tmpl.active_artwork.image_size}</span>
                          <span className="font-bold uppercase text-indigo-600 dark:text-indigo-400">{tmpl.active_artwork.status}</span>
                        </div>
                        <button
                          type="button"
                          className="text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:underline pt-1 flex items-center gap-1.5"
                          onClick={() => {
                            setSelectedPdf({
                              url: activeOutputPdfViewUrl,
                              pngUrl: activeOutputPngUrl,
                              title: `${tmpl.display_name} (Composited Output)`,
                              downloadUrl: activeOutputPdfDownloadUrl,
                            })
                            setModalViewMode('image')
                          }}
                        >
                          <Eye size={13} /> View Composited Result PDF
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="grid grid-cols-2 gap-2.5 pt-2 border-t border-slate-100 dark:border-slate-800">
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs font-semibold gap-1.5 h-9"
                      onClick={() => {
                        setSelectedPdf({
                          url: basePdfViewUrl,
                          pngUrl: basePngPreviewUrl,
                          title: `${tmpl.display_name} (Base Template)`,
                          downloadUrl: basePdfDownloadUrl,
                        })
                        setModalViewMode('image')
                      }}
                    >
                      <Eye size={14} />
                      Inspect Base
                    </Button>

                    <Link to={`/envelope-handler/manager?template=${tmpl.id}`} className="block">
                      <Button className="w-full text-xs font-semibold gap-1.5 h-9 bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-white text-white dark:text-slate-900 shadow-sm">
                        <Edit3 size={14} />
                        Manage Artwork
                      </Button>
                    </Link>
                  </div>
                </div>
              </motion.div>
            )
          })
        )}
      </div>

      {/* Guidelines Card */}
      <Card className="border-rose-300 dark:border-rose-900/80 bg-gradient-to-br from-rose-50/80 via-rose-50/40 to-card dark:from-rose-950/40 dark:via-slate-900/60 dark:to-card shadow-md rounded-2xl overflow-hidden">
        <CardHeader className="pb-3 border-b border-rose-200/80 dark:border-rose-900/50 bg-rose-50/50 dark:bg-rose-950/30">
          <CardTitle className="text-sm font-bold flex items-center gap-2 text-rose-950 dark:text-rose-200">
            <Sparkles size={16} className="text-rose-600 dark:text-rose-400" />
            Artwork Size & Format Specifications
          </CardTitle>
          <CardDescription className="text-xs text-rose-900/70 dark:text-rose-300/70">
            Ensure uploaded campaign images match the recommended dimensions for optimal print output.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl border border-rose-200/90 dark:border-rose-900/50 bg-rose-50/60 dark:bg-rose-950/40 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-rose-950 dark:text-rose-100">1. Large Envelope</span>
                <Badge variant="outline" className="text-xs font-mono border-rose-300 dark:border-rose-800 text-rose-700 dark:text-rose-300">Square</Badge>
              </div>
              <div className="text-xs text-slate-700 dark:text-slate-300 space-y-1">
                <div>Recommended Size: <strong className="text-rose-700 dark:text-rose-400 font-mono">833 × 817 px</strong></div>
                <div>Aspect Ratio: <span className="font-mono text-slate-900 dark:text-slate-100 font-semibold">0.70 – 1.40</span></div>
              </div>
            </div>

            <div className="p-4 rounded-xl border border-rose-200/90 dark:border-rose-900/50 bg-rose-50/60 dark:bg-rose-950/40 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-rose-950 dark:text-rose-100">2. Medium Envelope</span>
                <Badge variant="outline" className="text-xs font-mono border-rose-300 dark:border-rose-800 text-rose-700 dark:text-rose-300">Landscape</Badge>
              </div>
              <div className="text-xs text-slate-700 dark:text-slate-300 space-y-1">
                <div>Recommended Size: <strong className="text-rose-700 dark:text-rose-400 font-mono">1179 × 618 px</strong></div>
                <div>Aspect Ratio: <span className="font-mono text-slate-900 dark:text-slate-100 font-semibold">1.50 – 2.50</span></div>
              </div>
            </div>

            <div className="p-4 rounded-xl border border-rose-200/90 dark:border-rose-900/50 bg-rose-50/60 dark:bg-rose-950/40 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-rose-950 dark:text-rose-100">3. Self-Seal A4</span>
                <Badge variant="outline" className="text-xs font-mono border-rose-300 dark:border-rose-800 text-rose-700 dark:text-rose-300">Banner</Badge>
              </div>
              <div className="text-xs text-slate-700 dark:text-slate-300 space-y-1">
                <div>Recommended Size: <strong className="text-rose-700 dark:text-rose-400 font-mono">1070 × 361 px</strong></div>
                <div>Aspect Ratio: <span className="font-mono text-slate-900 dark:text-slate-100 font-semibold">2.50 – 4.50</span></div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Inspection Modal */}
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
                  <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs font-semibold text-white">
                    <button
                      type="button"
                      onClick={() => setModalViewMode('image')}
                      className={`px-3 py-1 rounded-md transition-colors ${modalViewMode === 'image' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
                    >
                      Image Preview
                    </button>
                    <button
                      type="button"
                      onClick={() => setModalViewMode('pdf')}
                      className={`px-3 py-1 rounded-md transition-colors ${modalViewMode === 'pdf' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
                    >
                      Inline PDF
                    </button>
                  </div>

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

              <div className="flex-1 bg-slate-950 p-4 overflow-auto flex items-center justify-center">
                {modalViewMode === 'pdf' ? (
                  <iframe
                    src={`${selectedPdf.url}#toolbar=0&navpanes=0&view=Fit`}
                    title={selectedPdf.title}
                    className="w-full h-full bg-white rounded-xl border border-slate-800"
                  />
                ) : (
                  <img
                    src={selectedPdf.pngUrl}
                    alt={selectedPdf.title}
                    className="max-h-full max-w-full object-contain rounded-lg shadow-2xl border border-slate-800"
                  />
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
