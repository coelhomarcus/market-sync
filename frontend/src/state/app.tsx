import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Mode } from '../lib/types'
import { load, save } from './storage'

export interface CartItem {
  slug: string
  name: string
  brand?: string
  unit: string
  image: string
  qty: number
}

interface AppState {
  mode: Mode
  setMode: (m: Mode) => void
  cart: CartItem[]
  cartCount: number
  addToCart: (item: Omit<CartItem, 'qty'>, qty?: number) => void
  setQty: (slug: string, qty: number) => void
  clearCart: () => void
  cartOpen: boolean
  setCartOpen: (open: boolean) => void
}

const Ctx = createContext<AppState | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<Mode>(() => load('modo', 'concurrent'))
  const [cart, setCart] = useState<CartItem[]>(() => load('cesta', []))
  const [cartOpen, setCartOpen] = useState(false)

  useEffect(() => save('cesta', cart), [cart])

  const setMode = useCallback((m: Mode) => {
    setModeState(m)
    save('modo', m)
  }, [])

  const addToCart = useCallback((item: Omit<CartItem, 'qty'>, qty = 1) => {
    setCart((prev) => {
      const found = prev.find((i) => i.slug === item.slug)
      if (found) return prev.map((i) => (i.slug === item.slug ? { ...i, qty: Math.min(99, i.qty + qty) } : i))
      return [...prev, { ...item, qty }]
    })
  }, [])

  const setQty = useCallback((slug: string, qty: number) => {
    setCart((prev) => (qty <= 0 ? prev.filter((i) => i.slug !== slug) : prev.map((i) => (i.slug === slug ? { ...i, qty: Math.min(99, qty) } : i))))
  }, [])

  const value = useMemo<AppState>(
    () => ({
      mode,
      setMode,
      cart,
      cartCount: cart.reduce((n, i) => n + i.qty, 0),
      addToCart,
      setQty,
      clearCart: () => setCart([]),
      cartOpen,
      setCartOpen,
    }),
    [mode, setMode, cart, addToCart, setQty, cartOpen],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useApp() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useApp fora do AppProvider')
  return ctx
}
