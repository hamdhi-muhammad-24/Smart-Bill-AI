import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lock, ShieldCheck, FileStack, Mail, Users, LogOut, ChevronRight, Sparkles, Sun, Moon } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { useTheme } from '../components/ThemeProvider'
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
    gradient: 'from-[#0066b3] to-[#00b2e3]',
    glow: 'hover:shadow-[#0066b3]/20',
    iconBg: 'bg-[#0066b3]/15 text-[#0066b3] dark:text-[#00b2e3] dark:bg-[#0066b3]/25',
    border: 'border-[#0066b3]/30 dark:border-[#0066b3]/40',
    accent: '#0066b3',
    badge: 'Admin Console',
  },
  {
    id: 'GMF_HANDLER',
    routeRole: 'gmf_handler',
    path: '/gmf-handler',
    label: 'GMF Handler Portal',
    subtitle: 'Upload and process GMF batch files, manage billing cycles and generation runs.',
    icon: FileStack,
    gradient: 'from-[#005f99] to-[#00b2e3]',
    glow: 'hover:shadow-cyan-500/20',
    iconBg: 'bg-cyan-500/15 text-cyan-700 dark:text-cyan-400 dark:bg-cyan-500/25',
    border: 'border-cyan-500/30 dark:border-cyan-500/40',
    accent: '#00b2e3',
    badge: 'Operations',
  },
  {
    id: 'ENVELOPE_HANDLER',
    routeRole: 'envelope_handler',
    path: '/envelope-handler',
    label: 'Envelope Campaign Portal',
    subtitle: 'Manage envelope artwork, templates, and print-ready composite PDFs.',
    icon: Mail,
    gradient: 'from-[#7c3aed] to-[#a855f7]',
    glow: 'hover:shadow-purple-500/20',
    iconBg: 'bg-purple-600/15 text-purple-700 dark:text-purple-400 dark:bg-purple-600/25',
    border: 'border-purple-600/30 dark:border-purple-600/40',
    accent: '#8b5cf6',
    badge: 'Campaigns',
  },
  {
    id: 'MANAGER',
    routeRole: 'manager',
    path: '/manager',
    label: 'User Management Portal',
    subtitle: 'Provision staff accounts, manage role permissions, review access requests.',
    icon: Users,
    gradient: 'from-[#00a651] to-[#00c853]',
    glow: 'hover:shadow-emerald-500/20',
    iconBg: 'bg-emerald-600/15 text-emerald-700 dark:text-emerald-400 dark:bg-emerald-600/25',
    border: 'border-emerald-600/30 dark:border-emerald-600/40',
    accent: '#00a651',
    badge: 'Management',
  },
]

export default function RoleSelector() {
  const { session, logout } = useAuth()
  const { toggleTheme } = useTheme()
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
    <div className="min-h-svh bg-background relative overflow-hidden selection:bg-[#0066b3]/20 selection:text-[#0066b3]">
      {/* Background ambient glows */}
      <div className="absolute -top-32 -left-32 w-[600px] h-[600px] rounded-full bg-[#0066b3]/10 dark:bg-[#0066b3]/20 blur-[140px] pointer-events-none" />
      <div className="absolute top-1/2 -right-20 w-[500px] h-[500px] rounded-full bg-[#00a651]/10 dark:bg-[#00a651]/15 blur-[120px] pointer-events-none" />
      <div className="absolute -bottom-20 left-1/3 w-[600px] h-[600px] rounded-full bg-purple-700/8 dark:bg-purple-700/15 blur-[140px] pointer-events-none" />

      {/* Top Bar */}
      <header className="relative z-10 flex items-center justify-between px-6 sm:px-10 h-16 border-b border-border/50 bg-card/60 shadow-xs backdrop-blur-xl">
        <Brand size="md" />

        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            title="Toggle theme"
            className="rounded-full hover:bg-muted"
          >
            <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            <span className="sr-only">Toggle theme</span>
          </Button>

          <div className="hidden sm:flex items-center gap-2.5 rounded-full border border-border/60 bg-muted/40 px-3 py-1.5 shadow-2xs">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#0066b3] to-[#00b2e3] text-[10px] font-extrabold text-white shadow-xs">
              {userInitials}
            </div>
            <span className="text-xs font-semibold text-foreground truncate max-w-[180px]">
              {session?.email ?? 'Unknown'}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => logout()}
            className="gap-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive rounded-lg"
            title="Log out"
          >
            <LogOut size={15} />
            <span className="hidden sm:inline">Sign Out</span>
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 max-w-5xl mx-auto px-4 sm:px-8 py-12">
        {/* Hero text */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-card/80 px-4 py-1.5 text-xs font-bold tracking-wider text-muted-foreground uppercase mb-6 shadow-2xs backdrop-blur-md">
            <Sparkles size={14} className="text-[#0066b3] dark:text-[#00b2e3]" />
            SLT-MOBITEL SECURE GATEWAY
          </div>
          <h1 className="text-3xl sm:text-4xl font-black tracking-tight text-foreground mb-3">
            Select Your Portal
          </h1>
          <p className="text-sm font-medium text-muted-foreground max-w-md mx-auto">
            You currently have access to <span className="text-foreground font-bold">{grantedCount}</span> of {PORTALS.length} operational consoles.
          </p>
        </div>

        {/* Portal Cards Grid */}
        <div className="grid gap-6 sm:grid-cols-2">
          {PORTALS.map((portal) => {
            const Icon = portal.icon
            const accessible = hasAccess(portal.id)

            return (
              <button
                key={portal.id}
                onClick={() => handlePortalClick(portal)}
                className={`
                  group relative text-left rounded-2xl border p-7 transition-all duration-300
                  ${accessible
                    ? `${portal.border} bg-card/80 hover:bg-card hover:shadow-2xl ${portal.glow} hover:-translate-y-1 cursor-pointer ring-1 ring-border/50`
                    : 'border-border/40 bg-muted/20 opacity-65 cursor-pointer hover:opacity-90 hover:bg-muted/30'
                  }
                  backdrop-blur-md shadow-sm
                `}
              >
                {/* Lock / Access indicator */}
                <div className="absolute top-5 right-5 flex items-center gap-2">
                  <span className="text-[10px] font-extrabold uppercase tracking-wider text-muted-foreground/80 px-2 py-0.5 rounded-md bg-muted/60 border border-border/40">
                    {portal.badge}
                  </span>
                  {accessible ? (
                    <span className="flex items-center gap-1.5 text-[11px] font-bold text-[#00a651] dark:text-[#00e676] bg-[#00a651]/10 dark:bg-[#00a651]/20 border border-[#00a651]/20 rounded-full px-2.5 py-0.5">
                      <span className="size-1.5 rounded-full bg-[#00a651] dark:bg-[#00e676] animate-pulse" />
                      Active
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-[11px] font-bold text-muted-foreground bg-muted/70 border border-border/60 rounded-full px-2.5 py-0.5">
                      <Lock size={10} />
                      Locked
                    </span>
                  )}
                </div>

                {/* Icon */}
                <div className={`flex size-14 items-center justify-center rounded-2xl mb-5 ${portal.iconBg} ${!accessible ? 'opacity-50' : ''} shadow-xs transition-transform duration-300 group-hover:scale-105`}>
                  <Icon size={26} />
                </div>

                {/* Text */}
                <h2 className="text-lg font-extrabold text-foreground mb-2 leading-tight tracking-tight group-hover:text-primary transition-colors">
                  {portal.label}
                </h2>
                <p className="text-xs font-medium text-muted-foreground leading-relaxed mb-6">
                  {portal.subtitle}
                </p>

                {/* CTA */}
                <div className="flex items-center">
                  {accessible ? (
                    <span className={`inline-flex items-center gap-2 text-xs font-bold rounded-xl px-4 py-2 text-white bg-gradient-to-r ${portal.gradient} shadow-md transition-all group-hover:shadow-lg`}>
                      Launch Console
                      <ChevronRight size={14} className="transition-transform duration-300 group-hover:translate-x-1" />
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-2 text-xs font-bold rounded-xl px-4 py-2 bg-muted text-muted-foreground border border-border/60 group-hover:text-foreground transition-colors">
                      <Lock size={12} />
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
