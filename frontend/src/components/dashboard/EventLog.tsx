import { useMemo, useState } from 'react'
import { bytes, clock, duration, int } from '../../lib/format'
import { marketColor, marketName, MARKETS, MODE_COLOR, MODE_LABEL } from '../../lib/markets'
import type { BusEvent, Mode, Resources } from '../../lib/types'
import { useLive } from '../../state/live'
import { Timeline, type TimelineEntry } from '../Timeline'

type Filter = 'todas' | 'sequential' | 'concurrent' | 'falhas'
const FILTERS: { id: Filter; label: string }[] = [
  { id: 'todas', label: 'Todas' },
  { id: 'sequential', label: 'Sequenciais' },
  { id: 'concurrent', label: 'Concorrentes' },
  { id: 'falhas', label: 'Com falha' },
]

interface MarketState extends TimelineEntry {
  bytes?: number
  count?: number
}

interface RequestItem {
  type: 'request'
  key: string
  seq: number
  start: BusEvent
  end?: BusEvent
  events: BusEvent[]
  markets: Record<string, MarketState>
}

interface SystemItem {
  type: 'system'
  key: string
  seq: number
  event: BusEvent
}

type Item = RequestItem | SystemItem

/** Agrupa o fluxo de eventos do WebSocket por requisição (request_id). */
function groupEvents(log: BusEvent[]): Item[] {
  const items: Item[] = []
  const byId = new Map<string, RequestItem>()
  for (const e of [...log].reverse()) {
    if (e.request_id) {
      let req = byId.get(e.request_id)
      if (!req) {
        if (e.type !== 'request_start') continue // começo ficou fora do buffer
        req = { type: 'request', key: e.request_id, seq: e.seq, start: e, events: [], markets: {} }
        byId.set(e.request_id, req)
        items.push(req)
      }
      req.events.push(e)
      const id = e.market
      if (e.type === 'market_connect' && id) req.markets[id] = { market_id: id, start_ms: e.t_ms ?? 0, thread: e.thread }
      if ((e.type === 'market_response' || e.type === 'market_error') && id) {
        req.markets[id] = {
          ...(req.markets[id] ?? { market_id: id, start_ms: (e.t_ms ?? 0) - (e.duration_ms ?? 0) }),
          end_ms: e.t_ms,
          ok: e.type === 'market_response',
          error: e.error,
          bytes: e.bytes as number | undefined,
          count: e.count,
        }
      }
      if (e.type === 'request_end') req.end = e
    } else if (['market_config', 'benchmark_start', 'benchmark_end', 'metrics_reset'].includes(e.type)) {
      items.push({ type: 'system', key: `s${e.seq}`, seq: e.seq, event: e })
    }
  }
  return items.reverse()
}

function describeRequest(e: BusEvent) {
  if (e.kind === 'basket') return `Comparação de ${e.query}`
  return e.query ? `Busca por “${e.query}”` : 'Catálogo inteiro'
}

function rawLine(e: BusEvent) {
  switch (e.type) {
    case 'request_start':
      return 'requisição recebida pelo agregador'
    case 'market_connect':
      return `connect() → ${marketName(e.market!)} (${e.thread})`
    case 'market_response':
      return `${marketName(e.market!)} respondeu ${e.count} itens, ${bytes(e.bytes as number)}, em ${duration(e.duration_ms)}`
    case 'market_error':
      return `${marketName(e.market!)}: ${e.error}`
    case 'request_end':
      return `resposta enviada ao navegador: ${duration(e.total_ms)}`
    default:
      return e.type
  }
}

function describeSystem(e: BusEvent) {
  switch (e.type) {
    case 'market_config':
      return `${marketName(e.market!)} reconfigurado: ${e.online ? 'no ar' : 'fora do ar'}, latência ${duration(e.latency_ms)}`
    case 'benchmark_start':
      return `Benchmark iniciado: ${e.runs} rodadas de cada modo, busca “${e.query}”`
    case 'benchmark_end':
      return 'Benchmark concluído'
    case 'metrics_reset':
      return 'Métricas zeradas'
    default:
      return e.type
  }
}

function RequestCard({ item }: { item: RequestItem }) {
  const [open, setOpen] = useState(false)
  const mode = item.start.mode as Mode
  const entries = MARKETS.map((m) => item.markets[m.id]).filter(Boolean)
  const lastMs = Math.max(0, ...entries.map((m) => m.end_ms ?? m.start_ms))
  const total = item.end?.total_ms
  const failures = entries.filter((m) => m.ok === false)
  const received = entries.reduce((n, m) => n + (m.bytes ?? 0), 0)
  const res = (item.end?.record as { resources?: Resources } | undefined)?.resources

  return (
    <li className={`rounded-xl border bg-white p-3 ${failures.length ? 'border-tomate/40' : 'border-linha'}`}>
      <div className="flex items-center gap-2">
        <span
          className="shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold text-white"
          style={{ background: MODE_COLOR[mode] }}
        >
          {MODE_LABEL[mode]}
        </span>
        <span className="min-w-0 truncate text-sm font-semibold">{describeRequest(item.start)}</span>
        {item.start.source === 'benchmark' && <span className="shrink-0 rounded bg-papel px-1.5 py-0.5 text-[11px] text-cinza">benchmark</span>}
        <span className="ml-auto shrink-0 text-xs text-cinza tabular-nums">{clock(item.start.ts)}</span>
      </div>

      <div className="mt-2.5">
        <Timeline entries={entries} scaleMs={total ?? Math.max(lastMs * 1.15, 800)} nowMs={total ? undefined : lastMs} compact />
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-cinza tabular-nums">
        {total != null ? (
          <span className="font-display text-base font-bold text-tinta">{duration(total)}</span>
        ) : (
          <span className="flex items-center gap-1.5 font-semibold text-tinta">
            <span className="size-2 animate-pulse rounded-full bg-gema" aria-hidden />
            em andamento
          </span>
        )}
        <span>
          {entries.filter((m) => m.ok).length} de {MARKETS.length} mercados
        </span>
        {received > 0 && <span>{bytes(received)} recebidos</span>}
        {res && (
          <>
            <span title="Threads criadas pelo agregador só para esta requisição">
              {res.threads_extra === 0 ? 'nenhuma thread extra' : res.threads_extra === 1 ? '1 thread extra' : `${res.threads_extra} threads extras`}
            </span>
            <span title="CPU do agregador + CPU dos mercados">CPU {res.cpu_ms.toFixed(1).replace('.', ',')} ms</span>
          </>
        )}
        <button onClick={() => setOpen(!open)} aria-expanded={open} className="ml-auto font-semibold text-folha hover:underline">
          {open ? 'Ocultar eventos' : `Ver ${item.events.length} eventos TCP`}
        </button>
      </div>

      {failures.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-tomate">
          {failures.map((f) => (
            <li key={f.market_id}>
              {marketName(f.market_id)}: {f.error}
            </li>
          ))}
        </ul>
      )}

      {open && (
        <ol className="mt-2 space-y-px rounded-lg bg-papel p-2 font-mono text-[11.5px]">
          {item.events.map((e) => (
            <li key={e.seq} className={`grid grid-cols-[4.5rem_0.5rem_minmax(0,1fr)] items-baseline gap-2 ${e.type === 'market_error' ? 'text-tomate' : ''}`}>
              <span className="text-right text-cinza tabular-nums">{e.t_ms != null ? `+${int(Math.round(e.t_ms))} ms` : ''}</span>
              {e.market ? <span className="size-2 self-center rounded-full" style={{ background: marketColor(e.market) }} aria-hidden /> : <span />}
              <span className="break-words">{rawLine(e)}</span>
            </li>
          ))}
        </ol>
      )}
    </li>
  )
}

export function EventLog() {
  const { log, connected } = useLive()
  const [filter, setFilter] = useState<Filter>('todas')
  const [withBenchmark, setWithBenchmark] = useState(true)
  const [frozen, setFrozen] = useState<BusEvent[] | null>(null)
  const items = useMemo(() => groupEvents(frozen ?? log), [frozen, log])
  const newer = frozen ? groupEvents(log).length - items.length : 0

  const shown = items.filter((it) => {
    if (it.type === 'system') return filter === 'todas'
    if (!withBenchmark && it.start.source === 'benchmark') return false
    if (filter === 'falhas') return Object.values(it.markets).some((m) => m.ok === false)
    if (filter === 'sequential' || filter === 'concurrent') return it.start.mode === filter
    return true
  })

  return (
    <div className="rounded-2xl border border-linha bg-white">
      <div className="flex flex-wrap items-center gap-2 border-b border-linha px-4 py-3">
        <div role="group" aria-label="Filtrar requisições" className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              aria-pressed={filter === f.id}
              className={`rounded-full px-3 py-1 text-xs font-semibold ${filter === f.id ? 'bg-tinta text-white' : 'text-cinza hover:bg-papel'}`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-xs text-cinza">
          <input type="checkbox" checked={withBenchmark} onChange={(e) => setWithBenchmark(e.target.checked)} className="accent-folha" />
          incluir benchmark
        </label>
        <button
          onClick={() => setFrozen(frozen ? null : log)}
          aria-pressed={!!frozen}
          className="ml-auto rounded-full border border-linha px-3 py-1 text-xs font-semibold hover:bg-papel"
        >
          {frozen ? `Retomar${newer > 0 ? ` (${newer} novas)` : ''}` : 'Pausar'}
        </button>
        <span className={`flex items-center gap-1.5 text-xs ${connected ? 'text-folha' : 'text-tomate'}`}>
          <span className={`size-2 rounded-full ${connected ? 'bg-folha' : 'bg-tomate'}`} aria-hidden />
          {connected ? 'ao vivo' : 'reconectando'}
        </span>
      </div>

      {/* altura fixa: a lista rola por dentro e a página não cresce */}
      <ol className="h-[34rem] space-y-2 overflow-y-auto overscroll-contain bg-papel/60 p-3" aria-live="off" aria-label="Requisições recentes">
        {shown.length === 0 && (
          <li className="p-3 text-sm text-cinza">
            {items.length === 0 ? 'Nenhuma requisição ainda. Faça uma busca na loja ou rode o benchmark.' : 'Nenhuma requisição com esse filtro.'}
          </li>
        )}
        {shown.map((it) =>
          it.type === 'request' ? (
            <RequestCard key={it.key} item={it} />
          ) : (
            <li key={it.key} className="flex items-center gap-2 px-1 text-xs text-cinza">
              <span className="tabular-nums">{clock(it.event.ts)}</span>
              {it.event.market && <span className="size-2 rounded-full" style={{ background: marketColor(it.event.market) }} aria-hidden />}
              <span>{describeSystem(it.event)}</span>
            </li>
          ),
        )}
      </ol>
      <p className="border-t border-linha px-4 py-2 text-xs text-cinza">
        {int(items.filter((i) => i.type === 'request').length)} requisições guardadas nesta sessão do painel; as mais novas ficam no topo.
      </p>
    </div>
  )
}
