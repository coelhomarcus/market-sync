import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { clock } from '../../lib/format'
import { MODE_COLOR } from '../../lib/modes'
import type { BusEvent } from '../../lib/types'
import { useLive } from '../../state/live'

const MAX_LINES = 400
const HIDDEN = new Set(['seq', 'type', 'ts', 'request_id', 'mode', 'kind', 'record', 'result'])

const TYPE_COLOR: Record<string, string> = {
  request_start: 'text-white font-semibold',
  request_end: 'text-white font-semibold',
  market_connect: 'text-white/60',
  market_response: 'text-[#7ee2a8]',
  market_retry: 'text-[#ffb4a6]',
  market_error: 'text-[#ff8a75] font-semibold',
}

/** Os campos do evento como chave=valor, do jeito que chegaram pelo WebSocket. */
function fields(e: BusEvent) {
  return Object.entries(e)
    .filter(([k, v]) => !HIDDEN.has(k) && v != null && typeof v !== 'object')
    .map(([k, v]) => `${k}=${typeof v === 'string' && /\s/.test(v) ? JSON.stringify(v) : v}`)
    .join('  ')
}

/** Todos os eventos publicados pelo agregador, um por linha, como num terminal. */
export function RawLog() {
  const { log, connected } = useLive()
  const [frozen, setFrozen] = useState<BusEvent[] | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const stick = useRef(true) // acompanha o fim da lista enquanto o usuário não rolar para cima

  const source = frozen ?? log
  const lines = useMemo(() => source.slice(0, MAX_LINES).reverse(), [source]) // mais antigo em cima
  const newer = frozen ? log.length - frozen.length : 0

  useLayoutEffect(() => {
    if (stick.current && box.current) box.current.scrollTop = box.current.scrollHeight
  }, [lines])

  return (
    <div className="overflow-hidden rounded-2xl border border-linha bg-tinta">
      <div className="flex items-center gap-3 border-b border-white/10 px-4 py-2 text-xs text-white/70">
        <span className="flex items-center gap-1.5">
          <span className={`size-2 rounded-full ${connected ? 'bg-[#7ee2a8]' : 'bg-tomate'}`} aria-hidden />
          ws://…/ws/events
        </span>
        <span className="tabular-nums">{lines.length} eventos</span>
        <button
          onClick={() => setFrozen(frozen ? null : log)}
          className="ml-auto rounded-full border border-white/20 px-3 py-0.5 font-semibold text-white hover:bg-white/10"
        >
          {frozen ? `Continuar${newer > 0 ? ` (${newer} novos)` : ''}` : 'Pausar'}
        </button>
      </div>
      <div
        ref={box}
        onScroll={(e) => {
          const el = e.currentTarget
          stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40
        }}
        className="h-[36rem] overflow-auto overscroll-contain p-3 font-mono text-[12px] leading-relaxed"
        role="log"
        aria-label="Eventos brutos do WebSocket"
      >
        {lines.length === 0 && <p className="text-white/50">Esperando eventos…</p>}
        {lines.map((e) => (
          <div key={e.seq} className="flex gap-3 whitespace-nowrap">
            <span className="text-white/40 tabular-nums">{clock(e.ts)}</span>
            <span className="w-16 shrink-0 text-white/40">{e.request_id ?? ''}</span>
            <span className="w-11 shrink-0 font-semibold" style={{ color: e.mode ? MODE_COLOR[e.mode] : undefined }}>
              {e.mode === 'sequential' ? 'SEQ' : e.mode === 'concurrent' ? 'CONC' : ''}
            </span>
            <span className={`w-36 shrink-0 ${TYPE_COLOR[e.type] ?? 'text-gema'}`}>{e.type}</span>
            <span className="text-white/80">{fields(e)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
