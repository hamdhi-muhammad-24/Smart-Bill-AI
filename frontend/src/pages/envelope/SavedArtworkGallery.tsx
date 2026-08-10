import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Layers, Download, Trash2, Send, Eye, RefreshCw, X, Maximize2, Filter
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { toast } from 'sonner'
import { motion, AnimatePresence } from 'framer-motion'

interface SavedArtwork {
  id: number
  template_id: number
  envelope_type: string
  display_name: string
  original_filename: string
  campaign_name: string
  image_size: string
  output_pdf_path?: string
  status: string
  rejection_reason?: string
  uploaded_by?: string
  created_at: string
}

const API_BASE = 'http://localhost:8090'

async function fetchSavedArtworks(envelopeType?: string, status?: string): Promise<SavedArtwork[]> {
  const params = new URLSearchParams()
  if (envelopeType && envelopeType !== 'ALL') params.append('envelope_type', envelopeType)
  if (status && status !== 'ALL') params.append('status', status)
  const res = await fetch(`${API_BASE}/api/envelope/artworks?${params.toString()}`)
  if (!res.ok) throw new Error('Failed to fetch saved artworks')
  return res.json()
}

export default function SavedArtworkGallery() {
  const queryClient = useQueryClient()
  const [selectedType, setSelectedType] = useState<string>('ALL')
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL')

  // Full Screen PDF Inspection Modal
  const [selectedPdf, setSelectedPdf] = useState<{
    url: string
    pngUrl: string
    title: string
    downloadUrl: string
  } | null>(null)

  const [modalViewMode, setModalViewMode] = useState<'image' | 'pdf'>('image')

  const { data: artworks, isLoading, refetch } = useQuery({
    queryKey: ['savedArtworks', selectedType, selectedStatus],
    queryFn: () => fetchSavedArtworks(selectedType, selectedStatus),
    refetchInterval: 5000,
  })

  // Submit Draft to Admin Mutation
  const submitMutation = useMutation({
    mutationFn: async (artworkId: number) => {
      const res = await fetch(`${API_BASE}/api/envelope/artworks/${artworkId}/submit`, { method: 'POST' })
      if (!res.ok) throw new Error('Failed to submit artwork')
      return res.json()
    },
    onSuccess: () => {
      toast.success('Artwork submitted for Admin review and approval!')
      queryClient.invalidateQueries({ queryKey: ['savedArtworks'] })
    },
  })

  // Delete Saved Draft Mutation
  const deleteMutation = useMutation({
    mutationFn: async (artworkId: number) => {
      const res = await fetch(`${API_BASE}/api/envelope/artworks/${artworkId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete artwork')
      return res.json()
    },
    onSuccess: () => {
      toast.success('Artwork permanently deleted from database!')
      queryClient.invalidateQueries({ queryKey: ['savedArtworks'] })
    },
  })

  // Delete All Saved Artworks Mutation
  const deleteAllMutation = useMutation({
    mutationFn: async () => {
      const params = new URLSearchParams()
      if (selectedType && selectedType !== 'ALL') params.append('envelope_type', selectedType)
      const res = await fetch(`${API_BASE}/api/envelope/artworks/all?${params.toString()}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('Failed to delete all artworks')
      return res.json()
    },
    onSuccess: (data) => {
      toast.success(data.message || 'All saved envelope artworks permanently deleted from database!')
      queryClient.invalidateQueries({ queryKey: ['savedArtworks'] })
    },
  })

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-10">
      <PageHeader
        title="Saved Artwork Gallery"
        description="View all saved envelope artwork variations, inspect draft previews, or submit campaign designs for Admin approval."
        breadcrumbs={[
          { label: 'Envelope Portal', to: '/envelope-handler' },
          { label: 'Saved Gallery' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              className="gap-2 text-xs font-semibold h-9"
            >
              <RefreshCw size={14} className={isLoading ? "animate-spin text-indigo-500" : ""} />
              Refresh Gallery
            </Button>
            {artworks && artworks.length > 0 && (
              <Button
                variant="destructive"
                size="sm"
                className="gap-2 text-xs font-semibold h-9"
                onClick={() => {
                  if (window.confirm("ARE YOU SURE? This will PERMANENTLY delete ALL saved envelope artworks from the database and remove their files from disk!")) {
                    deleteAllMutation.mutate()
                  }
                }}
                disabled={deleteAllMutation.isPending}
              >
                <Trash2 size={14} />
                Delete All Envelopes
              </Button>
            )}
          </div>
        }
      />

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 bg-card border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm">
        {/* Envelope Type Filter Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full sm:w-auto">
          {['ALL', 'LARGE', 'MEDIUM', 'SELF_SEAL'].map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => setSelectedType(type)}
              className={`px-3.5 py-1.5 text-xs font-semibold rounded-xl transition-all ${
                selectedType === type
                  ? 'bg-indigo-600 text-white font-bold shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              {type === 'ALL' ? 'All Formats' : type.replace('_', ' ')}
            </button>
          ))}
        </div>

        {/* Status Filter Dropdown / Buttons */}
        <div className="flex items-center gap-2 text-xs">
          <Filter size={14} className="text-slate-400" />
          <span className="text-slate-500 font-medium">Status:</span>
          {['ALL', 'DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED'].map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setSelectedStatus(st)}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors ${
                selectedStatus === st
                  ? 'bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 font-bold'
                  : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Artworks Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="animate-pulse rounded-2xl">
              <CardHeader className="h-28 bg-muted/30" />
              <CardContent className="h-48" />
            </Card>
          ))}
        </div>
      ) : artworks && artworks.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {artworks.map((art) => {
            const pngPreviewUrl = `${API_BASE}/api/envelope/artworks/${art.id}/preview`
            const pdfViewUrl = `${API_BASE}/api/envelope/artworks/${art.id}/view-pdf`
            const pdfDownloadUrl = `${API_BASE}/api/envelope/artworks/${art.id}/download`

            return (
              <motion.div
                key={art.id}
                whileHover={{ y: -4 }}
                transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                className="flex flex-col rounded-2xl border border-slate-200 dark:border-slate-800 bg-card shadow-sm overflow-hidden transition-all hover:shadow-xl group"
              >
                {/* Thumbnail Preview */}
                <div
                  className="h-56 bg-slate-950 relative cursor-pointer overflow-hidden border-b border-slate-800 flex items-center justify-center p-3"
                  onClick={() => {
                    setSelectedPdf({
                      url: pdfViewUrl,
                      pngUrl: pngPreviewUrl,
                      title: `${art.display_name} - ${art.campaign_name}`,
                      downloadUrl: pdfDownloadUrl,
                    })
                    setModalViewMode('image')
                  }}
                >
                  <img
                    src={pngPreviewUrl}
                    alt={art.campaign_name}
                    className="max-h-full max-w-full object-contain rounded-lg transition-transform duration-300 group-hover:scale-105"
                  />

                  {/* Status Badge */}
                  <div className="absolute top-3 left-3 z-10">
                    <Badge className={`text-xs font-semibold shadow-sm px-2.5 py-0.5 ${
                      art.status === 'APPROVED' ? 'bg-indigo-600 text-white' :
                      art.status === 'SUBMITTED' ? 'bg-amber-600 text-white' :
                      art.status === 'REJECTED' ? 'bg-rose-600 text-white' :
                      'bg-slate-800 text-slate-200 border border-slate-700'
                    }`}>
                      {art.status}
                    </Badge>
                  </div>

                  {/* Envelope Type Badge */}
                  <div className="absolute top-3 right-3 z-10">
                    <Badge variant="outline" className="bg-slate-900/80 text-indigo-300 border border-slate-700 text-xs font-mono uppercase font-bold px-2 py-0.5">
                      {art.envelope_type}
                    </Badge>
                  </div>

                  {/* Hover Inspect Overlay */}
                  <div className="absolute inset-0 bg-slate-950/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center z-20">
                    <span className="bg-white text-slate-900 px-3.5 py-2 rounded-full text-xs font-bold flex items-center gap-2 shadow-lg">
                      <Maximize2 size={14} className="text-indigo-600" /> Inspect Composite PDF
                    </span>
                  </div>
                </div>

                {/* Details Section */}
                <div className="p-5 flex flex-col justify-between flex-1 space-y-4">
                  <div className="space-y-2">
                    <h4 className="font-bold text-sm text-slate-900 dark:text-slate-100 truncate">{art.campaign_name}</h4>
                    <p className="text-xs text-slate-500 font-mono">{art.display_name} • {art.image_size}</p>

                    {art.rejection_reason && (
                      <p className="text-xs text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40 p-2 rounded-lg border border-rose-200 dark:border-rose-900/50">
                        Reason: {art.rejection_reason}
                      </p>
                    )}
                  </div>

                  {/* Action Buttons */}
                  <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs font-semibold gap-1.5 h-8"
                        onClick={() => {
                          setSelectedPdf({
                            url: pdfViewUrl,
                            pngUrl: pngPreviewUrl,
                            title: `${art.display_name} - ${art.campaign_name}`,
                            downloadUrl: pdfDownloadUrl,
                          })
                          setModalViewMode('image')
                        }}
                      >
                        <Eye size={13} />
                        Inspect
                      </Button>

                      <a href={pdfDownloadUrl} download target="_blank" rel="noreferrer" className="block">
                        <Button variant="outline" size="sm" className="w-full text-xs font-semibold gap-1.5 h-8">
                          <Download size={13} />
                          Download
                        </Button>
                      </a>
                    </div>

                    <div className="flex gap-2">
                      {art.status === 'DRAFT' && (
                        <Button
                          size="sm"
                          className="flex-1 text-xs font-semibold gap-1.5 h-8 bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm"
                          onClick={() => submitMutation.mutate(art.id)}
                          disabled={submitMutation.isPending}
                        >
                          <Send size={13} />
                          Submit to Admin
                        </Button>
                      )}

                      <Button
                        variant="destructive"
                        size="sm"
                        className={`text-xs font-semibold gap-1.5 h-8 ${art.status === 'DRAFT' ? 'px-3' : 'w-full'}`}
                        onClick={() => {
                          if (window.confirm(`Are you sure you want to delete "${art.campaign_name}"?`)) {
                            deleteMutation.mutate(art.id)
                          }
                        }}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 size={13} />
                        {art.status !== 'DRAFT' && <span>Delete Envelope</span>}
                      </Button>
                    </div>
                  </div>
                </div>
              </motion.div>
            )
          })}
        </div>
      ) : (
        <Card className="border-slate-200 dark:border-slate-800 p-12 text-center rounded-2xl">
          <div className="size-12 rounded-2xl bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mx-auto mb-3">
            <Layers size={24} />
          </div>
          <h4 className="font-bold text-base text-slate-900 dark:text-slate-100">No Saved Envelope Artworks Found</h4>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Upload promotional campaign images in the Envelope Manager to save drafts or submit to Admin.
          </p>
        </Card>
      )}

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
                <h3 className="font-bold text-sm text-white">{selectedPdf.title}</h3>

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

              <div className="flex-1 bg-slate-950 p-2 overflow-hidden">
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
