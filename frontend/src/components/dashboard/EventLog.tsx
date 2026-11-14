import { useMemo, useState } from 'react'
import { bytes, clock, duration, int } from '../../lib/format'
import { MODE_COLOR, MODE_LABEL } from '../../lib/modes'
import type { BusEvent, Mode } from '../../lib/types'
import { useLive } from '../../state/live'
import { useMarkets } from '../../state/markets'
import { Timeline, timelineScale, type TimelineEntry } from '../Timeline'

interface MarketRun extends TimelineEntry {
  count?: number
  bytes?: number
}

interface Request {
  id: string
  start: BusEvent
  end?: BusEvent
  markets: Record<string, MarketRun>
}

/** Junta os eventos do WebSocket por consulta (request_id), da mais nova para a mais antiga. */
function groupByRequest(log: BusEvent[]): Request[] {
  const byId = new Map<string, Request>()
  for (const e of [...log].reverse()) {
    if (!e.request_id) continue
    if (e.type === 'request_start') byId.set(e.request_id, { id: e.request_id, start: e, markets: {} })
    const req = byId.get(e.request_id)
    const id = e.market
    if (!req) continue // o começo ficou de fora do buffer
    if (e.type === 'market_connect' && id) req.markets[id] = { market_id: id, start_ms: e.t_ms ?? 0, thread: e.thread }
    if (e.type === 'market_retry' && id && req.markets[id]) req.markets[id] = { ...req.markets[id], attempts: (e.attempt ?? 1) + 1 }
    if ((e.type === 'market_response' || e.type === 'market_error') && id) {
      req.markets[id] = {
        ...req.markets[id],
        market_id: id,
        end_ms: e.t_ms,
        ok: e.type === 'market_response',
        error: e.error,
        attempts: e.attempts,
        count: e.count,
        bytes: e.bytes as number | undefined,
      }
    }
    if (e.type === 'request_end') req.end = e
  }
  return [...byId.values()].reverse()
}

function origin(e: BusEvent) {
  if (e.source === 'comparacao') return 'Comparação'
  if (e.source === 'benchmark') return 'Repetir 5×'
  if (e.source === 'cliente_tcp') return e.kind === 'basket' ? 'Cesta (cliente TCP)' : 'Cliente TCP'
  return e.kind === 'basket' ? 'Cesta' : 'Loja'
}

/** Situação de um mercado em poucas palavras. */
function outcome(m: MarketRun | undefined): { tone: 'ok' | 'fail' | 'wait'; short: string; long: string } {
  if (!m) return { tone: 'wait', short: 'na fila', long: 'ainda não começou' }
  const tries = m.attempts ?? 1
  if (m.end_ms == null) {
    return tries > 1
      ? { tone: 'fail', short: `tentativa ${tries}…`, long: `fora do ar, tentando de novo (tentativa ${tries})` }
      : { tone: 'wait', short: '…', long: 'esperando a resposta' }
  }
  const time = duration(m.end_ms - m.start_ms)
  if (m.ok) {
    const retry = tries > 1 ? ` na ${tries}ª tentativa` : ''
    return { tone: 'ok', short: time, long: `${int(m.count ?? 0)} produtos, ${bytes(m.bytes ?? 0)}${retry}` }
  }
  if (m.error?.startsWith('tempo')) return { tone: 'fail', short: 'timeout', long: 'desistiu: passou de 3 s sem responder' }
  return { tone: 'fail', short: 'fora do ar', long: `desistiu após ${tries} ${tries === 1 ? 'tentativa' : 'tentativas'}` }
}

const TONE = {
  ok: 'bg-folha-clara text-folha',
  fail: 'bg-tomate/10 text-tomate',
  wait: 'bg-papel text-cinza',
}

function RequestCard({ req, open, onToggle }: { req: Request; open: boolean; onToggle: () => void }) {
  const { markets, name, short } = useMarkets()
  const mode = req.start.mode as Mode
  const runs = Object.values(req.markets)
  const total = req.end?.total_ms
  const lastMs = Math.max(0, ...runs.map((m) => m.end_ms ?? m.start_ms))
  const ids = markets.length ? markets.map((m) => m.id) : runs.map((m) => m.market_id)
  const what = req.start.kind === 'basket' ? req.start.query : req.start.query ? `“${req.start.query}”` : 'catálogo inteiro'

  return (
    <li className="overflow-hidden rounded-xl border border-linha bg-white">
      <button onClick={onToggle} aria-expanded={open} className="w-full p-3 text-left hover:bg-papel/50">
        <div className="flex items-center gap-2">
          <span className="rounded-full px-2.5 py-0.5 text-xs font-semibold text-white" style={{ background: MODE_COLOR[mode] }}>
            {MODE_LABEL[mode]}
          </span>
          <span className="min-w-0 truncate font-semibold">{what}</span>
          <span className="shrink-0 text-xs text-cinza">
            {origin(req.start)} · {clock(req.start.ts).slice(0, 8)}
          </span>
          <span className="ml-auto font-display text-lg font-bold tabular-nums" style={{ color: total != null ? MODE_COLOR[mode] : undefined }}>
            {total != null ? duration(total) : 'consultando…'}
          </span>
          <span className={`text-cinza transition-transform ${open ? 'rotate-90' : ''}`} aria-hidden>
            ›
          </span>
        </div>
        <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Resultado de cada mercado">
          {ids.map((id) => {
            const o = outcome(req.markets[id])
            return (
              <li key={id} className={`rounded-full px-2 py-0.5 text-xs font-medium tabular-nums ${TONE[o.tone]} ${o.tone === 'wait' && req.markets[id] ? 'animate-pulse' : ''}`}>
                {o.tone === 'ok' ? '✓' : o.tone === 'fail' ? '✕' : '•'} {short(id)} <span className="opacity-75">{o.short}</span>
              </li>
            )
          })}
        </ul>
      </button>

      {open && (
        <div className="space-y-4 border-t border-linha bg-papel/40 p-4">
          <Timeline mode={mode} entries={runs} scaleMs={timelineScale(total ?? lastMs)} nowMs={total == null ? lastMs : undefined} />
          <table className="w-full text-sm tabular-nums">
            <thead>
              <tr className="text-left text-xs text-cinza">
                <th className="py-1 font-medium">Mercado</th>
                <th className="py-1 font-medium">Thread</th>
                <th className="py-1 text-right font-medium">Começou</th>
                <th className="py-1 text-right font-medium">Terminou</th>
                <th className="py-1 pl-4 font-medium">Resultado</th>
              </tr>
            </thead>
            <tbody>
              {ids.map((id) => {
                const m = req.markets[id]
                const o = outcome(m)
                return (
                  <tr key={id} className="border-t border-linha">
                    <td className="py-1.5 font-medium">{name(id)}</td>
                    <td className="py-1.5 font-mono text-xs text-cinza">{m?.thread ?? '—'}</td>
                    <td className="py-1.5 text-right">{m ? duration(m.start_ms) : '—'}</td>
                    <td className="py-1.5 text-right">{m?.end_ms != null ? duration(m.end_ms) : '—'}</td>
                    <td className={`py-1.5 pl-4 ${o.tone === 'fail' ? 'text-tomate' : o.tone === 'wait' ? 'text-cinza' : ''}`}>{o.long}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="text-sm text-cinza">
            {mode === 'sequential'
              ? 'Uma thread só: cada mercado começa quando o anterior termina, e o total é a soma de todos.'
              : 'Uma thread por mercado: todos começam juntos, e o total é o tempo do mais lento.'}
          </p>
        </div>
      )}
    </li>
  )
}

export function EventLog() {
  const { log } = useLive()
  const requests = useMemo(() => groupByRequest(log).slice(0, 30), [log])
  // só um cartão aberto por vez; até alguém clicar, fica aberto o mais recente
  const [openId, setOpenId] = useState<string | null | undefined>(undefined)
  const openNow = openId === undefined ? requests[0]?.id : openId

  return (
    <ol className="h-[36rem] space-y-2 overflow-y-auto overscroll-contain rounded-2xl border border-linha bg-papel/60 p-3" aria-label="Consultas recentes">
      {requests.length === 0 && <li className="p-3 text-sm text-cinza">Nenhuma consulta ainda.</li>}
      {requests.map((r) => (
        <RequestCard key={r.id} req={r} open={r.id === openNow} onToggle={() => setOpenId(r.id === openNow ? null : r.id)} />
      ))}
    </ol>
  )
}
