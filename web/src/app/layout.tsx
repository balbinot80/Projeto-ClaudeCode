import type { Metadata } from 'next'
import { Playfair_Display, Jost } from 'next/font/google'
import './globals.css'

const playfair = Playfair_Display({
  subsets: ['latin'],
  weight: ['400', '600', '700'],
  style: ['normal'],
  variable: '--font-display',
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
      <body className={`${playfair.variable} ${jost.variable} h-full`}>{children}</body>
    </html>
  )
}
