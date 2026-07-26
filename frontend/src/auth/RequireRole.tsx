import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import type { Session } from './AuthProvider'
import { Loader2 } from 'lucide-react'

const roleHome: Record<Session['role'], string> = {
  admin: '/admin',
  gmf_handler: '/gmf-handler',
  manager: '/manager',
  customer: '/app',
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
  if (!session) return <Navigate to="/login" replace />
  if (session.role !== role) return <Navigate to={roleHome[session.role]} replace />
  return <Outlet />
}
