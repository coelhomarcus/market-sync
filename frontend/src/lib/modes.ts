import type { Mode } from './types'

export const MODES: Mode[] = ['sequential', 'concurrent']
export const MODE_LABEL = { sequential: 'Sequencial', concurrent: 'Concorrente' } as const
export const MODE_COLOR = { sequential: '#d9480f', concurrent: '#1c7ed6' } as const
