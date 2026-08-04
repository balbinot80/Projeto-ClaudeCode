'use client'

import { useState, useEffect } from 'react'
import { Card, Status, COLUMNS } from '@/types/kanban'

interface Props {
  card?: Card | null
  defaultStatus?: Status
  onSave: (data: { title: string; description: string; status: Status; priority: Card['priority'] }) => void
  onClose: () => void
}

export default function CardModal({ card, defaultStatus = 'backlog', onSave, onClose }: Props) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState<Status>(defaultStatus)
  const [priority, setPriority] = useState<Card['priority']>('medium')

  useEffect(() => {
    if (card) {
      setTitle(card.title)
      setDescription(card.description || '')
      setStatus(card.status)
      setPriority(card.priority)
    }
  }, [card])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    onSave({ title: title.trim(), description: description.trim(), status, priority })
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(42,26,31,0.4)', backdropFilter: 'blur(2px)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl shadow-xl p-6 flex flex-col gap-4"
        style={{ background: 'var(--au-surface)', border: '1px solid var(--au-border)' }}
        onClick={e => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold" style={{ color: 'var(--au-primary)' }}>
          {card ? 'Editar card' : 'Novo card'}
        </h2>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--au-text-muted)' }}>
              Título *
            </label>
            <input
              autoFocus
              value={title}
              onChange={e => setTitle(e.target.value)}
              className="w-full rounded-lg px-3 py-2 text-sm outline-none"
              style={{ border: '1px solid var(--au-border)', background: 'var(--au-bg)', color: 'var(--au-text)' }}
              placeholder="O que precisa ser feito?"
            />
          </div>

          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--au-text-muted)' }}>
              Descrição
            </label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={3}
              className="w-full rounded-lg px-3 py-2 text-sm outline-none resize-none"
              style={{ border: '1px solid var(--au-border)', background: 'var(--au-bg)', color: 'var(--au-text)' }}
              placeholder="Detalhes opcionais..."
            />
          </div>

          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--au-text-muted)' }}>
                Coluna
              </label>
              <select
                value={status}
                onChange={e => setStatus(e.target.value as Status)}
                className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                style={{ border: '1px solid var(--au-border)', background: 'var(--au-bg)', color: 'var(--au-text)' }}
              >
                {COLUMNS.map(c => (
                  <option key={c.id} value={c.id}>{c.label}</option>
                ))}
              </select>
            </div>

            <div className="flex-1">
              <label className="block text-xs font-medium mb-1" style={{ color: 'var(--au-text-muted)' }}>
                Prioridade
              </label>
              <select
                value={priority}
                onChange={e => setPriority(e.target.value as Card['priority'])}
                className="w-full rounded-lg px-3 py-2 text-sm outline-none"
                style={{ border: '1px solid var(--au-border)', background: 'var(--au-bg)', color: 'var(--au-text)' }}
              >
                <option value="low">⬇ Baixa</option>
                <option value="medium">➡ Média</option>
                <option value="high">⬆ Alta</option>
              </select>
            </div>
          </div>

          <div className="flex gap-2 pt-1 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm transition"
              style={{ color: 'var(--au-text-muted)', background: 'var(--au-bg)' }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg text-sm font-semibold text-white transition"
              style={{ background: 'var(--au-primary)' }}
            >
              {card ? 'Salvar' : 'Criar card'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
