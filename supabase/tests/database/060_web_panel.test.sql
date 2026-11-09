-- Panel web (Fase 10, ADR 0014): saldos en USD, lista filtrada, gráficas, historial de
-- cambios y edición de movimientos desde la web, siempre limitados al dueño de la sesión.
begin;
create extension if not exists pgtap with schema extensions;
select plan(37);

insert into auth.users (id, email) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'ana@example.com'),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'beto@example.com'),
  ('cccccccc-0000-0000-0000-000000000003', 'carla@example.com');

-- Ana usa la tasa BCV y vive en Caracas (UTC-4); Beto, la paralela.
insert into users (id, telegram_id, display_name, auth_user_id, ves_rate_source, timezone) values
  ('00000000-0000-0000-0000-0000000000a1', 6001, 'Ana', 'aaaaaaaa-0000-0000-0000-000000000001',
   'bcv', 'America/Caracas'),
  ('00000000-0000-0000-0000-0000000000b2', 6002, 'Beto', 'bbbbbbbb-0000-0000-0000-000000000002',
   'parallel', 'America/Caracas');

-- Tasas: la BCV de hace 10 h queda vieja; la de COP es reciente. Historial de la BCV para el
-- poder adquisitivo (tres días, dos tasas el mismo día) y para la edición (tasa del 1 de nov).
create temp table local_days as
select (date_trunc('day', now() at time zone 'America/Caracas') - interval '3 days'
        + interval '12 hours') at time zone 'America/Caracas' as d3,
       (date_trunc('day', now() at time zone 'America/Caracas') - interval '2 days'
        + interval '10 hours') at time zone 'America/Caracas' as d2;
grant select on local_days to authenticated;
insert into exchange_rates (currency, source, usd_per_unit, fetched_at) values
  ('VES', 'bcv', 0.0020000000, (select d3 from local_days)),
  ('VES', 'bcv', 0.0019000000, (select d2 from local_days)),
  ('VES', 'bcv', 0.0018000000, (select d2 + interval '1 hour' from local_days)),
  ('VES', 'bcv', 0.0016000000, now() - interval '10 hours'),
  ('VES', 'parallel', 0.0010000000, now() - interval '1 hour'),
  ('COP', 'fx', 0.0002500000, now() - interval '1 hour'),
  ('USDT', 'coingecko', 1.0000000000, now() - interval '1 hour'),
  ('COP', 'fx', 0.0002000000, '2026-11-01 12:00+00');

-- Movimientos de Ana (fechas en UTC; en Caracas el primero cae el 2 de nov a las 20:00).
insert into transactions (id, user_id, account_id, currency, kind, amount, category_id,
                          description, occurred_at, usd_per_unit, rate_source, amount_usd,
                          raw_text, created_at)
select v.id::uuid, u.id, a.id, a.currency, v.kind, v.amount,
       (select c.id from categories c where c.user_id is null and c.name = v.category),
       v.description, v.occurred_at::timestamptz, v.rate, v.source, v.amount * v.rate,
       v.raw_text, v.occurred_at::timestamptz
from users u
join (values
  ('11111111-0000-0000-0000-000000000001', 'USD', 'expense', 15, 'comida', 'almuerzo',
   '2026-11-03 00:00+00', 1, 'pivot', 'gasté 15 en el almuerzo'),
  ('11111111-0000-0000-0000-000000000002', 'VES', 'expense', 1000, 'transporte', 'pasaje',
   '2026-11-03 05:00+00', 0.002, 'bcv', 'pagué 1000 bs de pasaje'),
  ('11111111-0000-0000-0000-000000000003', 'USD', 'income', 200, 'salario', 'sueldo',
   '2026-11-04 12:00+00', 1, 'pivot', 'me pagaron 200'),
  ('11111111-0000-0000-0000-000000000004', 'USD', 'expense', 5, 'comida', 'café',
   now()::text, 1, 'pivot', 'café 5 dólares')
) as v (id, currency, kind, amount, category, description, occurred_at, rate, source, raw_text)
  on true
join accounts a on a.user_id = u.id and a.currency = v.currency
where u.telegram_id = 6001;

-- Un movimiento de Beto que Ana no debe ver ni editar.
insert into transactions (id, user_id, account_id, currency, kind, amount, usd_per_unit,
                          rate_source, amount_usd)
select '22222222-0000-0000-0000-000000000001', u.id, a.id, 'USD', 'expense', 99, 1, 'pivot', 99
from users u join accounts a on a.user_id = u.id and a.currency = 'USD'
where u.telegram_id = 6002;

-- Un cambio de Ana: 50 USDT → 49.250 Bs a 985, contra una referencia de 1000.
insert into exchanges (user_id, from_account_id, to_account_id, from_amount, to_amount,
                       effective_rate, reference_rate)
select u.id, f.id, t.id, 50, 49250, 985, 1000
from users u
join accounts f on f.user_id = u.id and f.currency = 'USDT'
join accounts t on t.user_id = u.id and t.currency = 'VES'
where u.telegram_id = 6001;

-- ---- Sesión de Ana ----
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-0000-0000-000000000001","role":"authenticated"}', true);

-- Tasas vigentes y saldos en USD.
select is((select count(*)::int from latest_rates), 4, 'una tasa vigente por par con datos (sin P2P aún)');
select is(
  (select usd_per_unit from latest_rates where currency = 'VES' and source = 'bcv'),
  0.0016::numeric, 'la tasa vigente es la más reciente'
);
select is((select count(*)::int from account_balances_usd), 4, 'Ana ve solo sus 4 saldos');
select is(
  (select balance_usd from account_balances_usd where currency = 'VES'),
  (49250 - 1000) * 0.0016, 'los Bs se valoran con la tasa BCV de Ana'
);
select is(
  (select rate_stale from account_balances_usd where currency = 'VES'), true,
  'la tasa BCV de hace 10 horas está vieja'
);
select is(
  (select (rate_source, usd_per_unit, balance_usd)::text from account_balances_usd
   where currency = 'USD'),
  '(pivot,1,180.000000)', 'USD es el pivote: 200 − 15 − 5'
);
select is(
  (select balance_usd from account_balances_usd where currency = 'USDT'), -50::numeric,
  'USDT se valora con su propia tasa'
);

-- Lista de movimientos.
select is((select count(*)::int from list_transactions()), 4, 'Ana ve sus 4 movimientos');
select is((select max(total)::int from list_transactions(p_limit => 2)), 4,
  'el total no depende de la página');
select is((select count(*)::int from list_transactions(p_limit => 2, p_offset => 2)), 2,
  'la segunda página trae el resto');
select is((select count(*)::int from list_transactions(p_currency => 'VES')), 1,
  'filtro por moneda');
select is((select count(*)::int from list_transactions(p_kind => 'income')), 1,
  'filtro por tipo');
select is(
  (select count(*)::int from list_transactions(
    p_category_id => (select id from categories where name = 'comida' and user_id is null))),
  2, 'filtro por categoría'
);
select results_eq(
  $$select description from list_transactions(p_from => '2026-11-02', p_to => '2026-11-02')$$,
  $$values ('almuerzo'::text)$$,
  'las fechas son días de la zona del usuario: 00:00 UTC del 3 de nov es el 2 en Caracas'
);
select is(
  (select count(*)::int from list_transactions(p_from => '2026-11-03', p_to => '2026-11-04')), 2,
  'el rango incluye el último día completo'
);
select is((select count(*)::int from list_transactions(p_limit => 1000)), 4,
  'el límite se acota a 100 sin fallar');

-- Gráficas.
select results_eq(
  $$select category, total_usd from spending_by_category('2026-11-01', '2026-11-05')$$,
  $$values ('comida'::text, 15.000000::numeric), ('transporte', 2.000000)$$,
  'gasto por categoría en USD, de mayor a menor'
);
select is((select count(*)::int from spending_by_week(8)), 8, 'una fila por semana');
select is(
  (select expenses_usd from spending_by_week(8) order by week_start desc limit 1),
  5.000000::numeric, 'la semana actual suma solo sus gastos'
);
select is(
  (select week_start from spending_by_week(1)),
  date_trunc('week', now() at time zone 'America/Caracas')::date,
  'las semanas empiezan el lunes en la zona del usuario'
);
select is((select count(*)::int from bolivar_rates(30)), 3, 'una tasa del Bs por día');
select is(
  (select usd_per_unit from bolivar_rates(30)
   where day = (select (d2 at time zone 'America/Caracas')::date from local_days)),
  0.0018::numeric, 'de cada día se toma la última tasa'
);

-- Historial de cambios.
select results_eq(
  $$select from_currency, to_currency, difference_pct from exchange_history$$,
  $$values ('USDT'::text, 'VES'::text, -1.50::numeric)$$,
  'recibiste 1,5 % menos que con la tasa de referencia'
);

-- Edición: mismo monto y moneda → nada cambia.
select is(
  edit_transaction('11111111-0000-0000-0000-000000000001', 'expense', 15,
    (select id from accounts where currency = 'USD'),
    (select id from categories where name = 'comida' and user_id is null)),
  0, 'sin cambios no se registra nada'
);
-- Otro monto en la misma moneda: misma tasa, otro snapshot.
select is(
  edit_transaction('11111111-0000-0000-0000-000000000002', 'expense', 1500,
    (select id from accounts where currency = 'VES'),
    (select id from categories where name = 'transporte' and user_id is null)),
  1, 'cambiar el monto es un cambio'
);
select is(
  (select (usd_per_unit, rate_source, amount_usd)::text from transactions
   where id = '11111111-0000-0000-0000-000000000002'),
  '(0.0020000000,bcv,3.000000)', 'misma moneda: se conserva la tasa del registro'
);
-- Cambio de moneda y categoría: la tasa del usuario cuando se anotó.
select is(
  edit_transaction('11111111-0000-0000-0000-000000000001', 'expense', 60000,
    (select id from accounts where currency = 'COP'),
    (select id from categories where name = 'ocio' and user_id is null)),
  3, 'moneda, monto y categoría cambian'
);
select is(
  (select (currency, usd_per_unit, rate_source, amount_usd)::text from transactions
   where id = '11111111-0000-0000-0000-000000000001'),
  '(COP,0.0002000000,fx,12.000000)', 'otra moneda: la tasa vigente cuando se anotó'
);
select results_eq(
  $$select field, old_value, new_value from corrections
    where transaction_id = '11111111-0000-0000-0000-000000000001' order by field$$,
  $$values ('amount'::text, '15'::text, '60000'::text), ('category', 'comida', 'ocio'),
           ('currency', 'USD', 'COP')$$,
  'cada campo cambiado queda en corrections'
);
select ok(
  (select edited from list_transactions(p_currency => 'COP')),
  'la lista marca los movimientos editados'
);

select throws_ok(
  $$select edit_transaction('22222222-0000-0000-0000-000000000001', 'expense', 1,
      (select id from accounts where currency = 'USD'),
      (select id from categories where name = 'comida' and user_id is null))$$,
  'P0002', 'transaction_not_found', 'Ana no puede editar movimientos de Beto'
);
select throws_ok(
  $$select edit_transaction('11111111-0000-0000-0000-000000000003', 'income', 200,
      (select id from accounts where currency = 'USD'),
      (select id from categories where name = 'comida' and user_id is null))$$,
  '22023', 'category_mismatch', 'un ingreso no puede quedar en una categoría de gasto'
);
select throws_ok(
  $$select edit_transaction('11111111-0000-0000-0000-000000000003', 'income', 0,
      (select id from accounts where currency = 'USD'),
      (select id from categories where name = 'salario' and user_id is null))$$,
  '22023', 'invalid_amount', 'el monto debe ser positivo'
);

-- ---- Sesión de Beto: no ve nada de Ana ----
select set_config('request.jwt.claims', '{"sub":"bbbbbbbb-0000-0000-0000-000000000002","role":"authenticated"}', true);
select is((select count(*)::int from list_transactions()), 1, 'Beto ve solo su movimiento');
select is((select count(*)::int from exchange_history), 0, 'Beto no ve los cambios de Ana');

-- ---- Sesión sin vincular y anon ----
select set_config('request.jwt.claims', '{"sub":"cccccccc-0000-0000-0000-000000000003","role":"authenticated"}', true);
select throws_ok(
  $$select edit_transaction('11111111-0000-0000-0000-000000000003', 'income', 1, null, null)$$,
  '28000', 'not_linked', 'sin vincular no se edita nada'
);

reset role;
set local role anon;
select throws_ok('select * from list_transactions()', '42501', null,
  'anon no ejecuta las funciones del panel');

select * from finish();
rollback;
