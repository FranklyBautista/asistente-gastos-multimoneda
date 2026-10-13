-- Esquema inicial: usuarios, cuentas, categorías, movimientos, cambios, tasas y correcciones.
-- Reglas de monedas en docs/decisions/0002-monedas.md.

create table users (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint unique not null,
  display_name text,
  timezone text not null default 'America/Caracas',
  default_currency text not null default 'USD'
    check (default_currency in ('VES', 'COP', 'USD', 'USDT')),
  ves_rate_source text not null default 'parallel'
    check (ves_rate_source in ('bcv', 'parallel', 'p2p')),
  created_at timestamptz not null default now()
);

create table accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  name text not null,
  currency text not null check (currency in ('VES', 'COP', 'USD', 'USDT')),
  kind text not null check (kind in ('cash', 'bank', 'exchange', 'wallet')),
  opening_balance numeric(20, 6) not null default 0,
  archived boolean not null default false,
  unique (user_id, name),
  unique (id, user_id),           -- habilita las FK compuestas de exchanges
  unique (id, user_id, currency)  -- habilita la FK compuesta de transactions
);

create table categories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users (id) on delete cascade,  -- null = categoría global
  name text not null,
  kind text not null check (kind in ('expense', 'income')),
  unique nulls not distinct (user_id, name, kind)
);

create table transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  account_id uuid not null,
  currency text not null,
  kind text not null check (kind in ('expense', 'income')),
  amount numeric(20, 6) not null check (amount > 0),
  category_id uuid references categories (id),
  description text,
  occurred_at timestamptz not null default now(),
  usd_per_unit numeric(20, 10) not null check (usd_per_unit > 0),  -- snapshot de la tasa
  rate_source text not null
    check (rate_source in ('bcv', 'parallel', 'p2p', 'fx', 'coingecko', 'pivot')),
  amount_usd numeric(20, 6) not null,  -- amount * usd_per_unit
  raw_text text,
  parse_confidence numeric(3, 2) check (parse_confidence between 0 and 1),
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  -- la moneda y el dueño deben coincidir con los de la cuenta
  foreign key (account_id, user_id, currency) references accounts (id, user_id, currency)
);
create index on transactions (user_id, occurred_at desc) where deleted_at is null;
create index on transactions (account_id) where deleted_at is null;

create table exchanges (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  from_account_id uuid not null,
  to_account_id uuid not null,
  from_amount numeric(20, 6) not null check (from_amount > 0),
  to_amount numeric(20, 6) not null check (to_amount > 0),
  effective_rate numeric(20, 10) not null,  -- to_amount / from_amount
  reference_rate numeric(20, 10),           -- tasa de referencia del momento, misma dirección
  occurred_at timestamptz not null default now(),
  raw_text text,
  deleted_at timestamptz,
  check (from_account_id <> to_account_id),
  -- ambas cuentas deben ser del mismo dueño que el cambio
  foreign key (from_account_id, user_id) references accounts (id, user_id),
  foreign key (to_account_id, user_id) references accounts (id, user_id)
);
create index on exchanges (from_account_id) where deleted_at is null;
create index on exchanges (to_account_id) where deleted_at is null;

create table exchange_rates (
  id bigint generated always as identity primary key,
  currency text not null check (currency in ('VES', 'COP', 'USDT')),  -- USD es el pivote
  source text not null check (source in ('bcv', 'parallel', 'p2p', 'fx', 'coingecko')),
  usd_per_unit numeric(20, 10) not null check (usd_per_unit > 0),
  fetched_at timestamptz not null default now()
);
create index on exchange_rates (currency, source, fetched_at desc);

create table corrections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  transaction_id uuid references transactions (id) on delete set null,
  raw_text text not null,
  field text not null check (field in ('category', 'currency', 'amount', 'kind', 'account')),
  old_value text,
  new_value text not null,
  created_at timestamptz not null default now()
);

-- Saldos calculados desde los movimientos: nunca se guardan (ADR 0002).
create view account_balances with (security_invoker = true) as
select
  a.id as account_id,
  a.user_id,
  a.name,
  a.currency,
  a.opening_balance
  + coalesce((select sum(case t.kind when 'income' then t.amount else -t.amount end)
              from transactions t
              where t.account_id = a.id and t.deleted_at is null), 0)
  + coalesce((select sum(e.to_amount) from exchanges e
              where e.to_account_id = a.id and e.deleted_at is null), 0)
  - coalesce((select sum(e.from_amount) from exchanges e
              where e.from_account_id = a.id and e.deleted_at is null), 0)
  as balance
from accounts a;

-- Categorías globales: van en la migración (no en seed.sql) para que existan también en la nube.
insert into categories (user_id, name, kind) values
  (null, 'comida', 'expense'),
  (null, 'transporte', 'expense'),
  (null, 'servicios', 'expense'),
  (null, 'ocio', 'expense'),
  (null, 'salud', 'expense'),
  (null, 'otros', 'expense'),
  (null, 'salario', 'income'),
  (null, 'otros ingresos', 'income');

-- Cada usuario nuevo arranca con una cuenta por moneda.
create function create_default_accounts() returns trigger
language plpgsql
set search_path = public
as $$
begin
  insert into accounts (user_id, name, currency, kind) values
    (new.id, 'efectivo Bs', 'VES', 'cash'),
    (new.id, 'efectivo COP', 'COP', 'cash'),
    (new.id, 'efectivo USD', 'USD', 'cash'),
    (new.id, 'wallet USDT', 'USDT', 'wallet');
  return new;
end;
$$;

create trigger users_default_accounts
after insert on users
for each row execute function create_default_accounts();

-- RLS activada sin políticas: la API pública no ve nada hasta la Fase 9.
-- El bot usa credenciales de servicio y filtra siempre por user_id.
alter table users enable row level security;
alter table accounts enable row level security;
alter table categories enable row level security;
alter table transactions enable row level security;
alter table exchanges enable row level security;
alter table exchange_rates enable row level security;
alter table corrections enable row level security;
