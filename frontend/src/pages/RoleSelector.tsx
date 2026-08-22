import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lock, ShieldCheck, FileStack, Mail, Users, LogOut, ChevronRight, Sparkles } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import Brand from '../components/Brand'
import NoAccessModal from '../components/NoAccessModal'
import { Button } from '@/components/ui/button'

// Portal definitions
const PORTALS = [
  {
    id: 'ADMIN',
    routeRole: 'admin',
    path: '/admin',
    label: 'System Administration',
    subtitle: 'Invoice pipeline, GMF monitoring, template management, full system control.',
    icon: ShieldCheck,
    gradient: 'from-[#0066b3] to-[#0052a3]',
    glow: 'shadow-[#0066b3]/30',
    iconBg: 'bg-[#0066b3]/15 text-[#00b2e3]',
    border: 'border-[#0066b3]/30',
    accent: '#00b2e3',
  },
  {
    id: 'GMF_HANDLER',
    routeRole: 'gmf_handler',
    path: '/gmf-handler',
    label: 'GMF Handler Portal',
    subtitle: 'Upload and process GMF batch files, manage billing cycles and generation runs.',
    icon: FileStack,
    gradient: 'from-[#005f99] to-[#006db3]',
    glow: 'shadow-[#005f99]/30',
    iconBg: 'bg-[#005f99]/15 text-[#40b4e5]',
    border: 'border-[#005f99]/30',
    accent: '#40b4e5',
  },
  {
    id: 'ENVELOPE_HANDLER',
    routeRole: 'envelope_handler',
    path: '/envelope-handler',
    label: 'Envelope Handler Portal',
    subtitle: 'Manage envelope artwork, templates, and print-ready composite PDFs.',
    icon: Mail,
    gradient: 'from-[#6d28d9] to-[#7c3aed]',
    glow: 'shadow-purple-700/30',
    iconBg: 'bg-purple-700/15 text-purple-400',
    border: 'border-purple-700/30',
    accent: '#a78bfa',
  },
  {
    id: 'MANAGER',
    routeRole: 'manager',
    path: '/manager',
    label: 'User Management Portal',
    subtitle: 'Provision staff accounts, manage role permissions, review access requests.',
    icon: Users,
    gradient: 'from-[#00a651] to-[#00875a]',
    glow: 'shadow-[#00a651]/30',
    iconBg: 'bg-[#00a651]/15 text-[#00e676]',
    border: 'border-[#00a651]/30',
    accent: '#00e676',
  },
]

export default function RoleSelector() {
  const { session, logout } = useAuth()
  const navigate = useNavigate()
  const [noAccessModal, setNoAccessModal] = useState<{
    portalId: string
    portalLabel: string
  } | null>(null)

  function hasAccess(portalId: string): boolean {
    if (!session || !session.roles) return false
    const upperRoles = session.roles.map((r) => r.toUpperCase())
    if (portalId === 'GMF_HANDLER') {
      return upperRoles.includes('GMF_HANDLER') || upperRoles.includes('ADMIN1')
    }
    return upperRoles.includes(portalId.toUpperCase())
  }

  function handlePortalClick(portal: typeof PORTALS[0]) {
    if (hasAccess(portal.id)) {
      navigate(portal.path)
    } else {
      setNoAccessModal({ portalId: portal.id, portalLabel: portal.label })
    }
  }

  const userInitials = session?.email
    ? session.email.slice(0, 2).toUpperCase()
    : '??'

  const grantedCount = PORTALS.filter(p => hasAccess(p.id)).length

  return (
    <div className="min-h-svh bg-background relative overflow-hidden">
      {/* Background ambient glows */}
      <div className="absolute -top-32 -left-32 w-[500px] h-[500px] rounded-full bg-[#0066b3]/10 blur-[120px] pointer-events-none" />
      <div className="absolute top-1/2 -right-20 w-[400px] h-[400px] rounded-full bg-[#00a651]/8 blur-[100px] pointer-events-none" />
      <div className="absolute -bottom-20 left-1/3 w-[600px] h-[600px] rounded-full bg-purple-700/6 blur-[130px] pointer-events-none" />

      {/* Top Bar */}
      <header className="relative z-10 flex items-center justify-between px-6 sm:px-10 h-16 border-b border-border/50 bg-background/80 backdrop-blur-md">
        <Brand size="md" />

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2.5 rounded-full border border-border/60 bg-muted/40 px-3 py-1.5">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-[#0066b3]/15 text-[10px] font-extrabold text-[#00b2e3]">
              {userInitials}
            </div>
            <span className="text-xs font-semibold text-foreground truncate max-w-[180px]">
              {session?.email ?? 'Unknown'}
            </span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => logout()}
            className="rounded-full text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            title="Log out"
          >
            <LogOut size={17} />
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 max-w-5xl mx-auto px-4 sm:px-8 py-12">
        {/* Hero text */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-muted/40 px-4 py-2 text-xs font-bold tracking-widest text-muted-foreground uppercase mb-6">
            <Sparkles size={13} className="text-[#00b2e3]" />
            SLT-Mobitel Secure Gateway
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground mb-3">
            Select Your Portal
          </h1>
          <p className="text-sm font-medium text-muted-foreground max-w-md mx-auto">
            You have access to <span className="text-foreground font-bold">{grantedCount}</span> of {PORTALS.length} portals.
            Click a locked portal to request access.
          </p>
        </div>

        {/* Portal Cards Grid */}
        <div className="grid gap-5 sm:grid-cols-2">
          {PORTALS.map((portal) => {
            const Icon = portal.icon
            const accessible = hasAccess(portal.id)

            return (
              <button
                key={portal.id}
                onClick={() => handlePortalClick(portal)}
                className={`
                  group relative text-left rounded-2xl border p-6 transition-all duration-300
                  ${accessible
                    ? `${portal.border} bg-background/60 hover:bg-background/90 hover:shadow-xl hover:${portal.glow} hover:-translate-y-0.5 cursor-pointer`
                    : 'border-border/30 bg-muted/20 opacity-60 cursor-pointer hover:opacity-80'
                  }
                  backdrop-blur-sm
                `}
              >
                {/* Lock / Access indicator */}
                <div className="absolute top-4 right-4">
                  {accessible ? (
                    <span className="flex items-center gap-1.5 text-[10px] font-bold text-[#00a651] bg-[#00a651]/10 border border-[#00a651]/20 rounded-full px-2.5 py-1">
                      <span className="size-1.5 rounded-full bg-[#00a651] animate-pulse" />
                      Access Granted
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-[10px] font-bold text-muted-foreground bg-muted/50 border border-border/40 rounded-full px-2.5 py-1">
                      <Lock size={9} />
                      No Access
                    </span>
                  )}
                </div>

                {/* Icon */}
                <div className={`flex size-12 items-center justify-center rounded-xl mb-4 ${portal.iconBg} ${!accessible ? 'opacity-50' : ''}`}>
                  <Icon size={22} />
                </div>

                {/* Text */}
                <h2 className="text-[15px] font-extrabold text-foreground mb-1.5 leading-tight">
                  {portal.label}
                </h2>
                <p className="text-xs font-medium text-muted-foreground leading-relaxed mb-5">
                  {portal.subtitle}
                </p>

                {/* CTA */}
                <div className="flex items-center gap-2">
                  {accessible ? (
                    <span
                      className="inline-flex items-center gap-1.5 text-xs font-bold rounded-lg px-3 py-1.5 text-white transition-all"
                      style={{ background: `linear-gradient(135deg, ${portal.accent}cc, ${portal.accent}88)` }}
                    >
                      Enter Portal
                      <ChevronRight size={13} className="transition-transform group-hover:translate-x-0.5" />
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-xs font-bold rounded-lg px-3 py-1.5 bg-muted text-muted-foreground border border-border/40">
                      <Lock size={10} />
                      Request Access
                    </span>
                  )}
                </div>
              </button>
            )
          })}
        </div>

        {/* Footer hint */}
        <p className="mt-10 text-center text-[11px] font-medium text-muted-foreground">
          Contact your User Manager to request access to additional portals.
        </p>
      </main>

      {/* No Access Modal */}
      {noAccessModal && (
        <NoAccessModal
          portalId={noAccessModal.portalId}
          portalLabel={noAccessModal.portalLabel}
          userEmail={session?.email ?? ''}
          onClose={() => setNoAccessModal(null)}
        />
      )}
    </div>
  )
}
