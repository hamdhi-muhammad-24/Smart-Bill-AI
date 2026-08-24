import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import type { Session } from './AuthProvider'
import { Loader2 } from 'lucide-react'

/** Map a portal route role → the allowed uppercase DB role strings needed for access */
const portalRoles: Record<string, string[]> = {
  admin: ['ADMIN'],
  gmf_handler: ['GMF_HANDLER', 'ADMIN1'],
  envelope_handler: ['ENVELOPE_HANDLER'],
  manager: ['MANAGER'],
}

interface Props {
  role: Session['role']
}

export default function RequireRole({ role }: Props) {
  const { session, isChecking } = useAuth()

  if (isChecking) return (
    <div className="flex h-svh items-center justify-center bg-background">
      <Loader2 className="size-8 animate-spin text-primary" />
    </div>
  )

  // Not logged in at all → login page
  if (!session) return <Navigate to="/login" replace />

  // New user → request access
  if (session.isNewUser) return <Navigate to="/request-access" replace />

  const allowed = portalRoles[role] || [role.toUpperCase()]

  // Check if user has any of the allowed roles in their granted roles list
  const hasAccess = session.roles.some((r) => allowed.includes(r.toUpperCase()))

  if (!hasAccess) {
    return <Navigate to="/role-select" replace />
  }

  return <Outlet />
}

