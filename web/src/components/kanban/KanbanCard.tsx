'use client'

import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Card, PRIORITY_COLOR, PRIORITY_LABEL, Status, COLUMNS } from '@/types/kanban'

interface Props {
  card: Card
  onEdit: (card: Card) => void
  onDelete: (id: string) => void
  onMove: (id: string, status: Status) => void
}

export default function KanbanCard({ card, onEdit, onDelete, onMove }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }

  const otherCols = COLUMNS.filter(c => c.id !== card.status)

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="group rounded-xl p-4 shadow-sm flex flex-col gap-2 cursor-grab active:cursor-grabbing"
      {...attributes}
      {...listeners}
      onClick={e => e.stopPropagation()}
    >
      {/* Priority badge */}
      <div className="flex items-center justify-between">
        <span
          className="text-xs font-medium px-2 py-0.5 rounded-full"
          style={{
            color: PRIORITY_COLOR[card.priority],
            background: PRIORITY_COLOR[card.priority] + '18',
          }}
        >
          {PRIORITY_LABEL[card.priority]}
        </span>
        <span className="text-xs" style={{ color: 'var(--au-text-muted)' }}>
          {new Date(card.created_at).toLocaleDateString('pt-BR')}
        </span>
      </div>

      {/* Title */}
      <p className="text-sm font-semibold leading-snug" style={{ color: 'var(--au-text)' }}>
        {card.title}
      </p>

      {/* Description */}
      {card.description && (
        <p className="text-xs leading-relaxed" style={{ color: 'var(--au-text-muted)' }}>
          {card.description}
        </p>
      )}

      {/* Actions */}
      <div
        className="flex items-center gap-2 pt-1 opacity-0 group-hover:opacity-100 transition-opacity"
        onPointerDown={e => e.stopPropagation()}
      >
        <button
          onClick={() => onEdit(card)}
          className="text-xs px-2 py-1 rounded-md transition"
          style={{ color: 'var(--au-primary)', background: 'var(--au-primary-pale)' }}
        >
          Editar
        </button>
        {otherCols.map(col => (
          <button
            key={col.id}
            onClick={() => onMove(card.id, col.id)}
            className="text-xs px-2 py-1 rounded-md transition"
            style={{ color: col.color, background: col.color + '18' }}
          >
            → {col.label}
          </button>
        ))}
        <button
          onClick={() => onDelete(card.id)}
          className="text-xs px-2 py-1 rounded-md ml-auto transition"
          style={{ color: '#9CA3AF', background: '#F3F4F6' }}
        >
          ✕
        </button>
      </div>
    </div>
  )
}
