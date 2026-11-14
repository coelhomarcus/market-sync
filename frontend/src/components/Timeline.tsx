import { useState } from 'react'
import { duration } from '../lib/format'
import { MARKETS, marketColor, MARKET_BY_ID } from '../lib/markets'

export interface TimelineEntry {
  market_id: string
  start_ms: number
  end_ms?: number
  ok?: boolean
  error?: string | null
  thread?: string
}

interface Props {
  entries: TimelineEntry[]
  scaleMs: number
  nowMs?: number // para barras ainda em andamento
  compact?: boolean
  axis?: boolean
}

function niceStep(max: number) {
  for (const step of [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000]) if (max / step <= 6) return step
  return 10000
}

/** Diagrama de Gantt: uma linha por mercado, barra do início ao fim da consulta TCP. */
export function Timeline({ entries, scaleMs, nowMs, compact, axis = !compact }: Props) {
  const [hover, setHover] = useState<string | null>(null)
  const scale = Math.max(scaleMs, 1)
  const byId = Object.fromEntries(entries.map((e) => [e.market_id, e]))
  const rowH = compact ? 'h-2.5' : 'h-5'
  const step = niceStep(scale)
  const ticks = Array.from({ length: Math.floor(scale / step) + 1 }, (_, i) => i * step)

  return (
    <div className={compact ? 'space-y-1' : 'space-y-2'}>
      {MARKETS.map((m) => {
        const e = byId[m.id]
        const end = e?.end_ms ?? nowMs
        const pending = e && e.end_ms == null
        const failed = e?.ok === false
        const left = e ? (e.start_ms / scale) * 100 : 0
        const width = e && end != null ? Math.max(((end - e.start_ms) / scale) * 100, 0.6) : 0
        return (
          <div key={m.id} className="flex items-center gap-2">
            <span className={`shrink-0 truncate text-cinza ${compact ? 'w-20 text-[11px]' : 'w-28 text-xs'}`}>{m.short}</span>
            <div className={`relative flex-1 ${rowH}`} onMouseLeave={() => setHover(null)}>
              {axis &&
                ticks.map((t) => (
                  <div key={t} className="absolute inset-y-[-4px] w-px bg-linha" style={{ left: `${(t / scale) * 100}%` }} />
                ))}
              {e && (
                <div
                  className={`absolute inset-y-0 rounded-[4px] ${pending ? 'bar-pending' : ''}`}
                  style={{
                    left: `${left}%`,
                    width: `${Math.min(width, 100 - left)}%`,
                    background: failed
                      ? `repeating-linear-gradient(135deg, ${marketColor(m.id)} 0 3px, transparent 3px 6px)`
                      : marketColor(m.id),
                    boxShadow: failed ? `inset 0 0 0 1.5px ${marketColor(m.id)}` : undefined,
                  }}
                  onMouseEnter={() => setHover(m.id)}
                  onFocus={() => setHover(m.id)}
                  tabIndex={compact ? -1 : 0}
                  aria-label={`${MARKET_BY_ID[m.id].name}: ${failed ? 'falhou' : pending ? 'aguardando' : duration((e.end_ms ?? 0) - e.start_ms)}`}
                />
              )}
              {!compact && e && !pending && (
                <span
                  className={`pointer-events-none absolute top-1/2 -translate-y-1/2 text-xs whitespace-nowrap tabular-nums ${
                    left + width > 84 && !failed ? 'pr-1.5 font-semibold text-white' : 'pl-1.5 text-cinza'
                  }`}
                  style={left + width > 84 ? { right: `${Math.max(100 - left - width, 0)}%` } : { left: `${left + width}%` }}
                >
                  {failed ? 'falhou' : duration((e.end_ms ?? 0) - e.start_ms)}
                </span>
              )}
              {hover === m.id && e && !compact && (
                <div
                  className="absolute bottom-full z-10 mb-2 w-60 rounded-lg bg-tinta px-3 py-2 text-xs text-white shadow-lg"
                  style={{ left: `${Math.min(left, 60)}%` }}
                >
                  <p className="font-semibold">{MARKET_BY_ID[m.id].name}</p>
                  <p className="tabular-nums">
                    {duration(e.start_ms)} → {e.end_ms != null ? duration(e.end_ms) : 'aguardando'}
                  </p>
                  {e.thread && <p className="text-white/70">thread: {e.thread}</p>}
                  {e.error && <p className="text-[#ffb4a6]">{e.error}</p>}
                </div>
              )}
            </div>
          </div>
        )
      })}
      {axis && (
        <div className="flex gap-2">
          <span className="w-28 shrink-0" />
          <div className="relative h-4 flex-1 text-[11px] text-cinza tabular-nums">
            {ticks.map((t) => (
              <span
                key={t}
                className={`absolute whitespace-nowrap ${t / scale > 0.9 ? '-translate-x-full' : t === 0 ? '' : '-translate-x-1/2'}`}
                style={{ left: `${(t / scale) * 100}%` }}
              >
                {t === 0 ? '0' : duration(t)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
