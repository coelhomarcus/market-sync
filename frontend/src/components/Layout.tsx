import { NavLink, Outlet } from 'react-router'
import { useApp } from '../state/app'
import { useLive } from '../state/live'
import { CartDrawer } from './CartDrawer'
import { ModeToggle } from './ModeToggle'

function Logo() {
  return (
    <NavLink to="/" className="flex items-center gap-2.5" aria-label="Comparador de Preços, página inicial">
      <svg width="34" height="34" viewBox="0 0 32 32" aria-hidden>
        <path d="M4 9.5 13.5 3H28v14.5L18.5 29 4 14.5Z" fill="#ffd23f" stroke="#08402a" strokeWidth="2" strokeLinejoin="round" />
        <circle cx="22" cy="9" r="2.5" fill="#08402a" />
      </svg>
      <span className="leading-none">
        <span className="block font-display text-xl font-extrabold tracking-tight text-white">Comparador</span>
        <span className="block text-[12px] text-white/70">de preços de supermercado</span>
      </span>
    </NavLink>
  )
}

export function Layout() {
  const { cartCount, setCartOpen } = useApp()
  const { connected } = useLive()
  const link = ({ isActive }: { isActive: boolean }) =>
    `rounded-full px-3 py-1.5 text-sm font-semibold transition-colors ${isActive ? 'bg-white/15 text-white' : 'text-white/75 hover:text-white'}`

  return (
    <div className="min-h-dvh">
      <header className="bg-folha">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 sm:px-6">
          <Logo />
          <nav className="flex items-center gap-1" aria-label="Principal">
            <NavLink to="/" end className={link}>
              Loja
            </NavLink>
            <NavLink to="/painel" className={link}>
              <span className="inline-flex items-center gap-1.5">
                <span
                  className={`size-2 rounded-full ${connected ? 'bg-gema' : 'bg-white/30'}`}
                  title={connected ? 'Recebendo eventos ao vivo' : 'Sem conexão com o agregador'}
                />
                Comparar modos
              </span>
            </NavLink>
          </nav>
          <div className="flex w-full items-center gap-3 sm:ml-auto sm:w-auto">
            <ModeToggle />
            <button
              onClick={() => setCartOpen(true)}
              className="relative ml-auto flex shrink-0 items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-folha hover:bg-gema-clara"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6" />
                <circle cx="10" cy="20.5" r="1.3" />
                <circle cx="17" cy="20.5" r="1.3" />
              </svg>
              <span className="max-sm:sr-only">Cesta</span>
              {cartCount > 0 && (
                <span className="grid min-w-5 place-items-center rounded-full bg-gema px-1.5 text-xs font-bold text-tinta tabular-nums">{cartCount}</span>
              )}
            </button>
          </div>
        </div>
      </header>
      <Outlet />
      <CartDrawer />
    </div>
  )
}
