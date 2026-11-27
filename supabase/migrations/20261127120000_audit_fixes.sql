-- Auditoría del 2026-11-27.
--
-- 1. edit_transaction: un monto de 1e14 o más ahora responde 'invalid_amount' en vez de
--    'numeric field overflow'. El resto de la función es igual a 20261123120000_edit_debt_linked;
--    create or replace conserva los permisos (solo authenticated puede ejecutarla).
-- 2. period_totals: ingresos y gastos en USD entre dos días locales, sumados en la base. La web
--    y la app sumaban los ingresos leyendo list_transactions de 100 en 100 con un tope de 2.000,
--    así que el total desde el primer movimiento se cortaba sin avisar.

create or replace function edit_transaction(
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
  -- Sin typmod: con numeric(20, 6) un monto de 1e14 o más desbordaba aquí (22003), antes
  -- de la validación de abajo, y la app mostraba un error genérico en vez de invalid_amount.
  v_amount numeric := round(p_amount, 6);
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

  -- Un pago de deuda vigente no se edita: debt_balances seguiría contando el pago original
  -- y la deuda quedaría descuadrada. El bot ya lo protege con Deshacer (last_batch).
  if exists (
    select 1 from public.debt_payments p
    where p.transaction_id = v_tx.id and p.deleted_at is null
  ) then
    raise exception 'debt_linked' using errcode = '22023';
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

-- Mismo criterio que spending_by_category: snapshot en USD de cada movimiento (ADR 0002),
-- sin borrados, días locales del usuario con [p_from, p_to] incluidos.
create function period_totals(p_from date, p_to date)
returns table (income_usd numeric, expenses_usd numeric)
language sql
stable
security invoker
set search_path = ''
as $$
  select coalesce(sum(t.amount_usd) filter (where t.kind = 'income'), 0),
         coalesce(sum(t.amount_usd) filter (where t.kind = 'expense'), 0)
  from public.transactions t
  where t.deleted_at is null
    and t.occurred_at >= public.local_day_start(p_from)
    and t.occurred_at < public.local_day_start(p_to + 1)
$$;
revoke execute on function period_totals(date, date) from public, anon;
grant execute on function period_totals(date, date) to authenticated;