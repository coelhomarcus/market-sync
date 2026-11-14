import type { ReactNode } from 'react'

/** Uma seção do painel: título e explicação fora do cartão, conteúdo abaixo. */
export function Section({ id, title, description, actions, children }: { id: string; title: string; description?: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-20">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div className="max-w-3xl">
          <h2 id={`${id}-title`} className="font-display text-2xl font-bold tracking-tight">
            {title}
          </h2>
          {description && <p className="mt-0.5 text-sm text-cinza">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  )
}
