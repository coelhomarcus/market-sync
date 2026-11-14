import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { brl, duration } from '../lib/format'
import { MODE_LABEL } from '../lib/modes'
import type { BasketResponse } from '../lib/types'
import { useApp } from '../state/app'
import { useLiveQuery } from '../state/live'
import { useMarkets } from '../state/markets'
import { Drawer } from './Drawer'
import { PriceTag } from './PriceTag'
import { ProductImage } from './ProductImage'
import { Timeline, timelineScale } from './Timeline'

export function CartDrawer() {
  const { cart, setQty, clearCart, cartOpen, setCartOpen, mode } = useApp()
  const [result, setResult] = useState<BasketResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [startedAt, setStartedAt] = useState(0)
  const token = useRef(0)
  const live = useLiveQuery(loading, startedAt, { kind: 'basket' })
  const { name } = useMarkets()

  const compare = async () => {
    const my = ++token.current
    setResult(null) // o resultado anterior some: dá para sentir o tempo da nova consulta
    setLoading(true)
    setError(null)
    setStartedAt(performance.now())
    try {
      const res = await api.basket(mode, cart.map((i) => ({ slug: i.slug, qty: i.qty })))
      if (my === token.current) setResult(res)
    } catch (e) {
      if (my === token.current) setError((e as Error).message)
    } finally {
      if (my === token.current) setLoading(false)
    }
  }

  // trocou o modo com uma comparação na tela: compara de novo no modo novo
  const shownMode = useRef(mode)
  useEffect(() => {
    if (shownMode.current === mode) return
    shownMode.current = mode
    if (result || loading) void compare()
  }, [mode])


  return (
    <Drawer open={cartOpen} onClose={() => setCartOpen(false)} title="Sua cesta" wide>
      {cart.length === 0 ? (
        <div className="p-8 text-center">
          <p className="font-display text-xl font-bold">A cesta está vazia</p>
          <p className="mt-1 text-cinza">Adicione produtos pelo botão +.</p>
        </div>
      ) : (
        <>
          <ul className="divide-y divide-linha bg-white px-5">
            {cart.map((i) => (
              <li key={i.slug} className="flex items-center gap-3 py-3">
                <ProductImage src={i.image} name={i.name} className="size-12 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{i.name}</p>
                  <p className="text-xs text-cinza">
                    {i.brand ? `${i.brand}, ` : ''}
                    {i.unit}
                  </p>
                </div>
                <div className="flex items-center rounded-full border border-linha">
                  <button className="size-8" onClick={() => setQty(i.slug, i.qty - 1)} aria-label={`Diminuir ${i.name}`}>
                    −
                  </button>
                  <span className="w-6 text-center text-sm font-semibold tabular-nums">{i.qty}</span>
                  <button className="size-8" onClick={() => setQty(i.slug, i.qty + 1)} aria-label={`Aumentar ${i.name}`}>
                    +
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap items-center gap-3 border-b border-linha bg-white px-5 py-4">
            <button
              onClick={compare}
              disabled={loading}
              className="rounded-full bg-folha px-5 py-2.5 font-semibold text-white hover:bg-folha-escura disabled:opacity-60"
            >
              {loading ? 'Consultando…' : 'Comparar nos 5 mercados'}
            </button>
            <span className="text-sm text-cinza">Modo {MODE_LABEL[mode].toLowerCase()}</span>
            <button onClick={() => (clearCart(), setResult(null))} className="ml-auto text-sm text-cinza underline-offset-2 hover:underline">
              Esvaziar cesta
            </button>
          </div>
          {error && <p className="m-5 rounded-lg bg-tomate/10 p-3 text-sm text-tomate">{error}</p>}

          {loading && (
            <section className="space-y-3 p-5" aria-live="polite">
              <div className="flex items-baseline justify-between">
                <h3 className="font-display text-lg font-bold">Consultando os mercados…</h3>
                <span className="font-display text-2xl font-bold tabular-nums" style={{ color: mode === 'sequential' ? 'var(--color-seq)' : 'var(--color-conc)' }}>
                  {duration(live.elapsed)}
                </span>
              </div>
              <div className="rounded-xl border border-linha bg-white p-4">
                <Timeline mode={mode} entries={live.entries} scaleMs={timelineScale(live.elapsed)} nowMs={live.elapsed} />
              </div>
            </section>
          )}

          {result && (
            <section className="space-y-4 p-5" aria-live="polite">
              <div className="flex items-baseline justify-between">
                <h3 className="font-display text-lg font-bold">Total por mercado</h3>
                <span className="font-display text-2xl font-bold tabular-nums" style={{ color: result.mode === 'sequential' ? 'var(--color-seq)' : 'var(--color-conc)' }}>
                  {duration(result.total_ms)}
                </span>
              </div>
              <ol className="space-y-2">
                {result.markets.map((m) => {
                  const isBest = result.cheapest?.market_id === m.market_id
                  const missing = m.missing?.length ?? 0
                  return (
                    <li
                      key={m.market_id}
                      className={`flex items-center gap-3 rounded-xl border bg-white px-4 py-3 ${isBest ? 'border-tomate ring-2 ring-tomate/20' : 'border-linha'}`}
                    >
                      <p className="flex-1 font-semibold">{name(m.market_id)}</p>
                      {!m.ok ? (
                        <span className="text-sm text-tomate">não respondeu</span>
                      ) : isBest ? (
                        <div className="text-right">
                          <span className="mb-1 block text-xs font-bold text-tomate">Mais barata</span>
                          <PriceTag price={m.total!} size="sm" tone="tomate" />
                        </div>
                      ) : (
                        <span className="text-right">
                          <span className={`font-display text-lg font-bold tabular-nums ${missing ? 'text-cinza' : ''}`}>{brl(m.total!)}</span>
                          {missing > 0 && (
                            <span className="block text-xs text-cinza">
                              falta {missing} {missing === 1 ? 'item' : 'itens'}
                            </span>
                          )}
                        </span>
                      )}
                    </li>
                  )
                })}
              </ol>
              <div className="rounded-xl border border-linha bg-white p-4">
                <p className="mb-3 text-sm font-semibold">Tempo de cada mercado</p>
                <Timeline mode={result.mode} entries={result.timings} scaleMs={timelineScale(result.total_ms)} />
              </div>
            </section>
          )}
        </>
      )}
    </Drawer>
  )
}
