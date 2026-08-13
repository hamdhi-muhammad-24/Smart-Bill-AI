import { useState } from 'react'
import { Lock, ShieldOff, CheckCircle2, X } from 'lucide-react'
import { requestAccess } from '../lib/api'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface Props {
  portalId: string
  portalLabel: string
  userEmail: string
  onClose: () => void
}

const PORTAL_ACCENT: Record<string, string> = {
  ADMIN: '#00b2e3',
  GMF_HANDLER: '#40b4e5',
  ENVELOPE_HANDLER: '#a78bfa',
  MANAGER: '#00e676',
}

export default function NoAccessModal({ portalId, portalLabel, userEmail, onClose }: Props) {
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const accent = PORTAL_ACCENT[portalId] || '#00b2e3'

  async function handleRequest() {
    setLoading(true)
    try {
      await requestAccess({
        email: userEmail,
        requested_roles: [portalId],
        reason: reason.trim() || undefined,
      })
      setSubmitted(true)
      toast.success('Access request submitted! A manager will review it shortly.')
    } catch (err: any) {
      toast.error(err?.detail || 'Failed to submit request. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-2xl border border-border/60 bg-background shadow-2xl overflow-hidden">
        {/* Top accent bar */}
        <div className="h-1 w-full" style={{ background: `linear-gradient(90deg, ${accent}44, ${accent})` }} />

        <div className="p-6 space-y-5">
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-5 right-5 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X size={18} />
          </button>

          {submitted ? (
            /* Success state */
            <div className="text-center py-6 space-y-4">
              <div className="flex justify-center">
                <div className="flex size-16 items-center justify-center rounded-full bg-[#00a651]/10 text-[#00a651]">
                  <CheckCircle2 size={32} />
                </div>
              </div>
              <div>
                <h3 className="text-lg font-extrabold text-foreground">Request Submitted!</h3>
                <p className="text-sm font-medium text-muted-foreground mt-2 leading-relaxed">
                  Your request to access <span className="text-foreground font-bold">{portalLabel}</span> has been sent to a User Manager for review.
                </p>
              </div>
              <Button
                onClick={onClose}
                className="h-10 rounded-xl text-xs font-bold bg-gradient-to-r from-[#00a651] to-teal-600 text-white border-none"
              >
                Close
              </Button>
            </div>
          ) : (
            /* Request form */
            <>
              {/* Icon + title */}
              <div className="flex items-start gap-4">
                <div
                  className="flex size-12 shrink-0 items-center justify-center rounded-xl"
                  style={{ background: `${accent}18`, color: accent }}
                >
                  <ShieldOff size={22} />
                </div>
                <div>
                  <h3 className="text-lg font-extrabold text-foreground leading-tight">
                    No Access
                  </h3>
                  <p className="text-xs font-medium text-muted-foreground mt-0.5">
                    You don't have permission to access{' '}
                    <span className="text-foreground font-bold">{portalLabel}</span>.
                  </p>
                </div>
              </div>

              {/* Info box */}
              <div className="flex items-start gap-3 rounded-xl bg-muted/40 border border-border/40 p-4">
                <Lock size={14} className="text-muted-foreground mt-0.5 shrink-0" />
                <p className="text-xs font-medium text-muted-foreground leading-relaxed">
                  Your Microsoft account (<span className="text-foreground font-semibold">{userEmail}</span>) is not authorized for this portal. Request access below and a User Manager will review your request.
                </p>
              </div>

              {/* Reason textarea */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-foreground">
                  Reason for requesting access <span className="text-muted-foreground font-normal">(optional)</span>
                </label>
                <textarea
                  rows={3}
                  placeholder="Briefly describe why you need access to this portal..."
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-medium text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[#0066b3] resize-none"
                />
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-3 pt-1">
                <Button
                  variant="outline"
                  onClick={onClose}
                  className="h-10 rounded-xl text-xs font-bold"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleRequest}
                  disabled={loading}
                  className="h-10 rounded-xl text-xs font-bold text-white border-none"
                  style={{ background: `linear-gradient(135deg, ${accent}cc, ${accent})` }}
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="size-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                      Submitting...
                    </span>
                  ) : (
                    'Request Access'
                  )}
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
