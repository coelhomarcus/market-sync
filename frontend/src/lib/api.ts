import type { BasketResponse, BenchmarkResult, MarketStatus, MetricRecord, Mode, SearchResponse, Sort } from './types'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new Error('O agregador não está respondendo. Rode `python run_all.py` na pasta backend.')
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  search: (mode: Mode, params: { q: string; category?: string; sort?: Sort; page?: number; source?: 'loja' | 'comparacao' }) =>
    request<SearchResponse>(
      `/api/search/${mode}?${new URLSearchParams({
        q: params.q,
        category: params.category ?? '',
        sort: params.sort ?? 'preco',
        page: String(params.page ?? 1),
        source: params.source ?? 'loja',
      })}`,
    ),
  basket: (mode: Mode, items: { slug: string; qty: number }[]) => request<BasketResponse>(`/api/basket/${mode}`, json({ items })),
  benchmark: (runs: number, q: string) => request<BenchmarkResult>('/api/benchmark', json({ runs, q })),
  markets: () => request<MarketStatus[]>('/api/markets'),
  configure: (id: string, cfg: { latency_ms?: number; online?: boolean }) => request<MarketStatus>(`/api/markets/${id}/config`, json(cfg)),
  metricsHistory: () => request<{ records: MetricRecord[] }>('/api/metrics/history?limit=500'),
  resetMetrics: () => request<{ ok: boolean }>('/api/metrics', { method: 'DELETE' }),
}
