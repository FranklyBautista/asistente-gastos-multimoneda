-- Hábitos (Fase 12): topes por categoría de gasto, un tope vigente por categoría, lo gastado
-- en el mes local, ritmo de gasto para el colchón y aislamiento entre usuarios.
begin;
create extension if not exists pgtap with schema extensions;
select plan(22);

insert into auth.users (id, email) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'ana@example.com'),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'beto@example.com');

insert into users (id, telegram_id, display_name, auth_user_id) values
  ('00000000-0000-0000-0000-0000000000a1', 8001, 'Ana', 'aaaaaaaa-0000-0000-0000-000000000001'),
  ('00000000-0000-0000-0000-0000000000b2', 8002, 'Beto', 'bbbbbbbb-0000-0000-0000-000000000002');

-- Una categoría propia de Beto, que Ana no puede usar.
insert into categories (id, user_id, name, kind) values
  ('c0000000-0000-0000-0000-0000000000b2', '00000000-0000-0000-0000-0000000000b2',
   'mascotas', 'expense');

-- Gastos de Ana en USD: 30 y 50 en comida este mes, 7 en comida deshecho, 20 en comida el
-- mes pasado y 9 en transporte este mes. Beto: 100 en comida este mes.
create temporary table months as
select date_trunc('month', now() at time zone 'America/Caracas')
         at time zone 'America/Caracas' as this_month;

insert into transactions (user_id, account_id, currency, kind, amount, category_id,
                          usd_per_unit, rate_source, amount_usd, occurred_at, deleted_at)
select a.user_id, a.id, 'USD', 'expense', x.amount,
       (select id from categories where user_id is null and name = x.category),
       1, 'pivot', x.amount, x.occurred_at, x.deleted_at
from accounts a
join users u on u.id = a.user_id and a.currency = 'USD'
cross join months m
cross join lateral (values
  (8001, 30::numeric, 'comida', m.this_month + interval '1 hour', null::timestamptz),
  (8001, 50, 'comida', now(), null),
  (8001, 7, 'comida', now(), now()),
  (8001, 20, 'comida', m.this_month - interval '1 day', null),
  (8001, 9, 'transporte', now(), null),
  (8002, 100, 'comida', now(), null)
) as x (telegram_id, amount, category, occurred_at, deleted_at)
where u.telegram_id = x.telegram_id;

insert into budgets (id, user_id, category_id, limit_usd) values
  ('b0000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1',
   (select id from categories where user_id is null and name = 'comida'), 100),
  ('b0000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-0000000000b2',
   (select id from categories where user_id is null and name = 'comida'), 80);

select has_table('budgets');
select has_view('budget_progress');
select ok(
  (select relrowsecurity from pg_class where oid = 'public.budgets'::regclass),
  'budgets tiene RLS activo'
);
select is(
  (select context_replies from users where telegram_id = 8001),
  true, 'el contexto al anotar viene encendido'
);

-- ---- Reglas del tope ----
select throws_ok(
  $$insert into budgets (user_id, category_id, limit_usd)
    values ('00000000-0000-0000-0000-0000000000a1',
            (select id from categories where user_id is null and name = 'ocio'), 0)$$,
  '23514', null, 'un tope tiene que ser mayor que 0'
);
select throws_ok(
  $$insert into budgets (user_id, category_id, limit_usd)
    values ('00000000-0000-0000-0000-0000000000a1',
            (select id from categories where user_id is null and name = 'salario'), 10)$$,
  '23514', 'budget_category_invalid', 'una categoría de ingreso no lleva tope'
);
select throws_ok(
  $$insert into budgets (user_id, category_id, limit_usd)
    values ('00000000-0000-0000-0000-0000000000a1', 'c0000000-0000-0000-0000-0000000000b2', 10)$$,
  '23514', 'budget_category_invalid', 'nadie usa la categoría propia de otro usuario'
);
select lives_ok(
  $$insert into budgets (user_id, category_id, limit_usd)
    values ('00000000-0000-0000-0000-0000000000b2', 'c0000000-0000-0000-0000-0000000000b2', 10)$$,
  'cada quien usa sus categorías propias'
);
select throws_ok(
  $$insert into budgets (user_id, category_id, limit_usd)
    values ('00000000-0000-0000-0000-0000000000a1',
            (select id from categories where user_id is null and name = 'comida'), 120)$$,
  '23505', null, 'solo hay un tope vigente por categoría'
);

-- ---- Lo gastado en el mes ----
select results_eq(
  $$select category, limit_usd, spent_usd, remaining_usd from budget_progress
    where budget_id = 'b0000000-0000-0000-0000-000000000001'$$,
  $$values ('comida'::text, 100::numeric, 80::numeric, 20::numeric)$$,
  'cuenta solo los gastos vigentes de esa categoría en el mes local en curso'
);
select is(
  (select month_start from budget_progress where budget_id = 'b0000000-0000-0000-0000-000000000001'),
  (select (this_month at time zone 'America/Caracas')::date from months),
  'el mes es el calendario de la zona del usuario'
);

-- Reemplazar: el viejo se archiva y el nuevo apunta a él.
update budgets set archived_at = now() where id = 'b0000000-0000-0000-0000-000000000001';
insert into budgets (id, user_id, category_id, limit_usd, replaces_id) values
  ('b0000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-0000000000a1',
   (select id from categories where user_id is null and name = 'comida'), 120,
   'b0000000-0000-0000-0000-000000000001');
select results_eq(
  $$select budget_id, limit_usd from budget_progress
    where user_id = '00000000-0000-0000-0000-0000000000a1'$$,
  $$values ('b0000000-0000-0000-0000-000000000003'::uuid, 120::numeric)$$,
  'un tope archivado no sale en budget_progress'
);

-- ---- Sesión de Ana: solo lo suyo y solo lectura ----
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"aaaaaaaa-0000-0000-0000-000000000001","role":"authenticated"}', true);

select is((select count(*)::int from budgets), 2, 'Ana ve sus dos topes (vigente y archivado)');
select results_eq(
  'select category, spent_usd from budget_progress',
  $$values ('comida'::text, 80::numeric)$$,
  'budget_progress respeta la RLS de la sesión'
);
select throws_ok(
  $$insert into budgets (user_id, category_id, limit_usd)
    values ('00000000-0000-0000-0000-0000000000a1',
            (select id from categories where user_id is null and name = 'ocio'), 10)$$,
  '42501', null, 'la web no escribe topes directamente'
);
select throws_ok(
  $$update budgets set limit_usd = 1$$,
  '42501', null, 'la web no modifica topes directamente'
);

-- Ritmo de gasto: desde el primer movimiento de Ana (el día antes de empezar el mes) hasta hoy.
select is(
  (select window_days from spending_pace()),
  -- El primer movimiento cae el último día del mes pasado: los días del mes en curso + 1.
  extract(day from now() at time zone 'America/Caracas')::int + 1,
  'el ritmo usa los días desde el primer movimiento cuando son menos de 90'
);
select is(
  (select expenses_usd from spending_pace()), 109::numeric,
  'el ritmo suma los gastos vigentes de Ana en USD, sin los de Beto'
);
select is(
  (select window_days from spending_pace(1)), 1, 'el ritmo respeta la ventana pedida'
);
select is(
  (select expenses_usd from spending_pace(1)), 59::numeric,
  'con un día de ventana solo cuenta lo de hoy'
);

-- Sin movimientos no hay ritmo.
select set_config('request.jwt.claims', '{"sub":"cccccccc-0000-0000-0000-000000000003","role":"authenticated"}', true);
select results_eq(
  'select window_days, expenses_usd from spending_pace()',
  $$values (null::integer, null::numeric)$$,
  'sin movimientos visibles el ritmo viene vacío'
);

-- ---- anon no ve nada ----
reset role;
set local role anon;
select throws_ok('select * from budgets', '42501', null, 'anon no lee topes');

select * from finish();
rollback;
