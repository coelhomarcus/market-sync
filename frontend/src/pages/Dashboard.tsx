import { Benchmark } from '../components/dashboard/Benchmark'
import { EventLog } from '../components/dashboard/EventLog'
import { LastTimelines } from '../components/dashboard/LastTimelines'
import { MarketsTable } from '../components/dashboard/MarketsTable'
import { ResourcesPanel } from '../components/dashboard/Resources'
import { Scoreboard } from '../components/dashboard/Scoreboard'
import { Section } from '../components/dashboard/Section'
import { api } from '../lib/api'
import { useLive } from '../state/live'
import { useMarkets } from '../state/markets'

const NAV = [
  { id: 'resumo', label: 'Resumo' },
  { id: 'ultima', label: 'Última consulta' },
  { id: 'mercados', label: 'Mercados' },
  { id: 'recursos', label: 'Recursos' },
  { id: 'benchmark', label: 'Benchmark' },
  { id: 'eventos', label: 'Eventos' },
]

export function Dashboard() {
  const { records, connected } = useLive()
  const { markets, error, configure } = useMarkets()

  const reset = async () => {
    if (!confirm('Apagar todas as métricas?')) return
    await api.resetMetrics().catch(() => {})
  }

  return (
    <main>
      <div className="bg-folha pb-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-end justify-between gap-4 px-4 pt-3 sm:px-6">
          <div>
            <h1 className="font-display text-3xl font-extrabold tracking-tight text-white sm:text-4xl">Painel ao vivo</h1>
            <p className="mt-1 text-white/80">Sequencial × concorrente, consulta a consulta.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm ${connected ? 'bg-white/10 text-white' : 'bg-tomate text-white'}`}>
              <span className={`size-2 rounded-full ${connected ? 'bg-gema' : 'bg-white'}`} aria-hidden />
              {connected ? 'Ao vivo' : 'Sem conexão'}
            </span>
            <a href="/api/metrics/export.csv" download className="rounded-full bg-white px-4 py-1.5 text-sm font-semibold text-folha hover:bg-gema-clara">
              Exportar CSV
            </a>
            <button onClick={reset} className="rounded-full px-3 py-1.5 text-sm font-semibold text-white/85 hover:bg-white/10">
              Zerar
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
        <Section id="resumo" title="Resumo" description="Tempo médio de resposta em cada modo.">
          <Scoreboard records={records} />
        </Section>

        <Section id="ultima" title="Última consulta" description="Sequencial: um mercado depois do outro. Concorrente: todos juntos.">
          <LastTimelines records={records} />
        </Section>

        <Section
          id="mercados"
          title="Mercados"
          description="Cada mercado é um processo com seu próprio servidor TCP. Fora do ar, o agregador tenta de novo 3 vezes (espera 0,5 s, 1 s e 2 s) antes de desistir."
        >
          <MarketsTable markets={markets} error={error} configure={configure} />
        </Section>

        <Section id="recursos" title="Recursos" description="Média por consulta em cada modo.">
          <ResourcesPanel records={records} />
        </Section>

        <Section id="benchmark" title="Benchmark" description="Repete a mesma busca nos dois modos e compara as médias.">
          <div className="max-w-2xl">
            <Benchmark />
          </div>
        </Section>

        <Section id="eventos" title="Eventos" description="Cada consulta em tempo real. Abra um cartão para ver os eventos TCP.">
          <EventLog />
        </Section>
      </div>
    </main>
  )
}
