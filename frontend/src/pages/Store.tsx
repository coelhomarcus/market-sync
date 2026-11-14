import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { ProductCard } from '../components/ProductCard'
import { ProductDrawer } from '../components/ProductDrawer'
import { Timeline } from '../components/Timeline'
import { api } from '../lib/api'
import { duration, int } from '../lib/format'
import { MARKET_BY_ID, MARKETS, MODE_LABEL } from '../lib/markets'
import type { Product, SearchResponse, Sort } from '../lib/types'
import { useApp } from '../state/app'
import { useLiveQuery } from '../state/live'

interface Params {
  q: string
  category: string
  sort: Sort
  page: number
}

/** Números de página com reticências: 1 … 4 5 [6] 7 8 … 44 */
function pageList(page: number, pages: number): (number | '…')[] {
  const set = new Set([1, pages, page - 2, page - 1, page, page + 1, page + 2].filter((p) => p >= 1 && p <= pages))
  const sorted = [...set].sort((a, b) => a - b)
  const out: (number | '…')[] = []
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push('…')
    out.push(p)
  })
  return out
}

function SkeletonGrid() {
  return (
    <>
      {Array.from({ length: 10 }, (_, i) => (
        <div key={i} className="animate-pulse rounded-2xl border border-linha bg-white p-4" aria-hidden>
          <div className="mx-auto aspect-square w-full max-w-[180px] rounded-xl bg-papel" />
          <div className="mt-3 h-3 w-1/3 rounded bg-papel" />
          <div className="mt-2 h-4 w-4/5 rounded bg-papel" />
          <div className="mt-4 h-8 w-1/2 rounded bg-papel" />
        </div>
      ))}
    </>
  )
}

export function Store() {
  const { mode } = useApp()
  const [input, setInput] = useState('')
  const [params, setParams] = useState<Params>({ q: '', category: '', sort: 'destaques', page: 1 })
  const [data, setData] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Product | null>(null)
  const [startedAt, setStartedAt] = useState(0)
  const token = useRef(0)
  const gridTop = useRef<HTMLDivElement>(null)

  // cada mudança de modo, busca, categoria, ordem ou página consulta os 5 mercados de novo
  useEffect(() => {
    const my = ++token.current
    setLoading(true)
    setError(null)
    setStartedAt(performance.now())
    api
      .search(mode, params)
      .then((res) => my === token.current && setData(res))
      .catch((e: Error) => my === token.current && setError(e.message))
      .finally(() => my === token.current && setLoading(false))
  }, [mode, params])

  const live = useLiveQuery('search', loading, startedAt)

  const submit = (value: string) => {
    setInput(value)
    const q = value.trim()
    setParams({ q, category: '', sort: q ? 'preco' : 'destaques', page: 1 })
  }
  const update = (patch: Partial<Params>) => setParams((p) => ({ ...p, page: 1, ...patch }))
  const goToPage = (page: number) => {
    setParams((p) => ({ ...p, page }))
    gridTop.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const failed = data?.markets.filter((m) => !m.ok) ?? []
  // as categorias só mudam com a busca: ao trocar modo, ordem ou página elas continuam valendo
  const categories = data && data.query === params.q ? data.categories : null
  const allCount = categories?.reduce((n, c) => n + c.count, 0) ?? 0
  const modeColor = mode === 'sequential' ? 'var(--color-seq)' : 'var(--color-conc)'

  return (
    <main>
      <section className="bg-folha pb-8">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <form
            role="search"
            onSubmit={(e) => {
              e.preventDefault()
              submit(input)
            }}
            className="flex gap-2 pt-3"
          >
            <label htmlFor="busca" className="sr-only">
              Buscar produto
            </label>
            <div className="relative min-w-0 flex-1">
              <input
                id="busca"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Buscar produto, marca ou tamanho"
                className="w-full rounded-full border-0 bg-white py-3.5 pr-11 pl-5 text-base text-tinta placeholder:text-cinza/80 focus:ring-4 focus:ring-gema focus:outline-none"
              />
              {(input || params.q) && (
                <button
                  type="button"
                  onClick={() => submit('')}
                  aria-label="Limpar busca"
                  className="absolute top-1/2 right-3 grid size-7 -translate-y-1/2 place-items-center rounded-full text-cinza hover:bg-papel"
                >
                  ✕
                </button>
              )}
            </div>
            <button className="rounded-full bg-gema px-6 font-semibold text-tinta hover:bg-[#ffdc66]">Buscar</button>
          </form>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        {/* Quanto a consulta demorou e como foi com cada mercado */}
        <section
          aria-live="polite"
          className="-mt-4 grid gap-5 rounded-2xl border border-linha bg-white p-5 md:grid-cols-[minmax(0,0.7fr)_minmax(0,1.6fr)]"
        >
          <div>
            <p className="text-sm font-semibold" style={{ color: modeColor }}>
              Modo {MODE_LABEL[mode].toLowerCase()}
            </p>
            <p className="font-display text-5xl font-extrabold tracking-tight tabular-nums" style={{ color: modeColor }}>
              {duration(loading ? live.elapsed : data?.total_ms)}
            </p>
            <p className="mt-1 text-sm text-cinza">
              {loading ? (
                mode === 'sequential' ? (
                  'Um mercado de cada vez.'
                ) : (
                  'Todos os mercados ao mesmo tempo.'
                )
              ) : (
                data && (
                  <>
                    {data.ok_count} de {MARKETS.length} mercados responderam
                    {failed.length > 0 && (
                      <span className="text-tomate"> ({failed.map((f) => MARKET_BY_ID[f.market_id]?.short).join(', ')} fora do ar)</span>
                    )}
                    .{' '}
                    <Link to="/painel" className="font-semibold text-folha underline-offset-2 hover:underline">
                      Ver no painel
                    </Link>
                  </>
                )
              )}
            </p>
          </div>
          <div aria-label="Tempo de resposta de cada mercado">
            {loading ? (
              <Timeline entries={live.entries} scaleMs={Math.max(live.elapsed * 1.15, 1500)} nowMs={live.elapsed} />
            ) : (
              <Timeline entries={data?.markets ?? []} scaleMs={data?.total_ms ?? 1} />
            )}
          </div>
        </section>

        {error && (
          <p className="mt-6 rounded-xl bg-tomate/10 p-4 text-tomate" role="alert">
            {error}
          </p>
        )}

        <div ref={gridTop} className="scroll-mt-4 pt-8">
          <div className="flex min-h-9 flex-wrap items-center gap-2" role="group" aria-label="Categorias">
            {categories && (
              <button
                onClick={() => update({ category: '' })}
                aria-pressed={!params.category}
                className={`rounded-full px-3.5 py-1.5 text-sm font-medium ${
                  !params.category ? 'bg-tinta text-white' : 'border border-linha bg-white hover:border-tinta/40'
                }`}
              >
                Todas <span className="tabular-nums opacity-60">{int(allCount)}</span>
              </button>
            )}
            {categories?.map((c) => (
              <button
                key={c.name}
                onClick={() => update({ category: c.name })}
                aria-pressed={params.category === c.name}
                className={`rounded-full px-3.5 py-1.5 text-sm font-medium ${
                  params.category === c.name ? 'bg-tinta text-white' : 'border border-linha bg-white hover:border-tinta/40'
                }`}
              >
                {c.name} <span className="tabular-nums opacity-60">{int(c.count)}</span>
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-cinza">
              {loading ? (
                'Consultando os mercados…'
              ) : (
                data && (
                  <>
                    <span className="font-semibold text-tinta tabular-nums">{int(data.total_products)}</span> produtos
                    {params.category && <> em {params.category}</>}
                    {data.pages > 1 && <>, página {data.page} de {data.pages}</>}
                  </>
                )
              )}
            </p>
            <label className="flex items-center gap-2 text-sm text-cinza">
              Ordenar por
              <select
                value={params.sort}
                onChange={(e) => update({ sort: e.target.value as Sort })}
                className="rounded-lg border border-linha bg-white px-2 py-1.5 text-tinta"
              >
                <option value="destaques">Destaques</option>
                <option value="preco">Menor preço</option>
                <option value="economia">Maior diferença de preço</option>
                <option value="nome">Nome</option>
              </select>
            </label>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4 xl:grid-cols-5">
          {loading ? <SkeletonGrid /> : data?.products.map((p) => <ProductCard key={p.slug} product={p} onOpen={() => setSelected(p)} />)}
          {!loading && data && data.products.length === 0 && (
            <div className="col-span-full rounded-2xl border border-dashed border-linha p-10 text-center">
              <p className="font-display text-xl font-bold">Nada encontrado para “{params.q}”</p>
            </div>
          )}
        </div>

        {!loading && data && data.pages > 1 && (
          <nav className="mt-8 mb-16 flex flex-wrap items-center justify-center gap-1" aria-label="Páginas">
            <button
              onClick={() => goToPage(data.page - 1)}
              disabled={data.page <= 1}
              className="rounded-full px-3 py-2 text-sm font-semibold text-folha hover:bg-folha-clara disabled:opacity-40"
            >
              Anterior
            </button>
            {pageList(data.page, data.pages).map((p, i) =>
              p === '…' ? (
                <span key={`gap-${i}`} className="px-1 text-cinza">
                  …
                </span>
              ) : (
                <button
                  key={p}
                  onClick={() => goToPage(p)}
                  aria-current={p === data.page ? 'page' : undefined}
                  className={`min-w-9 rounded-full px-2 py-2 text-sm tabular-nums ${p === data.page ? 'bg-tinta font-semibold text-white' : 'hover:bg-white'}`}
                >
                  {p}
                </button>
              ),
            )}
            <button
              onClick={() => goToPage(data.page + 1)}
              disabled={data.page >= data.pages}
              className="rounded-full px-3 py-2 text-sm font-semibold text-folha hover:bg-folha-clara disabled:opacity-40"
            >
              Próxima
            </button>
          </nav>
        )}
        {!(data && data.pages > 1 && !loading) && <div className="mb-16" />}
      </div>

      <ProductDrawer key={selected?.slug} product={selected} timings={data?.markets ?? []} onClose={() => setSelected(null)} />
    </main>
  )
}
