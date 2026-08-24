import { PublicClientApplication } from '@azure/msal-browser'
import type { Configuration } from '@azure/msal-browser'

// Read values from .env with fallback defaults
const clientId = import.meta.env.VITE_AZURE_CLIENT_ID || '0d42d2c9-48a3-4924-980e-68c613f6737b'
const tenantId = import.meta.env.VITE_AZURE_TENANT_ID || '534253fc-dfb6-462f-b5ca-cbe81939f5ee'

export const msalConfig: Configuration = {
  auth: {
    clientId: clientId || '0d42d2c9-48a3-4924-980e-68c613f6737b',
    authority: `https://login.microsoftonline.com/${tenantId || '534253fc-dfb6-462f-b5ca-cbe81939f5ee'}`,
    knownAuthorities: ['login.microsoftonline.com'],
    redirectUri: typeof window !== 'undefined' ? window.location.origin : 'http://localhost:5173',
    postLogoutRedirectUri: typeof window !== 'undefined' ? window.location.origin : 'http://localhost:5173',
  },
  cache: {
    cacheLocation: 'sessionStorage',
  },
  system: {
    allowPlatformBroker: false, // Bypass Windows WAM broker delay for instant redirect (<50ms)
    redirectNavigationTimeout: 2000,
  },
}

export const msalInstance = new PublicClientApplication(msalConfig)

export const loginRequest = {
  scopes: ['User.Read', 'openid', 'profile', 'email'],
  prompt: 'select_account',
}

export function clearStaleMsalInteractions(): void {
  try {
    if (typeof sessionStorage !== 'undefined') {
      for (let i = sessionStorage.length - 1; i >= 0; i--) {
        const key = sessionStorage.key(i)
        if (key && (key.includes('interaction.status') || key.includes('interaction_status') || key.includes('msal-post-login'))) {
          sessionStorage.removeItem(key)
        }
      }
    }
    if (typeof localStorage !== 'undefined') {
      for (let i = localStorage.length - 1; i >= 0; i--) {
        const key = localStorage.key(i)
        if (key && (key.includes('interaction.status') || key.includes('interaction_status'))) {
          localStorage.removeItem(key)
        }
      }
    }
  } catch (e) {
    console.warn('Could not clear stale MSAL interactions:', e)
  }
}

