import type { MetricRecord, Mode } from './types'

export function stats(values: number[]) {
  if (!values.length) return { count: 0, avg: null, min: null, max: null }
  const sum = values.reduce((a, b) => a + b, 0)
  return { count: values.length, avg: sum / values.length, min: Math.min(...values), max: Math.max(...values) }
}

export function modeStats(records: MetricRecord[], mode: Mode) {
  return stats(records.filter((r) => r.mode === mode).map((r) => r.total_ms))
}

export function lastOf(records: MetricRecord[], mode: Mode) {
  for (let i = records.length - 1; i >= 0; i--) if (records[i].mode === mode) return records[i]
  return undefined
}
