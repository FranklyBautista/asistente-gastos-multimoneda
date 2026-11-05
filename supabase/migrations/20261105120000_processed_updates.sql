-- Updates de Telegram ya recibidos (Fase 8, ADR 0011).
-- Telegram puede entregar dos veces el mismo update (una respuesta del webhook que se pierde,
-- o un reinicio en polling antes de confirmar el offset). El bot reserva el update_id antes de
-- procesarlo y descarta los repetidos, así un mensaje no se anota dos veces.
-- update_id es único por bot, no global: por eso la clave incluye bot_id.
create table processed_updates (
  bot_id bigint not null,
  update_id bigint not null,
  received_at timestamptz not null default now(),
  primary key (bot_id, update_id)
);

-- Telegram guarda los updates pendientes 24 h; el bot borra las filas de más de 2 días.
create index processed_updates_received_at_idx on processed_updates (received_at);

-- Igual que el resto: RLS sin políticas; solo el bot (dueño de la tabla) la usa.
alter table processed_updates enable row level security;
