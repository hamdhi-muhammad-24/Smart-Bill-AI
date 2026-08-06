import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { LayoutDashboard, Menu, LogOut, Moon, Sun, Mail } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthProvider'
import { authMe } from '../lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { useTheme } from 'next-themes'
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

function SidebarFrame({ email, onNav }: { email?: string; onNav?: () => void }) {
  const { logout } = useAuth()
  const { theme, setTheme } = useTheme()

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground border-r border-sidebar-border shadow-md">
      <div className="p-3 border-b border-sidebar-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brand size="sm" />
          <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/20">
            Envelope
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          title="Toggle Theme"
        >
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </Button>
      </div>

      <SidebarNav onNav={onNav} />

      <div className="p-3 border-t border-sidebar-border">
        <div className="flex items-center gap-2 px-2 py-1.5 mb-2 rounded border border-white/5 bg-white/5">
          <div className="size-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-semibold text-sidebar-foreground/90 truncate flex-1">
            {email || 'envelope_handler'}
          </span>
          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded">
            Handler
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
  const { data: me } = useQuery({ queryKey: ['authMe'], queryFn: authMe })

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:block w-64 shrink-0 fixed inset-y-0 z-30">
        <SidebarFrame email={me?.email} />
      </aside>

      {/* Mobile Drawer */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="p-0 w-64 border-r-0 bg-sidebar">
          <SheetTitle className="sr-only">Envelope Portal Navigation</SheetTitle>
          <SidebarFrame email={me?.email} onNav={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-64">
        {/* Mobile Header Bar */}
        <header className="lg:hidden flex items-center justify-between p-3 border-b border-border bg-card">
          <Button variant="ghost" size="icon" onClick={() => setMobileOpen(true)}>
            <Menu size={18} />
          </Button>
          <Brand size="sm" />
          <div className="size-8" />
        </header>

        <main className="flex-1 p-4 md:p-6 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
