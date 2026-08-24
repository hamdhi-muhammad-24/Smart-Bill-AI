import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Menu, LogOut, Moon, Sun, Mail, Layers, LayoutGrid } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { useTheme } from '@/components/ThemeProvider'
import Brand from './Brand'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end: boolean
  pill: string
}

const NAV_ITEMS: NavItem[] = [
  { to: '/envelope-handler',          label: 'Overview',          icon: LayoutDashboard, end: true,  pill: 'bg-indigo-400/15 text-indigo-200' },
  { to: '/envelope-handler/manager',  label: 'Envelope Manager',  icon: Mail,            end: false, pill: 'bg-emerald-400/15 text-emerald-200' },
  { to: '/envelope-handler/gallery',  label: 'Saved Gallery',     icon: Layers,          end: false, pill: 'bg-blue-400/15 text-blue-200' },
]

function SidebarNav({ onNav }: { onNav?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5 p-2 flex-1">
      {NAV_ITEMS.map(({ to, label, icon: Icon, end, pill }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNav}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors',
              isActive
                ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium shadow-sm'
                : 'text-sidebar-foreground/68 hover:bg-sidebar-accent/45 hover:text-sidebar-foreground',
            )
          }
        >
          {({ isActive }) => (
            <>
              <span className={cn('flex size-7 shrink-0 items-center justify-center rounded-md', isActive ? pill : 'bg-white/5 text-sidebar-foreground/50')}>
                <Icon size={13} />
              </span>
              {label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

function SidebarFrame({ onNav }: { email?: string; onNav?: () => void }) {
  const { logout } = useAuth()

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground border-r border-sidebar-border shadow-md">
      <div className="p-4 border-b border-sidebar-border flex items-center justify-between">
        <Brand tone="dark" size="sm" />
      </div>

      <SidebarNav onNav={onNav} />

      <div className="p-3 border-t border-sidebar-border">
        <div className="flex items-center gap-2 px-2.5 py-2 mb-2 rounded-lg border border-white/5 bg-white/5">
          <div className="size-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-bold tracking-wide text-sidebar-foreground/90 flex-1">
            Envelope Handler
          </span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-sidebar-foreground/60 hover:bg-destructive/10 hover:text-destructive text-xs gap-2"
          onClick={logout}
        >
          <LogOut size={13} />
          Sign out
        </Button>
      </div>
    </div>
  )
}

export default function EnvelopeLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const { toggleTheme } = useTheme()
  const { logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen bg-background relative">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:block w-64 shrink-0 fixed inset-y-0 z-30">
        <SidebarFrame />
      </aside>

      {/* Mobile Drawer */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="p-0 w-64 border-r-0 bg-sidebar">
          <SheetTitle className="sr-only">Envelope Portal Navigation</SheetTitle>
          <SidebarFrame onNav={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-64">
        {/* Top Header Bar */}
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-border bg-card px-5 shadow-xs z-20">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </Button>

          <div className="hidden flex-col leading-tight sm:flex">
            <span className="text-sm font-semibold text-foreground">Envelope Campaign Portal</span>
            <span className="text-xs text-muted-foreground">Promotional artwork and envelope layout management</span>
          </div>

          <span className="flex-1" />

          {/* Switch Portal Button */}
          <Button
            variant="outline"
            size="sm"
            className="h-8.5 gap-2 rounded-lg border-border/80 bg-background/50 hover:bg-accent text-xs font-semibold shadow-xs transition-all text-foreground"
            onClick={() => navigate('/role-select')}
            title="Switch to another portal"
          >
            <LayoutGrid size={14} className="text-[#0066b3] dark:text-[#00b2e3]" />
            <span className="hidden sm:inline">Switch Portal</span>
          </Button>

          {/* Theme Toggle Button */}
          <Button
            variant="ghost"
            size="icon"
            className="rounded-full"
            onClick={toggleTheme}
            title="Toggle theme"
          >
            <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0 text-amber-500" />
            <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100 text-indigo-400" />
            <span className="sr-only">Toggle theme</span>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-muted-foreground hover:text-foreground"
            onClick={logout}
          >
            <LogOut size={14} />
            Logout
          </Button>
        </header>

        <main className="flex-1 p-4 md:p-6 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
