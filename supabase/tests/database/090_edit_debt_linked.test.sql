-- Los pagos de deuda no se editan desde la web ni la app (migración 20261123120000): la deuda
-- quedaría descuadrada. Un pago anulado libera su movimiento.
begin;
create extension if not exists pgtap with schema extensions;
select plan(4);

insert into auth.users (id, email) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'ana@example.com');
insert into users (id, telegram_id, display_name, auth_user_id) values
  ('00000000-0000-0000-0000-0000000000a1', 9001, 'Ana', 'aaaaaaaa-0000-0000-0000-000000000001');

insert into debts (id, user_id, direction, counterparty, currency, amount, usd_per_unit,
                   rate_source, amount_usd) values
  ('d0000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1', 'i_owe',
   'Miguel', 'USD', 20, 1, 'pivot', 20);

-- Dos gastos: el primero pagó parte de la deuda; el segundo es un gasto normal.
insert into transactions (id, user_id, account_id, currency, kind, amount, category_id,
                          usd_per_unit, rate_source, amount_usd)
select v.id::uuid, u.id, a.id, 'USD', 'expense', 5,
       (select c.id from categories c where c.user_id is null and c.name = 'comida'),
       1, 'pivot', 5
from users u
join accounts a on a.user_id = u.id and a.currency = 'USD'
join (values ('11111111-0000-0000-0000-000000000001'),
             ('11111111-0000-0000-0000-000000000002')) as v (id) on true
where u.telegram_id = 9001;

insert into debt_payments (id, user_id, debt_id, currency, amount, transaction_id) values
  ('e0000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000a1',
   'd0000000-0000-0000-0000-000000000001', 'USD', 5, '11111111-0000-0000-0000-000000000001');

set local role authenticated;
select set_config('request.jwt.claims',
  '{"sub":"aaaaaaaa-0000-0000-0000-000000000001","role":"authenticated"}', true);

select throws_ok(
  $$select edit_transaction('11111111-0000-0000-0000-000000000001', 'expense', 8,
      (select id from accounts where currency = 'USD'),
      (select id from categories where name = 'comida' and user_id is null))$$,
  '22023', 'debt_linked', 'un pago de deuda vigente no se edita'
);
select is(
  (select amount from transactions where id = '11111111-0000-0000-0000-000000000001'),
  5::numeric, 'el pago queda como estaba'
);
select is(
  edit_transaction('11111111-0000-0000-0000-000000000002', 'expense', 8,
    (select id from accounts where currency = 'USD'),
    (select id from categories where name = 'comida' and user_id is null)),
  1, 'un gasto sin deuda se sigue editando'
);

-- Con el pago anulado (Deshacer en el bot), el movimiento ya no está ligado a la deuda.
reset role;
update debt_payments set deleted_at = now() where id = 'e0000000-0000-0000-0000-000000000001';
set local role authenticated;
select is(
  edit_transaction('11111111-0000-0000-0000-000000000001', 'expense', 8,
    (select id from accounts where currency = 'USD'),
    (select id from categories where name = 'comida' and user_id is null)),
  1, 'con el pago anulado el movimiento vuelve a ser editable'
);

select * from finish();
rollback;
