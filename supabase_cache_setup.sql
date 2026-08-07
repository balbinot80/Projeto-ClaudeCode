-- ============================================================
-- Cache Supabase para dados da API Jueri — Streamlit App
-- Execute no SQL Editor do Supabase:
-- https://supabase.com/dashboard → projeto → SQL Editor
-- ============================================================

-- Tabela 1: listas (pedidos, produtos, revendedores, categorias)
CREATE TABLE IF NOT EXISTS public.cache_jueri (
  chave        TEXT PRIMARY KEY,
  dados        JSONB NOT NULL DEFAULT '[]'::jsonb,
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tabela 2: detalhes de pedidos individuais (itens, etc)
CREATE TABLE IF NOT EXISTS public.cache_pedidos_detalhes (
  pedido_id    INTEGER PRIMARY KEY,
  dados        JSONB NOT NULL DEFAULT '{}'::jsonb,
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Desabilitar RLS (o app usa a service key, sem login de usuário)
ALTER TABLE public.cache_jueri DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.cache_pedidos_detalhes DISABLE ROW LEVEL SECURITY;

-- Índices para buscas rápidas por data (útil para limpeza futura)
CREATE INDEX IF NOT EXISTS idx_cache_pedidos_detalhes_atualizado
  ON public.cache_pedidos_detalhes(atualizado_em);

-- ============================================================
-- Verificar se foi criado corretamente:
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('cache_jueri', 'cache_pedidos_detalhes');
-- ============================================================
