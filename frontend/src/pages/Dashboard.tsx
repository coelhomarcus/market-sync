import { useMemo, useState } from 'react'
import { Benchmark } from '../components/dashboard/Benchmark'
import { HistoryChart, MarketLatencyChart } from '../components/dashboard/Charts'
import { EventLog } from '../components/dashboard/EventLog'
import { LastTimelines } from '../components/dashboard/LastTimelines'
import { MarketsTable } from '../components/dashboard/MarketsTable'
import { Scoreboard } from '../components/dashboard/Scoreboard'
import { Section } from '../components/dashboard/Section'
import { api } from '../lib/api'
import { useLive } from '../state/live'
import { useMarkets } from '../state/markets'

type Origin = 'tudo' | 'loja' | 'benchmark'
const ORIGINS: { id: Origin; label: string }[] = [
  { id: 'tudo', label: 'Todas' },
  { id: 'loja', label: 'Só da loja' },
  { id: 'benchmark', label: 'Só do benchmark' },
]
const NAV = [
  { id: 'resumo', label: 'Resumo' },
  { id: 'linha-do-tempo', label: 'Linha do tempo' },
  { id: 'historico', label: 'Histórico' },
  { id: 'mercados', label: 'Mercados' },
  { id: 'benchmark', label: 'Benchmark e eventos' },
]

export function Dashboard() {
  const { records, connected } = useLive()
  const { markets, error, configure } = useMarkets()
  const [origin, setOrigin] = useState<Origin>('tudo')
  const filtered = useMemo(() => (origin === 'tudo' ? records : records.filter((r) => r.source === origin)), [records, origin])

  const reset = async () => {
    if (!confirm('Apagar todas as métricas registradas no agregador?')) return
    await api.resetMetrics().catch(() => {})
  }

  return (
    <main>
      <div className="bg-folha pb-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-end justify-between gap-4 px-4 pt-3 sm:px-6">
          <div className="max-w-2xl">
            <h1 className="font-display text-3xl font-extrabold tracking-tight text-white sm:text-4xl">Painel ao vivo</h1>
            <p className="mt-1 text-white/80">
              Cada busca da loja abre conexões TCP com os 5 mercados. Aqui você vê quanto cada uma levou, compara os dois modos e provoca falhas para
              ver o sistema reagir.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm ${connected ? 'bg-white/10 text-white' : 'bg-tomate text-white'}`}>
              <span className={`size-2 rounded-full ${connected ? 'bg-gema' : 'bg-white'}`} aria-hidden />
              {connected ? 'Recebendo eventos' : 'Sem conexão com o agregador'}
            </span>
            <a href="/api/metrics/export.csv" download className="rounded-full bg-white px-4 py-1.5 text-sm font-semibold text-folha hover:bg-gema-clara">
              Exportar CSV
            </a>
            <button onClick={reset} className="rounded-full px-3 py-1.5 text-sm font-semibold text-white/85 hover:bg-white/10">
              Zerar métricas
            </button>
          </div>
        </div>
      </div>

      <nav aria-label="Seções do painel" className="sticky top-0 z-20 border-b border-linha bg-papel/90 backdrop-blur">
        <ul className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 py-2 sm:px-6">
          {NAV.map((n) => (
            <li key={n.id}>
              <a href={`#${n.id}`} className="block rounded-full px-3 py-1.5 text-sm font-medium whitespace-nowrap text-cinza hover:bg-white hover:text-tinta">
                {n.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div className="mx-auto max-w-7xl space-y-12 px-4 py-8 sm:px-6">
        <Section
          id="resumo"
          title="Resumo"
          description="Tempo médio que o usuário espera em cada modo e o volume de dados trafegado."
          actions={
            <div role="radiogroup" aria-label="Quais requisições considerar" className="flex rounded-full border border-linha bg-white p-1">
              {ORIGINS.map((o) => (
                <button
                  key={o.id}
                  role="radio"
                  aria-checked={origin === o.id}
                  onClick={() => setOrigin(o.id)}
                  className={`rounded-full px-3 py-1 text-sm font-medium ${origin === o.id ? 'bg-tinta text-white' : 'text-cinza hover:text-tinta'}`}
                >
                  {o.label}
                </button>
              ))}
            </div>
          }
        >
          <Scoreboard records={filtered} markets={markets} />
        </Section>

        <Section
          id="linha-do-tempo"
          title="Linha do tempo das conexões"
          description="Cada barra vai do connect() à resposta de um mercado, na mesma escala nos dois lados. No sequencial as barras formam uma escada; no concorrente, começam juntas."
        >
          <LastTimelines records={filtered} />
        </Section>

        <Section id="historico" title="Histórico" description="Como os tempos evoluíram requisição a requisição, e quanto cada mercado costuma demorar.">
          <div className="grid gap-5 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <HistoryChart records={filtered} />
            </div>
            <MarketLatencyChart records={filtered} />
          </div>
        </Section>

        <Section
          id="mercados"
          title="Mercados"
          description="Cada mercado é um processo Python separado, com sua porta TCP e seu banco. Arraste a latência além do traço (3 s) para provocar timeout, ou tire um mercado do ar: a busca concorrente devolve o que os outros responderem."
        >
          <MarketsTable markets={markets} error={error} configure={configure} />
        </Section>

        <Section
          id="benchmark"
          title="Benchmark e eventos"
          description="O benchmark repete a mesma busca nos dois modos, alternando a ordem; o log mostra cada passo das conexões assim que acontece."
        >
          <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
            <Benchmark />
            <EventLog />
          </div>
        </Section>
      </div>
    </main>
  )
}
