-- Execute no SQL Editor do Supabase
-- Tabela de cache dos pedidos Jueri — atualizada pelo job de sincronização

create table if not exists pedidos_cache (
  id                      bigint primary key,
  codigo_pedido           text,
  status                  text,
  fk_revendedor_id        bigint,
  supervisor_nome         text,
  data_acerto             date,
  data_baixa              date,
  data_criacao            date,
  valor_total             numeric(12,2),
  valor_pre_baixa         numeric(12,2),
  valor_total_antes_baixa numeric(12,2),
  comprador_nome          text,
  synced_at               timestamptz default now()
);

-- Dados não sensíveis — leitura livre para usuários autenticados
alter table pedidos_cache enable row level security;

create policy "leitura autenticada"
  on pedidos_cache for select
  using (auth.role() = 'authenticated');

create policy "escrita pelo sync"
  on pedidos_cache for all
  using (true) with check (true);

-- Índices para as consultas mais comuns
create index if not exists idx_pedidos_status        on pedidos_cache (status);
create index if not exists idx_pedidos_data_baixa    on pedidos_cache (data_baixa);
create index if not exists idx_pedidos_data_acerto   on pedidos_cache (data_acerto);
create index if not exists idx_pedidos_revendedor    on pedidos_cache (fk_revendedor_id);

-- Tabela de controle do sync (guarda timestamp da última execução)
create table if not exists sync_log (
  id         serial primary key,
  tabela     text not null,
  total_rows integer,
  synced_at  timestamptz default now()
);
