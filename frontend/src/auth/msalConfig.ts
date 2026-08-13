import { PublicClientApplication } from '@azure/msal-browser'
import type { Configuration } from '@azure/msal-browser'

// Read values from .env
const clientId = import.meta.env.VITE_AZURE_CLIENT_ID || ''
const tenantId = import.meta.env.VITE_AZURE_TENANT_ID || ''

export const msalConfig: Configuration = {
  auth: {
    clientId: clientId,
    authority: `https://login.microsoftonline.com/${tenantId || 'common'}`,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'sessionStorage',
  },
}

export const msalInstance = new PublicClientApplication(msalConfig)

export const loginRequest = {
  scopes: ['User.Read', 'openid', 'profile', 'email'],
}
