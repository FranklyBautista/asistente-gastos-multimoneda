-- Arreglos de la auditoría del 2026-11-27 (migración 20261127120000): edit_transaction responde
-- invalid_amount con montos enormes, y period_totals suma ingresos y gastos en la base.
begin;
create extension if not exists pgtap with schema extensions;
select plan(7);

insert into auth.users (id, email) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'ana@example.com'),
  ('aaaaaaaa-0000-0000-0000-000000000002', 'beto@example.com');
insert into users (id, telegram_id, display_name, auth_user_id) values
  ('00000000-0000-0000-0000-0000000000a1', 9001, 'Ana', 'aaaaaaaa-0000-0000-0000-000000000001'),
  ('00000000-0000-0000-0000-0000000000b1', 9002, 'Beto', 'aaaaaaaa-0000-0000-0000-000000000002');

-- Ana: un gasto de 5, dos ingresos (30 y 12,5) y un ingreso borrado. Beto: un ingreso de 1000.
insert into transactions (id, user_id, account_id, currency, kind, amount, category_id,
                          usd_per_unit, rate_source, amount_usd, deleted_at)
select v.id::uuid, u.id, a.id, 'USD', v.kind, v.amount,
       case v.kind when 'expense'
         then (select c.id from categories c where c.user_id is null and c.name = 'comida')
       end,
       1, 'pivot', v.amount, v.deleted_at
from users u
join accounts a on a.user_id = u.id and a.currency = 'USD'
join (values
  (9001, '11111111-0000-0000-0000-000000000001', 'expense', 5::numeric, null::timestamptz),
  (9001, '11111111-0000-0000-0000-000000000002', 'income', 30, null),
  (9001, '11111111-0000-0000-0000-000000000003', 'income', 12.5, null),
  (9001, '11111111-0000-0000-0000-000000000004', 'income', 99, now()),
  (9002, '22222222-0000-0000-0000-000000000001', 'income', 1000, null)
) as v (telegram_id, id, kind, amount, deleted_at) on v.telegram_id = u.telegram_id;

set local role authenticated;
select set_config('request.jwt.claims',
  '{"sub":"aaaaaaaa-0000-0000-0000-000000000001","role":"authenticated"}', true);

-- 1. Montos fuera de rango: antes 1e14 desbordaba numeric(20, 6) con 22003.
select throws_ok(
  $$select edit_transaction('11111111-0000-0000-0000-000000000001', 'expense', 1e14,
      (select id from accounts where currency = 'USD'),
      (select id from categories where name = 'comida' and user_id is null))$$,
  '22023', 'invalid_amount', 'un monto de 1e14 responde invalid_amount'
);
select throws_ok(
  $$select edit_transaction('11111111-0000-0000-0000-000000000001', 'expense', 1e30,
      (select id from accounts where currency = 'USD'),
      (select id from categories where name = 'comida' and user_id is null))$$,
  '22023', 'invalid_amount', 'un monto de 1e30 también'
);
select is(
  edit_transaction('11111111-0000-0000-0000-000000000001', 'expense', 99999999999999.5,
    (select id from accounts where currency = 'USD'),
    (select id from categories where name = 'comida' and user_id is null)),
  1, 'el mayor monto que cabe se sigue aceptando'
);
reset role;
update transactions set amount = 5, amount_usd = 5
where id = '11111111-0000-0000-0000-000000000001';
set local role authenticated;

-- 2. period_totals: solo lo propio, sin borrados.
select is(
  (select income_usd from period_totals(current_date - 1, current_date + 1)),
  42.5::numeric, 'suma los ingresos propios sin los borrados'
);
select is(
  (select expenses_usd from period_totals(current_date - 1, current_date + 1)),
  5::numeric, 'suma los gastos propios'
);
select is(
  (select income_usd from period_totals(current_date - 30, current_date - 10)),
  0::numeric, 'un periodo sin movimientos da 0, no null'
);

reset role;
set local role anon;
select throws_ok(
  $$select * from period_totals(current_date, current_date)$$,
  '42501', null, 'anon no puede ejecutarla'
);

select * from finish();
rollback;
