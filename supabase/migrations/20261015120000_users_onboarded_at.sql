-- Marca cuándo el usuario terminó el onboarding de /start (Fase 2).
-- Null = todavía no eligió moneda por defecto, fuente de Bs y zona horaria.
alter table users add column onboarded_at timestamptz;
