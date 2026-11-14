const brlFmt = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

export const brl = (n: number) => brlFmt.format(n)

/** 25.49 -> { reais: '25', cents: '49' } para a etiqueta de preço */
export function splitPrice(n: number) {
  const [reais, cents] = n.toFixed(2).split('.')
  return { reais: Number(reais).toLocaleString('pt-BR'), cents }
}

export function duration(ms: number | null | undefined) {
  if (ms == null || Number.isNaN(ms)) return '—'
  if (ms < 1000) return `${Math.round(ms)} ms`
  return `${(ms / 1000).toFixed(2).replace('.', ',')} s`
}

export const num = (n: number, digits = 1) => n.toLocaleString('pt-BR', { maximumFractionDigits: digits, minimumFractionDigits: digits })

export const clock = (ts: number) =>
  new Date(ts * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
  '.' +
  String(Math.floor((ts % 1) * 1000)).padStart(3, '0')

/** Tamanho em unidades decimais (1 KB = 1000 bytes), como o seed e o relatório. */
export function bytes(n: number | null | undefined) {
  if (n == null) return '—'
  if (n < 1000) return `${n} B`
  if (n < 1e6) return `${num(n / 1e3, n < 1e4 ? 1 : 0)} KB`
  if (n < 1e9) return `${num(n / 1e6, 1)} MB`
  return `${num(n / 1e9, 2)} GB`
}

export const int = (n: number) => n.toLocaleString('pt-BR')
