import { useState } from 'react'
import { brl } from '../lib/format'
import { useMarkets } from '../state/markets'
import type { MarketTiming, Product } from '../lib/types'
import { useApp } from '../state/app'
import { Drawer } from './Drawer'
import { PriceTag } from './PriceTag'
import { ProductImage } from './ProductImage'

export function ProductDrawer({ product, timings, onClose }: { product: Product | null; timings: MarketTiming[]; onClose: () => void }) {
  const { addToCart } = useApp()
  const { markets } = useMarkets()
  const [qty, setQty] = useState(1)
  if (!product) return null

  const offered = new Set(product.offers.map((o) => o.market_id))
  const failed = timings.filter((t) => !t.ok)
  const notSold = markets.filter((m) => !offered.has(m.id) && !failed.some((f) => f.market_id === m.id))
  const best = product.cheapest

  return (
    <Drawer open onClose={onClose} title="Comparar preços">
      <div className="flex gap-4 bg-white px-5 pb-5">
        <ProductImage src={product.image} name={product.name} className="size-32 shrink-0" />
        <div className="min-w-0">
          <p className="text-xs text-cinza">{product.category}</p>
          <h3 className="font-display text-2xl leading-tight font-bold">{product.name}</h3>
          <p className="text-sm text-cinza">
            <span className="font-semibold text-folha">{product.brand}</span>, {product.unit}
          </p>
          {product.savings > 0 && (
            <p className="mt-2 text-sm">
              Escolhendo o mercado certo você economiza <strong>{brl(product.savings)}</strong> neste item.
            </p>
          )}
        </div>
      </div>

      <ol className="space-y-2 p-5" aria-label="Preços por mercado, do menor para o maior">
        {product.offers.map((o, i) => {
          const isBest = best && o.market_id === best.market_id
          return (
            <li
              key={o.market_id}
              className={`flex items-center gap-3 rounded-xl border bg-white px-4 py-3 ${isBest ? 'border-tomate ring-2 ring-tomate/20' : 'border-linha'} ${
                o.in_stock ? '' : 'opacity-60'
              }`}
            >
              <span className="w-5 text-sm font-semibold text-cinza tabular-nums">{i + 1}º</span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{o.market_name}</p>
                <p className="text-xs text-cinza">
                  {!o.in_stock
                    ? 'Sem estoque'
                    : isBest
                      ? `${o.stock} em estoque`
                      : `+ ${brl(o.price - (best?.price ?? o.price))} que o menor preço`}
                </p>
              </div>
              {isBest ? (
                <div className="text-right">
                  <span className="mb-1 block text-xs font-bold text-tomate">Menor preço</span>
                  <PriceTag price={o.price} size="sm" tone="tomate" />
                </div>
              ) : (
                <span className="font-display text-lg font-bold tabular-nums">{brl(o.price)}</span>
              )}
            </li>
          )
        })}
      </ol>

      {(notSold.length > 0 || failed.length > 0) && (
        <div className="space-y-1 px-5 text-sm text-cinza">
          {notSold.length > 0 && <p>Não vendem este produto: {notSold.map((m) => m.name).join(', ')}.</p>}
          {failed.length > 0 && (
            <p className="text-tomate">
              Não responderam a esta consulta: {failed.map((f) => f.market_name).join(', ')}.
            </p>
          )}
        </div>
      )}


      <div className="sticky bottom-0 mt-6 flex items-center gap-3 border-t border-linha bg-white px-5 py-4">
        <div className="flex items-center rounded-full border border-linha">
          <button className="size-10 text-lg" onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label="Diminuir quantidade">
            −
          </button>
          <span className="w-6 text-center font-semibold tabular-nums" aria-live="polite">
            {qty}
          </span>
          <button className="size-10 text-lg" onClick={() => setQty((q) => Math.min(99, q + 1))} aria-label="Aumentar quantidade">
            +
          </button>
        </div>
        <button
          className="flex-1 rounded-full bg-folha px-5 py-2.5 font-semibold text-white hover:bg-folha-escura"
          onClick={() => {
            addToCart({ slug: product.slug, name: product.name, brand: product.brand, unit: product.unit, image: product.image }, qty)
            onClose()
          }}
        >
          Adicionar à cesta
        </button>
      </div>
    </Drawer>
  )
}
