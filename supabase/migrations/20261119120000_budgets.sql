-- Hábitos (Fase 12, ADR 0017): topes por categoría, ritmo de gasto para el colchón y la
-- preferencia de recibir contexto al anotar.

-- 1. Topes. Cuánto quieres gastar como máximo al mes en una categoría de gasto, en USD. Se
--    comparan con el snapshot en USD de cada gasto (ADR 0002): así el tope no se queda viejo
--    cada vez que sube el dólar. El mes es el calendario local del usuario.
create table budgets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  category_id uuid not null references categories (id),
  limit_usd numeric(20, 6) not null check (limit_usd > 0 and limit_usd < 1e12),
  -- El tope vigente que este reemplazó, para que Deshacer lo restaure.
  replaces_id uuid references budgets (id) on delete set null,
  raw_text text,
  created_at timestamptz not null default now(),
  archived_at timestamptz  -- reemplazado, quitado o deshecho; queda como historial
);
-- Un solo tope vigente por categoría.
create unique index budgets_one_active on budgets (user_id, category_id)
  where archived_at is null;
create index budgets_category_idx on budgets (category_id);
create index budgets_replaces_idx on budgets (replaces_id) where replaces_id is not null;

-- La categoría tiene que ser de gasto y global o del mismo usuario. El bot ya lo valida; esto
-- lo garantiza aunque alguien escriba directo en la tabla.
create function check_budget_category() returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if not exists (
    select 1 from public.categories c
    where c.id = new.category_id
      and c.kind = 'expense'
      and (c.user_id is null or c.user_id = new.user_id)
  ) then
    raise exception 'budget_category_invalid' using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger budgets_check_category
  before insert or update of category_id, user_id on budgets
  for each row execute function check_budget_category();

-- 2. Cuánto lleva gastado cada tope vigente en el mes local en curso. La usa la web; el bot
--    calcula lo mismo con sus propias consultas (gastos.services.budgets).
create view budget_progress with (security_invoker = true) as
select
  b.id as budget_id,
  b.user_id,
  b.category_id,
  c.name as category,
  b.limit_usd,
  coalesce(s.spent_usd, 0) as spent_usd,
  b.limit_usd - coalesce(s.spent_usd, 0) as remaining_usd,
  m.month_start::date as month_start
from budgets b
join categories c on c.id = b.category_id
join users u on u.id = b.user_id
cross join lateral (
  select date_trunc('month', now() at time zone u.timezone) as month_start
) m
left join lateral (
  select sum(t.amount_usd) as spent_usd
  from transactions t
  where t.user_id = b.user_id
    and t.category_id = b.category_id
    and t.kind = 'expense'
    and t.deleted_at is null
    and t.occurred_at >= (m.month_start at time zone u.timezone)
    and t.occurred_at < ((m.month_start + interval '1 month') at time zone u.timezone)
) s on true
where b.archived_at is null;

-- 3. Ritmo de gasto para el colchón: cuántos días de historial se usan (hasta p_days) y cuánto
--    se gastó en USD en esos días. El colchón es el saldo en USD entre el gasto diario; la
--    cuenta la hacen la web y el bot con la misma regla (gastos.domain.runway).
create function spending_pace(p_days integer default 90)
returns table (window_days integer, expenses_usd numeric)
language sql
stable
security invoker
set search_path = ''
as $$
  with me as (
    select coalesce(
      (select u.timezone from public.users u where u.id = (select public.app_user_id())),
      'America/Caracas'
    ) as tz
  ),
  bounds as (
    select (now() at time zone me.tz)::date as today,
           (select (min(t.occurred_at) at time zone me.tz)::date
            from public.transactions t where t.deleted_at is null) as first_day
    from me
  ),
  win as (
    -- Sin movimientos no hay ritmo (least() ignoraría el null y daría la ventana entera).
    select today,
           case when first_day is null then null
                else least(today - first_day + 1, least(greatest(coalesce(p_days, 90), 1), 365))
           end as days
    from bounds
  )
  select win.days::integer,
         case when win.days is null then null else coalesce((
           select sum(t.amount_usd) from public.transactions t
           where t.deleted_at is null
             and t.kind = 'expense'
             and t.occurred_at >= public.local_day_start(win.today - win.days + 1)
             and t.occurred_at < public.local_day_start(win.today + 1)
         ), 0) end
  from win
$$;

-- 4. Contexto al anotar («comida: llevas 80 de 100 este mes»). Se apaga con /contexto.
alter table users add column context_replies boolean not null default true;

-- 5. Acceso de la web (ADR 0012): solo lectura de lo propio; el bot escribe como dueño.
alter table budgets enable row level security;
create policy budgets_select_own on budgets for select to authenticated
  using (user_id = (select app_user_id()));
grant select on budgets, budget_progress to authenticated;

revoke execute on function spending_pace(integer) from public, anon;
grant execute on function spending_pace(integer) to authenticated;
