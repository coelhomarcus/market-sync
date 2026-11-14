import { useState } from 'react'

/** Foto do produto; se o arquivo não existir, mostra a inicial sobre um fundo neutro. */
export function ProductImage({ src, name, className = '' }: { src: string; name: string; className?: string }) {
  const [failed, setFailed] = useState(false)
  if (failed)
    return (
      <div className={`grid place-items-center bg-folha-clara font-display text-4xl font-bold text-folha/50 ${className}`} aria-hidden>
        {name[0]}
      </div>
    )
  return <img src={src} alt={name} loading="lazy" onError={() => setFailed(true)} className={`object-contain mix-blend-multiply ${className}`} />
}
