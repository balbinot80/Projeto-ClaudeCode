import { cn } from '@/lib/utils'

type BadgeVariant = 'baixado' | 'aberto' | 'alerta' | 'neutro'

const variants: Record<BadgeVariant, string> = {
  baixado: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  aberto:  'bg-amber-50  text-amber-700  border-amber-200',
  alerta:  'bg-red-50    text-red-700    border-red-200',
  neutro:  'bg-gray-50   text-gray-600   border-gray-200',
}

export function Badge({ label, variant = 'neutro' }: { label: string; variant?: BadgeVariant }) {
  return (
    <span className={cn(
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border',
      variants[variant]
    )}>
      {label}
    </span>
  )
}

export function statusVariant(status: string): BadgeVariant {
  if (status === 'Baixado') return 'baixado'
  if (status === 'Aberto')  return 'aberto'
  return 'neutro'
}
