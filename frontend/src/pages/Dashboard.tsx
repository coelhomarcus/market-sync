import { useState } from 'react'
import { EventLog } from '../components/dashboard/EventLog'
import { MarketsTable } from '../components/dashboard/MarketsTable'
import { Race } from '../components/dashboard/Race'
import { RawLog } from '../components/dashboard/RawLog'
import { Section } from '../components/dashboard/Section'
import { api } from '../lib/api'
import { useLive } from '../state/live'

export function Dashboard() {
  const { connected } = useLive()
  const [eventsTab, setEventsTab] = useState<'consultas' | 'log'>('consultas')

  const reset = async () => {
    if (!confirm('Apagar todas as métricas?')) return
    await api.resetMetrics().catch(() => {})
  }

  return (
    <main>
      <div className="bg-folha pb-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-end justify-between gap-4 px-4 pt-3 sm:px-6">
          <div>
            <h1 className="font-display text-3xl font-extrabold tracking-tight text-white sm:text-4xl">Sequencial × concorrente</h1>
            <p className="mt-1 text-white/80">A mesma consulta nos 5 mercados, de dois jeitos.</p>
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

      <div className="mx-auto max-w-7xl space-y-12 px-4 py-8 sm:px-6">
        <Section id="comparacao" title="Comparação">
          <Race />
        </Section>

        <Section
          id="mercados"
          title="Mercados"
          description="Cada mercado é um processo com seu servidor TCP. Fora do ar, o agregador tenta de novo 3 vezes (0,5 s, 1 s e 2 s); acima de 3 s, desiste por timeout."
        >
          <MarketsTable />
        </Section>

        <Section
          id="eventos"
          title="Eventos"
          description={
            eventsTab === 'consultas'
              ? 'Cada consulta feita ao agregador, chegando ao vivo pelo WebSocket. Clique para ver o que aconteceu com cada mercado.'
              : 'Tudo o que o agregador publica no WebSocket, na ordem em que acontece, do jeito que chega.'
          }
          actions={
            <div role="tablist" aria-label="Como ver os eventos" className="flex rounded-full border border-linha bg-white p-1">
              {(
                [
                  ['consultas', 'Consultas'],
                  ['log', 'Log bruto'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  role="tab"
                  aria-selected={eventsTab === id}
                  onClick={() => setEventsTab(id)}
                  className={`rounded-full px-4 py-1 text-sm font-semibold ${eventsTab === id ? 'bg-tinta text-white' : 'text-cinza hover:text-tinta'}`}
                >
                  {label}
                </button>
              ))}
            </div>
          }
        >
          {eventsTab === 'consultas' ? <EventLog /> : <RawLog />}
        </Section>
      </div>
    </main>
  )
}
