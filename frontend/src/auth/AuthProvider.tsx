import { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { clearToken, setToken, getToken, authMe } from '../lib/api'
import { useMsal } from '@azure/msal-react'
import { loginRequest } from './msalConfig'

export interface Session {
  role: 'admin' | 'gmf_handler' | 'manager' | 'customer'
  customerId?: number
}

interface AuthContextValue {
  session: Session | null
  isChecking: boolean
  login: (session: Session) => void
  logout: () => void
}

const STORAGE_KEY = 'slt-auth'

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { instance, accounts, inProgress } = useMsal()
  const [session, setSession] = useState<Session | null>(null)
  const [isChecking, setIsChecking] = useState(true)

  useEffect(() => {
    // Wait until MSAL has finished its initial interactions
    if (inProgress !== 'none') {
      return
    }

    const currentToken = getToken()

    function acquireMsalToken() {
      instance
        .acquireTokenSilent({
          ...loginRequest,
          account: accounts[0]
        })
        .then((response) => {
          setToken(response.accessToken)
          return authMe()
        })
        .then((me) => {
          const r = me.role.toUpperCase()
          let role: Session['role'] = 'customer'
          if (r === 'ADMIN') role = 'admin'
          else if (r === 'MANAGER') role = 'manager'
          else if (r === 'GMF_HANDLER' || r === 'ADMIN1') role = 'gmf_handler'

          const verified: Session =
            role === 'customer' && me.customer_id != null
              ? { role: 'customer', customerId: me.customer_id }
              : { role }
          setSession(verified)
          localStorage.setItem(STORAGE_KEY, JSON.stringify(verified))
        })
        .catch((err) => {
          console.error("Silent token acquisition or authMe failed:", err)
          clearToken()
          localStorage.removeItem(STORAGE_KEY)
          setSession(null)
        })
        .finally(() => {
          setIsChecking(false)
        })
    }

    // 1. If we already have a local token (e.g. dev test token), verify via authMe first
    if (currentToken) {
      authMe()
        .then((me) => {
          const r = me.role.toUpperCase()
          let role: Session['role'] = 'customer'
          if (r === 'ADMIN') role = 'admin'
          else if (r === 'MANAGER') role = 'manager'
          else if (r === 'GMF_HANDLER' || r === 'ADMIN1') role = 'gmf_handler'

          const verified: Session =
            role === 'customer' && me.customer_id != null
              ? { role: 'customer', customerId: me.customer_id }
              : { role }
          setSession(verified)
          localStorage.setItem(STORAGE_KEY, JSON.stringify(verified))
        })
        .catch(() => {
          if (accounts.length > 0) {
            acquireMsalToken()
          } else {
            clearToken()
            localStorage.removeItem(STORAGE_KEY)
            setSession(null)
          }
        })
        .finally(() => {
          setIsChecking(false)
        })
      return
    }

    // 2. If no local token, check if MSAL has logged-in accounts
    if (accounts.length > 0) {
      acquireMsalToken()
    } else {
      clearToken()
      localStorage.removeItem(STORAGE_KEY)
      setSession(null)
      setIsChecking(false)
    }
  }, [instance, accounts, inProgress])

  function login(s: Session) {
    setSession(s)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
  }

  function logout() {
    setSession(null)
    localStorage.removeItem(STORAGE_KEY)
    clearToken()
    instance.logoutRedirect({ postLogoutRedirectUri: window.location.origin })
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
