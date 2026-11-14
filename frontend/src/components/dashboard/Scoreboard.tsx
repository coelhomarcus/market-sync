import { duration, int, num } from '../../lib/format'
import { MODE_COLOR, MODE_LABEL } from '../../lib/markets'
import { modeStats } from '../../lib/stats'
import type { MetricRecord, Mode } from '../../lib/types'

function ModeBar({ mode, s, max }: { mode: Mode; s: ReturnType<typeof modeStats>; max: number }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-2 font-semibold">
          <span className="size-2.5 rounded-full" style={{ background: MODE_COLOR[mode] }} aria-hidden />
          {MODE_LABEL[mode]}
        </span>
        <span className="font-display text-3xl font-bold tabular-nums">{duration(s.avg)}</span>
      </div>
      <div className="mt-1.5 h-4 rounded-full bg-papel">
        <div className="h-full rounded-full transition-[width]" style={{ width: `${((s.avg ?? 0) / max) * 100}%`, background: MODE_COLOR[mode] }} />
      </div>
      <p className="mt-1 text-xs text-cinza tabular-nums">
        {s.count === 0 ? 'nenhuma consulta' : `média de ${int(s.count)} ${s.count === 1 ? 'consulta' : 'consultas'}`}
      </p>
    </div>
  )
}

export function Scoreboard({ records }: { records: MetricRecord[] }) {
  const seq = modeStats(records, 'sequential')
  const conc = modeStats(records, 'concurrent')
  const speedup = seq.avg && conc.avg ? seq.avg / conc.avg : null
  const max = Math.max(seq.avg ?? 0, conc.avg ?? 0, 1)
  const failures = records.reduce((n, r) => n + r.error_count, 0)

  return (
    <div className="grid overflow-hidden rounded-2xl border border-linha bg-white lg:grid-cols-[1fr_2fr]">
      <div className="bg-folha p-6 text-white">
        {speedup ? (
          <>
            <p className="font-display text-7xl leading-none font-extrabold tracking-tight tabular-nums">{num(speedup)}×</p>
            <p className="mt-3 text-lg font-semibold">mais rápido no concorrente</p>
          </>
        ) : (
          <p className="font-display text-2xl font-bold">Faça buscas nos dois modos para comparar.</p>
        )}
        <p className="mt-4 text-sm text-white/75 tabular-nums">
          {int(records.length)} consultas{failures > 0 && `, ${int(failures)} falhas de mercado`}
        </p>
      </div>
      <div className="space-y-6 p-6">
        <ModeBar mode="sequential" s={seq} max={max} />
        <ModeBar mode="concurrent" s={conc} max={max} />
      </div>
    </div>
  )
}
