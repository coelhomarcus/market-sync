import { useState } from 'react'
import { api } from '../lib/api'
import { brl, duration } from '../lib/format'
import { marketColor, MARKET_BY_ID, MODE_LABEL } from '../lib/markets'
import type { BasketResponse } from '../lib/types'
import { useApp } from '../state/app'
import { Drawer } from './Drawer'
import { PriceTag } from './PriceTag'
import { ProductImage } from './ProductImage'
import { Timeline } from './Timeline'

export function CartDrawer() {
  const { cart, setQty, clearCart, cartOpen, setCartOpen, mode } = useApp()
  const [result, setResult] = useState<BasketResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const compare = async () => {
    setLoading(true)
    setError(null)
    try {
      setResult(await api.basket(mode, cart.map((i) => ({ slug: i.slug, qty: i.qty }))))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const names = Object.fromEntries(cart.map((i) => [i.slug, `${i.name}${i.brand ? ` ${i.brand}` : ''}`]))
  const best = result?.cheapest

  return (
    <Drawer open={cartOpen} onClose={() => setCartOpen(false)} title="Sua cesta" wide>
      {cart.length === 0 ? (
        <div className="p-8 text-center">
          <p className="font-display text-xl font-bold">A cesta está vazia</p>
          <p className="mt-1 text-cinza">Adicione produtos pelo botão + para descobrir em qual mercado a compra inteira sai mais barata.</p>
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
              {loading ? 'Consultando os mercados…' : 'Comparar cesta nos 5 mercados'}
            </button>
            <span className="text-sm text-cinza">Modo {MODE_LABEL[mode].toLowerCase()}</span>
            <button onClick={() => (clearCart(), setResult(null))} className="ml-auto text-sm text-cinza underline-offset-2 hover:underline">
              Esvaziar cesta
            </button>
          </div>
          {error && <p className="m-5 rounded-lg bg-tomate/10 p-3 text-sm text-tomate">{error}</p>}

          {result && (
            <section className="space-y-4 p-5" aria-live="polite">
              <div className="flex items-baseline justify-between">
                <h3 className="font-display text-lg font-bold">Total da cesta por mercado</h3>
                <span className="text-sm text-cinza tabular-nums">
                  {MODE_LABEL[result.mode]}: {duration(result.total_ms)}
                </span>
              </div>
              <ol className="space-y-2">
                {result.markets.map((m) => {
                  const isBest = best?.market_id === m.market_id
                  return (
                    <li
                      key={m.market_id}
                      className={`rounded-xl border bg-white px-4 py-3 ${isBest ? 'border-tomate ring-2 ring-tomate/20' : 'border-linha'}`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="size-3 shrink-0 rounded-full" style={{ background: marketColor(m.market_id) }} aria-hidden />
                        <div className="min-w-0 flex-1">
                          <p className="font-semibold">{MARKET_BY_ID[m.market_id]?.name ?? m.market_name}</p>
                          <p className="text-xs text-cinza">
                            {!m.ok
                              ? `Não respondeu: ${m.error}`
                              : m.complete
                                ? 'Tem todos os itens'
                                : `Faltam: ${m.missing!.map((s) => names[s] ?? s).join(', ')}`}
                          </p>
                        </div>
                        {m.ok &&
                          (isBest ? (
                            <div className="text-right">
                              <span className="mb-1 block text-xs font-bold text-tomate">Cesta mais barata</span>
                              <PriceTag price={m.total!} size="sm" tone="tomate" />
                            </div>
                          ) : (
                            <span className={`font-display text-lg font-bold tabular-nums ${m.complete ? '' : 'text-cinza'}`}>{brl(m.total!)}</span>
                          ))}
                      </div>
                    </li>
                  )
                })}
              </ol>
              {result.best_mix.lines.length > 0 && (
                <div className="rounded-xl bg-gema-clara p-4 text-sm">
                  <p>
                    Comprando cada item no mercado onde ele é mais barato, a cesta sai por <strong>{brl(result.best_mix.total)}</strong>
                    {result.best_mix.savings_vs_cheapest != null && result.best_mix.savings_vs_cheapest > 0 && (
                      <> — {brl(result.best_mix.savings_vs_cheapest)} a menos que a cesta mais barata em um único mercado</>
                    )}
                    .
                  </p>
                  <ul className="mt-2 space-y-0.5 text-cinza">
                    {result.best_mix.lines.map((l) => (
                      <li key={l.slug}>
                        {l.qty}× {l.name}
                        {l.brand ? ` ${l.brand}` : ''}: {brl(l.subtotal)} no {MARKET_BY_ID[l.market_id!]?.name}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="rounded-xl border border-linha bg-white p-4">
                <p className="mb-3 text-sm font-semibold">Linha do tempo da consulta</p>
                <Timeline entries={result.timings} scaleMs={result.total_ms} />
              </div>
            </section>
          )}
        </>
      )}
    </Drawer>
  )
}
