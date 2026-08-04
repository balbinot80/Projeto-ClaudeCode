'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

const links = [
  { href: '/revendedoras', label: '👥 Revendedoras' },
  { href: '/kanban',       label: '📋 Projetos'     },
]

export default function Nav() {
  const pathname = usePathname()
  const router   = useRouter()

  async function handleLogout() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
  }

  return (
    <header
      className="flex items-center justify-between px-6 py-3 shadow-sm"
      style={{ background: 'var(--au-surface)', borderBottom: '1px solid var(--au-border)' }}
    >
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 mr-4">
          <span style={{ fontSize: 20 }}>💎</span>
          <span
            className="text-base font-semibold tracking-tight"
            style={{ color: 'var(--au-primary)', fontFamily: 'Georgia, serif' }}
          >
            Aureum
          </span>
        </div>
        {links.map(l => (
          <Link
            key={l.href}
            href={l.href}
            className="text-sm font-medium px-3 py-1.5 rounded-lg transition"
            style={{
              color: pathname.startsWith(l.href) ? 'var(--au-primary)' : 'var(--au-text-muted)',
              background: pathname.startsWith(l.href) ? 'var(--au-primary-pale)' : 'transparent',
            }}
          >
            {l.label}
          </Link>
        ))}
      </div>
      <button
        onClick={handleLogout}
        className="text-sm px-3 py-1.5 rounded-lg transition"
        style={{ color: 'var(--au-text-muted)' }}
      >
        Sair
      </button>
    </header>
  )
}
