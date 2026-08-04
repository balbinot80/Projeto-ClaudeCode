import type { Metadata } from 'next'
import { Cormorant_Garamond, Jost } from 'next/font/google'
import './globals.css'

const cormorant = Cormorant_Garamond({
  subsets: ['latin'],
  weight: ['400', '600'],
  style: ['normal', 'italic'],
  variable: '--font-cormorant',
})

const jost = Jost({
  subsets: ['latin'],
  weight: ['300', '400', '600'],
  variable: '--font-jost',
})

export const metadata: Metadata = {
  title: 'Aureum — Gestão',
  description: 'Sistema de gestão de projetos Aureum Joias',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className="h-full">
      <body className={`${cormorant.variable} ${jost.variable} h-full`}>{children}</body>
    </html>
  )
}
