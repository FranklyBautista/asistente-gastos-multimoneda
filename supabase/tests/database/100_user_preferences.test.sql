-- Las preferencias se cambian desde la app con update_preferences (migración 20261126120000):
-- solo las propias, solo con valores que el bot entiende, y null deja el valor como estaba.
begin;
create extension if not exists pgtap with schema extensions;
select plan(9);

insert into auth.users (id, email) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'ana@example.com'),
  ('aaaaaaaa-0000-0000-0000-000000000002', 'beto@example.com');
insert into users (id, telegram_id, display_name, auth_user_id) values
  ('00000000-0000-0000-0000-0000000000a1', 9001, 'Ana', 'aaaaaaaa-0000-0000-0000-000000000001'),
  ('00000000-0000-0000-0000-0000000000b1', 9002, 'Beto', null);

set local role authenticated;
select set_config('request.jwt.claims',
  '{"sub":"aaaaaaaa-0000-0000-0000-000000000001","role":"authenticated"}', true);

select lives_ok(
  $$select update_preferences(p_default_currency => 'VES')$$,
  'cambia una sola preferencia'
);
select results_eq(
  $$select default_currency, ves_rate_source, timezone, context_replies from users$$,
  $$values ('VES'::text, 'parallel'::text, 'America/Caracas'::text, true)$$,
  'solo cambia la moneda: lo demás queda igual'
);
select lives_ok(
  $$select update_preferences('USDT', 'p2p', 'America/Bogota', false)$$,
  'cambia todas a la vez'
);
select results_eq(
  $$select default_currency, ves_rate_source, timezone, context_replies from users$$,
  $$values ('USDT'::text, 'p2p'::text, 'America/Bogota'::text, false)$$,
  'quedan los cuatro valores nuevos'
);

select throws_ok($$select update_preferences(p_default_currency => 'EUR')$$,
  '22023', 'invalid_currency', 'rechaza una moneda que el bot no maneja');
select throws_ok($$select update_preferences(p_ves_rate_source => 'dolartoday')$$,
  '22023', 'invalid_rate_source', 'rechaza una fuente de tasa desconocida');
select throws_ok($$select update_preferences(p_timezone => 'Asia/Tokyo')$$,
  '22023', 'invalid_timezone', 'rechaza una zona que el bot no ofrece');

-- Una cuenta web sin vincular no tiene usuario del bot que cambiar.
select set_config('request.jwt.claims',
  '{"sub":"aaaaaaaa-0000-0000-0000-000000000002","role":"authenticated"}', true);
select throws_ok($$select update_preferences(p_default_currency => 'COP')$$,
  '28000', 'not_linked', 'sin vínculo no cambia nada');

reset role;
select is(
  (select default_currency from users where telegram_id = 9002), 'USD',
  'el usuario de otra persona queda intacto'
);

select * from finish();
rollback;
