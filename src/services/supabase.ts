/**
 * Supabase client + auth helpers
 * ================================
 * Uses the official @supabase/supabase-js SDK.
 *
 * Exported functions keep the same signatures as the old manual store so
 * that api.ts and App.tsx only need minimal changes.
 *
 * Environment variables (must be set in .env.local and on Vercel):
 *   VITE_SUPABASE_URL      — your Supabase project URL
 *   VITE_SUPABASE_ANON_KEY — your Supabase anon/public key
 */

import { createClient, type Session, type User } from '@supabase/supabase-js'

// ── Supabase client singleton ─────────────────────────────────────────────────

const supabaseUrl      = import.meta.env.VITE_SUPABASE_URL      as string
const supabaseAnonKey  = import.meta.env.VITE_SUPABASE_ANON_KEY as string

if (!supabaseUrl || !supabaseAnonKey) {
  console.error(
    '[supabase] Missing env vars: VITE_SUPABASE_URL and/or VITE_SUPABASE_ANON_KEY. ' +
    'Add them to .env.local (dev) and Vercel Environment Variables (prod).',
  )
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,          // stores session in localStorage automatically
    autoRefreshToken: true,        // silently refreshes token before expiry
    detectSessionInUrl: true,      // handles magic-link / OAuth redirects
  },
})

// ── Re-exported types (used by App.tsx) ───────────────────────────────────────

export type { Session, User }

export interface StoredUser {
  id: string
  email: string
}

// ── Compatibility helpers (same names as before so api.ts still works) ────────

/**
 * Return the current access token from the live Supabase session.
 * Falls back to null when the user is not signed in.
 */
export function getAccessToken(): string | null {
  // supabase-js caches the session in memory after the first getSession() call.
  // For synchronous access we read directly from the internal storage key.
  const storageKey = `sb-${new URL(supabaseUrl).hostname.split('.')[0]}-auth-token`
  try {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return (parsed as { access_token?: string })?.access_token ?? null
  } catch {
    return null
  }
}

/**
 * @deprecated — session is now managed by the SDK.
 * Kept for backward compatibility; does nothing.
 */
export function setSupabaseSession(): void {
  // no-op: the SDK handles persistence automatically
}

/**
 * Sign the user out and clear the SDK session.
 * Mirrors the old clearSupabaseSession() behaviour.
 */
export async function clearSupabaseSession(): Promise<void> {
  await supabase.auth.signOut()
}

/**
 * Load the current session from the SDK (async, checks localStorage + token validity).
 * Returns null when there is no valid session.
 */
export async function loadStoredSession(): Promise<{
  session: { access_token: string; refresh_token: string; expires_at?: number }
  user: StoredUser
} | null> {
  const { data, error } = await supabase.auth.getSession()
  if (error || !data.session) return null

  const { session } = data
  return {
    session: {
      access_token:  session.access_token,
      refresh_token: session.refresh_token,
      expires_at:    session.expires_at,
    },
    user: {
      id:    session.user.id,
      email: session.user.email ?? '',
    },
  }
}

/**
 * Returns true when the SDK has a non-expired session.
 * Synchronous check using the cached token in localStorage.
 */
export function isSessionValid(): boolean {
  const token = getAccessToken()
  if (!token) return false

  // Decode exp from the JWT payload (no crypto needed — just a check)
  try {
    const [, payload] = token.split('.')
    const decoded = JSON.parse(atob(payload)) as { exp?: number }
    if (!decoded.exp) return true
    // Treat as expired 60 s early to account for clock skew
    return decoded.exp - 60 > Math.floor(Date.now() / 1000)
  } catch {
    return true // can't decode — assume valid
  }
}

/**
 * Return the stored user from the SDK session.
 */
export function getStoredUser(): StoredUser | null {
  const token = getAccessToken()
  if (!token) return null

  try {
    const [, payload] = token.split('.')
    const decoded = JSON.parse(atob(payload)) as { sub?: string; email?: string }
    if (!decoded.sub) return null
    return { id: decoded.sub, email: decoded.email ?? '' }
  } catch {
    return null
  }
}
