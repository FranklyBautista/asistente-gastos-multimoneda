-- Resumen semanal: una fila por usuario y semana, y la semana empieza el lunes.
begin;
create extension if not exists pgtap with schema extensions;
select plan(5);

select has_table('weekly_summaries');
select col_is_pk('weekly_summaries', array['user_id', 'week_start']);

insert into users (telegram_id) values (3001);
insert into weekly_summaries (user_id, week_start)
select id, date '2026-10-26' from users where telegram_id = 3001;

select throws_ok(
  $$insert into weekly_summaries (user_id, week_start)
    select id, date '2026-10-26' from users where telegram_id = 3001$$,
  '23505',
  null,
  'el resumen de una semana se registra una sola vez'
);

select throws_ok(
  $$insert into weekly_summaries (user_id, week_start)
    select id, date '2026-10-28' from users where telegram_id = 3001$$,
  '23514',
  null,
  'la semana debe empezar el lunes'
);

delete from users where telegram_id = 3001;
select is(
  (select count(*) from weekly_summaries ws
   where not exists (select 1 from users u where u.id = ws.user_id)),
  0::bigint,
  'al borrar el usuario se borran sus resúmenes'
);

select * from finish();
rollback;
