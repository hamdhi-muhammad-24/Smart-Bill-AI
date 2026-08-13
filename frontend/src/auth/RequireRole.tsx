import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import type { Session } from './AuthProvider'
import { Loader2 } from 'lucide-react'

/** Map a portal route role → the uppercase DB role string needed for access */
const portalRole: Record<string, string> = {
  admin: 'ADMIN',
  gmf_handler: 'GMF_HANDLER',
  envelope_handler: 'ENVELOPE_HANDLER',
  manager: 'MANAGER',
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

  const requiredDbRole = portalRole[role]

  // Check if user has the required role in their granted roles list
  const hasAccess = requiredDbRole && session.roles.includes(requiredDbRole)

  if (!hasAccess) {
    // TEMPORARY DEBUGGING STATE: Show what roles we actually have instead of redirecting
    return (
      <div className="flex h-svh flex-col items-center justify-center bg-background text-foreground p-8 text-center">
        <h1 className="text-2xl font-bold text-destructive mb-4">Access Denied by RequireRole</h1>
        <p className="mb-2">We tried to access a portal requiring: <strong>{requiredDbRole}</strong></p>
        <p className="mb-6">Your session has these roles: <strong>{JSON.stringify(session.roles)}</strong></p>
        <p className="text-muted-foreground text-sm max-w-md">
          If you see this screen, please copy the text above and send it to the developer. 
          If you don't see this screen and are still redirected to the Role Selector, the issue is somewhere else!
        </p>
        <button 
          onClick={() => window.location.href = '/role-select'}
          className="mt-8 px-4 py-2 bg-primary text-primary-foreground rounded"
        >
          Go Back
        </button>
      </div>
    )
  }

  return <Outlet />
}
