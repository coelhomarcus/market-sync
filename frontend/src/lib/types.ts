export type Mode = 'sequential' | 'concurrent'

export interface Offer {
  market_id: string
  market_name: string
  price: number
  stock: number
  in_stock: boolean
}

export interface Product {
  slug: string
  name: string
  brand: string
  category: string
  unit: string
  image: string
  order: number
  offers: Offer[]
  cheapest: Offer | null
  min_price: number | null
  max_price: number | null
  savings: number
}

export interface MarketTiming {
  market_id: string
  market_name: string
  ok: boolean
  error: string | null
  start_ms: number
  end_ms: number
  duration_ms: number
  connect_ms: number
  send_ms: number
  wait_ms: number
  bytes_sent: number
  bytes_received: number
  server_cpu_ms: number
  thread: string
}

export interface Resources {
  agg_cpu_ms: number
  server_cpu_ms: number
  cpu_ms: number
  cpu_util: number
  threads_base: number
  threads_peak: number
  threads_extra: number
  rss_mb: number
}

export type Sort = 'destaques' | 'preco' | 'economia' | 'nome'

export interface SearchResponse {
  request_id: string
  mode: Mode
  query: string
  category: string
  sort: Sort
  total_ms: number
  products: Product[]
  total_products: number
  total_offers: number
  page: number
  pages: number
  page_size: number
  categories: { name: string; count: number }[]
  markets: MarketTiming[]
  ok_count: number
  error_count: number
}

export interface BasketLine {
  slug: string
  name: string
  brand?: string
  unit?: string
  qty: number
  price: number
  subtotal: number
  market_id?: string
  market_name?: string
}

export interface BasketMarket {
  market_id: string
  market_name: string
  ok: boolean
  error?: string
  total?: number
  lines?: BasketLine[]
  missing?: string[]
  complete?: boolean
}

export interface BasketResponse {
  request_id: string
  mode: Mode
  total_ms: number
  markets: BasketMarket[]
  cheapest: BasketMarket | null
  best_mix: { total: number; lines: BasketLine[]; missing: string[]; savings_vs_cheapest: number | null }
  timings: MarketTiming[]
}

export interface MetricRecord {
  id: number
  ts: number
  mode: Mode
  kind: 'search' | 'basket'
  source: 'loja' | 'benchmark'
  query: string
  total_ms: number
  ok_count: number
  error_count: number
  markets: MarketTiming[]
  resources?: Resources
  request_id?: string
}

export interface Stats {
  count: number
  avg: number | null
  min: number | null
  max: number | null
  stdev: number | null
}

export interface BenchmarkResult {
  runs: number
  query: string
  sequential: Stats
  concurrent: Stats
  speedup: number | null
  resources?: Record<Mode, Partial<Resources> | undefined>
  samples: { mode: Mode; total_ms: number }[]
}

export interface MarketStatus {
  id: string
  name: string
  port: number
  color: string
  reachable: boolean
  online: boolean
  latency_ms?: number
  products?: number
  history_rows?: number
  db_bytes?: number
  cpu_s?: number
  rss_bytes?: number
  requests_served?: number
  thread_count?: number
  rtt_ms: number
  error?: string
}

export interface BusEvent {
  seq: number
  type: string
  ts: number
  request_id?: string
  mode?: Mode
  kind?: string
  market?: string
  t_ms?: number
  duration_ms?: number
  count?: number
  error?: string
  query?: string
  source?: string
  total_ms?: number
  ok_count?: number
  error_count?: number
  thread?: string
  record?: MetricRecord
  done?: number
  runs?: number
  online?: boolean
  latency_ms?: number
  [key: string]: unknown
}

export interface PriceHistory {
  slug: string
  days: number
  markets: { market_id: string; market_name: string; ok: boolean; error: string | null; points: { day: string; price: number }[] }[]
}
