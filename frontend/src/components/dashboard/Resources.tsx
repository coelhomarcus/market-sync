import { duration, num } from '../../lib/format'
import { MODE_COLOR, MODE_LABEL } from '../../lib/markets'
import type { MetricRecord, Mode, Resources } from '../../lib/types'

const MODES: Mode[] = ['sequential', 'concurrent']

function avg(records: MetricRecord[], mode: Mode, pick: (r: MetricRecord & { resources: Resources }) => number) {
  const list = records.filter((r): r is MetricRecord & { resources: Resources } => r.mode === mode && r.resources?.cpu_ms != null)
  return list.length ? list.reduce((s, r) => s + pick(r), 0) / list.length : null
}

function Metric({ title, values, format }: { title: string; values: Record<Mode, number | null>; format: (v: number) => string }) {
  const max = Math.max(...MODES.map((k) => values[k] ?? 0), 1e-9)
  return (
    <div className="p-5">
      <h3 className="mb-3 font-semibold">{title}</h3>
      <div className="space-y-3">
        {MODES.map((mode) => (
          <div key={mode}>
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="text-cinza">{MODE_LABEL[mode]}</span>
              <span className="font-display text-lg font-bold tabular-nums">{values[mode] == null ? '—' : format(values[mode]!)}</span>
            </div>
            <div className="mt-1 h-2.5 rounded-full bg-papel">
              <div className="h-full rounded-full" style={{ width: `${((values[mode] ?? 0) / max) * 100}%`, background: MODE_COLOR[mode] }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function ResourcesPanel({ records }: { records: MetricRecord[] }) {
  const by = (pick: (r: MetricRecord & { resources: Resources }) => number) => ({
    sequential: avg(records, 'sequential', pick),
    concurrent: avg(records, 'concurrent', pick),
  })

  return (
    <div className="overflow-hidden rounded-2xl border border-linha bg-white">
      <p className="border-b border-linha bg-folha-clara/50 px-5 py-4 font-display text-lg font-bold">
        Mesma CPU, mais threads: o concorrente não trabalha menos, ele espera os mercados ao mesmo tempo.
      </p>
      <div className="grid divide-y divide-linha sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        <Metric title="Tempo de resposta" values={by((r) => r.total_ms)} format={duration} />
        <Metric title="CPU usada" values={by((r) => r.resources.cpu_ms)} format={(v) => `${num(v, 1)} ms`} />
        <Metric title="Threads consultando os mercados" values={by((r) => r.resources.threads)} format={(v) => num(v, 0)} />
      </div>
    </div>
  )
}
