import { useState } from 'react'
import { api } from '../../lib/api'
import { duration, num } from '../../lib/format'
import { MODE_LABEL } from '../../lib/markets'
import type { BenchmarkResult, Mode } from '../../lib/types'
import { useLive } from '../../state/live'

export function Benchmark() {
  const { benchmark } = useLive()
  const [runs, setRuns] = useState(5)
  const [q, setQ] = useState('arroz')
  const [result, setResult] = useState<BenchmarkResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const start = async () => {
    setRunning(true)
    setError(null)
    try {
      setResult(await api.benchmark(runs, q))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="rounded-2xl border border-linha bg-white p-6">
      <div className="grid grid-cols-2 gap-3">
        <label className="text-sm">
          Rodadas
          <input
            type="number"
            min={1}
            max={30}
            value={runs}
            onChange={(e) => setRuns(Math.max(1, Math.min(30, Number(e.target.value) || 1)))}
            className="mt-1 w-full rounded-lg border border-linha px-3 py-2"
          />
        </label>
        <label className="text-sm">
          Busca
          <input value={q} onChange={(e) => setQ(e.target.value)} className="mt-1 w-full rounded-lg border border-linha px-3 py-2" />
        </label>
      </div>
      <button
        onClick={start}
        disabled={running}
        className="mt-3 w-full rounded-full bg-folha px-5 py-2.5 font-semibold text-white hover:bg-folha-escura disabled:opacity-60"
      >
        {running ? `Rodando… ${benchmark.done}/${benchmark.runs || runs}` : `Rodar benchmark (${runs}× cada modo)`}
      </button>
      {running && (
        <div className="mt-2 h-1.5 rounded-full bg-papel" role="progressbar" aria-valuemin={0} aria-valuemax={benchmark.runs || runs} aria-valuenow={benchmark.done}>
          <div className="h-full rounded-full bg-gema transition-[width]" style={{ width: `${(benchmark.done / (benchmark.runs || runs)) * 100}%` }} />
        </div>
      )}
      {error && <p className="mt-3 text-sm text-tomate">{error}</p>}

      {!result && !running && (
        <p className="mt-4 text-sm text-cinza">
          Cada rodada faz a busca uma vez em cada modo. Com 5 rodadas e as latências padrão, leva cerca de 25 s. O resultado aparece aqui e as
          consultas entram no resumo e nos gráficos acima.
        </p>
      )}
      {result && (
        <div className="mt-4">
          <table className="w-full text-sm tabular-nums">
            <thead>
              <tr className="text-left text-cinza">
                <th className="py-1 font-medium">Modo</th>
                <th className="py-1 text-right font-medium">Média</th>
                <th className="py-1 text-right font-medium">Mín.</th>
                <th className="py-1 text-right font-medium">Máx.</th>
                <th className="py-1 text-right font-medium">Desvio</th>
              </tr>
            </thead>
            <tbody>
              {(['sequential', 'concurrent'] as Mode[]).map((m) => (
                <tr key={m} className="border-t border-linha">
                  <td className="py-1.5 font-semibold">{MODE_LABEL[m]}</td>
                  <td className="py-1.5 text-right">{duration(result[m].avg)}</td>
                  <td className="py-1.5 text-right">{duration(result[m].min)}</td>
                  <td className="py-1.5 text-right">{duration(result[m].max)}</td>
                  <td className="py-1.5 text-right">{duration(result[m].stdev)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {result.resources?.sequential && result.resources?.concurrent && (
            <dl className="mt-3 grid grid-cols-[auto_1fr_1fr] gap-x-4 gap-y-1 text-sm tabular-nums">
              <dt className="text-cinza" />
              <dd className="text-xs text-cinza">Sequencial</dd>
              <dd className="text-xs text-cinza">Concorrente</dd>
              <dt className="text-cinza">CPU por consulta</dt>
              <dd>{num(result.resources.sequential.cpu_ms ?? 0, 1)} ms</dd>
              <dd>{num(result.resources.concurrent.cpu_ms ?? 0, 1)} ms</dd>
              <dt className="text-cinza">Ocupação da CPU</dt>
              <dd>{num((result.resources.sequential.cpu_util ?? 0) * 100, 1)}%</dd>
              <dd>{num((result.resources.concurrent.cpu_util ?? 0) * 100, 1)}%</dd>
              <dt className="text-cinza">Threads extras</dt>
              <dd>{num(result.resources.sequential.threads_extra ?? 0, 0)}</dd>
              <dd>{num(result.resources.concurrent.threads_extra ?? 0, 0)}</dd>
            </dl>
          )}
          {result.speedup && (
            <p className="mt-3 rounded-lg bg-gema-clara px-3 py-2 text-sm">
              Speedup de <strong>{num(result.speedup, 2)}×</strong> com {result.runs} rodadas de “{result.query}”.
            </p>
          )}
        </div>
      )}

    </section>
  )
}
