-- Datos de desarrollo local (solo se cargan con `supabase db reset`).
-- Las categorías globales y las cuentas por defecto vienen de la migración inicial.
insert into users (telegram_id, display_name)
values (1, 'Usuario de desarrollo');
