-- Resúmenes semanales enviados (Fase 7).
-- Una fila por usuario y semana: el bot la inserta antes de enviar el resumen automático,
-- así un reinicio o una segunda corrida del programador no lo manda dos veces.
create table weekly_summaries (
  user_id uuid not null references users(id) on delete cascade,
  week_start date not null,  -- lunes de la semana, en la zona horaria del usuario
  sent_at timestamptz not null default now(),
  primary key (user_id, week_start),
  check (extract(isodow from week_start) = 1)
);

-- Igual que el resto: RLS sin políticas hasta la Fase 9; el bot filtra por user_id.
alter table weekly_summaries enable row level security;
