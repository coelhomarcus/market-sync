// Espelho de backend/common/config.py — cores validadas para daltonismo (dataviz)
export const MARKETS = [
  { id: 'aurora', name: 'Mercado Aurora', short: 'Aurora', color: '#16a34a' },
  { id: 'supervila', name: 'SuperVila', short: 'SuperVila', color: '#2563eb' },
  { id: 'emporio-sol', name: 'Empório Sol', short: 'Empório Sol', color: '#ea580c' },
  { id: 'max-atacarejo', name: 'Max Atacarejo', short: 'Max', color: '#9333ea' },
  { id: 'ipe', name: 'Mercadinho Ipê', short: 'Ipê', color: '#db2777' },
] as const

export const MARKET_BY_ID: Record<string, (typeof MARKETS)[number]> = Object.fromEntries(MARKETS.map((m) => [m.id, m]))

export const marketColor = (id: string) => MARKET_BY_ID[id]?.color ?? '#5b6a61'
export const marketName = (id: string) => MARKET_BY_ID[id]?.name ?? id

export const MODE_LABEL = { sequential: 'Sequencial', concurrent: 'Concorrente' } as const
export const MODE_COLOR = { sequential: '#d9480f', concurrent: '#1c7ed6' } as const
