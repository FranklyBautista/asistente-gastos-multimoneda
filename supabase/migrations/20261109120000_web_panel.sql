-- Panel web (Fase 10, ADR 0014): saldos con consolidado en USD, lista de movimientos con
-- filtros, edición desde la web, gráficas e historial de cambios.
-- Las lecturas son vistas y funciones `security invoker`: pasan por la RLS de la sesión
-- (ADR 0012). La única escritura, editar un movimiento, es `security definer` y valida dueño.

-- 1. Tasa vigente de cada moneda y fuente. Una subconsulta por par usa el índice
--    (currency, source, fetched_at desc) en vez de recorrer todo el historial.
create view latest_rates with (security_invoker = true) as
select r.currency, r.source, r.usd_per_unit, r.fetched_at
from (values ('VES', 'bcv'), ('VES', 'parallel'), ('VES', 'p2p'), ('COP', 'fx'),
             ('USDT', 'coingecko')) as b (currency, source)
cross join lateral (
  select e.currency, e.source, e.usd_per_unit, e.fetched_at
  from exchange_rates e
  where e.currency = b.currency and e.source = b.source
  order by e.fetched_at desc
  limit 1
) r;

-- 2. Saldos con su equivalente en USD a la tasa vigente de la fuente del usuario (la del
--    bolívar es su preferencia; ver gastos.domain.currency.rate_source_for). USD es el
--    pivote. `stale` usa las mismas 6 horas que el bot (RATES_MAX_AGE_HOURS).
create view account_balances_usd with (security_invoker = true) as
select
  b.account_id,
  b.name,
  b.currency,
  b.balance,
  case when b.currency = 'USD' then 'pivot' else r.source end as rate_source,
  case when b.currency = 'USD' then 1::numeric else r.usd_per_unit end as usd_per_unit,
  r.fetched_at as rate_fetched_at,
  coalesce(r.fetched_at < now() - interval '6 hours', false) as rate_stale,
  round(b.balance * case when b.currency = 'USD' then 1 else r.usd_per_unit end, 6)
    as balance_usd
from account_balances b
join accounts a on a.id = b.account_id and not a.archived  -- igual que el bot (reports.py)
join users u on u.id = b.user_id
left join latest_rates r
  on b.currency <> 'USD'
  and r.currency = b.currency
  and r.source = case b.currency when 'VES' then u.ves_rate_source
                                 when 'COP' then 'fx'
                                 else 'coingecko' end;

-- 3. Historial de cambios con la diferencia contra la tasa de referencia, en la misma
--    dirección que la guarda el bot (gastos.domain.exchange.difference_pct).
create view exchange_history with (security_invoker = true) as
select
  e.id,
  e.occurred_at,
  e.from_amount,
  fa.currency as from_currency,
  fa.name as from_account,
  e.to_amount,
  ta.currency as to_currency,
  ta.name as to_account,
  e.effective_rate,
  e.reference_rate,
  round((e.effective_rate / nullif(e.reference_rate, 0) - 1) * 100, 2) as difference_pct
from exchanges e
join accounts fa on fa.id = e.from_account_id
join accounts ta on ta.id = e.to_account_id
where e.deleted_at is null;
create index if not exists exchanges_user_occurred_idx
  on exchanges (user_id, occurred_at desc) where deleted_at is null;

grant select on latest_rates, account_balances_usd, exchange_history to authenticated;

-- 4. Inicio de un día del usuario en UTC, con su zona horaria. Las fechas que elige la web
--    son días locales, igual que los periodos del bot (gastos.domain.periods).
create function local_day_start(p_day date) returns timestamptz
language sql
stable
security invoker
set search_path = ''
as $$
  select p_day::timestamp at time zone coalesce(
    (select u.timezone from public.users u where u.id = (select public.app_user_id())),
    'America/Caracas'
  )
$$;

-- 5. Movimientos con filtros y paginación. `total` es el total filtrado, para paginar.
create function list_transactions(
  p_currency text default null,
  p_category_id uuid default null,
  p_kind text default null,
  p_from date default null,
  p_to date default null,
  p_limit integer default 25,
  p_offset integer default 0
) returns table (
  id uuid,
  occurred_at timestamptz,
  kind text,
  amount numeric,
  currency text,
  account_id uuid,
  account_name text,
  category_id uuid,
  category_name text,
  description text,
  amount_usd numeric,
  rate_source text,
  edited boolean,
  total bigint
)
language sql
stable
security invoker
set search_path = ''
as $$
  select t.id, t.occurred_at, t.kind, t.amount, t.currency, a.id, a.name, c.id, c.name,
         t.description, t.amount_usd, t.rate_source,
         exists (select 1 from public.corrections k where k.transaction_id = t.id),
         count(*) over ()
  from public.transactions t
  join public.accounts a on a.id = t.account_id
  left join public.categories c on c.id = t.category_id
  where t.deleted_at is null
    and (p_currency is null or t.currency = p_currency)
    and (p_category_id is null or t.category_id = p_category_id)
    and (p_kind is null or t.kind = p_kind)
    and (p_from is null or t.occurred_at >= public.local_day_start(p_from))
    and (p_to is null or t.occurred_at < public.local_day_start(p_to + 1))
  order by t.occurred_at desc, t.id
  limit least(greatest(coalesce(p_limit, 25), 1), 100)
  offset greatest(coalesce(p_offset, 0), 0)
$$;

-- 6. Gráficas. Los montos se suman con el snapshot en USD de cada movimiento (ADR 0002):
--    es lo único comparable entre monedas.
create function spending_by_category(p_from date, p_to date)
returns table (category text, total_usd numeric, movements bigint)
language sql
stable
security invoker
set search_path = ''
as $$
  select coalesce(c.name, 'sin categoría'), sum(t.amount_usd), count(*)
  from public.transactions t
  left join public.categories c on c.id = t.category_id
  where t.deleted_at is null
    and t.kind = 'expense'
    and t.occurred_at >= public.local_day_start(p_from)
    and t.occurred_at < public.local_day_start(p_to + 1)
  group by 1
  order by 2 desc
$$;

-- Semanas de lunes a domingo en la zona del usuario; las semanas sin gastos salen en 0.
create function spending_by_week(p_weeks integer default 12)
returns table (week_start date, expenses_usd numeric, income_usd numeric)
language sql
stable
security invoker
set search_path = ''
as $$
  with tz as (
    select coalesce(
      (select u.timezone from public.users u where u.id = (select public.app_user_id())),
      'America/Caracas'
    ) as name
  ),
  weeks as (
    select (date_trunc('week', (now() at time zone tz.name)) - make_interval(weeks => g))::date
      as week_start
    from tz, generate_series(0, least(greatest(coalesce(p_weeks, 12), 1), 52) - 1) g
  )
  select w.week_start,
         coalesce(sum(t.amount_usd) filter (where t.kind = 'expense'), 0),
         coalesce(sum(t.amount_usd) filter (where t.kind = 'income'), 0)
  from weeks w
  left join public.transactions t
    on t.deleted_at is null
    and t.occurred_at >= public.local_day_start(w.week_start)
    and t.occurred_at < public.local_day_start(w.week_start + 7)
  group by w.week_start
  order by w.week_start
$$;

-- Poder adquisitivo del bolívar: la última tasa de cada día con la fuente del usuario.
create function bolivar_rates(p_days integer default 90)
returns table (day date, source text, usd_per_unit numeric)
language sql
stable
security invoker
set search_path = ''
as $$
  with me as (
    select coalesce(u.timezone, 'America/Caracas') as tz, coalesce(u.ves_rate_source, 'parallel') as source
    from (select 1) one
    left join public.users u on u.id = (select public.app_user_id())
  )
  select distinct on (day) (e.fetched_at at time zone me.tz)::date as day, e.source, e.usd_per_unit
  from me
  join public.exchange_rates e on e.currency = 'VES' and e.source = me.source
  where e.fetched_at >= now() - make_interval(days => least(greatest(coalesce(p_days, 90), 1), 365))
  order by day, e.fetched_at desc
$$;

-- 7. Editar un movimiento desde la web. Recalcula el snapshot como el bot
--    (gastos.services.corrections): misma moneda → misma tasa con el monto nuevo; otra
--    moneda → la tasa del usuario vigente cuando se anotó (o la primera posterior). Cada
--    campo cambiado queda en `corrections`, así la web también le enseña al bot (ADR 0009).
--    Devuelve cuántos campos cambiaron (0 = ya estaba así).
create function edit_transaction(
  p_id uuid,
  p_kind text,
  p_amount numeric,
  p_account_id uuid,
  p_category_id uuid
) returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid := (select public.app_user_id());
  v_ves_source text;
  v_tx public.transactions%rowtype;
  v_old_account public.accounts%rowtype;
  v_account public.accounts%rowtype;
  v_old_category text;
  v_category public.categories%rowtype;
  v_amount numeric(20, 6) := round(p_amount, 6);
  v_source text;
  v_rate numeric;
  v_rate_source text;
  v_changes integer := 0;
begin
  if v_user is null then
    raise exception 'not_linked' using errcode = '28000';
  end if;
  if p_kind is null or p_kind not in ('expense', 'income') then
    raise exception 'invalid_kind' using errcode = '22023';
  end if;
  if v_amount is null or v_amount <= 0 or v_amount >= 1e14 then
    raise exception 'invalid_amount' using errcode = '22023';
  end if;

  select * into v_tx from public.transactions
  where id = p_id and user_id = v_user and deleted_at is null
  for update;
  if not found then
    raise exception 'transaction_not_found' using errcode = 'P0002';
  end if;

  select * into v_account from public.accounts
  where id = p_account_id and user_id = v_user and not archived;
  if not found then
    raise exception 'account_not_found' using errcode = 'P0002';
  end if;
  select * into v_category from public.categories
  where id = p_category_id and (user_id is null or user_id = v_user);
  if not found or v_category.kind <> p_kind then
    raise exception 'category_mismatch' using errcode = '22023';
  end if;

  select * into v_old_account from public.accounts where id = v_tx.account_id;
  select name into v_old_category from public.categories where id = v_tx.category_id;

  -- Snapshot nuevo.
  if v_account.currency = v_tx.currency then
    v_rate := v_tx.usd_per_unit;
    v_rate_source := v_tx.rate_source;
  elsif v_account.currency = 'USD' then
    v_rate := 1;
    v_rate_source := 'pivot';
  else
    select ves_rate_source into v_ves_source from public.users where id = v_user;
    v_source := case v_account.currency when 'VES' then v_ves_source
                                        when 'COP' then 'fx'
                                        else 'coingecko' end;
    select r.usd_per_unit, r.source into v_rate, v_rate_source from (
      (select e.usd_per_unit, e.source, 0 as pref from public.exchange_rates e
       where e.currency = v_account.currency and e.source = v_source
         and e.fetched_at <= v_tx.created_at
       order by e.fetched_at desc limit 1)
      union all
      (select e.usd_per_unit, e.source, 1 as pref from public.exchange_rates e
       where e.currency = v_account.currency and e.source = v_source
         and e.fetched_at > v_tx.created_at
       order by e.fetched_at limit 1)
    ) r order by r.pref limit 1;
    if v_rate is null then
      raise exception 'rate_unavailable' using errcode = 'P0002';
    end if;
  end if;

  -- Un registro por campo cambiado, con los valores como los usa el prompt de extracción.
  if p_kind <> v_tx.kind then
    insert into public.corrections (user_id, transaction_id, raw_text, field, old_value, new_value)
    values (v_user, v_tx.id, 'edición en la web', 'kind', v_tx.kind, p_kind);
    v_changes := v_changes + 1;
  end if;
  if v_account.currency <> v_tx.currency then
    insert into public.corrections (user_id, transaction_id, raw_text, field, old_value, new_value)
    values (v_user, v_tx.id, 'edición en la web', 'currency', v_tx.currency, v_account.currency);
    v_changes := v_changes + 1;
  elsif v_account.id <> v_tx.account_id then
    insert into public.corrections (user_id, transaction_id, raw_text, field, old_value, new_value)
    values (v_user, v_tx.id, 'edición en la web', 'account', v_old_account.name, v_account.name);
    v_changes := v_changes + 1;
  end if;
  if v_amount <> v_tx.amount then
    insert into public.corrections (user_id, transaction_id, raw_text, field, old_value, new_value)
    values (v_user, v_tx.id, 'edición en la web', 'amount',
            trim_scale(v_tx.amount)::text, trim_scale(v_amount)::text);
    v_changes := v_changes + 1;
  end if;
  if v_tx.category_id is distinct from v_category.id then
    insert into public.corrections (user_id, transaction_id, raw_text, field, old_value, new_value)
    values (v_user, v_tx.id, 'edición en la web', 'category', v_old_category, v_category.name);
    v_changes := v_changes + 1;
  end if;

  if v_changes = 0 then
    return 0;
  end if;

  update public.transactions set
    kind = p_kind,
    amount = v_amount,
    account_id = v_account.id,
    currency = v_account.currency,
    category_id = v_category.id,
    usd_per_unit = v_rate,
    rate_source = v_rate_source,
    amount_usd = round(v_amount * v_rate, 6)
  where id = v_tx.id;
  return v_changes;
end;
$$;

-- 8. Permisos: solo sesiones iniciadas; anon no ejecuta nada (ADR 0012).
revoke execute on function local_day_start(date), list_transactions(text, uuid, text, date, date, integer, integer),
  spending_by_category(date, date), spending_by_week(integer), bolivar_rates(integer),
  edit_transaction(uuid, text, numeric, uuid, uuid)
  from public, anon;
grant execute on function local_day_start(date), list_transactions(text, uuid, text, date, date, integer, integer),
  spending_by_category(date, date), spending_by_week(integer), bolivar_rates(integer),
  edit_transaction(uuid, text, numeric, uuid, uuid)
  to authenticated;
