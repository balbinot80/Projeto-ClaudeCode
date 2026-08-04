'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  DndContext, DragEndEvent, PointerSensor, useSensor, useSensors, closestCenter,
} from '@dnd-kit/core'
import {
  SortableContext, verticalListSortingStrategy, arrayMove,
} from '@dnd-kit/sortable'
import { createClient } from '@/lib/supabase/client'
import { Card, Status, COLUMNS } from '@/types/kanban'
import KanbanCard from '@/components/kanban/KanbanCard'
import CardModal from '@/components/kanban/CardModal'

export default function KanbanPage() {
  const router = useRouter()
  const supabase = createClient()
  const [cards, setCards] = useState<Card[]>([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState<{ open: boolean; card?: Card; defaultStatus?: Status }>({ open: false })

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  const load = useCallback(async () => {
    const { data } = await supabase
      .from('cards')
      .select('*')
      .order('position', { ascending: true })
    if (data) setCards(data as Card[])
    setLoading(false)
  }, [supabase])

  useEffect(() => { load() }, [load])

  async function handleLogout() {
    await supabase.auth.signOut()
    router.push('/login')
  }

  async function handleSave(data: { title: string; description: string; status: Status; priority: Card['priority'] }) {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return

    if (modal.card) {
      const { data: updated } = await supabase
        .from('cards')
        .update({ ...data, updated_at: new Date().toISOString() })
        .eq('id', modal.card.id)
        .select()
        .single()
      if (updated) setCards(prev => prev.map(c => c.id === updated.id ? updated as Card : c))
    } else {
      const position = cards.filter(c => c.status === data.status).length
      const { data: created } = await supabase
        .from('cards')
        .insert({ ...data, user_id: user.id, position })
        .select()
        .single()
      if (created) setCards(prev => [...prev, created as Card])
    }
    setModal({ open: false })
  }

  async function handleDelete(id: string) {
    await supabase.from('cards').delete().eq('id', id)
    setCards(prev => prev.filter(c => c.id !== id))
  }

  async function handleMove(id: string, status: Status) {
    const position = cards.filter(c => c.status === status).length
    const { data: updated } = await supabase
      .from('cards')
      .update({ status, position, updated_at: new Date().toISOString() })
      .eq('id', id)
      .select()
      .single()
    if (updated) setCards(prev => prev.map(c => c.id === id ? updated as Card : c))
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const activeCard = cards.find(c => c.id === active.id)
    const overCard   = cards.find(c => c.id === over.id)
    if (!activeCard || !overCard || activeCard.status !== overCard.status) return

    const colCards = cards.filter(c => c.status === activeCard.status)
    const oldIndex = colCards.findIndex(c => c.id === active.id)
    const newIndex = colCards.findIndex(c => c.id === over.id)
    const reordered = arrayMove(colCards, oldIndex, newIndex).map((c, i) => ({ ...c, position: i }))

    setCards(prev => [
      ...prev.filter(c => c.status !== activeCard.status),
      ...reordered,
    ])

    await Promise.all(
      reordered.map(c => supabase.from('cards').update({ position: c.position }).eq('id', c.id))
    )
  }

  const colCards = (status: Status) =>
    cards.filter(c => c.status === status).sort((a, b) => a.position - b.position)

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--au-bg)' }}>
        <p style={{ color: 'var(--au-text-muted)' }}>Carregando...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--au-bg)' }}>
      {/* Header */}
      <header
        className="flex items-center justify-between px-6 py-4 shadow-sm"
        style={{ background: 'var(--au-surface)', borderBottom: '1px solid var(--au-border)' }}
      >
        <div className="flex items-center gap-3">
          <span style={{ fontSize: 22 }}>💎</span>
          <h1
            className="text-lg font-semibold tracking-tight"
            style={{ color: 'var(--au-primary)', fontFamily: 'Georgia, serif' }}
          >
            Aureum — Projetos
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setModal({ open: true })}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-white transition-opacity hover:opacity-90"
            style={{ background: 'var(--au-primary)' }}
          >
            + Novo card
          </button>
          <button
            onClick={handleLogout}
            className="px-3 py-2 rounded-lg text-sm transition"
            style={{ color: 'var(--au-text-muted)', background: 'var(--au-bg)' }}
          >
            Sair
          </button>
        </div>
      </header>

      {/* Board */}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <div className="flex-1 flex gap-4 p-6 overflow-x-auto">
          {COLUMNS.map(col => {
            const colList = colCards(col.id)
            return (
              <div key={col.id} className="flex-shrink-0 w-72 flex flex-col gap-3">
                {/* Column header */}
                <div className="flex items-center justify-between px-1">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: col.color }} />
                    <span className="text-sm font-semibold" style={{ color: 'var(--au-text)' }}>
                      {col.label}
                    </span>
                    <span
                      className="text-xs px-1.5 py-0.5 rounded-full font-medium"
                      style={{ background: col.color + '20', color: col.color }}
                    >
                      {colList.length}
                    </span>
                  </div>
                  <button
                    onClick={() => setModal({ open: true, defaultStatus: col.id })}
                    className="text-lg leading-none transition-opacity hover:opacity-60"
                    style={{ color: 'var(--au-text-muted)' }}
                    title="Adicionar card"
                  >
                    +
                  </button>
                </div>

                {/* Cards */}
                <div
                  className="flex-1 rounded-xl p-2 flex flex-col gap-2 min-h-24"
                  style={{ background: col.color + '0D', border: `1px dashed ${col.color}40` }}
                >
                  <SortableContext
                    items={colList.map(c => c.id)}
                    strategy={verticalListSortingStrategy}
                  >
                    {colList.map(card => (
                      <div
                        key={card.id}
                        className="rounded-xl"
                        style={{ background: 'var(--au-surface)', border: '1px solid var(--au-border)' }}
                      >
                        <KanbanCard
                          card={card}
                          onEdit={c => setModal({ open: true, card: c })}
                          onDelete={handleDelete}
                          onMove={handleMove}
                        />
                      </div>
                    ))}
                  </SortableContext>

                  {colList.length === 0 && (
                    <p className="text-xs text-center py-4" style={{ color: col.color + '80' }}>
                      Nenhum item
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </DndContext>

      {modal.open && (
        <CardModal
          card={modal.card}
          defaultStatus={modal.defaultStatus}
          onSave={handleSave}
          onClose={() => setModal({ open: false })}
        />
      )}
    </div>
  )
}
