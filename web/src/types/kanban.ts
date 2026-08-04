export type Status = 'backlog' | 'testing' | 'routine' | 'cancelled'

export interface Card {
  id: string
  title: string
  description: string | null
  status: Status
  priority: 'low' | 'medium' | 'high'
  position: number
  created_at: string
  updated_at: string
  user_id: string
}

export const COLUMNS: { id: Status; label: string; color: string }[] = [
  { id: 'backlog',   label: 'Backlog',      color: 'var(--col-backlog)'   },
  { id: 'testing',   label: 'Em teste',     color: 'var(--col-testing)'   },
  { id: 'routine',   label: 'Na rotina',    color: 'var(--col-routine)'   },
  { id: 'cancelled', label: 'Cancelado',    color: 'var(--col-cancelled)' },
]

export const PRIORITY_LABEL: Record<Card['priority'], string> = {
  low:    '⬇ Baixa',
  medium: '➡ Média',
  high:   '⬆ Alta',
}

export const PRIORITY_COLOR: Record<Card['priority'], string> = {
  low:    '#6B7280',
  medium: '#C4985A',
  high:   '#AB6774',
}
