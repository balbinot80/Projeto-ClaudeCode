-- Execute no SQL Editor do Supabase (https://supabase.com/dashboard)

create table if not exists cards (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade not null,
  title       text not null,
  description text,
  status      text not null default 'backlog'
              check (status in ('backlog','testing','routine','cancelled')),
  priority    text not null default 'medium'
              check (priority in ('low','medium','high')),
  position    integer not null default 0,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- Apenas o próprio usuário vê seus cards
alter table cards enable row level security;

create policy "users see own cards"  on cards for select using (auth.uid() = user_id);
create policy "users insert own"     on cards for insert with check (auth.uid() = user_id);
create policy "users update own"     on cards for update using (auth.uid() = user_id);
create policy "users delete own"     on cards for delete using (auth.uid() = user_id);
