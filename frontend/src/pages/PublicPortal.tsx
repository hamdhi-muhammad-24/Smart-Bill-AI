import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Bot,
  FileText,
  Headphones,
  HelpCircle,
  LockKeyhole,
  ReceiptText,
  ShieldCheck,
  Zap,
  Globe,
  ChevronRight,
  Moon,
  Sun
} from 'lucide-react'
import { useTheme } from '@/components/ThemeProvider'
import { useAuth } from '../auth/AuthProvider'
import Brand from '../components/Brand'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const navLinks = [
  { label: 'Home', href: '#home' },
  { label: 'Portal Access', href: '#portal-access' },
  { label: 'Smart Features', href: '#smart-features' },
  { label: 'Support', href: '#support' },
]

const actionCards = [
  {
    icon: Zap,
    title: 'GMF Operations Portal',
    description: 'For GMF handlers to securely upload files, monitor detection queues, and manage processing batches.',
    cta: 'Enter GMF Portal',
    helper: 'gmf@slt.com.lk',
    path: 'signin' as const,
    accentClass: 'from-blue-600 to-cyan-500',
    iconClass: 'bg-gradient-to-br from-[#0066b3] to-[#00b2e3] text-white shadow-[0_12px_30px_rgba(0,102,179,0.35)]',
    buttonClass: 'bg-gradient-to-r from-[#0066b3] to-[#00b2e3] text-white shadow-lg hover:shadow-[#00b2e3]/25 hover:-translate-y-0.5',
  },
  {
    icon: LockKeyhole,
    title: 'System Administration',
    description: 'For system administrators to generate billing cycles, design templates, and configure engine parameters.',
    cta: 'Enter Admin Console',
    helper: 'admin@slt.com.lk',
    path: 'signin' as const,
    accentClass: 'from-slate-800 to-slate-900 dark:from-slate-200 dark:to-slate-400',
    iconClass: 'bg-gradient-to-br from-slate-800 to-slate-900 dark:from-slate-200 dark:to-slate-400 text-white dark:text-slate-900 shadow-[0_12px_30px_rgba(51,65,85,0.35)] dark:shadow-[0_12px_30px_rgba(255,255,255,0.15)]',
    buttonClass: 'bg-gradient-to-r from-slate-800 to-slate-900 dark:from-slate-200 dark:to-slate-300 text-white dark:text-slate-900 shadow-lg hover:shadow-slate-500/25 dark:hover:shadow-white/20 hover:-translate-y-0.5',
  },
  {
    icon: ShieldCheck,
    title: 'User Management Portal',
    description: 'For user managers to provision new staff access, manage user roles, and monitor system activity logs.',
    cta: 'Enter Manager Portal',
    helper: 'manager@slt.com.lk',
    path: 'signin' as const,
    accentClass: 'from-emerald-600 to-teal-500',
    iconClass: 'bg-gradient-to-br from-[#00a651] to-teal-500 text-white shadow-[0_12px_30px_rgba(0,166,81,0.35)]',
    buttonClass: 'bg-gradient-to-r from-[#00a651] to-teal-500 text-white shadow-lg hover:shadow-[#00a651]/25 hover:-translate-y-0.5',
  },
]

const featureCards = [
  {
    icon: Bot,
    title: 'AI-Powered Generation',
    description: 'Our proprietary system parses massive GMF data lakes to instantly generate visually striking, pixel-perfect PDF invoices.',
  },
  {
    icon: Zap,
    title: 'High-Speed Processing',
    description: 'Engineered for telecom scale. Upload batch cycles and watch millions of records process in real-time on the Admin Hub.',
  },
  {
    icon: ShieldCheck,
    title: 'Enterprise Security',
    description: 'From multi-factor staff authentication to strict Role-Based Access Control, administrative operations are secured by AES-256 encryption.',
  },
]

const heroHighlights = [
  {
    label: 'Smart Billing',
    text: '100% AI-driven accuracy',
  },
  {
    label: 'Scale & Speed',
    text: 'Millions of records processed',
  },
  {
    label: 'SLT Secured',
    text: 'Enterprise-grade encryption',
  },
]

const gatewayStatusRows = [
  {
    icon: ReceiptText,
    label: 'Cycle Generation Engine',
    text: 'Operational - Auto Mode',
  },
  {
    icon: FileText,
    label: 'GMF Watcher Service',
    text: 'Real-time sync active',
  },
  {
    icon: LockKeyhole,
    label: 'Data Vault',
    text: 'Encrypted storage active',
  },
]

const supportLinks = [
  { label: 'Contact Support', href: 'mailto:support@slt.lk' },
  { label: 'Smart Features', href: '#smart-features' },
  { label: 'Privacy Policy', href: '#terms-privacy' },
]

export default function PublicPortal() {
  const { session } = useAuth()
  const { resolvedTheme, toggleTheme } = useTheme()
  const signInPath = !session
    ? '/login'
    : session.isNewUser
    ? '/request-access'
    : '/role-select'

  function resolveActionPath(action: (typeof actionCards)[number]): string {
    if (action.path === 'signin') return signInPath
    return action.path
  }

  return (
    <main className="min-h-svh bg-background text-foreground relative selection:bg-[#0066b3]/20 selection:text-[#0066b3] dark:selection:text-[#00b2e3]">
      {/* Premium Global Background Ambient Effects (SLT Colors: Blue & Emerald/Teal) */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden z-0">
        <div className="absolute -left-[10%] -top-[10%] size-[600px] rounded-full bg-[#0066b3]/15 blur-[120px] dark:bg-[#0066b3]/25" />
        <div className="absolute -right-[10%] top-[10%] size-[500px] rounded-full bg-[#00a651]/10 blur-[130px] dark:bg-[#00a651]/15" />
        <div className="absolute bottom-[-20%] left-[20%] size-[800px] rounded-full bg-[#00b2e3]/10 blur-[150px] dark:bg-[#00b2e3]/15" />
      </div>

      {/* Navigation */}
      <header className="sticky top-0 z-40 border-b border-border/40 bg-background/60 shadow-sm backdrop-blur-2xl">
        <div className="flex h-20 w-full items-center justify-between px-6 lg:px-10">
          {/* Logo on the far left */}
          <Brand size="md" tone={resolvedTheme === 'dark' ? 'dark' : 'light'} />

          {/* Centered Navigation Links */}
          <nav className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden items-center gap-10 text-[14px] font-semibold text-muted-foreground md:flex">
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="relative transition-colors hover:text-foreground after:absolute after:-bottom-2.5 after:left-0 after:h-0.5 after:w-0 after:rounded-full after:bg-[#0066b3] after:transition-all hover:after:w-full dark:after:bg-[#00b2e3]"
              >
                {link.label}
              </a>
            ))}
          </nav>

          {/* Action Buttons on the far right */}
          <div className="flex items-center gap-3 ml-auto">
            <Button
              variant="outline"
              size="icon"
              className="rounded-full bg-background/70 hover:bg-background backdrop-blur-md border-border/60 shadow-sm transition-all"
              onClick={toggleTheme}
              title="Toggle theme"
            >
              <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0 text-foreground" />
              <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100 text-foreground" />
              <span className="sr-only">Toggle theme</span>
            </Button>

            <Button asChild size="default" className="h-10 shrink-0 bg-gradient-to-r from-[#0066b3] to-[#00b2e3] px-5 text-[14px] font-bold text-white shadow-lg hover:shadow-[#0066b3]/30 hover:-translate-y-0.5 transition-all border-none rounded-full">
              <Link to={signInPath}>
                Portal Login
                <ArrowRight size={16} className="ml-2" />
              </Link>
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section id="home" className="relative z-10 overflow-hidden py-16 sm:py-24 lg:py-32 flex flex-col items-center justify-center min-h-[85vh]">
        <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-border to-transparent opacity-50" />

        <div className="relative mx-auto grid max-w-7xl gap-12 px-4 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:gap-16 lg:px-8 w-full">
          <div className="max-w-3xl pt-8">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#0066b3]/20 bg-[#0066b3]/5 px-4 py-2 text-sm font-bold text-[#0066b3] dark:text-[#66c2ff] shadow-sm backdrop-blur-md mb-6 ring-1 ring-[#0066b3]/10">
              <Globe size={16} />
              <span className="min-w-0 tracking-wide uppercase">SLT-MOBITEL Next-Gen Platform</span>
            </div>
            <h1 className="max-w-4xl text-5xl font-extrabold tracking-tight leading-[1.1] sm:text-6xl lg:text-7xl">
              <span className="bg-gradient-to-br from-foreground to-foreground/70 bg-clip-text text-transparent">Smart Billing &</span>
              <br />
              <span className="bg-gradient-to-r from-[#0066b3] via-[#00b2e3] to-[#00a651] bg-clip-text text-transparent">
                Invoice Gateway
              </span>
            </h1>
            <p className="mt-8 max-w-2xl text-lg sm:text-xl leading-relaxed text-muted-foreground font-medium">
              Experience the future of telecommunications billing. Our AI-driven platform processes millions of GMF records, generating beautiful, accurate invoices instantly while providing a secure portal for billing administrators and operations staff.
            </p>

            <div className="mt-12 flex flex-wrap items-center gap-4">
              <Button asChild size="lg" className="h-14 rounded-full bg-foreground text-background hover:bg-foreground/90 font-bold px-8 shadow-xl hover:-translate-y-0.5 transition-all border-none">
                <a href="#portal-access">
                  Explore Portals
                  <ChevronRight size={20} className="ml-2" />
                </a>
              </Button>
              <Button asChild size="lg" variant="outline" className="h-14 rounded-full border-border/60 bg-background/50 font-bold px-8 hover:bg-muted/50 backdrop-blur-sm transition-all text-foreground">
                <a href="#smart-features">
                  Discover Features
                </a>
              </Button>
            </div>

            <div className="mt-14 grid max-w-2xl gap-5 sm:grid-cols-3">
              {heroHighlights.map((item) => (
                <div
                  key={item.label}
                  className="glass-card rounded-2xl p-5 transition-all hover:-translate-y-1 hover:shadow-xl border-border/40 bg-background/40 backdrop-blur-xl"
                >
                  <p className="text-sm font-extrabold text-foreground">{item.label}</p>
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground font-medium">{item.text}</p>
                </div>
              ))}
            </div>
          </div>

          <aside className="relative overflow-hidden rounded-[2.5rem] glass-card p-8 sm:p-10 shadow-2xl ring-1 ring-white/10 dark:ring-white/5 bg-gradient-to-br from-background/80 to-background/40 backdrop-blur-2xl lg:mt-0 mt-8">
            <div className="pointer-events-none absolute -right-20 -top-20 size-72 rounded-full bg-gradient-to-br from-[#0066b3]/20 to-[#00a651]/20 blur-[80px]" />
            <div className="pointer-events-none absolute -left-20 -bottom-20 size-72 rounded-full bg-gradient-to-tr from-[#00b2e3]/20 to-transparent blur-[80px]" />

            <div className="relative">
              <div className="flex items-start justify-between gap-4 border-b border-border/40 pb-6 mb-6">
                <div className="flex min-w-0 items-center gap-5">
                  <div className="flex size-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-[#0066b3] to-[#00b2e3] text-white shadow-lg shadow-[#0066b3]/25">
                    <Zap size={28} className="fill-white/20" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-2xl font-extrabold text-foreground tracking-tight">System Status</h2>
                    <p className="mt-1 text-sm font-bold text-[#00a651] dark:text-[#00e676] flex items-center gap-2 bg-[#00a651]/10 dark:bg-[#00e676]/10 px-2.5 py-1 rounded-full w-fit border border-[#00a651]/20">
                      <span className="relative flex size-2.5">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00a651] dark:bg-[#00e676] opacity-75"></span>
                        <span className="relative inline-flex rounded-full size-2.5 bg-[#00a651] dark:bg-[#00e676]"></span>
                      </span>
                      All Services Operational
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid gap-4">
                {gatewayStatusRows.map((item) => {
                  const Icon = item.icon
                  return (
                    <div
                      key={item.label}
                      className="group flex items-center gap-5 rounded-2xl border border-border/40 bg-background/50 p-4 transition-all duration-300 hover:border-[#0066b3]/30 hover:bg-muted/50 hover:shadow-lg backdrop-blur-sm"
                    >
                      <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-muted/80 text-foreground shadow-sm ring-1 ring-border group-hover:bg-[#0066b3] group-hover:text-white group-hover:ring-[#0066b3] transition-all duration-300">
                        <Icon size={20} />
                      </span>
                      <div className="min-w-0">
                        <p className="text-[15px] font-bold text-foreground">{item.label}</p>
                        <p className="mt-1 text-xs font-medium text-muted-foreground">{item.text}</p>
                      </div>
                    </div>
                  )
                })}
              </div>

              <div className="mt-8 flex items-start gap-4 rounded-2xl bg-muted/30 p-4 border border-border/40">
                <LockKeyhole size={20} className="shrink-0 text-[#0066b3] mt-0.5" />
                <p className="text-xs leading-relaxed text-muted-foreground font-medium">
                  <strong className="text-foreground">Bank-Grade Security:</strong> End-to-end AES-256 encryption active for all system billing data and staff generation operations across the SLT-MOBITEL network.
                </p>
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section id="portal-access" className="relative z-10 mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8 pt-12">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-foreground tracking-tight">Select Your Workspace</h2>
          <p className="mt-4 text-lg text-muted-foreground font-medium max-w-2xl mx-auto">Choose the appropriate portal below to securely access your dedicated SLT-MOBITEL billing environment.</p>
        </div>

        <div className="grid gap-8 lg:grid-cols-3 max-w-7xl mx-auto">
          {actionCards.map((action) => {
            const Icon = action.icon
            return (
              <Card
                key={action.title}
                className={`glass-card relative overflow-hidden rounded-[2rem] py-0 transition-all duration-500 hover:-translate-y-2 hover:shadow-2xl border-border/50`}
              >
                <div className={`absolute inset-x-0 top-0 h-2 bg-gradient-to-r ${action.accentClass}`} />
                <CardContent className="flex h-full min-h-[320px] flex-col p-8 sm:p-10">
                  <div className="flex items-start justify-between gap-3">
                    <div className={`flex size-16 items-center justify-center rounded-2xl ${action.iconClass} transition-transform group-hover:scale-110`}>
                      <Icon size={28} />
                    </div>
                    <span className="whitespace-nowrap rounded-full bg-muted border border-border/50 px-3.5 py-1.5 text-xs font-bold text-foreground shadow-sm">
                      {action.helper}
                    </span>
                  </div>
                  <h2 className="mt-8 text-2xl font-extrabold text-foreground tracking-tight">{action.title}</h2>
                  <p className="mt-4 flex-1 text-[15px] leading-relaxed text-muted-foreground font-medium">{action.description}</p>
                  <Button asChild className={cn("mt-10 h-14 w-full justify-between px-6 font-extrabold border-none text-[15px] rounded-xl transition-all duration-300", action.buttonClass)}>
                    <Link to={resolveActionPath(action)}>
                      <span className="truncate">{action.cta}</span>
                      <ArrowRight size={20} />
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </section>

      <section id="smart-features" className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
        <div className="glass-card relative overflow-hidden rounded-[3rem] p-10 sm:p-16 border-border/40 shadow-2xl bg-gradient-to-b from-background/80 to-muted/20">
          <div className="absolute inset-0 opacity-[0.03] dark:opacity-[0.05] [background-image:radial-gradient(var(--foreground)_1px,transparent_1px)] [background-size:32px_32px]" />

          <div className="relative flex flex-col gap-6 md:flex-row md:items-end md:justify-between mb-16">
            <div className="max-w-3xl">
              <p className="text-sm font-extrabold uppercase tracking-widest text-[#0066b3] dark:text-[#66c2ff] mb-4 flex items-center gap-2">
                <SparklesIcon className="size-4" /> The SLT-MOBITEL Advantage
              </p>
              <h2 className="mt-3 text-4xl font-extrabold text-foreground sm:text-5xl tracking-tight leading-[1.15]">
                Modern Telecom <br className="hidden sm:block" /> E-Billing Made Simple
              </h2>
              <p className="mt-6 text-lg leading-relaxed text-muted-foreground max-w-2xl font-medium">
                We've revolutionized how billing data is processed. By ingesting complex GMF files, our AI engine designs, formats, and generates pixel-perfect PDF statements, ensuring accuracy and security across the network.
              </p>
            </div>
          </div>

          <div className="relative grid gap-8 md:grid-cols-3">
            {featureCards.map((feature) => {
              const Icon = feature.icon
              return (
                <div
                  key={feature.title}
                  className="group rounded-3xl border border-border/50 bg-background/60 p-8 transition-all duration-500 hover:-translate-y-2 hover:border-[#0066b3]/30 hover:bg-background hover:shadow-2xl backdrop-blur-sm"
                >
                  <div className="flex size-14 items-center justify-center rounded-2xl bg-muted text-foreground shadow-inner ring-1 ring-border group-hover:bg-[#0066b3] group-hover:text-white transition-all duration-300">
                    <Icon size={24} />
                  </div>
                  <h3 className="mt-6 text-xl font-extrabold text-foreground tracking-tight">{feature.title}</h3>
                  <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground font-medium">{feature.description}</p>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      <section id="support" className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
        <div className="glass-card rounded-[3rem] p-8 sm:p-12 lg:flex lg:items-center lg:justify-between lg:gap-12 border-border/40 shadow-xl bg-gradient-to-br from-background to-muted/30">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6">
            <div className="flex size-20 shrink-0 items-center justify-center rounded-3xl bg-gradient-to-br from-[#00a651] to-teal-600 text-white shadow-lg shadow-[#00a651]/25">
              <Headphones size={32} />
            </div>
            <div>
              <h2 className="text-3xl font-extrabold text-foreground tracking-tight">Need Assistance?</h2>
              <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-muted-foreground font-medium">
                Our support team is ready to help with credential verification, portal access issues, or system administration questions.
              </p>
            </div>
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-3 lg:mt-0 lg:min-w-[480px]">
            {supportLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="inline-flex h-14 items-center justify-center gap-3 whitespace-nowrap rounded-2xl border border-border bg-background/80 px-6 text-[15px] font-bold text-foreground shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-[#0066b3]/40 hover:bg-[#0066b3] hover:text-white hover:shadow-xl backdrop-blur-sm"
              >
                <HelpCircle size={18} />
                {link.label}
              </a>
            ))}
          </div>
        </div>
      </section>

      <footer id="terms-privacy" className="border-t border-border/60 bg-background/80 backdrop-blur-xl mt-auto">
        <div className="flex w-full flex-col sm:flex-row items-center justify-between px-6 lg:px-10 py-10 text-sm text-muted-foreground">
          <div className="flex-1 flex justify-start mb-6 sm:mb-0">
            <Brand size="md" tone={resolvedTheme === 'dark' ? 'dark' : 'light'} />
          </div>
          
          <div className="flex-[2] sm:flex-1 flex flex-col items-center text-center gap-1 font-medium">
            <p>&copy; {new Date().getFullYear()} SLT-MOBITEL. All rights reserved.</p>
            <p className="text-xs opacity-75">Smart Billing & Invoice Generation System v2.0</p>
          </div>

          <div className="flex-1 hidden sm:block"></div>
        </div>
      </footer>
    </main>
  )
}

function SparklesIcon(props: any) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
      <path d="M5 3v4" />
      <path d="M19 17v4" />
      <path d="M3 5h4" />
      <path d="M17 19h4" />
    </svg>
  )
}
