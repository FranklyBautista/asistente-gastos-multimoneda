-- Modelo multimoneda: estructura, datos por defecto, restricciones y saldos calculados.
begin;
create extension if not exists pgtap with schema extensions;
select plan(23);

-- Estructura
select has_table('users');
select has_table('accounts');
select has_table('categories');
select has_table('transactions');
select has_table('exchanges');
select has_table('exchange_rates');
select has_table('corrections');
select has_view('account_balances');

select is(
  (select count(*)::int from pg_tables
   where schemaname = 'public' and not rowsecurity),
  0,
  'todas las tablas públicas tienen RLS activada'
);

-- Datos por defecto
select is(
  (select count(*)::int from categories where user_id is null),
  8,
  'existen las 8 categorías globales'
);

insert into users (id, telegram_id) values
  ('00000000-0000-0000-0000-00000000000a', 1001),
  ('00000000-0000-0000-0000-00000000000b', 1002);

select results_eq(
  $$select currency from accounts
    where user_id = '00000000-0000-0000-0000-00000000000a' order by currency$$,
  $$values ('COP'), ('USD'), ('USDT'), ('VES')$$,
  'un usuario nuevo recibe una cuenta por moneda'
);

-- Atajos para las pruebas
create temp table acc as
select user_id, currency, id from accounts;

-- Saldos en las 4 monedas
insert into transactions (user_id, account_id, currency, kind, amount, usd_per_unit, rate_source, amount_usd)
select '00000000-0000-0000-0000-00000000000a', id, currency, kind, amount, rate, src, amount * rate
from acc
join (values
  ('VES', 'income',  1000::numeric,   0.0050::numeric, 'parallel'),
  ('VES', 'expense',  250,            0.0050,          'parallel'),
  ('COP', 'expense', 20000,           0.00025,         'fx'),
  ('USD', 'income',   100,            1,               'pivot'),
  ('USD', 'expense',   15,            1,               'pivot'),
  ('USDT', 'income',  200,            0.999,           'coingecko')
) as m (cur, kind, amount, rate, src) on m.cur = acc.currency
where acc.user_id = '00000000-0000-0000-0000-00000000000a';

select results_eq(
  $$select currency, balance from account_balances
    where user_id = '00000000-0000-0000-0000-00000000000a' order by currency$$,
  $$values ('COP', -20000::numeric), ('USD', 85::numeric), ('USDT', 200::numeric), ('VES', 750::numeric)$$,
  'saldos correctos en las 4 monedas'
);

-- Borrado lógico
update transactions set deleted_at = now()
where user_id = '00000000-0000-0000-0000-00000000000a' and currency = 'USD' and kind = 'expense';

select is(
  (select balance from account_balances
   where user_id = '00000000-0000-0000-0000-00000000000a' and currency = 'USD'),
  100::numeric,
  'los movimientos borrados no cuentan en el saldo'
);

-- Cambio de USDT a Bs
insert into exchanges (user_id, from_account_id, to_account_id, from_amount, to_amount, effective_rate)
values (
  '00000000-0000-0000-0000-00000000000a',
  (select id from acc where user_id = '00000000-0000-0000-0000-00000000000a' and currency = 'USDT'),
  (select id from acc where user_id = '00000000-0000-0000-0000-00000000000a' and currency = 'VES'),
  50, 3900, 78
);

select results_eq(
  $$select currency, balance from account_balances
    where user_id = '00000000-0000-0000-0000-00000000000a' and currency in ('USDT', 'VES')
    order by currency$$,
  $$values ('USDT', 150::numeric), ('VES', 4650::numeric)$$,
  'un cambio resta del origen y suma al destino'
);

-- Restricciones
select throws_ok(
  $$insert into transactions (user_id, account_id, currency, kind, amount, usd_per_unit, rate_source, amount_usd)
    values ('00000000-0000-0000-0000-00000000000a',
            (select id from acc where user_id = '00000000-0000-0000-0000-00000000000a' and currency = 'VES'),
            'USD', 'expense', 10, 1, 'pivot', 10)$$,
  '23503',
  null,
  'se rechaza una moneda distinta a la de la cuenta'
);

select throws_ok(
  $$insert into transactions (user_id, account_id, currency, kind, amount, usd_per_unit, rate_source, amount_usd)
    values ('00000000-0000-0000-0000-00000000000b',
            (select id from acc where user_id = '00000000-0000-0000-0000-00000000000a' and currency = 'USD'),
            'USD', 'expense', 10, 1, 'pivot', 10)$$,
  '23503',
  null,
  'se rechaza un movimiento en la cuenta de otro usuario'
);

select throws_ok(
  $$insert into exchanges (user_id, from_account_id, to_account_id, from_amount, to_amount, effective_rate)
    values ('00000000-0000-0000-0000-00000000000b',
            (select id from acc where user_id = '00000000-0000-0000-0000-00000000000b' and currency = 'USD'),
            (select id from acc where user_id = '00000000-0000-0000-0000-00000000000a' and currency = 'VES'),
            10, 780, 78)$$,
  '23503',
  null,
  'se rechaza un cambio hacia la cuenta de otro usuario'
);

select throws_ok(
  $$insert into accounts (user_id, name, currency, kind)
    values ('00000000-0000-0000-0000-00000000000a', 'euros', 'EUR', 'cash')$$,
  '23514',
  null,
  'se rechaza una moneda fuera de las 4 soportadas'
);

select throws_ok(
  $$insert into transactions (user_id, account_id, currency, kind, amount, usd_per_unit, rate_source, amount_usd)
    values ('00000000-0000-0000-0000-00000000000a',
            (select id from acc where user_id = '00000000-0000-0000-0000-00000000000a' and currency = 'USD'),
            'USD', 'expense', 0, 1, 'pivot', 0)$$,
  '23514',
  null,
  'se rechaza un monto igual a cero'
);

select throws_ok(
  $$insert into exchanges (user_id, from_account_id, to_account_id, from_amount, to_amount, effective_rate)
    values ('00000000-0000-0000-0000-00000000000a',
            (select id from acc where user_id = '00000000-0000-0000-0000-00000000000a' and currency = 'USD'),
            (select id from acc where user_id = '00000000-0000-0000-0000-00000000000a' and currency = 'USD'),
            10, 10, 1)$$,
  '23514',
  null,
  'se rechaza un cambio a la misma cuenta'
);

select throws_ok(
  $$insert into exchange_rates (currency, source, usd_per_unit) values ('USD', 'fx', 1)$$,
  '23514',
  null,
  'USD no tiene tasa propia porque es el pivote'
);

select throws_ok(
  $$insert into categories (user_id, name, kind) values (null, 'comida', 'expense')$$,
  '23505',
  null,
  'no se duplican categorías globales'
);

select lives_ok(
  $$insert into categories (user_id, name, kind)
    values ('00000000-0000-0000-0000-00000000000a', 'comida', 'expense')$$,
  'un usuario puede tener su propia categoría con un nombre global'
);

select * from finish();
rollback;
