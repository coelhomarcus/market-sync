import { useState } from 'react'
import { bytes, int } from '../../lib/format'
import type { MarketStatus } from '../../lib/types'
import { LatencySlider } from './LatencySlider'

function StatusBadge({ m }: { m: MarketStatus }) {
  const [tone, text, icon] = !m.reachable
    ? ['bg-tomate/10 text-tomate', 'Processo parado', 'M3 3l6 6M9 3 3 9']
    : !m.online
      ? ['bg-[#fff1d6] text-[#9a5b00]', 'Fora do ar', 'M3 3h6v6H3z']
      : ['bg-folha-clara text-folha', 'No ar', 'M2.5 6.5 5 9l4.5-5.5']
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden>
        <path d={icon} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {text}
    </span>
  )
}

const COLS = 'lg:grid-cols-[minmax(0,1.3fr)_7.5rem_minmax(15rem,2fr)_minmax(0,1.1fr)_6rem_8.5rem]'

function Row({ m, configure }: { m: MarketStatus; configure: (id: string, cfg: { latency_ms?: number; online?: boolean }) => Promise<unknown> }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const run = async (cfg: { latency_ms?: number; online?: boolean }) => {
    setErr(null)
    try {
      await configure(m.id, cfg)
    } catch (e) {
      setErr((e as Error).message)
      throw e
    }
  }

  return (
    <li className={`grid grid-cols-2 items-center gap-x-4 gap-y-3 px-5 py-4 ${COLS}`}>
      <div className="col-span-2 flex items-center gap-3 lg:col-span-1">
        <span className="size-3 shrink-0 rounded-full" style={{ background: m.color }} aria-hidden />
        <div className="min-w-0">
          <p className="truncate font-semibold">{m.name}</p>
          <p className="text-xs text-cinza tabular-nums">porta TCP {m.port}</p>
        </div>
      </div>
      <div>
        <StatusBadge m={m} />
      </div>
      <div className="col-span-2 lg:col-span-1">
        <LatencySlider
          value={m.latency_ms ?? 0}
          color={m.color}
          disabled={!m.reachable}
          label={`Latência simulada de ${m.name}`}
          onCommit={(v) => run({ latency_ms: v })}
        />
      </div>
      <div className="text-sm">
        {m.reachable ? (
          <>
            <p className="tabular-nums">{int(m.products ?? 0)} produtos</p>
            <p className="text-xs text-cinza tabular-nums">{bytes(m.db_bytes)}</p>
          </>
        ) : (
          <p className="text-xs text-cinza">—</p>
        )}
      </div>
      <p className="text-sm tabular-nums lg:text-right">
        {m.reachable ? int(m.requests_served ?? 0) : '—'}
        <span className="text-cinza lg:hidden"> consultas</span>
      </p>
      <div className="text-right">
        <button
          disabled={!m.reachable || busy}
          onClick={() => {
            setBusy(true)
            run({ online: !m.online })
              .catch(() => {})
              .finally(() => setBusy(false))
          }}
          className={`w-full rounded-full px-3 py-1.5 text-sm font-semibold lg:w-auto ${
            m.online ? 'border border-tomate/40 text-tomate hover:bg-tomate/5' : 'bg-folha text-white hover:bg-folha-escura'
          } disabled:opacity-40`}
        >
          {m.online ? 'Tirar do ar' : 'Colocar no ar'}
        </button>
      </div>
      {err && <p className="col-span-full text-sm text-tomate">{err}</p>}
    </li>
  )
}

export function MarketsTable({
  markets,
  error,
  configure,
}: {
  markets: MarketStatus[]
  error: string | null
  configure: (id: string, cfg: { latency_ms?: number; online?: boolean }) => Promise<unknown>
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-linha bg-white">
      <div className={`hidden gap-x-4 border-b border-linha bg-papel/60 px-5 py-2.5 text-xs font-semibold text-cinza lg:grid ${COLS}`}>
        <span>Mercado</span>
        <span>Situação</span>
        <span>
          Latência <span className="font-normal">(traço = timeout de 3 s)</span>
        </span>
        <span>Banco</span>
        <span className="text-right">Consultas</span>
        <span />
      </div>
      {error && <p className="px-5 py-3 text-sm text-tomate">{error}</p>}
      {markets.length === 0 && !error && <p className="px-5 py-6 text-sm text-cinza">Carregando…</p>}
      <ul className="divide-y divide-linha">
        {markets.map((m) => (
          <Row key={m.id} m={m} configure={configure} />
        ))}
      </ul>
    </div>
  )
}
