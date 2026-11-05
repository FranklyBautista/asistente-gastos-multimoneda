-- Updates recibidos: un update_id se registra una sola vez por bot.
begin;
create extension if not exists pgtap with schema extensions;
select plan(5);

select has_table('processed_updates');
select col_is_pk('processed_updates', array['bot_id', 'update_id']);
select ok(
  (select relrowsecurity from pg_class where oid = 'public.processed_updates'::regclass),
  'la tabla tiene RLS activo'
);

insert into processed_updates (bot_id, update_id) values (1, 100);

select throws_ok(
  $$insert into processed_updates (bot_id, update_id) values (1, 100)$$,
  '23505',
  null,
  'el mismo update de un bot se registra una sola vez'
);

select lives_ok(
  $$insert into processed_updates (bot_id, update_id) values (2, 100)$$,
  'otro bot puede tener el mismo update_id'
);

select * from finish();
rollback;
