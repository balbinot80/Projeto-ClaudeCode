import { NextResponse } from 'next/server'
import { getAllPages } from '@/lib/jueri'
import { createClient } from '@/lib/supabase/server'

export const maxDuration = 60 // segundos — necessário para buscar muitas páginas da Jueri

export async function GET() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  try {
    const pedidos = await getAllPages('pedido')
    return NextResponse.json(pedidos, {
      headers: { 'Cache-Control': 's-maxage=300, stale-while-revalidate=60' },
    })
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 })
  }
}
