import { bytes, duration, int, num } from '../../lib/format'
import { MODE_COLOR, MODE_LABEL } from '../../lib/markets'
import { modeStats } from '../../lib/stats'
import type { MarketStatus, MetricRecord, Mode } from '../../lib/types'

function ModeBar({ mode, s, max }: { mode: Mode; s: ReturnType<typeof modeStats>; max: number }) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-2 font-semibold">
          <span className="size-2.5 rounded-full" style={{ background: MODE_COLOR[mode] }} aria-hidden />
          {MODE_LABEL[mode]}
        </span>
        <span className="font-display text-2xl font-bold tabular-nums">{duration(s.avg)}</span>
      </div>
      <div className="mt-1.5 h-2.5 rounded-full bg-papel">
        <div className="h-full rounded-full" style={{ width: `${((s.avg ?? 0) / max) * 100}%`, background: MODE_COLOR[mode] }} />
      </div>
      <p className="mt-1 text-xs text-cinza tabular-nums">
        {s.count === 0 ? 'nenhuma consulta' : `${s.count} ${s.count === 1 ? 'consulta' : 'consultas'}`}
        {s.count > 1 && `, de ${duration(s.min)} a ${duration(s.max)}`}
      </p>
    </div>
  )
}

export function Scoreboard({ records, markets }: { records: MetricRecord[]; markets: MarketStatus[] }) {
  const seq = modeStats(records, 'sequential')
  const conc = modeStats(records, 'concurrent')
  const speedup = seq.avg && conc.avg ? seq.avg / conc.avg : null
  const max = Math.max(seq.avg ?? 0, conc.avg ?? 0, 1)
  const failures = records.reduce((n, r) => n + r.error_count, 0)
  const received = records.reduce((n, r) => n + r.markets.reduce((m, x) => m + (x.bytes_received ?? 0), 0), 0)
  const products = markets.reduce((n, m) => n + (m.products ?? 0), 0)
  const history = markets.reduce((n, m) => n + (m.history_rows ?? 0), 0)
  const dbBytes = markets.reduce((n, m) => n + (m.db_bytes ?? 0), 0)

  return (
    <div className="grid overflow-hidden rounded-2xl border border-linha bg-white lg:grid-cols-[1fr_1.3fr_1fr]">
      <div className="bg-folha p-6 text-white">
        <p className="text-sm text-white/75">Speedup médio</p>
        {speedup ? (
          <>
            <p className="font-display text-7xl leading-none font-extrabold tracking-tight tabular-nums">{num(speedup)}×</p>
            <p className="mt-3 text-sm text-white/85">
              O modo concorrente respondeu {num(speedup)} vezes mais rápido que o sequencial, na média das consultas abaixo.
            </p>
          </>
        ) : (
          <p className="mt-2 font-display text-2xl font-bold">Faça buscas nos dois modos para comparar</p>
        )}
      </div>
      <div className="space-y-5 border-linha p-6 lg:border-r">
        <ModeBar mode="sequential" s={seq} max={max} />
        <ModeBar mode="concurrent" s={conc} max={max} />
      </div>
      <dl className="grid grid-cols-2 content-start gap-x-4 gap-y-4 border-t border-linha p-6 text-sm lg:border-t-0">
        <div>
          <dt className="text-cinza">Requisições</dt>
          <dd className="font-display text-2xl font-bold tabular-nums">{int(records.length)}</dd>
        </div>
        <div>
          <dt className="text-cinza">Falhas de mercado</dt>
          <dd className={`font-display text-2xl font-bold tabular-nums ${failures ? 'text-tomate' : ''}`}>{int(failures)}</dd>
        </div>
        <div>
          <dt className="text-cinza">Recebido por TCP</dt>
          <dd className="font-display text-2xl font-bold tabular-nums">{bytes(received)}</dd>
        </div>
        <div>
          <dt className="text-cinza">Produtos nos bancos</dt>
          <dd className="font-display text-2xl font-bold tabular-nums">{int(products)}</dd>
        </div>
        <div className="col-span-2 text-xs text-cinza">
          {markets.length > 0 && (
            <>
              5 bancos SQLite com {int(history)} registros de preço histórico, {bytes(dbBytes)} no total.
            </>
          )}
        </div>
      </dl>
    </div>
  )
}
