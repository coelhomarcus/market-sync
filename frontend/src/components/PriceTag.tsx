import { splitPrice } from '../lib/format'

interface Props {
  price: number
  label?: string
  size?: 'sm' | 'md' | 'lg'
  tone?: 'gema' | 'tomate' | 'plain'
}

const SIZES = {
  sm: { reais: 'text-xl', cents: 'text-[11px]', pad: 'pl-4 pr-2.5 py-1' },
  md: { reais: 'text-[28px]', cents: 'text-xs', pad: 'pl-5 pr-3 py-1.5' },
  lg: { reais: 'text-5xl', cents: 'text-base', pad: 'pl-6 pr-4 py-2' },
}

const TONES = {
  gema: 'bg-gema text-tinta',
  tomate: 'bg-tomate text-white',
  plain: 'bg-white text-tinta ring-1 ring-linha',
}

/** Etiqueta de gôndola: centavos sobrescritos, como no preço de prateleira. */
export function PriceTag({ price, label, size = 'md', tone = 'gema' }: Props) {
  const { reais, cents } = splitPrice(price)
  const s = SIZES[size]
  return (
    <div className={`shelf-tag inline-flex flex-col leading-none ${TONES[tone]} ${s.pad}`} aria-label={`${label ? label + ' ' : ''}R$ ${reais},${cents}`}>
      {label && <span className="mb-0.5 text-[11px] font-medium opacity-80">{label}</span>}
      <span className="flex items-start font-display font-extrabold tracking-tight" aria-hidden>
        <span className={`${s.cents} mt-[0.2em] mr-0.5 font-bold`}>R$</span>
        <span className={s.reais}>{reais}</span>
        <span className={`${s.cents} mt-[0.2em] ml-px font-bold`}>,{cents}</span>
      </span>
    </div>
  )
}
