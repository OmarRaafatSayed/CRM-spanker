/**
 * App.tsx
 * =======
 * Root component with production-grade persistent session management.
 *
 * Session lifecycle
 * -----------------
 *  1. MOUNT  — loadStoredSession() re-hydrates auth from localStorage.
 *              If a valid, non-expired token is found, the user skips the
 *              login screen immediately (no flicker, no network round-trip).
 *
 *  2. LOGIN  — POST /auth/login → stores session + user via setSupabaseSession().
 *              All subsequent API calls automatically include the Bearer token
 *              (api.ts reads it from the same store on every request).
 *
 *  3. LOGOUT — clearSupabaseSession() wipes localStorage + memory cache.
 *              React state is reset to the login screen.
 *
 *  4. EXPIRY — isSessionValid() checks the stored expires_at timestamp on
 *              mount. Expired sessions are cleared and the user sees the
 *              login screen rather than a confusing 401 mid-session.
 */
import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './shared/ui/card'
import { Button } from './shared/ui/button'
import { Input } from './shared/ui/input'
import { Label } from './shared/ui/label'
import { Toaster } from './shared/ui/toaster'
import { LuxuryStatCard } from './shared/ui/LuxuryStatCard'
import { LuxuryCard } from './shared/ui/LuxuryCard'
import { LuxuryBadge } from './shared/ui/LuxuryBadge'
import { FlightSearch } from './domains/flights/components/FlightSearch'
import { HotelManagement } from './domains/hotels/components/HotelManagement'
import { VisaManagement } from './domains/visa/components/VisaManagement'
import { ManualPaymentLedger } from './domains/payments/components/PaymentLedger'
import { CRMCustomers } from './domains/customers/components/CRMCustomers'
import { DesktopSidebar, MobileTabBar, MobileDrawer, NAV_IDS } from './app/layout/Sidebar'
import { LangToggle } from './app/layout/LangToggle'
import {
  Plane, Hotel, FileText, CreditCard,
  LogIn, UserPlus, Users, ChevronRight, Loader2, Eye, EyeOff,
  TrendingUp, Clock, Package, CheckCircle2, Wifi, Settings,
  PackagePlus, Image, UserCheck, ScrollText,
} from 'lucide-react'
import {
  supabase,
  clearSupabaseSession,
  loadStoredSession,
  getStoredUser,
  isSessionValid,
  type StoredUser,
} from './shared/services/supabase'

// ── Constants ─────────────────────────────────────────────────────────────────

const DASH_ICONS = {
  flights:  { icon: Plane,      color: 'bg-blue-500'    },
  hotels:   { icon: Hotel,      color: 'bg-emerald-500' },
  visa:     { icon: FileText,   color: 'bg-violet-500'  },
  payments: { icon: CreditCard, color: 'bg-amber-500'   },
} as const

// ── Types ─────────────────────────────────────────────────────────────────────

interface AuthState {
  isLoggedIn: boolean
  /** true only during the initial mount check — prevents a login-screen flash */
  isHydrating: boolean
  user: StoredUser | null
}

// ── Component ─────────────────────────────────────────────────────────────────

function App() {
  const { t } = useTranslation()

  // ── Session state ─────────────────────────────────────────────────────────
  const [auth, setAuth] = useState<AuthState>({
    isLoggedIn: false,
    isHydrating: true,   // start hydrating; resolved in the effect below
    user: null,
  })

  // ── UI state ──────────────────────────────────────────────────────────────
  const [isLogin,          setIsLogin]          = useState(true)
  const [activeTab,        setActiveTab]         = useState('dashboard')
  const [sidebarCollapsed, setSidebarCollapsed]  = useState(false)
  const [drawerOpen,       setDrawerOpen]        = useState(false)
  const [authError,        setAuthError]         = useState<string | null>(null)
  const [isSubmitting,     setIsSubmitting]      = useState(false)
  const [showPassword,     setShowPassword]      = useState(false)
  const [formData, setFormData] = useState({
    email: '', password: '', firstName: '', lastName: '',
  })

  // ── Step 1: Re-hydration on mount ─────────────────────────────────────────
  // Runs once. Asks the Supabase SDK for the current session (reads from
  // localStorage, validates expiry, refreshes token if needed).
  // If valid → skip login screen. If expired/absent → show login.
  useEffect(() => {
    let cancelled = false

    loadStoredSession().then(stored => {
      if (cancelled) return

      if (stored && isSessionValid()) {
        setAuth({ isLoggedIn: true, isHydrating: false, user: stored.user })
      } else {
        if (stored) clearSupabaseSession()
        setAuth({ isLoggedIn: false, isHydrating: false, user: null })
      }
    })

    // Also listen for session changes (token refresh, sign-out from another tab)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (cancelled) return
      if (session) {
        setAuth({
          isLoggedIn: true,
          isHydrating: false,
          user: { id: session.user.id, email: session.user.email ?? '' },
        })
      } else {
        setAuth({ isLoggedIn: false, isHydrating: false, user: null })
      }
    })

    return () => {
      cancelled = true
      subscription.unsubscribe()
    }
  }, [])

  // ── Step 2: Login / Signup ────────────────────────────────────────────────
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError(null)
    setIsSubmitting(true)

    try {
      if (isLogin) {
        // ── Sign in ──────────────────────────────────────────────────────────
        const { data, error } = await supabase.auth.signInWithPassword({
          email:    formData.email,
          password: formData.password,
        })

        if (error) {
          setAuthError(error.message)
          return
        }

        if (!data.session) {
          setAuthError(t('auth.authFailed'))
          return
        }

        setAuth({
          isLoggedIn: true,
          isHydrating: false,
          user: { id: data.user.id, email: data.user.email ?? '' },
        })

      } else {
        // ── Sign up ──────────────────────────────────────────────────────────
        const { data, error } = await supabase.auth.signUp({
          email:    formData.email,
          password: formData.password,
          options: {
            data: {
              first_name: formData.firstName,
              last_name:  formData.lastName,
              full_name:  `${formData.firstName} ${formData.lastName}`.trim(),
            },
          },
        })

        if (error) {
          setAuthError(error.message)
          return
        }

        // Supabase may require email confirmation before a session is issued
        if (!data.session) {
          setAuthError(t('auth.checkEmail'))
          return
        }

        setAuth({
          isLoggedIn: true,
          isHydrating: false,
          user: { id: data.user!.id, email: data.user!.email ?? '' },
        })
      }

      // Clear sensitive fields on success
      setFormData(prev => ({ ...prev, password: '', firstName: '', lastName: '' }))

    } catch {
      setAuthError(t('auth.networkError'))
    } finally {
      setIsSubmitting(false)
    }
  }, [isLogin, formData, t])

  // ── Step 3: Logout ────────────────────────────────────────────────────────
  const handleLogout = useCallback(async () => {
    // Sign out from Supabase (clears localStorage + server session)
    await clearSupabaseSession()

    // Reset all React state
    setAuth({ isLoggedIn: false, isHydrating: false, user: null })
    setActiveTab('dashboard')
    setFormData({ email: '', password: '', firstName: '', lastName: '' })
    setAuthError(null)
  }, [])

  const setField = (field: string) =>
    (e: React.ChangeEvent<HTMLInputElement>) =>
      setFormData(prev => ({ ...prev, [field]: e.target.value }))

  // ── Hydration splash (prevents login-screen flash on refresh) ────────────
  if (auth.isHydrating) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-blue-600">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600 shadow-lg">
            <Plane className="h-7 w-7 text-white" />
          </div>
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      </div>
    )
  }

  // ── Login / Signup Screen ─────────────────────────────────────────────────
  if (!auth.isLoggedIn) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <Card className="w-full max-w-md shadow-xl">
          <CardHeader className="text-center pb-2">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600 shadow-lg">
              <Plane className="h-7 w-7 text-white" />
            </div>
            <CardTitle className="text-2xl font-bold">{t('app.name')}</CardTitle>
            <CardDescription>
              {isLogin ? t('auth.signInDesc') : t('auth.signUpDesc')}
            </CardDescription>
          </CardHeader>

          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {!isLogin && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="fn">{t('auth.firstName')}</Label>
                    <Input
                      id="fn"
                      placeholder={t('auth.firstNamePlaceholder')}
                      value={formData.firstName}
                      onChange={setField('firstName')}
                      disabled={isSubmitting}
                      required
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="ln">{t('auth.lastName')}</Label>
                    <Input
                      id="ln"
                      placeholder={t('auth.lastNamePlaceholder')}
                      value={formData.lastName}
                      onChange={setField('lastName')}
                      disabled={isSubmitting}
                      required
                    />
                  </div>
                </div>
              )}

              <div className="space-y-1">
                <Label htmlFor="email">{t('auth.email')}</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder={t('auth.emailPlaceholder')}
                  value={formData.email}
                  onChange={setField('email')}
                  disabled={isSubmitting}
                  required
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="password">{t('auth.password')}</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder={t('auth.passwordPlaceholder')}
                    value={formData.password}
                    onChange={setField('password')}
                    disabled={isSubmitting}
                    required
                    className="pe-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    className="absolute end-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                    tabIndex={-1}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword
                      ? <EyeOff className="h-4 w-4" />
                      : <Eye    className="h-4 w-4" />
                    }
                  </button>
                </div>
              </div>

              {/* Error message — replaces the blocking alert() */}
              {authError && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {authError}
                </p>
              )}

              <Button
                type="submit"
                className="w-full bg-blue-600 hover:bg-blue-700 h-11 text-base"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <><Loader2 className="me-2 h-4 w-4 animate-spin" />{t('auth.signIn')}...</>
                ) : isLogin ? (
                  <><LogIn className="me-2 h-4 w-4" />{t('auth.signIn')}</>
                ) : (
                  <><UserPlus className="me-2 h-4 w-4" />{t('auth.signUp')}</>
                )}
              </Button>
            </form>

            <div className="mt-4 flex items-center justify-between">
              <Button
                variant="ghost"
                onClick={() => { setIsLogin(!isLogin); setAuthError(null) }}
                className="text-sm text-gray-500 px-0"
                disabled={isSubmitting}
              >
                {isLogin ? t('auth.noAccount') : t('auth.hasAccount')}
              </Button>
              <LangToggle compact />
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // ── Main App ──────────────────────────────────────────────────────────────
  const displayEmail = auth.user?.email ?? formData.email
  const pageTitle    = t(`nav.${activeTab}`)

  return (
    <>
      <div className="flex h-screen bg-gray-100 overflow-hidden">

        {/* Desktop Sidebar */}
        <DesktopSidebar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          email={displayEmail}
          onSignOut={handleLogout}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(c => !c)}
        />

        {/* Main area */}
        <div className="flex-1 flex flex-col overflow-hidden bg-gradient-to-b from-[var(--color-bg-primary)] to-white">

          {/* Top bar with Luxury Styling */}
          <header className="bg-white border-b border-[var(--color-border-luxury)] h-14 md:h-16 flex items-center px-4 md:px-6 shrink-0 shadow-sm gap-3">
            <div className="flex-1 min-w-0">
              <h1 className="text-base md:text-lg font-semibold text-[var(--color-text-primary)] truncate">{pageTitle}</h1>
              <p className="text-xs text-[var(--color-text-muted)] hidden sm:block">{t('app.tagline')}</p>
            </div>
            <LangToggle />
            <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)] shrink-0">
              <Users className="h-4 w-4" />
              <span className="hidden sm:inline truncate max-w-[160px]">{displayEmail}</span>
            </div>
          </header>

          {/* Page content */}
          <main className="flex-1 overflow-y-auto p-4 md:p-6 pb-24 md:pb-6">

            {activeTab === 'dashboard' && (
              <div className="space-y-5 max-w-5xl mx-auto">
                <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 md:gap-4">
                  <LuxuryStatCard
                    label={t('dashboard.visits')}
                    value="4,821"
                    subtext={t('dashboard.thisMonth')}
                    icon={<TrendingUp className="h-6 w-6" />}
                    badgeColor="blue"
                    variant="premium"
                  />
                  <LuxuryStatCard
                    label={t('dashboard.pendingLeads')}
                    value="13"
                    subtext={t('dashboard.awaitingCRM')}
                    icon={<Clock className="h-6 w-6" />}
                    badgeColor="cyan"
                    variant="premium"
                  />
                  <LuxuryStatCard
                    label={t('dashboard.activePackages')}
                    value="8"
                    subtext={t('dashboard.onWebsite')}
                    icon={<Package className="h-6 w-6" />}
                    badgeColor="emerald"
                    variant="premium"
                  />
                  <LuxuryStatCard
                    label={t('dashboard.completed')}
                    value="142"
                    subtext={t('dashboard.allTime')}
                    icon={<CheckCircle2 className="h-6 w-6" />}
                    badgeColor="gold"
                    variant="premium"
                  />
                </div>

                <LuxuryCard variant="glass" className="p-6">
                  <h2 className="text-luxury-heading text-lg mb-1">{t('dashboard.welcome')}</h2>
                  <p className="text-luxury-body mb-4">{t('dashboard.welcomeDesc')}</p>
                  <div className="flex gap-2">
                    <LuxuryBadge label={t('dashboard.statusConnected')} variant="approved" style="gradient" icon={<Wifi className="h-3 w-3" />} />
                    <LuxuryBadge label={t('dashboard.statusReady')}     variant="info"     style="gradient" icon={<Settings className="h-3 w-3" />} />
                  </div>
                </LuxuryCard>

                <div>
                  <h2 className="text-luxury-heading text-base mb-3">{t('dashboard.quickActions')}</h2>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {[
                      { label: t('dashboard.addPackage'),  Icon: PackagePlus,  color: 'text-emerald-600' },
                      { label: t('dashboard.addBanner'),   Icon: Image,        color: 'text-blue-600'    },
                      { label: t('dashboard.reviewLeads'), Icon: UserCheck,   color: 'text-amber-600'   },
                      { label: t('dashboard.systemLogs'),  Icon: ScrollText,   color: 'text-purple-600'  },
                    ].map(item => (
                      <LuxuryCard
                        key={item.label}
                        variant="default"
                        className="flex flex-col items-center gap-2 text-center !p-4 cursor-pointer"
                        onClick={() => {}}
                      >
                        <item.Icon className={`h-7 w-7 ${item.color}`} />
                        <span className="text-sm font-medium text-[var(--color-text-primary)]">{item.label}</span>
                      </LuxuryCard>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'customers' && <CRMCustomers />}
            {activeTab === 'flights'  && <FlightSearch />}
            {activeTab === 'hotels'   && <HotelManagement />}
            {activeTab === 'visa'     && <VisaManagement />}
            {activeTab === 'payments' && <ManualPaymentLedger />}

          </main>
        </div>
      </div>

      {/* Mobile bottom tab bar */}
      <MobileTabBar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onOpenDrawer={() => setDrawerOpen(true)}
      />

      {/* Mobile vaul drawer */}
      <MobileDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        email={displayEmail}
        onSignOut={handleLogout}
      />

      {/* Toast notifications */}
      <Toaster />
    </>
  )
}

export default App
