-- Esquema de base de datos para Shark Attack en Supabase (PostgreSQL)
-- Ejecutar en el SQL Editor del proyecto en Supabase.

-- 1. Perfiles de usuario (enlazados a Supabase Auth)
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  nombre text,
  -- Provincias elegidas en el filtro inicial (Región Pampeana). NULL = aún no completó el filtro.
  provincias text[],
  created_at timestamptz not null default now()
);

-- Migración idempotente para bases ya existentes
alter table public.profiles add column if not exists provincias text[];

alter table public.profiles enable row level security;

create policy "profiles_select_own"
  on public.profiles for select
  using (auth.uid() = id);

create policy "profiles_update_own"
  on public.profiles for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Trigger para crear automáticamente el perfil al registrarse en auth.users
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, nombre)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'nombre', '')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- 2. Campos / Lotes del usuario
create table if not exists public.fields (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  nombre text not null,
  lat double precision not null,
  lon double precision not null,
  hectareas double precision check (hectareas is null or hectareas > 0),
  polygon jsonb,
  created_at timestamptz not null default now()
);

alter table public.fields add column if not exists polygon jsonb;

create index if not exists idx_fields_user_id on public.fields (user_id);

alter table public.fields enable row level security;

create policy "fields_select_own"
  on public.fields for select
  using (auth.uid() = user_id);

create policy "fields_insert_own"
  on public.fields for insert
  with check (auth.uid() = user_id);

create policy "fields_update_own"
  on public.fields for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "fields_delete_own"
  on public.fields for delete
  using (auth.uid() = user_id);

-- 3. Campañas e historial de cultivos por campo
create table if not exists public.campaigns (
  id uuid primary key default gen_random_uuid(),
  field_id uuid not null references public.fields (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  campana text not null check (campana in ('invierno', 'verano')),
  cultivo text not null,
  fecha_inicio date not null,
  fecha_fin date,
  rinde_kg_ha double precision check (rinde_kg_ha is null or rinde_kg_ha >= 0),
  resultado_notas text,
  simulacion_json jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_campaigns_field_fecha
  on public.campaigns (field_id, fecha_inicio desc);

create index if not exists idx_campaigns_user_id
  on public.campaigns (user_id);

alter table public.campaigns enable row level security;

create policy "campaigns_select_own"
  on public.campaigns for select
  using (auth.uid() = user_id);

create policy "campaigns_insert_own"
  on public.campaigns for insert
  with check (
    auth.uid() = user_id
    and exists (
      select 1 from public.fields f
      where f.id = field_id and f.user_id = auth.uid()
    )
  );

create policy "campaigns_update_own"
  on public.campaigns for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "campaigns_delete_own"
  on public.campaigns for delete
  using (auth.uid() = user_id);
