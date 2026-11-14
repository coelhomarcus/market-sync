import { bytes, duration, int, num } from '../../lib/format'
import { MODE_COLOR, MODE_LABEL } from '../../lib/markets'
import type { MarketStatus, MetricRecord, Mode, Resources as Res } from '../../lib/types'

const MODES: Mode[] = ['sequential', 'concurrent']

function avg(records: MetricRecord[], mode: Mode, pick: (r: Res, rec: MetricRecord) => number) {
  const list = records.filter((r) => r.mode === mode && r.resources && r.resources.cpu_ms != null)
  if (!list.length) return null
  return list.reduce((s, r) => s + pick(r.resources!, r), 0) / list.length
}

interface Metric {
  id: string
  title: string
  hint: string
  values: Record<Mode, number | null>
  format: (v: number) => string
  detail?: (mode: Mode) => string | null
}

function MetricBlock({ m }: { m: Metric }) {
  const max = Math.max(...MODES.map((k) => m.values[k] ?? 0), 1e-9)
  return (
    <div className="p-5">
      <h3 className="font-semibold">{m.title}</h3>
      <p className="mb-3 text-xs text-cinza">{m.hint}</p>
      <div className="space-y-3">
        {MODES.map((mode) => {
          const v = m.values[mode]
          return (
            <div key={mode}>
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className="text-cinza">{MODE_LABEL[mode]}</span>
                <span className="font-display text-lg font-bold tabular-nums">{v == null ? '—' : m.format(v)}</span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-papel">
                <div className="h-full rounded-full" style={{ width: `${((v ?? 0) / max) * 100}%`, background: MODE_COLOR[mode] }} />
              </div>
              {m.detail && v != null && <p className="mt-0.5 text-xs text-cinza tabular-nums">{m.detail(mode)}</p>}
            </div>
          )
        })}
      </div>
    </div>
  )
}

const ms1 = (v: number) => `${num(v, 1)} ms`

export function ResourcesPanel({ records, markets }: { records: MetricRecord[]; markets: MarketStatus[] }) {
  const time = (mode: Mode) => avg(records, mode, (_, rec) => rec.total_ms)
  const cpu = (mode: Mode) => avg(records, mode, (r) => r.cpu_ms)
  const aggCpu = (mode: Mode) => avg(records, mode, (r) => r.agg_cpu_ms)
  const srvCpu = (mode: Mode) => avg(records, mode, (r) => r.server_cpu_ms)
  const util = (mode: Mode) => avg(records, mode, (r) => r.cpu_util * 100)
  const threads = (mode: Mode) => avg(records, mode, (r) => r.threads_extra)
  const count = (mode: Mode) => records.filter((r) => r.mode === mode && r.resources?.cpu_ms != null).length

  const metrics: Metric[] = [
    {
      id: 'tempo',
      title: 'Tempo de resposta',
      hint: 'Quanto o usuário espera, em média.',
      values: { sequential: time('sequential'), concurrent: time('concurrent') },
      format: duration,
    },
    {
      id: 'cpu',
      title: 'CPU por requisição',
      hint: 'Processamento de verdade: agregador + os 5 mercados.',
      values: { sequential: cpu('sequential'), concurrent: cpu('concurrent') },
      format: ms1,
      detail: (mode) => `agregador ${ms1(aggCpu(mode) ?? 0)} + mercados ${ms1(srvCpu(mode) ?? 0)}`,
    },
    {
      id: 'ocupacao',
      title: 'Ocupação da CPU',
      hint: 'CPU usada ÷ tempo de resposta. O resto é espera pela rede.',
      values: { sequential: util('sequential'), concurrent: util('concurrent') },
      format: (v) => `${num(v, 1)}%`,
    },
    {
      id: 'threads',
      title: 'Threads extras no pico',
      hint: 'Threads que o agregador criou só para a requisição.',
      values: { sequential: threads('sequential'), concurrent: threads('concurrent') },
      format: (v) => num(v, 1),
    },
  ]

  const ts = time('sequential'), tc = time('concurrent'), cs = cpu('sequential'), cc = cpu('concurrent')
  const ready = ts && tc && cs && cc
  const latestRss = [...records].reverse().find((r) => r.resources?.rss_mb)?.resources?.rss_mb

  return (
    <div className="overflow-hidden rounded-2xl border border-linha bg-white">
      <div className="border-b border-linha bg-folha-clara/50 px-5 py-4">
        {ready ? (
          <p className="font-display text-xl font-bold">
            O concorrente responde {num(ts / tc)}× mais rápido usando {num((threads('concurrent') ?? 0) - (threads('sequential') ?? 0), 0)} threads a
            mais; a CPU por requisição fica na mesma ordem ({ms1(cs)} no sequencial, {ms1(cc)} no concorrente).
          </p>
        ) : (
          <p className="font-display text-xl font-bold">Faça consultas nos dois modos para comparar o consumo de recursos.</p>
        )}
        <p className="mt-1 text-sm text-cinza">
          Os dois modos fazem as mesmas 5 consultas; a concorrência não reduz o trabalho, ela sobrepõe as esperas. Médias de {int(count('sequential'))} consultas sequenciais e {int(count('concurrent'))} concorrentes.
        </p>
      </div>
      <div className="grid divide-y divide-linha sm:grid-cols-2 sm:divide-x lg:grid-cols-4 lg:divide-y-0">
        {metrics.map((m) => (
          <MetricBlock key={m.id} m={m} />
        ))}
      </div>
      <p className="border-t border-linha px-5 py-3 text-xs text-cinza">
        A CPU do agregador é medida no processo inteiro durante a requisição: no sequencial essa janela é cerca de 3× mais longa e inclui tarefas de
        fundo (WebSocket, atualização do painel). Requisições simultâneas de outras abas também entram nessa conta, inclusive nas threads. A CPU
        dos mercados é medida só na thread que atendeu a consulta.
      </p>
      <div className="overflow-x-auto border-t border-linha">
        <table className="w-full min-w-[34rem] text-sm tabular-nums">
          <caption className="px-5 pt-4 pb-2 text-left text-xs font-semibold text-cinza">Processos em execução agora</caption>
          <thead>
            <tr className="text-left text-xs text-cinza">
              <th className="px-5 py-1.5 font-medium">Processo</th>
              <th className="px-3 py-1.5 text-right font-medium">Memória (RSS)</th>
              <th className="px-3 py-1.5 text-right font-medium">CPU acumulada</th>
              <th className="px-5 py-1.5 text-right font-medium">Consultas atendidas</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-linha">
              <td className="px-5 py-2 font-medium">Agregador (FastAPI)</td>
              <td className="px-3 py-2 text-right">{latestRss ? `${num(latestRss, 1)} MB` : '—'}</td>
              <td className="px-3 py-2 text-right text-cinza">—</td>
              <td className="px-5 py-2 text-right">{int(records.length)}</td>
            </tr>
            {markets.map((m) => (
              <tr key={m.id} className="border-t border-linha">
                <td className="px-5 py-2">
                  <span className="mr-2 inline-block size-2.5 rounded-full" style={{ background: m.color }} aria-hidden />
                  {m.name}
                </td>
                <td className="px-3 py-2 text-right">{m.rss_bytes ? bytes(m.rss_bytes) : '—'}</td>
                <td className="px-3 py-2 text-right">{m.cpu_s != null ? `${num(m.cpu_s, 2)} s` : '—'}</td>
                <td className="px-5 py-2 text-right">{m.requests_served != null ? int(m.requests_served) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
