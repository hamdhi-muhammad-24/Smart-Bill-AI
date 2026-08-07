import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { LayoutTemplate, Loader2, CheckCircle2, Maximize2, X, Download } from 'lucide-react'
import { getTemplates, fetchTemplatePreviewBlobUrl } from '../../lib/api'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { motion, AnimatePresence } from 'framer-motion'

export default function InvoiceTemplates() {
  const { data, isLoading } = useQuery({
    queryKey: ['billing-templates'],
    queryFn: getTemplates,
  })

  const [selectedPdf, setSelectedPdf] = useState<string | null>(null)
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!data?.templates) return

    const urls: Record<string, string> = {}
    
    const fetchPreviews = async () => {
      for (const template of data.templates) {
        try {
          const url = await fetchTemplatePreviewBlobUrl(template.id)
          urls[template.id] = url
          setPreviewUrls(prev => ({ ...prev, [template.id]: url }))
        } catch (err) {
          console.warn(`Failed to fetch preview for ${template.id}:`, err)
        }
      }
    }

    fetchPreviews()

    return () => {
      Object.values(urls).forEach(url => URL.revokeObjectURL(url))
    }
  }, [data])

  const getTemplateFallbackPdf = (name: string, id: string) => {
    const lowerName = name.toLowerCase()
    const lowerId = id.toLowerCase()
    if (lowerId.includes('enterprise') || lowerName.includes('enterprise')) return '/templates/nonvat_enterprise.pdf'
    if (lowerId.includes('home') || lowerName.includes('home')) return '/templates/nonvat_home.pdf'
    if (lowerId.includes('summary') || lowerName.includes('summary')) return '/templates/summary_statement.pdf'
    if (lowerId.includes('grouping') || lowerName.includes('grouping')) return '/templates/product_label_grouping.pdf'
    if (lowerId.includes('subscription') || lowerName.includes('subscription')) return '/templates/subscription_ref_grouping.pdf'
    return '/templates/invoice_of_summary.pdf'
  }

  return (
    <div className="flex flex-col gap-6 max-w-6xl mx-auto pb-10">
      <PageHeader 
        title="Invoice Base Templates" 
        description="Available fixed layout templates for SLT billing generation." 
      />

      {isLoading ? (
        <div className="flex justify-center p-12">
          <Loader2 className="animate-spin text-muted-foreground size-8" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {data?.templates.map((template: any) => {
            const pdfUrl = previewUrls[template.id] || getTemplateFallbackPdf(template.name, template.id)
            return (
              <motion.div 
                whileHover={{ y: -4 }}
                key={template.id} 
                className="flex flex-col rounded-xl border bg-card shadow-sm overflow-hidden transition-all hover:shadow-lg group"
              >
                <div 
                  className="h-64 bg-slate-100 relative cursor-pointer overflow-hidden border-b"
                  onClick={() => setSelectedPdf(pdfUrl)}
                >
                  <div className="absolute inset-0 pointer-events-none">
                    <iframe 
                      src={`${pdfUrl}#toolbar=0&navpanes=0&scrollbar=0&view=FitH`} 
                      title={template.name}
                      className="w-[140%] h-[140%] origin-top-left scale-[0.71] bg-white pointer-events-none"
                    />
                  </div>
                  
                  <div className="absolute inset-0 bg-black/5 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span className="bg-white/95 text-slate-900 px-4 py-2 rounded-full text-sm font-medium flex items-center gap-2 shadow-sm backdrop-blur-sm transform translate-y-4 group-hover:translate-y-0 transition-transform">
                      <Maximize2 size={16} /> View Layout PDF
                    </span>
                  </div>
                </div>
                
                <div className="p-5 flex flex-col gap-2 bg-card border-t border-border/40">
                  <div className="flex justify-between items-start">
                    <h3 className="font-semibold text-lg text-foreground">{template.name}</h3>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ring-inset shadow-xs ${
                      template.ready 
                        ? 'bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-950/20 dark:text-emerald-400' 
                        : 'bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-950/20 dark:text-amber-400'
                    }`}>
                      <CheckCircle2 size={12} className={`mr-1 ${template.ready ? 'text-emerald-500' : 'text-amber-500'}`} /> {template.ready ? 'Active' : 'Draft'}
                    </span>
                  </div>
                  <p className="text-xs font-mono text-muted-foreground">Template ID: {template.id}</p>
                  
                  <div className="mt-4 flex flex-wrap gap-2 items-center justify-end w-full">
                    <button 
                      className="text-xs flex items-center gap-1.5 text-primary hover:text-primary/80 font-bold transition-all hover:translate-x-0.5"
                      onClick={(e) => {
                        e.stopPropagation();
                        const a = document.createElement('a');
                        a.href = pdfUrl;
                        a.download = `${template.name}_template.pdf`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                      }}
                    >
                      <Download size={14} /> Download Sample
                    </button>
                  </div>
                </div>
              </motion.div>
            )
          })}
          
          {data?.templates.length === 0 && (
            <div className="col-span-full text-center p-12 border border-dashed rounded-xl text-muted-foreground bg-slate-50/50">
              <LayoutTemplate size={48} className="mx-auto mb-4 opacity-20" />
              <p>No base templates discovered in the engine.</p>
            </div>
          )}
        </div>
      )}

      {/* Full Screen PDF Modal */}
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
              className="relative max-h-full max-w-5xl w-full h-[90vh] flex flex-col bg-slate-100 rounded-xl overflow-hidden shadow-2xl border border-white/10"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="absolute top-4 right-4 z-10 flex gap-2">
                <button 
                  className="text-slate-600 hover:text-slate-900 bg-white/80 hover:bg-white rounded-full p-2 shadow-sm transition-colors backdrop-blur-sm"
                  onClick={() => setSelectedPdf(null)}
                >
                  <X size={20} />
                </button>
              </div>
              
              <iframe 
                src={`${selectedPdf}#toolbar=0&navpanes=0`} 
                title="Full Template Preview" 
                className="w-full h-full bg-white"
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
