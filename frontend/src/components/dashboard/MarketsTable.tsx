import { useState } from 'react'
import { int } from '../../lib/format'
import type { MarketStatus } from '../../lib/types'
import { useMarkets } from '../../state/markets'

type Scenario = 'normal' | 'lento' | 'timeout' | 'fora'

const SCENARIOS: { id: Scenario; label: string }[] = [
  { id: 'normal', label: 'Normal' },
  { id: 'lento', label: 'Lento (2 s)' },
  { id: 'timeout', label: 'Timeout (5 s)' },
  { id: 'fora', label: 'Fora do ar' },
]

function current(m: MarketStatus): Scenario | null {
  if (!m.online) return 'fora'
  if (m.latency_ms === m.default_latency_ms) return 'normal'
  if (m.latency_ms === 2000) return 'lento'
  if (m.latency_ms === 5000) return 'timeout'
  return null
}

function config(m: MarketStatus, s: Scenario) {
  if (s === 'fora') return { online: false }
  const latency_ms = s === 'normal' ? m.default_latency_ms : s === 'lento' ? 2000 : 5000
  return { online: true, latency_ms }
}

function Row({ m }: { m: MarketStatus }) {
  const { configure } = useMarkets()
  const [busy, setBusy] = useState<Scenario | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const active = m.reachable ? current(m) : null

  const choose = (s: Scenario) => {
    setBusy(s)
    setErr(null)
    configure(m.id, config(m, s))
      .catch((e: Error) => setErr(e.message))
      .finally(() => setBusy(null))
  }

  return (
    <li className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3.5">
      <div className="w-44">
        <p className="font-semibold">{m.name}</p>
        <p className="text-xs text-cinza tabular-nums">
          {m.reachable ? `porta ${m.port} · ${int(m.latency_ms ?? 0)} ms` : `porta ${m.port} · processo parado`}
        </p>
      </div>
      <div role="radiogroup" aria-label={`Cenário de ${m.name}`} className="flex flex-wrap gap-1 rounded-full bg-papel p-1">
        {SCENARIOS.map((s) => {
          const on = active === s.id
          return (
            <button
              key={s.id}
              role="radio"
              aria-checked={on}
              disabled={!m.reachable || busy !== null}
              onClick={() => choose(s.id)}
              className={`rounded-full px-3 py-1 text-sm font-semibold transition-colors disabled:cursor-not-allowed ${
                on ? (s.id === 'normal' ? 'bg-folha text-white' : 'bg-tomate text-white') : 'text-cinza hover:bg-white hover:text-tinta'
              } ${busy === s.id ? 'animate-pulse' : ''}`}
            >
              {s.label}
            </button>
          )
        })}
      </div>
      <p className="ml-auto text-sm text-cinza tabular-nums">{m.reachable ? `${int(m.requests_served ?? 0)} consultas` : ''}</p>
      {err && <p className="w-full text-sm text-tomate">{err}</p>}
    </li>
  )
}

export function MarketsTable() {
  const { markets, error } = useMarkets()
  return (
    <div className="overflow-hidden rounded-2xl border border-linha bg-white">
      {error && <p className="px-5 py-3 text-sm text-tomate">{error}</p>}
      {markets.length === 0 && !error && <p className="px-5 py-6 text-sm text-cinza">Carregando…</p>}
      <ul className="divide-y divide-linha">
        {markets.map((m) => (
          <Row key={m.id} m={m} />
        ))}
      </ul>
    </div>
  )
}
