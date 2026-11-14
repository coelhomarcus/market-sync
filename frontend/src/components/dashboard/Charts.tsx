import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { duration } from '../../lib/format'
import { MARKETS, MODE_COLOR, MODE_LABEL } from '../../lib/markets'
import { stats } from '../../lib/stats'
import type { MetricRecord, Mode } from '../../lib/types'

const AXIS = { fontSize: 12, fill: '#5b6a61' }
const secs = (v: number) => `${(v / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} s`

function Card({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-linha bg-white p-6">
      <h2 className="font-display text-xl font-bold">{title}</h2>
      <p className="mb-4 text-sm text-cinza">{subtitle}</p>
      {children}
    </section>
  )
}

function Tip({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg bg-tinta px-3 py-2 text-xs text-white shadow-lg">{children}</div>
}

export function HistoryChart({ records }: { records: MetricRecord[] }) {
  const recent = records.slice(-80)
  const data = recent.map((r, i) => ({
    n: i + 1,
    sequential: r.mode === 'sequential' ? r.total_ms : null,
    concurrent: r.mode === 'concurrent' ? r.total_ms : null,
    rec: r,
  }))
  return (
    <Card title="Histórico de tempos" subtitle={`Tempo total de cada requisição, em ordem de chegada (últimas ${recent.length}).`}>
      <div className="mb-2 flex gap-4 text-sm" aria-hidden>
        {(['sequential', 'concurrent'] as Mode[]).map((m) => (
          <span key={m} className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded" style={{ background: MODE_COLOR[m] }} />
            {MODE_LABEL[m]}
          </span>
        ))}
      </div>
      <div className="h-64">
        {data.length === 0 ? (
          <p className="grid h-full place-items-center text-sm text-cinza">Sem requisições ainda.</p>
        ) : (
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#e7ece8" />
              <XAxis dataKey="n" tick={AXIS} tickLine={false} axisLine={{ stroke: '#d9e2da' }} />
              <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={secs} width={40} />
              <Tooltip
                cursor={{ stroke: '#15241b', strokeOpacity: 0.25 }}
                content={({ active, payload }) => {
                  const rec = active && (payload?.[0]?.payload?.rec as MetricRecord | undefined)
                  if (!rec) return null
                  return (
                    <Tip>
                      <p className="font-semibold">
                        {MODE_LABEL[rec.mode]}: {duration(rec.total_ms)}
                      </p>
                      <p className="text-white/70">
                        {rec.kind === 'basket' ? rec.query : `busca “${rec.query || 'tudo'}”`}, {rec.ok_count}/{rec.markets.length} mercados
                      </p>
                    </Tip>
                  )
                }}
              />
              {(['sequential', 'concurrent'] as Mode[]).map((m) => (
                <Line
                  key={m}
                  dataKey={m}
                  name={MODE_LABEL[m]}
                  stroke={MODE_COLOR[m]}
                  strokeWidth={2}
                  dot={{ r: 3.5, fill: MODE_COLOR[m], stroke: '#fff', strokeWidth: 1.5 }}
                  activeDot={{ r: 5, stroke: '#fff', strokeWidth: 2 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  )
}

export function MarketLatencyChart({ records }: { records: MetricRecord[] }) {
  const data = MARKETS.map((m) => {
    const all = records.flatMap((r) => r.markets.filter((x) => x.market_id === m.id))
    const s = stats(all.filter((x) => x.ok).map((x) => x.duration_ms))
    return { id: m.id, name: m.short, full: m.name, color: m.color, avg: s.avg ? Math.round(s.avg) : 0, s, errors: all.filter((x) => !x.ok).length }
  })
  return (
    <Card title="Latência média por mercado" subtitle="Tempo de cada resposta TCP bem-sucedida, contando a latência simulada.">
      <div className="h-64">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }} barCategoryGap="28%">
            <CartesianGrid vertical={false} stroke="#e7ece8" />
            <XAxis dataKey="name" tick={AXIS} tickLine={false} axisLine={{ stroke: '#d9e2da' }} interval={0} />
            <YAxis tick={AXIS} tickLine={false} axisLine={false} tickFormatter={secs} width={40} />
            <Tooltip
              cursor={{ fill: '#15241b', fillOpacity: 0.05 }}
              content={({ active, payload }) => {
                const d = active && (payload?.[0]?.payload as (typeof data)[number] | undefined)
                if (!d) return null
                return (
                  <Tip>
                    <p className="font-semibold">{d.full}</p>
                    <p>média {duration(d.s.avg)}</p>
                    {d.s.count > 1 && (
                      <p className="text-white/70">
                        de {duration(d.s.min)} a {duration(d.s.max)} em {d.s.count} respostas
                      </p>
                    )}
                    {d.errors > 0 && <p className="text-[#ffb4a6]">{d.errors} falhas</p>}
                  </Tip>
                )
              }}
            />
            <Bar dataKey="avg" radius={[4, 4, 0, 0]} isAnimationActive={false} maxBarSize={48}>
              {data.map((d) => (
                <Cell key={d.id} fill={d.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {data.some((d) => d.errors > 0) && (
        <p className="mt-2 text-sm text-tomate">
          Falhas: {data.filter((d) => d.errors).map((d) => `${d.full} (${d.errors})`).join(', ')}
        </p>
      )}
    </Card>
  )
}
