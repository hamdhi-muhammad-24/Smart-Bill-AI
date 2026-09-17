import { createContext, useContext, useState, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearToken, setToken, getToken, authMe } from '../lib/api'
import { useMsal } from '@azure/msal-react'
import { InteractionStatus } from '@azure/msal-browser'
import { clearStaleMsalInteractions } from './msalConfig'

export interface Session {
  role: 'admin' | 'gmf_handler' | 'envelope_handler' | 'manager' | 'super_admin' | 'customer'
  roles: string[]           // all granted portal roles (uppercase)
  email: string
  customerId?: number
  isNewUser?: boolean        // true when Microsoft login but not yet in DB
}

interface AuthContextValue {
  session: Session | null
  isChecking: boolean
  login: (session: Session) => void
  logout: () => void
}

const STORAGE_KEY = 'slt-auth'

const AuthContext = createContext<AuthContextValue | null>(null)

/** Maps backend role string → frontend portal route role */
function mapRole(r: string): Session['role'] {
  const u = r.toUpperCase()
  if (u === 'SUPER_ADMIN') return 'super_admin'
  if (u === 'ADMIN') return 'admin'
  if (u === 'MANAGER') return 'manager'
  if (u === 'GMF_HANDLER' || u === 'ADMIN1') return 'gmf_handler'
  if (u === 'ENVELOPE_HANDLER') return 'envelope_handler'
  return 'customer'
}

export function getDestinationRoute(session: Session): string {
  if (session.isNewUser) {
    return '/request-access'
  }
  if (session.role === 'super_admin' || session.roles?.includes('SUPER_ADMIN')) {
    return '/super-admin'
  }
  
  // Normalized active roles
  const activeRoles = session.roles && session.roles.length > 0
    ? session.roles.map(r => r.toUpperCase())
    : [session.role.toUpperCase()]

  // If user only has 1 operational role, take them directly into that workspace
  if (activeRoles.length === 1) {
    const single = activeRoles[0]
    if (single === 'ADMIN') return '/admin'
    if (single === 'GMF_HANDLER' || single === 'ADMIN1') return '/gmf-handler'
    if (single === 'ENVELOPE_HANDLER') return '/envelope-handler'
    if (single === 'MANAGER') return '/manager'
  }

  // If user has multiple operational workspaces granted (e.g. testuser016)
  return '/role-select'
}

function buildSessionFromMe(me: {
  id: number
  email: string
  role: string
  roles?: string[]
  is_new_user?: boolean
  customer_id?: number | null
}): Session {
  const cleanEmail = (me.email || '').trim().toLowerCase()
  const isSuper = me.role.toUpperCase() === 'SUPER_ADMIN' ||
    (me.roles && me.roles.map(r => r.toUpperCase()).includes('SUPER_ADMIN')) ||
    cleanEmail === 'testuser018@intranet.slt.com.lk'

  if (isSuper) {
    return { role: 'super_admin', roles: ['SUPER_ADMIN'], email: cleanEmail }
  }

  if (me.is_new_user) {
    return { role: 'customer', roles: [], email: cleanEmail, isNewUser: true }
  }

  const mappedRole = mapRole(me.role)
  const allRoles = me.roles ?? [me.role.toUpperCase()]
  if (mappedRole === 'customer' && me.customer_id != null) {
    return { role: 'customer', roles: allRoles, email: cleanEmail, customerId: me.customer_id }
  }
  return { role: mappedRole, roles: allRoles, email: cleanEmail }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const { instance, accounts, inProgress } = useMsal()
  const navigate = useNavigate()
  
  const [session, setSession] = useState<Session | null>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })
  
  const [isChecking, setIsChecking] = useState(() => {
    if (typeof window === 'undefined') return false
    const url = window.location.href
    const hasAuth = url.includes('code=') || url.includes('error=') || url.includes('id_token=') || sessionStorage.getItem('msal-post-login') === 'pending'
    return hasAuth || !getToken()
  })
  const isInitializing = useRef(false)

  useEffect(() => {
    // Wait until MSAL has finished its initial interactions (including redirect handling)
    if (inProgress !== InteractionStatus.None || isInitializing.current) {
      return
    }

    async function init() {
      if (isInitializing.current) return
      isInitializing.current = true

      try {
        let token: string | null = getToken()
        let account = instance.getActiveAccount() || accounts[0] || instance.getAllAccounts()[0] || null

        // 1. Check redirect result from MSAL if token not already captured
        if (!token) {
          try {
            const redirectResult = await instance.handleRedirectPromise()
            if (redirectResult) {
              token = redirectResult.idToken || redirectResult.accessToken || null
              if (redirectResult.account) {
                account = redirectResult.account
                instance.setActiveAccount(redirectResult.account)
              }
            }
          } catch (e) {
            console.warn('handleRedirectPromise exception (non-fatal):', e)
          }
        }

        if (account) {
          instance.setActiveAccount(account)
        }

        // 2. If no token, but an MSAL account exists, acquire token silently
        if (!token && account) {
          try {
            const silentResult = await instance.acquireTokenSilent({
              scopes: ['openid', 'profile', 'email'],
              account,
            })
            token = silentResult.idToken || silentResult.accessToken || null
          } catch (e) {
            console.warn('acquireTokenSilent failed:', e)
          }
        }

        // 3. If token obtained from MSAL or existing stored token:
        if (token) {
          setToken(token)
          sessionStorage.removeItem('msal-post-login')

          try {
            const emailHint = account?.username || undefined
            const me = await authMe(emailHint)
            const s = buildSessionFromMe(me)
            setSession(s)
            localStorage.setItem(STORAGE_KEY, JSON.stringify(s))

            const currentPath = window.location.pathname
            if (currentPath === '/login' || currentPath === '/') {
              navigate(getDestinationRoute(s), { replace: true })
            }
            return
          } catch (authErr) {
            console.error('authMe error with MSAL token:', authErr)
            const raw = localStorage.getItem(STORAGE_KEY)
            if (raw) {
              try {
                const cached = JSON.parse(raw)
                setSession(cached)
                const currentPath = window.location.pathname
                if (currentPath === '/login' || currentPath === '/') {
                  navigate(getDestinationRoute(cached), { replace: true })
                }
                return
              } catch {}
            }
            clearToken()
            localStorage.removeItem(STORAGE_KEY)
            setSession(null)
            return
          }
        }

        // 4. No token and no active MSAL account
        setSession(null)
      } catch (err) {
        console.error('AuthProvider init error:', err)
        const raw = localStorage.getItem(STORAGE_KEY)
        if (raw) {
          try {
            setSession(JSON.parse(raw))
          } catch {}
        } else {
          clearToken()
          localStorage.removeItem(STORAGE_KEY)
          setSession(null)
        }
      } finally {
        setIsChecking(false)
        isInitializing.current = false
      }
    }

    init()
  }, [instance, accounts, inProgress, navigate])

  function login(s: Session) {
    setSession(s)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
    setIsChecking(false)
  }

  function logout() {
    setSession(null)
    localStorage.removeItem(STORAGE_KEY)
    clearToken()
    clearStaleMsalInteractions()
    if (accounts.length > 0) {
      instance.logoutRedirect({
        account: accounts[0],
        postLogoutRedirectUri: window.location.origin + '/login',
      }).catch(() => {
        clearStaleMsalInteractions()
        navigate('/login', { replace: true })
      })
    } else {
      navigate('/login', { replace: true })
    }
  }

  return (
    <AuthContext.Provider value={{ session, isChecking, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
