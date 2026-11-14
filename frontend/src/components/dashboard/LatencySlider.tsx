import { useEffect, useRef, useState } from 'react'
import { duration } from '../../lib/format'

const MAX = 5000
const TIMEOUT = 3000

interface Props {
  value: number
  color: string
  disabled?: boolean
  label: string
  onCommit: (value: number) => Promise<unknown>
}

/**
 * Slider de latência que só envia o valor ao SOLTAR (ou após uma pausa no teclado).
 * Enquanto o usuário arrasta ou a configuração está a caminho, o valor que vem do
 * servidor não sobrescreve o local — é isso que evita o "pulo para trás".
 */
export function LatencySlider({ value, color, disabled, label, onCommit }: Props) {
  const [local, setLocal] = useState(value)
  const [saving, setSaving] = useState(false)
  const dragging = useRef(false)
  const inFlight = useRef(0)
  const committed = useRef(value)
  const keyTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    if (!dragging.current && inFlight.current === 0) {
      setLocal(value)
      committed.current = value
    }
  }, [value])

  const commit = (v: number) => {
    clearTimeout(keyTimer.current)
    keyTimer.current = undefined
    if (v === committed.current) return
    committed.current = v
    inFlight.current += 1
    setSaving(true)
    const previous = value
    onCommit(v)
      .catch(() => {
        // falhou: volta para o último valor confirmado pelo servidor
        committed.current = previous
        setLocal(previous)
      })
      .finally(() => {
        inFlight.current -= 1
        if (inFlight.current === 0) setSaving(false)
      })
  }

  const pct = (local / MAX) * 100
  const timeoutPct = (TIMEOUT / MAX) * 100
  const overTimeout = local > TIMEOUT
  const fill = overTimeout ? 'var(--color-tomate)' : color

  return (
    <div className={`flex items-center gap-3 ${disabled ? 'opacity-40' : ''}`}>
      <div className="relative flex-1 py-3">
        {/* trilho, preenchimento e marca do timeout */}
        <div className="pointer-events-none absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-linha">
          {/* o centro do polegar anda de 9 px até (largura − 9 px): o preenchimento acompanha */}
          <div className="h-full rounded-full" style={{ width: `calc(${pct / 100} * (100% - 18px) + 9px)`, background: fill }} />
        </div>
        <div className="pointer-events-none absolute top-1/2 h-4 w-0.5 -translate-y-1/2 rounded bg-tinta/40" style={{ left: `calc(${timeoutPct / 100} * (100% - 18px) + 8px)` }} />
        <input
          type="range"
          min={0}
          max={MAX}
          step={50}
          value={local}
          disabled={disabled}
          aria-label={label}
          aria-valuetext={`${duration(local)}${overTimeout ? ', acima do timeout de 3 segundos' : ''}`}
          onPointerDown={() => (dragging.current = true)}
          onPointerUp={(e) => {
            if (!dragging.current) return // só envia se o arraste começou neste slider
            dragging.current = false
            commit(Number((e.target as HTMLInputElement).value))
          }}
          onChange={(e) => {
            const v = Number(e.target.value)
            setLocal(v)
            if (!dragging.current) {
              // teclado: aplica depois de uma pausa curta nas setas
              clearTimeout(keyTimer.current)
              keyTimer.current = setTimeout(() => {
                keyTimer.current = undefined
                commit(v)
              }, 400)
            }
          }}
          onBlur={() => {
            dragging.current = false
            if (keyTimer.current) commit(local) // havia uma alteração por teclado ainda não enviada
          }}
          className="latency-range relative w-full"
          style={{ ['--thumb' as string]: fill }}
        />
      </div>
      <span className={`w-16 text-right text-sm font-semibold tabular-nums ${overTimeout ? 'text-tomate' : ''}`}>{duration(local)}</span>
      <span className="w-3" aria-hidden>
        {saving && <span className="block size-2 animate-pulse rounded-full bg-gema" title="Aplicando" />}
      </span>
    </div>
  )
}
