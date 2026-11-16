-- Deudas (Fase 11): pagos en la moneda de la deuda y sin pasar de lo pendiente, estado
-- calculado, anulación, contraparte normalizada y aislamiento entre usuarios.
begin;
create extension if not exists pgtap with schema extensions;
select plan(29);

insert into auth.users (id, email) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'ana@example.com'),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'beto@example.com');

insert into users (id, telegram_id, display_name, auth_user_id) values
  ('00000000-0000-0000-0000-0000000000a1', 7001, 'Ana', 'aaaaaaaa-0000-0000-0000-000000000001'),
  ('00000000-0000-0000-0000-0000000000b2', 7002, 'Beto', 'bbbbbbbb-0000-0000-0000-000000000002');

-- Deudas de Ana: le debe 20 USD a Miguel, Luisa le debe 50.000 COP y una anulada.
-- Beto le debe 10 USDT a Miguel.
insert into debts (id, user_id, direction, counterparty, currency, amount, usd_per_unit,
                   rate_source, amount_usd, cancelled_at) values
  ('d0000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'i_owe',
   '  Míguel   Ángel ', 'USD', 20, 1, 'pivot', 20, null),
  ('d0000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000a1',
   'owed_to_me', 'Luisa', 'COP', 50000, 0.00025, 'fx', 12.5, null),
  ('d0000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-0000000000a1', 'i_owe',
   'Pedro', 'USD', 5, 1, 'pivot', 5, now()),
  ('d0000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-0000000000b2', 'i_owe',
   'Miguel', 'USDT', 10, 1, 'coingecko', 10, null);

-- Un gasto de Ana que pagó parte de la deuda con Miguel.
insert into transactions (id, user_id, account_id, currency, kind, amount, usd_per_unit,
                          rate_source, amount_usd)
select '11111111-0000-0000-0000-000000000001', u.id, a.id, 'USD', 'expense', 5, 1, 'pivot', 5
from users u join accounts a on a.user_id = u.id and a.currency = 'USD'
where u.telegram_id = 7001;

select has_table('debts');
select has_table('debt_payments');
select has_view('debt_balances');
select ok(
  exists (select 1 from categories where user_id is null and name = 'pago de deudas' and kind = 'expense')
  and exists (select 1 from categories where user_id is null and name = 'cobro de deudas' and kind = 'income'),
  'existen las categorías globales de pago y cobro de deudas'
);
select ok(
  (select relrowsecurity from pg_class where oid = 'public.debts'::regclass)
  and (select relrowsecurity from pg_class where oid = 'public.debt_payments'::regclass),
  'las dos tablas tienen RLS activo'
);

-- ---- Contraparte ----
select is(
  (select counterparty_key from debts where id = 'd0000000-0000-0000-0000-000000000001'),
  'miguel angel',
  'la clave de la contraparte va en minúsculas, sin tildes y sin espacios de más'
);
select throws_ok(
  $$insert into debts (user_id, direction, counterparty, currency, amount, usd_per_unit,
                       rate_source, amount_usd)
    values ('00000000-0000-0000-0000-0000000000a1', 'i_owe', '   ', 'USD', 1, 1, 'pivot', 1)$$,
  '23514', null, 'la contraparte no puede estar vacía'
);
select throws_ok(
  $$insert into debts (user_id, direction, counterparty, currency, amount, usd_per_unit,
                       rate_source, amount_usd)
    values ('00000000-0000-0000-0000-0000000000a1', 'they_owe', 'X', 'USD', 1, 1, 'pivot', 1)$$,
  '23514', null, 'la dirección es i_owe u owed_to_me'
);

-- ---- Pagos ----
select throws_ok(
  $$insert into debt_payments (user_id, debt_id, currency, amount)
    values ('00000000-0000-0000-0000-0000000000a1', 'd0000000-0000-0000-0000-000000000001',
            'VES', 1000)$$,
  '23503', null, 'un pago en otra moneda que la deuda se rechaza'
);
select throws_ok(
  $$insert into debt_payments (user_id, debt_id, currency, amount)
    values ('00000000-0000-0000-0000-0000000000b2', 'd0000000-0000-0000-0000-000000000001',
            'USD', 1)$$,
  '23503', null, 'nadie paga la deuda de otro usuario'
);

select is(
  (select status from debt_balances where debt_id = 'd0000000-0000-0000-0000-000000000001'),
  'open', 'sin pagos, la deuda está abierta'
);

insert into debt_payments (id, user_id, debt_id, currency, amount, transaction_id) values
  ('e0000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1',
   'd0000000-0000-0000-0000-000000000001', 'USD', 5, '11111111-0000-0000-0000-000000000001');

select results_eq(
  $$select status, remaining from debt_balances
    where debt_id = 'd0000000-0000-0000-0000-000000000001'$$,
  $$values ('partial'::text, 15::numeric)$$,
  'un pago parcial deja la deuda partial con lo que resta'
);
select throws_ok(
  $$insert into debt_payments (user_id, debt_id, currency, amount)
    values ('00000000-0000-0000-0000-0000000000a1', 'd0000000-0000-0000-0000-000000000001',
            'USD', 15.01)$$,
  'P0001', 'payment_exceeds_remaining', 'un pago no supera lo pendiente'
);
select throws_ok(
  $$insert into debt_payments (user_id, debt_id, currency, amount, transaction_id)
    values ('00000000-0000-0000-0000-0000000000a1', 'd0000000-0000-0000-0000-000000000002',
            'COP', 1000, '11111111-0000-0000-0000-000000000001')$$,
  '23505', null, 'un movimiento paga como mucho una deuda'
);

insert into debt_payments (id, user_id, debt_id, currency, amount) values
  ('e0000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000a1',
   'd0000000-0000-0000-0000-000000000001', 'USD', 15);

select results_eq(
  $$select status, remaining from debt_balances
    where debt_id = 'd0000000-0000-0000-0000-000000000001'$$,
  $$values ('settled'::text, 0::numeric)$$,
  'pagar lo que resta la liquida'
);
select isnt(
  (select last_paid_at from debt_balances where debt_id = 'd0000000-0000-0000-0000-000000000001'),
  null, 'la vista dice cuándo fue el último pago'
);

-- Deshacer un pago reabre la deuda, y no se puede rehacer si ya no cabe.
update debt_payments set deleted_at = now() where id = 'e0000000-0000-0000-0000-000000000002';
select results_eq(
  $$select status, remaining from debt_balances
    where debt_id = 'd0000000-0000-0000-0000-000000000001'$$,
  $$values ('partial'::text, 15::numeric)$$,
  'un pago deshecho no cuenta'
);
insert into debt_payments (user_id, debt_id, currency, amount) values
  ('00000000-0000-0000-0000-0000000000a1', 'd0000000-0000-0000-0000-000000000001', 'USD', 10);
select throws_ok(
  $$update debt_payments set deleted_at = null
    where id = 'e0000000-0000-0000-0000-000000000002'$$,
  'P0001', 'payment_exceeds_remaining', 'restaurar un pago también respeta lo pendiente'
);
select throws_ok(
  $$update debt_payments set amount = 16
    where id = 'e0000000-0000-0000-0000-000000000001'$$,
  'P0001', 'payment_exceeds_remaining', 'subir el monto de un pago también respeta lo pendiente'
);

-- Las anuladas no reciben pagos ni salen en la vista.
select throws_ok(
  $$insert into debt_payments (user_id, debt_id, currency, amount)
    values ('00000000-0000-0000-0000-0000000000a1', 'd0000000-0000-0000-0000-000000000003',
            'USD', 1)$$,
  'P0001', 'debt_cancelled', 'una deuda anulada no recibe pagos'
);
select is(
  (select count(*)::int from debt_balances
   where debt_id = 'd0000000-0000-0000-0000-000000000003'),
  0, 'una deuda anulada no sale en debt_balances'
);

-- Borrar el gasto deja el pago sin movimiento en vez de borrarlo.
delete from transactions where id = '11111111-0000-0000-0000-000000000001';
select is(
  (select transaction_id from debt_payments where id = 'e0000000-0000-0000-0000-000000000001'),
  null, 'si se borra el movimiento, el pago queda sin movimiento'
);

-- ---- Sesión de Ana: solo lo suyo y solo lectura ----
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-0000-0000-000000000001","role":"authenticated"}', true);

select results_eq(
  'select counterparty_key from debts order by counterparty_key',
  $$values ('luisa'::text), ('miguel angel'), ('pedro')$$,
  'Ana ve sus tres deudas y ninguna de Beto'
);
select is((select count(*)::int from debt_payments), 3, 'Ana ve solo sus pagos');
select results_eq(
  'select counterparty_key, status from debt_balances order by counterparty_key',
  $$values ('luisa'::text, 'open'::text), ('miguel angel', 'partial')$$,
  'debt_balances respeta la RLS de la sesión'
);
select throws_ok(
  $$insert into debts (user_id, direction, counterparty, currency, amount, usd_per_unit,
                       rate_source, amount_usd)
    values ('00000000-0000-0000-0000-0000000000a1', 'i_owe', 'X', 'USD', 1, 1, 'pivot', 1)$$,
  '42501', null, 'la web no escribe deudas directamente'
);
select throws_ok(
  $$update debt_payments set deleted_at = now()$$,
  '42501', null, 'la web no modifica pagos directamente'
);

-- ---- anon no ve nada ----
reset role;
set local role anon;
select throws_ok('select * from debts', '42501', null, 'anon no lee deudas');
select throws_ok('select * from debt_balances', '42501', null, 'anon no lee debt_balances');

select * from finish();
rollback;
