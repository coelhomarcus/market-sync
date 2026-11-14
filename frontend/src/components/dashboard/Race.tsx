import { useState } from 'react'
import { api } from '../../lib/api'
import { duration, num } from '../../lib/format'
import { MODE_COLOR, MODE_LABEL, MODES } from '../../lib/modes'
import { lastOf, modeStats } from '../../lib/stats'
import type { MetricRecord, Mode, SearchResponse } from '../../lib/types'
import { useLive, useLiveQuery } from '../../state/live'
import { Timeline, timelineScale, type TimelineEntry } from '../Timeline'

type Results = Partial<Record<Mode, SearchResponse>>

function average(records: MetricRecord[], mode: Mode, pick: (r: MetricRecord) => number | undefined) {
  const values = records.filter((r) => r.mode === mode).map(pick).filter((v): v is number => v != null)
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0
}

/**
 * Uma linha com a média de todas as comparações ("Comparar" e "Repetir 5×"). Nelas os dois
 * modos fazem a mesma consulta, então tempo e CPU são comparáveis; a loja fica de fora.
 */
function AverageLine({ records: all }: { records: MetricRecord[] }) {
  const records = all.filter((r) => r.source !== 'loja')
  const seq = modeStats(records, 'sequential')
  const conc = modeStats(records, 'concurrent')
  const pairs = Math.min(seq.count, conc.count)
  if (!pairs || !seq.avg || !conc.avg) return null
  const threads = (m: Mode) => num(average(records, m, (r) => r.resources?.threads), 0)
  const cpu = (m: Mode) => num(average(records, m, (r) => r.resources?.cpu_ms), 0)
  return (
    <p className="border-t border-linha px-5 py-3 text-sm text-cinza tabular-nums">
      Média de {pairs} {pairs === 1 ? 'comparação' : 'comparações'}: <strong className="text-tinta">{num(seq.avg / conc.avg)}×</strong> · sequencial{' '}
      {duration(seq.avg)} · concorrente {duration(conc.avg)} · {threads('sequential')} × {threads('concurrent')} threads · CPU {cpu('sequential')} ×{' '}
      {cpu('concurrent')} ms (mesma CPU)
    </p>
  )
}

/**
 * A "corrida": a mesma consulta nos dois modos, disparadas juntas, com as linhas do
 * tempo empilhadas na mesma escala. Sem nenhuma corrida feita, mostra a última
 * consulta de cada modo.
 */
export function Race() {
  const { records, benchmark } = useLive()
  const [q, setQ] = useState('arroz')
  const [results, setResults] = useState<Results>({})
  const [running, setRunning] = useState(false)
  const [startedAt, setStartedAt] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const live = {
    sequential: useLiveQuery(running && !results.sequential, startedAt, { kind: 'search', mode: 'sequential', source: 'comparacao' }),
    concurrent: useLiveQuery(running && !results.concurrent, startedAt, { kind: 'search', mode: 'concurrent', source: 'comparacao' }),
  }

  const race = async () => {
    setResults({})
    setError(null)
    setRunning(true)
    setStartedAt(performance.now())
    try {
      await Promise.all(
        MODES.map((mode) => api.search(mode, { q, source: 'comparacao' }).then((res) => setResults((r) => ({ ...r, [mode]: res })))),
      )
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRunning(false)
    }
  }

  const repeat = async () => {
    setError(null)
    try {
      await api.benchmark(5, q) // as 10 consultas entram nas métricas e atualizam a linha de média
    } catch (e) {
      setError((e as Error).message)
    }
  }

  // o que mostrar em cada linha: resultado da corrida, corrida em andamento ou a última consulta
  const view = (mode: Mode): { entries: TimelineEntry[]; total?: number; now?: number } => {
    const res = results[mode]
    if (res) return { entries: res.markets, total: res.total_ms }
    if (running) return { entries: live[mode].entries, now: live[mode].elapsed }
    const rec = lastOf(records, mode)
    return { entries: rec?.markets ?? [], total: rec?.total_ms }
  }
  const rows = { sequential: view('sequential'), concurrent: view('concurrent') }
  const longest = Math.max(...MODES.map((m) => rows[m].total ?? rows[m].now ?? 0))
  const scale = timelineScale(longest)
  const seqTotal = rows.sequential.total
  const concTotal = rows.concurrent.total
  const speedup = seqTotal && concTotal ? seqTotal / concTotal : null

  return (
    <div className="rounded-2xl border border-linha bg-white">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void race()
        }}
        className="flex flex-wrap items-center gap-2 border-b border-linha p-4"
      >
        <label htmlFor="corrida-busca" className="sr-only">
          Produto
        </label>
        <input
          id="corrida-busca"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="w-40 rounded-full border border-linha px-4 py-2"
          placeholder="Produto"
        />
        <button disabled={running || benchmark.running} className="rounded-full bg-folha px-5 py-2 font-semibold text-white hover:bg-folha-escura disabled:opacity-60">
          {running ? 'Consultando…' : 'Comparar os dois modos'}
        </button>
        <button
          type="button"
          onClick={repeat}
          disabled={running || benchmark.running}
          className="rounded-full border border-linha px-4 py-2 text-sm font-semibold hover:bg-papel disabled:opacity-60"
        >
          {benchmark.running ? `Repetindo… ${benchmark.done}/${benchmark.runs}` : 'Repetir 5×'}
        </button>
        {error && <span className="text-sm text-tomate">{error}</span>}
      </form>

      <div className="space-y-6 p-5">
        {MODES.map((mode) => {
          const row = rows[mode]
          return (
            <div key={mode}>
              <div className="mb-2 flex items-baseline justify-between gap-3">
                <h3 className="flex items-center gap-2 font-semibold">
                  <span className="size-3 rounded-full" style={{ background: MODE_COLOR[mode] }} aria-hidden />
                  {MODE_LABEL[mode]}
                  <span className="text-sm font-normal text-cinza">
                    {mode === 'sequential' ? 'um mercado depois do outro · 1 thread' : 'todos ao mesmo tempo · 1 thread por mercado'}
                  </span>
                </h3>
                <span className="font-display text-3xl font-bold tabular-nums" style={{ color: MODE_COLOR[mode] }}>
                  {duration(row.total ?? row.now)}
                </span>
              </div>
              {row.entries.length ? (
                <Timeline mode={mode} entries={row.entries} scaleMs={scale} nowMs={row.total == null ? row.now : undefined} />
              ) : (
                <p className="rounded-lg border border-dashed border-linha p-4 text-center text-sm text-cinza">Clique em “Comparar os dois modos”.</p>
              )}
            </div>
          )
        })}
        {speedup && (
          <p className="rounded-xl bg-folha-clara px-4 py-3 text-center font-display text-xl font-bold">
            Concorrente {num(speedup)}× mais rápido
          </p>
        )}
      </div>
      <AverageLine records={records} />
    </div>
  )
}
