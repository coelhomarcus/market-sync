import { useMemo, useState } from 'react'
import { bytes, clock, duration } from '../../lib/format'
import { marketColor, marketName, MODE_LABEL } from '../../lib/markets'
import type { BusEvent } from '../../lib/types'
import { useLive } from '../../state/live'

type Filter = 'tudo' | 'requisicoes' | 'respostas' | 'erros'
const FILTERS: { id: Filter; label: string }[] = [
  { id: 'tudo', label: 'Tudo' },
  { id: 'requisicoes', label: 'Requisições' },
  { id: 'respostas', label: 'Respostas' },
  { id: 'erros', label: 'Erros' },
]

function describe(e: BusEvent): { text: string; tone?: 'erro' | 'fim' | 'inicio' } {
  switch (e.type) {
    case 'request_start':
      return {
        text: `${MODE_LABEL[e.mode!]}: ${e.kind === 'basket' ? e.query : `busca “${e.query || 'catálogo inteiro'}”`}${e.source === 'benchmark' ? ' (benchmark)' : ''}`,
        tone: 'inicio',
      }
    case 'market_connect':
      return { text: `connect() → ${marketName(e.market!)}` }
    case 'market_response':
      return { text: `${marketName(e.market!)} respondeu ${e.count} itens (${bytes(e.bytes as number)}) em ${duration(e.duration_ms)}` }
    case 'market_error':
      return { text: `${marketName(e.market!)}: ${e.error}`, tone: 'erro' }
    case 'request_end':
      return { text: `Concluída em ${duration(e.total_ms)}: ${e.ok_count} ok, ${e.error_count} falhas`, tone: 'fim' }
    case 'market_config':
      return { text: `${marketName(e.market!)} reconfigurado: ${e.online ? 'no ar' : 'fora do ar'}, latência ${duration(e.latency_ms)}` }
    case 'benchmark_start':
      return { text: `Benchmark iniciado: ${e.runs} rodadas de cada modo`, tone: 'inicio' }
    case 'benchmark_progress':
      return { text: `Benchmark: rodada ${e.done} de ${e.runs}` }
    case 'benchmark_end':
      return { text: 'Benchmark concluído', tone: 'fim' }
    case 'metrics_reset':
      return { text: 'Métricas zeradas' }
    default:
      return { text: e.type }
  }
}

function matches(e: BusEvent, f: Filter) {
  if (f === 'tudo') return true
  if (f === 'erros') return e.type === 'market_error'
  if (f === 'respostas') return e.type === 'market_response' || e.type === 'market_error'
  return e.type === 'request_start' || e.type === 'request_end'
}

export function EventLog() {
  const { log, connected } = useLive()
  const [filter, setFilter] = useState<Filter>('tudo')
  const [frozen, setFrozen] = useState<BusEvent[] | null>(null)
  const source = frozen ?? log
  const shown = useMemo(() => source.filter((e) => matches(e, filter)), [source, filter])
  const waiting = frozen ? log.length - frozen.length : 0

  return (
    <div className="flex h-full flex-col rounded-2xl border border-linha bg-white">
      <div className="flex flex-wrap items-center gap-2 border-b border-linha px-4 py-3">
        <div role="group" aria-label="Filtrar eventos" className="flex flex-wrap gap-1">
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
        <button
          onClick={() => setFrozen(frozen ? null : log)}
          className="ml-auto rounded-full border border-linha px-3 py-1 text-xs font-semibold hover:bg-papel"
          aria-pressed={!!frozen}
        >
          {frozen ? `Retomar${waiting > 0 ? ` (${waiting} novos)` : ''}` : 'Pausar'}
        </button>
        <span className={`flex items-center gap-1.5 text-xs ${connected ? 'text-folha' : 'text-tomate'}`}>
          <span className={`size-2 rounded-full ${connected ? 'bg-folha' : 'bg-tomate'}`} aria-hidden />
          {connected ? 'ao vivo' : 'reconectando'}
        </span>
      </div>
      <ol className="h-[28rem] flex-1 overflow-y-auto p-2 font-mono text-[12px]" aria-live="off">
        {shown.length === 0 && <li className="p-3 font-sans text-sm text-cinza">Nenhum evento ainda. Faça uma busca na loja ou rode o benchmark.</li>}
        {shown.map((e) => {
          const d = describe(e)
          return (
            <li
              key={e.seq}
              className={`grid grid-cols-[6.5rem_0.5rem_minmax(0,1fr)_auto] items-baseline gap-2 rounded px-2 py-1 ${
                d.tone === 'erro' ? 'bg-tomate/10 text-tomate' : d.tone === 'fim' ? 'bg-folha-clara/60 font-medium' : d.tone === 'inicio' ? 'font-medium' : ''
              }`}
            >
              <span className="text-cinza tabular-nums">{clock(e.ts)}</span>
              {e.market ? <span className="size-2 self-center rounded-full" style={{ background: marketColor(e.market) }} aria-hidden /> : <span />}
              <span className="break-words">{d.text}</span>
              <span className="text-cinza tabular-nums">{e.t_ms != null && e.type !== 'request_end' ? `+${Math.round(e.t_ms)} ms` : ''}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
