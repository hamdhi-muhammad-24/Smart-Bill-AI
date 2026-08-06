import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle2, AlertCircle, RefreshCw, Upload, Sparkles, ImageIcon, Edit3, Maximize2, Download, X, Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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

const API_BASE = 'http://localhost:8090'

async function fetchEnvelopeTemplates(): Promise<EnvelopeTemplateInfo[]> {
  const res = await fetch(`${API_BASE}/api/envelope/templates`)
  if (!res.ok) throw new Error('Failed to fetch envelope templates')
  return res.json()
}

export default function EnvelopeDashboard() {
  const { data: templates, isLoading, refetch } = useQuery({
    queryKey: ['envelopeTemplates'],
    queryFn: fetchEnvelopeTemplates,
    refetchInterval: 10000,
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
    <div className="space-y-6 max-w-7xl mx-auto">
      <PageHeader
        title="Envelope Promotional Image Portal"
        description="View SLT's 3 physical base envelope templates below. Always displays the empty base template layout by default. Click any base envelope card to inspect the full layout PDF or edit & upload promotional campaign artwork."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()} className="gap-2 text-xs font-bold">
              <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
              Refresh
            </Button>
            <Link to="/envelope-handler/manager">
              <Button size="sm" className="gap-2 text-xs font-bold bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md">
                <Upload size={13} />
                Envelope Manager
              </Button>
            </Link>
          </div>
        }
      />

      {/* 3 Base Envelope Default Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader className="h-24 bg-muted/40" />
              <CardContent className="h-44" />
            </Card>
          ))
        ) : (
          templates?.map((tmpl) => {
            // ALWAYS display the base empty envelope template preview by default on the dashboard
            const basePngPreviewUrl = `${API_BASE}/api/envelope/templates/${tmpl.id}/preview-base`
            const basePdfViewUrl = `${API_BASE}/api/envelope/templates/${tmpl.id}/base-pdf`
            const basePdfDownloadUrl = `${API_BASE}/api/envelope/templates/${tmpl.id}/download-base-pdf`

            // Composited output URL if artwork applied
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
                key={tmpl.id}
                className="flex flex-col rounded-xl border border-border/80 bg-card shadow-sm overflow-hidden transition-all hover:shadow-xl group"
              >
                {/* ALWAYS display the Base Empty Envelope Template Image */}
                <div
                  className="h-64 bg-slate-950/90 relative cursor-pointer overflow-hidden border-b flex items-center justify-center p-3"
                  onClick={() => {
                    setSelectedPdf({
                      url: basePdfViewUrl,
                      pngUrl: basePngPreviewUrl,
                      title: `${tmpl.display_name} (Base Empty Template)`,
                      downloadUrl: basePdfDownloadUrl,
                    })
                    setModalViewMode('image')
                  }}
                >
                  <img
                    src={basePngPreviewUrl}
                    alt={tmpl.display_name}
                    className="max-h-full max-w-full object-contain rounded shadow-lg transition-transform duration-300 group-hover:scale-105 border border-white/10"
                  />

                  {/* Status Overlay Badge */}
                  <div className="absolute top-3 left-3 z-10">
                    <Badge variant={tmpl.has_active_artwork ? "default" : "secondary"} className={tmpl.has_active_artwork ? "bg-emerald-500/90 text-white font-semibold text-[11px] shadow-sm" : "bg-black/70 backdrop-blur-md text-white border-white/20 text-[11px] shadow-sm"}>
                      {tmpl.has_active_artwork ? (
                        <span className="flex items-center gap-1">
                          <CheckCircle2 size={12} />
                          Artwork Applied
                        </span>
                      ) : (
                        <span className="flex items-center gap-1">
                          <AlertCircle size={12} />
                          Empty Base Envelope
                        </span>
                      )}
                    </Badge>
                  </div>

                  {/* Type Badge */}
                  <div className="absolute top-3 right-3 z-10">
                    <Badge variant="outline" className="bg-blue-600/90 backdrop-blur-md text-white border-blue-400/40 text-[10px] font-mono uppercase font-bold shadow-sm">
                      {tmpl.envelope_type}
                    </Badge>
                  </div>

                  {/* Hover Overlay Button */}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center z-20">
                    <span className="bg-white/95 text-slate-900 px-4 py-2 rounded-full text-xs font-extrabold flex items-center gap-2 shadow-lg backdrop-blur-sm transform translate-y-3 group-hover:translate-y-0 transition-transform">
                      <Maximize2 size={15} /> Inspect Base PDF Layout
                    </span>
                  </div>
                </div>

                {/* Card Content & Details */}
                <div className="p-5 flex flex-col justify-between flex-1 space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between items-start">
                      <h3 className="font-extrabold text-base text-foreground">{tmpl.display_name}</h3>
                    </div>

                    <div className="text-xs space-y-1.5 pt-1 text-muted-foreground">
                      <div className="flex justify-between border-b pb-1">
                        <span>Sample Artwork Size:</span>
                        <strong className="text-foreground font-mono">{tmpl.sample_img_size}</strong>
                      </div>
                      <div className="flex justify-between border-b pb-1">
                        <span>Placeholder Box:</span>
                        <span className="font-mono text-foreground font-semibold">{tmpl.box_size}</span>
                      </div>
                    </div>

                    {tmpl.active_artwork ? (
                      <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-2.5 text-xs space-y-1 mt-2">
                        <div className="font-semibold text-emerald-400 truncate flex items-center gap-1.5">
                          <ImageIcon size={13} />
                          {tmpl.active_artwork.filename}
                        </div>
                        <div className="text-muted-foreground flex justify-between text-[11px]">
                          <span>Size: {tmpl.active_artwork.image_size}</span>
                          <span className="font-bold uppercase text-emerald-400">{tmpl.active_artwork.status}</span>
                        </div>
                        <button
                          type="button"
                          className="text-[11px] font-bold text-emerald-400 hover:underline pt-1 flex items-center gap-1"
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
                          <Eye size={12} /> View Composited Result PDF
                        </button>
                      </div>
                    ) : (
                      <div className="rounded-xl bg-muted/40 border border-dashed p-2.5 text-center text-xs text-muted-foreground mt-2">
                        Base template ready. Click below to edit & add artwork.
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="grid grid-cols-2 gap-2 pt-2 border-t">
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs font-bold gap-1.5"
                      onClick={() => {
                        setSelectedPdf({
                          url: basePdfViewUrl,
                          pngUrl: basePngPreviewUrl,
                          title: `${tmpl.display_name} (Base Empty Template)`,
                          downloadUrl: basePdfDownloadUrl,
                        })
                        setModalViewMode('image')
                      }}
                    >
                      <Eye size={13} />
                      Inspect Base
                    </Button>

                    <Link to={`/envelope-handler/manager?template=${tmpl.id}`} className="block">
                      <Button className="w-full text-xs font-bold gap-1.5 bg-gradient-to-r from-slate-900 to-blue-950 hover:from-black hover:to-blue-900 text-white shadow">
                        <Edit3 size={13} />
                        View & Edit Base
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
      <Card className="bg-muted/30 border-dashed">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-extrabold flex items-center gap-2 text-foreground">
            <Sparkles size={16} className="text-blue-400" />
            Envelope Promotional Image Validation Rules
          </CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-muted-foreground grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
          <div className="space-y-1 p-3 rounded-xl border bg-card">
            <div className="font-bold text-foreground">1. Large Envelope</div>
            <div>• Required Size: <strong className="font-mono text-blue-400">833x817 px</strong></div>
            <div>• Aspect Ratio: Near Square (0.70 – 1.40)</div>
          </div>
          <div className="space-y-1 p-3 rounded-xl border bg-card">
            <div className="font-bold text-foreground">2. Medium Envelope</div>
            <div>• Required Size: <strong className="font-mono text-blue-400">1179x618 px</strong></div>
            <div>• Aspect Ratio: Wide Landscape (1.50 – 2.50)</div>
          </div>
          <div className="space-y-1 p-3 rounded-xl border bg-card">
            <div className="font-bold text-foreground">3. Self-Seal A4 Envelope</div>
            <div>• Required Size: <strong className="font-mono text-blue-400">1070x361 px</strong></div>
            <div>• Aspect Ratio: Banner Strip (2.50 – 4.50)</div>
          </div>
        </CardContent>
      </Card>

      {/* Full Screen High-Definition Inspection Modal */}
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
              {/* Modal Header Bar */}
              <div className="px-6 py-4 bg-slate-950 border-b border-white/10 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                  <h3 className="font-extrabold text-base text-white">{selectedPdf.title}</h3>
                  <Badge variant="outline" className="text-[10px] font-mono text-blue-400 border-blue-500/30">
                    High-Definition Inspection
                  </Badge>
                </div>

                <div className="flex items-center gap-3">
                  {/* PNG vs PDF Viewer Toggle */}
                  <div className="flex bg-slate-900 border border-white/10 rounded-lg p-0.5 text-xs font-bold text-white">
                    <button
                      type="button"
                      onClick={() => setModalViewMode('image')}
                      className={`px-2.5 py-1 rounded-md transition-colors ${modalViewMode === 'image' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}
                    >
                      Image Preview
                    </button>
                    <button
                      type="button"
                      onClick={() => setModalViewMode('pdf')}
                      className={`px-2.5 py-1 rounded-md transition-colors ${modalViewMode === 'pdf' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}
                    >
                      Inline PDF
                    </button>
                  </div>

                  <a href={selectedPdf.downloadUrl} download target="_blank" rel="noreferrer">
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

              {/* Modal Viewer Content */}
              <div className="flex-1 bg-slate-950 p-4 overflow-auto flex items-center justify-center">
                {modalViewMode === 'pdf' ? (
                  <iframe
                    src={`${selectedPdf.url}#toolbar=0&navpanes=0&view=Fit`}
                    title={selectedPdf.title}
                    className="w-full h-full bg-white rounded-xl border border-white/10"
                  />
                ) : (
                  <img
                    src={selectedPdf.pngUrl}
                    alt={selectedPdf.title}
                    className="max-h-full max-w-full object-contain rounded shadow-2xl border border-white/10"
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
