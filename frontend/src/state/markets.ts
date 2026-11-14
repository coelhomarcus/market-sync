import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import type { MarketStatus } from '../lib/types'
import { useLive } from './live'

/**
 * Estado dos mercados (comando STATUS via agregador), atualizado a cada 4 s.
 *
 * Um poll que saiu ANTES da última reconfiguração é descartado ao chegar: sem isso,
 * a resposta antiga sobrescreveria o valor novo e o slider "voltaria" por um instante.
 */
export function useMarkets() {
  const { marketsVersion } = useLive()
  const [markets, setMarkets] = useState<MarketStatus[]>([])
  const [error, setError] = useState<string | null>(null)
  const lastConfigAt = useRef(0)

  const refresh = useCallback(() => {
    const startedAt = performance.now()
    api
      .markets()
      .then((ms) => {
        if (startedAt < lastConfigAt.current) return // resposta velha: ignora
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

  const configure = useCallback(async (id: string, cfg: { latency_ms?: number; online?: boolean }) => {
    lastConfigAt.current = performance.now()
    const status = await api.configure(id, cfg)
    lastConfigAt.current = performance.now()
    setMarkets((prev) => prev.map((m) => (m.id === status.id ? status : m)))
    return status
  }, [])

  return { markets, error, configure }
}
