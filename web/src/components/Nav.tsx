'use client'

import Link from 'next/link'
import Image from 'next/image'
import { usePathname, useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { LogOut, Users, LayoutGrid } from 'lucide-react'

const links = [
  { href: '/revendedoras', label: 'Revendedoras', icon: Users },
  { href: '/kanban',       label: 'Projetos',     icon: LayoutGrid },
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
      className="flex items-center justify-between px-6 py-0 h-14 shrink-0"
      style={{ background: 'var(--au-primary)' }}
    >
      {/* Logo */}
      <div className="flex items-center gap-8">
        <div className="relative h-10 w-32 shrink-0">
          <Image
            src="/brand/logo-branco.png"
            alt="Aureum Joias"
            fill
            style={{ objectFit: 'contain', objectPosition: 'left center' }}
            priority
          />
        </div>

        {/* Links de navegação */}
        <nav className="flex items-center gap-1">
          {links.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href)
            return (
              <Link
                key={href}
                href={href}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-150"
                style={{
                  color:      active ? 'var(--au-primary)' : 'rgba(255,255,255,0.75)',
                  background: active ? '#FFFFFF'           : 'transparent',
                  fontFamily: 'var(--font-jost, Jost, sans-serif)',
                  letterSpacing: '0.02em',
                }}
                onMouseEnter={e => {
                  if (!active) (e.currentTarget as HTMLElement).style.color = '#FFFFFF'
                }}
                onMouseLeave={e => {
                  if (!active) (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.75)'
                }}
              >
                <Icon size={14} strokeWidth={1.75} />
                {label}
              </Link>
            )
          })}
        </nav>
      </div>

      {/* Sair */}
      <button
        onClick={handleLogout}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-all duration-150"
        style={{ color: 'rgba(255,255,255,0.65)', fontFamily: 'var(--font-jost, Jost, sans-serif)' }}
        onMouseEnter={e => (e.currentTarget.style.color = '#FFFFFF')}
        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.65)')}
      >
        <LogOut size={14} strokeWidth={1.75} />
        Sair
      </button>
    </header>
  )
}
