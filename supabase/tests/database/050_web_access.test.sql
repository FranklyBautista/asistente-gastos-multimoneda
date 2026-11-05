-- Acceso de la web: cada sesión ve solo lo suyo, anon no ve nada, y la vinculación por código
-- valida vencimiento, uso y cuentas ya vinculadas (ADR 0012).
begin;
create extension if not exists pgtap with schema extensions;
select plan(23);

-- Dos personas con cuenta web (Ana y Beto) y tres usuarios del bot.
insert into auth.users (id, email) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'ana@example.com'),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'beto@example.com'),
  ('cccccccc-0000-0000-0000-000000000003', 'carla@example.com');

insert into users (id, telegram_id, display_name, auth_user_id) values
  ('00000000-0000-0000-0000-0000000000a1', 5001, 'Ana', 'aaaaaaaa-0000-0000-0000-000000000001'),
  ('00000000-0000-0000-0000-0000000000b2', 5002, 'Beto', null),
  ('00000000-0000-0000-0000-0000000000c3', 5003, 'Carla', null);

insert into transactions (user_id, account_id, currency, kind, amount, usd_per_unit, rate_source, amount_usd)
select u.id, a.id, 'USD', 'expense', 10, 1, 'pivot', 10
from users u join accounts a on a.user_id = u.id and a.currency = 'USD'
where u.telegram_id in (5001, 5002);

insert into exchange_rates (currency, source, usd_per_unit) values ('VES', 'bcv', 0.0025);

insert into link_codes (code, user_id, expires_at) values
  ('BETA2345', '00000000-0000-0000-0000-0000000000b2', now() + interval '10 minutes'),
  ('VENC2345', '00000000-0000-0000-0000-0000000000c3', now() - interval '1 minute'),
  ('ANAXXXX2', '00000000-0000-0000-0000-0000000000a1', now() + interval '10 minutes'),
  ('CARLA234', '00000000-0000-0000-0000-0000000000c3', now() + interval '10 minutes');

select has_column('users', 'auth_user_id');
select has_table('link_codes');

-- ---- Sesión de Ana: solo sus datos ----
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-0000-0000-000000000001","role":"authenticated"}', true);

select results_eq('select telegram_id from users', 'values (5001::bigint)', 'Ana solo ve su usuario');
select is((select count(*)::int from accounts), 4, 'Ana ve sus 4 cuentas y ninguna ajena');
select is((select count(*)::int from transactions), 1, 'Ana ve solo su movimiento');
select is((select count(*)::int from account_balances), 4, 'la vista de saldos respeta la RLS');
select is((select count(*)::int from categories), 8, 'Ana ve las categorías globales');
select ok((select count(*) from exchange_rates) >= 1, 'las tasas se pueden leer');

select throws_ok('select * from link_codes', '42501', null, 'los códigos no se leen desde la web');
select throws_ok('select * from processed_updates', '42501', null, 'las tablas internas del bot no se leen');
select throws_ok(
  $$update transactions set amount = 1$$, '42501', null, 'la web no modifica movimientos directamente'
);
select throws_ok(
  $$insert into users (telegram_id) values (9999)$$, '42501', null, 'la web no crea usuarios'
);
select throws_ok(
  $$select redeem_link_code('BETA2345')$$, 'P0001', 'web_already_linked',
  'una cuenta web ya vinculada no puede vincular otro usuario del bot'
);

-- ---- Sesión de Beto (aún sin vincular) ----
select set_config('request.jwt.claims', '{"sub":"bbbbbbbb-0000-0000-0000-000000000002","role":"authenticated"}', true);

select is((select count(*)::int from transactions), 0, 'sin vincular no se ve ningún movimiento');
select throws_ok(
  $$select redeem_link_code('VENC2345')$$, 'P0001', 'invalid_code', 'un código vencido se rechaza'
);
select throws_ok(
  $$select redeem_link_code('NOEXISTE')$$, 'P0001', 'invalid_code', 'un código inexistente se rechaza'
);
select throws_ok(
  $$select redeem_link_code('ANAXXXX2')$$, 'P0001', 'telegram_already_linked',
  'no se puede tomar un usuario del bot vinculado a otra cuenta web'
);
select is(redeem_link_code(' beta2345 '), 'Beto', 'el canje vincula y acepta minúsculas y espacios');
select is((select count(*)::int from transactions), 1, 'tras vincular, Beto ve su movimiento');

-- ---- Sesión de Carla: el código de Beto ya se usó ----
select set_config('request.jwt.claims', '{"sub":"cccccccc-0000-0000-0000-000000000003","role":"authenticated"}', true);
select throws_ok(
  $$select redeem_link_code('BETA2345')$$, 'P0001', 'invalid_code', 'un código no se usa dos veces'
);

-- ---- Sin sesión ----
set local role anon;
select set_config('request.jwt.claims', '{"role":"anon"}', true);
select throws_ok('select * from transactions', '42501', null, 'anon no lee movimientos');
select throws_ok(
  $$select redeem_link_code('CARLA234')$$, '42501', null, 'anon no puede canjear códigos'
);
select throws_ok($$select app_user_id()$$, '42501', null, 'anon no llama funciones internas');

reset role;
select * from finish();
rollback;
