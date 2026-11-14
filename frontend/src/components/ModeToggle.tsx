import { useApp } from '../state/app'
import type { Mode } from '../lib/types'

const OPTIONS: { mode: Mode; label: string; hint: string }[] = [
  { mode: 'sequential', label: 'Sequencial', hint: 'Um mercado de cada vez, como uma fila com um só caixa' },
  { mode: 'concurrent', label: 'Concorrente', hint: 'Todos os mercados ao mesmo tempo, uma thread para cada' },
]

function Icon({ mode }: { mode: Mode }) {
  // sequencial = escada; concorrente = barras paralelas
  return mode === 'sequential' ? (
    <svg width="18" height="14" viewBox="0 0 18 14" aria-hidden>
      <rect x="0" y="0" width="6" height="3" rx="1.5" fill="currentColor" />
      <rect x="6" y="5.5" width="6" height="3" rx="1.5" fill="currentColor" />
      <rect x="12" y="11" width="6" height="3" rx="1.5" fill="currentColor" />
    </svg>
  ) : (
    <svg width="18" height="14" viewBox="0 0 18 14" aria-hidden>
      <rect x="0" y="0" width="14" height="3" rx="1.5" fill="currentColor" />
      <rect x="0" y="5.5" width="18" height="3" rx="1.5" fill="currentColor" />
      <rect x="0" y="11" width="10" height="3" rx="1.5" fill="currentColor" />
    </svg>
  )
}

export function ModeToggle() {
  const { mode, setMode } = useApp()
  return (
    <div role="radiogroup" aria-label="Modo de consulta aos mercados" className="flex min-w-0 rounded-full bg-folha-escura p-1">
      {OPTIONS.map((o) => {
        const active = o.mode === mode
        return (
          <button
            key={o.mode}
            role="radio"
            aria-checked={active}
            title={o.hint}
            onClick={() => setMode(o.mode)}
            className={`flex items-center gap-2 rounded-full px-2.5 py-1.5 sm:px-3 text-sm font-semibold transition-colors ${
              active ? 'bg-gema text-tinta' : 'text-white/75 hover:text-white'
            }`}
          >
            <Icon mode={o.mode} />
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
