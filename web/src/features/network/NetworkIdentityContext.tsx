import { createContext, useContext } from 'react'

const NetworkIdentityContext = createContext<string | null>(null)

export const NetworkIdentityProvider = NetworkIdentityContext.Provider

export function useNetworkIdentity() {
  return useContext(NetworkIdentityContext)
}
