import { duration } from '../../lib/format'
import { MODE_COLOR, MODE_LABEL } from '../../lib/markets'
import { lastOf } from '../../lib/stats'
import type { MetricRecord, Mode } from '../../lib/types'
import { Timeline } from '../Timeline'

export function LastTimelines({ records }: { records: MetricRecord[] }) {
  const seq = lastOf(records, 'sequential')
  const conc = lastOf(records, 'concurrent')
  const scale = Math.max(seq?.total_ms ?? 0, conc?.total_ms ?? 0, 500)

  const panel = (mode: Mode, rec?: MetricRecord) => (
    <div className="min-w-0">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="font-semibold">
          <span className="mr-2 inline-block size-2.5 rounded-full" style={{ background: MODE_COLOR[mode] }} />
          Última consulta {MODE_LABEL[mode].toLowerCase()}
        </h3>
        {rec && <span className="font-display text-xl font-bold tabular-nums">{duration(rec.total_ms)}</span>}
      </div>
      {rec ? (
        <>
          <Timeline entries={rec.markets} scaleMs={scale} />
          <p className="mt-2 text-xs text-cinza">
            {rec.kind === 'basket' ? `Comparação de ${rec.query}` : rec.query ? `Busca por “${rec.query}”` : 'Catálogo inteiro'}
            {rec.source === 'benchmark' && ' (benchmark)'}. Threads usadas: {new Set(rec.markets.map((m) => m.thread)).size}.
          </p>
        </>
      ) : (
        <p className="rounded-lg border border-dashed border-linha p-6 text-center text-sm text-cinza">
          Nenhuma consulta {MODE_LABEL[mode].toLowerCase()} ainda. Troque o modo no topo e faça uma busca na loja.
        </p>
      )}
    </div>
  )

  return (
    <div className="grid gap-8 rounded-2xl border border-linha bg-white p-6 lg:grid-cols-2">
      {panel('sequential', seq)}
      {panel('concurrent', conc)}
    </div>
  )
}
