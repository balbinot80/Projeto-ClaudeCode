'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

import { createClient } from '@/lib/supabase/client'

export default function LoginPage() {
  const router = useRouter()
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  async function handleLogin(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true)
    setError('')

    const supabase = createClient()
    const { error } = await supabase.auth.signInWithPassword({ email, password })

    if (error) {
      setError('E-mail ou senha incorretos.')
      setLoading(false)
      return
    }

    router.push('/revendedoras')
    router.refresh()
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ background: 'var(--au-primary)' }}
    >
      <div
        className="w-full max-w-sm rounded-2xl shadow-2xl p-8"
        style={{ background: 'var(--au-surface)', border: '1px solid rgba(255,255,255,0.15)' }}
      >
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div
            aria-label="Aureum Joias"
            style={{
              height: 80,
              width: 220,
              backgroundImage: 'url("/brand/logo-rosa.png")',
              backgroundSize: 'auto 280px',
              backgroundPosition: 'center center',
              backgroundRepeat: 'no-repeat',
            }}
          />
        </div>

        <form onSubmit={handleLogin} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold uppercase tracking-widest"
                   style={{ color: 'var(--au-text-muted)', fontFamily: 'var(--font-jost, Jost, sans-serif)' }}>
              E-mail
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="w-full rounded-xl px-4 py-2.5 text-sm outline-none transition-all"
              style={{
                border:     '1px solid var(--au-border)',
                background: 'var(--au-bg)',
                color:      'var(--au-text)',
                fontFamily: 'var(--font-jost, Jost, sans-serif)',
              }}
              placeholder="seu@email.com"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold uppercase tracking-widest"
                   style={{ color: 'var(--au-text-muted)', fontFamily: 'var(--font-jost, Jost, sans-serif)' }}>
              Senha
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="w-full rounded-xl px-4 py-2.5 text-sm outline-none transition-all"
              style={{
                border:     '1px solid var(--au-border)',
                background: 'var(--au-bg)',
                color:      'var(--au-text)',
                fontFamily: 'var(--font-jost, Jost, sans-serif)',
              }}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="text-sm text-center rounded-lg py-2"
               style={{ color: '#B91C1C', background: '#FEF2F2', fontFamily: 'var(--font-jost, Jost, sans-serif)' }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl py-3 text-sm font-semibold text-white transition-opacity mt-1"
            style={{
              background: 'var(--au-primary)',
              opacity:    loading ? 0.7 : 1,
              cursor:     loading ? 'not-allowed' : 'pointer',
              fontFamily: 'var(--font-jost, Jost, sans-serif)',
              letterSpacing: '0.06em',
            }}
          >
            {loading ? 'Entrando…' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  )
}
