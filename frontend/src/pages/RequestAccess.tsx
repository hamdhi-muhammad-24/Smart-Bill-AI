import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, FileStack, Mail, Users, CheckCircle2, ArrowLeft, Sparkles } from 'lucide-react'
import { requestAccess } from '../lib/api'
import { useAuth } from '../auth/AuthProvider'
import Brand from '../components/Brand'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

const PORTALS = [
  {
    id: 'ADMIN',
    label: 'System Administration',
    desc: 'Invoice pipeline, GMF monitoring, full system control.',
    icon: ShieldCheck,
    color: '#00b2e3',
  },
  {
    id: 'GMF_HANDLER',
    label: 'GMF Handler Portal',
    desc: 'Upload and process GMF batch files and billing cycles.',
    icon: FileStack,
    color: '#40b4e5',
  },
  {
    id: 'ENVELOPE_HANDLER',
    label: 'Envelope Handler Portal',
    desc: 'Manage envelope artwork and print-ready composite PDFs.',
    icon: Mail,
    color: '#a78bfa',
  },
  {
    id: 'MANAGER',
    label: 'User Management Portal',
    desc: 'Provision staff accounts and manage role permissions.',
    icon: Users,
    color: '#00e676',
  },
]

export default function RequestAccess() {
  const { session, logout } = useAuth()
  const navigate = useNavigate()

  const [selectedRoles, setSelectedRoles] = useState<string[]>([])
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const userEmail = session?.email ?? ''

  function toggleRole(roleId: string) {
    setSelectedRoles(prev =>
      prev.includes(roleId) ? prev.filter(r => r !== roleId) : [...prev, roleId]
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (selectedRoles.length === 0) {
      toast.warning('Please select at least one portal to request access to.')
      return
    }
    setLoading(true)
    try {
      await requestAccess({
        email: userEmail,
        requested_roles: selectedRoles,
        reason: reason.trim() || undefined,
      })
      setSubmitted(true)
    } catch (err: any) {
      toast.error(err?.detail || 'Failed to submit request. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    return (
      <div className="min-h-svh bg-background flex flex-col items-center justify-center px-4 relative overflow-hidden">
        <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-[600px] h-[400px] rounded-full bg-[#00a651]/10 blur-[120px] pointer-events-none" />
        <div className="relative z-10 text-center max-w-md mx-auto space-y-6">
          <div className="flex justify-center">
            <div className="flex size-20 items-center justify-center rounded-full bg-[#00a651]/15 text-[#00a651]">
              <CheckCircle2 size={40} />
            </div>
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-foreground">Request Submitted!</h1>
            <p className="mt-3 text-sm font-medium text-muted-foreground leading-relaxed">
              Your access request has been sent to a User Manager for review. You'll be notified once it's approved.
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              Submitted as: <span className="text-foreground font-semibold">{userEmail}</span>
            </p>
          </div>
          <div className="flex flex-col gap-3">
            <Button
              onClick={() => navigate('/login')}
              variant="outline"
              className="h-11 rounded-xl text-xs font-bold"
            >
              Return to Login
            </Button>
            <Button
              onClick={logout}
              className="h-11 rounded-xl text-xs font-bold bg-gradient-to-r from-[#0066b3] to-[#00b2e3] text-white border-none"
            >
              Sign Out
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-svh bg-background relative overflow-hidden">
      {/* Ambient glows */}
      <div className="absolute -top-24 -left-24 w-[450px] h-[450px] rounded-full bg-[#0066b3]/10 blur-[100px] pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-[#00a651]/8 blur-[100px] pointer-events-none" />

      {/* Header */}
      <header className="relative z-10 flex items-center justify-between px-6 sm:px-10 h-16 border-b border-border/50 bg-background/80 backdrop-blur-md">
        <Brand size="md" />
        <Button
          variant="ghost"
          size="sm"
          className="gap-2 text-xs font-bold text-muted-foreground hover:text-foreground"
          onClick={logout}
        >
          <ArrowLeft size={14} />
          Sign Out
        </Button>
      </header>

      <main className="relative z-10 max-w-xl mx-auto px-4 sm:px-6 py-12">
        {/* Hero */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-muted/40 px-4 py-2 text-xs font-bold tracking-widest text-muted-foreground uppercase mb-5">
            <Sparkles size={12} className="text-[#00b2e3]" />
            New User Registration
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground mb-2">
            Request Portal Access
          </h1>
          <p className="text-sm font-medium text-muted-foreground max-w-sm mx-auto">
            Welcome! Your Microsoft account has been verified but hasn't been granted portal access yet. Select the portals you need below.
          </p>
          <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-border/60 bg-muted/30 px-4 py-2 text-xs font-semibold text-muted-foreground">
            Signed in as: <span className="text-foreground font-bold ml-1">{userEmail}</span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Portal selection */}
          <div className="space-y-3">
            <p className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
              Select portals you need access to
            </p>
            {PORTALS.map((p) => {
              const Icon = p.icon
              const selected = selectedRoles.includes(p.id)
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => toggleRole(p.id)}
                  className={`
                    w-full text-left flex items-center gap-4 p-4 rounded-xl border transition-all duration-200
                    ${selected
                      ? 'border-transparent bg-background shadow-md'
                      : 'border-border/40 bg-background/50 hover:bg-background/80'
                    }
                  `}
                  style={selected ? {
                    boxShadow: `0 0 0 2px ${p.color}66, 0 4px 20px ${p.color}18`,
                  } : {}}
                >
                  {/* Checkbox */}
                  <div
                    className="flex size-5 shrink-0 items-center justify-center rounded-md border-2 transition-all"
                    style={selected
                      ? { background: p.color, borderColor: p.color }
                      : { borderColor: 'var(--border)' }
                    }
                  >
                    {selected && (
                      <svg viewBox="0 0 12 12" className="size-3 text-white fill-white">
                        <path d="M2 6l3 3 5-5" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                      </svg>
                    )}
                  </div>

                  {/* Icon */}
                  <div
                    className="flex size-9 shrink-0 items-center justify-center rounded-lg text-white"
                    style={{ background: `${p.color}22`, color: p.color }}
                  >
                    <Icon size={18} />
                  </div>

                  {/* Label */}
                  <div>
                    <p className="text-sm font-bold text-foreground">{p.label}</p>
                    <p className="text-[11px] font-medium text-muted-foreground mt-0.5">{p.desc}</p>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Reason */}
          <div className="space-y-2">
            <label className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground">
              Reason / Business Justification <span className="font-normal normal-case">(optional)</span>
            </label>
            <textarea
              rows={3}
              placeholder="Briefly explain why you need access to the selected portals..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm font-medium text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[#0066b3] resize-none transition-all"
            />
          </div>

          {/* Submit */}
          <Button
            type="submit"
            disabled={loading || selectedRoles.length === 0}
            className="w-full h-12 rounded-xl font-extrabold text-sm text-white border-none bg-gradient-to-r from-[#0066b3] to-[#00b2e3] shadow-lg shadow-[#0066b3]/25 hover:opacity-90 disabled:opacity-50 transition-all"
          >
            {loading ? (
              <span className="flex items-center gap-2.5">
                <span className="size-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                Submitting Request...
              </span>
            ) : (
              `Submit Access Request${selectedRoles.length > 0 ? ` (${selectedRoles.length} portal${selectedRoles.length > 1 ? 's' : ''})` : ''}`
            )}
          </Button>

          <p className="text-center text-[11px] font-medium text-muted-foreground">
            A User Manager will review your request and grant access as appropriate.
          </p>
        </form>
      </main>
    </div>
  )
}
