import { createContext, useContext, useState, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearToken, setToken, getToken, authMe } from '../lib/api'
import { useMsal } from '@azure/msal-react'
import { InteractionStatus } from '@azure/msal-browser'
import { loginRequest, clearStaleMsalInteractions } from './msalConfig'

export interface Session {
  role: 'admin' | 'gmf_handler' | 'envelope_handler' | 'manager' | 'customer'
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
  if (u === 'ADMIN') return 'admin'
  if (u === 'MANAGER') return 'manager'
  if (u === 'GMF_HANDLER' || u === 'ADMIN1') return 'gmf_handler'
  if (u === 'ENVELOPE_HANDLER') return 'envelope_handler'
  return 'customer'
}

function buildSessionFromMe(me: {
  id: number
  email: string
  role: string
  roles?: string[]
  is_new_user?: boolean
  customer_id?: number | null
}): Session {
  if (me.is_new_user) {
    return { role: 'customer', roles: [], email: me.email, isNewUser: true }
  }
  const mappedRole = mapRole(me.role)
  const allRoles = me.roles ?? [me.role.toUpperCase()]
  if (mappedRole === 'customer' && me.customer_id != null) {
    return { role: 'customer', roles: allRoles, email: me.email, customerId: me.customer_id }
  }
  return { role: mappedRole, roles: allRoles, email: me.email }
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
        let token: string | null = null
        let account = accounts[0] || instance.getAllAccounts()[0] || null

        // 1. Check redirect result from MSAL
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

        // 2. If no redirect token, but an MSAL account exists, acquire token silently
        if (!token && account) {
          try {
            instance.setActiveAccount(account)
            const silentResult = await instance.acquireTokenSilent({
              ...loginRequest,
              account,
            })
            token = silentResult.idToken || silentResult.accessToken || null
          } catch (e) {
            console.warn('acquireTokenSilent failed:', e)
          }
        }

        // 3. If token obtained from MSAL (redirect or silent):
        if (token) {
          setToken(token)
          sessionStorage.removeItem('msal-post-login')

          try {
            const me = await authMe()
            const s = buildSessionFromMe(me)
            setSession(s)
            localStorage.setItem(STORAGE_KEY, JSON.stringify(s))

            const currentPath = window.location.pathname
            if (currentPath === '/login' || currentPath === '/') {
              if (me.is_new_user) {
                navigate('/request-access', { replace: true })
              } else {
                navigate('/role-select', { replace: true })
              }
            }
            return
          } catch (authErr) {
            console.error('authMe error with MSAL token:', authErr)
          }
        }

        // 4. Check existing stored token (e.g. dev token or persistent session)
        const storedToken = getToken()
        if (storedToken) {
          if (storedToken.startsWith('dev-')) {
            try {
              const me = await authMe()
              const s = buildSessionFromMe(me)
              setSession(s)
              localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
            } catch {
              const raw = localStorage.getItem(STORAGE_KEY)
              if (raw) {
                setSession(JSON.parse(raw))
              }
            }
            return
          }

          try {
            const me = await authMe()
            const s = buildSessionFromMe(me)
            setSession(s)
            localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
            return
          } catch {
            clearToken()
            localStorage.removeItem(STORAGE_KEY)
            setSession(null)
            return
          }
        }

        // 5. No stored token and no active MSAL account
        setSession(null)
      } catch (err) {
        console.error('AuthProvider init error:', err)
        const raw = localStorage.getItem(STORAGE_KEY)
        if (!raw) {
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
