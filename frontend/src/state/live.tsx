import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api } from '../lib/api'
import type { BusEvent, MetricRecord, Mode } from '../lib/types'

/** Estado de uma requisição em andamento, montado a partir dos eventos do WebSocket. */
export interface LiveRequest {
  request_id: string
  mode: Mode
  kind: string
  query: string
  source: string
  startedAt: number // performance.now() local
  markets: Record<string, { start_ms: number; end_ms?: number; ok?: boolean; error?: string }>
  total_ms?: number
  done: boolean
}

interface LiveState {
  connected: boolean
  records: MetricRecord[]
  log: BusEvent[]
  live: LiveRequest[]
  benchmark: { running: boolean; done: number; runs: number }
  marketsVersion: number // muda quando algum mercado é reconfigurado
}

const Ctx = createContext<LiveState | null>(null)
const MAX_RECORDS = 600
const MAX_LOG = 300

export function LiveProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(false)
  const [records, setRecords] = useState<MetricRecord[]>([])
  const [log, setLog] = useState<BusEvent[]>([])
  const [live, setLive] = useState<LiveRequest[]>([])
  const [benchmark, setBenchmark] = useState({ running: false, done: 0, runs: 0 })
  const [marketsVersion, setMarketsVersion] = useState(0)
  const seen = useRef(new Set<number>())

  useEffect(() => {
    api
      .metricsHistory()
      .then((h) =>
        setRecords((prev) => {
          const ids = new Set(prev.map((r) => r.id))
          return [...h.records.filter((r) => !ids.has(r.id)), ...prev].sort((a, b) => a.id - b.id)
        }),
      )
      .catch(() => {})
  }, [])

  useEffect(() => {
    let ws: WebSocket | null = null
    let retry: ReturnType<typeof setTimeout>
    let closed = false

    const handle = (e: BusEvent) => {
      if (seen.current.has(e.seq)) return
      seen.current.add(e.seq)
      setLog((prev) => [e, ...prev].slice(0, MAX_LOG))

      switch (e.type) {
        case 'request_start':
          setLive((prev) =>
            [
              {
                request_id: e.request_id!,
                mode: e.mode!,
                kind: e.kind ?? 'search',
                query: e.query ?? '',
                source: e.source ?? 'loja',
                startedAt: performance.now(),
                markets: {},
                done: false,
              },
              ...prev,
            ].slice(0, 8),
          )
          break
        case 'market_connect':
        case 'market_response':
        case 'market_error':
          setLive((prev) =>
            prev.map((r) => {
              if (r.request_id !== e.request_id) return r
              const m = { ...(r.markets[e.market!] ?? { start_ms: e.t_ms ?? 0 }) }
              if (e.type === 'market_connect') m.start_ms = e.t_ms ?? 0
              else {
                m.end_ms = e.t_ms
                m.ok = e.type === 'market_response'
                m.error = e.error
              }
              return { ...r, markets: { ...r.markets, [e.market!]: m } }
            }),
          )
          break
        case 'request_end':
          setLive((prev) => prev.map((r) => (r.request_id === e.request_id ? { ...r, done: true, total_ms: e.total_ms } : r)))
          if (e.record) {
            const rec = { ...e.record, request_id: e.request_id }
            setRecords((prev) => (prev.some((r) => r.id === rec.id) ? prev : [...prev, rec].slice(-MAX_RECORDS)))
          }
          break
        case 'benchmark_start':
          setBenchmark({ running: true, done: 0, runs: e.runs ?? 0 })
          break
        case 'benchmark_progress':
          setBenchmark({ running: true, done: e.done ?? 0, runs: e.runs ?? 0 })
          break
        case 'benchmark_end':
          setBenchmark((b) => ({ ...b, running: false, done: b.runs }))
          break
        case 'metrics_reset':
          setRecords([])
          break
        case 'market_config':
          setMarketsVersion((v) => v + 1)
          break
      }
    }

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws/events`)
      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        if (!closed) retry = setTimeout(connect, 1500)
      }
      ws.onmessage = (msg) => {
        const data = JSON.parse(msg.data)
        if (data.type === 'hello') {
          ;(data.recent as BusEvent[]).forEach((e) => seen.current.add(e.seq))
          setLog((prev) => [...[...(data.recent as BusEvent[])].reverse(), ...prev].slice(0, MAX_LOG))
          return
        }
        handle(data as BusEvent)
      }
    }
    connect()
    return () => {
      closed = true
      clearTimeout(retry)
      ws?.close()
    }
  }, [])

  const value = useMemo(
    () => ({ connected, records, log, live, benchmark, marketsVersion }),
    [connected, records, log, live, benchmark, marketsVersion],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLive() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useLive fora do LiveProvider')
  return ctx
}
