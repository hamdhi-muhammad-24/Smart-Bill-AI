import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  FileCheck2,
  Menu,
  LogOut,
  Moon,
  Sun,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthProvider'
import { authMe } from '../lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { useTheme } from '@/components/ThemeProvider'
import Brand from './Brand'

const NAV_ITEMS = [
  {
    to: '/super-admin',
    label: 'GMF Test Center',
    icon: FileCheck2,
    end: true,
    pill: 'bg-[#0066b3]/15 text-[#0066b3] dark:text-[#00b2e3]',
  },
]

function SidebarNav({ onNav }: { onNav?: () => void }) {
  return (
    <nav className="flex flex-col gap-1 p-3 flex-1">
      {NAV_ITEMS.map(({ to, label, icon: Icon, end, pill }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNav}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-semibold transition-all',
              isActive
                ? 'bg-sidebar-accent text-sidebar-accent-foreground font-medium shadow-xs'
                : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground',
            )
          }
        >
          {({ isActive }) => (
            <>
              <span
                className={cn(
                  'flex size-7 shrink-0 items-center justify-center rounded-lg',
                  isActive ? pill : 'bg-white/5 text-sidebar-foreground/50',
                )}
              >
                <Icon size={15} />
              </span>
              <span>{label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

function SidebarFrame({ email, onNav }: { email?: string; onNav?: () => void }) {
  const initials = email ? email.slice(0, 2).toUpperCase() : 'AD'

  return (
    <div className="flex flex-col h-full bg-sidebar text-sidebar-foreground">
      <div className="flex h-16 shrink-0 items-center border-b border-sidebar-border px-5">
        <Brand tone="dark" size="md" />
      </div>

      <SidebarNav onNav={onNav} />

      {/* Avatar badge at bottom */}
      <div className="shrink-0 border-t border-sidebar-border p-3.5">
        <div className="flex items-center gap-3 px-1 py-1">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/10 text-xs font-semibold text-white ring-1 ring-white/10">
            {initials}
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-xs font-medium text-sidebar-foreground truncate">
              {email ?? 'Administrator'}
            </span>
            <span className="mt-0.5 inline-flex w-fit items-center rounded-full bg-[#0066b3]/15 px-2 py-px text-[10px] font-medium text-[#0066b3] dark:text-[#00b2e3]">
              Quality Assurance
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function SuperAdminLayout() {
  const [sheetOpen, setSheetOpen] = useState(false)
  const { logout } = useAuth()
  const navigate = useNavigate()
  const { toggleTheme } = useTheme()

  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: authMe,
    staleTime: Infinity,
  })

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-svh bg-background relative overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-0 right-1/4 w-[500px] h-[500px] rounded-full bg-blue-500/5 dark:bg-blue-500/10 blur-3xl pointer-events-none -z-10" />
      <div className="absolute bottom-10 left-1/3 w-[600px] h-[600px] rounded-full bg-cyan-500/5 dark:bg-cyan-500/10 blur-3xl pointer-events-none -z-10" />

      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border md:flex relative z-10">
        <SidebarFrame email={me?.email} />
      </aside>

      {/* Mobile sidebar sheet */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="left" className="w-64 p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SidebarFrame email={me?.email} onNav={() => setSheetOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Main column */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top bar */}
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-border bg-card px-6 shadow-xs">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setSheetOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </Button>

          <div className="hidden flex-col leading-tight sm:flex whitespace-nowrap">
            <span className="text-sm font-semibold">SLT-MOBITEL Billing System</span>
            <span className="text-xs text-muted-foreground">Invoice Verification & Testing</span>
          </div>

          <span className="flex-1" />

          <Button
            variant="ghost"
            size="icon"
            className="rounded-full"
            onClick={toggleTheme}
            title="Toggle theme"
          >
            <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            <span className="sr-only">Toggle theme</span>
          </Button>

          {me?.email && (
            <span className="hidden rounded-full border border-border bg-muted/50 px-3 py-1 text-xs font-medium text-muted-foreground lg:block whitespace-nowrap">
              {me.email}
            </span>
          )}

          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-muted-foreground hover:text-foreground whitespace-nowrap"
            onClick={handleLogout}
          >
            <LogOut size={14} />
            Sign Out
          </Button>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto px-5 py-6 sm:px-8 lg:px-10">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
