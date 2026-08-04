import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

const BASE_URL = process.env.JUERI_BASE_URL!
const TOKEN    = process.env.JUERI_TOKEN!

// Busca uma única página — rápido o suficiente para o limite de 10s do Hobby
export async function GET(req: NextRequest) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const page = req.nextUrl.searchParams.get('page') ?? '1'
  const url  = `${BASE_URL}/pedido?page=${page}`

  try {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${TOKEN}`, Accept: 'application/json' },
      cache: 'no-store',
    })

    if (res.status === 429) return NextResponse.json({ error: 'rate_limit' }, { status: 429 })
    if (!res.ok)            return NextResponse.json({ error: `Jueri ${res.status}` }, { status: 500 })

    const json = await res.json()
    return NextResponse.json({
      data:          json.data          ?? [],
      next_page_url: json.next_page_url ?? null,
      last_page:     json.last_page     ?? 1,
      current_page:  json.current_page  ?? Number(page),
    })
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 })
  }
}
