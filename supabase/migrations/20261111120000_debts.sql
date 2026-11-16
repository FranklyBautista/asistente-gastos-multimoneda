-- Deudas (Fase 11): lo que debes y lo que te deben, como un libro aparte de los saldos.
-- Registrar o liquidar una deuda no mueve dinero por sí solo; lo mueve el movimiento que se
-- enlaza al pago (debt_payments.transaction_id), que llegará con la liquidación desde el bot.

-- 1. Deudas. Se quedan en su moneda original; el snapshot guarda su valor en USD al
--    registrarlas, igual que los movimientos (ADR 0002).
create table debts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  direction text not null check (direction in ('i_owe', 'owed_to_me')),
  counterparty text not null check (length(btrim(counterparty)) between 1 and 80),
  -- Para buscar: «Miguel», «miguel» y «Míguel  » son la misma persona. Se calcula aquí para
  -- que el bot y la web no puedan normalizar distinto.
  counterparty_key text generated always as (
    regexp_replace(
      lower(translate(btrim(counterparty), 'ÁÀÄÂÉÈËÊÍÌÏÎÓÒÖÔÚÙÜÛÑáàäâéèëêíìïîóòöôúùüûñ',
                                           'AAAAEEEEIIIIOOOOUUUUNaaaaeeeeiiiioooouuuun')),
      '\s+', ' ', 'g')
  ) stored,
  currency text not null check (currency in ('VES', 'COP', 'USD', 'USDT')),
  amount numeric(20, 6) not null check (amount > 0),
  category_id uuid references categories (id),
  description text,
  incurred_at timestamptz not null default now(),
  usd_per_unit numeric(20, 10) not null check (usd_per_unit > 0),  -- snapshot de la tasa
  rate_source text not null
    check (rate_source in ('bcv', 'parallel', 'p2p', 'fx', 'coingecko', 'pivot')),
  amount_usd numeric(20, 6) not null,  -- amount * usd_per_unit
  raw_text text,
  cancelled_at timestamptz,            -- anulada por error (no por pagarla: esa se liquida)
  created_at timestamptz not null default now(),
  unique (id, user_id, currency)       -- habilita la FK compuesta de debt_payments
);
-- Buscar por contraparte («le pagué a Miguel») y borrar en cascada desde users.
create index debts_user_counterparty_idx on debts (user_id, counterparty_key);
-- Lo último que anotó el usuario, para Deshacer (como transactions y exchanges).
create index debts_user_created_idx on debts (user_id, created_at desc);

-- 2. Pagos. Siempre en la moneda de la deuda y del mismo dueño: lo garantiza la FK compuesta.
create table debt_payments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  debt_id uuid not null,
  currency text not null,
  amount numeric(20, 6) not null check (amount > 0),
  -- Gasto o ingreso que movió el dinero; null = se pagó por otra vía («Sin movimiento»).
  transaction_id uuid references transactions (id) on delete set null,
  paid_at timestamptz not null default now(),
  raw_text text,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  foreign key (debt_id, user_id, currency)
    references debts (id, user_id, currency) on delete cascade
);
create index debt_payments_debt_idx on debt_payments (debt_id) where deleted_at is null;
create index debt_payments_user_created_idx on debt_payments (user_id, created_at desc);
create index debt_payments_transaction_idx on debt_payments (transaction_id)
  where transaction_id is not null;
-- Un movimiento paga como mucho una deuda.
create unique index debt_payments_transaction_once on debt_payments (transaction_id)
  where transaction_id is not null and deleted_at is null;

-- 3. Un pago nunca supera lo pendiente ni cae en una deuda anulada. El bot pregunta antes,
--    pero esto lo garantiza aunque dos pagos lleguen a la vez: se bloquea la deuda y se
--    suman los pagos vigentes con ella bloqueada.
create function check_debt_payment() returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_debt public.debts%rowtype;
  v_paid numeric;
begin
  if new.deleted_at is not null then
    return new;  -- deshacer un pago siempre se puede
  end if;

  select * into v_debt from public.debts
  where id = new.debt_id and user_id = new.user_id and currency = new.currency
  for update;
  if not found then
    return new;  -- otra moneda u otro dueño: lo rechaza la FK compuesta con su propio error
  end if;
  if v_debt.cancelled_at is not null then
    raise exception 'debt_cancelled' using errcode = 'P0001';
  end if;

  select coalesce(sum(p.amount), 0) into v_paid
  from public.debt_payments p
  where p.debt_id = new.debt_id and p.deleted_at is null and p.id <> new.id;

  if v_paid + new.amount > v_debt.amount then
    raise exception 'payment_exceeds_remaining'
      using errcode = 'P0001',
            detail = format('pendiente %s, pago %s', v_debt.amount - v_paid, new.amount);
  end if;
  return new;
end;
$$;

create trigger debt_payments_check
  before insert or update of amount, debt_id, deleted_at on debt_payments
  for each row execute function check_debt_payment();

-- 4. Pendiente y estado calculados, nunca guardados (como los saldos). Sin las anuladas.
create view debt_balances with (security_invoker = true) as
select
  s.*,
  case when s.remaining <= 0 then 'settled'
       when s.remaining < s.amount then 'partial'
       else 'open' end as status
from (
  select
    d.id as debt_id,
    d.user_id,
    d.direction,
    d.counterparty,
    d.counterparty_key,
    d.currency,
    d.amount,
    d.amount - coalesce(p.paid, 0) as remaining,
    d.amount_usd,
    d.category_id,
    d.description,
    d.incurred_at,
    p.last_paid_at
  from debts d
  left join lateral (
    select sum(x.amount) as paid, max(x.paid_at) as last_paid_at
    from debt_payments x
    where x.debt_id = d.id and x.deleted_at is null
  ) p on true
  where d.cancelled_at is null
) s;

-- 5. Acceso de la web (ADR 0012): solo lectura de lo propio; el bot escribe como dueño.
alter table debts enable row level security;
alter table debt_payments enable row level security;

create policy debts_select_own on debts for select to authenticated
  using (user_id = (select app_user_id()));
create policy debt_payments_select_own on debt_payments for select to authenticated
  using (user_id = (select app_user_id()));

grant select on debts, debt_payments, debt_balances to authenticated;
