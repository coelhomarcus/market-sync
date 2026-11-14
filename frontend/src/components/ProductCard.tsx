import { brl } from '../lib/format'
import { MARKET_BY_ID } from '../lib/markets'
import type { Product } from '../lib/types'
import { useApp } from '../state/app'
import { PriceTag } from './PriceTag'
import { ProductImage } from './ProductImage'

export function ProductCard({ product, onOpen }: { product: Product; onOpen: () => void }) {
  const { addToCart } = useApp()
  const cheapest = product.cheapest
  const available = product.offers.filter((o) => o.in_stock).length

  return (
    <article className="group relative flex flex-col rounded-2xl border border-linha bg-white p-4 transition-colors hover:border-folha/40">
      <button onClick={onOpen} className="absolute inset-0 z-0 rounded-2xl" aria-label={`Comparar preços de ${product.name}`} />
      <ProductImage src={product.image} name={product.name} className="pointer-events-none mx-auto aspect-square w-full max-w-[180px]" />
      <p className="mt-3 text-xs font-semibold text-folha">{product.brand}</p>
      <h3 className="font-display text-[17px] leading-tight font-bold">{product.name}</h3>
      <p className="text-sm text-cinza">{product.unit}</p>

      <div className="mt-3 flex flex-1 items-end justify-between gap-2">
        {cheapest ? (
          <div>
            <PriceTag price={cheapest.price} label="a partir de" />
            <p className="mt-1.5 text-xs text-cinza">
              no <span className="font-semibold text-tinta">{MARKET_BY_ID[cheapest.market_id]?.name ?? cheapest.market_name}</span>
            </p>
          </div>
        ) : (
          <p className="text-sm font-medium text-tomate">Sem estoque nos mercados</p>
        )}
        <button
          onClick={() => addToCart({ slug: product.slug, name: product.name, brand: product.brand, unit: product.unit, image: product.image })}
          className="relative z-10 grid size-10 shrink-0 place-items-center rounded-full bg-folha text-white hover:bg-folha-escura"
          aria-label={`Adicionar ${product.name} à cesta`}
          title="Adicionar à cesta"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
            <path d="M9 3v12M3 9h12" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      <p className="mt-3 border-t border-dashed border-linha pt-2 text-xs text-cinza">
        {available} {available === 1 ? 'mercado tem' : 'mercados têm'}
        {product.savings > 0 && (
          <>
            , diferença de <span className="font-semibold text-tinta">{brl(product.savings)}</span>
          </>
        )}
      </p>
    </article>
  )
}
