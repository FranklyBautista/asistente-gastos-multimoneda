-- Onboarding del bot: columna onboarded_at y preferencias válidas.
begin;
create extension if not exists pgtap with schema extensions;
select plan(4);

select has_column('users', 'onboarded_at');
select col_is_null('users', 'onboarded_at');

insert into users (telegram_id) values (2001);

select is(
  (select onboarded_at from users where telegram_id = 2001),
  null,
  'un usuario nuevo empieza sin onboarding'
);

select throws_ok(
  $$update users set ves_rate_source = 'binance' where telegram_id = 2001$$,
  '23514',
  null,
  'se rechaza una fuente de Bs desconocida'
);

select * from finish();
rollback;
