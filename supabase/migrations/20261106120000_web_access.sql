-- Acceso de la web (Fase 9, ADR 0012).
-- La web entra con la anon key y la sesión de Supabase Auth: lee solo lo suyo por RLS y no
-- escribe tablas directamente (las escrituras pasan por funciones). El bot sigue entrando
-- como dueño de las tablas y se salta la RLS.

-- 1. Cuenta web vinculada a cada usuario del bot.
alter table users
  add column auth_user_id uuid unique references auth.users(id) on delete set null;

-- 2. Códigos de un solo uso que genera /vincular y canjea la web.
create table link_codes (
  code text primary key check (code ~ '^[A-HJ-NP-Z2-9]{8}$'),
  user_id uuid not null references users(id) on delete cascade,
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);
create index link_codes_user_id_idx on link_codes (user_id);
alter table link_codes enable row level security;

-- 3. Permisos: nada para anon; solo lectura para authenticated en lo que muestra la web.
--    Sin esto, Supabase concede todo a ambos roles y la RLS sería la única barrera.
revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke execute on all functions in schema public from public, anon, authenticated;
alter default privileges in schema public revoke all on tables from anon, authenticated;
alter default privileges in schema public revoke all on sequences from anon, authenticated;
alter default privileges in schema public revoke execute on functions from public, anon, authenticated;
-- PUBLIC recibe EXECUTE en toda función nueva por un default global que el anterior (por
-- esquema) no quita; cada función expuesta se revoca y concede explícitamente más abajo.
alter default privileges revoke execute on functions from public;

grant select on users, accounts, categories, transactions, exchanges, exchange_rates,
  corrections, account_balances to authenticated;

-- 4. Usuario del bot que corresponde a la sesión. security definer: lee users sin pasar por
--    su RLS, así las políticas no se consultan unas a otras.
create function app_user_id() returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select id from public.users where auth_user_id = (select auth.uid())
$$;
revoke execute on function app_user_id() from public, anon;
grant execute on function app_user_id() to authenticated;

-- 5. Políticas de lectura por dueño.
create policy users_select_own on users for select to authenticated
  using (auth_user_id = (select auth.uid()));
create policy accounts_select_own on accounts for select to authenticated
  using (user_id = (select app_user_id()));
create policy categories_select_own on categories for select to authenticated
  using (user_id is null or user_id = (select app_user_id()));
create policy transactions_select_own on transactions for select to authenticated
  using (user_id = (select app_user_id()));
create policy exchanges_select_own on exchanges for select to authenticated
  using (user_id = (select app_user_id()));
create policy corrections_select_own on corrections for select to authenticated
  using (user_id = (select app_user_id()));
-- Las tasas son datos públicos de mercado: cualquier sesión las lee.
create policy exchange_rates_select_all on exchange_rates for select to authenticated
  using (true);

-- 6. Canje del código. Valida vencimiento, uso y que ninguna de las dos cuentas esté ya
--    vinculada a otra; bloquea la fila para que dos canjes simultáneos no ganen ambos.
create function redeem_link_code(p_code text) returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_auth uuid := (select auth.uid());
  v_link public.link_codes%rowtype;
  v_user public.users%rowtype;
begin
  if v_auth is null then
    raise exception 'not_authenticated' using errcode = '28000';
  end if;

  select * into v_link from public.link_codes
  where code = upper(trim(p_code))
  for update;
  if not found or v_link.used_at is not null or v_link.expires_at <= now() then
    raise exception 'invalid_code' using errcode = 'P0001';
  end if;

  select * into v_user from public.users where id = v_link.user_id for update;
  if v_user.auth_user_id is not null and v_user.auth_user_id <> v_auth then
    raise exception 'telegram_already_linked' using errcode = 'P0001';
  end if;
  if exists (select 1 from public.users where auth_user_id = v_auth and id <> v_user.id) then
    raise exception 'web_already_linked' using errcode = 'P0001';
  end if;

  update public.users set auth_user_id = v_auth where id = v_user.id;
  update public.link_codes set used_at = now() where code = v_link.code;
  return coalesce(v_user.display_name, '');
end;
$$;
revoke execute on function redeem_link_code(text) from public, anon;
grant execute on function redeem_link_code(text) to authenticated;
