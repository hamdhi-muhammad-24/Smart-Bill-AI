import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  ShieldCheck,
  Zap,
  Moon,
  Sun
} from 'lucide-react'
import { useTheme } from '@/components/ThemeProvider'
import { useAuth } from '../auth/AuthProvider'
import { setToken } from '../lib/api'
import Brand from '../components/Brand'
import { Button } from '@/components/ui/button'
import { useMsal } from '@azure/msal-react'
import { InteractionStatus } from '@azure/msal-browser'
import { loginRequest, clearStaleMsalInteractions } from '../auth/msalConfig'

// Remove ROLE_HOME

export default function Login() {
  const { isChecking, session, login } = useAuth()
  const { resolvedTheme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const { instance, inProgress } = useMsal()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Redirect if already authenticated
  useEffect(() => {
    if (!isChecking && session) {
      if (session.isNewUser) {
        navigate('/request-access', { replace: true })
      } else {
        navigate('/role-select', { replace: true })
      }
    }
  }, [isChecking, session, navigate])

  if (isChecking) return null

  const isMsalBusy = inProgress !== InteractionStatus.None

  async function handleMicrosoftLogin() {
    if (loading) return
    setError(null)
    setLoading(true)
    clearStaleMsalInteractions()
    try {
      // Use redirect (not popup) so auth happens in the main window.
      // After redirect, MSAL returns to the app and AuthProvider handles the token.
      sessionStorage.setItem('msal-post-login', 'pending')
      await instance.loginRedirect(loginRequest)
      // loginRedirect navigates away — code below never runs
    } catch (err: any) {
      console.error('MSAL Login error:', err)
      sessionStorage.removeItem('msal-post-login')
      clearStaleMsalInteractions()
      setLoading(false)

      const errMsg = String(err?.message || '')
      const errCode = String(err?.errorCode || '')

      if (errCode === 'timed_out' || errMsg.includes('timed_out') || errMsg.includes('failed_to_redirect')) {
        // User clicked browser back button or navigation was cancelled
        setError(null)
      } else if (errCode === 'interaction_in_progress' || errMsg.includes('interaction_in_progress')) {
        // Interaction lock was cleared; try login once more automatically
        try {
          sessionStorage.setItem('msal-post-login', 'pending')
          await instance.loginRedirect(loginRequest)
        } catch {
          setError(null)
          setLoading(false)
        }
      } else if (errCode === 'user_cancelled' || errMsg.includes('user_cancelled')) {
        setError(null)
      } else {
        setError(errMsg || 'Authentication failed or was cancelled.')
      }
    }
  }

  function handleDevLogin(targetRole: 'admin' | 'gmf_handler' | 'envelope_handler' | 'manager') {
    const devToken = `dev-${targetRole}-token`
    setToken(devToken)
    // For dev, grant all roles to admin, otherwise just the target role
    const devRoles = targetRole === 'admin'
      ? ['ADMIN', 'GMF_HANDLER', 'ENVELOPE_HANDLER', 'MANAGER']
      : [targetRole.toUpperCase().replace('GMF_HANDLER', 'GMF_HANDLER')]
    login({
      role: targetRole,
      roles: devRoles,
      email: `${targetRole}@slt.lk`,
    })
    navigate('/role-select')
  }

  return (
    <main className="min-h-svh w-full flex bg-background selection:bg-[#0066b3]/20 selection:text-[#0066b3]">
      <div className="relative hidden lg:flex flex-1 flex-col overflow-hidden bg-slate-950">
        <div className="absolute inset-0 z-0">
          <div className="absolute -left-[10%] top-[10%] h-[700px] w-[700px] rounded-full bg-[#0066b3]/30 blur-[140px] animate-pulse [animation-duration:15s]" />
          <div className="absolute right-[0%] top-[30%] h-[600px] w-[600px] rounded-full bg-[#00a651]/20 blur-[130px] animate-pulse [animation-duration:12s] [animation-delay:2s]" />
          <div className="absolute -bottom-[20%] left-[30%] h-[800px] w-[800px] rounded-full bg-[#00b2e3]/20 blur-[150px] animate-pulse [animation-duration:18s] [animation-delay:4s]" />
        </div>
        <div className="absolute top-0 left-0 w-full h-16 flex items-center px-8 z-20">
          <Brand size="md" tone="dark" className="text-white drop-shadow-md" />
        </div>
        <div className="relative z-10 flex h-full w-full flex-col justify-center px-10 xl:px-16 pt-10">
          <div className="max-w-xl xl:max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-[13px] font-bold tracking-wide text-white shadow-sm backdrop-blur-md mb-8">
              <ShieldCheck size={16} className="text-[#00b2e3]" />
              SLT-MOBITEL SECURE GATEWAY
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl xl:text-6xl leading-[1.15]">
              AI-Powered <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#00b2e3] to-[#00a651]">
                Invoice Generation
              </span>
            </h1>
            <p className="mt-8 text-lg font-medium leading-relaxed text-slate-300">
              Access the centralized SLT-MOBITEL billing environment. Manage massive GMF batch cycles securely, verify generated statements, and monitor the automated pipeline in real-time.
            </p>
            <div className="mt-12 flex items-center gap-8">
              <div className="flex items-center gap-4">
                <div className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-white/10 text-white backdrop-blur-sm border border-white/10 shadow-lg">
                  <Zap size={26} className="text-[#00b2e3]" />
                </div>
                <div>
                  <p className="text-[15px] font-bold text-white">High-Speed Pipeline</p>
                  <p className="text-[13px] font-medium text-slate-400">Process millions of records</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-white/10 text-white backdrop-blur-sm border border-white/10 shadow-lg">
                  <ShieldCheck size={26} className="text-[#00a651]" />
                </div>
                <div>
                  <p className="text-[15px] font-bold text-white">Bank-Grade Security</p>
                  <p className="text-[13px] font-medium text-slate-400">Microsoft Entra ID SSO</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="relative flex w-full flex-col bg-background lg:w-[500px] xl:w-[650px] lg:shrink-0">
        <div className="absolute top-0 left-0 w-full h-16 px-6 sm:px-8 flex justify-between items-center z-20">
          <div className="lg:hidden">
            <Brand size="md" tone={resolvedTheme === 'dark' ? 'dark' : 'light'} />
          </div>
          <div className="ml-auto flex items-center gap-3">
            <Button
              variant="outline"
              size="icon"
              className="rounded-full bg-background hover:bg-muted border-border transition-all"
              onClick={toggleTheme}
              title="Toggle theme"
            >
              <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0 text-foreground" />
              <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100 text-foreground" />
              <span className="sr-only">Toggle theme</span>
            </Button>
            <Button asChild variant="outline" className="gap-2 text-foreground font-semibold shadow-sm rounded-full bg-background hover:bg-muted border-border transition-all">
              <Link to="/">
                <ArrowLeft size={16} />
                Return to Portal
              </Link>
            </Button>
          </div>
        </div>
        <div className="absolute inset-0 z-0 lg:hidden overflow-hidden">
          <div className="absolute -top-[10%] right-[0%] h-[500px] w-[500px] rounded-full bg-[#0066b3]/5 blur-[100px]" />
          <div className="absolute bottom-[0%] left-[0%] h-[500px] w-[500px] rounded-full bg-[#00a651]/5 blur-[100px]" />
        </div>
        <div className="relative z-10 flex h-full w-full flex-col justify-center px-6 sm:px-12 xl:px-20 pt-28 lg:pt-0">
          <div className="flex flex-col space-y-2 mb-10">
            <h2 className="text-3xl font-extrabold tracking-tight text-foreground">Staff SSO Login</h2>
            <p className="text-[15px] font-medium text-muted-foreground">
              Sign in with your SLT-MOBITEL Microsoft Entra ID account to access the billing environment.
            </p>
          </div>
          
          <div className="grid gap-7">
            {error && (
              <div className="flex gap-3 rounded-xl border border-destructive/20 bg-destructive/10 px-4 py-4 mt-2">
                <AlertCircle size={20} className="mt-0.5 shrink-0 text-destructive" />
                <p className="text-[14px] leading-relaxed text-destructive font-bold" role="alert">
                  {error}
                </p>
              </div>
            )}
            <Button
              onClick={handleMicrosoftLogin}
              className="h-16 w-full bg-gradient-to-r from-[#0066b3] to-[#00b2e3] hover:opacity-90 font-extrabold text-[16px] text-white shadow-lg shadow-[#0066b3]/25 active:scale-[0.98] border-none transition-all duration-300 rounded-xl group"
              disabled={loading || isMsalBusy}
            >
              {loading || isMsalBusy ? (
                <span className="flex items-center gap-3">
                  <span className="size-5 animate-spin rounded-full border-[3px] border-white/30 border-t-white" />
                  {isMsalBusy ? 'Initializing Microsoft Login...' : 'Connecting to Microsoft...'}
                </span>
              ) : (
                <span className="flex items-center justify-center gap-3 w-full px-2 tracking-wide">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21" className="size-6 fill-white"><path d="M10 0H0v10h10V0zM21 0H11v10h10V0zM10 11H0v10h10V11zM21 11H11v10h10V11z"/></svg>
                  Login with Microsoft
                  <ArrowRight size={20} className="transition-transform group-hover:translate-x-1" />
                </span>
              )}
            </Button>
          </div>

          {/* 1-Click Dev Test Switch */}
          <div className="mt-8 rounded-2xl border border-dashed border-border/80 bg-muted/30 p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Zap size={14} className="text-[#00a651]" /> 1-Click Dev Test Switch
              </span>
              <span className="text-[10px] font-bold bg-[#00a651]/15 text-[#00a651] px-2 py-0.5 rounded-full">DEV MODE</span>
            </div>
            <p className="text-xs text-muted-foreground font-medium">Test any portal instantly without needing a Microsoft account:</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <button
                type="button"
                onClick={() => handleDevLogin('admin')}
                className="h-11 text-xs font-extrabold rounded-xl border border-border/80 bg-card hover:bg-[#0066b3]/10 hover:border-[#0066b3]/40 text-foreground hover:text-[#0066b3] dark:hover:text-[#00b2e3] transition-all flex items-center justify-center shadow-xs cursor-pointer active:scale-95"
              >
                Admin
              </button>
              <button
                type="button"
                onClick={() => handleDevLogin('gmf_handler')}
                className="h-11 text-xs font-extrabold rounded-xl border border-border/80 bg-card hover:bg-cyan-500/10 hover:border-cyan-500/40 text-foreground hover:text-cyan-700 dark:hover:text-cyan-400 transition-all flex items-center justify-center shadow-xs cursor-pointer active:scale-95"
              >
                GMF Handler
              </button>
              <button
                type="button"
                onClick={() => handleDevLogin('envelope_handler')}
                className="h-11 text-xs font-extrabold rounded-xl border border-border/80 bg-card hover:bg-purple-500/10 hover:border-purple-500/40 text-foreground hover:text-purple-700 dark:hover:text-purple-400 transition-all flex items-center justify-center shadow-xs cursor-pointer active:scale-95"
              >
                Envelope
              </button>
              <button
                type="button"
                onClick={() => handleDevLogin('manager')}
                className="h-11 text-xs font-extrabold rounded-xl border border-border/80 bg-card hover:bg-emerald-500/10 hover:border-emerald-500/40 text-foreground hover:text-emerald-700 dark:hover:text-emerald-400 transition-all flex items-center justify-center shadow-xs cursor-pointer active:scale-95"
              >
                User Manager
              </button>
            </div>
          </div>
          <p className="mt-12 text-center text-[13px] font-medium text-muted-foreground leading-relaxed">
            Secured by SLT-MOBITEL Enterprise Gateway. <br className="hidden sm:block" /> By signing in, you agree to our <a href="#" className="text-foreground font-bold hover:text-[#0066b3] transition-colors">Terms of Service</a> & <a href="#" className="text-foreground font-bold hover:text-[#0066b3] transition-colors">Privacy Policy</a>.
          </p>
        </div>
      </div>
    </main>
  )
}
