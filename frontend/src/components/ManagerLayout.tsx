import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Menu, LogOut, Moon, Sun, Users } from 'lucide-react'
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
  { to: '/manager', label: 'User Directory', icon: Users, end: true, pill: 'bg-emerald-400/15 text-emerald-200' },
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
  const initials = email ? email.slice(0, 2).toUpperCase() : 'MGR'

  return (
    <div className="flex flex-col h-full bg-sidebar text-sidebar-foreground">
      <div className="flex h-16 shrink-0 items-center border-b border-sidebar-border px-4">
        <Brand tone="dark" size="md" />
      </div>

      <SidebarNav onNav={onNav} />

      <div className="shrink-0 border-t border-sidebar-border p-3">
        <div className="flex items-center gap-2.5 px-1 py-1">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-emerald-500/20 text-xs font-semibold text-emerald-300 ring-1 ring-emerald-500/30">
            {initials}
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-xs font-medium text-sidebar-foreground truncate">
              {email ?? 'User Manager'}
            </span>
            <span className="mt-1 inline-flex w-fit items-center rounded-full bg-emerald-400/15 px-2 py-px text-[10px] font-medium text-emerald-300">
              User Manager Portal
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function ManagerLayout() {
  const [sheetOpen, setSheetOpen] = useState(false)
  const { logout } = useAuth()
  const navigate = useNavigate()
  const { theme, setTheme } = useTheme()

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
      <div className="absolute top-0 right-1/4 w-[500px] h-[500px] rounded-full bg-emerald-500/5 dark:bg-emerald-500/10 blur-3xl pointer-events-none -z-10" />
      <div className="absolute bottom-10 left-1/3 w-[600px] h-[600px] rounded-full bg-teal-500/5 dark:bg-teal-500/10 blur-3xl pointer-events-none -z-10" />

      <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border md:flex relative z-10">
        <SidebarFrame email={me?.email} />
      </aside>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="left" className="w-64 p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SidebarFrame email={me?.email} onNav={() => setSheetOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex flex-col flex-1 min-w-0">
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-border bg-card px-5 shadow-sm">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setSheetOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </Button>

          <div className="hidden flex-col leading-tight sm:flex">
            <span className="text-sm font-semibold">User Management Portal</span>
            <span className="text-xs text-muted-foreground">Provision staff accounts and manage system role permissions</span>
          </div>

          <span className="flex-1" />

          <Button
            variant="ghost"
            size="icon"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title="Toggle theme"
            className="rounded-full hover:bg-muted"
          >
            <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
            <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
            <span className="sr-only">Toggle theme</span>
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={handleLogout}
            className="rounded-full text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            title="Log out"
          >
            <LogOut size={18} />
          </Button>
        </header>

        <main className="flex-1 overflow-y-auto p-4 md:p-6 bg-background">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
