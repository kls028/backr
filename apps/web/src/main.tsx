import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import App from '@/App'
import { AuthProvider } from '@/providers/AuthProvider'
import { SolanaProvider } from '@/providers/SolanaProvider'
import '@/index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Chain-derived data goes stale on its own schedule; refetching on every
      // window focus just burns RPC quota.
      refetchOnWindowFocus: false,
      staleTime: 10_000,
      retry: 1,
    },
  },
})

const container = document.getElementById('root')
if (!container) throw new Error('Missing #root element')

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SolanaProvider>
        <AuthProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AuthProvider>
      </SolanaProvider>
    </QueryClientProvider>
  </StrictMode>,
)
