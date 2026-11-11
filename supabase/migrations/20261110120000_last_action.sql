-- Última acción del usuario (revisión del 2026-11-09): una corrección por mensaje solo puede
-- tocar lo último que se anotó. Para saber si eso fue un cambio de moneda hace falta cuándo
-- se registró cada cambio; `occurred_at` no sirve porque puede estar en el pasado.

alter table exchanges add column created_at timestamptz;
-- Para los cambios viejos, la mejor aproximación es la fecha del cambio.
update exchanges set created_at = occurred_at where created_at is null;
alter table exchanges
  alter column created_at set default now(),
  alter column created_at set not null;

-- Lo último que anotó cada usuario (incluidos los deshechos): last_batch y undo_batch.
create index transactions_user_created_idx on transactions (user_id, created_at desc);
create index exchanges_user_created_idx on exchanges (user_id, created_at desc);
