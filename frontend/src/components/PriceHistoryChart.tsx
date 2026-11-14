import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../lib/api'
import { brl, duration } from '../lib/format'
import { marketColor, MARKET_BY_ID, MARKETS } from '../lib/markets'
import type { PriceHistory } from '../lib/types'

const AXIS = { fontSize: 11, fill: '#5b6a61' }
const shortDay = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

/** Preço diário do produto em cada mercado, lido da tabela price_history de cada banco. */
export function PriceHistoryChart({ slug }: { slug: string }) {
  const [data, setData] = useState<PriceHistory | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ms, setMs] = useState(0)

  useEffect(() => {
    const t0 = performance.now()
    api
      .history(slug, 90)
      .then((h) => (setData(h), setMs(performance.now() - t0)))
      .catch((e: Error) => setError(e.message))
  }, [slug])

  if (error) return <p className="px-5 text-sm text-tomate">{error}</p>
  if (!data) return <p className="px-5 text-sm text-cinza">Carregando histórico de preços…</p>

  const series = data.markets.filter((m) => m.ok && m.points.length)
  const days = [...new Set(series.flatMap((m) => m.points.map((p) => p.day)))].sort()
  const rows = days.map((day) => {
    const row: Record<string, string | number> = { day }
    for (const m of series) {
      const point = m.points.find((p) => p.day === day)
      if (point) row[m.market_id] = point.price
    }
    return row
  })
  const ordered = MARKETS.filter((m) => series.some((s) => s.market_id === m.id))

  return (
    <section className="mx-5 rounded-xl border border-linha bg-white p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h4 className="font-semibold">Preço nos últimos {data.days} dias, em R$</h4>
        <span className="text-xs text-cinza tabular-nums">consulta HISTORY: {duration(ms)}</span>
      </div>
      {series.length === 0 ? (
        <p className="mt-2 text-sm text-cinza">Nenhum mercado tem histórico deste produto.</p>
      ) : (
        <>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-cinza">
            {ordered.map((m) => (
              <span key={m.id} className="flex items-center gap-1.5">
                <span className="h-0.5 w-3 rounded" style={{ background: m.color }} />
                {m.short}
              </span>
            ))}
          </div>
          <div className="mt-2 h-44">
            <ResponsiveContainer>
              <LineChart data={rows} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#e7ece8" />
                <XAxis dataKey="day" tick={AXIS} tickLine={false} axisLine={{ stroke: '#d9e2da' }} tickFormatter={shortDay} minTickGap={28} />
                <YAxis
                  tick={AXIS}
                  tickLine={false}
                  axisLine={false}
                  width={36}
                  domain={['auto', 'auto']}
                  tickFormatter={(v: number) => v.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}
                />
                <Tooltip
                  content={({ active, payload, label }) =>
                    active && payload?.length ? (
                      <div className="rounded-lg bg-tinta px-3 py-2 text-xs text-white shadow-lg">
                        <p className="mb-1 font-semibold">{shortDay(String(label))}</p>
                        {[...payload]
                          .sort((a, b) => Number(a.value) - Number(b.value))
                          .map((p) => (
                            <p key={String(p.dataKey)} className="flex justify-between gap-3 tabular-nums">
                              <span>{MARKET_BY_ID[String(p.dataKey)]?.short}</span>
                              <span>{brl(Number(p.value))}</span>
                            </p>
                          ))}
                      </div>
                    ) : null
                  }
                />
                {ordered.map((m) => (
                  <Line
                    key={m.id}
                    dataKey={m.id}
                    stroke={marketColor(m.id)}
                    strokeWidth={2}
                    dot={false}
                    type="stepAfter"
                    connectNulls
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </section>
  )
}
