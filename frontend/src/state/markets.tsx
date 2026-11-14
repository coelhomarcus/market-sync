import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api } from '../lib/api'
import type { MarketStatus } from '../lib/types'
import { useLive } from './live'

type Config = { latency_ms?: number; online?: boolean }

interface MarketsState {
  markets: MarketStatus[] // nome, cor e situação de cada mercado, na ordem do config.py
  error: string | null
  name: (id: string) => string
  short: (id: string) => string
  configure: (id: string, cfg: Config) => Promise<MarketStatus>
}

const Ctx = createContext<MarketsState | null>(null)

/**
 * Os mercados vêm do agregador (comando STATUS por TCP), atualizados a cada 4 s:
 * o site não repete a lista de mercados que já existe no config.py.
 */
export function MarketsProvider({ children }: { children: ReactNode }) {
  const { marketsVersion } = useLive()
  const [markets, setMarkets] = useState<MarketStatus[]>([])
  const [error, setError] = useState<string | null>(null)
  const lastConfigAt = useRef(0)

  const refresh = useCallback(() => {
    const startedAt = performance.now()
    api
      .markets()
      .then((ms) => {
        if (startedAt < lastConfigAt.current) return // resposta de antes da última mudança: ignora
        setMarkets(ms)
        setError(null)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 4000)
    return () => clearInterval(id)
  }, [refresh, marketsVersion])

  const configure = useCallback(async (id: string, cfg: Config) => {
    lastConfigAt.current = performance.now()
    const status = await api.configure(id, cfg)
    lastConfigAt.current = performance.now()
    setMarkets((prev) => prev.map((m) => (m.id === status.id ? status : m)))
    return status
  }, [])

  const value = useMemo<MarketsState>(() => {
    const byId = Object.fromEntries(markets.map((m) => [m.id, m]))
    return {
      markets,
      error,
      configure,
      name: (id) => byId[id]?.name ?? id,
      short: (id) => byId[id]?.short ?? id,
    }
  }, [markets, error, configure])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useMarkets() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useMarkets fora do MarketsProvider')
  return ctx
}
